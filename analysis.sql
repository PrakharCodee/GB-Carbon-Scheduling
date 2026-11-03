
WITH paired AS (
 SELECT *, actual-forecast AS error FROM intensity
 WHERE actual IS NOT NULL AND forecast IS NOT NULL
), monthly AS (
 SELECT month, COUNT(*) AS paired_intervals, AVG(actual) AS mean_actual_g_kwh,
 AVG(ABS(error)) AS mae_g_kwh, AVG(error) AS bias_g_kwh
 FROM paired GROUP BY month
)
SELECT *, mean_actual_g_kwh-LAG(mean_actual_g_kwh) OVER(ORDER BY month) AS change_g_kwh
FROM monthly ORDER BY month;
