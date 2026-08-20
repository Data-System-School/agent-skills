# The literature survey side door

The input here is a **field**, not a paper: which papers and which people define this
corner of it, and does a survey already exist. The output is a reading list whose entries
each enter the ladder separately. This is that side door.

## Finding the field

What is being harvested at every step is bibliographic signal — titles, authors, venues,
years, citation lists, and pointers to surveys. Never the argument, never the contribution,
never a summary of what a paper says. That is the reader's, on the ladder.

1. **Find the entry points.** Use an academic search engine — Google Scholar, Semantic
   Scholar — and well-chosen keywords to get three to five recent, highly-cited papers.
   Take their titles, authors, venues and years, and take the *citation lists* out of their
   related-work sections. The citation lists give a thumbnail of the field, and possibly a
   pointer to a survey. **If a survey exists, the search is done** — put it at the top of
   the list and congratulate the reader; it is their entry point, and it enters the ladder
   at `sealed` like every other row.
2. **Find the key papers and the key people.** No survey? Look for shared citations and
   repeated author names across those bibliographies. Obtain the key papers and set them
   aside unopened. Go to the researchers' own sites and see where they publish — that names
   the top venues, because the best researchers publish in them.
3. **Scan the recent proceedings** of those venues, at the level of titles and authors.
   Those papers, plus the ones set aside in step 2, are the first version of the survey.
   The passes through them are the reader's, taken on the ladder — the survey does not take
   them on the reader's behalf. If the bibliographies converge on a key paper the list
   missed, obtain it, add it as a row, and iterate.

Data-systems venues are a concrete example here, not the only answer: SIGMOD, VLDB,
CIDR, and OSDI/SOSP/NSDI for distributed and streaming work.

For a survey of a *running system* rather than a research literature, add the
non-academic sources: design docs, commit history, issue tracker. Papers tell you what
was intended; the tracker tells you what happened.

## The boundary

This is the one rule that keeps the survey from becoming a bypass of [pass 1](pass-1.md):

> **The survey may be delegated. The reading may not.** Finding entry points,
> extracting shared citations, spotting repeated author names, and scanning proceedings
> are lookup, not comprehension — do all of it. Every paper that comes out of a survey
> enters the ladder at `sealed`, exactly like a paper the reader brought in themselves.
> A reading list is not a head start on pass 1.

A candidate that seems to need a pass before it earns its row does not get one here. Put it
on the list with what the lookup actually established, and let the reader spend pass 1 on
it — that is the decision pass 1 exists to make.

## Output format

A table: which paper, why it is on the list, and the suggested entry rung.

| Paper | Why it is on the list | Suggested entry rung |
|---|---|---|
| `<title, authors, year>` | shared citation / repeated author / venue scan / survey pointer | `sealed` |

The "why" column holds the lookup evidence, not a verdict on the paper's content: how it
was found, not what it argues.

The entry rung is always `sealed` — see the boundary above. A survey produces
candidates, not verdicts; nothing it turns up skips pass 1.

One line is required, not optional: what the survey could **not** establish — a venue
not scanned, a paywalled key paper, a bibliography not obtained. A survey that silently
truncates reads as complete coverage when it was not.
