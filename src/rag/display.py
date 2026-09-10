"""Turn a retrieved policy chunk into fields the review UI can render cleanly.

Chunks are whitespace-collapsed markdown, so a hit looks like::

    # SME Lending Standards (SYNTHETIC — not real SCB policy) ## Tenor limits SME working-...

The portal must not dump those hashes into a sidebar blockquote.
"""
from __future__ import annotations

import re
from functools import lru_cache

from src.rag.schemas import RetrievedChunk

_SYNTHETIC = re.compile(
    r"\s*\((?:SYNTHETIC[^)]*|وثيقة اصطناعية[^)]*)\)\s*",
    re.IGNORECASE,
)
_H1 = re.compile(r"^#\s+(.*?)(?=\s+##|\s*$)")


@lru_cache(maxsize=1)
def _corpus_h2() -> tuple[str, ...]:
    """H2 titles from the synthetic corpus, longest first so 'Restricted (...)' beats 'Restricted'."""
    from src.rag.corpus import load_corpus

    found: set[str] = set()
    for _, _, text in load_corpus():
        for match in re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE):
            found.add(match.group(1).strip())
    return tuple(sorted(found, key=len, reverse=True))


def pretty_doc_label(doc_id: str) -> str:
    rest = re.sub(r"^(en|ar)_", "", doc_id)
    return rest.replace("_", " ")


def parse_policy_text(text: str) -> dict:
    """Split collapsed markdown into title, section/body blocks, synthetic flag."""
    synthetic = bool(re.search(r"SYNTHETIC|اصطناعية", text, re.IGNORECASE))
    cleaned = _SYNTHETIC.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    title = None
    h1 = _H1.match(cleaned)
    if h1:
        title = h1.group(1).strip() or None
        cleaned = cleaned[h1.end():].strip()
    else:
        cleaned = re.sub(r"^#\s+", "", cleaned)

    pieces = re.split(r"\s+##\s+", cleaned)
    headings = _corpus_h2()
    blocks: list[dict[str, str]] = []
    for piece in pieces:
        piece = piece.strip()
        if piece.startswith("## "):
            piece = piece[3:].strip()
        if not piece:
            continue
        section = ""
        body = piece
        for heading in headings:
            if piece == heading or piece.startswith(heading + " "):
                section = heading
                body = piece[len(heading):].strip()
                break
        blocks.append({"section": section, "body": body})
    if not blocks:
        blocks = [{"section": "", "body": cleaned}]
    return {"title": title or "", "synthetic": synthetic, "blocks": blocks}


def chunk_view(hit: RetrievedChunk) -> dict:
    parsed = parse_policy_text(hit.text)
    title = parsed["title"] or pretty_doc_label(hit.doc_id)
    passage = hit.chunk_id.rsplit("#", 1)[-1]
    score_pct = int(round(max(0.0, min(1.0, hit.score)) * 100))
    return {
        "title": title,
        "lang": hit.lang,
        "synthetic": parsed["synthetic"],
        "blocks": parsed["blocks"],
        "doc_id": hit.doc_id,
        "passage": passage,
        "score_pct": score_pct,
        "rtl": hit.lang == "ar",
    }
