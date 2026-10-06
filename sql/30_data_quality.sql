-- Rows the pipeline corrected or set aside, kept so they can be inspected and counted.

-- Applications whose requisition was never exported. Excluded from all facts.
CREATE TABLE dq.orphan_applications AS
SELECT a.application_id, a.req_id, a.candidate_id, a.applied_at
FROM stg.applications a
LEFT JOIN core.dim_requisition r USING (req_id)
WHERE r.req_id IS NULL;

-- Stage events that arrived more than once. One copy is kept in staging.
CREATE TABLE dq.duplicate_stage_events AS
SELECT trim(application_id) AS application_id, lower(trim(stage)) AS stage,
       occurred_at::timestamp AS occurred_at, count(*) - 1 AS extra_copies
FROM raw.stage_events
GROUP BY 1, 2, 3
HAVING count(*) > 1;

-- People registered under more than one candidate id.
CREATE TABLE dq.duplicate_candidates AS
SELECT person_key, email_normalized, candidate_record_count - 1 AS extra_records
FROM core.dim_candidate
WHERE candidate_record_count > 1;

-- Applications where a stage is dated before the stage that precedes it.
-- They still count in the funnel but are excluded from every duration metric.
CREATE TABLE dq.out_of_order_applications AS
SELECT application_id, min(stage_name) FILTER (WHERE entered_at < previous_entered_at) AS first_bad_stage
FROM core.fact_stage_event
GROUP BY application_id
HAVING bool_or(entered_at < previous_entered_at);

-- Source spellings that are not in the mapping table (should always be empty).
CREATE TABLE dq.unmapped_source_labels AS
SELECT source_raw, count(*) AS applications
FROM stg.applications
WHERE source_raw IS NOT NULL AND source_name = 'Unknown'
GROUP BY source_raw;

-- One line per check: how many rows were affected, out of how many.
CREATE TABLE dq.summary AS
SELECT * FROM (
    SELECT 1 AS check_order, 'Applications with no matching requisition (excluded)' AS check_name,
           (SELECT count(*) FROM dq.orphan_applications) AS rows_affected,
           (SELECT count(*) FROM raw.applications)       AS rows_checked
    UNION ALL
    SELECT 2, 'Duplicate stage events (extra copies removed)',
           (SELECT COALESCE(sum(extra_copies), 0) FROM dq.duplicate_stage_events),
           (SELECT count(*) FROM raw.stage_events)
    UNION ALL
    SELECT 3, 'Duplicate candidate records (merged into one person)',
           (SELECT COALESCE(sum(extra_records), 0) FROM dq.duplicate_candidates),
           (SELECT count(*) FROM raw.candidates)
    UNION ALL
    SELECT 4, 'Applications with out-of-order stage dates (excluded from durations)',
           (SELECT count(*) FROM dq.out_of_order_applications),
           (SELECT count(*) FROM core.fact_application)
    UNION ALL
    SELECT 5, 'Applications with no source recorded (reported as Unknown)',
           (SELECT count(*) FROM stg.applications WHERE source_raw IS NULL),
           (SELECT count(*) FROM raw.applications)
    UNION ALL
    SELECT 6, 'Applications whose source spelling was standardized',
           (SELECT count(*) FROM stg.applications WHERE source_raw IS NOT NULL AND source_raw <> source_name),
           (SELECT count(*) FROM raw.applications)
    UNION ALL
    SELECT 7, 'Source spellings missing from the mapping table',
           (SELECT count(*) FROM dq.unmapped_source_labels),
           (SELECT count(DISTINCT source_raw) FROM stg.applications)
) s;
ALTER TABLE dq.summary ADD COLUMN pct_affected numeric(6,3);
UPDATE dq.summary SET pct_affected = round(100.0 * rows_affected / NULLIF(rows_checked, 0), 3);
