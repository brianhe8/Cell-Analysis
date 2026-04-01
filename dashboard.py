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


@st.cache_data
def db_table_projects() -> pd.DataFrame:
    if not DB_PATH.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            "SELECT id AS project_pk, code AS project FROM projects ORDER BY code",
            conn,
        )
    finally:
        conn.close()


@st.cache_data
def db_table_subjects() -> pd.DataFrame:
    if not DB_PATH.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            """
            SELECT subj.id AS subject_pk,
                   p.code AS project,
                   subj.subject_id,
                   subj.indication,
                   subj.age,
                   subj.sex,
                   subj.treatment,
                   subj.response
            FROM subjects subj
            JOIN projects p ON subj.project_id = p.id
            ORDER BY p.code, subj.subject_id
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data
def db_table_samples(limit: int) -> pd.DataFrame:
    if not DB_PATH.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            f"""
            SELECT s.id AS sample_pk,
                   p.code AS project,
                   subj.subject_id,
                   s.sample_id,
                   s.sample_type,
                   s.time_from_treatment_start,
                   s.b_cell, s.cd8_t_cell, s.cd4_t_cell, s.nk_cell, s.monocyte
            FROM samples s
            JOIN subjects subj ON s.subject_id = subj.id
            JOIN projects p ON subj.project_id = p.id
            ORDER BY s.sample_id
            LIMIT {int(limit)}
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data
def db_count_samples() -> int:
    if not DB_PATH.is_file():
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT COUNT(*) FROM samples").fetchone()
        return int(row[0]) if row else 0
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
        st.subheader("Explore database")
        st.caption(
            "SQLite tables `projects`, `subjects`, and `samples`. "
            "The roll-up is a quick summary; other views list table rows."
        )
        if not DB_PATH.is_file():
            st.info("No database. Run `make pipeline`.")
        else:
            view = st.radio(
                "View",
                (
                    "Project summary (subject & sample counts)",
                    "Table: projects",
                    "Table: subjects",
                    "Table: samples",
                ),
                horizontal=True,
                key="explore_view",
            )
            if view.startswith("Project summary"):
                ov = cohort_overview()
                if ov.empty:
                    st.info("No rows.")
                else:
                    st.dataframe(ov, use_container_width=True)
            elif view == "Table: projects":
                df = db_table_projects()
                st.metric("Rows", f"{len(df):,}")
                st.dataframe(df, use_container_width=True, hide_index=True)
            elif view == "Table: subjects":
                df = db_table_subjects()
                st.metric("Rows", f"{len(df):,}")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                total = db_count_samples()
                if total == 0:
                    st.info("No samples in the database.")
                elif total <= 5_000:
                    df = db_table_samples(total)
                    st.caption(f"Showing all {total:,} samples.")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    cap = min(15_000, total)
                    default = min(5_000, cap)
                    max_rows = st.slider(
                        "Max rows to show",
                        min_value=500,
                        max_value=cap,
                        value=default,
                        step=500,
                        help="Samples table is large; capped at 15,000 rows for browser performance.",
                    )
                    df = db_table_samples(max_rows)
                    st.metric("Rows displayed", f"{len(df):,}")
                    if max_rows < total:
                        st.caption(f"Total samples in database: {total:,}. Increase the slider to load more (up to {cap:,}).")
                    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
