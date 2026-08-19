# Examples

Real end-to-end runs of the skills in this repository, against a real codebase.

Everything here was produced by actually running the skill and recording what happened:
the commands are the commands that ran, the outputs are the outputs they printed, and the
checks that failed or silently no-opped are reported rather than cleaned up. Where a check
could not run, the example says so instead of substituting a weaker claim.

The subject is **[DuckDB](https://github.com/duckdb/duckdb)** — an in-process analytical
SQL database. It suits all four investigation modes: it is large enough that orientation
is a real problem, its behavior is observable from a shell without building anything, and
it has a public PR history to analyze.

## Skills

### [`investigate-codebase`](investigate-codebase/)

Four runs, one per mode, all against DuckDB:

| # | Mode | Question | What the evidence changed |
|---|---|---|---|
| [01](investigate-codebase/01-orient-duckdb-source.md) | `ORIENT` | How is the DuckDB source organized, and where would I start reading? | The in-repo architecture doc omits the component that actually owns query orchestration |
| [02](investigate-codebase/02-trace-zonemap-pruning.md) | `TRACE` | Why is a filter on one column 27× faster than the same filter on another? | Two different pruning mechanisms at two layers; the first negative control silently no-opped |
| [03](investigate-codebase/03-impact-pr-19235.md) | `IMPACT` | What does PR #19235 actually change, and what must stay the same? | 32× faster on the target shape, results invariant — except for one unspecified ordering that users do depend on |
| [04](investigate-codebase/04-verify-generated-sql.md) | `VERIFY` | Is this generated reporting query correct? | 6/6 tests green at 100% coverage, three real bugs, revenue inflated N× |

Reproduction steps are in each example and in
[`investigate-codebase/README.md`](investigate-codebase/README.md).
