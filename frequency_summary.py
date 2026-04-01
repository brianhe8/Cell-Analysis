import argparse
import csv
import sqlite3
import sys
from contextlib import nullcontext
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
    parser = argparse.ArgumentParser(
        description="Part 2: relative frequency of each cell population per sample."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write CSV to this path (UTF-8). Default: stdout.",
    )
    args = parser.parse_args()

    if not DB_PATH.is_file():
        raise SystemExit(f"Missing database: {DB_PATH} (run load_data.py first)")

    out_path = args.output
    if out_path is not None and not out_path.is_absolute():
        out_path = ROOT / out_path

    conn = sqlite3.connect(DB_PATH)
    try:
        stream_ctx = (
            open(out_path, "w", newline="", encoding="utf-8")
            if out_path is not None
            else nullcontext(sys.stdout)
        )
        with stream_ctx as stream:
            w = csv.writer(stream, lineterminator="\n")
            w.writerow(["sample", "total_count", "population", "count", "percentage"])
            for sample, total, population, count, pct in iter_frequency_rows(conn):
                w.writerow([sample, total, population, count, f"{pct:.2f}"])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
