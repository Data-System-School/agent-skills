# `investigate-codebase` on vLLM

Four runs against [vLLM](https://github.com/vllm-project/vllm), one per mode, chosen for a
constraint the DuckDB examples do not have: **the system cannot be run on the investigating
machine.** vLLM is a GPU inference server, ships no wheel for macOS arm64, and there is no
CUDA device here. "Start it and look" is not on the table for any of the four.

| Example | Mode | Depth | Evidence it rests on |
|---|---|---|---|
| [01 — Where to start reading vLLM](01-orient-vllm-source.md) | `ORIENT` | `working` | Measured repo shape, a runtime identity check, the in-repo architecture doc |
| [02 — Trace the prefix-cache ceiling](02-trace-prefix-cache-ceiling.md) | `TRACE` | `working` | vLLM's real `KVCacheManager` and `Scheduler` on CPU, a causal manipulation, a negative control |
| [03 — Impact of PR #36708](03-impact-pr-36708.md) | `IMPACT` | `audit` | Resolved base/head worktrees, a 13-shape hash differential, head's tests against base's code |
| [04 — Verify a generated logits processor](04-verify-generated-logitsproc.md) | `VERIFY` | `audit` | Contract-derived checks on vLLM's own `BatchUpdate` types, plus a negative control |

02 and 04 are the ones where the confident answer is wrong. 01 is the one that decides how
much of a 554,000-line package you have to read; 03 is the one where a three-line diff
turns out to have an upgrade plan attached.

## Environment used

| | |
|---|---|
| Subject | `vllm-project/vllm` at `b1388b1fbf5aaef47937fabe98931211684666a6` (tag `v0.19.1`) |
| Platform | macOS 26.4.1 (Darwin 25.4.0), arm64 |
| Python | 3.12.0, `uv` 0.11.26 |
| torch | 2.10.0 — `torch.cuda.is_available()` is `False` |
| vLLM | **not installed** — the source tree is on `PYTHONPATH`; no `vllm._C`, no compiled kernels |

Example 03 additionally uses two `git worktree` checkouts, at the PR's base and head.

vLLM's `AGENTS.md` requires `uv` rather than bare `pip`, so `uv` is what the commands below
use.

## Reproduction

```bash
git clone --filter=blob:none --no-checkout https://github.com/vllm-project/vllm.git
git -C vllm checkout v0.19.1

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "torch==2.10.0"
uv pip install --python .venv/bin/python -r vllm/requirements/common.txt
uv pip install --python .venv/bin/python pytest pytest-cov tblib   # for the test suites
```

vLLM's platform detection reads installed distribution metadata, which a source tree on
`PYTHONPATH` does not have; without it the platform resolves to `UnspecifiedPlatform` and
both the scheduler and vLLM's test teardown fail in ways that look like library bugs.
Example 02 §3 works through that failure; the minimal fix is:

```bash
SP=$(.venv/bin/python -c "import site; print(site.getsitepackages()[0])")
mkdir -p "$SP/vllm-0.19.1.dist-info"
printf 'Metadata-Version: 2.1\nName: vllm\nVersion: 0.19.1\n' > "$SP/vllm-0.19.1.dist-info/METADATA"
```

Then, from the vLLM checkout root:

```bash
A=/path/to/artifacts

# 01 ORIENT
PYTHONPATH=. ../.venv/bin/python $A/vllm_repo_map.py .

# 02 TRACE
PYTHONPATH=. ../.venv/bin/python $A/vllm_prefix_cache_probe.py
PYTHONPATH=. ../.venv/bin/python $A/vllm_scheduler_probe.py

# 03 IMPACT — needs the two extra worktrees
git worktree add --detach ../vllm-base 269bf46d9^
git worktree add --detach ../vllm-head 269bf46d9
PYTHONHASHSEED=0 PYTHONPATH=../vllm-base ../.venv/bin/python $A/mm_hash_key_differential.py probe base.json
PYTHONHASHSEED=0 PYTHONPATH=../vllm-head ../.venv/bin/python $A/mm_hash_key_differential.py probe head.json
../.venv/bin/python $A/mm_hash_key_differential.py compare base.json head.json

# 04 VERIFY — run from the artifacts directory
cd $A
PYTHONPATH=/path/to/vllm ../.venv/bin/python -m pytest test_generated_logits_processor.py -q \
    --cov=generated_logits_processor --cov-report=term-missing   # 8 passed, 100%
PYTHONPATH=/path/to/vllm ../.venv/bin/python verify_logitsprocs.py   # 2/6 checks pass, exits 1

# vLLM's own CPU-runnable V1 core suite
PYTHONPATH=. ../.venv/bin/python -m pytest \
  tests/v1/core/test_prefix_caching.py \
  tests/v1/core/test_kv_cache_utils.py \
  tests/v1/core/test_scheduler.py -q
# 191 passed, 1 skipped in 134.35s
```

`vllm_scheduler_probe.py` builds a `ModelConfig` for `facebook/opt-125m`, so its first run
reads that model's config from HuggingFace (config and tokenizer only — no weights).

## What stays unknown

No forward pass was run, on any device, in any of the four examples. Every number is
structure, scheduling, cache accounting, or sampling-layer state from the real classes;
none of it observes a GPU, an attention kernel, or a generated token. Each example marks
that boundary explicitly rather than inferring across it.

## Runnable artifacts

[`artifacts/`](artifacts/) holds the files the examples execute.
