# `investigate-codebase` on DuckDB

Four complete runs against [DuckDB](https://github.com/duckdb/duckdb), one per mode.

| Example | Mode | Depth | Evidence it rests on |
|---|---|---|---|
| [01 — Orient in the DuckDB source](01-orient-duckdb-source.md) | `ORIENT` | `working` | Source structure, plus profiler phase names observed at runtime |
| [02 — Trace zone-map pruning](02-trace-zonemap-pruning.md) | `TRACE` | `working` | Controlled timing experiment, optimizer toggles, a correctness oracle |
| [03 — Impact of PR #19235](03-impact-pr-19235.md) | `IMPACT` | `audit` | Resolved base/head, a 12-query differential, a benchmark |
| [04 — Verify a generated report query](04-verify-generated-sql.md) | `VERIFY` | `audit` | Independent oracle, metamorphic and boundary checks, negative control |

Read them in any order. 02 and 03 are the ones that show the skill changing an answer
that a confident-sounding investigation would have gotten wrong.

## Environment used

Every example was run on the same setup, and every example states the revision its claims
are anchored to.

| | |
|---|---|
| Subject | `duckdb/duckdb` at `14eca11bd9d4a0de2ea0f078be588a9c1c5b279c` (tag `v1.5.3`) |
| Binary | `duckdb` CLI `v1.5.3`, `source_id` `14eca11bd9` |
| Python | `duckdb` 1.5.3 on CPython 3.12.0 |
| Platform | macOS (Darwin 25.4.0), x86_64 |

The CLI's `source_id` is the same commit as the checkout, so source claims and runtime
claims in these examples refer to the same build. That is deliberate: it is what lets a
`SOURCE` claim and a `RUNTIME` claim in the same ledger be talking about the same code.

```bash
# source, pinned to the revision the installed binary was built from
git clone --filter=blob:none https://github.com/duckdb/duckdb.git
git -C duckdb checkout 14eca11bd9

# the binary, and the revision it reports
duckdb -c "PRAGMA version;"
# ┌─────────────────┬────────────┬───────────┐
# │ library_version │ source_id  │ codename  │
# ├─────────────────┼────────────┼───────────┤
# │ v1.5.3          │ 14eca11bd9 │ Variegata │
# └─────────────────┴────────────┴───────────┘
```

Nothing here requires building DuckDB from source. Where a check *would* have required it,
the example records that check as `UNKNOWN` with the reason and the command that would
close it.

## Runnable artifacts

[`artifacts/`](artifacts/) holds the files the examples execute:

| File | Used by | What it is |
|---|---|---|
| `differential_unnest_rewriter.py` | 03 | Differential harness: 12 queries × optimizer rule on/off, comparing results and plans |
| `revenue_report.py` | 04 | The generated module under verification |
| `test_revenue_report.py` | 04 | The tests generated alongside it — all pass, all miss the bugs |
| `verify_checks.py` | 04 | The independent checks written from the ticket, including a negative control |
| `fanout_scaling.py` | 04 | Quantifies the fan-out defect and the fixture's blind spots |

```bash
python -m venv venv && ./venv/bin/pip install "duckdb==1.5.3" pytest pytest-cov

./venv/bin/python artifacts/differential_unnest_rewriter.py

cd artifacts
../venv/bin/python -m pytest -q --cov=revenue_report --cov-report=term-missing   # 6 passed, 100%
../venv/bin/python verify_checks.py                                              # 2/5 checks pass
../venv/bin/python fanout_scaling.py
```
