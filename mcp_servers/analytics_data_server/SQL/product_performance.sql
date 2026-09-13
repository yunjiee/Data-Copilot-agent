SELECT
    products.id AS product_id,
    products.name AS product_name,
    products.category AS category,
    products.brand AS brand,
    COUNT(
        DISTINCT IF(
            order_items.status NOT IN (
                'Cancelled',
                'Returned'
            ),
            order_items.order_id,
            NULL
        )
    ) AS order_count,
    COUNTIF(
        order_items.status NOT IN (
            'Cancelled',
            'Returned'
        )
    ) AS units_sold,
    ROUND(
        SUM(
            IF(
                order_items.status NOT IN (
                    'Cancelled',
                    'Returned'
                ),
                order_items.sale_price,
                0
            )
        ),
        2
    ) AS revenue,
    COUNTIF(
        order_items.status = 'Returned'
    ) AS return_count,
    SAFE_DIVIDE(
        COUNTIF(
            order_items.status = 'Returned'
        ),
        COUNTIF(
            order_items.status != 'Cancelled'
        )
    ) AS return_rate

FROM `{order_items_table}` AS order_items
INNER JOIN `{products_table}` AS products ON order_items.product_id = products.id
WHERE DATE(order_items.created_at) BETWEEN @start_date AND @end_date
GROUP BY
    product_id,
    product_name,
    category,
    brand
ORDER BY
    revenue DESC
LIMIT @limit