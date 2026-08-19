# Artifacts

The two probes [example 01](../01-trace-prefix-cache-ceiling.md) executes. Both drive
vLLM's *own* classes from a source checkout on `PYTHONPATH` — no vLLM logic is
reimplemented here, and neither needs a GPU or model weights.

Setup is in the [folder README](../README.md#reproduction). Run both from the vLLM checkout
root so that `PYTHONPATH=.` makes `vllm` and `tests` importable.

## `vllm_prefix_cache_probe.py`

Asks the real `KVCacheManager` how much of a request it considers already computed, across
seven cases: an exact repeat, sub-block shared prefixes, `prompt_logprobs` and `cache_salt`,
a cap manipulation, a `block_size` sweep, a negative control, and block-hash stability.

```bash
PYTHONPATH=. ../.venv/bin/python vllm_prefix_cache_probe.py
```

The request and KV-cache-config constructors are copied from
`tests/v1/core/test_prefix_caching.py` at the same revision; everything they build is
vLLM's.

## `vllm_scheduler_probe.py`

Drives the real V1 `Scheduler` through the same scenario and reports the number of tokens
each request is scheduled for — 512 then 16 with prefix caching on, 512 then 512 with it
off.

```bash
PYTHONPATH=. ../.venv/bin/python vllm_scheduler_probe.py
```

It then repeats the run with `find_longest_cache_hit` wrapped so the cache lookup is capped
one token higher, undoing exactly the `- 1` in `KVCacheManager.get_computed_blocks`. That
run is expected to fail: it prints the `AssertionError` location rather than a hit count,
which is the point of the check. Nothing in the vLLM checkout is modified — the wrapper is
installed and removed inside the process.

Constructing `ModelConfig` reads `facebook/opt-125m`'s config from the HuggingFace cache or
network on first run.
