-- Q5. Where do candidates wait the longest?
-- The slowest stage in each department, by median days spent in the stage.
SELECT department, stage_name AS slowest_stage, median_days, p90_days, stage_exits
FROM (
    SELECT *, row_number() OVER (PARTITION BY department ORDER BY median_days DESC) AS rn
    FROM mart.time_in_stage
) t
WHERE rn = 1
ORDER BY median_days DESC;
