# VERIFY — a generated DuckDB report query with a green test suite

> **Prompt**
>
> An agent wrote `revenue_report.py` and its tests from ticket ANALYTICS-812. Tests pass.
> Before I put this in the monthly close, check whether it's actually right.

---

## Selection

| | |
|---|---|
| **Mode** | `VERIFY` |
| **Depth** | `audit` — the output feeds a financial close; a wrong number is not self-announcing |
| **Scope** | `monthly_segment_revenue()` and its test suite |
| **Environment** | `duckdb` 1.5.3 (Python), CPython 3.12.0, pytest 9.1.1 |
| **Artifacts** | [`revenue_report.py`](artifacts/revenue_report.py), [`test_revenue_report.py`](artifacts/test_revenue_report.py), [`verify_checks.py`](artifacts/verify_checks.py), [`fanout_scaling.py`](artifacts/fanout_scaling.py) |

---

## 1. Establish the oracle *before* reading the implementation

Per the guide, the independent sources of intended behavior come first — otherwise the
implementation defines what "correct" means and the check becomes a restatement of the code.

The ticket, quoted in the module's own docstring:

> **ANALYTICS-812 — Monthly revenue by customer segment**
>
> For a given calendar month, report per customer segment:
> * `revenue` — sum of the order total for every order placed in that month that was not cancelled
> * `order_count` — number of such orders
> * `units` — total units shipped across those orders
>
> An order is "placed in month M" if its `order_ts` falls in M (UTC). Cancelled orders are
> excluded from every figure.

This is a usable oracle: three quantities, each defined over a stated row population. It
yields six behavioral claims:

| | Claim |
|---|---|
| **R1** | `revenue` = sum of `orders.total_amount` over non-cancelled orders in the month |
| **R2** | `order_count` = the number of such orders |
| **R3** | `units` = sum of `order_items.qty` over those orders |
| **M1** | *(metamorphic)* Re-splitting an order's line items must not change `revenue` or `order_count` — the ticket defines revenue over orders, not over lines |
| **B1** | *(boundary)* An order whose `status` is `NULL` is not cancelled, so it counts |
| **B2** | *(boundary)* An order with no line items still contributes `revenue` and `order_count` |

M1, B1, and B2 follow from the ticket without reading a line of the implementation. That
matters: they are the three checks the implementation and its tests both miss.

## 2. Assess the evidence already on offer

```console
$ cd artifacts && python -m pytest -q --cov=revenue_report --cov-report=term-missing
......                                                                   [100%]
================================ tests coverage ================================
Name                Stmts   Miss  Cover   Missing
-------------------------------------------------
revenue_report.py       5      0   100%
-------------------------------------------------
TOTAL                   5      0   100%
6 passed in 0.10s
```

6 passing tests, 100% line coverage, and six test names that read like a specification:
`test_revenue_per_segment`, `test_excludes_cancelled_orders`, `test_excludes_other_months`,
`test_order_count_and_units`, `test_empty_month_returns_no_rows`, `test_groups_by_segment`.

None of this is an oracle. The tests were generated from the same understanding as the
query, so they are **correlated evidence**: if that understanding is wrong, both are wrong
together and agree with each other. Coverage compounds the problem — it measures that the
single SQL statement executed, which one test would have achieved.

What the fixture contains is more informative than what the tests assert:

```console
$ python fanout_scaling.py            # second half of the output
why the generated test suite misses it -- its fixture:
  line items per order:      [(10, 1), (11, 1), (12, 1), (13, 1)]
  orders with NULL status:   0
  orders with no line items: 0
```

Every order has exactly one line item. No `NULL` statuses. No item-less orders. The fixture
is blind in exactly the three places M1, B1, and B2 probe — and the odds of that being
coincidence are low, because a model that does not see a failure mode does not build a
fixture that exposes it.

## 3. The implementation

```python
SELECT
    c.segment                  AS segment,
    SUM(o.total_amount)        AS revenue,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(i.qty)                 AS units
FROM orders o
JOIN customers c   ON c.customer_id = o.customer_id
JOIN order_items i ON i.order_id = o.order_id
WHERE strftime(o.order_ts, '%Y-%m') = ?
  AND o.status <> 'cancelled'
GROUP BY c.segment
ORDER BY c.segment
```

It reads well, and `COUNT(DISTINCT o.order_id)` in particular reads like the work of someone
who thought about the join. That detail matters later.

## 4. The independent checks

[`artifacts/verify_checks.py`](artifacts/verify_checks.py) is written against the ticket,
not against the query. It builds its own datasets, and it carries its own reference
implementation derived from R1–R3 — revenue and order count from `orders` alone, units in a
separate correlated subquery, so the line-item join cannot influence the money:

```python
SELECT c.segment,
       SUM(o.total_amount)                               AS revenue,
       COUNT(*)                                          AS order_count,
       COALESCE(SUM((SELECT SUM(i.qty) FROM order_items i
                     WHERE i.order_id = o.order_id)), 0) AS units
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE strftime(o.order_ts, '%Y-%m') = ?
  AND (o.status IS DISTINCT FROM 'cancelled')
GROUP BY c.segment
ORDER BY c.segment
```

```console
$ python verify_checks.py
PASS  D1  one order, one line item
FAIL  M1  same order split across two line items
        implementation : [('enterprise', Decimal('200.00'), 1, 2)]
        oracle         : [('enterprise', Decimal('100.00'), 1, 2)]
FAIL  B1  order with NULL status
        implementation : []
        oracle         : [('enterprise', Decimal('100.00'), 1, 2)]
FAIL  B2  order with no line items
        implementation : []
        oracle         : [('enterprise', Decimal('100.00'), 1, 0)]
PASS  N1  negative control: seeded fault is detected by the comparison

2/5 checks passed
```

Three defects. Two controls frame them:

- **D1 passes** — on the shape the generated fixture uses, implementation and oracle agree.
  The checks are not failing everything; the disagreement is specific.
- **N1 passes** — a fault seeded into the oracle side is detected by the comparison. Without
  this, three `FAIL`s would be indistinguishable from a comparison that always fails.

### Defect 1 — join fan-out inflates revenue (M1)

`JOIN order_items` multiplies each order row by its line-item count before `SUM` sees it.

```console
$ python fanout_scaling.py            # first half of the output
fan-out scaling: one 100.00 order, N line items totalling the same goods
 line items   reported revenue  inflation
          1             100.00         1x
          2             200.00         2x
          3             300.00         3x
          4             400.00         4x
          5             500.00         5x
```

Revenue is multiplied by the number of line items. On real order data — where a multi-item
order is the normal case — the monthly total is inflated by roughly the average basket size.

This is the defect the `COUNT(DISTINCT o.order_id)` makes hard to see. `order_count` is
*correct*: the `DISTINCT` compensates for exactly this fan-out. A reviewer who checks whether
the author understood the join finds evidence that they did, on the very line above the one
that gets it wrong. `units` is also correct — quantity genuinely lives at line-item grain.
Only `revenue`, at order grain, is wrong.

### Defect 2 — `<>` drops NULL status (B1)

`o.status <> 'cancelled'` evaluates to `NULL` when `status` is `NULL`, and `WHERE` keeps only
rows that are `TRUE`. Orders with unknown status disappear from every figure — not flagged,
not errored, just absent. The ticket says to exclude cancelled orders; a `NULL` status is
not `'cancelled'`. `IS DISTINCT FROM` is the operator that matches the requirement.

### Defect 3 — inner join drops order-less orders (B2)

`JOIN order_items` is inner, so an order with no line-item rows contributes nothing —
not even its revenue. Any order that is paid but not yet picked, or is a pure service
charge, vanishes.

All three defects fail the same way: **silently, in the direction of a plausible number.**
The report renders, the totals look like money, and nothing indicates that revenue is
inflated by fan-out while a different subset of revenue has been dropped entirely.

## 5. A note on what was *not* checked

The `WHERE strftime(o.order_ts, '%Y-%m') = ?` predicate is wrapped in a function call, so it
cannot be used for zone-map pruning the way a range predicate on `order_ts` could — see
[example 02](02-trace-zonemap-pruning.md). That is a performance observation, not a
correctness one, and it was not measured here.

The ticket says "UTC". `orders.order_ts` is `TIMESTAMP`, which in DuckDB is timezone-naive,
so `strftime` performs no conversion and the column's own semantics decide what UTC means.
Whether the ingest path writes UTC is outside this repository and is recorded as `UNKNOWN`,
not as a pass.

---

## Report

### Direct answer

The query is wrong in three independent ways, and its test suite cannot detect any of them.
`revenue` is multiplied by the number of line items per order; orders with `NULL` status are
silently excluded from every figure; orders with no line items are silently excluded from
every figure. `order_count` and `units` are correct. Do not use this for a financial close.

### Verification matrix

| Claim | Independent oracle | Implementation path | Check | Negative control | Result |
|---|---|---|---|---|---|
| R1 `revenue` = Σ non-cancelled order totals | Ticket | `SUM(o.total_amount)` after `JOIN order_items` | D1, M1 | N1 | **FAIL** — ×N line items |
| R2 `order_count` | Ticket | `COUNT(DISTINCT o.order_id)` | D1, M1 | N1 | PASS |
| R3 `units` = Σ `qty` | Ticket | `SUM(i.qty)` | D1, M1 | N1 | PASS |
| M1 line-item split is revenue-neutral | Ticket defines revenue at order grain | inner join to `order_items` | M1 | N1 | **FAIL** — 100.00 → 200.00 |
| B1 `NULL` status counts | Three-valued logic + ticket | `o.status <> 'cancelled'` | B1 | N1 | **FAIL** — row dropped |
| B2 item-less order counts | Ticket defines revenue over orders | `JOIN order_items` | B2 | N1 | **FAIL** — row dropped |
| Month boundary / UTC semantics | Ingest contract | `strftime(order_ts, '%Y-%m')` | — | — | `UNKNOWN` — contract not available |
| Cancelled orders excluded | Ticket | `o.status <> 'cancelled'` | generated suite | — | PASS (for non-`NULL` status) |

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| Generated suite passes with 100% line coverage | `RUNTIME` | `pytest -q --cov=revenue_report` | 6 passed; 5/5 statements |
| Coverage is uninformative here | `INFERRED` | Module is one SQL statement in one function | Any single test reaches 100% |
| Fixture has 1 line item per order, 0 `NULL` statuses, 0 item-less orders | `RUNTIME` | Direct query of the fixture | Blind exactly where the defects are |
| Revenue scales linearly with line-item count | `RUNTIME` | N = 1..5, `revenue_report.py` unmodified | 100 / 200 / 300 / 400 / 500 |
| `NULL` status drops the order | `RUNTIME` | `verify_checks.py` B1 | Implementation `[]`, oracle 1 row |
| Item-less order drops the order | `RUNTIME` | `verify_checks.py` B2 | Implementation `[]`, oracle 1 row |
| `order_count` and `units` are correct | `RUNTIME` | D1 and M1 agree on columns 3 and 4 | Holds for the shapes tested |
| Checks can detect a fault | `RUNTIME` | N1 negative control | Seeded fault detected |
| Checks are not vacuously failing | `RUNTIME` | D1 passes on the single-item shape | Disagreement is specific |
| UTC semantics of `order_ts` | `UNKNOWN` | — | Requires the ingest contract, not in scope |
| Behavior at production data volume | `UNKNOWN` | — | All checks run on ≤5-row datasets |
| Decimal precision under `SUM` at scale | `UNKNOWN` | — | `DECIMAL(12,2)` overflow not exercised |

### Calibrated conclusion

> At `revenue_report.py` as generated, running under duckdb 1.5.3 / CPython 3.12.0, checks
> D1, M1, B1, B2 and negative control N1 support the following: `order_count` and `units`
> satisfy R2 and R3 for the datasets tested; `revenue` violates R1 whenever any order has a
> number of line items other than one, and the reported population violates the ticket's row
> definition for orders with `NULL` status and for orders with no line items. UTC month-
> boundary semantics and behavior at production volume remain unverified.
>
> The generated test suite passes and does not bear on this conclusion: it is correlated
> evidence, and its fixture excludes all three failing conditions.

No numeric probability of correctness is given. The defects are demonstrated, and the
untested regions are named.

### Recommendation

**Block.** Three of six behavioral claims fail, in a financial reporting path, with silent
failure modes. Human approval is warranted regardless of what a fix looks like, per the
guide's rule for high-consequence changes.

Ordered by expected information gain, the next steps are:

1. Re-run `verify_checks.py` against any proposed fix. It already encodes the requirement
   and has a working negative control, so it is the cheapest regression gate available.
2. Add a fourth check for the ticket's month boundary — an order at `23:59:59` on the last
   day of the month, and one at `00:00:00` on the first — the remaining boundary in the
   requirement that no check covers.
3. Resolve the UTC question against the ingest contract. It is currently `UNKNOWN` and no
   amount of testing in this repository can close it.
4. Only then run against a production-sized dataset, to exercise `DECIMAL(12,2)` limits.

Not recommended: asking the generating model for more tests. That adds correlated evidence
to a body of evidence whose problem is correlation.

---

## What the mode changed

The default response to "tests pass, is it right?" is to read the query, find it plausible,
note the 100% coverage, and agree. Every observation in that chain is true, and the
conclusion is wrong.

Four constraints changed the output:

- **Establish the oracle before reading the implementation.** M1, B1, and B2 come from the
  ticket. Read the query first and they do not occur to you, because the query is a coherent
  answer to a subtly different question — and coherence is what reading it produces.
- **Treat co-generated tests as correlated evidence.** The suite is not weak. It is
  well-named, well-structured, and tests six real behaviors. It is also blind in exactly the
  three places its author was blind, which is what correlation means and why counting tests
  does not help.
- **Coverage measures execution, not assertion quality.** 100% of five statements, and three
  defects. The number was never evidence about correctness.
- **Test the test.** Three failures are only informative if the comparison can pass (D1) and
  can detect a seeded fault (N1). Without both controls, `2/5` is a number about the checks,
  not about the code — and in [example 02](02-trace-zonemap-pruning.md) exactly that
  distinction is what a silently no-opping control destroyed.
