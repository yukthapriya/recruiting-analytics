-- Q4. Which sources produce hires, and which only produce applicants?
-- hire_lift > 1 means the source supplies a larger share of hires than of applications.
SELECT source_name,
       applications,
       hires,
       round(100 * share_of_applications, 1)                          AS pct_of_applications,
       round(100 * share_of_hires, 1)                                 AS pct_of_hires,
       round(share_of_hires / NULLIF(share_of_applications, 0), 2)    AS hire_lift,
       round(100 * offer_acceptance_rate, 1)                          AS offer_acceptance_pct,
       round(100 * retention_90d_rate, 1)                             AS retention_90d_pct,
       cost_per_hire_usd
FROM mart.source_quality
ORDER BY hire_lift DESC NULLS LAST;
