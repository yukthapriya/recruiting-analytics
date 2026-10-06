# Recruiting Analytics Warehouse

[![data-tests](https://github.com/yukthapriya/recruiting-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/yukthapriya/recruiting-analytics/actions/workflows/ci.yml)

A PostgreSQL data model, SQL metrics and automated data tests for a hiring pipeline:
800 requisitions, 58,158 applications and 79,200 stage events over two years.

It answers three questions a recruiting team asks every week:

1. **Funnel conversion:** where do candidates drop out?
2. **Time to fill:** how long does a requisition stay open, and is that changing?
3. **Source quality:** which sources produce hires, and which only produce applicants?

The raw export is messy on purpose. The pipeline cleans it, counts what it cleaned,
and 66 tests check the result on every push.

**Dashboard:** _add your Tableau Public link here_ (build steps in [`tableau/DASHBOARD.md`](tableau/DASHBOARD.md))

## Results

All numbers below come from the SQL in this repository. `make report` and `make analysis` reproduce them.

### Funnel conversion

| Stage | Candidates | From previous stage | From application |
|---|---:|---:|---:|
| Applied | 58,101 | | 100.0% |
| Recruiter Screen | 12,400 | 21.3% | 21.3% |
| Hiring Manager Screen | 5,728 | 46.2% | 9.9% |
| Onsite | 2,193 | 38.3% | 3.8% |
| Offer | 638 | 29.1% | 1.1% |
| Hired | 476 | 74.6% | 0.8% |

The biggest gap against the company average is in AI & Robotics, where 21.8% of onsite
candidates receive an offer against 29.1% company-wide ([`analysis/01_funnel_leaks.sql`](analysis/01_funnel_leaks.sql)).

### Time to fill

Median time to fill is **51 days** (90th percentile 74) across 476 filled requisitions.

| Department | Filled | Median days | 90th percentile |
|---|---:|---:|---:|
| AI & Robotics | 52 | 64.5 | 88.5 |
| Vehicle Software | 55 | 56.0 | 82.6 |
| Finance | 39 | 55.0 | 71.4 |
| Energy | 39 | 53.0 | 69.2 |
| Supply Chain | 51 | 52.0 | 75.0 |
| People | 31 | 48.0 | 70.0 |
| Service | 72 | 47.0 | 65.6 |
| Manufacturing | 137 | 43.0 | 66.4 |

The slowest stage in every department is the hiring manager screen: a median of 8.7 days
company-wide and 13.7 days in AI & Robotics ([`analysis/05_time_in_stage.sql`](analysis/05_time_in_stage.sql)).

### Source quality

| Source | Applications | Hires | % of applications | % of hires | Hire lift | 90-day retention | Cost per hire |
|---|---:|---:|---:|---:|---:|---:|---:|
| Internal | 1,742 | 56 | 3.0% | 11.8% | 3.92 | 96.0% | $0 |
| Referral | 4,708 | 131 | 8.1% | 27.5% | 3.40 | 96.4% | $2,500 |
| Agency | 2,320 | 38 | 4.0% | 8.0% | 2.00 | 94.1% | $17,550 |
| University | 3,385 | 25 | 5.8% | 5.3% | 0.90 | 61.9% | $6,080 |
| LinkedIn | 10,314 | 74 | 17.8% | 15.6% | 0.88 | 82.5% | $9,730 |
| Careers Site | 15,166 | 90 | 26.1% | 18.9% | 0.72 | 91.9% | $1,600 |
| Unknown | 1,143 | 5 | 2.0% | 1.1% | 0.53 | 80.0% | $0 |
| Job Board | 19,323 | 57 | 33.3% | 12.0% | 0.36 | 72.3% | $9,263 |

Hire lift is a source's share of hires divided by its share of applications. Job boards bring
a third of all applications and 12% of hires; referrals bring 8% of applications and 27.5% of hires.

One finding came from the data quality work, not the metric itself: five hires have no source
recorded. Their cost still sits under the source that was paid, so that source's cost per hire is
overstated (Agency shows $17,550 against a flat $17,100 fee). Missing source data distorts spend
metrics, which is why the pipeline reports "Unknown" as its own row instead of dropping it.

## About the data

Real applicant-tracking data is private, so the export is **synthetic**. [`data/generate.py`](data/generate.py)
simulates a hiring process from a fixed seed, so every run produces byte-identical files.
The patterns above (referrals converting well, technical roles filling slowly) are assumptions
written into that simulation. They demonstrate the analysis; they are not findings about any real company.

The export has the problems real ATS exports have, injected at known rates:

| Problem in the raw export | Rows affected | Share | What the pipeline does |
|---|---:|---:|---|
| Source spelled inconsistently ("LinkedIn", "linkedin", "Linked In") | 8,374 | 14.4% | Maps 18 spellings to 7 names |
| No source recorded | 1,146 | 2.0% | Reports it as "Unknown" |
| Stage event exported twice | 773 | 1.0% | Keeps one copy |
| Same person registered twice (email case or spacing) | 161 | 0.3% | Merges into one person |
| Stage dated before the previous stage | 72 | 0.1% | Keeps in the funnel, excludes from durations |
| Application points at a requisition that was never exported | 57 | 0.1% | Sets aside, excludes from facts |

Every one of these is counted in `dq.summary` on each build.

## Data model

```
raw   7 tables   the export as it landed, every column text
 |
stg   7 views    typed, trimmed, standardized, de-duplicated  (+ 2 mapping tables)
 |
core  10 tables  dimensions and facts with primary keys, foreign keys and check constraints
 |
mart  9 tables   reporting tables read by Tableau
dq    6 tables   rows that were corrected or set aside, and a summary
```

- **Dimensions:** `dim_requisition`, `dim_candidate` (one row per person), `dim_source`, `dim_recruiter`, `dim_date`
- **Facts:** `fact_application` (one row per application, stage dates pivoted),
  `fact_stage_event` (one row per stage reached), `fact_hire`, `fact_source_cost`
- **Marts:** `application_funnel`, `funnel_stage_counts`, `funnel_conversion`, `time_to_fill`,
  `time_to_fill_summary`, `time_in_stage`, `source_quality`, `weekly_pipeline`, `open_requisition_aging`

Column-level definitions are in [`docs/data_dictionary.md`](docs/data_dictionary.md).

Definitions used throughout:

- **Time to fill:** days from the requisition's open date to the date the offer was accepted.
- **Step conversion:** candidates reaching a stage divided by candidates reaching the stage before it.
- **Hire lift:** share of hires divided by share of applications.
- **90-day retention:** hires still employed 90 days after starting, among hires old enough to measure.

## Tests

`pytest` runs 66 checks against the built warehouse:

| File | What it checks |
|---|---|
| [`test_keys_and_integrity.py`](tests/test_keys_and_integrity.py) | Keys are unique and non-null; no fact row lacks its dimension row; only accepted values |
| [`test_business_rules.py`](tests/test_business_rules.py) | No stage is skipped; each filled requisition has exactly one hire; nobody applies after a requisition closes |
| [`test_reconciliation.py`](tests/test_reconciliation.py) | Row counts and totals tie out from raw to core to mart, so nothing is lost or double counted |
| [`test_metrics.py`](tests/test_metrics.py) | The funnel never grows; rates stay between 0 and 1; overall conversion equals the product of the steps |
| [`test_data_quality.py`](tests/test_data_quality.py) | Known problems stay under set limits; planted bad rows are caught |

Two tests plant bad data inside a rolled-back transaction (an unmapped source spelling, a duplicated
event) and assert the pipeline catches it, so a passing run means the checks work and not just that the
input was clean.

[GitHub Actions](.github/workflows/ci.yml) starts PostgreSQL 16, rebuilds everything from the seed,
runs the tests, and fails if the committed Tableau extracts differ from what the code produces.

## Run it

Requires Python 3.11+ and Docker (or any PostgreSQL 14+).

```bash
docker compose up -d                 # PostgreSQL on localhost:5432
pip install -r requirements.txt
make all                             # generate, load, build, export (about 10 seconds)
make test                            # 66 data tests
make analysis                        # the seven analysis queries
```

To use another database, set `DATABASE_URL`, for example
`make all DATABASE_URL=postgresql://user:pass@host:5432/dbname`.

## Repository layout

```
data/generate.py     seeded generator for the raw ATS export
pipeline/run.py      load, build, export and report steps
sql/                 schemas, staging, core model, data quality, marts
analysis/            seven business questions, one SQL file each
tests/               66 data tests
tableau/             extracts for the dashboard and the build guide
docs/                data dictionary
```

## Limits

- The data is simulated, so the business patterns are assumptions, not discoveries.
- Each requisition has one opening; multi-headcount requisitions are not modeled.
- Cost per hire uses sourcing spend only, not recruiter time.
- The model rebuilds from scratch on every run; it is not incremental.
