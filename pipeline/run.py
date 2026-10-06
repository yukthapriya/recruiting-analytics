"""Build the recruiting analytics warehouse.

  python -m pipeline.run all        # generate data, load, build, export
  python -m pipeline.run generate   # write the raw CSV export to data/raw
  python -m pipeline.run build      # load raw CSVs and run every SQL file in sql/
  python -m pipeline.run export     # write the reporting tables to tableau/*.csv
  python -m pipeline.run report     # print the data quality summary and headline metrics
  python -m pipeline.run analysis   # run every query in analysis/ and print the results

The database comes from DATABASE_URL (default: postgresql://postgres@localhost:5432/recruiting).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SQL_DIR = ROOT / "sql"
TABLEAU_DIR = ROOT / "tableau"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/recruiting")

RAW_TABLES = ["recruiters", "requisitions", "candidates", "applications", "stage_events", "hires", "source_costs"]
EXPORTS = {
    "application_funnel": "SELECT * FROM mart.application_funnel ORDER BY application_id",
    "funnel_stage_counts": "SELECT * FROM mart.funnel_stage_counts ORDER BY applied_quarter, department, source_name, stage_rank",
    "funnel_conversion": "SELECT * FROM mart.funnel_conversion ORDER BY department, stage_rank",
    "time_to_fill": "SELECT * FROM mart.time_to_fill ORDER BY req_id",
    "time_to_fill_summary": "SELECT * FROM mart.time_to_fill_summary ORDER BY department, filled_quarter",
    "time_in_stage": "SELECT * FROM mart.time_in_stage ORDER BY department, stage_rank",
    "source_quality": "SELECT * FROM mart.source_quality ORDER BY rank_by_hire_rate",
    "weekly_pipeline": "SELECT * FROM mart.weekly_pipeline ORDER BY week_start",
    "open_requisition_aging": "SELECT * FROM mart.open_requisition_aging ORDER BY days_open DESC",
    "data_quality_summary": "SELECT check_name, rows_affected, rows_checked, pct_affected FROM dq.summary ORDER BY check_order",
}


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, autocommit=False)


def run_sql_file(cur: psycopg.Cursor, path: Path) -> None:
    started = time.perf_counter()
    cur.execute(path.read_text())
    print(f"  ran {path.name:<24} {time.perf_counter() - started:6.2f}s")


def generate() -> None:
    from data.generate import generate as gen
    counts = gen(seed=42, n_reqs=800, out=RAW_DIR)
    print("generated raw export:", ", ".join(f"{k}={v:,}" for k, v in counts.items()))


def build() -> None:
    """Load the raw export and run the SQL layers, all in one transaction."""
    with connect() as conn, conn.cursor() as cur:
        for name in ("00_schemas.sql", "01_raw_tables.sql"):
            run_sql_file(cur, SQL_DIR / name)
        for table in RAW_TABLES:
            path = RAW_DIR / f"{table}.csv"
            with path.open("rb") as f, cur.copy(f"COPY raw.{table} FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
                while chunk := f.read(1 << 16):
                    copy.write(chunk)
            cur.execute(f"SELECT count(*) FROM raw.{table}")
            print(f"  loaded raw.{table:<14} {cur.fetchone()[0]:>8,} rows")
        for path in sorted(SQL_DIR.glob("[1-9]*.sql")):
            run_sql_file(cur, path)
        conn.commit()
    print("build complete")


def export() -> None:
    TABLEAU_DIR.mkdir(exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        for name, query in EXPORTS.items():
            out = TABLEAU_DIR / f"{name}.csv"
            with out.open("wb") as f, cur.copy(f"COPY ({query}) TO STDOUT WITH (FORMAT csv, HEADER true)") as copy:
                for data in copy:
                    f.write(data)
            rows = sum(1 for _ in out.open()) - 1
            print(f"  wrote tableau/{out.name:<28} {rows:>7,} rows")


def print_table(cur: psycopg.Cursor, title: str) -> None:
    cols = [d.name for d in cur.description]
    rows = [[("" if v is None else str(v)) for v in row] for row in cur.fetchall()]
    widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print(f"\n{title}")
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))


def analysis() -> None:
    with connect() as conn, conn.cursor() as cur:
        for path in sorted((ROOT / "analysis").glob("*.sql")):
            sql = path.read_text()
            question = next(line[3:].strip() for line in sql.splitlines() if line.startswith("-- Q"))
            cur.execute(sql)
            print_table(cur, f"{path.name}: {question}")


def report() -> None:
    queries = {
        "Data quality summary": "SELECT check_name, rows_affected, rows_checked, pct_affected FROM dq.summary ORDER BY check_order",
        "Funnel (all departments)": "SELECT stage_name, reached, step_conversion, overall_conversion FROM mart.funnel_conversion WHERE department = 'All' ORDER BY stage_rank",
        "Source quality": "SELECT source_name, applications, hires, share_of_applications, share_of_hires, application_to_hire_rate, retention_90d_rate, cost_per_hire_usd FROM mart.source_quality ORDER BY rank_by_hire_rate",
    }
    with connect() as conn, conn.cursor() as cur:
        for title, query in queries.items():
            cur.execute(query)
            print_table(cur, title)


def main() -> None:
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    steps = {"generate": [generate], "build": [build], "export": [export], "report": [report],
             "analysis": [analysis], "all": [generate, build, export, report]}
    if step not in steps:
        sys.exit(__doc__)
    for fn in steps[step]:
        print(f"== {fn.__name__}")
        fn()


if __name__ == "__main__":
    main()
