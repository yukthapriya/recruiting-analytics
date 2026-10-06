"""Every table has a unique, non-null key, and every fact row points at a real dimension row."""
import pytest

KEYS = [
    ("core.dim_requisition", "req_id"),
    ("core.dim_recruiter", "recruiter_id"),
    ("core.dim_candidate", "person_key"),
    ("core.dim_candidate", "email_normalized"),
    ("core.candidate_xref", "candidate_id"),
    ("core.fact_application", "application_id"),
    ("core.fact_hire", "application_id"),
    ("core.fact_hire", "req_id"),
    ("mart.application_funnel", "application_id"),
    ("mart.time_to_fill", "req_id"),
    ("mart.source_quality", "source_name"),
]


@pytest.mark.parametrize("table,column", KEYS)
def test_key_is_unique_and_not_null(db, table, column):
    total, distinct, nulls = db.rows(
        f"SELECT count(*), count(DISTINCT {column}), count(*) FILTER (WHERE {column} IS NULL) FROM {table}")[0]
    assert total > 0, f"{table} is empty"
    assert nulls == 0, f"{table}.{column} has {nulls} NULLs"
    assert total == distinct, f"{table}.{column} has {total - distinct} duplicate values"


FOREIGN_KEYS = [
    ("core.fact_application", "req_id", "core.dim_requisition", "req_id"),
    ("core.fact_application", "person_key", "core.dim_candidate", "person_key"),
    ("core.fact_application", "source_name", "core.dim_source", "source_name"),
    ("core.fact_stage_event", "application_id", "core.fact_application", "application_id"),
    ("core.fact_hire", "application_id", "core.fact_application", "application_id"),
    ("core.fact_source_cost", "source_name", "core.dim_source", "source_name"),
    ("core.dim_requisition", "recruiter_id", "core.dim_recruiter", "recruiter_id"),
    ("mart.application_funnel", "req_id", "core.dim_requisition", "req_id"),
]


@pytest.mark.parametrize("child,child_col,parent,parent_col", FOREIGN_KEYS)
def test_no_orphan_rows(db, child, child_col, parent, parent_col):
    orphans = db.scalar(
        f"SELECT count(*) FROM {child} c LEFT JOIN {parent} p ON p.{parent_col} = c.{child_col} "
        f"WHERE p.{parent_col} IS NULL")
    assert orphans == 0, f"{orphans} rows in {child} have no match in {parent}"


ACCEPTED = [
    ("core.dim_requisition", "status", {"open", "filled", "cancelled"}),
    ("core.fact_application", "outcome", {"Hired", "Rejected", "Withdrawn", "Offer Declined", "In Progress"}),
    ("core.fact_stage_event", "stage_name",
     {"Applied", "Recruiter Screen", "Hiring Manager Screen", "Onsite", "Offer", "Hired"}),
    ("core.fact_application", "source_name",
     {"Job Board", "Careers Site", "LinkedIn", "Referral", "University", "Agency", "Internal", "Unknown"}),
]


@pytest.mark.parametrize("table,column,allowed", ACCEPTED)
def test_only_accepted_values(db, table, column, allowed):
    found = {r[0] for r in db.rows(f"SELECT DISTINCT {column} FROM {table}")}
    assert found <= allowed, f"unexpected values in {table}.{column}: {found - allowed}"
