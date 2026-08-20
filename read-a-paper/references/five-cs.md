# The five Cs

The five Cs are the output of pass 1, and the input to exactly one decision: does this
paper get the next fifty minutes? They are not a summary. Four of the five ask about the
paper's relationship to something outside itself — the genre it belongs to, the argument
it joins, the machine it assumed, and you, the reader. Only Contributions asks what's
inside the paper. That's deliberate: at ten minutes, position tells you more about
whether to keep reading than content does.

## The trap column

Each C below comes with a question and a trap: the specific, plausible-sounding wrong
move that answers a different, easier question instead of the one actually being asked.
The wording is exact on purpose — check your own answer against it before you move on,
and if you're coaching someone else through pass 1, use the same wording to catch them
making the same move.

| | The question | The trap |
|---|---|---|
| **Category** | What type of paper is this? | Reading a prototype's benchmarks as measurement. |
| **Context** | Which other papers is it related to? Which theoretical bases were used? | Listing the citations instead of finding the argument. |
| **Correctness** | Do the assumptions appear valid? | Asking *is the paper right?* — that is a different question, and a later one. |
| **Contributions** | What are the main contributions? | Restating the abstract. |
| **Clarity** | Is the paper well written? | Blaming yourself by default. |

### Category

Papers cluster into a small number of genres, and the trap is reading one as if it were
another. A measurement paper's benchmarks *are* the contribution — the numbers themselves
are the claim. A paper describing a research prototype has benchmarks too, but they're
advocacy: the authors chose the workload that flatters their own system, so read them as
a demonstration, not a measurement. A paper analyzing an existing system or dataset sits
between the two — it measures something the authors didn't build. Worth naming on its
own: the pure cost-model paper, which argues from arithmetic and never ran anything at
all. Its evidence is a derivation, not a number off a machine — there is nothing here to
trust or distrust empirically, only arithmetic to check. Knowing which genre you're in by
minute two changes what the rest of the paper owes you.

### Context

Find the one paper this paper is arguing with. Most papers exist because an earlier
answer to the same problem had a specific weakness the authors set out to fix — a cost it
paid, a case it handled badly, a claim they think is wrong. That target is usually more
informative than the full reference list: a bibliography tells you what the authors read,
but the one paper they're actually arguing with tells you what problem they think they're
solving, and against which alternative. Look in the introduction and related-work section
for the paper that gets named, contrasted, or improved on directly — that's your anchor,
not a head count of citations.

### Correctness

This isn't asking whether the paper's own logic holds together — that's a different,
later question. It's asking whether the world the authors assumed is your world. That
usually comes down to three things: the workload they tested or assumed, the hardware or
platform it ran on, and the failure model they designed against. A paper can be entirely
correct on its own terms and still say nothing useful about your situation, because the
ground underneath it has moved. At pass 1, just note the assumption — you're flagging it,
not testing it yet.

### Contributions

Separate the mechanism the paper invented from the system it happened to ship inside. The
mechanism is the idea — the algorithm, the technique, the argument — and it's what
transfers: it can outlive the specific system, the hardware it ran on, and the team that
built it. The system is one instantiation of that idea, built under constraints that may
no longer hold. If your answer to "what are the contributions" could be lifted verbatim
from the abstract, you haven't done this one yet — the abstract describes the system;
your job is to name the mechanism underneath it.

### Clarity

This isn't a courtesy grade for the authors, and it isn't optional. If pass 1 leaves you
unable to state the paper's contribution, that's evidence about the paper at least as
often as it's evidence about you. Record *which* — it decides what you do next: return
with more background of your own, or reach for a summary of the paper instead.

If you cannot answer all five in ten minutes, either the paper is badly written or you
stopped too early. Both are results.

## Worked: the LSM-Tree paper in ten minutes

O'Neil, Cheng, Gawlick and O'Neil, *The Log-Structured Merge-Tree* (1996). Here is what a
real pass 1 produces, before you have read one body section:

- **Category** — Neither a measurement paper nor a prototype paper: a **design plus a
  cost model**. The authors derive the structure's I/O cost algebraically and compare it
  to a B-tree's on paper. No system was built; no number in it was measured. Knowing that
  by minute two changes how you read the rest — there is nothing here to trust or
  distrust *empirically*, only arithmetic to check.
- **Context** — It argues with the B-tree, on the narrow ground of insert cost, using an
  index over a TPC-A-style History table as its case. Behind it: the Log-Structured File
  System, and the older differential-file idea of batching changes somewhere cheap and
  merging them later. Ahead of it: LevelDB, RocksDB, Cassandra, HBase.
- **Correctness** — The load-bearing assumption is that **the disk arm is the scarce
  resource** — seeks are expensive, sequential I/O is nearly free. True of 1996 disks.
  Not true of an NVMe SSD, where the seek penalty this entire design exists to dodge has
  largely evaporated. Note it and move on; confirming it against real hardware is a
  separate, later step.
- **Contributions** — The **mechanism**: hold the newest data in a memory component,
  cascade it to disk components by rolling sequential merge, and buy cheap writes with
  reads that may have to touch several components. That transferred to every LSM engine
  running today. The specific multi-component cost model mostly did not — production
  engines went to leveled and tiered compaction instead.
- **Clarity** — Dense and notation-heavy, and far harder to read than its central idea is
  to understand. That is the paper, not you — if a clear secondary explanation of the
  mechanism exists, read that first and come back to the original for the cost model.

**The decision this buys you.** Ten minutes in, you have the mechanism, its one fatal
assumption, and the fact that its evidence is arithmetic rather than measurement. That
last fact is already a question worth its own experiment: *does the write cost win
survive on flash?* You didn't answer the question — you earned the right to ask it. The
RocksDB paper, twenty-five years of production evidence about exactly this, is a natural
next read.
