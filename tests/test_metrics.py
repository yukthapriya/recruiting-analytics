"""The reported metrics are internally consistent."""


def test_funnel_never_grows_from_one_stage_to_the_next(db):
    bad = db.scalar("""
        SELECT count(*) FROM (
            SELECT reached, lag(reached) OVER (PARTITION BY department ORDER BY stage_rank) AS previous
            FROM mart.funnel_conversion) t
        WHERE reached > previous""")
    assert bad == 0


def test_conversion_rates_are_between_0_and_1(db):
    bad = db.scalar("""
        SELECT count(*) FROM mart.funnel_conversion
        WHERE step_conversion NOT BETWEEN 0 AND 1 OR overall_conversion NOT BETWEEN 0 AND 1""")
    assert bad == 0


def test_overall_conversion_is_the_product_of_the_steps(db):
    rows = db.rows("""
        SELECT department,
               exp(sum(ln(step_conversion)) FILTER (WHERE stage_rank > 1)) AS product,
               max(overall_conversion) FILTER (WHERE stage_rank = 6)       AS reported
        FROM mart.funnel_conversion
        GROUP BY department""")
    for department, product, reported in rows:
        assert abs(float(product) - float(reported)) < 0.0005, department


def test_median_never_exceeds_p90(db):
    assert db.scalar("SELECT count(*) FROM mart.time_to_fill_summary WHERE median_days_to_fill > p90_days_to_fill") == 0
    assert db.scalar("SELECT count(*) FROM mart.time_in_stage WHERE median_days > p90_days") == 0


def test_time_in_stage_is_never_negative(db):
    assert db.scalar("SELECT count(*) FROM mart.time_in_stage WHERE median_days < 0") == 0


def test_rates_and_costs_are_in_range(db):
    bad = db.scalar("""
        SELECT count(*) FROM mart.source_quality
        WHERE application_to_hire_rate NOT BETWEEN 0 AND 1
           OR offer_acceptance_rate   NOT BETWEEN 0 AND 1
           OR retention_90d_rate      NOT BETWEEN 0 AND 1
           OR spend_usd < 0 OR cost_per_hire_usd < 0""")
    assert bad == 0


def test_hires_never_exceed_offers_or_applications(db):
    bad = db.scalar("SELECT count(*) FROM mart.source_quality WHERE hires > offers OR offers > onsites OR onsites > applications")
    assert bad == 0


def test_reached_flags_agree_with_the_furthest_stage(db):
    bad = db.scalar("""
        SELECT count(*) FROM mart.application_funnel
        WHERE reached_applied + reached_recruiter_screen + reached_hm_screen
            + reached_onsite + reached_offer + reached_hired
           <> (SELECT stage_rank FROM stg.stage_map WHERE stage_name = furthest_stage)""")
    assert bad == 0
