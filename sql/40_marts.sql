-- ---------------------------------------------------------------------------
-- mart.application_funnel : one row per application, ready for Tableau
-- ---------------------------------------------------------------------------
CREATE TABLE mart.application_funnel AS
SELECT a.application_id,
       a.req_id,
       r.department, r.level, r.location, r.title,
       rec.recruiter_name,
       a.source_name, s.source_category,
       a.applied_at::date                                  AS applied_date,
       d.year_quarter                                      AS applied_quarter,
       1                                                   AS reached_applied,
       (a.furthest_stage_rank >= 2)::int                   AS reached_recruiter_screen,
       (a.furthest_stage_rank >= 3)::int                   AS reached_hm_screen,
       (a.furthest_stage_rank >= 4)::int                   AS reached_onsite,
       (a.furthest_stage_rank >= 5)::int                   AS reached_offer,
       (a.furthest_stage_rank >= 6)::int                   AS reached_hired,
       a.furthest_stage, a.outcome, a.outcome_reason,
       CASE WHEN a.hired_at IS NOT NULL AND NOT a.has_timestamp_issue
            THEN round(extract(epoch FROM a.hired_at - a.applied_at) / 86400.0, 1) END AS days_applied_to_hired,
       a.has_timestamp_issue
FROM core.fact_application a
JOIN core.dim_requisition r   USING (req_id)
JOIN core.dim_recruiter  rec  USING (recruiter_id)
JOIN core.dim_source     s    USING (source_name)
JOIN core.dim_date       d    ON d.date_key = a.applied_at::date;
ALTER TABLE mart.application_funnel ADD PRIMARY KEY (application_id);

-- ---------------------------------------------------------------------------
-- mart.funnel_stage_counts : quarter x department x source x stage (long format)
-- ---------------------------------------------------------------------------
CREATE TABLE mart.funnel_stage_counts AS
SELECT f.applied_quarter, f.department, f.source_name,
       m.stage_rank, m.stage_name,
       count(*) FILTER (WHERE a.furthest_stage_rank >= m.stage_rank) AS applications_reached
FROM mart.application_funnel f
JOIN core.fact_application a USING (application_id)
CROSS JOIN (SELECT stage_rank, stage_name FROM stg.stage_map WHERE NOT is_terminal) m
GROUP BY f.applied_quarter, f.department, f.source_name, m.stage_rank, m.stage_name;
ALTER TABLE mart.funnel_stage_counts ADD PRIMARY KEY (applied_quarter, department, source_name, stage_rank);

-- ---------------------------------------------------------------------------
-- mart.funnel_conversion : conversion from each stage to the next, per department
-- ('All' = company-wide). step = share of the previous stage; overall = share of applicants.
-- ---------------------------------------------------------------------------
CREATE TABLE mart.funnel_conversion AS
WITH counts AS (
    SELECT COALESCE(department, 'All') AS department, stage_rank, stage_name,
           sum(applications_reached)   AS reached
    FROM mart.funnel_stage_counts
    GROUP BY GROUPING SETS ((department, stage_rank, stage_name), (stage_rank, stage_name))
)
SELECT department, stage_rank, stage_name, reached,
       round(reached / NULLIF(lag(reached) OVER w, 0), 4)          AS step_conversion,
       round(reached / NULLIF(first_value(reached) OVER w, 0), 4)  AS overall_conversion
FROM counts
WINDOW w AS (PARTITION BY department ORDER BY stage_rank);
ALTER TABLE mart.funnel_conversion ADD PRIMARY KEY (department, stage_rank);

-- ---------------------------------------------------------------------------
-- mart.time_to_fill : one row per filled requisition
-- time to fill = days from the requisition opening to the accepted offer
-- ---------------------------------------------------------------------------
CREATE TABLE mart.time_to_fill AS
SELECT r.req_id, r.title, r.department, r.level, r.location, rec.recruiter_name,
       r.opened_date,
       h.accepted_date                                   AS filled_date,
       h.accepted_date - r.opened_date                   AS days_to_fill,
       dd.year_quarter                                   AS filled_quarter,
       h.source_name                                     AS hire_source,
       (SELECT count(*) FROM core.fact_application a WHERE a.req_id = r.req_id) AS applications_received
FROM core.dim_requisition r
JOIN core.fact_hire h      USING (req_id)
JOIN core.dim_recruiter rec USING (recruiter_id)
JOIN core.dim_date dd      ON dd.date_key = h.accepted_date
WHERE r.status = 'filled';
ALTER TABLE mart.time_to_fill ADD PRIMARY KEY (req_id);

CREATE TABLE mart.time_to_fill_summary AS
SELECT COALESCE(department, 'All')     AS department,
       filled_quarter,
       count(*)                        AS requisitions_filled,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY days_to_fill)::numeric(6,1) AS median_days_to_fill,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY days_to_fill)::numeric(6,1) AS p90_days_to_fill
FROM mart.time_to_fill
GROUP BY GROUPING SETS ((department, filled_quarter), (filled_quarter));
ALTER TABLE mart.time_to_fill_summary ADD PRIMARY KEY (department, filled_quarter);

-- ---------------------------------------------------------------------------
-- mart.time_in_stage : how long candidates wait in each stage
-- Applications with out-of-order dates are excluded.
-- ---------------------------------------------------------------------------
CREATE TABLE mart.time_in_stage AS
SELECT COALESCE(r.department, 'All') AS department,
       e.stage_rank, e.stage_name,
       count(*)                      AS stage_exits,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM e.exited_at - e.entered_at) / 86400.0)::numeric(6,1) AS median_days,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM e.exited_at - e.entered_at) / 86400.0)::numeric(6,1) AS p90_days
FROM core.fact_stage_event e
JOIN core.fact_application a USING (application_id)
JOIN core.dim_requisition r  USING (req_id)
WHERE e.exited_at IS NOT NULL
  AND e.stage_rank < 6
  AND NOT a.has_timestamp_issue
GROUP BY GROUPING SETS ((r.department, e.stage_rank, e.stage_name), (e.stage_rank, e.stage_name));
ALTER TABLE mart.time_in_stage ADD PRIMARY KEY (department, stage_rank);

-- ---------------------------------------------------------------------------
-- mart.source_quality : does a source produce hires, or just applicants?
-- ---------------------------------------------------------------------------
CREATE TABLE mart.source_quality AS
WITH apps AS (
    SELECT source_name,
           count(*)                                              AS applications,
           count(*) FILTER (WHERE furthest_stage_rank >= 2)      AS recruiter_screens,
           count(*) FILTER (WHERE furthest_stage_rank >= 4)      AS onsites,
           count(*) FILTER (WHERE furthest_stage_rank >= 5)      AS offers,
           count(*) FILTER (WHERE furthest_stage_rank >= 6)      AS hires,
           count(*) FILTER (WHERE outcome = 'Offer Declined')    AS offers_declined
    FROM core.fact_application
    GROUP BY source_name
),
retention AS (
    SELECT source_name,
           count(*) FILTER (WHERE retained_90d IS NOT NULL)      AS hires_with_90d_result,
           count(*) FILTER (WHERE retained_90d)                  AS hires_retained_90d
    FROM core.fact_hire
    GROUP BY source_name
),
spend AS (
    SELECT source_name, sum(spend_usd) AS spend_usd
    FROM core.fact_source_cost
    GROUP BY source_name
)
SELECT a.source_name, s.source_category,
       a.applications, a.recruiter_screens, a.onsites, a.offers, a.hires,
       round(a.applications / sum(a.applications) OVER (), 4)              AS share_of_applications,
       round(a.hires / NULLIF(sum(a.hires) OVER (), 0), 4)                 AS share_of_hires,
       round(a.hires::numeric / NULLIF(a.applications, 0), 4)              AS application_to_hire_rate,
       round(a.recruiter_screens::numeric / NULLIF(a.applications, 0), 4)  AS screen_rate,
       round(a.hires::numeric / NULLIF(a.hires + a.offers_declined, 0), 4) AS offer_acceptance_rate,
       r.hires_with_90d_result,
       round(r.hires_retained_90d::numeric / NULLIF(r.hires_with_90d_result, 0), 4) AS retention_90d_rate,
       COALESCE(sp.spend_usd, 0)                                           AS spend_usd,
       round(COALESCE(sp.spend_usd, 0) / NULLIF(a.hires, 0), 0)            AS cost_per_hire_usd,
       rank() OVER (ORDER BY a.hires::numeric / NULLIF(a.applications, 0) DESC NULLS LAST) AS rank_by_hire_rate
FROM apps a
JOIN core.dim_source s USING (source_name)
LEFT JOIN retention r  USING (source_name)
LEFT JOIN spend sp     USING (source_name);
ALTER TABLE mart.source_quality ADD PRIMARY KEY (source_name);

-- ---------------------------------------------------------------------------
-- mart.weekly_pipeline : applications and hires per week, with a 4-week average
-- ---------------------------------------------------------------------------
CREATE TABLE mart.weekly_pipeline AS
WITH weeks AS (
    SELECT DISTINCT week_start FROM core.dim_date WHERE date_key BETWEEN date '2024-01-01' AND date '2025-12-31'
),
apps AS (
    SELECT date_trunc('week', applied_at)::date AS week_start, count(*) AS applications
    FROM core.fact_application GROUP BY 1
),
hires AS (
    SELECT date_trunc('week', accepted_date)::date AS week_start, count(*) AS hires
    FROM core.fact_hire GROUP BY 1
)
SELECT w.week_start,
       COALESCE(a.applications, 0) AS applications,
       COALESCE(h.hires, 0)        AS hires,
       round(avg(COALESCE(a.applications, 0)) OVER (ORDER BY w.week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 1) AS applications_4wk_avg
FROM weeks w
LEFT JOIN apps a  USING (week_start)
LEFT JOIN hires h USING (week_start)
ORDER BY w.week_start;
ALTER TABLE mart.weekly_pipeline ADD PRIMARY KEY (week_start);

-- ---------------------------------------------------------------------------
-- mart.open_requisition_aging : operational list of requisitions still open
-- ---------------------------------------------------------------------------
CREATE TABLE mart.open_requisition_aging AS
SELECT r.req_id, r.title, r.department, r.level, r.location, rec.recruiter_name, r.opened_date,
       date '2025-12-31' - r.opened_date AS days_open,
       CASE WHEN date '2025-12-31' - r.opened_date > 180 THEN 'Over 180 days'
            WHEN date '2025-12-31' - r.opened_date > 90  THEN '91-180 days'
            ELSE '90 days or less' END   AS age_band,
       count(a.application_id)                                        AS applications,
       count(a.application_id) FILTER (WHERE a.outcome = 'In Progress') AS in_progress
FROM core.dim_requisition r
JOIN core.dim_recruiter rec USING (recruiter_id)
LEFT JOIN core.fact_application a USING (req_id)
WHERE r.status = 'open'
GROUP BY r.req_id, r.title, r.department, r.level, r.location, rec.recruiter_name, r.opened_date;
ALTER TABLE mart.open_requisition_aging ADD PRIMARY KEY (req_id);
