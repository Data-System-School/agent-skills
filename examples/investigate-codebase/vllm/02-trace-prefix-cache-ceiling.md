# TRACE — why a fully cached prompt still pays for a whole block of prefill

> **Prompt**
>
> We turned on prefix caching in vLLM. For a workload that re-sends one identical
> 512-token prompt, `vllm:prefix_cache_hits / vllm:prefix_cache_queries` settles at about
> 0.97 and never reaches 1.0. For a second workload whose requests share a 12-token system
> prompt, it stays at 0.00. Trace what actually decides the hit. We have no GPU on hand.

---

## Selection

| | |
|---|---|
| **Mode** | `TRACE` |
| **Depth** | `working` |
| **Scope** | Request token ids → block hashes → cache lookup → tokens the scheduler asks the model to run, for a repeated prompt under APC |
| **Revision** | `b1388b1fbf5aaef47937fabe98931211684666a6` (tag `v0.19.1`) |
| **Environment** | macOS 26.4.1, arm64, Python 3.12.0, torch 2.10.0, **no CUDA**, vLLM **not installed** — source tree on `PYTHONPATH` |
| **Artifacts** | [`vllm_prefix_cache_probe.py`](artifacts/vllm_prefix_cache_probe.py), [`vllm_scheduler_probe.py`](artifacts/vllm_scheduler_probe.py) |

`TRACE`, not `ORIENT`: the question is one concrete observable with a causal answer, and it
needs a thin slice through a 1,475-file package rather than a map of it.

The environment is the constraint that shapes this run. vLLM is a GPU inference server and
this machine has no GPU, so "just run it and look" is not available. Most of the work below
is finding out *which* parts of vLLM can still be executed, and being explicit about where
that stops.

---

## 1. Anchor the target

```console
$ git clone --filter=blob:none --no-checkout https://github.com/vllm-project/vllm.git
$ git -C vllm checkout v0.19.1
$ git -C vllm rev-parse HEAD
b1388b1fbf5aaef47937fabe98931211684666a6
```

The repository ships agent instructions, which the operating contract says to read before
touching implementation:

```console
$ head -3 vllm/AGENTS.md
# Agent Instructions for vLLM
> These instructions apply to **all** AI-assisted contributions to `vllm-project/vllm`.
> Breaching these guidelines can result in automatic banning.
```

Most of `AGENTS.md` governs contributions — duplicate-work checks, no busywork PRs, a human
who can defend every line. None of that applies to a read-only investigation, and no PR is
being proposed here. One rule does apply, because it is about the environment:

> **Never use system `python3` or bare `pip`/`pip install`.** All Python commands must go
> through `uv` and `.venv/bin/python`.

So `uv` it is.

**Can the system under investigation be run at all?** That question is cheaper to answer
first than last:

```console
$ uv pip install --python .venv-probe/bin/python --no-build --dry-run "vllm==0.19.1"
  × No solution found when resolving dependencies:
  ╰─▶ Because vllm==0.19.1 has no usable wheels and you require vllm==0.19.1,
      we can conclude that your requirements are unsatisfiable.

$ .venv/bin/python -c "import torch; print(torch.cuda.is_available())"
False
```

No wheel for macOS arm64, no CUDA. An end-to-end `LLM(...)` or `vllm serve` run is out of
reach, and stays `UNKNOWN` for the whole investigation. That is not the same as having no
runtime evidence — it means finding the boundary of what *is* executable.

Two facts move that boundary a long way:

```console
$ rg -n "current_platform" vllm/v1/core/ vllm/v1/request.py vllm/v1/kv_cache_interface.py
$ echo "rg exit: $?"
rg exit: 1
```

Nothing in the V1 KV-cache and request layer consults the platform — no device coupling to
work around. And vLLM marks its own prefix-caching tests as CPU tests:

```python
# tests/v1/core/test_prefix_caching.py:42
pytestmark = pytest.mark.cpu_test
```

So the layer that answers this question is exactly the layer that runs without a GPU.

## 2. Frame falsifiable questions

- **P1** — A re-sent identical prompt is not 100% cached. Something withholds part of it,
  and the withheld amount is a whole block rather than a token.
- **P2** — A 12-token shared prefix reports 0.00 because the cache is keyed on *full*
  blocks, and 12 tokens never fill one.
- **P3** — P1's shortfall is caused by the lookup being capped below the prompt length. If
  that cap moves, the shortfall moves with it.

P3 is the one that makes this causal rather than a story that happens to fit the numbers.

## 3. Build the smallest harness that can run — and get it wrong first

Source tree on `PYTHONPATH`, no install:

```console
$ PYTHONPATH=vllm .venv/bin/python -c "import vllm.v1.core.kv_cache_manager as m; print('OK')"
vllm/vllm/__init__.py:7: RuntimeWarning: Failed to read commit hash: No module named 'vllm._version'
WARNING [__init__.py:28] The vLLM package was not found, so its version could not be inspected.
                         This may cause platform detection to fail.
OK
```

The KV-cache manager imports. The scheduler does not:

```console
$ PYTHONPATH=. ../.venv/bin/python -c "
from tests.v1.core.utils import create_scheduler
create_scheduler(enable_prefix_caching=True, block_size=16)"
RuntimeError: Failed to infer device type, please set the environment variable
`VLLM_LOGGING_LEVEL=DEBUG` to turn on verbose logging to help debug the issue.
```

Taking the error's own advice:

```console
$ PYTHONPATH=. VLLM_LOGGING_LEVEL=DEBUG ../.venv/bin/python -c "from vllm.platforms import current_platform"
DEBUG [platforms/__init__.py:56]  TPU platform is not available because: No module named 'libtpu'
DEBUG [platforms/__init__.py:106] CUDA platform is not available because: NVML Shared Library Not Found
DEBUG [platforms/__init__.py:127] ROCm platform is not available because: No module named 'amdsmi'
DEBUG [platforms/__init__.py:165] Checking if CPU platform is available.
DEBUG [platforms/__init__.py:182] CPU platform is not available because: No package metadata was found for vllm
```

The last line is not about hardware. `cpu_platform_plugin` (`vllm/platforms/__init__.py:163`)
would have accepted this machine on the second check:

```python
try:
    is_cpu = vllm_version_matches_substr("cpu")     # raises: no distribution metadata
    ...
    if not is_cpu:
        is_cpu = sys.platform.startswith("darwin")  # never reached
except Exception as e:
    logger.debug("CPU platform is not available because: %s", str(e))
```

The macOS branch sits after the version probe inside the same `try`, so a metadata error
takes the whole block down and the platform resolves to `UnspecifiedPlatform`. **This is a
property of the harness, not of vLLM's behavior on a supported install** — a source tree on
`PYTHONPATH` is not an installed distribution. The fix is to make it one, minimally:

```console
$ SP=$(.venv/bin/python -c "import site; print(site.getsitepackages()[0])")
$ mkdir -p "$SP/vllm-0.19.1.dist-info"
$ printf 'Metadata-Version: 2.1\nName: vllm\nVersion: 0.19.1\n' > "$SP/vllm-0.19.1.dist-info/METADATA"
$ PYTHONPATH=. ../.venv/bin/python -c "
from vllm.platforms import current_platform
print(type(current_platform).__name__, current_platform.is_cpu())"
CpuPlatform True
```

That one gap had been quietly corrupting a check that looked like it was about the code
under test. Before the shim, vLLM's own prefix-caching suite reported this:

```console
$ PYTHONPATH=. ../.venv/bin/python -m pytest tests/v1/core/test_prefix_caching.py -q
49 passed, 1 warning, 49 errors in 6.77s

$ ... -q "tests/v1/core/test_prefix_caching.py::test_null_parent_block_hash"
_______________ ERROR at teardown of test_null_parent_block_hash _______________
    @pytest.fixture(autouse=True)
    def cleanup_fixture(should_do_global_cleanup_after_test: bool):
        yield
        if should_do_global_cleanup_after_test:
>           cleanup_dist_env_and_memory()
vllm/distributed/parallel_state.py:1932: in cleanup_dist_env_and_memory
    torch.accelerator.empty_cache()
E   RuntimeError: device_allocator INTERNAL ASSERT FAILED ... Allocator for mps is not a DeviceAllocator.
```

49 errors, zero of them from a test body. `cleanup_dist_env_and_memory` guards that call
with `if not current_platform.is_cpu()` (`parallel_state.py:1931`); with the platform
unresolved that guard was false, so teardown asked an Apple-silicon torch build to empty a
CUDA-style allocator. With the metadata shim in place:

```console
$ PYTHONPATH=. ../.venv/bin/python -m pytest tests/v1/core/test_prefix_caching.py \
      tests/v1/core/test_kv_cache_utils.py tests/v1/core/test_scheduler.py -q
191 passed, 1 skipped, 16 warnings in 134.35s (0:02:14)

$ ... tests/v1/core/test_scheduler.py -q -rs
SKIPPED [1] tests/v1/core/test_scheduler.py:2048: needs investigation
```

The one skip is vLLM's own — a `pytest.skip("needs investigation")` in the repository, not
an environment skip introduced here. vLLM's V1 core suite — prefix caching, block hashing,
scheduling — passes on a laptop with no GPU. That is the floor the rest of this
investigation stands on.

## 4. Measure the phenomenon

[`artifacts/vllm_prefix_cache_probe.py`](artifacts/vllm_prefix_cache_probe.py) drives the
real `KVCacheManager` and `Request`; the only local code is the request/config constructor
copied from `tests/v1/core/test_prefix_caching.py`. One request is scheduled to warm the
cache, a second asks how much of itself is already computed.

```console
$ PYTHONPATH=/path/to/vllm .venv/bin/python vllm_prefix_cache_probe.py
A. exact repeat of the same prompt
  case                               prompt     hit     ratio
  identical prompt, second request      512     496    96.88%
  -> 16 tokens (1 block(s) of 16) are recomputed even though every token was cached.
  -> PrefixCacheStats: queries=1024 hits=496

B. shared prefix shorter than one block
  shared prefix len                  prompt     hit     ratio
  shared=12  (block_size=16)             76       0     0.00%
  shared=15  (block_size=16)             79       0     0.00%
  shared=16  (block_size=16)             80      16    20.00%
  shared=17  (block_size=16)             81      16    19.75%
  shared=32  (block_size=16)             96      32    33.33%

F. negative control — a prompt that shares nothing
  disjoint prompt, same length          512       0     0.00%
  -> control passed (0 hits), so the probe can distinguish hit from miss.
```

P1 and P2 hold, with numbers: the shortfall is **exactly one block of 16**, not one token,
and the 12-token prefix is not partially cached — it is not cached at all. `shared=17`
matters more than it looks: 17 shared tokens still buy only 16, because the 17th does not
fill a second block.

The reported ratio also stops being mysterious. `PrefixCacheStats.record`
(`vllm/v1/metrics/stats.py:131`) counts `queries` as the full prompt length and `hits` as
the block-aligned computed tokens, so a stream of identical 512-token prompts converges on
496/512 = 0.969, which is the ~0.97 in the prompt.

## 5. Locate the mechanism in source

| Step | Symbol | Input | Decision | Output | Evidence |
|---|---|---|---|---|---|
| 1 | `request_block_hasher` | token ids, `block_size` | `if end_token_idx > num_tokens: break` — only full blocks | chained `block_hashes` | `SOURCE` `vllm/v1/core/kv_cache_utils.py:596` |
| 2 | `KVCacheManager.get_computed_blocks` | `Request` | `skip_reading_prefix_cache` short-circuit | `(no blocks, 0)` | `SOURCE` `vllm/v1/core/kv_cache_manager.py:192` |
| 3 | same | `Request` | `max_cache_hit_length = request.num_tokens - 1` | cap passed down | `SOURCE` `vllm/v1/core/kv_cache_manager.py:201` |
| 4 | `UnitaryKVCacheCoordinator.find_longest_cache_hit` | hashes + cap | delegate per KV-cache group | hit blocks | `SOURCE` `vllm/v1/core/kv_cache_coordinator.py:349` |
| 5 | `FullAttentionManager.find_longest_cache_hit` | hashes + cap | `max_num_blocks = max_length // block_size`, then walk the chain until a miss | list of cached blocks | `SOURCE` `vllm/v1/core/single_type_kv_cache_manager.py:445` |
| 6 | `Scheduler.schedule` | `num_computed_tokens` | `num_new_tokens = request.num_tokens - num_computed_tokens`; `assert num_new_tokens > 0` | tokens the model runs | `SOURCE` `vllm/v1/core/sched/scheduler.py:681` |

Step 3 carries its own explanation:

```python
# vllm/v1/core/kv_cache_manager.py:195-201
# NOTE: When all tokens hit the cache, we must recompute the last token
# to obtain logits. Thus, set max_cache_hit_length to prompt_length - 1.
# This can trigger recomputation of an entire block, rather than just
# the single last token, because allocate_slots() requires
# num_computed_tokens to be block-size aligned. Removing this limitation
# could slightly improve performance in the future.
max_cache_hit_length = request.num_tokens - 1
```

The integer division in step 5 turns that one-token cap into a one-block loss: `511 // 16`
is 31 blocks, not 31.9.

## 6. Test P3 — move the cap, and then remove it

If the cap is the cause, adding tokens the cache has never seen should let the *cached*
part be reused in full. Same warm cache, longer query:

```console
D. manipulation — same cache, one extra token on the query
  query length                       prompt     hit     ratio
  512 cached +  0 new token(s)          512     496    96.88%
  512 cached +  1 new token(s)          513     512    99.81%
  512 cached +  2 new token(s)          514     512    99.61%
  512 cached + 16 new token(s)          528     512    96.97%
```

One extra token moves the hit from 496 to 512. Nothing about the cache changed — only
`request.num_tokens`, and therefore the cap. P3 holds.

The stronger version is to remove the subtraction and see what breaks.
[`artifacts/vllm_scheduler_probe.py`](artifacts/vllm_scheduler_probe.py) drives the real
`Scheduler`, then re-runs the same scenario with `find_longest_cache_hit` wrapped so the cap
arrives one token higher — undoing exactly the `- 1`, without editing the repository or
reimplementing anything:

```console
$ PYTHONPATH=/path/to/vllm .venv/bin/python vllm_scheduler_probe.py
prompt = 512 tokens, block_size = 16, same prompt twice

  enable_prefix_caching     req 1 tokens  req 2 tokens   queries    hits
  False                              512           512         0       0
  True                               512            16      1024     496

  manipulation: cache lookup capped at num_tokens instead of num_tokens - 1
    -> AssertionError at vllm/v1/core/sched/scheduler.py:681
```

Two results in one run. The scheduler asks the model for **16 tokens instead of 512** on the
second request. The 3.1% the ratio reports as missing *is* the entire remaining cost — a 32×
reduction in prefill work, flattened by the metric into "about 97%". And giving back the
withheld token does
not produce a 100% hit; it produces `assert num_new_tokens > 0` firing at the line named in
step 6. A fully cached prompt would be scheduled with zero tokens to run, and there would be
no forward pass to produce the next token's logits.

## 7. Case C: identical tokens, zero hit, different mechanism

The 0.00 workload has a second, unrelated way to happen — one that timing or hit-rate data
could never distinguish from a cold cache:

```console
C. identical prompt, but the request asks for prompt logprobs
  case                               prompt     hit     ratio
  prompt_logprobs=None                  512     496    96.88%
  prompt_logprobs=1                     512       0     0.00%
  cache_salt='tenant-b'                 512       0     0.00%
```

Same token ids, same warm cache, no hit at all. Two different causes:

| | Where | Why |
|---|---|---|
| `prompt_logprobs=1` | `vllm/sampling_params.py:425` → `skip_reading_prefix_cache = self.prompt_logprobs is not None`, consumed at `kv_cache_manager.py:192` | The lookup is skipped before any hashing. The source says *that*, not *why*; the likely reason — reused blocks carry no logits, so prompt-position logprobs need the prompt run — is `INFERRED` |
| `cache_salt='tenant-b'` | `generate_block_hash_extra_keys` (`kv_cache_utils.py:497-526`) folds the salt into the **first** block's extra keys | Hashes chain, so one changed key at block 0 changes every block hash — the intended multi-tenant isolation |

Attributing a 0.00 hit rate to "the prefix isn't long enough" would be right for case B and
wrong for both of these, and the two are only a few characters apart in a request body.

## 8. Challenge the model

**How large can the last-block tax get?** It scales with `block_size`. The probe builds
`KVCacheConfig` directly, so the sweep includes sizes the CLI would not necessarily accept —
the endpoints are there to show the shape, not to recommend a setting:

```console
E. same 512-token repeat, different block_size
  block_size=1                          512     511    99.80%
  block_size=16                         512     496    96.88%
  block_size=64                         512     448    87.50%
  block_size=128                        512     384    75.00%
  block_size=256                        512     256    50.00%
```

The middle of that sweep is not hypothetical. `CacheConfig.DEFAULT_BLOCK_SIZE` is 16
(`vllm/config/cache.py:34`), but a platform overrides it when the user did not choose one:
`CpuPlatform.check_and_update_config` sets **128** (`vllm/platforms/cpu.py:165-166`) and
`XpuPlatform` sets 64 (`vllm/platforms/xpu.py:167`). On a CPU backend at its own default,
an exact prompt repeat reuses 384 of 512 tokens — a 25% recompute tax on a prompt that is
entirely cached. What a CUDA deployment resolves to was not observed here.

**Are block hashes stable across processes?** The chain is seeded by `NONE_HASH`:

```console
G. block-hash stability across processes
  PYTHONHASHSEED=None  hash_algo=sha256
  block[0] hash, first  init_none_hash: 614eb7f91bb2685df21b492e8aad62bb...
  block[0] hash, second init_none_hash: 347de0f88a7a62032664111df980a292...
  identical: False
  with PYTHONHASHSEED='0' set, identical: True
```

`init_none_hash` (`vllm/v1/core/kv_cache_utils.py:91-106`) uses `os.urandom(32)` when
`PYTHONHASHSEED` is unset, and warns about it *only* for the CBOR hash functions — while the
default `prefix_caching_hash_algo` is `sha256` (`vllm/config/cache.py:68`), which takes the
same random branch silently. Within one engine process this is harmless. Whether it matters
for anything that compares hashes *across* processes is not settled here and is recorded as
`UNKNOWN`.

**Does the documentation say any of this?** Partly. `docs/design/prefix_caching.md` states
"We only cache full blocks" — case B is documented. The word "recompute" does not appear in
that document or in `docs/features/automatic_prefix_caching.md`, and the doc's framing is
"prefix caching is almost a free lunch". Case A is implementation behavior with no
documentation, described only in the source comment quoted in §5.

---

## Report

### Direct answer

A repeated prompt cannot report a 100% prefix-cache hit. `get_computed_blocks` caps the
lookup at `request.num_tokens - 1` so that at least one token remains to run — a scheduled
request with zero tokens would trip `assert num_new_tokens > 0`, and the model must run the
last position to produce logits. `FullAttentionManager.find_longest_cache_hit` then floors
that cap to whole blocks (`max_length // block_size`), which turns a one-token reservation
into a one-block reservation: 496 of 512 tokens at `block_size=16`, giving 0.969. The
12-token workload reports 0.00 for a different reason — only full blocks are hashed, so a
12-token shared prefix is never a cache key at all. And identical tokens can still report
0.00 for two further reasons that have nothing to do with prefix length: `prompt_logprobs`
skips the lookup entirely, and `cache_salt` changes every block hash by design.

In work terms rather than metric terms: the second request was scheduled for **16 tokens
instead of 512**.

### Shortest supported execution path

```
request token ids
  └─ Request.__init__ → block_hasher              only FULL blocks hashed, chained
                                                  kv_cache_utils.py:596
      └─ Scheduler.schedule()                     waiting request, num_computed_tokens == 0
          └─ KVCacheManager.get_computed_blocks
              ├─ skip_reading_prefix_cache ──────► (0 hits)          [case C: prompt_logprobs]
              │                                    kv_cache_manager.py:192
              ├─ max_cache_hit_length = num_tokens - 1               [case A]
              │                                    kv_cache_manager.py:201
              └─ coordinator.find_longest_cache_hit
                  └─ FullAttentionManager.find_longest_cache_hit
                     max_num_blocks = max_length // block_size       [case A + case B]
                     single_type_kv_cache_manager.py:445
          └─ num_new_tokens = request.num_tokens - num_computed_tokens
             assert num_new_tokens > 0             scheduler.py:681  ← why the -1 exists
```

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| An exact 512-token repeat hits 496 tokens, not 512 | `RUNTIME` | `vllm_prefix_cache_probe.py` case A, real `KVCacheManager` | 96.88%; `queries=1024 hits=496` |
| The shortfall is one whole block, not one token | `RUNTIME` + `SOURCE` | case A; `single_type_kv_cache_manager.py:445` | `511 // 16 == 31` blocks |
| The cap is `num_tokens - 1` | `SOURCE` | `kv_cache_manager.py:201` and its NOTE at `:195` | Comment states the reason: logits for the last token |
| The cap is the cause | `RUNTIME` | case D: +1 query token → hit 496 → 512 | Manipulation; cache unchanged |
| Removing the cap breaks scheduling | `RUNTIME` | `vllm_scheduler_probe.py`, wrapped `find_longest_cache_hit` | `AssertionError` at `scheduler.py:681` |
| Second request runs 16 tokens instead of 512 | `RUNTIME` | `vllm_scheduler_probe.py`, real `Scheduler` | APC off: 512/512; APC on: 512/16 |
| A sub-block shared prefix caches nothing | `RUNTIME` + `SOURCE` | case B (12, 15 → 0; 16 → 16); `kv_cache_utils.py:596` | Documented in `docs/design/prefix_caching.md` |
| `prompt_logprobs` disables the lookup | `RUNTIME` + `SOURCE` | case C; `sampling_params.py:425` → `kv_cache_manager.py:192` | Identical tokens, 0 hits |
| `cache_salt` changes every block hash | `RUNTIME` + `SOURCE` | case C; `kv_cache_utils.py:518-526` | Salt enters at block 0; chaining does the rest |
| Tax scales with `block_size` | `RUNTIME` | case E: 96.88% at 16, 87.50% at 64, 75.00% at 128, 50.00% at 256 | Sweep bypasses CLI validation by building `KVCacheConfig` directly |
| Platforms override the default block size | `SOURCE` | `platforms/cpu.py:165-166` (128), `platforms/xpu.py:167` (64), `config/cache.py:34` (16) | So the 75% row is a shipped CPU default, not an extreme; CUDA's resolved value was not observed |
| Block hashes are not reproducible across processes by default | `RUNTIME` + `SOURCE` | case G; `kv_cache_utils.py:91-106`, `config/cache.py:68` | Warning fires only for CBOR algorithms; `sha256` takes the same branch silently |
| vLLM's own V1 core tests pass here | `RUNTIME` | `pytest tests/v1/core/{test_prefix_caching,test_kv_cache_utils,test_scheduler}.py` | 191 passed, 1 skipped, 134s |
| End-to-end engine behavior on GPU | `UNKNOWN` | `uv pip install --no-build vllm==0.19.1` → no usable wheels; `torch.cuda.is_available()` is `False` | Nothing here was measured through a real forward pass |
| "vLLM's V1 core cannot be exercised on this machine" — the first reading of `Failed to infer device type` plus 49 teardown errors | `CONTRADICTED` | Distribution-metadata shim → `CpuPlatform`; the same suite then runs green | Both failures were the harness's, not the subject's |

### Risks, contradictions, assumptions, unknowns

- **No forward pass was ever run.** Every number above is scheduling and cache accounting.
  That the 16 scheduled tokens actually produce the same output as 512 is vLLM's claim, not
  an observation from this run. Closing it needs a GPU host: run the same prompt twice with
  `--enable-prefix-caching` and compare outputs and TTFT.
- **The harness is not an installed vLLM.** A `dist-info` shim stands in for a real install,
  and `vllm._C` is absent. It is only sound because nothing in `vllm/v1/core/` consults
  `current_platform` (checked, §1) and because vLLM's own suite passes under it. Any claim
  about compiled kernels, attention backends, or memory would not be.
- **`UnspecifiedPlatform` produced 49 convincing errors** that pointed at teardown code in
  vLLM rather than at the harness. The tests themselves had already passed; only reading the
  failure line by line separated the two. A harness defect that surfaces as a library error
  is the failure mode to expect in this setup.
- **`block_size` was chosen, not observed.** Real deployments derive it from the model and
  hardware, and hybrid models use a *different*
  `find_longest_cache_hit` — `SlidingWindowManager` (`single_type_kv_cache_manager.py:486`),
  `MambaManager` (`:785`), `ChunkedLocalAttentionManager` (`:625`) — with their own
  alignment rules. Nothing here applies to them without re-running the probe.
- **Unverified**: KV-connector / disaggregated-prefill paths, where
  `num_external_computed_tokens` adds to the local hit (`scheduler.py:640-642`); eagle
  speculative decoding, which drops one more matched block by design
  (`single_type_kv_cache_manager.py:457-460`); and whether cross-process hash instability
  affects any shipped connector.

### Smallest next verification steps

1. On a GPU host, serve one model with `--enable-prefix-caching`, send the same prompt
   twice, and read `vllm:prefix_cache_queries` / `vllm:prefix_cache_hits` — confirm 496/512
   end to end, and that outputs match the uncached run.
2. Re-run the probe against `make_kv_cache_config_hybrid_model` from vLLM's tests to find
   out whether sliding-window groups pay the same one-block tax.
3. Set `--prefix-caching-hash-algo sha256_cbor` with and without `PYTHONHASHSEED` and check
   whether the warning at `kv_cache_utils.py:97` is the only difference from `sha256`.

### Prediction questions

1. A 500-token prompt at `block_size=16` is re-sent. How many tokens does the scheduler
   run — and why is it 4 rather than the 16 the 512-token case paid?
2. A request arrives whose prompt is identical to a cached one but one token *shorter*.
   What does it hit, and what does that predict about padding prompts to block boundaries?
3. Two of the zeros here look identical in the metric: the 12-token shared prefix (§4) and
   `prompt_logprobs=1` (§7). Which one becomes non-zero at `block_size=1`, and which does
   not?

---

## What the mode changed

The plausible answer to the prompt — "prefix caching only reuses full blocks, so you lose
the partial tail; and your 12-token prefix is shorter than a block" — is half right. It
explains the 0.00 and gets the 0.97 wrong: nothing about the 512-token prompt is partial,
all 32 blocks are full and cached, and the loss is a deliberate reservation rather than a
rounding leftover.

Three constraints changed the output:

- **Ask what can be executed before concluding nothing can.** "No GPU" ruled out the engine,
  not the investigation. The layer that answers this question has no device coupling at all,
  and vLLM's own tests say so by marking themselves `cpu_test`.
- **A manipulation beats an explanation that fits.** The source comment at
  `kv_cache_manager.py:195` already states the reason, and quoting it would have looked like
  evidence. Adding one token (496 → 512) and then removing the cap entirely
  (`AssertionError` at `scheduler.py:681`) is what makes it a cause rather than a plausible
  annotation.
- **Errors from the harness will impersonate errors from the subject.** 49 teardown failures
  and a `Failed to infer device type` both looked like vLLM misbehaving on macOS. Both came
  from a missing `dist-info` directory in the investigator's own venv. Recording that, rather
  than quietly fixing it, is what keeps the 191 passing tests meaningful.
