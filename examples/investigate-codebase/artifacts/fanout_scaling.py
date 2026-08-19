"""Quantify defect 1 and show why the generated fixture cannot see it.

Part one scales the number of line items on a single order and reports what
`monthly_segment_revenue` returns.  Part two queries the generated test fixture
for the three conditions the independent checks probe.
"""

from decimal import Decimal

import duckdb

from revenue_report import SCHEMA, monthly_segment_revenue

print("fan-out scaling: one 100.00 order, N line items totalling the same goods")
print(f"{'line items':>11}  {'reported revenue':>17}  {'inflation':>9}")
for n in range(1, 6):
    c = duckdb.connect()
    c.execute(SCHEMA)
    c.execute("INSERT INTO customers VALUES (1,'enterprise','2023-01-05')")
    c.execute("INSERT INTO orders VALUES (10,1,'2024-03-04 10:00:00',100.00,'shipped')")
    for i in range(n):
        c.execute(f"INSERT INTO order_items VALUES (10,'sku-{i}',1,{100 / n:.2f})")
    revenue = monthly_segment_revenue(c, "2024-03")[0][1]
    print(f"{n:>11}  {str(revenue):>17}  {revenue / Decimal('100.00'):>8.0f}x")
    c.close()

print()
print("why the generated test suite misses it -- its fixture:")
c = duckdb.connect()
c.execute(SCHEMA)
c.execute("""INSERT INTO customers VALUES
    (1,'enterprise','2023-01-05'),(2,'smb','2023-02-11'),(3,'enterprise','2023-03-02')""")
c.execute("""INSERT INTO orders VALUES
    (10,1,'2024-03-04 10:00:00',100.00,'shipped'),
    (11,2,'2024-03-15 09:30:00', 40.00,'shipped'),
    (12,3,'2024-03-20 17:45:00', 60.00,'cancelled'),
    (13,1,'2024-04-02 08:00:00',999.00,'shipped')""")
c.execute("""INSERT INTO order_items VALUES
    (10,'sku-a',2,50.00),(11,'sku-b',4,10.00),(12,'sku-c',1,60.00),(13,'sku-d',3,333.00)""")
print("  line items per order:     ",
      c.execute("SELECT order_id, count(*) FROM order_items GROUP BY order_id ORDER BY order_id").fetchall())
print("  orders with NULL status:  ",
      c.execute("SELECT count(*) FROM orders WHERE status IS NULL").fetchone()[0])
print("  orders with no line items:",
      c.execute("""SELECT count(*) FROM orders o
                   WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)""").fetchone()[0])
c.close()
