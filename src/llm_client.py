"""
Tanak wrapper oko LLM poziva, da agenti ne zavise direktno od jednog provajdera.
Podržava tri providera (SPEC.md sekcija 8 — "konfigurabilno"), izabrana preko POC_LLM_PROVIDER:
  - "mlx": mlx_lm.server OpenAI-compatible HTTP (/v1/chat/completions) — bez import mlx
  - "ollama": lokalni ili mrežni Ollama server
  - "api": Anthropic API (default)
Pozivaoci (financial_wizard.py, narrative_synthesizer.py) koriste samo complete_json() i ne znaju
koji je provider aktivan.
"""
import fcntl
import json
import os
import re
import threading
import time
from pathlib import Path

from src.config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    MLX_BASE_URL,
    MLX_MODEL,
    MLX_VISION_BASE_URL,
    MLX_VISION_MODEL,
    OCR_ENGINE,
    OLLAMA_BASE_URL,
    OLLAMA_FORCE_VISION_UNLOAD,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
    mlx_autoswap_enabled,
)
from src.logging_setup import get_logger

log = get_logger("llm")


class _MlxHttpLock:
    """Serialize mlx HTTP across threads *and* processes (portal + run_demo).

    14B and VL can both stay loaded on :8080 / :8081, but one GPU should not
    prefill two requests at once (`in_flight=2` → 40s+ TTFT).
    """

    def __init__(self) -> None:
        self._thread = threading.Lock()
        self._fh = None
        self._path = Path(
            os.environ.get("MLX_HTTP_LOCKFILE", "")
            or Path(os.environ.get("TMPDIR", "/tmp")) / "bank-memo-mlx.lock"
        )

    # A crashed/hung holder must not block the pipeline forever — after this many seconds we
    # log and proceed without the cross-process lock (the thread lock still holds).
    _ACQUIRE_TIMEOUT_SECONDS = 90

    def __enter__(self):
        self._thread.acquire()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self._path, "a+")
            deadline = time.monotonic() + self._ACQUIRE_TIMEOUT_SECONDS
            while True:
                try:
                    fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        log.warning(
                            "MLX HTTP lock still held after %ss — proceeding without the "
                            "cross-process lock", self._ACQUIRE_TIMEOUT_SECONDS,
                        )
                        break
                    time.sleep(0.25)
        except Exception:
            if self._fh is not None:
                self._fh.close()
                self._fh = None
            self._thread.release()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._fh is not None:
                fcntl.flock(self._fh, fcntl.LOCK_UN)
                self._fh.close()
        finally:
            self._fh = None
            self._thread.release()


MLX_HTTP_LOCK = _MlxHttpLock()

OLLAMA_TIMEOUT_SECONDS = 180  # manji lokalni modeli (npr. qwen2.5:3b) mogu biti spori na dužim dokumentima
MLX_TIMEOUT_SECONDS = 180
MLX_LM_SERVER_START_CMD = (
    f".venv/bin/python -m mlx_lm server --model {MLX_MODEL} "
    f"--port {MLX_BASE_URL.rsplit(':', 1)[-1] or '8080'}"
)
MLX_VLM_SERVER_START_CMD = (
    f".venv/bin/python -m mlx_vlm server --model {MLX_VISION_MODEL} "
    f"--port {MLX_VISION_BASE_URL.rsplit(':', 1)[-1] or '8081'} --host 127.0.0.1"
)
# Backward-compatible alias used in older error strings / tests.
MLX_SERVER_START_CMD = MLX_LM_SERVER_START_CMD
# Shared with vision OCR so Ollama does not reload the VL weights when extract starts.
# 12288 + a full-page image is what left qwen2.5vl:7b at 100% GPU then Stopping... on Mini.
OLLAMA_VISION_NUM_CTX = 8192
# Text-only extract (tesseract path). 4096 silently truncates noisy OCR JSON.
OLLAMA_EXTRACT_NUM_CTX = 16384
_PLACEHOLDER_API_KEYS = {"sk-ant-...", "sk-ant-"}


class LLMNotConfigured(RuntimeError):
    pass


def ollama_extract_model() -> str:
    """Model for complete_json. Vision OCR reuses the VL model so the GPU never swaps mid-pipeline."""
    if OCR_ENGINE == "vision":
        return OLLAMA_VISION_MODEL
    return OLLAMA_MODEL


def ollama_extract_num_ctx() -> int:
    if OCR_ENGINE == "vision":
        return OLLAMA_VISION_NUM_CTX
    return OLLAMA_EXTRACT_NUM_CTX


def active_chat_model() -> str:
    if LLM_PROVIDER == "ollama":
        return ollama_extract_model()
    if LLM_PROVIDER == "mlx":
        # Extract always uses MLX_MODEL. VL is only for scanned-page OCR in the ingestor.
        return MLX_MODEL
    return LLM_MODEL


_last_mlx_chat_model: str | None = None


def short_model_id(model: str) -> str:
    """Drop org prefix (mlx-community/Qwen2.5-14B-Instruct-4bit → Qwen2.5-14B-Instruct-4bit)."""
    return (model or "").rsplit("/", 1)[-1]


def last_mlx_chat_model() -> str | None:
    return _last_mlx_chat_model


def remember_mlx_chat_model(model: str) -> None:
    global _last_mlx_chat_model
    _last_mlx_chat_model = model


def unload_ollama_model(model: str) -> None:
    """Ask Ollama to drop a resident model. Never call this while a generate/chat is in flight."""
    import requests

    if not model:
        return
    log.info("Unload request keep_alive=0 model=%s", model)
    try:
        requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        log.warning("Unload request failed for %s: %s", model, exc)
        return


def release_vision_model_for_extract() -> None:
    """Default vision path keeps the VL model loaded for Financial Wizard (no swap, no /api/ps).

    Optional: OLLAMA_FORCE_VISION_UNLOAD=1 posts keep_alive=0 once then sleeps — no poll loop.
    """
    if LLM_PROVIDER != "ollama" or OCR_ENGINE != "vision":
        return
    if not OLLAMA_FORCE_VISION_UNLOAD:
        log.info("Reusing vision model %s for extract (no unload)", OLLAMA_VISION_MODEL)
        return
    log.info(
        "Force-unload vision model %s after OCR (OLLAMA_FORCE_VISION_UNLOAD=1)",
        OLLAMA_VISION_MODEL,
    )
    unload_ollama_model(OLLAMA_VISION_MODEL)
    time.sleep(2)


def _resolved_anthropic_key() -> str | None:
    """None if the env value is missing, blank, or still the .env.example placeholder."""
    key = (ANTHROPIC_API_KEY or "").strip()
    if not key or key in _PLACEHOLDER_API_KEYS or key.endswith("..."):
        return None
    return key


def _missing_anthropic_key_message() -> str:
    return (
        "ANTHROPIC_API_KEY nije podešen. Kopiraj .env.example u .env u korenu projekta, "
        "pa ili upiši pravi ključ, ili prebaci POC_LLM_PROVIDER=mlx / ollama ako "
        "koristiš lokalni model. Vidi README.md. Streamlit mora da se restartuje "
        "posle izmene .env."
    )


def _extract_json(text: str) -> dict | list:
    """
    LLM ume da vrati JSON umotan u markdown fence, sa objašnjenjem PRE ili POSLE JSON bloka, ili
    oboje — čak i kad prompt eksplicitno traži "samo JSON". Umesto da zahtevamo da je ceo odgovor
    čist JSON (što je pucalo na Anthropic odgovorima tipa "{...}\n\nNote: ..."), pronađemo prvi
    '{' ili '[' u tekstu i parsiramo JEDNU validnu JSON vrednost od te tačke pomoću raw_decode,
    ignorišući sve što dolazi posle nje (umesto da to izazove "Extra data" grešku).
    """
    fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else text

    start = next((i for i, ch in enumerate(candidate) if ch in "{["), None)
    if start is None:
        raise ValueError(f"Model nije vratio nikakav JSON objekat/niz: {text!r}")

    try:
        obj, _ = json.JSONDecoder().raw_decode(candidate, start)
        return obj
    except json.JSONDecodeError:
        # Lokalni modeli (npr. mlx 14B-4bit) povremeno vrate ODSEČEN JSON — string presečen na
        # max_tokens, nedostaje zatvarajuća zagrada. Umesto da ceo dokument padne, probaj da
        # "zatvoriš" ono što je stiglo i parsiraj to. Vidi FINDINGS.md.
        repaired = _repair_truncated_json(candidate[start:])
        if repaired is not None:
            log.warning("Recovered a truncated JSON response by closing it (%s chars)", len(repaired))
            return json.loads(repaired)
        raise


def _repair_truncated_json(s: str) -> str | None:
    """Best-effort close of a JSON value cut off mid-generation. Returns None if unrecoverable."""
    buf: list[str] = []
    stack: list[str] = []
    in_str = False
    escaped = False
    for ch in s:
        if in_str:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            buf.append(ch)
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
            buf.append(ch)
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()
            buf.append(ch)
        else:
            buf.append(ch)
    if in_str:
        buf.append('"')  # close the dangling string
    # drop a trailing partial key/value like `, "source_snippet": "` → `,`... then strip trailing comma
    text = "".join(buf)
    text = re.sub(r",\s*(\"[^\"]*\"\s*:?\s*)?$", "", text)
    text += "".join(reversed(stack))
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        return None


def masked_key_preview() -> str:
    """Bezbedan prikaz Anthropic ključa za dijagnostiku — nikad ne otkriva pun ključ."""
    key = _resolved_anthropic_key()
    if not key:
        if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.strip() != ANTHROPIC_API_KEY:
            stripped = ANTHROPIC_API_KEY.strip()
            return (
                f"{stripped[:10]}... (dužina {len(ANTHROPIC_API_KEY)} — PAŽNJA: ima whitespace na krajevima)"
            )
        return "(nije podešen)"
    if len(key) < 15:
        return f"'{key}' (dužina {len(key)} — izgleda prekratko za pravi ključ, možda je placeholder?)"
    return f"{key[:10]}...{key[-4:]} (dužina {len(key)})"


def provider_setup_error() -> str | None:
    """Cheap local check (no network) for the review UI. None if a call is worth attempting."""
    if LLM_PROVIDER in ("ollama", "mlx"):
        return None
    if LLM_PROVIDER != "api":
        return (
            f"Unknown POC_LLM_PROVIDER={LLM_PROVIDER!r}. "
            "Use mlx, ollama, or api. Restart Streamlit after changing `.env`."
        )
    if not _resolved_anthropic_key():
        return (
            "Anthropic API key isn't set. Copy `.env.example` to `.env` in the project root, "
            "then either add a real `ANTHROPIC_API_KEY` or set `POC_LLM_PROVIDER=mlx` / `ollama`. "
            "Restart Streamlit after changing `.env`."
        )
    return None


def active_provider_summary() -> str:
    if OCR_ENGINE == "vision":
        extra = f", OCR={OCR_ENGINE}/{OLLAMA_VISION_MODEL}"
    elif OCR_ENGINE == "mlx_vision":
        extra = (
            f", OCR={OCR_ENGINE}/{MLX_VISION_MODEL} @ {MLX_VISION_BASE_URL}"
        )
    else:
        extra = f", OCR={OCR_ENGINE}"
    if LLM_PROVIDER == "ollama":
        return f"ollama @ {OLLAMA_BASE_URL} (chat: {ollama_extract_model()}{extra})"
    if LLM_PROVIDER == "mlx":
        return f"mlx @ {MLX_BASE_URL} (chat: {active_chat_model()}{extra})"
    return f"api / anthropic (model: {LLM_MODEL}, ključ: {masked_key_preview()}{extra})"


def _mlx_text_server_down_message(exc: Exception) -> str:
    return (
        f"Cannot reach mlx_lm.server at {MLX_BASE_URL}.\n"
        f"Error: {exc}\n\n"
        "Start the text extract server (leave VL running on 8081):\n"
        f"  {MLX_LM_SERVER_START_CMD}\n"
        "Or: scripts/start_mlx_servers.sh"
    )


def _mlx_same_url_message() -> str:
    return (
        "MLX_BASE_URL and MLX_VISION_BASE_URL are the same "
        f"({MLX_BASE_URL}). One process cannot be both 14B Instruct and VL 7B.\n"
        "Keep extract on :8080 and OCR on :8081:\n"
        f"  {MLX_LM_SERVER_START_CMD}\n"
        f"  {MLX_VLM_SERVER_START_CMD}"
    )


def _probe_mlx_models(url: str) -> None:
    import requests

    resp = requests.get(f"{url}/v1/models", timeout=10)
    resp.raise_for_status()


def _mlx_chat_targets() -> list[tuple[str, str]]:
    """Prefer 14B for text; if that process is gone, VL on :8081 can still chat."""
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, model in (
        (MLX_BASE_URL, MLX_MODEL),
        (MLX_VISION_BASE_URL, MLX_VISION_MODEL),
    ):
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        targets.append((url, model))
    return targets


def _mlx_reachable(url: str) -> tuple[bool, Exception | None]:
    import requests

    try:
        _probe_mlx_models(url)
        return True, None
    except requests.exceptions.RequestException as exc:
        return False, exc


def check_provider_ready() -> None:
    """Brza provera pre nego što pipeline krene — bolje pući odmah nego posle pola dokumenta."""
    if LLM_PROVIDER == "mlx":
        if OCR_ENGINE == "mlx_vision" and MLX_BASE_URL == MLX_VISION_BASE_URL:
            raise LLMNotConfigured(_mlx_same_url_message())
        if mlx_autoswap_enabled():
            log.info("MLX autoswap on — 14B/VL start on demand")
            return
        text_ok, text_exc = _mlx_reachable(MLX_BASE_URL)
        if OCR_ENGINE == "mlx_vision":
            vision_ok, vision_exc = _mlx_reachable(MLX_VISION_BASE_URL)
            if not text_ok and not vision_ok:
                raise LLMNotConfigured(
                    "No MLX server is reachable for chat.\n"
                    f"  {MLX_BASE_URL}: {text_exc}\n"
                    f"  {MLX_VISION_BASE_URL}: {vision_exc}\n\n"
                    f"Start 14B:\n  {MLX_LM_SERVER_START_CMD}\n"
                    f"Start VL:\n  {MLX_VLM_SERVER_START_CMD}\n"
                    "Or: scripts/start_mlx_servers.sh"
                )
            if not text_ok:
                log.warning(
                    "mlx_lm at %s is down (%s) — extract/memo will use VL at %s",
                    MLX_BASE_URL,
                    text_exc,
                    MLX_VISION_BASE_URL,
                )
            if not vision_ok:
                log.warning(
                    "mlx_vlm at %s is down (%s) — scanned pages will fail OCR",
                    MLX_VISION_BASE_URL,
                    vision_exc,
                )
            return
        if not text_ok:
            raise LLMNotConfigured(_mlx_text_server_down_message(text_exc)) from text_exc
        return

    if LLM_PROVIDER == "ollama":
        import requests

        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise LLMNotConfigured(
                f"Ne mogu da se povežem na Ollama server {OLLAMA_BASE_URL}.\n"
                f"Greška: {exc}\n\n"
                "Proveri: da li je server dostupan sa ove mašine/mreže (VPN?), da li je "
                "OLLAMA_BASE_URL tačan u .env, i da li Ollama servis radi na toj adresi."
            ) from exc

        available_models = [m.get("name", "") for m in resp.json().get("models", [])]
        needed = ollama_extract_model()
        if needed not in available_models and not any(
            m.startswith(needed.split(":")[0]) for m in available_models
        ):
            raise LLMNotConfigured(
                f"Model '{needed}' nije pronađen na {OLLAMA_BASE_URL}.\n"
                f"Dostupni modeli na tom serveru: {available_models or '(nijedan)'}\n"
                "Podesi model u .env na jedan od dostupnih, ili povuci model sa "
                f"'ollama pull {needed}' na serveru."
            )
        return

    if LLM_PROVIDER != "api":
        raise LLMNotConfigured(
            f"Unknown POC_LLM_PROVIDER={LLM_PROVIDER!r}. Use mlx, ollama, or api."
        )
    if not _resolved_anthropic_key():
        raise LLMNotConfigured(_missing_anthropic_key_message())


def _complete_json_ollama(system: str, user: str) -> dict | list:
    import requests

    model = ollama_extract_model()
    num_ctx = ollama_extract_num_ctx()
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": "json",
                    "stream": False,
                    "keep_alive": "10m",
                    "options": {"num_ctx": num_ctx, "temperature": 0},
                },
                timeout=OLLAMA_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return _extract_json(content)
        except requests.exceptions.Timeout as exc:
            last_error = exc
            log.warning(
                "Ollama chat timeout (attempt %s/3) model=%s — retry without unload",
                attempt + 1,
                model,
            )
        except requests.exceptions.RequestException as exc:
            raise LLMNotConfigured(
                f"Poziv ka Ollama serveru ({OLLAMA_BASE_URL}, model {model}) nije uspeo: {exc}"
            ) from exc
    raise LLMNotConfigured(
        f"Poziv ka Ollama serveru ({OLLAMA_BASE_URL}, model {model}) nije uspeo: {last_error}"
    )


def _complete_json_anthropic(system: str, user: str, max_tokens: int) -> dict | list:
    import anthropic

    api_key = _resolved_anthropic_key()
    if not api_key:
        raise LLMNotConfigured(_missing_anthropic_key_message())

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except TypeError as exc:
        # Newer anthropic SDKs raise TypeError (not AuthenticationError) when no
        # api_key/auth_token/credentials can be resolved at request-build time.
        message = str(exc).lower()
        if "authentication" in message or "api_key" in message or "x-api-key" in message:
            raise LLMNotConfigured(_missing_anthropic_key_message()) from exc
        raise
    except anthropic.AuthenticationError as exc:
        raise LLMNotConfigured(
            f"Anthropic API je odbio ključ (401 - invalid API key).\n"
            f"Ključ koji se trenutno koristi: {masked_key_preview()}\n\n"
            "Najčešći uzroci:\n"
            "  1. U .env je ostao placeholder iz .env.example (sk-ant-...) umesto pravog ključa\n"
            "  2. Ključ je zalepljen sa navodnicima ili razmakom oko '=' u .env fajlu\n"
            "  3. Ključ je za drugi provajder/projekat, istekao je ili je opozvan na "
            "console.anthropic.com\n\n"
            "Ili: podesi POC_LLM_PROVIDER=mlx ili ollama u .env za lokalni model."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise LLMNotConfigured(
            f"Anthropic API je vratio grešku: {exc.status_code} — {exc.message}"
        ) from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json(text)


def _mlx_message_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise LLMNotConfigured(f"mlx_lm.server returned no choices: {payload!r}")
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def _complete_json_mlx(system: str, user: str, max_tokens: int) -> dict | list:
    """OpenAI-compatible chat. Prefers MLX_MODEL on :8080; falls back to VL if 14B died."""
    import requests

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if mlx_autoswap_enabled():
        from src.mlx_servers import ensure_mlx_text

        try:
            ensure_mlx_text()
        except RuntimeError as exc:
            raise LLMNotConfigured(str(exc)) from exc
        targets = [(MLX_BASE_URL, MLX_MODEL)]
    else:
        targets = _mlx_chat_targets()
    last_unreach: Exception | None = None
    last_url = ""
    last_model = ""
    for restart_pass in range(2):
        for url, model in targets:
            last_url, last_model = url, model
            try:
                return _post_mlx_chat(url, model, messages, max_tokens)
            except requests.exceptions.ConnectionError as exc:
                last_unreach = exc
                log.warning("mlx chat unreachable %s model=%s — %s", url, model, exc)
                continue
        # Every target dropped the connection. On this box that is almost always the mlx worker
        # being OOM-killed mid-generation. Try one restart of a fresh single server, then retry.
        if restart_pass == 0 and mlx_autoswap_enabled():
            log.warning("All mlx targets dropped — restarting the server once (likely OOM)")
            _restart_mlx_server_for(last_url)
            time.sleep(3)
            continue
        break
    raise LLMNotConfigured(
        f"mlx server ({last_url}, model {last_model}) keeps dropping the connection mid-request: "
        f"{last_unreach}\n"
        "On a 24 GB Mini this is almost always OUT OF MEMORY. To fix:\n"
        "  • close the browser / Cursor / Claude desktop while a run is active\n"
        "  • keep MLX_MODEL on the 7B (not 14B) in .env\n"
        "  • or POC_OCR_ENGINE=mlx_vision_extract — scans then never load a text model\n"
        f"Manual restart:\n  {MLX_LM_SERVER_START_CMD}\n  {MLX_VLM_SERVER_START_CMD}"
    )


def _post_mlx_chat(
    url: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
) -> dict | list:
    import requests

    endpoint = f"{url}/v1/chat/completions"
    base_payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    last_error: Exception | None = None
    use_response_format = True
    msgs = list(messages)
    for attempt in range(3):
        payload = dict(base_payload)
        payload["messages"] = msgs
        if use_response_format:
            payload["response_format"] = {"type": "json_object"}
        try:
            with MLX_HTTP_LOCK:
                resp = requests.post(endpoint, json=payload, timeout=MLX_TIMEOUT_SECONDS)
            if resp.status_code == 400 and use_response_format:
                log.warning("mlx server rejected response_format; retrying without it")
                use_response_format = False
                continue
            resp.raise_for_status()
            remember_mlx_chat_model(model)
            content = _mlx_message_content(resp.json())
            try:
                obj = _extract_json(content)
                log.info("mlx chat ok url=%s model=%s", url, model)
                return obj
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                log.warning(
                    "MLX chat returned unparseable JSON (attempt %s/3) — %s", attempt + 1, exc,
                )
                # nudge the model on the next attempt
                msgs = list(messages) + [
                    {"role": "assistant", "content": content[:2000]},
                    {"role": "user", "content":
                        "That response was not valid JSON (truncated or malformed). Reply again "
                        "with ONLY a single minified JSON value, nothing else, and keep every "
                        "string short."},
                ]
                continue
        except requests.exceptions.Timeout as exc:
            last_error = exc
            log.warning(
                "MLX chat timeout (attempt %s/3) url=%s model=%s",
                attempt + 1,
                url,
                model,
            )
        except requests.exceptions.ConnectionError:
            # Server accepted the socket then dropped it mid-generation. Let the caller
            # (`_complete_json_mlx`) decide: fall back to another server, or restart + retry.
            raise
        except requests.exceptions.RequestException as exc:
            raise LLMNotConfigured(
                f"Call to mlx server ({url}, model {model}) failed: {exc}\n"
                f"Start text model:\n  {MLX_LM_SERVER_START_CMD}\n"
                f"Start VL:\n  {MLX_VLM_SERVER_START_CMD}"
            ) from exc
    raise LLMNotConfigured(
        f"Call to mlx server ({url}, model {model}) failed: {last_error}"
    )


def _restart_mlx_server_for(url: str) -> None:
    """Best-effort restart of whichever mlx server owns `url` (used after an OOM drop)."""
    try:
        from src.mlx_servers import ensure_mlx_text, ensure_mlx_vision, reap_stray_mlx_servers

        reap_stray_mlx_servers(keep_ports=set())
        time.sleep(1)
        if url.rstrip("/") == MLX_VISION_BASE_URL:
            ensure_mlx_vision()
        else:
            ensure_mlx_text()
    except Exception as exc:  # noqa: BLE001 — this is a recovery path, never fatal here
        log.warning("Could not auto-restart mlx server for %s: %s", url, exc)


def complete_json(system: str, user: str, max_tokens: int = 4096) -> dict | list:
    """Pozove aktivni LLM provider (POC_LLM_PROVIDER) sa system+user promptom, parsira JSON."""
    model = active_chat_model()
    log.info("complete_json start provider=%s model=%s", LLM_PROVIDER, model)
    started = time.monotonic()
    try:
        if LLM_PROVIDER == "ollama":
            result = _complete_json_ollama(system, user)
        elif LLM_PROVIDER == "mlx":
            result = _complete_json_mlx(system, user, max_tokens)
        elif LLM_PROVIDER == "api":
            result = _complete_json_anthropic(system, user, max_tokens)
        else:
            raise LLMNotConfigured(
                f"Unknown POC_LLM_PROVIDER={LLM_PROVIDER!r}. Use mlx, ollama, or api."
            )
    except LLMNotConfigured as exc:
        log.error(
            "complete_json failed provider=%s model=%s (%.1fs): %s",
            LLM_PROVIDER,
            model,
            time.monotonic() - started,
            exc,
        )
        raise
    except Exception:
        log.exception(
            "complete_json failed provider=%s model=%s (%.1fs)",
            LLM_PROVIDER,
            model,
            time.monotonic() - started,
        )
        raise
    log.info(
        "complete_json done provider=%s model=%s (%.1fs)",
        LLM_PROVIDER,
        model,
        time.monotonic() - started,
    )
    return result
