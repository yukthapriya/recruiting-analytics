-- Q3. Which departments and levels are slowest to fill?
SELECT department,
       count(*)                                                              AS requisitions_filled,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY days_to_fill)::numeric(6,1) AS median_days_to_fill,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY days_to_fill)::numeric(6,1) AS p90_days_to_fill,
       round(avg(applications_received), 0)                                  AS avg_applications_per_requisition
FROM mart.time_to_fill
GROUP BY department
ORDER BY median_days_to_fill DESC;
