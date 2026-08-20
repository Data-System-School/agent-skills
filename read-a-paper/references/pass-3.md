# Pass 3 — the re-creation

## Before you re-create

This rung runs its own commit cycle, and what is sealed here is the re-creation itself. On
entry the notes file reads `pass: 3`, `stage: sealed`: the proofs and the derivations stay
closed, and so does any secondary account of them — someone else's walkthrough, a talk, an
implementation write-up. The reader re-creates first, out of what passes 1 and 2 left them
holding; the skill re-creates second. Two re-creations are worth comparing only if they
were made independently.

The gate's reasoning, what counts as a commit, the no-backdating rule and the shape of a
refusal are in [pass-1.md](pass-1.md). They govern this rung unchanged.

## The key move

Attempt to re-create the work. Make the same assumptions the authors made and build the
thing in your head. Comparing your re-creation against the paper surfaces not just the
innovations but the *hidden failings and assumptions* — the ones no summary mentions,
because the authors did not mention them either.

Identify and challenge every assumption in every statement. Note ideas for future work
as they occur.

Once `committed`, read everything, proofs included — and read a proof by re-deriving it
rather than by following it. This is the only rung at which the proofs are read at all;
passes 1 and 2 both leave them shut.

## The exit

You can reconstruct the paper's structure from memory, name its strong and weak points,
and pinpoint implicit assumptions, missing citations, and problems with the experimental
or analytical technique.

Budget: more than an hour or two, even in a familiar area. Many hours, if not.

## Divergences at this rung

At pass 1, divergence is the skill's own [five Cs](five-cs.md) held up against the
reader's, cell by cell. At pass 3 the shape changes: the divergence report here is not a
second opinion, it is a **second re-creation**. Where two independent re-creations
diverge is where the paper left something unstated.

The three rules do not change: answered differently → discuss; the reader wrote
`UNANSWERED` and the skill answered → discuss, and it is still the highest-value cell;
agreement → one line, no elaboration. [pass-1.md](pass-1.md) gives the reason once.

## Out of scope: running it

> If you intend to cite or depend on this claim, the next step is not another reading —
> it is running it. A paper is a claim backed by someone else's evidence, on someone
> else's hardware, against someone else's workload; it is a very good reason to run the
> experiment, and it is not the experiment. Running it is out of scope for this skill.

## Notes to append

Append this section to the paper's notes file, below the pass 2 blocks.

```markdown
## Pass 3 — my re-creation    <date time>

- **Assumptions I had to make:** <!-- -->
- **The structure, from memory:** <!-- -->
- **Strong points / weak points:** <!-- -->
- **Implicit assumptions, missing citations, technique problems:** <!-- -->
- **Ideas for future work:** <!-- -->

## Pass 3 — divergences    <date time>

<!-- Only divergences. Agreement gets one line. -->
```

Then close the frontmatter: `stage: contrasted`, `pass:` left at 3. This rung is the top of
the ladder; there is no rung above it to advance to.
