# Examples

Real end-to-end runs of the skills in this repository, against real codebases.

Everything here was produced by actually running the skill and recording what happened:
the commands are the commands that ran, the outputs are the outputs they printed, and the
checks that failed or silently no-opped are reported rather than cleaned up. Where a check
could not run, the example says so instead of substituting a weaker claim.

Each subject lives in its own folder, because the subject is part of what the example
demonstrates:

- **[DuckDB](https://github.com/duckdb/duckdb)** — an in-process analytical SQL database.
  It suits all four investigation modes: large enough that orientation is a real problem,
  observable from a shell without building anything, with a public PR history to analyze.
- **[vLLM](https://github.com/vllm-project/vllm)** — a GPU LLM inference server, chosen for
  the opposite constraint. It ships no wheel for the investigating machine and there is no
  GPU on it, so the run has to find out how much evidence is still obtainable when the
  system under investigation cannot be started.

## Skills

### [`investigate-codebase`](investigate-codebase/)

| # | Subject | Mode | Question | What the evidence changed |
|---|---|---|---|---|
| [01](investigate-codebase/duckdb/01-orient-duckdb-source.md) | DuckDB | `ORIENT` | How is the DuckDB source organized, and where would I start reading? | The in-repo architecture doc omits the component that actually owns query orchestration |
| [02](investigate-codebase/duckdb/02-trace-zonemap-pruning.md) | DuckDB | `TRACE` | Why is a filter on one column 27× faster than the same filter on another? | Two different pruning mechanisms at two layers; the first negative control silently no-opped |
| [03](investigate-codebase/duckdb/03-impact-pr-19235.md) | DuckDB | `IMPACT` | What does PR #19235 actually change, and what must stay the same? | 32× faster on the target shape, results invariant — except for one unspecified ordering that users do depend on |
| [04](investigate-codebase/duckdb/04-verify-generated-sql.md) | DuckDB | `VERIFY` | Is this generated reporting query correct? | 6/6 tests green at 100% coverage, three real bugs, revenue inflated N× |
| [01](investigate-codebase/vllm/01-trace-prefix-cache-ceiling.md) | vLLM | `TRACE` | Why does a re-sent identical prompt report a 97% prefix-cache hit rate instead of 100%? | The missing block is a deliberate reservation, not a rounding loss — and 49 test "failures" came from the harness, not from vLLM |

Reproduction steps are in each example and in the per-subject READMEs:
[`duckdb/`](investigate-codebase/duckdb/README.md), [`vllm/`](investigate-codebase/vllm/README.md).
