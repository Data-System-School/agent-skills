# `investigate-codebase` on vLLM

One run against [vLLM](https://github.com/vllm-project/vllm), chosen for a constraint the
DuckDB examples do not have: **the system cannot be run on the investigating machine.**
vLLM is a GPU inference server, ships no wheel for macOS arm64, and there is no CUDA device
here. "Start it and look" is not on the table.

| Example | Mode | Depth | Evidence it rests on |
|---|---|---|---|
| [01 — Trace the prefix-cache ceiling](01-trace-prefix-cache-ceiling.md) | `TRACE` | `working` | vLLM's real `KVCacheManager` and `Scheduler` executed on CPU, a causal manipulation, a negative control, and vLLM's own test suite |

The question is why a re-sent identical prompt reports a ~0.97 prefix-cache hit rate instead
of 1.00, and why a 12-token shared prefix reports 0.00. The answers are different mechanisms
in different places, and one of them is a deliberate reservation rather than a rounding loss.

## Environment used

| | |
|---|---|
| Subject | `vllm-project/vllm` at `b1388b1fbf5aaef47937fabe98931211684666a6` (tag `v0.19.1`) |
| Platform | macOS 26.4.1 (Darwin 25.4.0), arm64 |
| Python | 3.12.0, `uv` 0.11.26 |
| torch | 2.10.0 — `torch.cuda.is_available()` is `False` |
| vLLM | **not installed** — the source tree is on `PYTHONPATH`; no `vllm._C`, no compiled kernels |

vLLM's `AGENTS.md` requires `uv` rather than bare `pip`, so `uv` is what the commands below
use.

## Reproduction

```bash
git clone --filter=blob:none --no-checkout https://github.com/vllm-project/vllm.git
git -C vllm checkout v0.19.1

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "torch==2.10.0"
uv pip install --python .venv/bin/python -r vllm/requirements/common.txt
uv pip install --python .venv/bin/python pytest tblib          # for vLLM's own test suite
```

vLLM's platform detection reads installed distribution metadata, which a source tree on
`PYTHONPATH` does not have; without it the platform resolves to `UnspecifiedPlatform` and
both the scheduler and vLLM's test teardown fail in ways that look like library bugs. The
example works through that failure in §3; the minimal fix is:

```bash
SP=$(.venv/bin/python -c "import site; print(site.getsitepackages()[0])")
mkdir -p "$SP/vllm-0.19.1.dist-info"
printf 'Metadata-Version: 2.1\nName: vllm\nVersion: 0.19.1\n' > "$SP/vllm-0.19.1.dist-info/METADATA"
```

Then, from the vLLM checkout root:

```bash
PYTHONPATH=. ../.venv/bin/python /path/to/artifacts/vllm_prefix_cache_probe.py
PYTHONPATH=. ../.venv/bin/python /path/to/artifacts/vllm_scheduler_probe.py

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

No forward pass was run, on any device. Every number in the example is scheduling and cache
accounting from the real classes; none of it observes a GPU, an attention kernel, or a
generated token. The example marks that boundary explicitly rather than inferring across it.

## Runnable artifacts

[`artifacts/`](artifacts/) holds the two probes the example executes.
