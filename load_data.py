import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_counts.db"
CSV_PATH = ROOT / "cell-count.csv"


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {k.strip(): (v.strip() if v is not None else "") for k, v in row.items()}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS samples;
        DROP TABLE IF EXISTS subjects;
        DROP TABLE IF EXISTS projects;
        PRAGMA foreign_keys = ON;

        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE
        );

        CREATE TABLE subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects (id),
            subject_id TEXT NOT NULL,
            indication TEXT NOT NULL,
            age INTEGER NOT NULL,
            sex TEXT NOT NULL,
            treatment TEXT NOT NULL,
            response TEXT NOT NULL,
            UNIQUE (project_id, subject_id)
        );

        CREATE TABLE samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL REFERENCES subjects (id),
            sample_id TEXT NOT NULL UNIQUE,
            sample_type TEXT NOT NULL,
            time_from_treatment_start INTEGER NOT NULL,
            b_cell INTEGER NOT NULL,
            cd8_t_cell INTEGER NOT NULL,
            cd4_t_cell INTEGER NOT NULL,
            nk_cell INTEGER NOT NULL,
            monocyte INTEGER NOT NULL
        );

        CREATE INDEX idx_samples_subject ON samples (subject_id);
        CREATE INDEX idx_subjects_project ON subjects (project_id);
        """
    )


def load_csv(conn: sqlite3.Connection) -> int:
    project_ids: dict[str, int] = {}
    subject_ids: dict[tuple[int, str], int] = {}
    inserted = 0

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = _normalize_row(raw)
            proj = row["project"]
            subj = row["subject"]

            if proj not in project_ids:
                conn.execute("INSERT OR IGNORE INTO projects (code) VALUES (?)", (proj,))
                cur = conn.execute("SELECT id FROM projects WHERE code = ?", (proj,))
                project_ids[proj] = int(cur.fetchone()[0])

            pid = project_ids[proj]
            sk = (pid, subj)

            if sk not in subject_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO subjects (
                        project_id, subject_id, indication, age, sex,
                        treatment, response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        subj,
                        row["condition"],
                        int(row["age"]),
                        row["sex"],
                        row["treatment"],
                        row["response"],
                    ),
                )
                cur = conn.execute(
                    "SELECT id FROM subjects WHERE project_id = ? AND subject_id = ?",
                    (pid, subj),
                )
                subject_ids[sk] = int(cur.fetchone()[0])

            sid = subject_ids[sk]
            conn.execute(
                """
                INSERT INTO samples (
                    subject_id, sample_id, sample_type, time_from_treatment_start,
                    b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    row["sample"],
                    row["sample_type"],
                    int(row["time_from_treatment_start"]),
                    int(row["b_cell"]),
                    int(row["cd8_t_cell"]),
                    int(row["cd4_t_cell"]),
                    int(row["nk_cell"]),
                    int(row["monocyte"]),
                ),
            )
            inserted += 1

    return inserted


def main() -> None:
    if not CSV_PATH.is_file():
        raise SystemExit(f"Missing data file: {CSV_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        init_schema(conn)
        n = load_csv(conn)
        conn.commit()
        print(f"Wrote {DB_PATH} with {n} sample rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
