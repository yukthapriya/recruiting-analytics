-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------
CREATE TABLE core.dim_source (
    source_name     text PRIMARY KEY,
    source_category text NOT NULL
);
INSERT INTO core.dim_source VALUES
    ('Careers Site', 'Inbound'), ('Job Board', 'Inbound'),
    ('LinkedIn', 'Sourced'),     ('Agency', 'Sourced'),
    ('Referral', 'Network'),     ('Internal', 'Network'),
    ('University', 'Campus'),    ('Unknown', 'Unknown');

CREATE TABLE core.dim_recruiter AS
SELECT recruiter_id, recruiter_name FROM stg.recruiters;
ALTER TABLE core.dim_recruiter ADD PRIMARY KEY (recruiter_id);

CREATE TABLE core.dim_requisition AS
SELECT req_id, title, department, location, level, recruiter_id, hiring_manager_id,
       opened_date, status, closed_date
FROM stg.requisitions;
ALTER TABLE core.dim_requisition
    ADD PRIMARY KEY (req_id),
    ADD FOREIGN KEY (recruiter_id) REFERENCES core.dim_recruiter (recruiter_id),
    ADD CHECK (status IN ('open', 'filled', 'cancelled')),
    ADD CHECK (closed_date IS NULL OR closed_date >= opened_date);

-- One row per real person: candidate records that share a normalized email are merged.
CREATE TABLE core.dim_candidate AS
SELECT dense_rank() OVER (ORDER BY email_normalized) AS person_key,
       email_normalized,
       min(created_at)  AS first_seen_at,
       count(*)         AS candidate_record_count
FROM stg.candidates
GROUP BY email_normalized;
ALTER TABLE core.dim_candidate ADD PRIMARY KEY (person_key);
CREATE UNIQUE INDEX ON core.dim_candidate (email_normalized);

-- Lookup from every raw candidate id to the person it belongs to.
CREATE TABLE core.candidate_xref AS
SELECT c.candidate_id, d.person_key
FROM stg.candidates c
JOIN core.dim_candidate d USING (email_normalized);
ALTER TABLE core.candidate_xref
    ADD PRIMARY KEY (candidate_id),
    ADD FOREIGN KEY (person_key) REFERENCES core.dim_candidate (person_key);

CREATE TABLE core.dim_date AS
SELECT d::date                                   AS date_key,
       extract(year FROM d)::int                 AS year,
       extract(quarter FROM d)::int              AS quarter,
       to_char(d, 'YYYY') || '-Q' || extract(quarter FROM d)::int AS year_quarter,
       date_trunc('month', d)::date              AS month_start,
       date_trunc('week', d)::date               AS week_start
FROM generate_series(date '2024-01-01', date '2026-03-31', interval '1 day') AS g(d);
ALTER TABLE core.dim_date ADD PRIMARY KEY (date_key);

-- ---------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------

-- Applications that point at a real requisition and a known candidate.
-- The rest are set aside in dq.orphan_applications (see 30_data_quality.sql).
CREATE TEMP TABLE valid_applications AS
SELECT a.application_id, a.req_id, x.person_key, a.source_name, a.applied_at
FROM stg.applications a
JOIN core.dim_requisition r USING (req_id)
JOIN core.candidate_xref  x USING (candidate_id);

-- One row per application per stage reached, in stage order.
CREATE TABLE core.fact_stage_event AS
WITH progression AS (
    SELECT application_id, 'applied' AS stage, applied_at AS entered_at
    FROM valid_applications
    UNION ALL
    SELECT e.application_id, e.stage, e.occurred_at
    FROM stg.stage_events e
    JOIN valid_applications v USING (application_id)
    JOIN stg.stage_map m ON m.stage = e.stage AND NOT m.is_terminal
),
terminal AS (
    SELECT e.application_id, min(e.occurred_at) AS ended_at
    FROM stg.stage_events e
    JOIN stg.stage_map m ON m.stage = e.stage AND m.is_terminal
    GROUP BY e.application_id
)
SELECT p.application_id,
       m.stage_rank,
       m.stage_name,
       p.entered_at,
       lag(p.entered_at)  OVER w AS previous_entered_at,
       COALESCE(lead(p.entered_at) OVER w, t.ended_at) AS exited_at
FROM progression p
JOIN stg.stage_map m USING (stage)
LEFT JOIN terminal t USING (application_id)
WINDOW w AS (PARTITION BY p.application_id ORDER BY m.stage_rank);
ALTER TABLE core.fact_stage_event ADD PRIMARY KEY (application_id, stage_rank);
CREATE INDEX ON core.fact_stage_event (stage_rank);

-- One row per application with each stage date pivoted into its own column.
CREATE TABLE core.fact_application AS
WITH stages AS (
    SELECT application_id,
           max(stage_rank)                                  AS furthest_stage_rank,
           min(entered_at) FILTER (WHERE stage_rank = 2)    AS screen_at,
           min(entered_at) FILTER (WHERE stage_rank = 3)    AS hm_screen_at,
           min(entered_at) FILTER (WHERE stage_rank = 4)    AS onsite_at,
           min(entered_at) FILTER (WHERE stage_rank = 5)    AS offer_at,
           min(entered_at) FILTER (WHERE stage_rank = 6)    AS hired_at,
           bool_or(entered_at < previous_entered_at)        AS has_timestamp_issue
    FROM core.fact_stage_event
    GROUP BY application_id
),
terminal AS (
    SELECT DISTINCT ON (e.application_id)
           e.application_id, m.stage_name AS terminal_outcome, e.occurred_at AS terminal_at, e.reason
    FROM stg.stage_events e
    JOIN stg.stage_map m ON m.stage = e.stage AND m.is_terminal
    ORDER BY e.application_id, e.occurred_at
)
SELECT v.application_id, v.req_id, v.person_key, v.source_name,
       v.applied_at,
       s.screen_at, s.hm_screen_at, s.onsite_at, s.offer_at, s.hired_at,
       s.furthest_stage_rank,
       (SELECT stage_name FROM stg.stage_map WHERE stage_rank = s.furthest_stage_rank) AS furthest_stage,
       CASE WHEN s.hired_at IS NOT NULL THEN 'Hired'
            WHEN t.terminal_outcome IS NOT NULL THEN t.terminal_outcome
            ELSE 'In Progress' END                          AS outcome,
       COALESCE(s.hired_at, t.terminal_at)                  AS outcome_at,
       t.reason                                             AS outcome_reason,
       COALESCE(s.has_timestamp_issue, false)               AS has_timestamp_issue
FROM valid_applications v
JOIN stages s USING (application_id)
LEFT JOIN terminal t USING (application_id);
ALTER TABLE core.fact_application
    ADD PRIMARY KEY (application_id),
    ADD FOREIGN KEY (req_id)      REFERENCES core.dim_requisition (req_id),
    ADD FOREIGN KEY (person_key)  REFERENCES core.dim_candidate (person_key),
    ADD FOREIGN KEY (source_name) REFERENCES core.dim_source (source_name),
    ADD CHECK (outcome IN ('Hired', 'Rejected', 'Withdrawn', 'Offer Declined', 'In Progress')),
    ADD CHECK (furthest_stage_rank BETWEEN 1 AND 6);
CREATE INDEX ON core.fact_application (req_id);
CREATE INDEX ON core.fact_application (source_name);
CREATE INDEX ON core.fact_application (applied_at);
ALTER TABLE core.fact_stage_event
    ADD FOREIGN KEY (application_id) REFERENCES core.fact_application (application_id);

CREATE TABLE core.fact_hire AS
SELECT h.application_id, a.req_id, a.source_name, a.hired_at::date AS accepted_date,
       h.start_date, h.retained_90d
FROM stg.hires h
JOIN core.fact_application a USING (application_id);
ALTER TABLE core.fact_hire
    ADD PRIMARY KEY (application_id),
    ADD FOREIGN KEY (application_id) REFERENCES core.fact_application (application_id),
    ADD UNIQUE (req_id);          -- one hire per requisition

CREATE TABLE core.fact_source_cost AS
SELECT month_start, source_name, spend_usd FROM stg.source_costs;
ALTER TABLE core.fact_source_cost
    ADD PRIMARY KEY (month_start, source_name),
    ADD FOREIGN KEY (source_name) REFERENCES core.dim_source (source_name),
    ADD CHECK (spend_usd >= 0);
