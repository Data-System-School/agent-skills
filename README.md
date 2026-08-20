# agent-skills

Portable agent skills for coding agents.

Each skill is a self-contained directory of Markdown instructions that an agent loads
on demand. Nothing here is executable and nothing is host-specific: the same procedure
runs under Claude Code, OpenAI Codex, and any other host that reads the skill format.

## Skills

| Skill | What it does | Examples |
|---|---|---|
| [`investigate-codebase`](investigate-codebase/) | Builds an evidence-backed working model of an existing codebase. Orient in an unfamiliar repository, trace a runtime flow, analyze change impact, or verify generated code. Read-only by default. | [8 end-to-end runs](examples/investigate-codebase/) |
| [`read-a-paper`](read-a-paper/) | Runs the three-pass method as a ladder with a stop-or-continue decision at every rung. You commit your own five Cs before it opens the paper; it then reads independently and discusses only where you diverge. | — |

### investigate-codebase

Most "explain this codebase" prompts produce a confident directory tour that nobody can
check. This skill optimizes for the opposite: the smallest model that answers the actual
question, with every material claim tied to evidence or explicitly marked unknown.

Pick one **mode**:

| Mode | Use it for |
|---|---|
| `ORIENT` | Mapping a large or unfamiliar repository into 5–7 components and a 5–12 file reading route |
| `TRACE` | Explaining one concrete runtime, control, or data flow as a falsifiable causal path |
| `IMPACT` | Analyzing a PR, branch, commit, or diff for semantic behavior delta and blast radius |
| `VERIFY` | Assessing generated or changed code against independent correctness oracles |

Then a **depth**: `scan` (landmarks, uncertainty kept explicit), `working` (the default —
evidence-backed explanation plus focused checks), or `audit` (broadened risk coverage).

Every claim lands in an evidence ledger labeled `SOURCE`, `RUNTIME`, `INFERRED`,
`UNKNOWN`, or `CONTRADICTED`, anchored to a revision plus path and symbol. The skill is
deliberately strict about a few things:

- **Read-only unless you asked otherwise.** No edits, installs, branch switches, or
  state resets. Dirty worktree changes are preserved and kept out of comparisons.
- **Static reachability is not a runtime trace.** A source-derived diagram is labeled as
  a static model; `RUNTIME` requires an executed command and its outcome.
- **Green tests are not proof.** Coverage measures execution, not assertion quality, and
  AI-written tests for AI-written code are treated as correlated evidence.
- **Missing capability becomes `UNKNOWN`, not a weaker claim.** Skipped, flaky,
  timed-out, and credential-blocked checks are reported rather than quietly dropped.
- **No uncalibrated correctness percentage.** Conclusions are conditional: at revision X
  in environment Y, evidence supports Z for scenarios A and B; C remains unverified.

### read-a-paper

Asking an AI to explain a paper produces a fluent summary that never lets you stall, so
you finish feeling informed with no idea what you failed to understand. This skill
optimizes for the opposite: your own reading, committed before the paper is opened, then
checked against a second, independent reading rather than replaced by one.

The ladder is three rungs, each ending in its own decision:

| Pass | Budget | Exit decision |
|---|---|---|
| 1 | 5–10 min | read on / stop here — stopping is a result, not a failure |
| 2 | ≤ 1 hr | set aside / come back later / go to pass 3 |
| 3 | hours | done |

A sidecar notes file tracks position outside the conversation, through three gate
states: `sealed` (the paper is not yet opened), `committed` (the reader's own five Cs —
category, context, correctness, contributions, clarity — are on record, including any
the reader could not answer), and `contrasted` (the skill has read the paper and logged
where its own five Cs diverge from the reader's). A side door, entered before pass 1,
builds a reading list around a field instead of one paper.

The skill is deliberately strict about a few things:

- **The paper is not opened before you commit.** The gate is on reading, not on
  speaking, because a leak rarely takes the form of a stated answer — the rule
  attaches to an auditable action instead.
- **Not answering is a valid commit; a blank is not.** `UNANSWERED — ran out of time`
  is a finding. Silence records nothing.
- **Agreement gets one line.** Elaborating where you and the skill already agree is a
  distillation by the back door.
- **The survey may be delegated; the reading may not.** Every paper a survey produces
  enters the ladder sealed.
- **Stopping after pass 1 is a result.** Most papers deserve exactly that.
- **It will not run the experiment for you, and says so.** A paper is a very good
  reason to run one; it is not one.

## Examples

[`examples/`](examples/) holds real end-to-end runs against real codebases —
[DuckDB](https://github.com/duckdb/duckdb) and [vLLM](https://github.com/vllm-project/vllm).
The commands are the commands that ran and the outputs are the outputs they printed,
including the checks that failed or silently no-opped.

## Install

Clone once:

```bash
git clone https://github.com/Data-System-School/agent-skills.git
```

**Claude Code**, available in every project:

```bash
cp -r agent-skills/investigate-codebase ~/.claude/skills/
```

**Claude Code**, scoped to one repository and checked in with it:

```bash
mkdir -p .claude/skills
cp -r /path/to/agent-skills/investigate-codebase .claude/skills/
```

**OpenAI Codex**:

```bash
cp -r agent-skills/investigate-codebase ~/.codex/skills/
```

Symlink instead of copy if you want `git pull` to update the installed skill:

```bash
ln -s "$PWD/agent-skills/investigate-codebase" ~/.claude/skills/investigate-codebase
```

## Use

Hosts match a request against each skill's `description` and load the skill when it
fits, so usually you just describe the task:

> Trace how an authenticated upload request reaches S3 in this service.

> Analyze PR #412 for behavioral impact and blast radius.

You can also name it and steer mode and depth directly:

> Use investigate-codebase in IMPACT + VERIFY mode at audit depth on this branch.

## Skill layout

```
investigate-codebase/
├── SKILL.md                        # frontmatter + the operating contract and loop
├── references/                     # mode guides, read only for the selected mode
│   ├── orient-large-codebase.md
│   ├── trace-runtime-flow.md
│   ├── analyze-pr-impact.md
│   └── verify-generated-code.md
├── agents/
│   └── openai.yaml                 # display name, icon, and policy for OpenAI hosts
└── assets/
    └── icon.svg
```

Two conventions worth keeping if you add a skill here:

- `SKILL.md` frontmatter needs `name` and `description`. The description is the trigger,
  so it should state when to use the skill *and* when not to — `investigate-codebase`
  includes an explicit "do not trigger only because a coding task touches an existing
  repository."
- Keep `SKILL.md` as the router and push mode-specific detail into `references/`. The
  agent then loads one guide instead of all four, which keeps the resident instructions
  small.
- Keep examples in `examples/<skill-name>/`, outside the skill directory. Installing a
  skill copies its directory, so anything inside it becomes weight the agent carries on
  every load; examples are for humans evaluating the skill, not for the agent running it.

## License

[MIT](LICENSE).
