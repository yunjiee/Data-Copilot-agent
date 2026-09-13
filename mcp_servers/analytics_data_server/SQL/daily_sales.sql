SELECT
    DATE(created_at) AS order_date,
    COUNT(DISTINCT order_id) AS order_count,
    ROUND(SUM(sale_price), 2) AS revenue
FROM `{table_name}`
WHERE DATE(created_at) BETWEEN @start_date AND @end_date
AND status NOT IN ('Cancelled','Returned')
GROUP BY order_date
ORDER BY order_date