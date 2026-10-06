SET client_min_messages = warning;
-- Rebuild everything from scratch on each run so results never depend on leftovers.
DROP SCHEMA IF EXISTS raw  CASCADE;
DROP SCHEMA IF EXISTS stg  CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS dq   CASCADE;
DROP SCHEMA IF EXISTS mart CASCADE;

CREATE SCHEMA raw;   -- the ATS export exactly as it landed (all text)
CREATE SCHEMA stg;   -- typed, trimmed, standardized, de-duplicated
CREATE SCHEMA core;  -- dimensions and facts with enforced keys
CREATE SCHEMA dq;    -- rows the pipeline set aside, and a summary of why
CREATE SCHEMA mart;  -- reporting tables that Tableau reads
