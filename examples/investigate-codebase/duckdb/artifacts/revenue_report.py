"""Monthly revenue reporting over the orders dataset.

Generated from the ticket:

    ANALYTICS-812 -- Monthly revenue by customer segment

    For a given calendar month, report per customer segment:
      * revenue      -- sum of the order total for every order placed in that
                        month that was not cancelled
      * order_count  -- number of such orders
      * units        -- total units shipped across those orders

    An order is "placed in month M" if its order_ts falls in M (UTC).
    Cancelled orders are excluded from every figure.
"""

from __future__ import annotations

import duckdb


SCHEMA = """
CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    segment      VARCHAR,
    signup_ts    TIMESTAMP
);
CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER,
    order_ts     TIMESTAMP,
    total_amount DECIMAL(12, 2),
    status       VARCHAR
);
CREATE TABLE order_items (
    order_id     INTEGER,
    sku          VARCHAR,
    qty          INTEGER,
    unit_price   DECIMAL(12, 2)
);
"""


def monthly_segment_revenue(con: duckdb.DuckDBPyConnection, month: str):
    """Revenue, order count and units per segment for `month` ('YYYY-MM')."""
    return con.execute(
        """
        SELECT
            c.segment                AS segment,
            SUM(o.total_amount)      AS revenue,
            COUNT(DISTINCT o.order_id) AS order_count,
            SUM(i.qty)               AS units
        FROM orders o
        JOIN customers c   ON c.customer_id = o.customer_id
        JOIN order_items i ON i.order_id = o.order_id
        WHERE strftime(o.order_ts, '%Y-%m') = ?
          AND o.status <> 'cancelled'
        GROUP BY c.segment
        ORDER BY c.segment
        """,
        [month],
    ).fetchall()
