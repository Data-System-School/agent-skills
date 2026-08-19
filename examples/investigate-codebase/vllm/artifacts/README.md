# Artifacts

The files the [vLLM examples](../) execute. Everything here drives vLLM's *own* classes
from a source checkout on `PYTHONPATH` — no vLLM logic is reimplemented — and nothing needs
a GPU or model weights.

Setup is in the [folder README](../README.md#reproduction). Run from the vLLM checkout root
(so `PYTHONPATH=.` makes `vllm` and `tests` importable), except where noted.

| File | Used by | What it is |
|---|---|---|
| `vllm_repo_map.py` | [01](../01-orient-vllm-source.md) | Measures the package by subpackage, resolves the `LLMEngine` alias at runtime, counts the dispatch surface |
| `vllm_prefix_cache_probe.py` | [02](../02-trace-prefix-cache-ceiling.md) | Seven cases against the real `KVCacheManager`: exact repeat, sub-block prefixes, `prompt_logprobs`/`cache_salt`, a cap manipulation, a `block_size` sweep, a negative control, hash stability |
| `vllm_scheduler_probe.py` | [02](../02-trace-prefix-cache-ceiling.md) | Drives the real V1 `Scheduler`; then repeats the run with the cache-lookup cap raised by one, which is expected to fail |
| `mm_hash_key_differential.py` | [03](../03-impact-pr-36708.md) | Base/head differential over 13 multimodal request shapes: extra keys, block hashes, cross-shape collisions |
| `generated_logits_processor.py` | [04](../04-verify-generated-logitsproc.md) | The AI-generated module under verification. Kept broken on purpose |
| `test_generated_logits_processor.py` | [04](../04-verify-generated-logitsproc.md) | The tests generated alongside it: 8 pass at 100% line coverage and detect none of the defects |
| `verify_logitsprocs.py` | [04](../04-verify-generated-logitsproc.md) | Six checks written from vLLM's `LogitsProcessor` contract, plus a correct reference as negative control |

## Notes on running them

```bash
# 01
PYTHONPATH=. ../.venv/bin/python vllm_repo_map.py .

# 02
PYTHONPATH=. ../.venv/bin/python vllm_prefix_cache_probe.py
PYTHONPATH=. ../.venv/bin/python vllm_scheduler_probe.py
```

`vllm_scheduler_probe.py` installs a wrapper around `find_longest_cache_hit` for its last
section and removes it again in a `finally`; nothing in the vLLM checkout is modified. That
run is *expected* to raise — it prints the `AssertionError` location instead of a hit count,
which is the point of the check.

```bash
# 03 — PYTHONHASHSEED is required, not optional
PYTHONHASHSEED=0 PYTHONPATH=../vllm-base ../.venv/bin/python mm_hash_key_differential.py probe base.json
PYTHONHASHSEED=0 PYTHONPATH=../vllm-head ../.venv/bin/python mm_hash_key_differential.py probe head.json
../.venv/bin/python mm_hash_key_differential.py compare base.json head.json
```

Without `PYTHONHASHSEED`, `init_none_hash` seeds the block-hash chain from `os.urandom` and
the two dumps are not comparable. `compare` exits non-zero if a text-only block hash
changed — the invariant the PR must not break.

```bash
# 04 — run from this directory
PYTHONPATH=/path/to/vllm ../.venv/bin/python -m pytest test_generated_logits_processor.py -q \
    --cov=generated_logits_processor --cov-report=term-missing
# 8 passed, 34 statements, 100%

PYTHONPATH=/path/to/vllm ../.venv/bin/python verify_logitsprocs.py
# generated: 2/6, control: 6/6  -- exits 1
```

`generated_logits_processor.py` is kept broken on purpose. It is the subject of example 04,
not a utility to reuse; the reference implementation inside `verify_logitsprocs.py` is the
one that satisfies the contract.
