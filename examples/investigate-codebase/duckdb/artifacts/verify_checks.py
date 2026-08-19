"""Independent checks for ANALYTICS-812.

Written from the ticket text and the table schema only.  It deliberately does
not reuse the generated module's fixture or its tests: those are correlated
evidence, since the same model produced the query and the tests that bless it.

Oracles used
  R1 revenue      = sum of orders.total_amount over non-cancelled orders in the month
  R2 order_count  = number of such orders
  R3 units        = sum of order_items.qty over those orders
  M1 (metamorphic) splitting one order line into two lines with the same total
                   quantity must not change revenue or order_count
  B1 (boundary)   an order whose status is NULL is not cancelled, so it counts
  B2 (boundary)   an order with no line items still contributes revenue
"""

from __future__ import annotations

from decimal import Decimal

import duckdb

from revenue_report import SCHEMA, monthly_segment_revenue

MONTH = "2024-03"


def fresh():
    c = duckdb.connect()
    c.execute(SCHEMA)
    c.execute("INSERT INTO customers VALUES (1,'enterprise','2023-01-05'),(2,'smb','2023-02-11')")
    return c


def reference(con, month):
    """Reference implementation derived from the ticket, not from the code.

    Revenue and order_count come from `orders` alone -- the line-item join can
    only change `units`, so it is done in a separate scalar subquery.
    """
    return con.execute(
        """
        SELECT c.segment,
               SUM(o.total_amount)                                        AS revenue,
               COUNT(*)                                                   AS order_count,
               COALESCE(SUM((SELECT SUM(i.qty) FROM order_items i
                             WHERE i.order_id = o.order_id)), 0)          AS units
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE strftime(o.order_ts, '%Y-%m') = ?
          AND (o.status IS DISTINCT FROM 'cancelled')
        GROUP BY c.segment
        ORDER BY c.segment
        """,
        [month],
    ).fetchall()


def show(title, impl, ref):
    ok = impl == ref
    print(f"{'PASS' if ok else 'FAIL'}  {title}")
    if not ok:
        print(f"        implementation : {impl}")
        print(f"        oracle         : {ref}")
    return ok


results = []

# --- D1: differential vs the reference on a single-line-item dataset -----------
con = fresh()
con.execute("INSERT INTO orders VALUES (10,1,'2024-03-04 10:00:00',100.00,'shipped')")
con.execute("INSERT INTO order_items VALUES (10,'sku-a',2,50.00)")
results.append(show("D1  one order, one line item", monthly_segment_revenue(con, MONTH), reference(con, MONTH)))
con.close()

# --- M1: metamorphic -- split one line into two, revenue must not move --------
con = fresh()
con.execute("INSERT INTO orders VALUES (10,1,'2024-03-04 10:00:00',100.00,'shipped')")
con.execute("INSERT INTO order_items VALUES (10,'sku-a',1,50.00),(10,'sku-b',1,50.00)")
results.append(show("M1  same order split across two line items", monthly_segment_revenue(con, MONTH), reference(con, MONTH)))
con.close()

# --- B1: boundary -- NULL status is not 'cancelled' ---------------------------
con = fresh()
con.execute("INSERT INTO orders VALUES (10,1,'2024-03-04 10:00:00',100.00,NULL)")
con.execute("INSERT INTO order_items VALUES (10,'sku-a',2,50.00)")
results.append(show("B1  order with NULL status", monthly_segment_revenue(con, MONTH), reference(con, MONTH)))
con.close()

# --- B2: boundary -- order with no line items ---------------------------------
con = fresh()
con.execute("INSERT INTO orders VALUES (10,1,'2024-03-04 10:00:00',100.00,'shipped')")
results.append(show("B2  order with no line items", monthly_segment_revenue(con, MONTH), reference(con, MONTH)))
con.close()

# --- N1: negative control -- do these checks detect a fault at all? -----------
# Inject a known fault into the ORACLE side (double every revenue) and confirm
# D1, which passed above, now fails.  If it still passes, the check is inert.
con = fresh()
con.execute("INSERT INTO orders VALUES (10,1,'2024-03-04 10:00:00',100.00,'shipped')")
con.execute("INSERT INTO order_items VALUES (10,'sku-a',2,50.00)")
impl = monthly_segment_revenue(con, MONTH)
mutated = [(seg, rev * 2, cnt, units) for seg, rev, cnt, units in reference(con, MONTH)]
detected = impl != mutated
print(f"{'PASS' if detected else 'FAIL'}  N1  negative control: seeded fault is detected by the comparison")
results.append(detected)
con.close()

print()
print(f"{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
