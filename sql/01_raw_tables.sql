-- Landing tables. Every column is text on purpose: nothing is rejected at load,
-- so bad values are visible and counted instead of silently dropped.
CREATE TABLE raw.recruiters   (recruiter_id text, recruiter_name text);
CREATE TABLE raw.requisitions (req_id text, title text, department text, location text, level text,
                               recruiter_id text, hiring_manager_id text, opened_date text,
                               status text, closed_date text);
CREATE TABLE raw.candidates   (candidate_id text, email text, created_at text);
CREATE TABLE raw.applications (application_id text, candidate_id text, req_id text, source text, applied_at text);
CREATE TABLE raw.stage_events (event_id text, application_id text, stage text, occurred_at text, reason text);
CREATE TABLE raw.hires        (application_id text, start_date text, retained_90d text);
CREATE TABLE raw.source_costs (month text, source text, spend_usd text);
