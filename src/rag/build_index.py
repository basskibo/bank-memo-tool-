"""
(Re)build the persistent RAG vector DB from the policy corpus.

    .venv/bin/python -m src.rag.build_index            # build/refresh (RAG_STORE from env)
    .venv/bin/python -m src.rag.build_index --force    # wipe and rebuild
    RAG_STORE=chroma .venv/bin/python -m src.rag.build_index

The portal builds this lazily on first use too — run this ahead of a demo so the first query
is instant.
"""
from __future__ import annotations

import argparse
import shutil

from src.config import RAG_CHROMA_DIR, RAG_STORE
from src.rag.index import build_index, reset_index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="delete the existing DB first")
    args = ap.parse_args()

    if args.force and RAG_STORE == "chroma":
        import pathlib

        p = pathlib.Path(RAG_CHROMA_DIR)
        if p.exists():
            shutil.rmtree(p)
            print(f"removed {p}")

    reset_index()
    idx = build_index()
    probe = idx.query("maximum SME tenor", k=3)
    print(f"store={idx.kind}  built OK")
    if idx.kind == "chroma":
        print(f"persisted to: {RAG_CHROMA_DIR}")
    print("probe 'maximum SME tenor':", [(h.doc_id, h.score) for h in probe])


if __name__ == "__main__":
    main()
