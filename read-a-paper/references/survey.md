# The literature survey side door

A paper rarely arrives alone. Before pass 1 on any one paper, it is often worth building
a reading list around it: does a survey already exist, and if not, which papers and
which people define this corner of the field? This is that side door.

## Finding the field

1. **Find the entry points.** Use an academic search engine — Google Scholar, Semantic
   Scholar — and well-chosen keywords to get three to five recent, highly-cited papers.
   Make one pass on each, then read their *related work* sections. That gives a
   thumbnail of the field, and possibly a pointer to a survey. **If you find a survey,
   you are done** — read it and congratulate yourself.
2. **Find the key papers and the key people.** No survey? Look for shared citations and
   repeated author names across those bibliographies. Download the key papers and set
   them aside. Go to the researchers' own sites and see where they publish — that names
   the top venues, because the best researchers publish in them.
3. **Scan the recent proceedings** of those venues. Those papers, plus the ones set
   aside in step 2, are the first version of the survey; make two passes through them.
   If they all cite a key paper that was missed, obtain it, read it, and iterate.

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

## Output format

A table: which paper, why it is on the list, and the suggested entry rung.

| Paper | Why it is on the list | Suggested entry rung |
|---|---|---|
| `<title, authors, year>` | shared citation / repeated author / venue scan / survey pointer | `sealed` |

The entry rung is always `sealed` — see the boundary above. A survey produces
candidates, not verdicts; nothing it turns up skips pass 1.

One line is required, not optional: what the survey could **not** establish — a venue
not scanned, a paywalled key paper, a bibliography not obtained. A survey that silently
truncates reads as complete coverage when it was not.
