"""
Interactive dashboard for Cell Analysis pipeline outputs.
Run via: make dashboard
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_counts.db"
FREQ_CSV = ROOT / "frequencies.csv"
BOXPLOT = ROOT / "response_boxplots.png"
PART3_REPORT = ROOT / "response_analysis_report.txt"
PART4_REPORT = ROOT / "subset_analysis_report.txt"


@st.cache_data
def load_frequencies() -> pd.DataFrame | None:
    if not FREQ_CSV.is_file():
        return None
    return pd.read_csv(FREQ_CSV)


@st.cache_data
def cohort_overview() -> pd.DataFrame:
    if not DB_PATH.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            """
            SELECT p.code AS project,
                   COUNT(DISTINCT subj.id) AS subjects,
                   COUNT(s.id) AS samples
            FROM samples s
            JOIN subjects subj ON s.subject_id = subj.id
            JOIN projects p ON subj.project_id = p.id
            GROUP BY p.code
            ORDER BY p.code
            """,
            conn,
        )
    finally:
        conn.close()


def main() -> None:
    st.set_page_config(
        page_title="Cell Analysis",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Cell Analysis dashboard")
    st.caption("Parts 2–4: frequencies, responder analysis, baseline subset summaries.")

    with st.sidebar:
        st.header("Run order")
        st.code("make setup\nmake pipeline\nmake dashboard", language="bash")
        if not DB_PATH.is_file():
            st.warning("Database not found. Run `make pipeline` first.")

    tab_freq, tab_resp, tab_subset, tab_explore = st.tabs(
        ["Part 2: Frequencies", "Part 3: Response", "Part 4: Baseline subset", "Explore DB"]
    )

    with tab_freq:
        st.subheader("Relative frequencies per sample")
        df = load_frequencies()
        if df is None:
            st.info("Run `make pipeline` to generate `frequencies.csv`.")
        else:
            st.metric("Long-format rows", f"{len(df):,}")
            pop = st.selectbox("Population", sorted(df["population"].unique()))
            filt = df[df["population"] == pop]
            st.dataframe(filt.head(500), use_container_width=True)
            if len(filt) > 500:
                st.caption("Showing first 500 rows for this population.")

    with tab_resp:
        st.subheader("Melanoma + miraclib PBMC: responders vs non-responders")
        if BOXPLOT.is_file():
            st.image(str(BOXPLOT), use_container_width=True)
        else:
            st.warning("Missing `response_boxplots.png`. Run `make pipeline`.")
        if PART3_REPORT.is_file():
            st.text_area(
                "Statistical report",
                PART3_REPORT.read_text(encoding="utf-8"),
                height=400,
            )
        else:
            st.info("Run `make pipeline` to generate `response_analysis_report.txt`.")

    with tab_subset:
        st.subheader("Baseline (day 0) PBMC — melanoma + miraclib")
        if PART4_REPORT.is_file():
            st.text_area(
                "Subset report",
                PART4_REPORT.read_text(encoding="utf-8"),
                height=320,
            )
        else:
            st.info("Run `make pipeline` to generate `subset_analysis_report.txt`.")

    with tab_explore:
        st.subheader("Projects in the database")
        ov = cohort_overview()
        if ov.empty:
            st.info("No data. Run `make pipeline`.")
        else:
            st.dataframe(ov, use_container_width=True)


if __name__ == "__main__":
    main()
