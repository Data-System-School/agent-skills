# Pass 1 — the commit gate

## Budget and order

5–10 minutes. Read in this order, and no other:

1. Title, abstract, and introduction — carefully.
2. Every section and sub-section heading — ignore everything under them.
3. The math, if there is any — a glance, only to see what it stands on.
4. The conclusions.
5. The references — a scan, ticking off the ones already read.

That scan is what the ten minutes buys: an answer to each of the [five Cs](five-cs.md).
Pass 1 is a triage, not a reading — the order above is the whole method, not a
suggested starting point.

## The notes file

The notes file is a sidecar: it sits next to the paper, same directory. `lsm-tree.pdf`
gets `lsm-tree.notes.md`. If the source is a URL with no local file to sit beside, the
notes file lands in the working directory instead — and the skill says that path out
loud, once, the first time it creates the file.

Frontmatter is **state**: it changes as the paper moves through the ladder. The body is
**record**: once a section is written, it is appended to, never edited. That split is
what makes "no backdating" (below) enforceable — a state field can move forward; a
paragraph already in the body cannot be rewritten after the fact.

Create the file with this template. Leave the HTML comments in the body as prompts until
the reader replaces them with their own words.

Fill the frontmatter from what is already in hand. `paper:` comes from the reader or from
the filename — never from opening the paper to check, which is the act the gate forbids
below; if neither supplies it, leave the placeholder and fill it once `committed`.
`secondary:` is whatever entry triage established, not the template's default.

```markdown
---
paper: "<title, authors, year>"
source: <path or URL>
stage: sealed             # sealed | committed | contrasted
pass: 1
secondary: none           # none | exists-unread | used
---

## Pass 1 — my commit    <date time>

- **Category:** <!-- measurement, analysis, prototype, or cost model? -->
- **Context:** <!-- which ONE paper is it arguing with? -->
- **Correctness:** <!-- is the world they assumed your world? workload / hardware / failure model -->
- **Contributions:** <!-- the mechanism, separated from the system -->
- **Clarity:** <!-- if you can't state the contribution: whose problem is that? -->
- **Decision:** <!-- read on, or stop here -->

## Pass 1 — divergences    <date time>

<!-- Only divergences. Agreement gets one line. -->

- **Decision, revised:** <!-- unchanged, or changed — and by which divergence -->
```

The five slots in `Pass 1 — my commit` are the [five Cs](five-cs.md); the trap column
there is the standard each answer is checked against once the skill has read the paper
and written its own.

## The gate

Three stages, tracked in the notes file's `stage` field: `sealed`, `committed`,
`contrasted`. The rule in one line: **before `committed`, this rung's material is not
opened.** The three run in order and never run backwards *within* a rung — a commit once
written is not un-written. But the cycle is per rung, not per paper: when a pass's exit
decision is to go on, `pass:` advances and `stage` returns to `sealed` for the rung above,
which starts with the reader's commit exactly as this one did.

Everything below — what `sealed` permits, why the gate is on reading, what counts as a
commit, no backdating, and the refusal shapes — is written for pass 1 and governs passes 2
and 3 identically, with each rung's own slots in place of the five Cs and each rung's own
material in place of the paper.

### `sealed`

Permitted:

- locating the file or the URL;
- establishing *whether* secondary material exists — a survey, a distillation, a talk —
  without reading it;
- handing over the empty template above;
- noting the start time;
- explaining background terminology that does not reference this paper.

Forbidden: opening the original — no PDF read, no fetch of the paper itself, no
exception for "just the title" or "just to check if it's worth reading." Forbidden on the
same footing: reading any secondary account of it — a survey, a distillation, a talk, a
blog post — because a distillation carries the five Cs whole, and handing one over ends the
gate as completely as reading the paper does.

### Why the gate is on reading, not speaking

Write this rule as forbidding an action, never as forbidding a sentence. "The skill has
read the paper but won't say what's in it" looks like compliance and is not — it is a
decorative gate, because almost none of what actually leaks during `sealed` is a stated
answer:

- **A question can carry its answer.** "Notice how it compares against the B-tree?" has
  already given away Context — the question could not exist without having read for the
  answer first.
- **A shortlist is the skill writing the answer and calling it a choice.** Offering
  "measurement, prototype, or cost model — which one?" after the skill has read the
  paper isn't a question; it's the skill's own answer, narrowed down and handed back as
  if the reader had supplied it.
- **Acknowledgement is a signal.** The reader writes half an answer and the skill says
  "right" — one word, and the guess is confirmed before the reader finished forming it.
- **A summary leaks on the way past.** Reading the abstract aloud "just to help orient,"
  or paraphrasing a section while explaining something else, moves the content without
  ever stating a conclusion.

None of those four is planned — nobody sits down intending to leak Context through a
leading question. That's exactly why a rule phrased as "don't reveal the answer" fails:
it polices sentences, and not one of the four leaks above is a sentence with the answer
in it. So the rule is not on what gets said. It is on a single action, checkable by
anyone reading the transcript: before the notes file reaches `committed`, the skill does
not open the paper.

### `committed`

All five slots hold the reader's own words, plus a Decision. **Every slot still holding
only an HTML comment means uncommitted** — the prompt is not an answer, and neither is the
prompt with a word appended to it. Content includes a **named failure**:
`UNANSWERED — ran out of time before the conclusions` is a commit; a blank is not.

This isn't a formality. [five-cs.md](five-cs.md) gives the rule this comes from: failing
to answer all five in ten minutes means either the paper is badly written or the reader
stopped too early, and both are findings. A blank slot records neither — it just erases
which one happened. Naming the failure is what gives Clarity something to work with
later.

**No backdating.** Once a `Pass 1 — my commit` block exists, it is final — not touched
to fix a typo in the reasoning, not touched because the reader thought of a better
answer five minutes later, not touched for any reason. The next thought is a new
thought: it goes in the divergence report, appended below, on its own timestamp.

### `contrasted`

The divergence report and the revised decision both exist. `stage` moves to
`contrasted` only once they do — not when the skill finishes its own read, and not on
request.

## Divergences

Once `committed`, the skill opens the paper — and reads pass 1's slice of it, not the
whole thing: title, abstract and introduction; every section and sub-section heading; a
glance at the maths; the conclusions; the references. **Not the body.** The body is pass
2's, and reading it now seals nothing for the rung the reader has not yet committed to.

Off that slice, the skill writes its own five Cs into the divergence report, cell by cell,
against the reader's:

- Both answered, **differently** → discuss.
- The reader wrote `UNANSWERED`, the skill answered → discuss. **This is the
  highest-value cell** — it is the one place the gate was worth running at all.
- Both **agree** → one line. No elaboration.

The third rule is discipline, not brevity: elaborating on an agreement hands over a
distillation by the back door, and that dissolves the mechanism the whole gate exists to
protect.

One caveat, and state it whenever it applies: if `secondary: used` — the reader's pass 1
came from a summary rather than the paper itself — agreement between the two answers is
not evidence of anything. They may simply share a source. Say so in the report.

Close by updating `Decision, revised`: unchanged, or changed — and by which divergence. A
decision that *flips* — going to stop, then the skill names the paper this one argues with
and pass 2 is suddenly worth an hour — is the clearest single measure of whether the
contrast was worth running, and it costs one line to record.

Then move the frontmatter to match it, in one edit. Stop here → `stage: contrasted`, `pass:`
left at 1; the paper is finished, and stopping is the result. Read on → `pass: 2` and
`stage: sealed` together, and the next rung opens with the reader's commit, not with the
skill's reading. The pass 1 blocks already in the body are what records that this rung was
run; frontmatter only says where the reader stands now.

## Refusals

The gate gets tested directly, in conversation. Refuse in **one sentence, no lecture**.
A second refusal in the same conversation is **shorter than the first, never longer** —
repetition is not an invitation to justify further.

- *"Just give me the five Cs."* Refused — the paper isn't open; here is the empty
  template instead.
- *"I'll fill it in afterwards, tell me the gist now."* Refused — that's backdating with
  extra steps: the commit exists before the read, never reconstructed after it.
- *"Read it first and give me a few Category options to pick from."* Refused — a
  shortlist read off the paper is the skill choosing the answer and handing it back as a
  menu.
