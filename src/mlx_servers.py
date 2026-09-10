"""Start/stop mlx_lm and mlx_vlm so Mini 24 GB only holds the model currently needed."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from src.config import (
    MLX_BASE_URL,
    MLX_MODEL,
    MLX_VISION_BASE_URL,
    MLX_VISION_MODEL,
    mlx_autoswap_enabled,
)
from src.logging_setup import get_logger

log = get_logger("mlx_servers")

_SWAP_LOCK = threading.Lock()
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOAD_TIMEOUT_SECONDS = 180
OnStatus = Callable[[str], None] | None


def _port(url: str, default: int) -> int:
    parsed = urlparse(url)
    if parsed.port:
        return parsed.port
    return 443 if parsed.scheme == "https" else default


def _text_port() -> int:
    return _port(MLX_BASE_URL, 8080)


def _vision_port() -> int:
    return _port(MLX_VISION_BASE_URL, 8081)


def _listener_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for token in result.stdout.split():
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid != os.getpid():
            pids.append(pid)
    return pids


def _all_mlx_server_pids() -> dict[int, str]:
    """Every running `python -m mlx_lm server` / `mlx_vlm server` on this machine → its cmdline.
    These leak easily: a crashed portal, a manual `python -m mlx_vlm server` in a terminal, a
    duplicate on a port that never got cleaned. Each one holds ~5-8 GB of Metal memory.
    """
    result = subprocess.run(
        ["pgrep", "-fl", "-a" if sys.platform == "linux" else "-lf", "mlx_"],
        capture_output=True, text=True, check=False,
    )
    if not result.stdout:
        result = subprocess.run(["pgrep", "-fl", "mlx_"], capture_output=True, text=True, check=False)
    out: dict[int, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid_s, cmd = parts
        if ("mlx_lm server" not in cmd and "mlx_vlm server" not in cmd and
                "mlx_lm.server" not in cmd and "mlx_vlm.server" not in cmd):
            continue
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid != os.getpid():
            out[pid] = cmd
    return out


def reap_stray_mlx_servers(keep_ports: set[int] | None = None) -> list[int]:
    """Kill mlx model servers that are NOT the listener on one of `keep_ports`. Returns the pids
    killed. Called before we start a server so the Mini never holds two 7B+ models at once."""
    keep_ports = keep_ports or set()
    keep_pids: set[int] = set()
    for p in keep_ports:
        keep_pids.update(_listener_pids(p))
    killed: list[int] = []
    for pid, cmd in _all_mlx_server_pids().items():
        if pid in keep_pids:
            continue
        log.warning("Reaping stray mlx server pid=%s (%s)", pid, cmd[:120])
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        killed.append(pid)
    if killed:
        deadline = time.time() + 15
        while time.time() < deadline and any(_pid_alive(p) for p in killed):
            time.sleep(0.3)
        for pid in killed:
            if _pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    return killed


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _healthy(url: str) -> bool:
    import requests

    try:
        resp = requests.get(f"{url.rstrip('/')}/v1/models", timeout=3)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def _stop_port(port: int) -> None:
    pids = _listener_pids(port)
    if not pids:
        return
    log.info("Stopping process(es) on port %s: %s", port, pids)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    deadline = time.time() + 25
    while time.time() < deadline and _listener_pids(port):
        time.sleep(0.4)
    for pid in _listener_pids(port):
        log.warning("Force-killing PID %s on port %s", pid, port)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
    time.sleep(0.3)


def _settle_after_unload() -> None:
    """The freed model's ~5 GB of Metal/wired pages are not reclaimed the instant the process
    exits. Starting the next model too soon → it OOM-crashes on the first prefill. Give the
    kernel a moment; poll free memory if we can read it."""
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False).stdout
        page = 4096
        free = 0
        for line in out.splitlines():
            if line.startswith("Pages free:") or line.startswith("Pages inactive:"):
                free += int(line.split(":")[1].strip().rstrip(".")) * page
        if free > 6 * 1024**3:
            time.sleep(1)
            return
    except Exception:  # noqa: BLE001
        pass
    time.sleep(3)


def _wait_healthy(url: str, what: str) -> None:
    deadline = time.time() + _LOAD_TIMEOUT_SECONDS
    while time.time() < deadline:
        if _healthy(url):
            log.info("%s ready at %s", what, url)
            return
        time.sleep(1)
    raise RuntimeError(
        f"{what} did not become ready at {url} within {_LOAD_TIMEOUT_SECONDS}s. "
        "Check the mlx server terminal /tmp/bank-memo-mlx-*.log"
    )


def _spawn(args: list[str], log_name: str) -> None:
    log_path = Path(os.environ.get("TMPDIR", "/tmp")) / log_name
    handle = open(log_path, "ab")
    log.info("Starting %s (log %s)", args, log_path)
    subprocess.Popen(
        args,
        cwd=_PROJECT_ROOT,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _start_text() -> None:
    _spawn(
        [
            sys.executable,
            "-m",
            "mlx_lm",
            "server",
            "--model",
            MLX_MODEL,
            "--port",
            str(_text_port()),
        ],
        "bank-memo-mlx-lm.log",
    )


def _start_vision() -> None:
    _spawn(
        [
            sys.executable,
            "-m",
            "mlx_vlm",
            "server",
            "--model",
            MLX_VISION_MODEL,
            "--port",
            str(_vision_port()),
            "--host",
            "127.0.0.1",
        ],
        "bank-memo-mlx-vlm.log",
    )


def ensure_mlx_vision(on_status: OnStatus = None) -> None:
    """VL on :8081 for OCR. Reaps every other mlx server first so Mini holds ONE model."""
    if not mlx_autoswap_enabled():
        return
    with _SWAP_LOCK:
        if _healthy(MLX_VISION_BASE_URL) and not _listener_pids(_text_port()) and len(_all_mlx_server_pids()) <= 1:
            return
        if on_status:
            on_status("Stopping other models and loading VL 7B for OCR…")
        reap_stray_mlx_servers(keep_ports={_vision_port()})
        _stop_port(_text_port())
        _settle_after_unload()
        if not _healthy(MLX_VISION_BASE_URL):
            _start_vision()
            _wait_healthy(MLX_VISION_BASE_URL, f"mlx_vlm {MLX_VISION_MODEL}")
        else:
            log.info("VL already up at %s", MLX_VISION_BASE_URL)


def ensure_mlx_text(on_status: OnStatus = None) -> None:
    """Text model on :8080 for extract/memo. Reaps every other mlx server first."""
    if not mlx_autoswap_enabled():
        return
    with _SWAP_LOCK:
        if _healthy(MLX_BASE_URL) and not _listener_pids(_vision_port()) and len(_all_mlx_server_pids()) <= 1:
            return
        if on_status:
            on_status("Stopping other models and loading text model for extract…")
        reap_stray_mlx_servers(keep_ports={_text_port()})
        _stop_port(_vision_port())
        _settle_after_unload()
        if not _healthy(MLX_BASE_URL):
            _start_text()
            _wait_healthy(MLX_BASE_URL, f"mlx_lm {MLX_MODEL}")
        else:
            log.info("Text model already up at %s", MLX_BASE_URL)


def stop_all_mlx() -> list[int]:
    """Kill every mlx model server (both ports + strays). For a 'reset' button / shutdown."""
    with _SWAP_LOCK:
        _stop_port(_text_port())
        _stop_port(_vision_port())
        return reap_stray_mlx_servers(keep_ports=set())
