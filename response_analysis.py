from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_counts.db"
DEFAULT_PLOT = ROOT / "response_boxplots.png"

POPULATIONS = ("b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte")

LABELS = {
    "b_cell": "B cell",
    "cd8_t_cell": "CD8+ T cell",
    "cd4_t_cell": "CD4+ T cell",
    "nk_cell": "NK cell",
    "monocyte": "Monocyte",
}

QUERY = """
SELECT
    s.sample_id,
    subj.response,
    s.b_cell, s.cd8_t_cell, s.cd4_t_cell, s.nk_cell, s.monocyte
FROM samples s
JOIN subjects subj ON s.subject_id = subj.id
WHERE subj.indication = 'melanoma'
  AND subj.treatment = 'miraclib'
  AND s.sample_type = 'PBMC'
  AND subj.response IN ('yes', 'no')
"""


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Return Benjamini–Hochberg FDR-adjusted q-values."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    adj_sorted = np.empty(m)
    adj_sorted[m - 1] = min(1.0, ranked[m - 1] * m / m)
    for i in range(m - 2, -1, -1):
        adj_sorted[i] = min(adj_sorted[i + 1], ranked[i] * m / (i + 1))
    out = np.empty(m)
    out[order] = adj_sorted
    return out


def load_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(QUERY, conn)
    if df.empty:
        return df
    totals = df[list(POPULATIONS)].sum(axis=1)
    for col in POPULATIONS:
        df[f"pct_{col}"] = np.where(totals > 0, 100.0 * df[col] / totals, np.nan)
    return df


def run_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pop in POPULATIONS:
        col = f"pct_{pop}"
        no_vals = df.loc[df["response"] == "no", col].dropna()
        yes_vals = df.loc[df["response"] == "yes", col].dropna()
        if len(no_vals) < 2 or len(yes_vals) < 2:
            rows.append(
                {
                    "population": pop,
                    "n_no": len(no_vals),
                    "n_yes": len(yes_vals),
                    "median_no": float(no_vals.median()) if len(no_vals) else np.nan,
                    "median_yes": float(yes_vals.median()) if len(yes_vals) else np.nan,
                    "p_value": np.nan,
                }
            )
            continue
        res = mannwhitneyu(
            yes_vals, no_vals, alternative="two-sided", method="auto"
        )
        rows.append(
            {
                "population": pop,
                "n_no": len(no_vals),
                "n_yes": len(yes_vals),
                "median_no": float(no_vals.median()),
                "median_yes": float(yes_vals.median()),
                "p_value": float(res.pvalue),
            }
        )
    out = pd.DataFrame(rows)
    if not out["p_value"].isna().all():
        valid = out["p_value"].notna()
        q = np.full(len(out), np.nan)
        q[valid.values] = benjamini_hochberg(out.loc[valid, "p_value"].values)
        out["q_bh"] = q
    else:
        out["q_bh"] = np.nan
    return out


def plot_boxplots(df: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11, 7), constrained_layout=True)
    axes_flat = axes.ravel()
    for ax, pop in zip(axes_flat, POPULATIONS):
        col = f"pct_{pop}"
        data = [
            df.loc[df["response"] == "no", col].dropna(),
            df.loc[df["response"] == "yes", col].dropna(),
        ]
        ax.boxplot(
            data,
            labels=["Non-responder\n(response=no)", "Responder\n(response=yes)"],
            widths=0.55,
        )
        ax.set_ylabel("Relative frequency (%)")
        ax.set_title(LABELS[pop])
    axes_flat[-1].set_visible(False)
    fig.suptitle(
        "PBMC population frequencies: melanoma + miraclib\n"
        "Responders vs non-responders",
        fontsize=12,
    )
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_report(df: pd.DataFrame, stats_df: pd.DataFrame, out, plot_path: Path) -> None:
    alpha = 0.05
    print(
        "Cohort: melanoma, treatment=miraclib, sample_type=PBMC, response yes/no\n"
        f"Samples: n={len(df)} "
        f"(non-responders={len(df[df['response'] == 'no'])}, "
        f"responders={len(df[df['response'] == 'yes'])})\n",
        file=out,
    )
    print(
        "Mann–Whitney U (two-sided): relative frequency (%) vs response group\n"
        f"Multiple testing: Benjamini–Hochberg FDR; significance at q ≤ {alpha}\n",
        file=out,
    )
    for _, r in stats_df.iterrows():
        pop = r["population"]
        q = r["q_bh"]
        q_str = f"{q:.4g}" if pd.notna(q) else "—"
        p_str = f"{r['p_value']:.4g}" if pd.notna(r["p_value"]) else "—"
        sig = (
            "yes"
            if pd.notna(q) and q <= alpha
            else ("no" if pd.notna(r["p_value"]) else "—")
        )
        print(
            f"  {LABELS[pop]:12}  n_no={int(r['n_no']):4}  n_yes={int(r['n_yes']):4}  "
            f"median_no={r['median_no']:.2f}%  median_yes={r['median_yes']:.2f}%  "
            f"p={p_str}  q_BH={q_str}  significant (FDR)? {sig}",
            file=out,
        )

    significant = stats_df[stats_df["q_bh"].notna() & (stats_df["q_bh"] <= alpha)]
    print(file=out)
    if significant.empty:
        print(
            "Conclusion: After FDR correction, no population showed a significant "
            "difference in relative frequency between responders and non-responders.",
            file=out,
        )
    else:
        names = ", ".join(LABELS[p] for p in significant["population"])
        print(
            "Conclusion: The following populations differ significantly between "
            f"groups (Mann–Whitney U, FDR q ≤ {alpha}): {names}.",
            file=out,
        )

    plot_boxplots(df, plot_path)
    print(f"\nSaved boxplot figure: {plot_path}", file=out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Part 3: responder vs non-responder PBMC frequencies (melanoma + miraclib)."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write statistical report to this file (UTF-8). Default: stdout.",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=DEFAULT_PLOT,
        metavar="FILE",
        help=f"Boxplot image path (default: {DEFAULT_PLOT.name}).",
    )
    args = parser.parse_args()

    plot_path = args.plot if args.plot.is_absolute() else ROOT / args.plot
    report_path = args.report
    if report_path is not None and not report_path.is_absolute():
        report_path = ROOT / report_path

    if not DB_PATH.is_file():
        raise SystemExit(f"Missing database: {DB_PATH} (run load_data.py first)")

    conn = sqlite3.connect(DB_PATH)
    try:
        df = load_frame(conn)
    finally:
        conn.close()

    if df.empty:
        raise SystemExit("No rows match filters (melanoma, miraclib, PBMC, yes/no).")

    stats_df = run_tests(df)

    if report_path is None:
        write_report(df, stats_df, sys.stdout, plot_path)
    else:
        with open(report_path, "w", encoding="utf-8") as out:
            write_report(df, stats_df, out, plot_path)


if __name__ == "__main__":
    main()
