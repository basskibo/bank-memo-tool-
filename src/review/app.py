"""
Prost review UI — SPEC.md 8 ("Streamlit ili ekvivalent"), implementira [HUMAN REVIEW] korake
iz SPEC.md 3.2 dijagrama.

Pokretanje: .venv/bin/streamlit run src/review/app.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # da src.* importi rade

from src.agents.narrative_synthesizer import synthesize_memo
from src.config import SAMPLE_DOCS_DIR
from src.orchestration.graph import apply_human_review, run_extraction

st.set_page_config(page_title="Credit Memo Agent POC", layout="wide")
st.title("Credit Memo Agent — POC Review UI")
st.caption("Implementacija SPEC.md / PLAN.md — vidi poc/SPEC.md za pravila iza svakog koraka.")

sample_files = sorted(Path(SAMPLE_DOCS_DIR).glob("*.pdf"))
selected = st.selectbox("Test dokument", sample_files, format_func=lambda p: p.name)

if "fields" not in st.session_state:
    st.session_state.fields = None
    st.session_state.document = None

if st.button("1. Pokreni ekstrakciju (ingest → extract → validate)"):
    with st.spinner("Radim..."):
        result = run_extraction(str(selected))
    if result.get("error"):
        st.error(result["error"])
    else:
        st.session_state.document = result["document"]
        st.session_state.fields = result["fields"]
        st.success(f"Gotovo. {len(result['fields'])} polja izvučeno.")

if st.session_state.fields:
    fields = st.session_state.fields
    confirmed = [f for f in fields if f.status == "confirmed"]
    needs_review = [f for f in fields if f.status == "needs_review"]

    st.subheader(f"Potvrđena polja ({len(confirmed)})")
    for f in confirmed:
        st.markdown(f"**{f.field_name}**: {f.value} {f.unit or ''}  \n"
                    f"*izvor: str. {f.source_page} — \"{f.source_snippet}\"* (confidence {f.confidence:.2f})")

    st.subheader(f"Zahteva pregled ({len(needs_review)})")
    decisions = {}
    for f in needs_review:
        with st.container(border=True):
            st.markdown(f"**{f.field_name}** — predloženo: `{f.value}`")
            st.caption(f"str. {f.source_page} — \"{f.source_snippet}\" · {f.validation_note or ''}")
            col1, col2 = st.columns([3, 1])
            corrected_value = col1.text_input("Ispravljena vrednost", value=f.value, key=f"val_{f.field_name}")
            confirm = col2.checkbox("Potvrdi", key=f"confirm_{f.field_name}")
            if confirm:
                decisions[f.field_name] = {"value": corrected_value, "status": "confirmed"}

    if st.button("2. Primeni odluke reviewer-a"):
        st.session_state.fields = apply_human_review(fields, decisions)
        st.rerun()

    all_confirmed = [f for f in st.session_state.fields if f.status == "confirmed"]
    remaining = [f for f in st.session_state.fields if f.status == "needs_review"]

    st.divider()
    st.write(f"Preostalo za review: {len(remaining)}")

    if st.button("3. Generiši nacrt memoranduma", disabled=len(all_confirmed) == 0):
        with st.spinner("Pišem memo..."):
            memo = synthesize_memo(
                client_name=next((f.value for f in all_confirmed if f.field_name == "company_name"), "Unknown"),
                confirmed_fields=all_confirmed,
                open_exceptions=[f.field_name for f in remaining],
            )
        st.subheader("Nacrt memoranduma")
        if memo.guardrail_violations:
            st.error("Guardrail violation — memo sadrži brojku bez pouzdanog izvora:")
            for v in memo.guardrail_violations:
                st.write(f"- {v}")
        for section in memo.sections:
            st.markdown(f"### {section.title}")
            st.write(section.text)
        if memo.open_exceptions:
            st.warning(f"Otvoreni izuzeci (nisu uključeni u memo): {', '.join(memo.open_exceptions)}")
