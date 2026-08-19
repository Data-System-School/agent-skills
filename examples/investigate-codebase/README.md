# `investigate-codebase` — end-to-end examples

Real runs of the skill, one folder per subject codebase, all four modes against each.
Every example states the revision its claims are anchored to, the environment it ran in,
and the checks that could not run.

| Subject | Runs | Why this codebase |
|---|---|---|
| [`duckdb/`](duckdb/) | 4 — `ORIENT`, `TRACE`, `IMPACT`, `VERIFY` | Large enough that orientation is a real problem, observable from a shell without building anything, with a public PR history |
| [`vllm/`](vllm/) | 4 — `ORIENT`, `TRACE`, `IMPACT`, `VERIFY` | The opposite constraint: a GPU-only system that **cannot be run** on the investigating machine at all |

## The runs

| Example | Subject | Mode | Depth | What the evidence changed |
|---|---|---|---|---|
| [01 — Orient in the DuckDB source](duckdb/01-orient-duckdb-source.md) | DuckDB | `ORIENT` | `working` | The in-repo architecture doc omits the component that actually owns query orchestration |
| [02 — Trace zone-map pruning](duckdb/02-trace-zonemap-pruning.md) | DuckDB | `TRACE` | `working` | Two pruning mechanisms at two layers; the first negative control silently no-opped |
| [03 — Impact of PR #19235](duckdb/03-impact-pr-19235.md) | DuckDB | `IMPACT` | `audit` | 32× faster, results invariant — except one unspecified ordering users do depend on |
| [04 — Verify a generated report query](duckdb/04-verify-generated-sql.md) | DuckDB | `VERIFY` | `audit` | 6/6 tests green at 100% coverage, three real bugs, revenue inflated N× |
| [01 — Where to start reading vLLM](vllm/01-orient-vllm-source.md) | vLLM | `ORIENT` | `working` | The architecture doc's file pointers land on 14 lines of aliases; 31% of the package is model transcriptions |
| [02 — Trace the prefix-cache ceiling](vllm/02-trace-prefix-cache-ceiling.md) | vLLM | `TRACE` | `working` | A fully cached prompt still reruns a whole block; 49 test "failures" came from the harness |
| [03 — Impact of PR #36708](vllm/03-impact-pr-36708.md) | vLLM | `IMPACT` | `audit` | Certain cost (every multimodal cache invalidated), zero collisions actually removed |
| [04 — Verify a generated logits processor](vllm/04-verify-generated-logitsproc.md) | vLLM | `VERIFY` | `audit` | 8/8 tests green at 100% coverage, 2/6 contract checks pass, a cross-request leak |

Each subject folder has its own README with the exact environment and reproduction steps.

## Reading order

- **New to the skill**: [DuckDB 02](duckdb/02-trace-zonemap-pruning.md) is the shortest
  complete loop — a hypothesis, a manipulation, and a control that failed silently.
- **Interested in what happens when you cannot run the system**: the whole
  [vLLM folder](vllm/), where nothing was ever executed on a GPU.
- **Evaluating AI-written code**: [DuckDB 04](duckdb/04-verify-generated-sql.md) for a
  generated query with no contract, [vLLM 04](vllm/04-verify-generated-logitsproc.md) for
  generated code against a written one.
- **Deciding whether to take a change**: [DuckDB 03](duckdb/03-impact-pr-19235.md) and
  [vLLM 03](vllm/03-impact-pr-36708.md) — one where the change is worth it, one where the
  cost is certain and the benefit is not.
