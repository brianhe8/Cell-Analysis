from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_counts.db"

# Core cohort: same disease/treatment/tissue as Part 3, plus baseline timepoint.
BASE_WHERE = """
subj.indication = 'melanoma'
  AND subj.treatment = 'miraclib'
  AND s.sample_type = 'PBMC'
  AND s.time_from_treatment_start = 0
"""

SAMPLES_PER_PROJECT = f"""
SELECT p.code AS project, COUNT(*) AS n_samples
FROM samples s
JOIN subjects subj ON s.subject_id = subj.id
JOIN projects p ON subj.project_id = p.id
WHERE {BASE_WHERE}
GROUP BY p.code
ORDER BY p.code
"""

SUBJECTS_BY_RESPONSE = f"""
SELECT subj.response, COUNT(DISTINCT subj.id) AS n_subjects
FROM samples s
JOIN subjects subj ON s.subject_id = subj.id
WHERE {BASE_WHERE}
GROUP BY subj.response
ORDER BY subj.response
"""

SUBJECTS_BY_SEX = f"""
SELECT subj.sex, COUNT(DISTINCT subj.id) AS n_subjects
FROM samples s
JOIN subjects subj ON s.subject_id = subj.id
WHERE {BASE_WHERE}
GROUP BY subj.sex
ORDER BY subj.sex
"""

TOTAL_SAMPLES = f"""
SELECT COUNT(*) FROM samples s
JOIN subjects subj ON s.subject_id = subj.id
WHERE {BASE_WHERE}
"""

TOTAL_SUBJECTS = f"""
SELECT COUNT(DISTINCT subj.id) FROM samples s
JOIN subjects subj ON s.subject_id = subj.id
WHERE {BASE_WHERE}
"""


def main() -> None:
    if not DB_PATH.is_file():
        raise SystemExit(f"Missing database: {DB_PATH} (run load_data.py first)")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        n_samples = conn.execute(TOTAL_SAMPLES).fetchone()[0]
        n_subjects = conn.execute(TOTAL_SUBJECTS).fetchone()[0]

        if n_samples == 0:
            raise SystemExit(
                "No rows match: melanoma, miraclib, PBMC, time_from_treatment_start=0."
            )

        print(
            "Cohort: melanoma, treatment=miraclib, sample_type=PBMC, "
            "time_from_treatment_start=0 (baseline)\n"
            f"Total samples: {n_samples}  |  Distinct subjects: {n_subjects}\n"
        )

        print("Samples per project:")
        for row in conn.execute(SAMPLES_PER_PROJECT):
            print(f"  {row['project']}: {row['n_samples']}")
        print()

        print("Subjects by response (responder=yes, non-responder=no):")
        response_rows = list(conn.execute(SUBJECTS_BY_RESPONSE))
        label_map = {"yes": "Responder (yes)", "no": "Non-responder (no)"}
        for row in response_rows:
            r = row["response"] or "(empty)"
            label = label_map.get(row["response"], f"Other ({r})")
            print(f"  {label}: {row['n_subjects']}")
        print()

        print("Subjects by sex:")
        sex_rows = list(conn.execute(SUBJECTS_BY_SEX))
        sex_label = {"M": "Male (M)", "F": "Female (F)"}
        for row in sex_rows:
            s = row["sex"] or "(empty)"
            label = sex_label.get(row["sex"], f"Other ({s})")
            print(f"  {label}: {row['n_subjects']}")

        # Sanity check: subject counts should partition (each subject one response/sex).
        resp_sum = sum(r["n_subjects"] for r in response_rows)
        sex_sum = sum(r["n_subjects"] for r in sex_rows)
        if resp_sum != n_subjects or sex_sum != n_subjects:
            print(
                "\nNote: sums above may differ from distinct subjects if any subject "
                "has multiple response or sex values across joined rows (unexpected "
                "for this schema)."
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
