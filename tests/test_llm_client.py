import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm_client import (
    LLMNotConfigured,
    _extract_json,
    check_provider_ready,
    complete_json,
    provider_setup_error,
    short_model_id,
)


def test_extract_json_passes_valid_and_ignores_trailing_prose():
    assert _extract_json('[{"x": 1}]\n\nNote: done.') == [{"x": 1}]
    assert _extract_json('```json\n{"a": 2}\n```') == {"a": 2}


def test_extract_json_recovers_string_truncated_at_max_tokens():
    # response cut off mid-snippet (the actual 14B-4bit failure mode)
    truncated = '[{"field_name": "company_name", "value": "Misr Pharma", "source_snippet": "Legal name Misr Pharma Distr'
    out = _extract_json(truncated)
    assert out[0]["field_name"] == "company_name"
    assert out[0]["value"] == "Misr Pharma"


def test_extract_json_recovers_object_cut_after_dangling_key():
    out = _extract_json('{"a": 1, "b": "ok", "c": "')
    assert out["a"] == 1 and out["b"] == "ok"


def test_extract_json_still_raises_on_pure_garbage():
    with pytest.raises((ValueError, __import__("json").JSONDecodeError)):
        _extract_json("not json at all, no braces")


def test_short_model_id_strips_org_prefix():
    assert short_model_id("mlx-community/Qwen2.5-14B-Instruct-4bit") == (
        "Qwen2.5-14B-Instruct-4bit"
    )
    assert short_model_id("qwen2.5:14b") == "qwen2.5:14b"


def test_complete_json_missing_anthropic_key_raises_configured_error():
    with (
        patch("src.llm_client.LLM_PROVIDER", "api"),
        patch("src.llm_client.ANTHROPIC_API_KEY", None),
        pytest.raises(LLMNotConfigured, match="ANTHROPIC_API_KEY"),
    ):
        complete_json("system", "user")


def test_complete_json_placeholder_key_is_treated_as_missing():
    with (
        patch("src.llm_client.LLM_PROVIDER", "api"),
        patch("src.llm_client.ANTHROPIC_API_KEY", "sk-ant-..."),
        pytest.raises(LLMNotConfigured, match="ANTHROPIC_API_KEY"),
    ):
        complete_json("system", "user")


def test_complete_json_does_not_call_anthropic_without_a_key():
    with (
        patch("src.llm_client.LLM_PROVIDER", "api"),
        patch("src.llm_client.ANTHROPIC_API_KEY", None),
        patch("anthropic.Anthropic") as anthropic_cls,
        pytest.raises(LLMNotConfigured),
    ):
        complete_json("system", "user")
    anthropic_cls.assert_not_called()


def test_check_provider_ready_rejects_missing_api_key():
    with (
        patch("src.llm_client.LLM_PROVIDER", "api"),
        patch("src.llm_client.ANTHROPIC_API_KEY", ""),
        pytest.raises(LLMNotConfigured, match="ANTHROPIC_API_KEY"),
    ):
        check_provider_ready()


def test_provider_setup_error_for_api_without_key():
    with (
        patch("src.llm_client.LLM_PROVIDER", "api"),
        patch("src.llm_client.ANTHROPIC_API_KEY", None),
    ):
        assert provider_setup_error() is not None


def test_provider_setup_error_none_for_ollama():
    with patch("src.llm_client.LLM_PROVIDER", "ollama"):
        assert provider_setup_error() is None


def test_anthropic_auth_typeerror_is_wrapped_as_configured_error():
    fake_messages = MagicMock()
    fake_messages.create.side_effect = TypeError(
        "Could not resolve authentication method. Expected one of api_key, "
        "auth_token, or credentials to be set."
    )
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    with (
        patch("src.llm_client.LLM_PROVIDER", "api"),
        patch("src.llm_client.ANTHROPIC_API_KEY", "sk-ant-abcdefghijklmnopqrstuvwxyz"),
        patch("anthropic.Anthropic", return_value=fake_client),
        pytest.raises(LLMNotConfigured, match="ANTHROPIC_API_KEY"),
    ):
        complete_json("system", "user")


def test_release_vision_unloads_resident_model_when_forced():
    from src.llm_client import release_vision_model_for_extract

    with (
        patch("src.llm_client.OLLAMA_FORCE_VISION_UNLOAD", True),
        patch("src.llm_client.LLM_PROVIDER", "ollama"),
        patch("src.llm_client.OCR_ENGINE", "vision"),
        patch("src.llm_client.OLLAMA_VISION_MODEL", "qwen2.5vl:3b"),
        patch("src.llm_client.time.sleep"),
        patch("src.llm_client.unload_ollama_model") as unload,
    ):
        release_vision_model_for_extract()
        unload.assert_called_once_with("qwen2.5vl:3b")


def test_release_vision_is_noop_by_default():
    """Vision extract reuses the VL model — no keep_alive=0 and no /api/ps poll."""
    from src.llm_client import release_vision_model_for_extract

    with (
        patch("src.llm_client.OLLAMA_FORCE_VISION_UNLOAD", False),
        patch("src.llm_client.LLM_PROVIDER", "ollama"),
        patch("src.llm_client.OCR_ENGINE", "vision"),
        patch("src.llm_client.OLLAMA_VISION_MODEL", "qwen2.5vl:3b"),
        patch("src.llm_client.unload_ollama_model") as unload,
    ):
        release_vision_model_for_extract()
        unload.assert_not_called()


def test_complete_json_ollama_uses_vision_model_when_ocr_is_vision():
    fake = MagicMock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {"message": {"content": '{"ok": true}'}}

    with (
        patch("src.llm_client.LLM_PROVIDER", "ollama"),
        patch("src.llm_client.OCR_ENGINE", "vision"),
        patch("src.llm_client.OLLAMA_VISION_MODEL", "qwen2.5vl:7b"),
        patch("src.llm_client.OLLAMA_MODEL", "qwen2.5:7b"),
        patch("requests.post", return_value=fake) as post,
    ):
        result = complete_json("sys", "user")

    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "qwen2.5vl:7b"
    assert payload["keep_alive"] == "10m"
    assert payload["options"]["num_ctx"] == 8192
    assert result == {"ok": True}


def test_complete_json_ollama_uses_text_model_when_ocr_is_tesseract():
    fake = MagicMock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {"message": {"content": '{"ok": true}'}}

    with (
        patch("src.llm_client.LLM_PROVIDER", "ollama"),
        patch("src.llm_client.OCR_ENGINE", "tesseract"),
        patch("src.llm_client.OLLAMA_VISION_MODEL", "qwen2.5vl:7b"),
        patch("src.llm_client.OLLAMA_MODEL", "qwen2.5:7b"),
        patch("requests.post", return_value=fake) as post,
    ):
        complete_json("sys", "user")

    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "qwen2.5:7b"
    assert payload["options"]["num_ctx"] == 16384


def test_provider_setup_error_none_for_mlx():
    with patch("src.llm_client.LLM_PROVIDER", "mlx"):
        assert provider_setup_error() is None


def test_check_provider_ready_mlx_ok():
    fake = MagicMock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {"data": [{"id": "mlx-community/Qwen2.5-7B-Instruct-4bit"}]}

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "tesseract"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("requests.get", return_value=fake) as get,
    ):
        check_provider_ready()

    get.assert_called_once()
    assert get.call_args.args[0] == "http://127.0.0.1:8080/v1/models"


def test_check_provider_ready_mlx_down():
    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "tesseract"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")),
        pytest.raises(LLMNotConfigured, match="mlx_lm.server"),
    ):
        check_provider_ready()


def test_complete_json_mlx_posts_openai_chat_completions():
    fake = MagicMock()
    fake.status_code = 200
    fake.raise_for_status.return_value = None
    fake.json.return_value = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_MODEL", "mlx-community/Qwen2.5-7B-Instruct-4bit"),
        patch("requests.post", return_value=fake) as post,
        patch("anthropic.Anthropic") as anthropic_cls,
    ):
        result = complete_json("sys", "user")

    anthropic_cls.assert_not_called()
    assert post.call_args.args[0] == "http://127.0.0.1:8080/v1/chat/completions"
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "mlx-community/Qwen2.5-7B-Instruct-4bit"
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 4096
    assert payload["stream"] is False
    assert result == {"ok": True}


def test_complete_json_mlx_retries_without_response_format_on_400():
    bad = MagicMock()
    bad.status_code = 400
    ok = MagicMock()
    ok.status_code = 200
    ok.raise_for_status.return_value = None
    ok.json.return_value = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_MODEL", "mlx-community/Qwen2.5-7B-Instruct-4bit"),
        patch("requests.post", side_effect=[bad, ok]) as post,
    ):
        result = complete_json("sys", "user")

    assert result == {"ok": True}
    assert post.call_count == 2
    assert "response_format" in post.call_args_list[0].kwargs["json"]
    assert "response_format" not in post.call_args_list[1].kwargs["json"]


def test_complete_json_mlx_keeps_text_model_when_ocr_is_mlx_vision():
    fake = MagicMock()
    fake.status_code = 200
    fake.raise_for_status.return_value = None
    fake.json.return_value = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "mlx_vision"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_MODEL", "mlx-community/Qwen2.5-14B-Instruct-4bit"),
        patch(
            "src.llm_client.MLX_VISION_MODEL",
            "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
        ),
        patch("requests.post", return_value=fake) as post,
    ):
        result = complete_json("sys", "user")

    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "mlx-community/Qwen2.5-14B-Instruct-4bit"
    assert result == {"ok": True}


def test_check_provider_ready_mlx_down_still_asks_for_text_server_with_mlx_vision():
    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "mlx_vision"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_VISION_BASE_URL", "http://127.0.0.1:8081"),
        patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")),
        pytest.raises(LLMNotConfigured, match="No MLX server is reachable"),
    ):
        check_provider_ready()


def test_check_provider_ready_rejects_same_url_for_text_and_vision():
    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "mlx_vision"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_VISION_BASE_URL", "http://127.0.0.1:8080"),
        pytest.raises(LLMNotConfigured, match="same"),
    ):
        check_provider_ready()


def test_check_provider_ready_mlx_vision_probes_both_servers():
    fake = MagicMock()
    fake.raise_for_status.return_value = None
    fake.json.return_value = {"data": [{"id": "ok"}]}

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "mlx_vision"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_VISION_BASE_URL", "http://127.0.0.1:8081"),
        patch("requests.get", return_value=fake) as get,
    ):
        check_provider_ready()

    assert [c.args[0] for c in get.call_args_list] == [
        "http://127.0.0.1:8080/v1/models",
        "http://127.0.0.1:8081/v1/models",
    ]


def test_check_provider_ready_mlx_vision_down_after_text_ok():
    fake = MagicMock()
    fake.raise_for_status.return_value = None

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "mlx_vision"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_VISION_BASE_URL", "http://127.0.0.1:8081"),
        patch(
            "requests.get",
            side_effect=[fake, requests.exceptions.ConnectionError("vl down")],
        ),
    ):
        check_provider_ready()


def test_check_provider_ready_mlx_ok_when_only_vl_is_up():
    fake = MagicMock()
    fake.raise_for_status.return_value = None

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.OCR_ENGINE", "mlx_vision"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_VISION_BASE_URL", "http://127.0.0.1:8081"),
        patch(
            "requests.get",
            side_effect=[requests.exceptions.ConnectionError("14b down"), fake],
        ),
    ):
        check_provider_ready()


def test_complete_json_mlx_falls_back_to_vl_when_14b_refused():
    fake = MagicMock()
    fake.status_code = 200
    fake.raise_for_status.return_value = None
    fake.json.return_value = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }

    def post(url, **kwargs):
        if ":8080" in url:
            raise requests.exceptions.ConnectionError("refused")
        return fake

    with (
        patch("src.llm_client.LLM_PROVIDER", "mlx"),
        patch("src.llm_client.MLX_BASE_URL", "http://127.0.0.1:8080"),
        patch("src.llm_client.MLX_MODEL", "mlx-community/Qwen2.5-14B-Instruct-4bit"),
        patch("src.llm_client.MLX_VISION_BASE_URL", "http://127.0.0.1:8081"),
        patch(
            "src.llm_client.MLX_VISION_MODEL",
            "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
        ),
        patch("requests.post", side_effect=post) as mock_post,
    ):
        result = complete_json("sys", "user")

    assert result == {"ok": True}
    urls = [c.args[0] for c in mock_post.call_args_list]
    assert urls[0] == "http://127.0.0.1:8080/v1/chat/completions"
    assert urls[-1] == "http://127.0.0.1:8081/v1/chat/completions"
    assert mock_post.call_args.kwargs["json"]["model"] == (
        "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
    )
