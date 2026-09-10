"""
End-to-end retrieval check on the gold question set (SPEC.md §9).

Loads the real embedding model once (module-scoped) — ~10-15 s. Skipped if
sentence-transformers is not installed.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("sentence_transformers")

from evaluation.rag_gold import GOLD  # noqa: E402
from src.config import RAG_TOP_K  # noqa: E402


@pytest.fixture(scope="module")
def hits_by_query():
    from src.rag import retrieve
    from src.rag.index import reset_index

    reset_index()
    out = {g.query: retrieve(g.query, k=RAG_TOP_K) for g in GOLD}
    reset_index()
    return out


@pytest.mark.parametrize("gold", GOLD, ids=[g.expect_doc_id + "/" + g.lang for g in GOLD])
def test_gold_query_lands_on_the_right_passage(gold, hits_by_query):
    hits = hits_by_query[gold.query]
    assert hits, f"no hits for: {gold.query}"
    assert hits[0].doc_id == gold.expect_doc_id, (
        f"rank-1 was {hits[0].doc_id}, expected {gold.expect_doc_id}"
    )
    assert gold.expect_phrase in hits[0].text, (
        f"rank-1 chunk of {hits[0].doc_id} is missing the expected phrase"
    )
    assert -1.0 <= hits[0].score <= 1.0


def test_every_hit_carries_a_citation(hits_by_query):
    for hits in hits_by_query.values():
        for h in hits:
            assert h.doc_id and h.chunk_id and h.chunk_id.startswith(h.doc_id + "#")
            assert h.citation() == f"{h.doc_id} · {h.chunk_id}"


def test_empty_query_returns_nothing(hits_by_query):
    from src.rag import retrieve

    assert retrieve("   ") == []


def test_overall_rank1_accuracy_is_high(hits_by_query):
    correct = sum(
        1 for g in GOLD
        if hits_by_query[g.query] and hits_by_query[g.query][0].doc_id == g.expect_doc_id
    )
    # small corpus, not a KPI — but a working demo should get nearly all of these
    assert correct >= len(GOLD) - 1


def test_policy_check_builds_queries_from_fields(hits_by_query):
    from src.models.schemas import ExtractedField
    from src.rag import build_policy_queries, run_policy_check

    fs = [
        ExtractedField(field_name="company_name", value="Cairo Textile Exports S.A.E.",
                       source_document_id="d", source_page=1, source_snippet="x",
                       confidence=0.9, status="confirmed"),
        ExtractedField(field_name="requested_facility_amount", value="15,000,000", unit="EGP",
                       source_document_id="d", source_page=1, source_snippet="x",
                       confidence=0.9, status="confirmed"),
        ExtractedField(field_name="collateral_offered", value="Export receivables assignment",
                       source_document_id="d", source_page=1, source_snippet="x",
                       confidence=0.9, status="confirmed"),
    ]
    topics = [t for t, _ in build_policy_queries(fs, "loan_application")]
    assert "Collateral & LTV" in topics
    assert "Prohibited / restricted activity" in topics

    items = run_policy_check(fs, "loan_application", k=3)
    assert items and all(it.query and isinstance(it.hits, list) for it in items)
    collateral_item = next(it for it in items if it.topic == "Collateral & LTV")
    assert collateral_item.hits[0].doc_id == "en_collateral_ltv"


def test_policy_check_is_read_only_on_fields():
    """run_policy_check must not mutate the ExtractedField list it is given."""
    from src.models.schemas import ExtractedField
    from src.rag import run_policy_check

    f = ExtractedField(field_name="company_name", value="Acme", source_document_id="d",
                       source_page=1, source_snippet="x", confidence=0.9, status="confirmed")
    before = f.model_dump()
    run_policy_check([f], "financial_statement", k=2)
    assert f.model_dump() == before


def test_chroma_store_persists_and_matches_memory(tmp_path, monkeypatch):
    """RAG_STORE=chroma builds a real on-disk DB and returns the same rank-1 doc as memory."""
    pytest.importorskip("chromadb")
    import src.rag.index as idx_mod

    monkeypatch.setattr(idx_mod, "RAG_CHROMA_DIR", str(tmp_path / "chroma"))
    idx_mod.reset_index()

    chroma = idx_mod.build_index("chroma")
    assert chroma.kind == "chroma"
    assert (tmp_path / "chroma" / "chroma.sqlite3").exists()  # persisted
    assert (tmp_path / "chroma" / "manifest.json").exists()

    mem = idx_mod.build_index("memory")
    for g in GOLD[:5]:
        c1 = chroma.query(g.query, k=1)[0].doc_id
        m1 = mem.query(g.query, k=1)[0].doc_id
        assert c1 == m1 == g.expect_doc_id

    # second open of the same dir must NOT re-embed (manifest fingerprint matches)
    reopened = idx_mod.ChromaPolicyIndex(idx_mod.build_chunks(), tmp_path / "chroma")
    assert reopened.collection.count() == mem.matrix.shape[0]
    idx_mod.reset_index()
