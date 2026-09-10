import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import RAG_CHUNK_CHARS_AR, RAG_CHUNK_CHARS_EN
from src.rag.chunk import chunk_document, detect_lang
from src.rag.corpus import build_chunks, load_corpus


def test_detect_lang():
    assert detect_lang("The maximum tenor is 36 months.") == "en"
    assert detect_lang("المدة القصوى هي 36 شهراً") == "ar"
    assert detect_lang("EGP 22,000,000 تمويل") == "ar"   # mixed but mostly Arabic
    assert detect_lang("") == "en"


def test_chunks_respect_language_window_and_overlap():
    en = "word " * 400  # ~2000 chars
    ch = chunk_document("en_test", en, "en")
    assert len(ch) >= 3
    assert all(len(c.text) <= RAG_CHUNK_CHARS_EN + 5 for c in ch)
    # consecutive chunks overlap (end of one appears near the start of the next)
    assert ch[0].char_end - ch[1].char_start > 0

    ar = "كلمة " * 400
    ca = chunk_document("ar_test", ar, "ar")
    assert all(len(c.text) <= RAG_CHUNK_CHARS_AR + 5 for c in ca)


def test_chunk_ids_are_unique_and_ordered():
    ch = chunk_document("en_test", "sentence one. " * 200, "en")
    ids = [c.chunk_id for c in ch]
    assert ids == sorted(ids, key=lambda s: int(s.split("#")[1]))
    assert len(ids) == len(set(ids))


def test_corpus_loads_both_languages():
    docs = load_corpus()
    langs = {lang for _, lang, _ in docs}
    assert langs == {"en", "ar"}
    assert len(docs) >= 6
    assert all("SYNTHETIC" in text or "اصطناعية" in text for _, _, text in docs)


def test_build_chunks_covers_every_doc():
    docs = {d for d, _, _ in load_corpus()}
    chunk_docs = {c.doc_id for c in build_chunks()}
    assert chunk_docs == docs
