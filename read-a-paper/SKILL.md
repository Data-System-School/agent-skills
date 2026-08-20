---
name: read-a-paper
description: >-
  Read a research paper by the three-pass method, one pass at a time, with an
  explicit stop-or-continue decision at the end of each. Use when the user wants to
  read, triage, or decide whether to read an academic paper; wants their own five Cs
  (category, context, correctness, contributions, clarity) tested against a second,
  independent reading; or is surveying an unfamiliar field and needs entry-point
  papers, key authors, and venues. The reader commits their own answers first and the
  paper is not opened before they do. Do not use to summarize a paper on the reader's
  behalf, to produce a distillation, or to answer a question about a paper the reader
  does not intend to read.
---

# Read a Paper

## Objective

Depth is a decision, made up to three times — once at the end of each pass. Most
papers deserve pass 1 and nothing more, and that is the point of having passes, not
laziness.

The three passes, the five Cs and the literature survey are S. Keshav's; the commit gate
built around them is not. Attribution in full: [five-cs.md](references/five-cs.md).

## Find the position

Look for the sidecar notes file next to the paper. No file → the paper is new; start at
entry triage below. A file → read its frontmatter `stage` and `pass`, and resume at that
rung, in that stage. The notes file is the source of truth for position — not this
conversation, and not anything said earlier in it.

## Entry triage

Before pass 1, establish whether trustworthy secondary material exists for this paper — a
survey, a distillation, the authors' own talk. **Establishing *whether* one exists is the
whole of triage.** Judge it on provenance — who wrote it, where it was published, whether
it is the authors' own — and never on its content: opening it to decide whether it is any
good is opening it. Do not open it, skim it, quote it, or answer out of it: while `sealed`
the gate covers the paper and every secondary account of it alike, because a distillation
carries all five Cs and handing one over ends the gate exactly as reading the paper would.

Record the finding in the notes file's `secondary` field — `none`, or `exists-unread` when
one was found. If the reader says their own answers came out of that material rather than
the paper, set `secondary: used`; that value changes how the divergence report must be
read, and the report has to say so.

The table below is advice **to the reader** about their own reading, and it applies to the
reading they do after they have committed. It grants this skill nothing.

| Secondary material… | …stands in for |
|---|---|
| pass 1 | **Yes**, and better than your own ten-minute skim |
| pass 2 | **Mostly** — but open the original for the *figures*; summaries have none, and pass 2 is where rushed work shows itself |
| pass 3 | **No.** Reading someone else's re-creation is a different act with a different result |
| running the claim yourself | **Never** |

The risk is the reason the table is not just permission, even for the reader: these
summaries are easy to read, and easy is the problem. Struggling through an original tells
you where your model is thin; a fluent summary tells you nothing, because it never lets you
stall. Pair them — read the summary, close it, and explain the mechanism cold.

## The ladder

Three rungs, rising budget and rising stakes. Each row links to the guide for that
pass; load **exactly one pass guide** per invocation.
[five-cs.md](references/five-cs.md) is not a fourth guide but a shared dependency — load it
alongside whichever guide points at it.

| Pass | Budget | Exit decision | Guide |
|---|---|---|---|
| 1 | 5–10 min | read on / **stop here** — stopping is a result, not a failure | [pass-1.md](references/pass-1.md) |
| 2 | ≤ 1 hr | set aside / come back later / go to pass 3 | [pass-2.md](references/pass-2.md) |
| 3 | hours | done | [pass-3.md](references/pass-3.md) |

Side door — a field rather than one paper: [survey.md](references/survey.md).

## What the reading is for

Ask before pass 1: are you deciding whether to read it, citing it, implementing it, or
discussing it? The answer sets a floor, never a finish line — each rung's exit decision is
still the reader's.

| Reading it in order to… | Floor |
|---|---|
| decide whether to read it | pass 1 — deciding is exactly what pass 1 buys |
| discuss it | pass 1, and say which depth is behind what you are saying |
| cite it, or depend on its claim | pass 2, minimum |
| implement it, or argue against it | pass 3 |

The rule underneath the table: **do not cite past your reading depth.** Pass 1 buys a
decision and a name; it does not buy the right to assert what the paper shows.

## The gate

Three stages, tracked in the notes file's frontmatter: `sealed` → `committed` →
`contrasted`. The cycle is **per rung, not per paper**. Every rung starts at `sealed`, and
the ladder re-enters it there each time `pass:` advances.

The invariant, and it holds identically at all three rungs: **while `stage: sealed`,
nothing that rung would read is opened — not the paper, and not any secondary account of
it.** `sealed` ends when the reader's own slots for *that* pass have content; at pass 1
those slots are the five Cs — see [five-cs.md](references/five-cs.md). `contrasted` begins
once that pass's divergence report and revised decision both exist.

Once `committed`, read what that rung covers and nothing beyond it:

- **Pass 1** — title, abstract and introduction; every heading; a glance at the maths; the
  conclusions; the references. Not the body.
- **Pass 2** — the body, the figures closely, and the references not yet read. Not the
  proofs.
- **Pass 3** — everything, proofs included, re-derived rather than followed.

Handed a whole PDF at pass 1, an agent that reads all of it has broken the gate for passes
2 and 3 before the reader has committed to either.

Advancing a rung is one edit to the frontmatter: `pass:` to the next number and `stage:`
back to `sealed`, together. The body keeps the record of what was finished; frontmatter
says only where the reader stands now.

Why the gate polices an action and not a sentence, what counts as a commit, no backdating,
and the shape of a refusal are in [pass-1.md](references/pass-1.md). Those sections govern
every rung, not only the first — read them at whichever rung you enter on.

Where the host provides one, prefer a subagent for the reading itself, so the paper
never enters the main conversation and the gate is structural rather than
disciplinary. That is a preference, not the mechanism: the rule sits on the tool
action — open the paper, or don't — and it has to hold exactly the same on a host
with no subagents at all.

**Degradation.** No subagent → read inline; the gate is unchanged. No fetch → ask for
a local file. `Read` cannot open the PDF → ask the reader to paste the text in, and ask
once `committed`, never before — a paste while `sealed` puts the paper in front of you
exactly as a successful read would, and the gate does not care which tool delivered it.
When even the paste is unavailable, the rung does not run: say so and stop.

Never substitute a weaker source for the paper — an abstract page, a publisher's landing
page, a blog post about the paper. Reading one of those is not reading the paper, and
saying out loud that you did it does not make it one; while `sealed` it is a secondary
account, which the gate forbids outright. Separately, and at every stage: name the file or
URL you actually opened.
