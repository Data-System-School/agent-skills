# ORIENT — where to start reading 554,000 lines of vLLM

> **Prompt**
>
> We are adopting vLLM and need to understand it well enough to debug it and extend it,
> not just run it. It is 1,475 Python files plus a directory of CUDA kernels. Where do I
> start, and how much of it do I actually have to read?

---

## Selection

| | |
|---|---|
| **Mode** | `ORIENT` |
| **Depth** | `working` |
| **Scope** | The serving path for one text-generation request; enough structure to place a bug report |
| **Revision** | `b1388b1fbf5aaef47937fabe98931211684666a6` (tag `v0.19.1`) |
| **Environment** | macOS 26.4.1, arm64, Python 3.12.0, torch 2.10.0, **no CUDA**; vLLM source on `PYTHONPATH` |
| **Artifacts** | [`vllm_repo_map.py`](artifacts/vllm_repo_map.py) |

`ORIENT`, not `TRACE`: there is no single observable to explain yet. The deliverable is a
map with a reading route, and the largest risk is reading the wrong 200,000 lines.

---

## 1. Anchor the target

```console
$ git -C vllm rev-parse HEAD
b1388b1fbf5aaef47937fabe98931211684666a6
$ ls vllm/AGENTS.md vllm/CLAUDE.md
vllm/AGENTS.md  vllm/CLAUDE.md
```

`CLAUDE.md` is one line pointing at `AGENTS.md`. `AGENTS.md` is a contribution policy —
duplicate-work checks, no busywork PRs, a human who can defend every line — plus one rule
that binds any tooling here: *never use system `python3` or bare `pip`; go through `uv`.*
None of the contribution rules apply to a read-only investigation, and no PR is proposed.

This machine cannot run vLLM end to end (no CUDA, no wheel for macOS arm64); the boundary
of what *is* executable is worked out in
[02 — Trace the prefix-cache ceiling](02-trace-prefix-cache-ceiling.md) and reused here.

## 2. Measure before reading

Guessing which directory matters is how orientation goes wrong. Counting is cheap:

```console
$ PYTHONPATH=. ../.venv/bin/python vllm_repo_map.py .

1. where the Python actually is
-------------------------------
  vllm/model_executor/           567 files    266737 lines   48.1%
  vllm/v1/                       236 files     86329 lines   15.6%
  vllm/distributed/               88 files     34191 lines    6.2%
  vllm/entrypoints/              145 files     31992 lines    5.8%
  vllm/transformers_utils/        85 files     18216 lines    3.3%
  vllm/tool_parsers/              37 files     15211 lines    2.7%
  vllm/lora/                      43 files     11970 lines    2.2%
  vllm/benchmarks/                22 files     11585 lines    2.1%
  vllm/compilation/               35 files     10748 lines    1.9%
  vllm/config/                    27 files     10150 lines    1.8%
  vllm/ (all)                   1475 files    554250 lines

  of which vllm/model_executor/models/: 273 files, 171879 lines (31.0% of the package)
                                        — one file per architecture
  csrc/ (CUDA/C++):            220 files
  tests/:                      851 test files
```

Nearly half the package is `model_executor/`, and 31% of the whole package is 273 model
definition files — one per supported architecture, each a `torch.nn.Module` transcription
of a HuggingFace model. Reading them teaches you about Qwen and Llama, not about vLLM.

The engine is `vllm/v1/`: 15.6% of the lines, and the only directory where the words
scheduler, KV cache, worker, and executor all appear. **That reduction — 554k lines to
86k, and in practice to about a dozen files — is most of what orientation is for.**

## 3. The document that exists, and where it points

`docs/design/arch_overview.md` is the in-repo architecture document. It has two sections
about the same thing, written at different times.

The first is current and useful:

> ## V1 Process Architecture
> […] **API Server Process** […] communicates with the engine core process(es) via ZMQ
> sockets. […] **Engine Core Process** […] runs the scheduler, manages KV cache, and
> coordinates model execution across GPU workers. It runs a busy loop […]
> There is **1 engine core process per data parallel rank**.

The second describes a different system:

> ## LLM Engine
> The `LLMEngine` class is the core component of the vLLM engine. […] The `LLMEngine`
> includes input processing, model execution (possibly distributed across multiple hosts
> and/or GPUs), scheduling, and output processing.
> The code for `LLMEngine` can be found in [vllm/engine/llm_engine.py].
> […] The code for `AsyncLLMEngine` can be found in [vllm/engine/async_llm_engine.py].

Both files exist. Following either pointer costs almost nothing, because there is almost
nothing there:

```console
2. does the directory name tell you where the engine is?
--------------------------------------------------------
  vllm/engine/llm_engine.py                    7 lines
  vllm/v1/engine/llm_engine.py               430 lines
  vllm.engine.llm_engine.LLMEngine is vllm.v1.engine.llm_engine.LLMEngine: True
  but vllm/engine/arg_utils.py still holds 2348 lines of live config surface
```

```python
# vllm/engine/llm_engine.py — the whole file
from vllm.v1.engine.llm_engine import LLMEngine as V1LLMEngine

LLMEngine = V1LLMEngine  # type: ignore
```

`vllm/engine/async_llm_engine.py` is the same shape, aliasing
`vllm.v1.engine.async_llm.AsyncLLM`. The identity check is the part worth doing at
runtime rather than by reading: `is` returning `True` proves there is no second
implementation hiding behind the older name.

Nothing on the serving path imports through those aliases. The OpenAI server reaches for
the V1 class directly:

```python
# vllm/entrypoints/openai/api_server.py:126,136
from vllm.v1.engine.async_llm import AsyncLLM
...
async_llm = AsyncLLM.from_vllm_config(...)
```

— while the comments a few lines above it still say "in-process using the AsyncLLMEngine
Directly" (`:117-118`). So the stale naming is in the code as well as the document.

**Directory layout is not the architecture here.** `vllm/engine/` reads like the engine
and is 14 lines of aliases plus the 2,348-line argument parser, which *is* live and *is*
where every CLI flag is defined. Both facts have to be carried; neither is guessable.

## 4. The minimal model

Six components, named by what they own at runtime rather than by directory:

| # | Responsibility | Where | Owns |
|---|---|---|---|
| 1 | **Request intake** — HTTP or Python API, tokenization, multimodal loading | `vllm/entrypoints/` (`llm.py`, `openai/api_server.py`) | Client protocol, input processing |
| 2 | **Engine client** — turns a request into an `EngineCoreRequest` and gets outputs back | `vllm/v1/engine/llm_engine.py`, `async_llm.py`, `core_client.py` | The process boundary (ZMQ), detokenization, output streaming |
| 3 | **Engine core** — the busy loop | `vllm/v1/engine/core.py` (`EngineCore:87`, `EngineCoreProc:778`, `run_busy_loop:1136`) | Step cadence; owns 4 and 5 |
| 4 | **Scheduler** — which requests run this step and for how many tokens | `vllm/v1/core/sched/scheduler.py` (`schedule:348`) | Token budget, preemption, chunked prefill |
| 5 | **KV cache manager** — block allocation and prefix-cache lookup | `vllm/v1/core/kv_cache_manager.py`, `block_pool.py`, `kv_cache_utils.py` | Block hashes, reuse, eviction |
| 6 | **Executor → worker → model runner** — the forward pass | `vllm/v1/executor/abstract.py` (`Executor:36`), `vllm/v1/worker/gpu_worker.py`, `gpu_model_runner.py` | Device placement, batching into tensors, attention backend, CUDA graphs |

The model definitions in `vllm/model_executor/models/` sit *below* 6 and are selected by
registry lookup. They are 31% of the package and 0% of the control flow.

## 5. One vertical slice

Offline generation, from `LLM.generate` to a scheduled forward pass:

```
LLM.generate                              vllm/entrypoints/llm.py:382 (LLMEngine.from_engine_args)
  └─ LLMEngine.add_request                vllm/v1/engine/llm_engine.py:216
      └─ EngineCoreClient                  vllm/v1/engine/llm_engine.py:111 (make_client)
          │                                ── process boundary: ZMQ, in-process for LLM(),
          │                                   separate process for the server ──
          └─ EngineCore.step               vllm/v1/engine/core.py:380
              ├─ Scheduler.schedule        core.py:391  →  sched/scheduler.py:348
              │   └─ KVCacheManager.get_computed_blocks   kv_cache_manager.py:176
              └─ Executor.execute_model    core.py:392  →  executor/abstract.py:199
                  └─ Worker.execute_model  worker/gpu_worker.py:743
                      └─ GPUModelRunner.execute_model     worker/gpu_model_runner.py:3770
                          └─ the registered nn.Module      model_executor/models/<arch>.py
```

Two lines of `EngineCore.step` are the whole engine:

```python
# vllm/v1/engine/core.py:391-392
scheduler_output = self.scheduler.schedule()
future = self.model_executor.execute_model(scheduler_output, non_block=True)
```

Everything above them decides *what* to run; everything below runs it.

## 6. Challenge the model: what the tree does not show

A file listing suggests the system is static. Three numbers say otherwise:

```console
3. how much of vLLM is dispatch you cannot see in the tree
----------------------------------------------------------
  registered model architectures:  323
  resolved platform:               CpuPlatform
  executor implementations:        4 (multiproc_executor, ray_distributed_executor,
                                      ray_executor, uniproc_executor)
  attention backend modules:       20

  `import vllm` took 1.71s
```

323 architectures, 4 executors, 20 attention backends — all chosen at startup from
config, hardware probing, and entry-point plugins. `resolved platform: CpuPlatform` is
this machine's answer; on a CUDA host the same import produces a different platform
class, a different executor, and a different attention backend, and therefore a different
half of the codebase.

These are the skill's *unresolved edges*: reading `gpu_model_runner.py` tells you what
happens if the platform resolved to CUDA, and nothing about whether it did. Any claim of
the form "vLLM does X" needs the config that produced X.

---

## Report

### Direct answer

Read `vllm/v1/`. It is 15.6% of the package and contains the engine: the busy loop
(`v1/engine/core.py`), the scheduler (`v1/core/sched/scheduler.py`), the KV-cache manager
(`v1/core/kv_cache_manager.py`), and the worker/model-runner path (`v1/worker/`). Treat
`vllm/model_executor/models/` — 273 files, 31% of the package — as data rather than
architecture: it is one transcription per supported model, reached by registry lookup.
Ignore `vllm/engine/` except for `arg_utils.py`: its two engine modules are 7-line
aliases into `vllm/v1/`, which `vllm.engine.llm_engine.LLMEngine is
vllm.v1.engine.llm_engine.LLMEngine` returning `True` confirms at runtime.

The in-repo architecture document will send you to those aliases. Its "V1 Process
Architecture" section is accurate; its "LLM Engine" section describes the pre-V1 monolith
and points at files that no longer implement anything.

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| 1,475 Python files, 554,250 lines in `vllm/` | `RUNTIME` | `vllm_repo_map.py` at `b1388b1f` | Counts blank and comment lines |
| `model_executor/` is 48.1%; `models/` alone is 31.0% (273 files) | `RUNTIME` | same | One file per architecture |
| `vllm/v1/` is 15.6% (236 files) and holds scheduler, KV cache, worker | `SOURCE` + `RUNTIME` | same; `vllm/v1/` listing | — |
| `vllm/engine/llm_engine.py` is a 7-line alias | `SOURCE` + `RUNTIME` | file contents; `LLMEngine is V1LLMEngine` → `True` | Same for `async_llm_engine.py` |
| `vllm/engine/arg_utils.py` is still live, 2,348 lines | `SOURCE` | `vllm/entrypoints/llm.py:41` imports `EngineArgs` from it | The one reason to open `vllm/engine/` |
| The OpenAI server uses `vllm.v1.engine.async_llm.AsyncLLM` directly | `SOURCE` | `vllm/entrypoints/openai/api_server.py:126,136` | Its own comments at `:117-118` still say `AsyncLLMEngine` |
| `arch_overview.md` points at the alias files for "the code for `LLMEngine`" | `SOURCE` | `docs/design/arch_overview.md`, "LLM Engine" section | Contradicts its own "V1 Process Architecture" section above it |
| One step = `scheduler.schedule()` then `executor.execute_model()` | `SOURCE` | `vllm/v1/engine/core.py:391-392` | Static reading; no step was executed on this machine |
| 323 registered architectures, 4 executors, 20 attention backends | `RUNTIME` | `vllm_repo_map.py` section 3 | Counted by import and by module listing |
| Which of those is used | `UNKNOWN` | `resolved platform: CpuPlatform` here | Determined at startup by hardware and config; a CUDA host resolves differently |
| Engine core runs in its own process for online serving | `SOURCE` | `EngineCoreProc` (`core.py:778`), ZMQ imports, `docs/design/arch_overview.md` | Not observed running; no server was started |

### Recommended reading route

Twelve files, in causal order, with one reason each:

| # | File | Why |
|---|---|---|
| 1 | `docs/design/arch_overview.md` | Read the "V1 Process Architecture" section only; stop at "LLM Engine" |
| 2 | `vllm/entrypoints/llm.py` | The offline API, and the shortest path from user code to the engine |
| 3 | `vllm/engine/arg_utils.py` | Every CLI flag and its default; the config vocabulary the rest of the code speaks |
| 4 | `vllm/config/cache.py`, `config/model.py` | The two config objects that decide the most downstream behavior |
| 5 | `vllm/v1/engine/llm_engine.py` | Where a request becomes an engine-core request |
| 6 | `vllm/v1/engine/core_client.py` | The process boundary — in-process vs. ZMQ, chosen here |
| 7 | `vllm/v1/engine/core.py` | `step()` at `:380`; the two lines that are the engine |
| 8 | `vllm/v1/core/sched/scheduler.py` | `schedule()`: token budget, chunked prefill, preemption |
| 9 | `vllm/v1/core/kv_cache_manager.py` | Block allocation and prefix-cache lookup — see example 02 |
| 10 | `vllm/v1/worker/gpu_model_runner.py` | Where a `SchedulerOutput` becomes tensors and a forward pass |
| 11 | `vllm/platforms/interface.py` | How the platform, executor, and attention backend get chosen |
| 12 | `vllm/model_executor/models/registry.py` | How an architecture string becomes one of 323 modules |

### Risks, assumptions, unknowns

- **Everything about the device half is unread and unrun here.** Attention backends,
  CUDA graphs, `torch.compile`, and the 220 files in `csrc/` are outside this map. On this
  machine they are unreachable, not merely unexamined.
- **The map is of the text-generation path.** Pooling/embedding models, encoder-decoder
  models, speculative decoding, LoRA, and the KV-connector (disaggregated prefill) paths
  each add components this model does not name.
- **Line counts are a proxy for attention, not for importance.** `vllm/config/` is 1.8% of
  the lines and decides which of the other 98% executes.
- **`arch_overview.md` may be stale in other places too.** Only the two sections quoted
  were checked against the code.

### Smallest next verification steps

1. On a CUDA host, run `vllm_repo_map.py` again and compare `resolved platform` and the
   selected executor — that is the fastest way to see how much of the map is
   config-dependent.
2. `rg -n "class .*Executor\b" vllm/v1/executor/` and read `uniproc_executor.py` first; it
   is the degenerate case and makes `multiproc_executor.py` legible.
3. Start a server with `--api-server-count 2 --data-parallel-size 2` and count processes,
   testing the arch document's process-count table directly.

### Prediction questions

1. A bug report says "vLLM produces garbage for `Qwen3ForCausalLM` but only with tensor
   parallelism". Which two of the six components can you rule out immediately, and why?
2. `vllm/engine/llm_engine.py` is 7 lines. What would have to be true for deleting it to
   break a user, given that nothing on the serving path imports it?
3. The repo map counts 20 attention backend modules but the engine uses one. What single
   command would tell you which — and why can it not be answered from the source alone?

---

## What the mode changed

The default orientation move — open the architecture document, follow its file pointers,
skim the biggest directory — produces a map that is wrong in the two ways that cost the
most time later: it lands on 14 lines of aliases while believing it has found the engine,
and it spends its attention on the 31% of the package that is model transcriptions.

Three constraints changed the output:

- **Count before reading.** "Where do I start" is partly a measurement question, and the
  measurement took one command. It moved the target from 554k lines to 86k and named the
  273 files that are safe to skip.
- **Describe components by runtime responsibility, not by directory.** `vllm/engine/` is
  named for the engine and does not contain it; `vllm/v1/` is named for a version and
  does. Only the responsibility-based model survives that.
- **Treat documents as intent to be reconciled, not as ground truth.** `arch_overview.md`
  is not wrong so much as layered: an accurate V1 section sits above a stale V0 one. The
  `is` check that separated them took one line and is the difference between a map you can
  debug from and one that quietly misleads.
