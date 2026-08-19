# IMPACT — what DuckDB PR #19235 actually changes

> **Prompt**
>
> Analyze https://github.com/duckdb/duckdb/pull/19235 for behavioral impact and blast
> radius. It's an optimizer change and it's already merged — I want to know what it did to
> query behavior, not a summary of the diff.

---

## Selection

| | |
|---|---|
| **Mode** | `IMPACT` |
| **Depth** | `audit` — an optimizer rewrite that produces wrong results produces *silently* wrong results |
| **Scope** | PR [duckdb/duckdb#19235](https://github.com/duckdb/duckdb/pull/19235), `+106/-8` across 4 files |
| **Base** | `44b706b2b79dbc04df8396da698f256acac07dc1` |
| **Head** | `5c465bafebf223ba7a17f04a7365d86fc8fc20b7` |
| **Merge commit** | `875cf9d201f7b85b0b4e2af0dc0fc5de7ed4aff1`, 2025-11-10 |
| **Observed in** | `duckdb` v1.5.3 (`source_id` `14eca11bd9`) — the first release containing the change is v1.5.0 |

---

## 1. Anchor the comparison

```console
$ gh pr view 19235 -R duckdb/duckdb --json baseRefOid,headRefOid,mergeCommit,mergedAt,author
baseRefOid:  44b706b2b79dbc04df8396da698f256acac07dc1
headRefOid:  5c465bafebf223ba7a17f04a7365d86fc8fc20b7
mergeCommit: 875cf9d201f7b85b0b4e2af0dc0fc5de7ed4aff1
mergedAt:    2025-11-10T14:02:48Z
author:      flashmouse
```

The merge commit has two parents, and **neither of them is the base to diff against**:

```console
$ git log -1 --format='%P' 875cf9d201f7b85b0b4e2af0dc0fc5de7ed4aff1
23d01e6975f847a9f143e2f153304bdf06cf3803 5c465bafebf223ba7a17f04a7365d86fc8fc20b7

$ git merge-base 23d01e6975f847a9f143e2f153304bdf06cf3803 5c465bafebf223ba7a17f04a7365d86fc8fc20b7
44b706b2b79dbc04df8396da698f256acac07dc1

$ git rev-list --count 44b706b2b79dbc04df8396da698f256acac07dc1..23d01e6975f847a9f143e2f153304bdf06cf3803
33
```

`main` advanced **33 commits** while the PR was open. Diffing against the merge commit's
first parent would fold those 33 unrelated commits into the analysis. Here GitHub's
`baseRefOid` and the merge base agree, so both are recorded and the merge base is used.

```console
$ git diff --stat 44b706b2 5c465baf
 src/include/duckdb/optimizer/unnest_rewriter.hpp |  3 +-
 src/include/duckdb/planner/expression_binder.hpp |  5 +-
 src/optimizer/unnest_rewriter.cpp                | 72 ++++++++++++++++++++++--
 test/optimizer/unnest_rewriter.test_slow         | 34 +++++++++++
 4 files changed, 106 insertions(+), 8 deletions(-)
```

Nothing generated, vendored, or formatting-only. All four files are semantic.

```console
$ git tag --contains 875cf9d201f7b85b0b4e2af0dc0fc5de7ed4aff1 | head -3
v1.5.0
v1.5.1
v1.5.2
```

Shipped in v1.5.0, so the change is present in the v1.5.3 binary used below.

## 2. What the diff does

`UnnestRewriter` is one of DuckDB's 34 optimizer passes. It removes a `DELIM_JOIN` — the
plan shape used for correlated subqueries — when the correlation is just an `UNNEST`.
Before this PR it recognized one plan pattern; the PR adds a second.

```cpp
// src/optimizer/unnest_rewriter.cpp, added by the PR
	// pattern1: delim_get -> unnest-> projection
	if (curr_op->get()->type == LogicalOperatorType::LOGICAL_UNNEST &&
	    curr_op->get()->children[0]->type == LogicalOperatorType::LOGICAL_DELIM_GET) {
		candidates.push_back(op);
		return;
	}

	curr_op = &delim_join.children[other_idx];
	if (curr_op->get()->type == LogicalOperatorType::LOGICAL_GET) {
		auto &get = curr_op->get()->Cast<LogicalGet>();
		if (!ExpressionBinder::IsUnnestFunction(get.function.name)) {
			return;
		}
		// pattern2: delim_get -> projection -> table_in_out(unnest)
		auto &unnest_get_ref = curr_op->get()->Cast<LogicalGet>();
		if (unnest_get_ref.ordinality_idx.IsValid()) {
			// we also unnest delim_index so cannot rewrite it
			return;
		}
		...
		replacer.stop_operator = proj;
		replacer.VisitOperator(*root);          // rewrites bindings across the whole plan
		candidates.push_back(op);
	}
```

In SQL terms, pattern 1 is the scalar form (`SELECT UNNEST(t.arr) ...` in a subquery),
pattern 2 is the table-function form (`CROSS JOIN unnest(arr) AS values(value)`). Pattern 2
is what the PR adds.

Two structural facts stand out and drive the rest of the analysis:

- `FindCandidates` gained a `root` parameter so the new branch can call
  `replacer.VisitOperator(*root)` — it **mutates the whole plan tree while the candidate
  search is still recursing over it**.
- `ExpressionBinder::IsUnnestFunction` moved from `protected` to `public` in
  `src/include/duckdb/planner/expression_binder.hpp` — a header change, not just an
  implementation change.

## 3. Isolating base behavior without building the base

Observing base behavior would normally mean building DuckDB at `44b706b2`. There is a
cheaper isolation that is also *more* precise: DuckDB can disable a single optimizer pass
at runtime.

```sql
SET disabled_optimizers='unnest_rewriter';
```

That is not "the base revision" — it is "this binary with this rule off" — but for queries
whose only relevant rewrite is this rule, it isolates the rule far better than comparing
two releases, which would differ by thousands of unrelated commits.

```console
$ duckdb -c "
CREATE TABLE with_array(foo INT, arr DOUBLE[]);
INSERT INTO with_array VALUES(1,[1,2,3]),(2,[4,5,6]);
EXPLAIN SELECT foo, value FROM with_array CROSS JOIN unnest(arr) AS values(value);"

│         PROJECTION        │
│           UNNEST          │
│          SEQ_SCAN         │

$ duckdb -c "... ; SET disabled_optimizers='unnest_rewriter';
EXPLAIN SELECT foo, value FROM with_array CROSS JOIN unnest(arr) AS values(value);"

│      LEFT_DELIM_JOIN      │
│      Join Type: INNER     │
│     delim_index IS NOT    ├──────────────┬────────────────────┐
│  DISTINCT FROM delim_index│              │                    │
│       Delim Index: 1      │              │                    │
        ...                          HASH_JOIN           HASH_GROUP_BY
                                     SEQ_SCAN             DELIM_SCAN
```

Extracting just the operator names from each plan:

```
rule ON : ['PROJECTION', 'UNNEST', 'SEQ_SCAN']
rule OFF: ['LEFT_DELIM_JOIN', 'PROJECTION', 'HASH_JOIN', 'HASH_GROUP_BY',
           'STREAMING_WINDOW', 'COLUMN_DATA_SCAN', 'INOUT_FUNCTION', 'SEQ_SCAN',
           'PROJECTION', 'DELIM_SCAN']
```

Three operators become ten, including a join, a hash aggregate, a streaming window, and a
delim scan. That is the intended change, visible in the shipped binary.

### What the toggle cannot tell us

```console
$ ./venv/bin/python -c "..."   # see artifacts/differential_unnest_rewriter.py
pattern1 (scalar UNNEST in subquery, PRE-EXISTING rewrite)
   rule ON  -> delim_join present: False
   rule OFF -> delim_join present: True
pattern2 (table-function unnest, ADDED by PR 19235)
   rule ON  -> delim_join present: False
   rule OFF -> delim_join present: True
```

Both patterns respond identically to the toggle, because the toggle disables the *whole
rule*, which predates the PR. **The toggle isolates the rule, not the PR.** Attribution of
pattern 2 to this PR rests on `SOURCE` evidence — the diff adds exactly that branch — plus
the regression test the PR ships, not on the runtime toggle.

The PR description adds a second reason for caution:

> I found #19085 also fix issue by pushdown filter, I think the 2 PRs could coexist

Two merged PRs address the same issue. Any version-bracketed comparison (1.4.x vs 1.5.x)
would have been unable to tell them apart. That is precisely the misattribution the
rule-level toggle avoids.

## 4. The preserved invariant

An optimizer pass may change the plan freely. It may not change the answer. That invariant
is testable directly: run a battery of queries with the rule on and off and compare results.

[`artifacts/differential_unnest_rewriter.py`](artifacts/differential_unnest_rewriter.py) —
12 queries covering empty arrays, `NULL` arrays, `NULL` elements, `WITH ORDINALITY`, outer
joins, filters, aggregation, string element types, nested subqueries, and two unnests joined
together:

```console
$ ./venv/bin/python artifacts/differential_unnest_rewriter.py
duckdb 1.5.3

query                   result equal?   plan changed?   DELIM_JOIN on/off
------------------------------------------------------------------------------
q1_basic                SAME            changed         no/yes
q2_ordinality           SAME            identical       yes/yes
q3_empty_and_null       SAME            changed         no/yes
q4_left_join_style      SAME            identical       yes/yes
q5_where_filter         SAME            identical       yes/yes
q6_agg                  SAME            changed         no/yes
q7_two_unnests          SAME            changed         no/yes
q8_strings              SAME            changed         no/yes
q9_nested_subquery      SAME            identical       yes/yes
q10_correlated_agg      *** DIFFERENT ***changed         no/yes
q11_ordinality_filter   SAME            identical       yes/yes
q12_edge_ordinality     SAME            identical       yes/yes
------------------------------------------------------------------------------
queries: 12   invariant violations: 1
```

### Investigating q10 before reporting it

`q10` is `SELECT foo, list(value) FROM with_array CROSS JOIN unnest(arr) AS values(value)
GROUP BY foo ORDER BY foo`. A difference here would be a correctness regression in a shipped
release, so the check itself is suspect until shown otherwise.

```console
rule ON  [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
rule OFF [(1, [3.0, 2.0, 1.0]), (2, [6.0, 5.0, 4.0])]

--- is list() order even stable within one config? 5 repeats, rule ON ---
  run 0 [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
  run 1 [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
  run 2 [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
  run 3 [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
  run 4 [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]

--- deterministic reformulation: list(value ORDER BY value) ---
rule ON  [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
rule OFF [(1, [1.0, 2.0, 3.0]), (2, [4.0, 5.0, 6.0])]
```

The list is **reversed**, deterministic within each configuration, and identical once the
aggregate is given an explicit `ORDER BY`. `list()` without `ORDER BY` has no specified
element order — the difference is in unspecified behavior, not in the result.

**Verdict: not an invariant violation.** It is still a real consequence, and it belongs in
the report: queries that relied on `list()` reproducing array order — which the old plan
happened to reverse and the new plan happens to preserve — silently change on upgrade to
v1.5.0. Nothing warns about it.

## 5. The intended change, measured

```console
$ ./venv/bin/python - <<'PY'
# 300k rows x 4-element arrays = 1.2M output rows, threads=1, median of 5
Q = "SELECT count(*), sum(value) FROM big CROSS JOIN unnest(arr) AS values(value)"
PY
rule ON  (v1.5.3 default): median     17.0 ms   result=(1200000, 449998500000.0)   delim_join=False
rule OFF (base-equivalent): median    544.8 ms   result=(1200000, 449998500000.0)   delim_join=True
speedup: 32.0x     results identical: True
```

**32×** on the shape the PR targets, with both aggregates identical across 1.2M rows.

## 6. Where the rewrite does *not* fire

```console
pattern2 + WHERE on unnested value
   rule ON  -> delim_join present: True
   rule OFF -> delim_join present: True
pattern2 + WITH ORDINALITY (explicitly excluded)
   rule ON  -> delim_join present: True
   rule OFF -> delim_join present: True
```

`WITH ORDINALITY` is excluded deliberately — the `ordinality_idx.IsValid()` guard in the
diff, asserted by the PR's own test, which requires `DELIM_JOIN` to still be present there.

Adding a `WHERE` on the unnested value also prevents the rewrite, at v1.5.3, *after* both
this PR and #19085 shipped. Users who filter the unnested column — a common shape — do not
get the 32×. Reported as a coverage limitation, not a defect: nothing claims that shape is
covered.

---

## Report

### Intended observable change

For `CROSS JOIN unnest(<list column>)` without `WITH ORDINALITY`, the plan loses its
`LEFT_DELIM_JOIN` and becomes a flat `SEQ_SCAN → UNNEST → PROJECTION`. Measured at **32×**
faster on 1.2M output rows. Results are unchanged.

### Before/after behavior matrix

| Scenario | Base (rule off) | Head (v1.5.3) | Intended? | Evidence | Residual risk |
|---|---|---|---|---|---|
| `CROSS JOIN unnest(arr)` | `LEFT_DELIM_JOIN` + `HASH_JOIN` + `HASH_GROUP_BY` | `SEQ_SCAN → UNNEST → PROJECTION` | yes | `EXPLAIN`, both configs | — |
| same, 1.2M output rows | 544.8 ms | 17.0 ms | yes | median of 5, `threads=1` | — |
| results of 12 unnest queries | — | identical | yes (invariant) | `differential_unnest_rewriter.py` | element order, below |
| empty array `[]`, `NULL` array, `NULL` element | identical | identical | yes | q3, q12 | — |
| `WITH ORDINALITY` | `DELIM_JOIN` | `DELIM_JOIN` (unchanged) | yes — explicit guard | q2, q11, q12; PR test asserts it | correctness depends on the guard |
| `WHERE` on unnested value | `DELIM_JOIN` | `DELIM_JOIN` (unchanged) | not addressed | q5 | optimization does not reach a common shape |
| `list()` without `ORDER BY` over unnested rows | `[3.0, 2.0, 1.0]` | `[1.0, 2.0, 3.0]` | unspecified behavior | q10 + 5 repeats + `ORDER BY` reformulation | **silent change for queries that depended on it** |

### Preserved invariants

1. **Result multiset equality with the rule off** — 12/12 queries, once q10 is reduced to a
   deterministic form.
2. **`WITH ORDINALITY` keeps its delim join** — the ordinality column is derived from the
   delim index, so rewriting it would change results. Guarded and tested.
3. **Pattern 1 continues to be rewritten** — the pre-existing branch returns early,
   confirmed present at v1.5.3.
4. **Column bindings across the whole plan stay consistent** after `VisitOperator(*root)`.
   Verified only by the 12 queries' results, not structurally.

### Transitive impact and blast radius

- **Every query containing `unnest` as a table function** reaches the new branch. The guard
  is `ExpressionBinder::IsUnnestFunction(get.function.name)` — a **match on the function
  name string**. A user-defined or extension-provided table function named `unnest` would
  enter a rewrite built for the builtin. Not tested; no evidence either way.
- **`IsUnnestFunction` moved `protected` → `public`** in a header under `src/include/`.
  Widening visibility does not break source compatibility, but the header is part of what
  extensions compile against, so it is a contract surface change rather than an internal one.
- **`FindCandidates` now mutates the plan mid-traversal** via `replacer.VisitOperator(*root)`
  while the recursion holds `unique_ptr` references into the same tree. The 12 queries
  include nested and repeated unnests (q7, q9) and show no problem; that is evidence, not
  proof, for plan shapes not tried.
- **The new branch relies on two `D_ASSERT`s** for the shape of `proj.expressions` and of
  the column bindings it rewrites. Those
  compile out of release builds. If an assumption is violated in a shipped binary the
  outcome is not a crash but a silently wrong rewrite — which is why this analysis is at
  `audit` depth.

### Validation evidence

| Claim | Status | Command | Result |
|---|---|---|---|
| Base = `44b706b2`, head = `5c465baf`, 33 unrelated commits on `main` | `SOURCE` | `git merge-base`, `git rev-list --count` | GitHub's `baseRefOid` agrees with the merge base |
| Shipped in v1.5.0+ | `SOURCE` | `git tag --contains 875cf9d2` | v1.5.0 … v1.5.5 |
| Plan loses the delim join | `RUNTIME` | `EXPLAIN` with and without `disabled_optimizers='unnest_rewriter'` | 10 operators → 3 |
| 32× faster on the target shape | `RUNTIME` | median of 5, `threads=1`, 1.2M output rows, duckdb 1.5.3 | 544.8 ms → 17.0 ms |
| Results invariant across 12 queries | `RUNTIME` | `artifacts/differential_unnest_rewriter.py` | 11 identical, q10 explained below |
| q10 difference is unspecified `list()` order | `RUNTIME` | 5 repeats per config + `list(value ORDER BY value)` | Deterministic per plan; identical when ordered |
| Pattern 2 attributable to this PR | `SOURCE` | the diff adds exactly that branch + its regression test | **not** shown by the runtime toggle |
| Rule-off ≠ PR base | `RUNTIME` | pattern 1 responds to the toggle identically | Toggle isolates the rule, not the PR |
| Behavior at `44b706b2` itself | `UNKNOWN` | would need `make` at base and head | `cmake` unavailable here; not run |
| Name-collision risk for a table function named `unnest` | `UNKNOWN` | — | Would need an extension defining one |
| Concurrency / plan-cache interaction | `UNKNOWN` | — | Not exercised |

### Compatibility, operational, and rollback concerns

- **Rollback is a one-line runtime setting**, not a redeploy: `SET
  disabled_optimizers='unnest_rewriter'` disables the rewrite — at the cost of also
  disabling the pre-existing pattern-1 rewrite.
- **Silent result-shape change on upgrade** for `list()`/`array_agg()` without `ORDER BY`
  over unnested rows. Correct by the SQL semantics, invisible in tests that sort, and
  invisible in a diff review.
- **`test/optimizer/unnest_rewriter.test_slow` ends without a trailing newline** (`\ No
  newline at end of file`). Cosmetic.

### Residual risk and recommendation

At revision `5c465baf` (observed through v1.5.3, `source_id` `14eca11bd9`), the rewrite
produces identical results to the un-rewritten plan for all 12 tested shapes, is guarded
against the one case where it would be unsound (`WITH ORDINALITY`), and is 32× faster on the
shape it targets. Its release-build safety rests on `D_ASSERT`s that do not run in release,
and the mid-traversal plan mutation was validated behaviorally rather than structurally.

**Conditional recommendation: merge** — as it in fact was, and it has since shipped in six
releases. The two items worth carrying forward are the `list()` ordering change, which
deserves a release note, and the name-based `IsUnnestFunction` guard, which is untested
against a non-builtin function of that name.

### Smallest next verification steps

1. Build at `44b706b2` and `5c465baf` and re-run the 12-query differential, converting
   "rule off" into a true base comparison — the one thing this analysis could not do.
2. Run the shipped suite `test/optimizer/unnest_rewriter.test_slow` at head and confirm the
   ordinality assertions hold in a release build, where the `D_ASSERT`s are absent.
3. Fuzz plan shapes: nested unnests, unnest over `unnest`, unnest inside recursive CTEs —
   the shapes most likely to break a mid-traversal binding replacement.

---

## What the mode changed

A review of this PR reads as: small, well-tested optimizer improvement, adds a pattern,
guards the unsafe case, ships a regression test. Correct — and it misses all three of the
findings that matter.

Four constraints changed the output:

- **Resolve the base rather than guessing it.** The merge commit's first parent is 33
  commits ahead of the real base. Diffing against it would have pulled in unrelated changes.
- **State what the evidence attributes and what it does not.** The optimizer toggle is a
  better isolation than version bracketing, and it *still* cannot separate this PR from the
  rule it extends. Saying so is the difference between a measurement and a claim.
- **List preserved invariants, not just changes.** "Results must be identical" is the entire
  contract of an optimizer pass, and it is the thing a diff review cannot check. Testing it
  is what surfaced the `list()` ordering change.
- **Challenge a failing check before reporting it.** The one flagged violation was
  unspecified behavior, not a bug — but it was also a genuine user-visible change, so it
  belongs in the report under compatibility rather than under correctness. Both halves of
  that took evidence to establish.
