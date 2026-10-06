"""Row counts and totals tie out between layers, so nothing is lost or double counted."""


def test_every_raw_application_is_either_modeled_or_set_aside(db):
    raw = db.scalar("SELECT count(*) FROM raw.applications")
    modeled = db.scalar("SELECT count(*) FROM core.fact_application")
    orphaned = db.scalar("SELECT count(*) FROM dq.orphan_applications")
    assert raw == modeled + orphaned


def test_candidate_records_roll_up_to_people(db):
    raw = db.scalar("SELECT count(*) FROM raw.candidates")
    records, people = db.rows("SELECT sum(candidate_record_count), count(*) FROM core.dim_candidate")[0]
    merged = db.scalar("SELECT COALESCE(sum(extra_records), 0) FROM dq.duplicate_candidates")
    assert raw == records
    assert people == raw - merged


def test_stage_events_tie_out_after_removing_duplicates(db):
    raw = db.scalar("SELECT count(*) FROM raw.stage_events")
    kept = db.scalar("SELECT count(*) FROM stg.stage_events")
    extra = db.scalar("SELECT COALESCE(sum(extra_copies), 0) FROM dq.duplicate_stage_events")
    assert raw == kept + extra


def test_every_raw_hire_is_in_the_hire_fact(db):
    assert db.scalar("SELECT count(*) FROM raw.hires") == db.scalar("SELECT count(*) FROM core.fact_hire")


def test_funnel_totals_match_the_facts(db):
    applied, hired = db.rows("""
        SELECT max(reached) FILTER (WHERE stage_rank = 1), max(reached) FILTER (WHERE stage_rank = 6)
        FROM mart.funnel_conversion WHERE department = 'All'""")[0]
    assert applied == db.scalar("SELECT count(*) FROM core.fact_application")
    assert hired == db.scalar("SELECT count(*) FROM core.fact_hire")


def test_department_funnels_add_up_to_the_company_funnel(db):
    mismatched = db.scalar("""
        SELECT count(*) FROM (
            SELECT stage_rank,
                   sum(reached) FILTER (WHERE department <> 'All') AS by_department,
                   max(reached) FILTER (WHERE department = 'All')  AS company
            FROM mart.funnel_conversion GROUP BY stage_rank) t
        WHERE by_department <> company""")
    assert mismatched == 0


def test_source_quality_totals_match_the_facts(db):
    apps, hires, share_apps, share_hires = db.rows("""
        SELECT sum(applications), sum(hires), sum(share_of_applications), sum(share_of_hires)
        FROM mart.source_quality""")[0]
    assert apps == db.scalar("SELECT count(*) FROM core.fact_application")
    assert hires == db.scalar("SELECT count(*) FROM core.fact_hire")
    assert abs(float(share_apps) - 1) < 0.001
    assert abs(float(share_hires) - 1) < 0.001


def test_spend_in_the_mart_equals_spend_in_the_export(db):
    raw = db.scalar("SELECT sum(spend_usd::numeric) FROM raw.source_costs")
    mart = db.scalar("SELECT sum(spend_usd) FROM mart.source_quality")
    assert raw == mart


def test_time_to_fill_covers_every_filled_requisition(db):
    filled = db.scalar("SELECT count(*) FROM core.dim_requisition WHERE status = 'filled'")
    assert db.scalar("SELECT count(*) FROM mart.time_to_fill") == filled
    assert db.scalar("SELECT sum(requisitions_filled) FROM mart.time_to_fill_summary WHERE department = 'All'") == filled
    assert db.scalar("SELECT sum(requisitions_filled) FROM mart.time_to_fill_summary WHERE department <> 'All'") == filled


def test_weekly_pipeline_adds_up(db):
    apps, hires = db.rows("SELECT sum(applications), sum(hires) FROM mart.weekly_pipeline")[0]
    assert apps == db.scalar("SELECT count(*) FROM core.fact_application")
    assert hires == db.scalar("SELECT count(*) FROM core.fact_hire")
