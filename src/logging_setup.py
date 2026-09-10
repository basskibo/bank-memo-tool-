"""Terminal logging for the credit-memo pipeline.

Streamlit reruns the UI script on every widget interaction. Configure the `bankmemo`
logger once per process (own StreamHandler, no propagate) so INFO lines reach the
terminal that launched `streamlit run`, without a "starting app" line on each rerun.
"""
from __future__ import annotations

import logging
import sys

BANKMEMO_LOGGER = "bankmemo"

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%H:%M:%S"


def get_logger(suffix: str = "") -> logging.Logger:
    name = BANKMEMO_LOGGER if not suffix else f"{BANKMEMO_LOGGER}.{suffix}"
    return logging.getLogger(name)


def configure_logging() -> None:
    """Attach a stdout handler to `bankmemo` if this process does not already have one."""
    logger = logging.getLogger(BANKMEMO_LOGGER)
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(handler)
    logger.propagate = False
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, OSError):
        pass


def log_pipeline_entry(entry: dict) -> None:
    """Mirror one in-app pipeline log dict as a single terminal line."""
    logger = get_logger("pipeline")
    step = f" ({entry['step']})" if entry.get("step") else ""
    label = entry.get("label") or "Pipeline"
    message = (entry.get("message") or "").replace("\n", " | ")
    if len(message) > 400:
        message = message[:397] + "..."
    stage = entry.get("stage") or ""
    level = logging.ERROR if stage == "error" else logging.INFO
    logger.log(level, "%s — %s%s", label, message, step)
