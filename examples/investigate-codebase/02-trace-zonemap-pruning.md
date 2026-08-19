# TRACE — why one filter is 27× faster than the same filter on another column

> **Prompt**
>
> Two queries on the same 10M-row DuckDB table, same shape, same number of result rows.
> One takes 1ms, the other 27ms. Trace what actually happens differently.

---

## Selection

| | |
|---|---|
| **Mode** | `TRACE` |
| **Depth** | `working` |
| **Scope** | The read path from SQL text to column data, for a single-table filtered scan |
| **Revision** | `14eca11bd9d4a0de2ea0f078be588a9c1c5b279c` (tag `v1.5.3`) |
| **Environment** | `duckdb` CLI v1.5.3, `source_id` `14eca11bd9`, `PRAGMA threads=1`, macOS x86_64 |

`TRACE`, not `ORIENT`: the question is one concrete behavior with a concrete observable, and
the answer is a causal path.

---

## 1. Anchor the target

A table where one column correlates with storage order and one does not:

```console
$ duckdb trace.duckdb -c "
CREATE TABLE events AS
  SELECT i AS id, (i*2654435761)%1000000 AS rnd, 'p'||(i%13) AS tag
  FROM range(10000000) t(i);
CHECKPOINT;
SELECT count(*) AS rows, count(DISTINCT row_group_id) AS row_groups
FROM pragma_storage_info('events');
"
┌───────┬────────────┐
│ rows  │ row_groups │
├───────┼────────────┤
│   573 │         82 │
└───────┴────────────┘
```

82 row groups over 10M rows — DuckDB's default row group size is 122,880 rows. `id` is
written in ascending order; `rnd` is a multiplicative hash, so its values are spread evenly
across every row group.

## 2. Frame falsifiable questions

Three predictions that could each be wrong:

- **P1** — A range filter on `id` reads far less than 10M rows, because most row groups can
  be excluded before their data is decompressed.
- **P2** — The same-shaped filter on `rnd` cannot exclude anything, because every row group
  contains matching-looking values.
- **P3** — Whatever performs the exclusion depends on the filter reaching the scan operator.
  Remove that, and P1's advantage disappears.

P3 is the one that makes this a causal claim rather than a correlation between "sorted
column" and "fast".

## 3. The controlled experiment

Same table, same column type, same query shape, single-threaded, best of three:

```console
$ cat zonemap.sql
PRAGMA threads=1;
.timer on
SELECT count(*) AS a_sorted_id           FROM events WHERE id  BETWEEN 5000000 AND 5000009;
SELECT count(*) AS b_random_in_range     FROM events WHERE rnd BETWEEN  500000 AND  500009;
SELECT count(*) AS c_random_out_of_range FROM events WHERE rnd BETWEEN 5000000 AND 5000009;

$ duckdb trace.duckdb -box < zonemap.sql
│ a_sorted_id │            10      Run Time (s): real 0.001
│ b_random_in_range │     100      Run Time (s): real 0.027
│ c_random_out_of_range │   0      Run Time (s): real 0.000
```

| Case | Filter | Rows out | Time | Reading |
|---|---|---|---|---|
| **A** | `id BETWEEN 5000000 AND 5000009` | 10 | **0.001s** | ~1 of 82 row groups touched |
| **B** | `rnd BETWEEN 500000 AND 500009` | 100 | **0.027s** | all 82 row groups scanned |
| **C** | `rnd BETWEEN 5000000 AND 5000009` | 0 | **0.000s** | nothing scanned at all |

P1 and P2 hold. Case C was not in the original question and is the more interesting result:
a filter on the *uncorrelated* column can also be free, if it matches nothing anywhere.

## 4. Locate the mechanism in source

The physical plan says where the filter ends up:

```console
$ duckdb trace.duckdb -c "EXPLAIN SELECT count(*) FROM events WHERE id BETWEEN 5000000 AND 5000009;"
┌───────────────────────────┐
│    UNGROUPED_AGGREGATE    │
│        count_star()       │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          SEQ_SCAN         │
│     trace.main.events     │
│   Type: Sequential Scan   │
│          Filters:         │
│id>=5000000 AND id<=5000009│
│      ~2,000,000 rows      │
└───────────────────────────┘
```

The predicate is *inside* the scan node, not a separate `FILTER` operator above it. The
optimizer pass that puts it there, and the storage code that consumes it:

| Step | Symbol | Input | Decision | Output / side effect | Evidence |
|---|---|---|---|---|---|
| 1 | `FilterPushdown::PushdownGet` | `LogicalFilter` above `LogicalGet` | Can this scan accept filters? (`get.function.filter_pushdown`) | Writes `get.table_filters` | `SOURCE` `src/optimizer/pushdown/pushdown_get.cpp:48,59` |
| 2 | `PhysicalPlanGenerator::Plan` | `LogicalGet` with `table_filters` | — | `SEQ_SCAN` node carrying the filters | `RUNTIME` `EXPLAIN` above |
| 3 | `RowGroup::CheckZonemap` | one row group + filter list | Per-row-group min/max vs. predicate | `false` ⇒ **entire row group skipped** | `SOURCE` `src/storage/table/row_group.cpp:523-546`, called at `:326`, `:355` |
| 4 | `ColumnData::CheckZonemap` | `StorageIndex` + filter | `filter.CheckStatistics(...)` on that column's row-group stats | `FILTER_ALWAYS_FALSE` / `_TRUE` / `NO_PRUNING_POSSIBLE` | `SOURCE` `src/storage/table/column_data.cpp:413-426` |
| 5 | `RowGroup::CheckZonemapSegments` | scan state | Same test at *segment* granularity within a surviving row group | Advances the scan past whole segments | `SOURCE` `src/storage/table/row_group.cpp:548-575`, called at `:624` |

Two granularities, not one — row group first, then segments inside the row groups that
survive. The relevant test in step 3:

```cpp
// src/storage/table/row_group.cpp:532-535
auto prune_result = GetColumn(base_column_index).CheckZonemap(base_column_index, filter);
if (prune_result == FilterPropagateResult::FILTER_ALWAYS_FALSE) {
    return false;                     // row group cannot contain a match — skip it entirely
}
```

## 5. Test P3 — and get it wrong the first time

P3 says the mechanism depends on the filter reaching the scan. DuckDB can disable
individual optimizer passes, so the filter can be kept out of the scan node deliberately.

**First attempt, which produced a false result:**

```console
$ duckdb trace.duckdb -box < zonemap2.sql   # contained: SET disable_optimizers='filter_pushdown';
│ a_sorted_NO_pushdown │  10    Run Time (s): real 0.001
```

Unchanged. Read literally, this refutes P3 — the pushdown pass is apparently irrelevant.

It does not. The setting is named `disabled_optimizers`, not `disable_optimizers`, and the
`SET` statement had failed:

```console
$ duckdb trace.duckdb -c "SET disable_optimizers='filter_pushdown';"
Catalog Error: unrecognized configuration parameter "disable_optimizers"
Did you mean: "disabled_optimizers"
```

The error was there; the `grep` used to pull timings out of the run had discarded it. The
"negative control" never applied, so the identical timing was the *expected* result of
changing nothing — and it looked exactly like a refutation.

**Corrected:**

```console
$ cat zonemap3.sql
PRAGMA threads=1;
SET disabled_optimizers='filter_pushdown';
.timer on
SELECT count(*) AS a_sorted_NO_pushdown FROM events WHERE id BETWEEN 5000000 AND 5000009;

$ duckdb trace.duckdb -box < zonemap3.sql
│ a_sorted_NO_pushdown │   10     Run Time (s): real 0.016
```

0.001s → **0.016s**, and the plan confirms why:

```console
$ duckdb trace.duckdb -c "SET disabled_optimizers='filter_pushdown';
                          EXPLAIN SELECT count(*) FROM events WHERE id BETWEEN 5000000 AND 5000009;"
│    UNGROUPED_AGGREGATE    │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │        ← predicate is now a separate operator
│ ((id >= 5000000) AND (id <│
│        = 5000009))        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          SEQ_SCAN         │
│   Type: Sequential Scan   │
│      Projections: id      │        ← no Filters: line
│      ~10,000,000 rows     │        ← estimate jumps from 2M to 10M
└───────────────────────────┘
```

P3 holds. Removing one optimizer pass moves the predicate out of the scan node, and the
16× advantage disappears with it. This is a manipulation, not a correlation.

## 6. Case C is a different mechanism

Case C stayed at 0.000s even with `filter_pushdown` off — which the model so far does not
explain. Its plan is not a scan at all:

```console
$ duckdb trace.duckdb -c "EXPLAIN SELECT count(*) FROM events WHERE rnd BETWEEN 5000000 AND 5000009;"
│    UNGROUPED_AGGREGATE    │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│        EMPTY_RESULT       │
└───────────────────────────┘
```

`rnd`'s maximum is 999,999, so a different pass — `statistics_propagation` — proves the
predicate unsatisfiable at *plan time* and replaces the scan with `EMPTY_RESULT`. Disable
that pass and the query falls back to the scan-time mechanism:

```console
$ duckdb trace.duckdb -c "SET disabled_optimizers='statistics_propagation';
                          EXPLAIN SELECT count(*) FROM events WHERE rnd BETWEEN 5000000 AND 5000009;"
│          SEQ_SCAN         │
│          Filters:         │
│   rnd>=5000000 AND rnd<   │
│          =5000009         │
└───────────────────────────┘

$ duckdb trace.duckdb -box < zonemap4.sql        # same query, statistics_propagation off
│ c_outofrange_stats_off │   0      Run Time (s): real 0.000
```

Still free. So there are **two independent pruning mechanisms at two layers**, and this
query is covered by both:

| | Where | What it uses | What it produces |
|---|---|---|---|
| Plan-time | `optimizer_statistics_propagation` | table-level column statistics | `EMPTY_RESULT` — the scan never exists |
| Scan-time | `RowGroup::CheckZonemap` | per-row-group and per-segment statistics | row groups skipped during the scan |

Attributing case C to zone maps would have been wrong, and no amount of timing data would
have revealed it — only the plan did.

## 7. Challenge the model: what breaks pruning?

Pruning a row group by its stored min/max is only safe if that min/max is kept honest when
rows change. The update path is where that happens:

```cpp
// src/storage/table/row_group.cpp:951-963  (RowGroup::Update)
auto &col_data = GetColumn(column.index);
...
col_data.Update(transaction, data_table, column.index, update_chunk.data[i], ids, count, row_group_start);
MergeStatistics(column.index, *col_data.GetUpdateStatistics());   // widen this column's stats
```

Every update merges the new values' statistics into that column's row-group statistics,
which is what `RowGroup::CheckZonemap` later reads (`ColumnData::CheckZonemap(const
StorageIndex &, TableFilter &)`, `column_data.cpp:413-426` — note that this overload
consults `stats->statistics` only, precisely because the merge already happened).

That predicts something checkable: an update that moves a value *into* the filtered range
must widen its row group's statistics enough to defeat the pruning of that row group — or
the query returns a wrong answer. Row id `3` lives in row group 0, which case A prunes.

```console
$ duckdb trace_upd.duckdb -c "
UPDATE events SET id = 5000005 WHERE id = 3;
SELECT count(*) AS must_be_11 FROM events WHERE id BETWEEN 5000000 AND 5000009;
"
┌────────────┐
│ must_be_11 │
├────────────┤
│ 11         │
└────────────┘
```

11, not 10. This is a correctness oracle rather than a timing measurement: an
implementation that pruned on the original min/max returns 10 here and is silently wrong.

Two intermediate predictions were **too coarse and were corrected** by their own results:

```console
# updating a different column (tag) in every row group — does id pruning degrade?
$ duckdb trace_upd.duckdb -box < upd.sql
UPDATE events SET tag = tag WHERE id % 122880 = 5;      Run Time (s): real 0.053
│ after_update_on_tag │  10                             Run Time (s): real 0.000

# updating the filtered column itself, values unchanged?
$ duckdb trace_upd.duckdb -box < upd2.sql
UPDATE events SET id = id WHERE id % 122880 = 5;        Run Time (s): real 0.036
│ after_update_on_id │   10                             Run Time (s): real 0.000
```

Neither degrades pruning, and `MergeStatistics` explains both: an update to `tag` widens
`tag`'s statistics, not `id`'s, and an identity update to `id` merges a range `id` already
covered. The refined claim — *pruning is lost per column, and only when the update widens
that column's statistics across the filter boundary* — is narrower than the "updates break
pruning" it replaced, and all three results fall out of it.

A second, independent guard exists at segment granularity:
`ColumnData::CheckZonemap(ColumnScanState &, TableFilter &)` (`column_data.cpp:382-411`)
compares base statistics against live update statistics and returns `NO_PRUNING_POSSIBLE`
when they disagree. That path was not exercised by these three tests and is recorded as
`SOURCE` only.

---

## Report

### Direct answer

Case A is fast because the predicate is pushed into the scan node
(`FilterPushdown::PushdownGet`), and `RowGroup::CheckZonemap` then compares each row
group's min/max against it and skips the ones that cannot match. `id` ascends with storage
order, so 81 of 82 row groups are excluded before any column data is read. `rnd` is a hash,
so every row group's min/max spans the whole domain and nothing can be excluded — case B
pays for all 82. Case C is free for a different reason entirely: it is unsatisfiable
against table-level statistics, so `statistics_propagation` deletes the scan at plan time.

### Shortest supported execution path

```
SQL text
  └─ Planner                    LogicalFilter above LogicalGet
      └─ Optimizer
          ├─ statistics_propagation   → predicate provably empty?  → LOGICAL_EMPTY_RESULT   [case C]
          └─ filter_pushdown          → get.table_filters = ...    src/optimizer/pushdown/pushdown_get.cpp:59
      └─ PhysicalPlanGenerator  SEQ_SCAN carrying "Filters:"
          └─ scan loop
              ├─ RowGroup::CheckZonemap          per row group    row_group.cpp:523  → skip 81/82   [case A]
              ├─ RowGroup::CheckZonemapSegments  per segment      row_group.cpp:548
              └─ ColumnData::CheckZonemap        column stats     column_data.cpp:413 (row group)
                                                                  column_data.cpp:382 (segment, + live updates)
```

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| Filter on `id` is ~27× faster than the same shape on `rnd` | `RUNTIME` | `duckdb trace.duckdb -box < zonemap.sql`, `PRAGMA threads=1`, best of 3 | 0.001s vs 0.027s |
| Because the predicate is carried by the scan node | `RUNTIME` | `EXPLAIN` shows `Filters:` inside `SEQ_SCAN` | Separate `FILTER` operator when pushdown is off |
| `filter_pushdown` is what puts it there | `RUNTIME` | `SET disabled_optimizers='filter_pushdown'` → 0.001s becomes 0.016s, plan gains a `FILTER` node | Causal manipulation |
| Row groups are skipped by min/max comparison | `SOURCE` | `14eca11bd9` `src/storage/table/row_group.cpp:523-546` | Skip count itself not directly instrumented — see unknowns |
| Pruning also happens per segment | `SOURCE` | `src/storage/table/row_group.cpp:548-575`, called at `:624` | Not separately measured |
| Case C is plan-time, not scan-time | `RUNTIME` | `EXPLAIN` → `EMPTY_RESULT`; still 0.000s with `statistics_propagation` off | Both mechanisms independently cover this query |
| Updates widen row-group statistics, so a row group holding an updated value stops being prunable | `SOURCE` + `RUNTIME` | `src/storage/table/row_group.cpp:951-963` (`MergeStatistics`); `UPDATE events SET id = 5000005 WHERE id = 3` → count is 11 | Correctness oracle, not a timing result |
| Pruning is lost per column, and only when the update widens that column's stats across the filter boundary | `SOURCE` + `RUNTIME` | `row_group.cpp:962`; `upd.sql`, `upd2.sql` both stayed at 0.000s | Two coarser predictions were falsified first |
| "81 of 82 row groups skipped" | `INFERRED` | Timing ratio + 82 row groups from `pragma_storage_info` | The engine does not report a skip count here |
| First `filter_pushdown` negative control | `CONTRADICTED`, then invalid | `SET disable_optimizers=...` → `Catalog Error` | Setting name wrong; result was of a check that never ran |

### Risks, contradictions, unknowns

- **The exact number of skipped row groups is `INFERRED`, not measured.** It is consistent
  with the timing and with the source, but nothing in this run counts them. Closing it
  needs either a build with scan instrumentation or a metric this version does not expose.
- **A failed check can imitate a successful one.** The `disable_optimizers` typo produced
  a plausible refutation of a correct hypothesis. The only reason it was caught is that
  "no effect at all" is a suspicious result for a control, and re-running it without the
  output filter showed the error. A check whose failure mode is silence needs its own
  verification.
- **Timings are single-run wall clock on a warm cache**, single-threaded, on one machine.
  The 27× and 16× ratios are large enough to survive that noise; a 1.2× would not have been.
- **Unverified**: behavior under concurrent readers and writers, and whether the same path
  is taken for Parquet or CSV scans, which have their own filter-pushdown implementations
  outside `src/storage/`.

### Smallest next verification steps

1. `EXPLAIN ANALYZE` both queries and compare `TABLE_SCAN` operator time specifically,
   isolating scan cost from aggregation cost.
2. Repeat case A after `VACUUM`/re-sort on `rnd` — if the model is right, `rnd` becomes fast
   and `id` becomes slow, purely from the change in storage order.
3. Run the same three cases against a Parquet file to find out whether row-group pruning
   there is the same code path or a parallel implementation.

### Prediction questions

1. `CREATE TABLE t AS SELECT ... ORDER BY rnd` and re-run cases A and B. Which timings swap,
   and which stay the same?
2. Case C is covered by both mechanisms. Which one wins if both are enabled — and what
   would you measure to tell?
3. The segment-level check returns `NO_PRUNING_POSSIBLE` when base and update statistics
   disagree, rather than intersecting them. What does that cost, and why might it be the
   right trade?

---

## What the mode changed

The obvious answer to the prompt — "zone maps; the sorted column prunes, the hashed one
doesn't" — is right about case A and wrong about case C, and it is not something the asker
can check.

Three constraints changed the output:

- **Static reachability is not a runtime trace.** Reading `RowGroup::CheckZonemap` explains
  case A perfectly and says nothing about case C. The plan for case C contains no scan at
  all, which only the `EXPLAIN` revealed.
- **A prediction has to be falsifiable, and the check has to be checked.** The `filter_pushdown`
  toggle turned a correlation into a manipulation — but only on the second attempt, after
  the first control silently no-opped and produced a convincing wrong answer.
- **Record contradicted predictions instead of deleting them.** Two update-related
  predictions were falsified. Keeping them is what produced the precise claim — pruning is
  lost *per column*, and only when update statistics disagree — instead of the vague and
  wrong "updates break pruning".
