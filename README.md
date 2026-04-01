# Cell Analysis

Python pipeline and interactive dashboard for normalizing clinical trial cell-count data into SQLite, computing population frequencies, statistical comparisons (Part 3), and baseline cohort summaries (Part 4).

## Live dashboard link

`**https://cell-analysis.streamlit.app/**`

Locally: start the app with `make dashboard` and use the URL Streamlit prints (in **GitHub Codespaces**, open the **Ports** tab, forward port **8501**, and open the forwarded URL).

---

## Reproduce results (GitHub Codespaces)

1. Open this repository in a Codespace (or clone locally with Python 3.10+). On some Linux images, install Make if needed: `sudo apt-get update && sudo apt-get install -y make`.
2. From the repository root:

```bash
make setup
make pipeline
```

1. **Outputs produced by `make pipeline`**

| Artifact                       | Description                                                         |
| ------------------------------ | ------------------------------------------------------------------- |
| `cell_counts.db`               | SQLite database (Part 1)                                            |
| `frequencies.csv`              | Long-format relative frequencies per sample and population (Part 2) |
| `response_boxplots.png`        | Boxplots: responders vs non-responders (Part 3)                     |
| `response_analysis_report.txt` | Console statistics from Part 3 (Mann–Whitney, FDR)                  |
| `subset_analysis_report.txt`   | Baseline subset counts (Part 4)                                     |

2. **Dashboard**

```bash
make dashboard
```

Then open `http://localhost:8501` (or the Codespaces forwarded URL for port 8501).

**Input data:** `cell-count.csv` must be present in the repo root (same directory as `Makefile`). The pipeline rebuilds the database from this file every run.

---

## Relational database schema and rationale

### Tables

1. `**projects`\*\*

- `id` (PK), `code` (unique trial/study identifier, e.g. `prj1`).
- **Why:** Many rows share the same project; storing it once avoids repeating long codes and gives a stable foreign key for partitioning data by study.

2. `**subjects`\*\*

- `id` (PK), `project_id` (FK → `projects`), `subject_id` (string id within the project), `indication`, `age`, `sex`, `treatment`, `response`.
- **Unique constraint:** `(project_id, subject_id)`.
- **Why:** Demographics and clinical attributes belong to the person, not to each blood draw. Normalizing here removes duplicate subject metadata for every sample row in the CSV.

3. `**samples`\*\*

- `id` (PK), `subject_id` (FK → `subjects`), `sample_id` (unique), `sample_type`, `time_from_treatment_start`, and five integer count columns: `b_cell`, `cd8_t_cell`, `cd4_t_cell`, `nk_cell`, `monocyte`.
- **Why:** Each row is one biological specimen at one timepoint; counts are facts about that sample. Linking to `subjects` keeps analytics join-friendly (filter by indication, treatment, response, then aggregate samples).

### Indexes

- `idx_samples_subject` on `samples(subject_id)` — fast “all samples for this subject” and join paths from subject filters.
- `idx_subjects_project` on `subjects(project_id)` — fast per-project enrollment and Part 4–style “samples per project” queries.

### Scaling

- **Lots of projects and samples:** For mostly read-only reporting, SQLite is suitable if the indexes line up with how you actually filter (project, subject, sample type, day on study). If you outgrow it—huge concurrency, massive writes, or team-wide dashboards—the same three-table layout drops neatly into Postgres or BigQuery; you keep the keys and joins, swap the engine.
- **Many different analyses:** Counts and measurements live on `samples`; things that describe the person live on `subjects`. That way you are not copy-pasting age, sex, and response onto every blood draw. When you need a new cell type or assay, you can add a column on `samples`, or go full flexible with a skinny `(sample_id, metric, value)` table—trade-off is messier SQL.
- **Shape of the model:** Think of it as a small star: project → subject → sample. That matches how people ask questions (“which trial,” “which patients,” “which timepoints”). If dashboards get slow, you can pre-aggregate in a warehouse or materialized view without redoing how raw data lands.

---

## Code structure and design choices

| Module                 | Role                                                                                                                                                                                                                                    |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `load_data.py`         | Part 1: (Re)creates schema, loads `cell-count.csv` into `cell_counts.db`. Single script so ingestion is one command and always matches the defined schema.                                                                              |
| `frequency_summary.py` | Part 2: Reads counts from `samples`, emits long-format CSV. Use `-o frequencies.csv` (as in `make pipeline`) or omit `-o` to write to stdout.                                                                                           |
| `response_analysis.py` | Part 3: Pandas + SciPy for cohort filter, Mann–Whitney U, Benjamini–Hochberg FDR, and Matplotlib boxplots. Optional `--report FILE` (default stdout); `--plot` sets the PNG path.                                                       |
| `subset_analysis.py`   | Part 4: SQL summaries for baseline PBMC melanoma/miraclib cohort. Optional `--report FILE` (default stdout).                                                                                                                            |
| `dashboard.py`         | Streamlit UI: tabs for frequency preview, Part 3 figure and report, Part 4 report, and an **Explore DB** view (project roll-up plus `projects` / `subjects` / `samples` tables). Reads pipeline artifacts and queries `cell_counts.db`. |
| `Makefile`             | `setup` / `pipeline` / `dashboard` targets for a repeatable workflow in GitHub Codespaces.                                                                                                                                              |

**Why split scripts instead of one notebook?** Each part maps to its own script and outputs, CLI runs stay easy to test, and the Makefile runs the full sequence with no manual steps. Population lists and paths are repeated only where needed instead of pulling everything into a shared package layer.

---

## Makefile targets

| Target           | Behavior                                                                            |
| ---------------- | ----------------------------------------------------------------------------------- |
| `make setup`     | Installs dependencies from `requirements.txt`.                                      |
| `make pipeline`  | Runs `load_data.py`, writes `frequencies.csv`, Part 3 plot + report, Part 4 report. |
| `make dashboard` | Starts Streamlit on `0.0.0.0:8501` for local or Codespaces access.                  |

Override the interpreter if needed: `make setup PYTHON=python`.
