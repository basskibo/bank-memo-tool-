from unittest.mock import MagicMock, patch

from src.mlx_servers import ensure_mlx_text, ensure_mlx_vision


def test_ensure_mlx_text_noops_when_autoswap_off():
    with (
        patch("src.mlx_servers.mlx_autoswap_enabled", return_value=False),
        patch("src.mlx_servers._start_text") as start,
        patch("src.mlx_servers._stop_port") as stop,
    ):
        ensure_mlx_text()
    start.assert_not_called()
    stop.assert_not_called()


def test_ensure_mlx_text_stops_vision_and_starts_14b():
    with (
        patch("src.mlx_servers.mlx_autoswap_enabled", return_value=True),
        patch("src.mlx_servers._healthy", side_effect=[False, False]),
        patch("src.mlx_servers._listener_pids", return_value=[99]),
        patch("src.mlx_servers._stop_port") as stop,
        patch("src.mlx_servers._start_text") as start,
        patch("src.mlx_servers._wait_healthy") as wait,
    ):
        status = MagicMock()
        ensure_mlx_text(on_status=status)

    status.assert_called_once()
    stop.assert_called()
    start.assert_called_once()
    wait.assert_called_once()


def test_ensure_mlx_vision_stops_text_and_starts_vl():
    with (
        patch("src.mlx_servers.mlx_autoswap_enabled", return_value=True),
        patch("src.mlx_servers._healthy", side_effect=[False, False]),
        patch("src.mlx_servers._listener_pids", return_value=[42]),
        patch("src.mlx_servers._stop_port") as stop,
        patch("src.mlx_servers._start_vision") as start,
        patch("src.mlx_servers._wait_healthy") as wait,
    ):
        ensure_mlx_vision()

    stop.assert_called()
    start.assert_called_once()
    wait.assert_called_once()


def test_ensure_mlx_text_skips_start_when_only_14b_is_up():
    with (
        patch("src.mlx_servers.mlx_autoswap_enabled", return_value=True),
        patch("src.mlx_servers._healthy", return_value=True),
        patch("src.mlx_servers._listener_pids", return_value=[]),
        patch("src.mlx_servers._start_text") as start,
        patch("src.mlx_servers._stop_port") as stop,
    ):
        ensure_mlx_text()
    start.assert_not_called()
    stop.assert_not_called()
