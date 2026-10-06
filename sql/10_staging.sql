-- ---------------------------------------------------------------------------
-- Reference data
-- ---------------------------------------------------------------------------

-- Every spelling of a source seen in the export, mapped to one name.
-- A test fails if a new, unmapped spelling ever appears.
CREATE TABLE stg.source_label_map (
    raw_label   text PRIMARY KEY,   -- lower-cased, single-spaced
    source_name text NOT NULL
);
INSERT INTO stg.source_label_map VALUES
    ('job board', 'Job Board'), ('jobboard', 'Job Board'),
    ('careers site', 'Careers Site'), ('career site', 'Careers Site'),
    ('linkedin', 'LinkedIn'), ('linked in', 'LinkedIn'),
    ('referral', 'Referral'), ('employee referral', 'Referral'),
    ('university', 'University'), ('campus', 'University'),
    ('agency', 'Agency'),
    ('internal', 'Internal');

-- The hiring stages in order. Terminal events have no rank.
CREATE TABLE stg.stage_map (
    stage       text PRIMARY KEY,
    stage_name  text NOT NULL,
    stage_rank  int,
    is_terminal boolean NOT NULL
);
INSERT INTO stg.stage_map VALUES
    ('applied',          'Applied',               1, false),
    ('recruiter_screen', 'Recruiter Screen',      2, false),
    ('hm_screen',        'Hiring Manager Screen', 3, false),
    ('onsite',           'Onsite',                4, false),
    ('offer_extended',   'Offer',                 5, false),
    ('offer_accepted',   'Hired',                 6, false),
    ('offer_declined',   'Offer Declined',     NULL, true),
    ('rejected',         'Rejected',           NULL, true),
    ('withdrawn',        'Withdrawn',          NULL, true);

-- ---------------------------------------------------------------------------
-- Typed and cleaned views over the raw export
-- ---------------------------------------------------------------------------
CREATE VIEW stg.recruiters AS
SELECT trim(recruiter_id) AS recruiter_id, trim(recruiter_name) AS recruiter_name
FROM raw.recruiters;

CREATE VIEW stg.requisitions AS
SELECT trim(req_id)                    AS req_id,
       trim(title)                     AS title,
       trim(department)                AS department,
       trim(location)                  AS location,
       trim(level)                     AS level,
       trim(recruiter_id)              AS recruiter_id,
       trim(hiring_manager_id)         AS hiring_manager_id,
       opened_date::date               AS opened_date,
       lower(trim(status))             AS status,
       NULLIF(trim(closed_date), '')::date AS closed_date
FROM raw.requisitions;

-- One person can register more than once with the same address typed differently.
CREATE VIEW stg.candidates AS
SELECT trim(candidate_id)      AS candidate_id,
       email                   AS email_raw,
       lower(trim(email))      AS email_normalized,
       created_at::timestamp   AS created_at
FROM raw.candidates;

CREATE VIEW stg.applications AS
SELECT trim(a.application_id)                AS application_id,
       trim(a.candidate_id)                  AS candidate_id,
       trim(a.req_id)                        AS req_id,
       NULLIF(trim(a.source), '')            AS source_raw,
       COALESCE(m.source_name, 'Unknown')    AS source_name,
       a.applied_at::timestamp               AS applied_at
FROM raw.applications a
LEFT JOIN stg.source_label_map m
       ON m.raw_label = lower(regexp_replace(trim(a.source), '\s+', ' ', 'g'));

-- The export sometimes sends the same event twice. Keep one copy.
CREATE VIEW stg.stage_events AS
SELECT DISTINCT ON (e.application_id, e.stage, e.occurred_at)
       trim(e.event_id)               AS event_id,
       trim(e.application_id)         AS application_id,
       lower(trim(e.stage))           AS stage,
       e.occurred_at::timestamp       AS occurred_at,
       NULLIF(trim(e.reason), '')     AS reason
FROM raw.stage_events e
ORDER BY e.application_id, e.stage, e.occurred_at, e.event_id;

CREATE VIEW stg.hires AS
SELECT trim(application_id)                  AS application_id,
       start_date::date                      AS start_date,
       NULLIF(trim(retained_90d), '')::boolean AS retained_90d   -- NULL = too recent to know
FROM raw.hires;

CREATE VIEW stg.source_costs AS
SELECT month::date AS month_start, trim(source) AS source_name, spend_usd::numeric(12,2) AS spend_usd
FROM raw.source_costs;
