# Artifacts

Files the examples execute. Nothing here is part of the skill — these exist so the runs in
the examples can be reproduced and disagreed with.

```bash
python -m venv venv && ./venv/bin/pip install "duckdb==1.5.3" pytest pytest-cov
```

## `differential_unnest_rewriter.py` — used by [example 03](../03-impact-pr-19235.md)

Tests the invariant that a DuckDB optimizer pass may change the plan but not the answer.
Runs 12 unnest queries twice — once with `unnest_rewriter` enabled, once with
`SET disabled_optimizers='unnest_rewriter'` — and compares result multisets and plans.

```bash
./venv/bin/python differential_unnest_rewriter.py
```

Exits non-zero, by design: `q10_correlated_agg` differs. Example 03 works through why that
is unspecified `list()` element ordering rather than a correctness regression, and why it
is still worth reporting.

## `revenue_report.py`, `test_revenue_report.py`, `verify_checks.py` — used by [example 04](../04-verify-generated-sql.md)

`revenue_report.py` is a generated module with three real defects. `test_revenue_report.py`
is the test suite generated alongside it: it passes, at 100% line coverage, and detects none
of them. `verify_checks.py` is written from the ticket instead of from the code, and
includes a negative control.

```bash
./venv/bin/python -m pytest -q --cov=revenue_report --cov-report=term-missing
# 6 passed, 100% coverage

./venv/bin/python verify_checks.py
# 2/5 checks passed  -- exits 1
```

`fanout_scaling.py` quantifies the first defect and queries the generated fixture for the
three conditions it fails to contain:

```bash
./venv/bin/python fanout_scaling.py
```

`revenue_report.py` is kept broken on purpose. It is the subject of the example, not a
utility to reuse.
