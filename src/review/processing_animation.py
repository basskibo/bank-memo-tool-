"""Stage-aware Lottie visuals for live pipeline processing in the review UI."""
from __future__ import annotations

import html
import json
from pathlib import Path

from src.review.pipeline_messages import (
    STAGE_EXTRACT,
    STAGE_INGEST,
    STAGE_MEMO,
    STAGE_VALIDATE,
    pipeline_progress,
)

_LOTTIE_DIR = Path(__file__).resolve().parent / "assets" / "lottie"
_STAGE_FILES = {
    STAGE_INGEST: "scan_document.json",
    STAGE_EXTRACT: "ai_analysis.json",
    STAGE_VALIDATE: "validation.json",
    STAGE_MEMO: "writing.json",
}
_STAGE_CAPTIONS = {
    STAGE_INGEST: "Reading PDF pages and running OCR where needed…",
    STAGE_EXTRACT: "Extracting financial fields with AI…",
    STAGE_VALIDATE: "Verifying each value against its source page…",
    STAGE_MEMO: "Drafting credit memo sections…",
}
_ANIMATION_CACHE: dict[str, dict] = {}


def _load_animation(stage: str) -> dict:
    if stage not in _ANIMATION_CACHE:
        path = _LOTTIE_DIR / _STAGE_FILES[stage]
        _ANIMATION_CACHE[stage] = json.loads(path.read_text(encoding="utf-8"))
    return _ANIMATION_CACHE[stage]


def animation_stage_from_log(entries: list[dict]) -> str:
    if not entries:
        return STAGE_INGEST

    last = entries[-1]
    stage = last.get("stage", STAGE_INGEST)
    if stage in (STAGE_INGEST, STAGE_EXTRACT, STAGE_VALIDATE, STAGE_MEMO):
        return stage

    for entry in reversed(entries):
        prior = entry.get("stage")
        if prior in _STAGE_FILES:
            return prior
    return STAGE_INGEST


def _stage_caption(entries: list[dict], stage: str) -> str:
    if stage == STAGE_INGEST:
        if any("ocr" in (e.get("message") or "").lower() for e in entries[-3:]):
            return "Scanning image pages with OCR…"
        if entries and "opening pdf" in entries[-1].get("message", "").lower():
            return "Opening PDF and reading pages…"
    return _STAGE_CAPTIONS[stage]


def render_processing_animation_html(
    entries: list[dict],
    *,
    animation_id: str,
) -> str:
    """HTML for st.html — Lottie loop matched to the current pipeline stage."""
    stage = animation_stage_from_log(entries)
    animation_data = _load_animation(stage)
    _, phase, detail, current, total = pipeline_progress(entries)
    caption = _stage_caption(entries, stage)
    safe_id = html.escape(animation_id, quote=True)
    safe_phase = html.escape(phase)
    safe_detail = html.escape(detail)
    safe_caption = html.escape(caption)
    progress_text = html.escape(f"{current}/{total} steps")
    animation_json = json.dumps(animation_data).replace("<", "\\u003c")

    return f"""<style>
.processing-visual {{
    display: flex; align-items: center; gap: 1.25rem;
    background: linear-gradient(135deg, #f8fbff 0%, #eef4fc 100%);
    border: 1px solid #d6e3f3; border-radius: 16px;
    padding: 0.85rem 1.25rem; margin-bottom: 0.85rem;
    box-shadow: 0 6px 18px rgba(0, 71, 186, 0.08);
}}
.processing-lottie {{
    width: 132px; height: 132px; flex: 0 0 auto;
    border-radius: 14px; background: white;
    border: 1px solid #e3ebf5;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.7);
    position: relative; overflow: hidden;
}}
.processing-lottie::before {{
    content: "";
    position: absolute; inset: 14% 18%;
    border: 2px solid #d6e3f3; border-radius: 8px;
    background: linear-gradient(180deg, #fafcff 0%, #eef4fc 100%);
    pointer-events: none; z-index: 0;
}}
.processing-lottie::after {{
    content: "";
    position: absolute; left: 16%; right: 16%; height: 3px;
    background: linear-gradient(90deg, transparent, #0047BA, transparent);
    box-shadow: 0 0 10px rgba(0, 71, 186, 0.45);
    animation: processing-scan 1.9s ease-in-out infinite;
    pointer-events: none; z-index: 1;
}}
.processing-lottie svg {{
    position: relative; z-index: 2;
}}
@keyframes processing-scan {{
    0% {{ top: 18%; opacity: 0.35; }}
    50% {{ top: 72%; opacity: 1; }}
    100% {{ top: 18%; opacity: 0.35; }}
}}
.processing-visual-body {{ flex: 1; min-width: 0; }}
.processing-visual-phase {{
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: #64707c; margin-bottom: 0.25rem;
}}
.processing-visual-title {{
    font-size: 1.02rem; font-weight: 700; color: #1a2430; line-height: 1.35;
    margin-bottom: 0.35rem;
}}
.processing-visual-detail {{
    font-size: 0.86rem; color: #4a5560; line-height: 1.45; margin-bottom: 0.55rem;
}}
.processing-visual-meta {{
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-size: 0.74rem; font-weight: 700; color: #0047BA;
    background: rgba(0, 71, 186, 0.08); border-radius: 999px;
    padding: 0.28rem 0.7rem;
}}
.processing-visual-meta::before {{
    content: ""; width: 0.45rem; height: 0.45rem; border-radius: 50%;
    background: #0047BA; animation: processing-pulse 1.1s ease-in-out infinite;
}}
@keyframes processing-pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.35; transform: scale(0.82); }}
}}
@media (max-width: 720px) {{
    .processing-visual {{ flex-direction: column; text-align: center; }}
    .processing-lottie {{ width: 112px; height: 112px; }}
}}
</style>
<div class="processing-visual">
  <div id="{safe_id}" class="processing-lottie" aria-hidden="true"></div>
  <div class="processing-visual-body">
    <div class="processing-visual-phase">{safe_phase}</div>
    <div class="processing-visual-title">{safe_caption}</div>
    <div class="processing-visual-detail">{safe_detail}</div>
    <div class="processing-visual-meta">{progress_text}</div>
  </div>
</div>
<script>
(function() {{
  var stage = {json.dumps(stage)};
  var containerId = {json.dumps(animation_id)};
  var cacheKey = containerId + ":" + stage;
  var animationData = {animation_json};

  function mountLottie() {{
    if (window.__scbLottieKey === cacheKey && window.__scbLottieAnim) {{
      return;
    }}
    if (window.__scbLottieAnim) {{
      window.__scbLottieAnim.destroy();
      window.__scbLottieAnim = null;
    }}
    var container = document.getElementById(containerId);
    if (!container || !window.lottie) return;
    window.__scbLottieKey = cacheKey;
    window.__scbLottieAnim = window.lottie.loadAnimation({{
      container: container,
      renderer: "svg",
      loop: true,
      autoplay: true,
      animationData: animationData,
    }});
  }}

  function ensureLottie() {{
    if (window.lottie) {{
      mountLottie();
      return;
    }}
    var existing = document.querySelector('script[data-scb-lottie="1"]');
    if (existing) {{
      existing.addEventListener("load", mountLottie, {{ once: true }});
      return;
    }}
    var script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js";
    script.dataset.scbLottie = "1";
    script.onload = mountLottie;
    document.head.appendChild(script);
  }}

  ensureLottie();
}})();
</script>"""
