# IMPACT — a one-line "fix" that invalidates every multimodal prefix cache

> **Prompt**
>
> vLLM PR #36708, "fix: disambiguate multimodal prefix cache keys", is three lines of
> source. We run multimodal workloads with prefix caching on. What does it actually
> change, what must stay the same, and do we need to plan for the upgrade?

---

## Selection

| | |
|---|---|
| **Mode** | `IMPACT` |
| **Depth** | `audit` |
| **Scope** | Block-hash computation for multimodal requests, and everything that consumes a block hash |
| **Base** | `e5a77a5015e663784119d88d7ff9e77ce7419aef` |
| **Head** | `269bf46d99f1df74e4d779f9c52c74002e057a17` (squash merge of #36708, 2026‑03‑20) |
| **Environment** | macOS 26.4.1, arm64, Python 3.12.0, torch 2.10.0, **no CUDA**; both revisions as `git worktree` checkouts |
| **Artifacts** | [`mm_hash_key_differential.py`](artifacts/mm_hash_key_differential.py) |

`IMPACT`, not `VERIFY`: the question is the behavior delta of a specific merged change and
its blast radius, not whether the code is good.

---

## 1. Anchor base and head

Resolve them from PR metadata rather than guessing:

```console
$ gh pr view 36708 --repo vllm-project/vllm --json number,state,mergeCommit,baseRefName,mergedAt,additions,deletions,changedFiles
{"additions":29,"deletions":16,"changedFiles":3,"baseRefName":"main",
 "mergeCommit":{"oid":"269bf46d99f1df74e4d779f9c52c74002e057a17"},
 "mergedAt":"2026-03-20T02:33:20Z","number":36708,"state":"MERGED"}

$ git rev-parse 269bf46d9^
e5a77a5015e663784119d88d7ff9e77ce7419aef

$ git merge-base --is-ancestor 269bf46d9 v0.19.1 && echo "shipped in v0.19.1"
shipped in v0.19.1

$ git worktree add --detach ../vllm-base e5a77a501
$ git worktree add --detach ../vllm-head 269bf46d9
```

Two worktrees rather than a branch switch, so nothing in the pinned `v0.19.1` checkout
the other examples use is disturbed.

```console
$ git show --stat 269bf46d9 | tail -4
 tests/v1/core/test_kv_cache_utils.py | 18 ++++++++++--------
 tests/v1/core/test_prefix_caching.py | 16 ++++++++++++----
 vllm/v1/core/kv_cache_utils.py       | 11 +++++++----
```

The whole source change, in `_gen_mm_extra_hash_keys`:

```diff
-    if last_pos.offset + last_pos.length < start_token_idx:
+    if last_pos.offset + last_pos.length <= start_token_idx:
         return extra_keys, start_mm_idx
@@
-            if start_token_idx > offset + length:
+            if start_token_idx >= offset + length:
                 # This block has passed the current mm input.
@@
-            # The block contains the current mm input.
-            extra_keys.append(mm_feature.identifier)
+            # The block contains the current mm input. Include its offset
+            # relative to the start of the block so prefix-cache keys stay
+            # distinct when the same MM item appears at different positions
+            # within otherwise-identical placeholder blocks.
+            extra_keys.append((mm_feature.identifier, offset - start_token_idx))
```

Three changes, not one: two boundary comparisons and a **key format change**.

## 2. The PR description, and what history says instead

The description is four lines:

> ## Summary
> Disambiguate multimodal prefix cache keys.
> ## Change
> - adjust multimodal prefix cache key construction in `vllm/v1/core/kv_cache_utils.py`

No reproduction, no statement of the wrong behavior, no mention of what the format change
costs. Version control has more to say. The function's docstring — untouched by this PR —
already specified the new format:

```python
# vllm/v1/core/kv_cache_utils.py, at BOTH revisions
"""Generate extra keys related to MultiModal request for block hash
computation. For multi-modal inputs, the extra keys are
(mm_hash, start_offset) that indicate a mm input contained in the
block and its starting offset in the block tokens.
```

At base the code appended a bare `identifier`. So the base code contradicted its own
docstring, and the PR restored the documented contract. `git log -S` dates the drift:

```console
$ git log --oneline -S "mm_start" -- vllm/v1/core/kv_cache_utils.py
8c3230d8c [V1] Simpify vision block hash for prefix caching by removing offset from hash (#11646)
bf8717eba [V1] Prefix caching for vision language models (#11187)

$ git log -1 --format='%h %ad %s' --date=short bf8717eba
bf8717eba 2024-12-17 [V1] Prefix caching for vision language models (#11187)
$ git log -1 --format='%h %ad %s' --date=short 8c3230d8c
8c3230d8c 2024-12-31 [V1] Simpify vision block hash for prefix caching by removing offset from hash (#11646)
```

The offset was in the original design, **deliberately removed two weeks later**, and
restored 15 months after that. #11646 is not a slip; it argues the case and benchmarks it:

> But offset is redundant and the following hash format is enough […]
> **Simple proof:** We need to distinguish the above example with the following cases:
> 1. The same image but different offset, e.g., `T0,T1,T2,P00 | P01,P02,P03,P04 | …`. The
>    hash0 becomes `hash(None, T0,T1, T2,P00, aaa)`, which is different

That proof holds whenever a shifted image changes *which* placeholder tokens land in the
block. It says nothing about a block that is **entirely** placeholders, where the token-id
component is identical for every alignment — which is exactly the case the 2026 comment
names. So the two PRs are not in contradiction; #11646 proved a narrower statement than it
claimed, and #36708 covers the gap it left. Neither PR says this.

## 3. What changed, measured

[`artifacts/mm_hash_key_differential.py`](artifacts/mm_hash_key_differential.py) builds 13
request shapes and, at each revision, records what `generate_block_hash_extra_keys` returns
per block window and what `Request.block_hashes` produces. Both runs set `PYTHONHASHSEED`,
without which `init_none_hash` seeds the chain from `os.urandom` and no two processes are
comparable (see [example 02](02-trace-prefix-cache-ceiling.md#8-challenge-the-model)).

```console
$ PYTHONHASHSEED=0 PYTHONPATH=vllm-base .venv/bin/python mm_hash_key_differential.py probe base.json
$ PYTHONHASHSEED=0 PYTHONPATH=vllm-head .venv/bin/python mm_hash_key_differential.py probe head.json
$ .venv/bin/python mm_hash_key_differential.py compare base.json head.json
```

```console
1. extra keys per block window (generate_block_hash_extra_keys)
  img_at_0_len16   [ 0:16]   base ('img_a',)           -> head (('img_a', 0),)
  img_at_8_len16   [ 0:16]   base ('img_a',)           -> head (('img_a', 8),)
  img_at_8_len16   [16:32]   base ('img_a',)           -> head (('img_a', -8),)
  img_spans_blocks [32:48]   base ('img_b',)           -> head (('img_b', -24),)
  two_imgs_0_16    [16:32]   base ('img_a',)           -> head (('img_a', 0),)
  two_imgs_0_24    [16:32]   base ('img_a',)           -> head (('img_a', 8),)
  adversarial_len20 [16:32]  base ('img_x', 'img_y')   -> head (('img_x', -16), ('img_y', 4))
  …
  24 window(s) changed, 28 unchanged
```

Two effects are visible in that table:

| Effect | Where it shows | Cause |
|---|---|---|
| Key format: `id` → `(id, offset − block_start)` | every window holding an mm item | the third hunk |
| Offsets can be negative | `('img_a', -8)` — a block holding an item's *tail* | `offset - start_token_idx` is not clamped, unlike the `max(0, …)` the 2024 version used |

What is *not* in that table is either boundary hunk. The prompt hasher threads
`curr_mm_idx` forward, so by the time a block starts at an item's end the loop has already
advanced past that item and neither `>` nor `>=` is reached. The boundary change is only
observable where the index is **not** threaded — the decode path, where
`request_block_hasher` passes `start_mm_idx = -1` for blocks completed by generated tokens:

```console
1b. same windows on the decode path (start_mm_idx = -1)
  img_at_0_len16   [16:32]   base ('img_a',)   -> head None
  img_at_0_len32   [32:48]   base ('img_b',)   -> head None
  two_imgs_0_16    [32:48]   base ('img_a',)   -> head None
  img_a_then_c     [32:48]   base ('img_c',)   -> head None
  …
  25 window(s) changed, 27 unchanged
```

Exactly one block per request is affected: the one starting at the byte after the last mm
item ends. At base it carries that item's identifier despite containing no multimodal
tokens; at head it carries nothing. Since base only ever *adds* a key, this can cost a
cache hit but cannot cause a wrong one.

## 4. What must stay the same

The question an upgrade turns on is not what changed but what did not.

```console
2. block hashes: which request shapes changed between base and head
  adversarial_len16      4/4 block hashes differ
  adversarial_len20      4/4 block hashes differ
  img_a_then_c           4/4 block hashes differ
  img_at_0_len16         4/4 block hashes differ
  img_at_0_len32         4/4 block hashes differ
  img_at_16_len16        3/4 block hashes differ
  img_at_4_len32         4/4 block hashes differ
  img_at_8_len16         4/4 block hashes differ
  img_spans_blocks       4/4 block hashes differ
  text_only_32           same
  text_only_64           same
  two_imgs_0_16          4/4 block hashes differ
  two_imgs_0_24          4/4 block hashes differ

  unchanged shapes: 2  (text_only_32, text_only_64)
  changed shapes:   11
  invariant holds: every text-only shape keeps its exact block hashes
```

**Text-only requests are bit-identical across the upgrade** — `_gen_mm_extra_hash_keys`
returns early when `request.mm_features` is empty, and the differential confirms it rather
than assuming it. Text-only prefix caches survive.

**Every multimodal request's hashes change.** Not "some blocks": for ten of eleven mm
shapes, all four block hashes differ, and `img_at_16_len16` keeps only its one leading
text block. That is the upgrade cost, and it is certain:

- Any warm prefix cache is cold for multimodal traffic after the upgrade. In-process this
  is a one-time miss; across a fleet it is a thundering-herd risk if all replicas restart
  together.
- Anything that *persists or ships* block hashes sees a format change, not just new values.
  `extra_keys` is part of the KV-event payload (`vllm/distributed/kv_events.py:63`,
  `list[tuple[Any, ...] | None]`), so external subscribers and KV connectors that key on
  it are affected. Whether any shipped connector compares hashes across versions was not
  determined here and is recorded as `UNKNOWN`.

## 5. What it buys — and the counterexample it does not cover

The differential also asks the question the PR title implies: does the change remove any
collision?

```console
3. cross-shape hash collisions within one revision
  base: 11 collision(s)
    block 0: adversarial_len16 == adversarial_len20
    block 0: img_at_0_len16 == two_imgs_0_16
    block 0: img_at_16_len16 == text_only_32
    …
  head: 11 collision(s)
    block 0: adversarial_len16 == adversarial_len20
    …
  fixed by the change:      0
  introduced by the change: 0
```

**Zero.** Every collision at base is still there at head, and each of the ordinary ones is
a legitimate shared prefix — `img_at_0_len16` and `two_imgs_0_16` really do start with the
same 16 tokens and the same image, so sharing block 0 is a cache hit, not a bug.

The interesting row is the pair built deliberately to be ambiguous. `adversarial_len16`
and `adversarial_len20` use the same identifiers with different lengths, so blocks 0 and 1
hold identical placeholder token ids with the items aligned differently — the exact shape
the PR comment describes. At block 0 they collide **at both revisions**:

```console
adversarial_len16  block 0: base ('img_x',)  head (('img_x', 0),)
adversarial_len20  block 0: base ('img_x',)  head (('img_x', 0),)
```

The new key records where an item *starts relative to the block*. For two items that both
start at the block's first token, that is `0` either way; what differs between these two
requests is the item's **length**, which the key still does not carry. The change narrows
the ambiguity to same-start-different-extent, it does not close it.

Whether even that residue is reachable in production is a separate question. Constructing
it required two mm items sharing an identifier while having different lengths, and the
identifier is the hash of the processed multimodal item, from which the placeholder count
is derived — so ordinary request construction should not produce it. This harness could
not build a reachable collision that head fixes; that is a statement about 13 shapes, not
a proof.

## 6. Do the tests capture it?

Running head's tests against base's code is the cheapest test of whether the change is
observable at all:

```console
$ cd vllm-base && git checkout 269bf46d9 -- tests/v1/core/test_kv_cache_utils.py tests/v1/core/test_prefix_caching.py
$ PYTHONPATH=. ../.venv/bin/python -m pytest tests/v1/core/test_kv_cache_utils.py tests/v1/core/test_prefix_caching.py -q
FAILED tests/v1/core/test_kv_cache_utils.py::test_request_block_hasher[sha256]
FAILED tests/v1/core/test_kv_cache_utils.py::test_request_with_prompt_embeds_and_mm_inputs[sha256]
FAILED tests/v1/core/test_prefix_caching.py::test_mm_prefix_caching - assert ...
7 failed, 91 passed
$ git checkout HEAD -- tests/v1/core/test_kv_cache_utils.py tests/v1/core/test_prefix_caching.py
```

| code | tests | result |
|---|---|---|
| base | base | 98 passed |
| base | head | **7 failed**, 91 passed |
| head | head | 98 passed |

The seven failures are all assertions on the new key format. The suite proves the format
changed; **no test in either revision asserts that a collision is prevented**, which is
consistent with the differential finding nothing to prevent.

## 7. A check that was wrong before it was right

The first version of the harness called `generate_block_hash_extra_keys(req, start, end, 0)`
for every window — passing `start_mm_idx=0` each time. It produced a table showing
`adversarial_len16` and `adversarial_len20` with *identical* base keys
`('img_x', 'img_y')` at block 1, which reads as a collision the fix removes.

The real caller does not do that. `request_block_hasher` threads the index:

```python
# vllm/v1/core/kv_cache_utils.py
extra_keys, curr_mm_idx = generate_block_hash_extra_keys(
    request, start_token_idx, end_token_idx, curr_mm_idx
)
```

With the index threaded, the two shapes diverge at block 1 (`('img_y',)` vs
`('img_x', 'img_y')`) because they had already consumed a different number of mm items —
and the apparent collision disappears. The harness now threads it, and the block-hash
column agrees with the key column instead of contradicting it.

---

## Report

### Direct answer

#36708 changes the multimodal block-hash key from `identifier` to
`(identifier, offset − block_start)` and fixes two off-by-one boundary comparisons. The
consequences are asymmetric:

- **Certain cost.** Every multimodal request's block hashes change — 11 of 13 probed
  shapes, mostly all blocks. Warm multimodal prefix caches are invalidated by the upgrade,
  and the `extra_keys` payload published in KV events changes shape for external consumers.
  Text-only hashes are bit-identical, verified, so text traffic is unaffected.
- **Unquantified benefit.** Across 13 shapes the change removes **zero** hash collisions,
  and the one deliberately-ambiguous pair still collides at head because the key encodes
  where an item starts, not how far it extends. The PR restores what the function's own
  docstring has specified since 2024 and closes the gap in #11646's redundancy argument —
  blocks that are entirely placeholders — but neither the PR nor the test suite exhibits a
  case where the old key produced a wrong cache hit.

For an upgrade plan: expect a cold multimodal prefix cache on rollout and stagger restarts;
check any KV-event or KV-connector consumer that reads `extra_keys`; text-only deployments
need no action.

### Behavioral impact matrix

| Input class | Base | Head | Delta |
|---|---|---|---|
| Text-only request | hashes H | hashes H | **none** (verified bit-identical) |
| Request with any mm item | `('img',)` per block | `(('img', rel_offset),)` | all block hashes change |
| Block starting exactly where an item ends, on the decode path | stale key attached | key dropped | one block per request; can cost a hit, cannot cause a wrong one |
| Same block on the fresh-prompt path | no key | no key | none — the threaded `curr_mm_idx` already moved past the item |
| Block holding an item's tail | `('img',)` | `(('img', −k),)` | negative offsets appear in keys |
| Two items sharing an identifier, different lengths, aligned differently | block 0 collides | **block 0 still collides** | unchanged |
| KV-event `extra_keys` payload | `list[str]` shape | `list[tuple]` shape | wire format change |

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| Base/head are `e5a77a501` / `269bf46d9`; merged 2026‑03‑20; in `v0.19.1` | `SOURCE` | `gh pr view 36708`; `git rev-parse 269bf46d9^`; `git merge-base --is-ancestor` | Squash merge, so head is the PR |
| The change is 3 hunks: two boundaries and a key format | `SOURCE` | `git show 269bf46d9 -- vllm/v1/core/kv_cache_utils.py` | +29/−16 across 3 files, 2 of them tests |
| The new format is what the docstring already specified | `SOURCE` | docstring identical at both revisions | Base code contradicted it |
| The offset was removed deliberately in 2024 | `SOURCE` | `8c3230d8c` (#11646), title and PR body with benchmark | Restored 15 months later |
| #11646's proof does not cover all-placeholder blocks | `INFERRED` | its stated proof relies on differing block token ids | Consistent with #36708's comment |
| 24 of 52 probed key windows change on the prompt path | `RUNTIME` | `mm_hash_key_differential.py compare`, section 1 | 13 shapes × 4 windows |
| The two boundary hunks are invisible on the prompt path | `RUNTIME` + `SOURCE` | no `-> None` transitions in section 1; `request_block_hasher` threads `curr_mm_idx` | They fire only where the index is not threaded |
| On the decode path (`start_mm_idx = -1`) they drop one stale key per request | `RUNTIME` | section 1b: 25 windows change, including 6 `-> None` | Base attaches an mm identifier to a block with no mm tokens |
| Text-only block hashes are bit-identical | `RUNTIME` | same, section 2, with `PYTHONHASHSEED=0` | The invariant this change must not break |
| All 11 multimodal shapes change their block hashes | `RUNTIME` | same | 10 of them in every block |
| The change removes 0 collisions and introduces 0 | `RUNTIME` | same, section 3 | Among these 13 shapes only |
| The constructed ambiguous pair still collides at head | `RUNTIME` | `adversarial_len16 == adversarial_len20` at block 0, both revisions | Key encodes start offset, not extent |
| Head's tests fail on base code | `RUNTIME` | 7 failed, 91 passed; base/base and head/head both 98 passed | Assertions on the key format only |
| No test asserts a collision is prevented | `SOURCE` | reading the 3 changed tests | Consistent with the differential |
| `extra_keys` is published in KV events | `SOURCE` | `vllm/distributed/kv_events.py:63,79` | Consumers not enumerated |
| First harness version showed a collision the fix removes | `CONTRADICTED` | fixed `start_mm_idx=0` per window vs. the threaded index in `request_block_hasher` | The apparent collision was an artifact of the harness |

### Risks, contradictions, unknowns

- **No model was run.** Every result is hash computation. That a colliding hash would
  actually produce wrong output — reused KV for a differently-aligned image — follows from
  what the cache is for, but was not observed. It needs a GPU host.
- **13 shapes is not a proof of absence.** "Zero collisions fixed" is a statement about
  what this harness could construct with `block_size=16` and single-image prompts. Video,
  audio, interleaved multi-image prompts, and `start_mm_idx == -1` (blocks completed by
  generated tokens) were not probed.
- **The residual ambiguity may be unreachable.** Building it required two mm items with the
  same identifier and different lengths. If the identifier always determines the
  placeholder count, that is unreachable and the residue is theoretical; that implication
  was not verified against the multimodal processor and is `UNKNOWN`.
- **KV-connector impact is `UNKNOWN`.** `extra_keys` crosses a process boundary in KV
  events; whether any shipped connector or external cache compares hashes produced by
  different vLLM versions was not determined.
- **Deployment risk is inferred, not measured.** "Cold cache on rollout" follows from the
  hashes changing; its throughput cost on real traffic was not benchmarked here.

### Smallest next verification steps

1. On a GPU host, serve a vision model at base and at head, send the same image prompt
   twice at each, and compare `vllm:prefix_cache_hits` — confirms the invalidation is
   one-time rather than permanent.
2. Extend the differential to multi-image and video shapes, and to blocks hashed after
   generation starts (`start_mm_idx == -1`), where the boundary change also applies.
3. Ask the multimodal processor whether one identifier can ever correspond to two
   placeholder lengths. A "no" makes the residual collision unreachable and the fix purely
   contract-restoring; a "yes" makes it a real, still-open bug.

### Prediction questions

1. The upgrade lands and text-only latency is unchanged while multimodal TTFT spikes for
   ten minutes and then recovers. Which line of the diff explains it, and what would make
   the spike permanent instead?
2. `img_at_16_len16` changed 3 of 4 block hashes, not 4. Which block kept its hash, and
   what does that tell you about where mm keys attach?
3. If you had to close the residual ambiguity, what would you add to the key — and what
   would that cost the cache hit rate for a long image split across many blocks?

---

## What the mode changed

Read as a three-line diff, this is a typo fix. Read through its consequences, it is a
cache-invalidating format change whose stated benefit does not reproduce.

Three constraints changed the output:

- **Ask what must stay the same, not only what changed.** The delta the PR describes is
  the key format; the fact that decides the upgrade plan is that text-only hashes are
  bit-identical while every multimodal hash moves. Only a differential across both
  revisions distinguishes those, and only the invariant makes the change safe to ship.
- **History is evidence.** The PR body says "disambiguate". `git log -S` says the offset
  was added in 2024, argued away two weeks later with a benchmark, and restored 15 months
  after that — and the docstring specified the new format the whole time. That turns a
  bare diff into a decision with a rationale that can be checked, and the check found the
  gap in the 2024 argument.
- **Check the check.** The first harness passed a fixed `start_mm_idx` instead of threading
  it as the real caller does, and produced exactly the collision the PR title predicts.
  It would have been a satisfying result to report. Matching the caller removed it.
