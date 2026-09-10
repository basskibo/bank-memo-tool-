import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Unit tests must not spawn mlx_lm / mlx_vlm.
os.environ["POC_MLX_AUTOSWAP"] = "0"


@pytest.fixture(autouse=True)
def _reset_mlx_chat_model_memo():
    """`src.llm_client._last_mlx_chat_model` is a module global set after a successful mlx chat.
    Without this reset it leaks between tests and makes runtime-label assertions order-dependent."""
    import src.llm_client as _llm

    _llm._last_mlx_chat_model = None
    yield
    _llm._last_mlx_chat_model = None


@pytest.fixture(autouse=True)
def _no_real_process_kills(monkeypatch):
    """Safety net: no unit test may signal a real OS process or sleep on a memory settle.
    `reap_stray_mlx_servers` shells out to pgrep and would SIGTERM a developer's running portal
    server; `_settle_after_unload` sleeps 3s. Tests that exercise the swap logic re-patch the
    specific internals they assert on."""
    import src.llm_client as _llm
    import src.mlx_servers as _ms

    monkeypatch.setattr(_ms, "reap_stray_mlx_servers", lambda keep_ports=None: [], raising=False)
    monkeypatch.setattr(_ms, "_all_mlx_server_pids", lambda: {}, raising=False)
    monkeypatch.setattr(_ms, "_settle_after_unload", lambda: None, raising=False)
    monkeypatch.setattr(_llm, "_restart_mlx_server_for", lambda url: None, raising=False)


@pytest.fixture(autouse=True)
def _neutralize_mlx_http_lock(monkeypatch):
    """`MLX_HTTP_LOCK` takes a real cross-process flock. In tests the HTTP call is mocked, so the
    lock is pure overhead — and it will block for real if a portal/run_demo process on this
    machine is holding it. Swap it for a no-op context manager."""
    import contextlib

    from src.agents import vision_extractor as _ve
    import src.agents.document_ingestor as _di
    import src.llm_client as _llm

    noop = contextlib.nullcontext()
    monkeypatch.setattr(_llm, "MLX_HTTP_LOCK", noop, raising=False)
    monkeypatch.setattr(_di, "MLX_HTTP_LOCK", noop, raising=False)
    monkeypatch.setattr(_ve, "MLX_HTTP_LOCK", noop, raising=False)
