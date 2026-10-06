-- Q6. Which recruiters carry the most requisitions that have been open over 90 days?
SELECT recruiter_name,
       count(*)                                         AS open_requisitions,
       count(*) FILTER (WHERE days_open > 90)           AS open_over_90_days,
       max(days_open)                                   AS oldest_days_open,
       sum(in_progress)                                 AS candidates_in_progress
FROM mart.open_requisition_aging
GROUP BY recruiter_name
HAVING count(*) FILTER (WHERE days_open > 90) > 0
ORDER BY open_over_90_days DESC, oldest_days_open DESC
LIMIT 10;
