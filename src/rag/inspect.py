"""
See what the RAG "index" holds. There is no persistent database — the index is an in-memory
numpy matrix rebuilt each process (`src/rag/index.py`). This dumps what goes into it.

    .venv/bin/python -m src.rag.inspect              # print a summary + every chunk
    .venv/bin/python -m src.rag.inspect --md OUT.md  # write it as markdown
    .venv/bin/python -m src.rag.inspect --vectors    # also show embedding stats (loads the model)
"""
from __future__ import annotations

import argparse
from collections import Counter

from src.config import RAG_EMBED_MODEL
from src.rag.corpus import build_chunks, load_corpus


def _summary_lines(chunks, docs) -> list[str]:
    by_lang = Counter(c.lang for c in chunks)
    by_doc = Counter(c.doc_id for c in chunks)
    out = [
        f"corpus dir : sample_docs/policy_corpus/  ({len(docs)} .md files)",
        f"chunks     : {len(chunks)}  (en={by_lang['en']}, ar={by_lang['ar']})",
        f"embed model: {RAG_EMBED_MODEL}",
        "store      : in-memory numpy matrix (n_chunks x 384), rebuilt per process — NOT persisted",
        "",
        "chunks per document:",
    ]
    out += [f"  {d:<32} {n}" for d, n in sorted(by_doc.items())]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", metavar="PATH", help="write markdown to this file")
    ap.add_argument("--vectors", action="store_true", help="also embed and show vector stats")
    args = ap.parse_args()

    docs = load_corpus()
    chunks = build_chunks()

    lines = _summary_lines(chunks, docs)

    if args.vectors:
        import numpy as np
        from src.rag.index import PolicyIndex

        idx = PolicyIndex(chunks)
        m = idx.matrix
        lines += [
            "",
            f"vectors    : shape {m.shape}, dtype {m.dtype}, "
            f"row-norm min/max {float(np.linalg.norm(m, axis=1).min()):.3f}/"
            f"{float(np.linalg.norm(m, axis=1).max()):.3f} (unit-norm)",
        ]

    body = ["", "=" * 70, "ALL CHUNKS (this is everything the retriever can return)", "=" * 70]
    for c in chunks:
        body += [
            "",
            f"[{c.chunk_id}]  lang={c.lang}  chars {c.char_start}-{c.char_end}  len={len(c.text)}",
            c.text,
        ]

    text = "\n".join(lines + body)

    if args.md:
        md = ["# RAG index contents\n", "```", *lines, "```", ""]
        for c in chunks:
            md += [
                f"### `{c.chunk_id}`  ·  `{c.lang}`  ·  chars {c.char_start}–{c.char_end}",
                "",
                f"> {c.text}",
                "",
            ]
        from pathlib import Path
        Path(args.md).write_text("\n".join(md), encoding="utf-8")
        print(f"wrote {args.md}  ({len(chunks)} chunks)")
    else:
        print(text)


if __name__ == "__main__":
    main()
