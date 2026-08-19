# `investigate-codebase` — end-to-end examples

Real runs of the skill, one folder per subject codebase. Every example states the revision
its claims are anchored to, the environment it ran in, and the checks that could not run.

| Subject | Runs | Why this codebase |
|---|---|---|
| [`duckdb/`](duckdb/) | 4 — one per mode (`ORIENT`, `TRACE`, `IMPACT`, `VERIFY`) | Large enough that orientation is a real problem, observable from a shell without building anything, with a public PR history |
| [`vllm/`](vllm/) | 1 — `TRACE` | The opposite constraint: a GPU-only system that **cannot be run** on the investigating machine at all |

## The runs

| Example | Subject | Mode | Depth | What the evidence changed |
|---|---|---|---|---|
| [01 — Orient in the DuckDB source](duckdb/01-orient-duckdb-source.md) | DuckDB | `ORIENT` | `working` | The in-repo architecture doc omits the component that actually owns query orchestration |
| [02 — Trace zone-map pruning](duckdb/02-trace-zonemap-pruning.md) | DuckDB | `TRACE` | `working` | Two pruning mechanisms at two layers; the first negative control silently no-opped |
| [03 — Impact of PR #19235](duckdb/03-impact-pr-19235.md) | DuckDB | `IMPACT` | `audit` | 32× faster, results invariant — except one unspecified ordering users do depend on |
| [04 — Verify a generated report query](duckdb/04-verify-generated-sql.md) | DuckDB | `VERIFY` | `audit` | 6/6 tests green at 100% coverage, three real bugs, revenue inflated N× |
| [01 — Trace the prefix-cache ceiling](vllm/01-trace-prefix-cache-ceiling.md) | vLLM | `TRACE` | `working` | A fully cached prompt still reruns a whole block; 49 test "failures" came from the harness, not the code |

Each subject folder has its own README with the exact environment and reproduction steps.

## Reading order

- **New to the skill**: [DuckDB 02](duckdb/02-trace-zonemap-pruning.md) is the shortest
  complete loop — a hypothesis, a manipulation, and a control that failed silently.
- **Interested in what happens when you cannot run the system**:
  [vLLM 01](vllm/01-trace-prefix-cache-ceiling.md) is the whole example.
- **Evaluating AI-written code**: [DuckDB 04](duckdb/04-verify-generated-sql.md).
