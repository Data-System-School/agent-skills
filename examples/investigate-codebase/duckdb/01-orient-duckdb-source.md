# ORIENT — getting oriented in the DuckDB source

> **Prompt**
>
> I need to work on DuckDB's query engine and I've never opened the repo. Give me a
> working model of how the source is organized and a reading route that actually gets
> me to the code that runs a query.

---

## Selection

| | |
|---|---|
| **Mode** | `ORIENT` |
| **Depth** | `working` |
| **Scope** | `src/` of `duckdb/duckdb`. `third_party/`, `tools/`, `extension/`, and `benchmark/` in the parking lot |
| **Revision** | `14eca11bd9d4a0de2ea0f078be588a9c1c5b279c` (tag `v1.5.3`) |
| **Environment** | `duckdb` CLI v1.5.3, `source_id` `14eca11bd9` — same commit as the checkout |

`ORIENT` rather than `TRACE`, because the request is for a navigation model, not for one
behavior. `working` rather than `scan`, because the reading route has to be verified
against actual wiring, not guessed from directory names.

---

## 1. Anchor the target

```console
$ git -C duckdb rev-parse HEAD
14eca11bd9d4a0de2ea0f078be588a9c1c5b279c

$ git -C duckdb describe --tags
v1.5.3

$ git -C duckdb status --porcelain
                          # clean — no local modifications to separate out

$ duckdb -c "PRAGMA version;"
┌─────────────────┬────────────┬───────────┐
│ library_version │ source_id  │ codename  │
├─────────────────┼────────────┼───────────┤
│ v1.5.3          │ 14eca11bd9 │ Variegata │
└─────────────────┴────────────┴───────────┘
```

The installed binary's `source_id` matches the checkout, so runtime observations below can
be attributed to the source being read.

Repository instructions: `CONTRIBUTING.md` at the root. No `AGENTS.md`, `CLAUDE.md`, or
per-directory agent instruction files.

```console
$ find duckdb -maxdepth 3 -iname 'AGENTS.md' -o -maxdepth 3 -iname 'CLAUDE.md' -o -maxdepth 3 -iname 'CONTRIBUTING.md' | grep -v third_party
duckdb/CONTRIBUTING.md
```

Scale, to decide whether one pass is even possible:

```console
$ find src -name '*.cpp' -o -name '*.hpp' | wc -l
2710
$ find src -name '*.cpp' -o -name '*.hpp' | xargs wc -l | tail -1
  444950 total
$ find third_party -name '*.cpp' -o -name '*.hpp' -o -name '*.c' -o -name '*.h' | xargs wc -l | tail -1
  420191 total
$ git rev-list --count HEAD
70547
```

445k lines of first-party source and a near-equal mass of vendored code. This is over the
"split into subsystems" threshold, so the first pass covers the query path only; storage
internals, the extension system, and the client bindings are named as boundaries and
deferred.

## 2. Frame falsifiable questions

The request becomes three questions that a wrong map would answer wrong:

1. Where does execution actually enter the system for a SQL string?
2. Which single component sequences parse → plan → optimize → execute, and is it one of
   the directories the in-repo documentation names?
3. Can each stage of that sequence be observed at runtime, or is the sequence only an
   inference from reading source?

Question 3 is what separates a map that can be checked from a directory tour.

## 3. Build the minimum map

`src/` has fourteen subdirectories. File counts say where the mass is, not where the
control is, so this is used only to rank the reading order:

```console
$ for d in src/*/; do n=$(find "$d" -name '*.cpp' -o -name '*.hpp' | wc -l | tr -d ' '); echo "$n	$d"; done | sort -rn
1333	src/include/
201	src/execution/
191	src/parser/
189	src/planner/
188	src/function/
175	src/common/
127	src/storage/
112	src/main/
111	src/optimizer/
38	src/catalog/
18	src/parallel/
12	src/transaction/
10	src/verification/
5	src/logging/
```

There is an architecture document in the tree — `src/README.md` — which describes seven
components: Parser, Planner, Optimizer, Execution, Catalog, Storage, Transaction. Per the
operating contract that is *intent evidence*, to be reconciled with the wiring rather than
copied. Reconciling it is what produced the one contradiction in this report.

### Component map

Seven components, named by runtime responsibility:

| Component | Directory | Owns | Contract it exposes |
|---|---|---|---|
| **Session & orchestration** | `src/main/` | `ClientContext` — the per-connection object that sequences every stage, owns the transaction context, profiler, and result lifetime | `duckdb.h` (6288 lines, C API); `Connection`/`ClientContext` C++ API |
| **Parser** | `src/parser/` | SQL text → `SQLStatement` / `ParsedExpression` / `TableRef` trees | `Parser::ParseQuery`; the parse tree types |
| **Binder & planner** | `src/planner/` | Name resolution against the catalog, type binding, `LogicalOperator` tree | `Planner::CreatePlan`; `LogicalOperator` |
| **Optimizer** | `src/optimizer/` | 34 rewrite passes over the logical plan | `Optimizer::Optimize`; contract is *logical equivalence* — see below |
| **Execution** | `src/execution/` | `LogicalOperator` → `PhysicalOperator`; push-based operator implementations | `PhysicalPlanGenerator::Plan`; `PhysicalOperator` |
| **Scheduling** | `src/parallel/` | `Executor`, pipelines, events, `TaskScheduler` — the machinery that actually runs the physical plan on threads | `Executor::Initialize`; `Pipeline`, `TaskScheduler` |
| **Storage & transactions** | `src/storage/`, `src/transaction/`, `src/catalog/` | Row groups, column segments, statistics, WAL, MVCC, catalog entries | `TableScan` bind/scan functions; `DuckTransaction` |

`src/common/`, `src/function/`, `src/logging/`, and `src/verification/` are cross-cutting
and are not first-pass components: `common` is utilities and types, `function` is the
built-in function catalog, `verification` is the test-only plan re-verification harness.

### Representative vertical slice

One slice, chosen because it crosses every boundary above: **a `SELECT` string becomes a
result set.**

```
duckdb -c "SELECT ..."                       tools/shell/
  └─ Connection::Query                       src/main/connection.cpp
      └─ ClientContext::CreatePreparedStatementInternal   src/main/client_context.cpp:387
          ├─ Planner::CreatePlan                          :405   → LogicalOperator tree
          ├─ Optimizer::Optimize                          :435   → rewritten LogicalOperator tree
          └─ PhysicalPlanGenerator::Plan                  :447   → PhysicalOperator tree
      └─ ClientContext::PendingPreparedStatementInternal
          └─ Executor::Initialize                         :596
              └─ Executor::InitializeInternal    src/parallel/executor.cpp:388
                  └─ TaskScheduler::CreateProducer                :396
```

The orchestration is one function, and it is short enough to read in full:

```console
$ sed -n '394,451p' src/main/client_context.cpp
	auto &profiler = QueryProfiler::Get(*this);
	profiler.StartQuery(query, IsExplainAnalyze(statement.get()), true);
	profiler.StartPhase(MetricType::PLANNER);
	Planner logical_planner(*this);
	...
	logical_planner.CreatePlan(std::move(statement));
	...
	if (config.enable_optimizer && logical_plan->RequireOptimizer()) {
		profiler.StartPhase(MetricType::ALL_OPTIMIZERS);
		Optimizer optimizer(*logical_planner.binder, *this);
		logical_plan = optimizer.Optimize(std::move(logical_plan));
		...
	}

	// Convert the logical query plan into a physical query plan.
	profiler.StartPhase(MetricType::PHYSICAL_PLANNER);
	PhysicalPlanGenerator physical_planner(*this);
	result->physical_plan = physical_planner.Plan(std::move(logical_plan));
	profiler.EndPhase();
```

## 4. Confirm the slice at runtime

So far the slice is `SOURCE` only — read from code, therefore an inference about what
executes. The `profiler.StartPhase(MetricType::...)` calls make it checkable: if those
phases are real, the profiler must emit them by those names.

```console
$ duckdb -c "
PRAGMA enable_profiling='json';
PRAGMA profiling_output='/tmp/prof.json';
PRAGMA custom_profiling_settings='{\"PLANNER\":\"true\",\"ALL_OPTIMIZERS\":\"true\",\"PHYSICAL_PLANNER\":\"true\"}';
SELECT count(*) FROM range(1000000) t(i) WHERE i % 7 = 0;
"
┌──────────────┐
│ count_star() │
├──────────────┤
│       142858 │
└──────────────┘

$ python3 -c "import json; d=json.load(open('/tmp/prof.json')); print({k:v for k,v in d.items() if k!='children'})"
{'planner': 0.000835958, 'all_optimizers': 0.000601249, 'physical_planner': 0.000284874,
 'optimizer_filter_pushdown': 0.000156167, 'optimizer_join_order': 0.000160666,
 'optimizer_statistics_propagation': 0.000201458, 'optimizer_expression_rewriter': 3.025e-05,
 'optimizer_unnest_rewriter': 9.59e-07, 'optimizer_deliminator': 4.58e-07, ...}
```

The three phase names appear, in the order the source calls them, with the individual
optimizer passes nested under `all_optimizers`. The slice is now `RUNTIME`, and the
optimizer's internal structure — one timed pass per rule — is visible without reading
`src/optimizer/optimizer.cpp` at all.

This is the payoff of matching the binary to the checkout: the phase names are a bridge
between the source being read and the process being run.

## 5. Challenge the model

The prediction that could falsify the map: *if `ClientContext` is really the orchestrator,
the in-repo architecture document should say so.*

It does not.

```console
$ grep -oE '^# .*' src/README.md
# Parser
# Planner
# Optimizer
# Execution
# Catalog
# Storage
# Transaction
```

`src/README.md` documents seven components and **`src/main/` is not among them**, nor is
`src/parallel/`. The document describes the pipeline as a sequence of transformations —
which is accurate as far as it goes — but the component that owns the sequencing, the
transaction context, the profiler, and the result lifetime is undocumented, and so is the
component that actually runs the physical plan on threads.

The document also states that "the execution layer ... converts [the logical plan] into a
physical query plan" (`src/README.md`, Execution section). At this revision the conversion
is invoked from `src/main/client_context.cpp:447`, and `Executor` — the thing that runs the
plan — lives in `src/parallel/`, not `src/execution/`.

This is recorded as a contradiction rather than resolved. It is also the single most useful
output of this pass: a reader who trusted the document would look for the query lifecycle
in `src/execution/` and not find it.

---

## Report

### Direct answer

DuckDB's query path is a five-stage pipeline sequenced by a single function,
`ClientContext::CreatePreparedStatementInternal` in `src/main/client_context.cpp`. Read that
function first; the rest of `src/` is reachable from it. The in-repo architecture document
(`src/README.md`) is a good description of the *stages* but omits the component that owns
the *sequencing*, so do not use it as a navigation map.

### System purpose and boundary

DuckDB is an in-process analytical SQL engine: it is linked into a host process rather than
run as a server, so its outermost boundary is a library API (`src/include/duckdb.h`, 6288
lines of C API, plus the C++ `Connection`/`ClientContext` surface) rather than a network
protocol. Everything in `src/` sits behind that boundary. Durable side effects are confined
to `src/storage/` (database files, WAL) and to file-system access performed by table
functions; concurrency is confined to `src/parallel/`.

### Contracts and invariants

- **Optimizer**: every pass in `src/optimizer/` must preserve logical equivalence. The
  plan may change freely; the result set may not. This is the invariant that
  [example 03](03-impact-pr-19235.md) tests against a real optimizer change.
- **Physical plan**: push-based. Operators receive `DataChunk`s; they do not pull.
- **`ClientContext` is not thread-safe by itself** — `CreatePreparedStatementInternal` takes
  a `ClientContextLock &` as its first parameter, which is how the locking discipline is
  enforced at compile time rather than by convention.
- **Profiler phases are part of the observable surface**, not just diagnostics: they are
  what makes the pipeline checkable from outside.

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| Query pipeline is Planner → Optimizer → PhysicalPlanGenerator, sequenced in one function | `SOURCE` | `14eca11bd9` `src/main/client_context.cpp:387-451`, `ClientContext::CreatePreparedStatementInternal` | Read in full |
| Those three stages execute in that order | `RUNTIME` | `PRAGMA enable_profiling='json'` + `custom_profiling_settings` on the v1.5.3 CLI | Emits `planner`, `all_optimizers`, `physical_planner` |
| Optimizer is 34 separate passes | `SOURCE` + `RUNTIME` | `ls src/optimizer/*.cpp` → 34; profiler emits one `optimizer_*` metric per pass | Both agree |
| Physical plan is handed to `Executor`, which is in `src/parallel/` | `SOURCE` | `src/main/client_context.cpp:596` → `src/parallel/executor.cpp:377-396` | `InitializeInternal` obtains a `TaskScheduler` producer |
| `src/README.md` omits `src/main/` and `src/parallel/` | `CONTRADICTED` (doc vs. wiring) | `src/README.md` headings vs. call sites above | Doc describes stages, not ownership |
| Test topology is 4759 sqllogictest files + 143 C++ test files | `SOURCE` | `find test -name '*.test' -o -name '*.test_slow' \| wc -l`; `find test -name '*.cpp' \| wc -l` | Behavior is specified in SQL, not C++ |
| `ClientContext` locking is compile-time enforced | `INFERRED` | `ClientContextLock &lock` first parameter on the internal entry points | Not verified against a concurrent repro |
| Storage-layer state ownership | `UNKNOWN` | — | Out of first-pass scope; see [example 02](02-trace-zonemap-pruning.md) |

### Reading route

Twelve files, in causal order. One reason each.

| # | File | Why this file |
|---|---|---|
| 1 | `src/README.md` | The intended model — read it first *so you can notice what it leaves out* |
| 2 | `src/main/client_context.cpp` | The orchestrator; `CreatePreparedStatementInternal` at :387 is the spine of everything else |
| 3 | `src/include/duckdb/main/client_context.hpp` | What a session owns: transaction context, profiler, config, result lifetime |
| 4 | `src/main/connection.cpp` | The boundary above `ClientContext`; how `Query()` and `Prepare()` enter |
| 5 | `src/parser/parser.cpp` | SQL text → parse tree; also where the vendored Postgres grammar is wrapped |
| 6 | `src/planner/planner.cpp` | Parse tree → `LogicalOperator`; where the catalog is consulted |
| 7 | `src/planner/binder.cpp` | Name and type resolution — the largest source of "why does my query not bind" |
| 8 | `src/optimizer/optimizer.cpp` | The pass list; maps 1:1 onto the `optimizer_*` profiler metrics |
| 9 | `src/execution/physical_plan_generator.cpp` | `LogicalOperator` → `PhysicalOperator`, the logical/physical boundary |
| 10 | `src/parallel/executor.cpp` | Physical plan → pipelines → scheduled tasks; the missing half of "Execution" |
| 11 | `src/parallel/pipeline.cpp` | What a pipeline is, and where push-based execution actually pushes |
| 12 | `src/storage/table/row_group.cpp` | The bottom of the read path, and the subject of [example 02](02-trace-zonemap-pruning.md) |

Supporting, when a specific question demands it: `src/include/duckdb.h` (C API contract),
`src/catalog/catalog.cpp` (symbol resolution), `src/transaction/duck_transaction.cpp` (MVCC).

Parking lot: `third_party/` (420k lines, vendored — including the Postgres parser),
`tools/` (shell, Swift, Julia bindings), `extension/` (in-tree extensions: parquet, json,
icu, tpch, tpcds), `benchmark/`.

### Contradictions, risks, unknowns

- **Contradiction.** `src/README.md` omits `src/main/` and `src/parallel/`, the components
  that own orchestration and execution scheduling respectively. Anyone navigating from the
  document alone will look in the wrong directory for the query lifecycle.
- **Unknown.** Whether `src/execution/` or `src/parallel/` owns operator state at runtime.
  The static split suggests `execution` defines operators and `parallel` runs them, but
  that edge was not resolved at this depth.
- **Unknown.** Extension loading. `extension/` contains five in-tree extensions and
  `src/main/extension*.cpp` handles installation, but whether an extension can insert an
  optimizer pass — and therefore change the pipeline this map describes — was not checked.
  The profiler emitting an `optimizer_extension` metric suggests it can.
- **Assumption.** That `v1.5.3` is representative. Directory-level structure is stable
  across recent DuckDB releases, but no cross-version check was run.

### Smallest next verification steps

1. `grep -n "optimizer_extension" src/optimizer/optimizer.cpp` — resolve whether extensions
   can add optimizer passes, which is the one edge that could invalidate the component map.
2. Set a breakpoint or add a log at `src/parallel/pipeline_executor.cpp` and run one query
   to convert the `execution`/`parallel` ownership split from `INFERRED` to `RUNTIME`.
3. Pick one sqllogictest under `test/optimizer/` and run it, to learn the test harness
   before it is needed under time pressure.

### Prediction questions

1. `ClientContext::CreatePreparedStatementInternal` guards the optimizer with
   `if (config.enable_optimizer && logical_plan->RequireOptimizer())`. Which profiler
   metrics disappear when a plan returns `false` from `RequireOptimizer()`, and which
   remain?
2. A query is `EXPLAIN`ed but never executed. Which of the twelve files above are touched,
   and which are not?
3. `src/verification/` is compiled into the shipped binary but named in neither the
   architecture doc nor this map. Predict what it does from its position in the pipeline,
   then check against `src/main/client_verify.cpp`.

---

## What the mode changed

A confident directory tour of this repo writes itself: fourteen directories, each with an
obvious name, and an architecture document in the tree that appears to confirm them. That
tour would have sent a new contributor to `src/execution/` to find the query lifecycle.

Three constraints changed the output:

- **Reconcile documentation with wiring, and record contradictions.** The doc is not wrong,
  it is incomplete in a way that matters for navigation — and that only surfaces if you go
  looking for the orchestrator instead of accepting the stage list.
- **Runtime evidence must come from an executed command.** The pipeline order could have
  been asserted from reading source and would have been correct. Running the profiler made
  it checkable by the reader, and cost one command.
- **Split when the model gets too big.** 445k lines does not fit in one map. Naming storage
  internals, extensions, and bindings as boundaries and deferring them is what kept the
  component map at seven entries instead of fourteen.
