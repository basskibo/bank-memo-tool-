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
    format_pct,
    pipeline_progress,
    runtime_model_label,
)

_LOTTIE_DIR = Path(__file__).resolve().parent / "assets" / "lottie"
_STAGE_FILES = {
    STAGE_INGEST: "scan_document.json",
    STAGE_EXTRACT: "ai_analysis.json",
    STAGE_VALIDATE: "validation.json",
    STAGE_MEMO: "writing.json",
}
_STAGE_CAPTIONS = {
    STAGE_INGEST: "Reading PDF…",
    STAGE_EXTRACT: "Extracting…",
    STAGE_VALIDATE: "Verifying sources…",
    STAGE_MEMO: "Drafting memo…",
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


def processing_caption(entries: list[dict]) -> str:
    """Human-readable status line for the live processing card."""
    frac, _, _, _, _ = pipeline_progress(entries)
    return f"{_stage_caption(entries, animation_stage_from_log(entries))} {format_pct(frac)}"


def _stage_caption(entries: list[dict], stage: str) -> str:
    if stage == STAGE_INGEST:
        if any("ocr" in (e.get("message") or "").lower() for e in entries[-3:]):
            return "Scanning pages…"
        if entries and "opening pdf" in entries[-1].get("message", "").lower():
            return "Reading PDF…"
    return _STAGE_CAPTIONS[stage]


_MODEL_CHIP_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" '
    'fill="currentColor" aria-hidden="true">'
    '<path d="M20 9V7c0-1.1-.9-2-2-2h-3c0-1.66-1.34-3-3-3S9 3.34 9 5H6c-1.1 0-2 .9-2 2v2'
    'c-1.66 0-3 1.34-3 3s1.34 3 3 3v4c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4c1.66 0 3-1.34 '
    '3-3s-1.34-3-3-3zM7.5 11.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5S9.83 13 9 13s-1.5-.67'
    '-1.5-1.5zM16 17H8v-2h8v2zm-1-4c-.83 0-1.5-.67-1.5-1.5S14.17 10 15 10s1.5.67 1.5 '
    '1.5S15.83 13 15 13z"/></svg>'
)


def _model_chip_kicker(model_label: str) -> str:
    lowered = model_label.lower()
    if "no llm" in lowered or "pdfplumber" in lowered or "tesseract" in lowered:
        return "Engine"
    return "Model"


def render_processing_animation_html(
    entries: list[dict],
    *,
    animation_id: str,
) -> str:
    """HTML for st.html — Lottie loop matched to the current pipeline stage."""
    stage = animation_stage_from_log(entries)
    animation_data = _load_animation(stage)
    frac, phase, detail, _, _ = pipeline_progress(entries)
    caption = f"{_stage_caption(entries, stage)} {format_pct(frac)}"
    model_label = runtime_model_label(entries)
    safe_id = html.escape(animation_id, quote=True)
    safe_phase = html.escape(phase)
    safe_detail = html.escape(detail)
    safe_caption = html.escape(caption)
    safe_model = html.escape(model_label)
    safe_kicker = html.escape(_model_chip_kicker(model_label))
    progress_text = html.escape(format_pct(frac))
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
.processing-visual-pills {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem;
}}
.processing-visual-meta {{
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-size: 0.74rem; font-weight: 700; color: #0047BA;
    background: rgba(0, 71, 186, 0.08); border-radius: 999px;
    padding: 0.28rem 0.7rem;
}}
.processing-visual-model {{
    display: inline-flex; align-items: center; gap: 0.35rem;
    max-width: 100%; min-width: 0;
    font-size: 0.68rem; font-weight: 400; color: #6b7784;
}}
.processing-visual-model svg {{
    flex: 0 0 auto; color: #8a96a3;
}}
.processing-visual-model-kicker {{
    flex: 0 0 auto; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase; font-size: 0.62rem; color: #8a96a3;
}}
.processing-visual-model-id {{
    min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    color: #5c6773;
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
    <div class="processing-visual-pills">
      <div class="processing-visual-meta">{progress_text}</div>
      <div class="processing-visual-model" title="{safe_kicker}: {safe_model}">
        {_MODEL_CHIP_ICON}
        <span class="processing-visual-model-kicker">{safe_kicker}</span>
        <span class="processing-visual-model-id">{safe_model}</span>
      </div>
    </div>
  </div>
</div>
<script>
(function() {{
  var stage = {json.dumps(stage)};
  var containerId = {json.dumps(animation_id)};
  var cacheKey = containerId + ":" + stage;
  var animationData = {animation_json};

    function mountLottie() {{
    var container = document.getElementById(containerId);
    var alreadyMounted = container && container.childNodes.length > 0;
    if (window.__scbLottieKey === cacheKey && window.__scbLottieAnim && alreadyMounted) {{
      return;
    }}
    if (window.__scbLottieAnim) {{
      window.__scbLottieAnim.destroy();
      window.__scbLottieAnim = null;
    }}
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
