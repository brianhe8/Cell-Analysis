import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_counts.db"

POPULATIONS = ("b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte")


def iter_frequency_rows(conn: sqlite3.Connection):
    cols = ", ".join(POPULATIONS)
    cur = conn.execute(
        f"SELECT sample_id, {cols} FROM samples ORDER BY sample_id"
    )
    for row in cur:
        sample_id = row[0]
        counts = dict(zip(POPULATIONS, row[1:]))
        total = sum(counts.values())
        for population in POPULATIONS:
            c = counts[population]
            pct = (100.0 * c / total) if total else 0.0
            yield sample_id, total, population, c, pct


def main() -> None:
    if not DB_PATH.is_file():
        raise SystemExit(f"Missing database: {DB_PATH} (run load_data.py first)")

    conn = sqlite3.connect(DB_PATH)
    try:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["sample", "total_count", "population", "count", "percentage"])
        for sample, total, population, count, pct in iter_frequency_rows(conn):
            w.writerow([sample, total, population, count, f"{pct:.2f}"])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
