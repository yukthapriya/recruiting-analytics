-- Q1. Where does each department lose the most candidates, compared with the company?
-- step_conversion = share of candidates in the previous stage who reach this one.
WITH company AS (
    SELECT stage_rank, step_conversion AS company_rate
    FROM mart.funnel_conversion
    WHERE department = 'All'
),
ranked AS (
    SELECT d.department,
           d.stage_name                                  AS into_stage,
           d.step_conversion                             AS department_rate,
           c.company_rate,
           round(d.step_conversion - c.company_rate, 4)  AS gap_vs_company,
           rank() OVER (PARTITION BY d.department ORDER BY d.step_conversion - c.company_rate) AS worst_rank
    FROM mart.funnel_conversion d
    JOIN company c USING (stage_rank)
    WHERE d.department <> 'All' AND d.stage_rank > 1
)
SELECT department, into_stage, department_rate, company_rate, gap_vs_company
FROM ranked
WHERE worst_rank = 1
ORDER BY gap_vs_company;
