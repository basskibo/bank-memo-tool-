"""
Tanak wrapper oko LLM poziva, da agenti ne zavise direktno od jednog provajdera.
Podržava dva providera (SPEC.md sekcija 8 — "konfigurabilno"), izabrana preko POC_LLM_PROVIDER:
  - "ollama": lokalni ili mrežni Ollama server (npr. onaj koji tim već koristi u drugom projektu)
  - "api": Anthropic API (default)
Pozivaoci (financial_wizard.py, narrative_synthesizer.py) koriste samo complete_json() i ne znaju
koji je provider aktivan.
"""
import json
import re

from src.config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

OLLAMA_TIMEOUT_SECONDS = 180  # manji lokalni modeli (npr. qwen2.5:3b) mogu biti spori na dužim dokumentima


class LLMNotConfigured(RuntimeError):
    pass


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

    obj, _ = json.JSONDecoder().raw_decode(candidate, start)
    return obj


def masked_key_preview() -> str:
    """Bezbedan prikaz Anthropic ključa za dijagnostiku — nikad ne otkriva pun ključ."""
    if not ANTHROPIC_API_KEY:
        return "(nije podešen)"
    key = ANTHROPIC_API_KEY.strip()
    if key != ANTHROPIC_API_KEY:
        return f"{key[:10]}... (dužina {len(ANTHROPIC_API_KEY)} — PAŽNJA: ima whitespace na krajevima)"
    if len(key) < 15:
        return f"'{key}' (dužina {len(key)} — izgleda prekratko za pravi ključ, možda je placeholder?)"
    return f"{key[:10]}...{key[-4:]} (dužina {len(key)})"


def active_provider_summary() -> str:
    if LLM_PROVIDER == "ollama":
        return f"ollama @ {OLLAMA_BASE_URL} (model: {OLLAMA_MODEL})"
    return f"api / anthropic (model: {LLM_MODEL}, ključ: {masked_key_preview()})"


def check_provider_ready() -> None:
    """Brza provera pre nego što pipeline krene — bolje pući odmah nego posle pola dokumenta."""
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
                "OLLAMA_BASE_URL tačan u poc/.env, i da li Ollama servis radi na toj adresi."
            ) from exc

        available_models = [m.get("name", "") for m in resp.json().get("models", [])]
        if OLLAMA_MODEL not in available_models and not any(
            m.startswith(OLLAMA_MODEL.split(":")[0]) for m in available_models
        ):
            raise LLMNotConfigured(
                f"Model '{OLLAMA_MODEL}' nije pronađen na {OLLAMA_BASE_URL}.\n"
                f"Dostupni modeli na tom serveru: {available_models or '(nijedan)'}\n"
                "Podesi OLLAMA_MODEL u poc/.env na jedan od dostupnih, ili povuci model sa "
                f"'ollama pull {OLLAMA_MODEL}' na serveru."
            )
    elif not ANTHROPIC_API_KEY:
        raise LLMNotConfigured(
            "ANTHROPIC_API_KEY nije podešen. Postavi ga u poc/.env, ili prebaci "
            "POC_LLM_PROVIDER=ollama ako koristiš lokalni/mrežni Ollama server. Vidi README.md."
        )


def _complete_json_ollama(system: str, user: str) -> dict | list:
    import requests

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": "json",  # primorava Ollama da vrati validan JSON
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise LLMNotConfigured(
            f"Poziv ka Ollama serveru ({OLLAMA_BASE_URL}, model {OLLAMA_MODEL}) nije uspeo: {exc}"
        ) from exc

    content = resp.json()["message"]["content"]
    return _extract_json(content)


def _complete_json_anthropic(system: str, user: str, max_tokens: int) -> dict | list:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as exc:
        raise LLMNotConfigured(
            f"Anthropic API je odbio ključ (401 - invalid API key).\n"
            f"Ključ koji se trenutno koristi: {masked_key_preview()}\n\n"
            "Najčešći uzroci:\n"
            "  1. U poc/.env je ostao placeholder iz .env.example (sk-ant-...) umesto pravog ključa\n"
            "  2. Ključ je zalepljen sa navodnicima ili razmakom oko '=' u .env fajlu\n"
            "  3. Ključ je za drugi provajder/projekat, istekao je ili je opozvan na "
            "console.anthropic.com\n\n"
            "Ili: podesi POC_LLM_PROVIDER=ollama u poc/.env ako imaš pristup Ollama serveru."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise LLMNotConfigured(
            f"Anthropic API je vratio grešku: {exc.status_code} — {exc.message}"
        ) from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json(text)


def complete_json(system: str, user: str, max_tokens: int = 4096) -> dict | list:
    """Pozove aktivni LLM provider (POC_LLM_PROVIDER) sa system+user promptom, parsira JSON."""
    if LLM_PROVIDER == "ollama":
        return _complete_json_ollama(system, user)
    return _complete_json_anthropic(system, user, max_tokens)
