"""Rules of the hiring process that the data must obey."""
from .conftest import DATA_END


def test_every_application_starts_at_applied(db):
    missing = db.scalar("""
        SELECT count(*) FROM core.fact_application a
        WHERE NOT EXISTS (SELECT 1 FROM core.fact_stage_event e
                          WHERE e.application_id = a.application_id AND e.stage_rank = 1)""")
    assert missing == 0


def test_no_application_skips_a_stage(db):
    skipped = db.scalar("""
        SELECT count(*) FROM (
            SELECT application_id FROM core.fact_stage_event
            GROUP BY application_id HAVING max(stage_rank) <> count(*)) s""")
    assert skipped == 0, f"{skipped} applications reached a stage without passing the one before it"


def test_stage_dates_move_forward_unless_flagged(db):
    bad = db.scalar("""
        SELECT count(*) FROM core.fact_stage_event e
        JOIN core.fact_application a USING (application_id)
        WHERE e.entered_at < e.previous_entered_at AND NOT a.has_timestamp_issue""")
    assert bad == 0


def test_flagged_applications_are_kept_out_of_durations(db):
    leaked = db.scalar("""
        SELECT count(*) FROM mart.application_funnel
        WHERE has_timestamp_issue AND days_applied_to_hired IS NOT NULL""")
    assert leaked == 0


def test_hired_means_offer_was_accepted(db):
    bad = db.scalar("""
        SELECT count(*) FROM core.fact_application
        WHERE (outcome = 'Hired') <> (furthest_stage_rank = 6)""")
    assert bad == 0


def test_every_hire_passed_through_an_offer(db):
    bad = db.scalar("SELECT count(*) FROM core.fact_application WHERE hired_at IS NOT NULL AND offer_at IS NULL")
    assert bad == 0


def test_each_filled_requisition_has_exactly_one_hire(db):
    bad = db.scalar("""
        SELECT count(*) FROM core.dim_requisition r
        LEFT JOIN (SELECT req_id, count(*) AS hires FROM core.fact_hire GROUP BY req_id) h USING (req_id)
        WHERE (r.status = 'filled') <> (COALESCE(h.hires, 0) = 1)""")
    assert bad == 0


def test_filled_requisition_closes_on_the_day_the_offer_is_accepted(db):
    bad = db.scalar("""
        SELECT count(*) FROM core.dim_requisition r JOIN core.fact_hire h USING (req_id)
        WHERE r.closed_date <> h.accepted_date""")
    assert bad == 0


def test_open_requisitions_have_no_close_date(db):
    assert db.scalar("SELECT count(*) FROM core.dim_requisition WHERE status = 'open' AND closed_date IS NOT NULL") == 0
    assert db.scalar("SELECT count(*) FROM core.dim_requisition WHERE status <> 'open' AND closed_date IS NULL") == 0


def test_nobody_applies_before_a_requisition_opens_or_after_it_closes(db):
    bad = db.scalar("""
        SELECT count(*) FROM core.fact_application a JOIN core.dim_requisition r USING (req_id)
        WHERE a.applied_at::date < r.opened_date
           OR (r.closed_date IS NOT NULL AND a.applied_at::date > r.closed_date)""")
    assert bad == 0


def test_nothing_is_dated_after_the_end_of_the_export(db):
    late = db.scalar("SELECT count(*) FROM core.fact_stage_event WHERE entered_at::date > %s", (DATA_END,))
    assert late == 0


def test_time_to_fill_is_never_negative(db):
    assert db.scalar("SELECT count(*) FROM mart.time_to_fill WHERE days_to_fill < 0") == 0


def test_retention_is_only_recorded_once_90_days_have_passed(db):
    bad = db.scalar("""
        SELECT count(*) FROM core.fact_hire
        WHERE retained_90d IS NOT NULL AND start_date + 90 > %s::date""", (DATA_END,))
    assert bad == 0
