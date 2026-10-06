-- Q2. How long does it take to fill a requisition, and is it getting better or worse?
-- Median and 90th percentile days to fill per quarter, with the change from the prior quarter.
SELECT filled_quarter,
       requisitions_filled,
       median_days_to_fill,
       p90_days_to_fill,
       median_days_to_fill - lag(median_days_to_fill) OVER (ORDER BY filled_quarter) AS change_vs_prior_quarter
FROM mart.time_to_fill_summary
WHERE department = 'All'
ORDER BY filled_quarter;
