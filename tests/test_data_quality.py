"""Known problems in the export stay within limits, and the cleaning steps really ran."""
import pytest

# check_order in dq.summary -> highest share of rows we accept before the build should fail
LIMITS = {1: 0.5, 2: 2.0, 3: 2.0, 4: 0.5, 5: 5.0, 7: 0.0}


@pytest.mark.parametrize("check_order,max_pct", sorted(LIMITS.items()))
def test_data_quality_issue_is_within_limit(db, check_order, max_pct):
    name, pct = db.rows("SELECT check_name, pct_affected FROM dq.summary WHERE check_order = %s", (check_order,))[0]
    assert float(pct) <= max_pct, f"{name}: {pct}% of rows affected, limit is {max_pct}%"


def test_summary_reports_every_check(db):
    assert db.scalar("SELECT count(*) FROM dq.summary WHERE pct_affected IS NOT NULL") == 7


def test_every_source_spelling_is_mapped(db):
    unmapped = db.rows("SELECT source_raw, applications FROM dq.unmapped_source_labels")
    assert unmapped == [], f"add these spellings to stg.source_label_map: {unmapped}"


def test_export_really_contains_the_problems_we_clean(db):
    """Guards against the cleaning code passing only because the input happened to be clean."""
    assert db.scalar("SELECT count(DISTINCT source) FROM raw.applications WHERE trim(source) <> ''") > 7
    assert db.scalar("SELECT count(*) FROM raw.candidates WHERE email <> lower(trim(email))") > 0
    assert db.scalar("SELECT count(*) FROM dq.duplicate_stage_events") > 0
    assert db.scalar("SELECT count(*) FROM dq.out_of_order_applications") > 0
    assert db.scalar("SELECT count(*) FROM dq.orphan_applications") > 0


def test_no_person_appears_twice_after_merging(db):
    dupes = db.scalar("""
        SELECT count(*) FROM (SELECT email_normalized FROM core.dim_candidate
                              GROUP BY email_normalized HAVING count(*) > 1) d""")
    assert dupes == 0


def test_a_new_source_spelling_is_caught(scratch):
    """Plant an application with a source nobody mapped and confirm the check flags it."""
    scratch.execute("""
        INSERT INTO raw.applications (application_id, candidate_id, req_id, source, applied_at)
        SELECT 'A_TEST_1', candidate_id, req_id, 'Glassdoor', applied_at FROM raw.applications LIMIT 1""")
    flagged = scratch.rows("""
        SELECT source_raw FROM stg.applications
        WHERE source_raw IS NOT NULL AND source_name = 'Unknown'""")
    assert flagged == [("Glassdoor",)]


def test_a_duplicated_event_is_removed(scratch):
    """Plant a second copy of an event and confirm staging still returns one."""
    before = scratch.scalar("SELECT count(*) FROM stg.stage_events")
    scratch.execute("""
        INSERT INTO raw.stage_events (event_id, application_id, stage, occurred_at, reason)
        SELECT 'E_TEST_1', application_id, stage, occurred_at, reason FROM raw.stage_events LIMIT 1""")
    assert scratch.scalar("SELECT count(*) FROM stg.stage_events") == before
