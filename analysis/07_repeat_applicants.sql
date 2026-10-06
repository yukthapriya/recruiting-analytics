-- Q7. How many people apply more than once, and do repeat applicants get hired more often?
-- Uses person_key, so the same person registered under two candidate ids counts once.
WITH per_person AS (
    SELECT person_key,
           count(*)                               AS applications,
           bool_or(outcome = 'Hired')             AS was_hired
    FROM core.fact_application
    GROUP BY person_key
)
SELECT CASE WHEN applications = 1 THEN '1 application'
            WHEN applications = 2 THEN '2 applications'
            ELSE '3 or more' END                  AS applicant_group,
       count(*)                                   AS people,
       sum(applications)                          AS applications,
       count(*) FILTER (WHERE was_hired)          AS people_hired,
       round(100.0 * count(*) FILTER (WHERE was_hired) / count(*), 2) AS pct_of_people_hired
FROM per_person
GROUP BY 1
ORDER BY 1;
