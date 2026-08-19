# VERIFY — a generated logits processor, 100% covered and wrong three ways

> **Prompt**
>
> Ticket LP-204 asked for a custom vLLM logits processor that bans a token once a request
> has emitted it `max_token_repeats` times. The model produced the processor and a test
> suite; the suite passes. Is it correct? We cannot run a GPU here.

---

## Selection

| | |
|---|---|
| **Mode** | `VERIFY` |
| **Depth** | `audit` |
| **Scope** | `generated_logits_processor.py` against vLLM's `LogitsProcessor` contract |
| **Revision** | `b1388b1fbf5aaef47937fabe98931211684666a6` (tag `v0.19.1`) |
| **Environment** | macOS 26.4.1, arm64, Python 3.12.0, torch 2.10.0, **no CUDA**; vLLM source on `PYTHONPATH` |
| **Artifacts** | [`generated_logits_processor.py`](artifacts/generated_logits_processor.py), [`test_generated_logits_processor.py`](artifacts/test_generated_logits_processor.py), [`verify_logitsprocs.py`](artifacts/verify_logitsprocs.py) |

`VERIFY`, not `TRACE`: the question is whether code satisfies a contract, and the contract
exists independently of the code — which is what makes the checks worth writing.

---

## 1. Anchor the target: which oracles exist

The generated module implements a vLLM extension point, so the oracle is not a matter of
taste. Three independent ones are available at this revision:

| Oracle | Where | What it settles |
|---|---|---|
| The interface contract | `vllm/v1/sample/logits_processor/interface.py` | Method semantics, the meaning of `BatchUpdate`, what `is_argmax_invariant()` promises |
| The extension guide | `docs/features/custom_logitsprocs.md` | The batch-update model the engine guarantees, and the required processing order |
| Shipped implementations | `vllm/v1/sample/logits_processor/builtin.py` | A reference for the same bookkeeping, in `process_dict_updates` (`:555`) |

Two clauses from `interface.py` do most of the work:

```python
# vllm/v1/sample/logits_processor/interface.py:45-54
# Key assumption: the `output_tok_ids` list (which is an element of each
# tuple in `added`) is a reference to the request's running output tokens
# list; via this reference, the logits processors always see the latest
# list of generated output tokens.
#
# NOTE:
# * Added or moved requests may replace existing requests with the same index.
# * Operations should be processed in the following order:
#   - removed, added, moved
```

```python
# vllm/v1/sample/logits_processor/interface.py:85-88
def is_argmax_invariant(self) -> bool:
    """True if logits processor has no impact on the
    argmax computation in greedy sampling."""
```

and one clause from the guide explains why that flag is not cosmetic:

> `is_argmax_invariant()` is evaluated once at startup; if `True`, vLLM will skip applying
> this logits processor in a given step when all requests use greedy sampling

The guide also spells out the batch lifecycle the processor must survive — Adds that reuse
a finished request's index, Removes, then **Unidirectional Moves to condense the batch** and
**Swap Moves to reorder it for the attention backend**.

## 2. The tests pass, at 100% coverage

```console
$ PYTHONPATH=/path/to/vllm ../.venv/bin/python -m pytest test_generated_logits_processor.py -q \
      --cov=generated_logits_processor --cov-report=term-missing

Name                            Stmts   Miss  Cover   Missing
-------------------------------------------------------------
generated_logits_processor.py      34      0   100%
-------------------------------------------------------------
8 passed, 1 warning in 7.17s
```

Eight tests, every statement executed, nothing skipped. The suite covers a request with no
config, a request under the threshold, a request over it, two independent requests, a
removed request, a `None` update, the return value of `apply`, and an out-of-range index.

That list is worth reading twice. It is a reasonable set of *unit* tests and it is entirely
about one engine step with a static batch.

## 3. Frame the checks from the contract, not from the code

[`artifacts/verify_logitsprocs.py`](artifacts/verify_logitsprocs.py) encodes six rules
taken from the two documents above, each check naming the clause it tests:

| Check | Rule |
|---|---|
| C1 | `output_tok_ids` is a live reference — the processor "always sees the latest list of generated output tokens" |
| C2 | Swap Moves reorder the batch; state must follow the request |
| C3 | Condensing after a Remove uses Unidirectional Moves; state must follow the request |
| C4 | `is_argmax_invariant()` is `True` only if `apply` cannot change the argmax |
| C5 | A `None` batch update means no batch change — state survives it |
| C6 | An Add may replace an existing request at the same index |

Every check drives vLLM's own `BatchUpdate` and `MoveDirectionality` types, so the batch
operations are the engine's, not an invented approximation.

A correct implementation of the same feature is checked alongside as a **negative control**.
It differs from the generated one in three lines: it delegates the bookkeeping to vLLM's own
`process_dict_updates`, keeps the `output_tok_ids` reference instead of copying it, and
reports `is_argmax_invariant() -> False`. If the control does not score 6/6, the checks are
wrong and the result means nothing.

## 4. Run them

```console
$ PYTHONPATH=/path/to/vllm ../.venv/bin/python verify_logitsprocs.py

generated_logits_processor.py
-----------------------------
  [FAIL] C1 live output_tok_ids reference       before=[] after=[] (want [] then [5])
  [FAIL] C2 swap move follows the request       row0=[1] row1=[2] (want [2] then [1])
  [FAIL] C3 condense move follows the request   row0=[] row1=[2] (want [3] then [2])
  [FAIL] C4 is_argmax_invariant() is honest     is_argmax_invariant()=True, argmax 7 -> 0
  [PASS] C5 None update preserves state         row0=[4] (want [4])
  [PASS] C6 Add replaces the same index         row0=[] (want [])
  2/6 checks passed

negative control: reference on vLLM's process_dict_updates
----------------------------------------------------------
  [PASS] C1 live output_tok_ids reference       before=[] after=[5] (want [] then [5])
  [PASS] C2 swap move follows the request       row0=[2] row1=[1] (want [2] then [1])
  [PASS] C3 condense move follows the request   row0=[3] row1=[2] (want [3] then [2])
  [PASS] C4 is_argmax_invariant() is honest     is_argmax_invariant()=False, argmax 7 -> 0
  [PASS] C5 None update preserves state         row0=[4] (want [4])
  [PASS] C6 Add replaces the same index         row0=[] (want [])
  6/6 checks passed

control passed: every check is satisfiable by a correct implementation
```

2/6, with the control at 6/6. Three defects, in decreasing subtlety.

## 5. The three defects

### D1 — the feature does nothing for greedy requests, and says so

```python
# generated_logits_processor.py
def is_argmax_invariant(self) -> bool:
    # Repetition guarding only removes tokens the request has already used, so
    # the highest-scoring remaining token is unchanged.
    return True
```

The comment states a claim that C4 falsifies in one step: with token 7 banned and token 7
the argmax, `apply` moves the argmax from 7 to 0. Banning the top token is the *purpose* of
the processor.

The consequence is worse than a wrong annotation. Per the guide, vLLM skips an
argmax-invariant processor entirely when every request in a step uses greedy sampling. So
LP-204's feature silently does nothing in exactly the configuration a developer reaches for
when testing it — `temperature=0` — and works when sampling is on. A bug report of the form
"the repetition guard only works sometimes" would follow, and it would look like a
scheduling flake.

### D2 — the ban never updates after the request is admitted

```python
self.req_info[index] = (int(max_repeats), list(output_tok_ids))
```

`list(...)` snapshots the tokens the request had *when it entered the batch* — for a fresh
request, none. The contract says this list is a live reference maintained by the engine, and
the whole point of the processor is to react to tokens generated later. C1 shows it: after
the engine appends a second `5`, the reference sees `[5]` banned and the generated module
still sees nothing.

The generated tests cannot catch this because every one of them passes a fully-formed token
list at Add time and never advances a step.

### D3 — `moved` is not handled at all

`update_state` processes `removed` and `added` and ignores `batch_update.moved`. Both move
kinds are used by the engine — Swaps to reorder for the attention backend, Unidirectional
Moves to condense after a Remove — and both mis-attribute state:

- **C2 (swap)**: rows 0 and 1 swap, the masks do not. Each request now carries the other's
  ban list.
- **C3 (condense)**: `row0=[]`. The request that moved down into slot 0 lost its guard
  entirely, because its state is still filed under index 2, which is no longer in the batch.

This is the only defect whose *severity* depends on something not observable here: how often
the engine actually emits moves. Condensing happens whenever a request finishes ahead of its
neighbours, which is constant under real traffic; Swap frequency depends on the attention
backend's reordering and is `UNKNOWN` on this machine.

## 6. What D3 does to a request that never opted in

```console
consequence of C2 for a request that never opted in
--------------------------------------------------
  before swap: rowA=[1] rowB=[]
  after swap:  rowA=[] rowB=[1]
  request B now has token 1 banned although it set no max_token_repeats, and
  request A has no guard at all
```

Request B never set `max_token_repeats`. After one reordering it has a token removed from
its distribution because of another request's history. That is a cross-request effect in the
sampling path — the class of bug that shows up as "the model sometimes refuses to say a
word" and is close to unreproducible from a single request.

## 7. Why the tests were never going to catch it

The suite is not lazy; it is *shaped wrong*. Every test:

- calls `update_state` at most twice,
- never appends to an `output_tok_ids` list after the Add,
- never passes a non-empty `moved`,
- and asserts on `apply` output only in the step immediately after the Add.

The contract's difficulty is entirely in the other direction: state that must track a batch
across steps while the engine reorders it underneath. 100% line coverage is reached on the
first step, because there is no separate code path for the fifth — which is exactly why
coverage says nothing here. The three defects live in code that *runs* in every test and is
only wrong later.

---

## Report

### Direct answer

The module does not implement LP-204. At revision `b1388b1f`, driving vLLM's own
`BatchUpdate` types on CPU, it satisfies 2 of 6 contract checks while its own suite passes
8/8 at 100% line coverage.

- It declares itself argmax-invariant while banning the argmax, so vLLM skips it entirely
  for all-greedy batches — the feature is silently absent at `temperature=0`.
- It copies `output_tok_ids` instead of holding the engine's live list, so the ban is
  computed from the tokens the request had at admission and never updates.
- It ignores `batch_update.moved`, so any batch reorder or condense re-points every stored
  ban list at the wrong request, including at requests that never enabled the feature.

The first two are unconditional. The third is unconditional in mechanism; how often the
engine moves requests was not measured here.

### Correctness matrix

| Scenario | Expected | Generated | Status |
|---|---|---|---|
| Single request, threshold reached at admission | token banned | banned | ✅ |
| Request without `max_token_repeats` | untouched | untouched | ✅ |
| `None` batch update | state preserved | preserved | ✅ |
| Add replaces an existing index | state cleared | cleared | ✅ |
| Threshold reached by tokens generated after admission | token banned | **not banned** | ❌ D2 |
| Batch reordered by a Swap | mask follows the request | **mask stays on the row** | ❌ D3 |
| Batch condensed after a Remove | mask follows the request | **guard lost entirely** | ❌ D3 |
| All-greedy batch | processor applied | **processor skipped by vLLM** | ❌ D1 |
| Argmax token banned | argmax changes; `is_argmax_invariant()` must be `False` | returns `True` | ❌ D1 |

### Evidence ledger

| Claim | Status | Anchor | Result / limitation |
|---|---|---|---|
| Generated suite passes at 100% line coverage | `RUNTIME` | `pytest -q --cov=generated_logits_processor` | 8 passed; 34 statements, 0 missed |
| The contract requires `output_tok_ids` to be a live reference | `SOURCE` | `interface.py:45-50` | Stated as a "key assumption" |
| The module copies it | `SOURCE` | `generated_logits_processor.py`, `list(output_tok_ids)` | — |
| …and therefore never updates | `RUNTIME` | C1: `before=[] after=[]` vs control `after=[5]` | Same input, two implementations |
| The contract requires `removed, added, moved` handling | `SOURCE` | `interface.py:53-54`; `docs/features/custom_logitsprocs.md:80` | Order and both move kinds specified |
| `moved` is not handled | `SOURCE` + `RUNTIME` | no reference to `batch_update.moved`; C2 and C3 fail | C3 loses the guard entirely (`row0=[]`) |
| A swap leaks a ban onto a request that never opted in | `RUNTIME` | `verify_logitsprocs.py` consequence section | rowB gains token 1 |
| `is_argmax_invariant()` is `True` but `apply` changes the argmax | `RUNTIME` | C4: argmax 7 → 0 | Directly contradicts the docstring's definition |
| vLLM skips argmax-invariant processors for all-greedy steps | `SOURCE` | `docs/features/custom_logitsprocs.md:39` | Not observed running; no engine step was executed |
| The checks are satisfiable | `RUNTIME` | negative control: 6/6 on a reference using `process_dict_updates` | Rules out checks that no implementation could pass |
| Real-world frequency of Swap moves | `UNKNOWN` | requires a running engine with an attention backend | Determines D3's severity, not its existence |
| End-to-end behavior in a served request | `UNKNOWN` | no CUDA, no vLLM wheel for this platform (see [02](02-trace-prefix-cache-ceiling.md#1-anchor-the-target)) | Everything here is the sampling layer in isolation |

### Risks, assumptions, unknowns

- **Passing tests and full coverage were actively misleading here.** Both were true of a
  module with three defects, and the coverage number is what makes the suite *look*
  thorough. Coverage measures which lines ran, and all three defects are in lines that run.
- **The checks encode my reading of the contract.** They quote `interface.py` and the guide,
  and the negative control shows a correct implementation passes them — but a rule I did not
  extract is a rule not tested. C1–C6 are not the whole contract.
- **No engine step was executed.** The `BatchUpdate` sequences in the checks are constructed
  from the documented model, not captured from a running `InputBatch`. If the engine's real
  sequences differ from the documentation, the checks inherit that error. Capturing real
  sequences needs a GPU host.
- **D1's consequence is `SOURCE`, not `RUNTIME`.** That vLLM skips argmax-invariant
  processors in all-greedy steps is documented and was not observed here.
- **The module is kept broken on purpose.** It is the subject of this example, not a utility
  to reuse.

### Smallest next verification steps

1. Fix the three defects (delegate to `process_dict_updates`, keep the reference, return
   `False`) and re-run `verify_logitsprocs.py` — expect 6/6, which is what the control
   already demonstrates is reachable.
2. On a GPU host, log the `BatchUpdate` sequences a real run produces for ~100 requests and
   replay them through both implementations; that converts D3's severity from `UNKNOWN` to a
   count.
3. Add a step-advancing test to the generated suite — Add, then append a token, then
   `update_state(None)`, then assert — and confirm it fails before the fix. A suite that
   cannot fail on D2 is the finding, not the module.

### Prediction questions

1. The team fixes D2 and D3 but leaves `is_argmax_invariant()` returning `True`. A user
   reports the guard works with `temperature=0.7` and not with `temperature=0`. Which line of
   the guide explains it?
2. C3 produced `row0=[]` — a request with *no* guard — while C2 produced a swapped-but-present
   guard. Why does the condense case lose state outright when the swap case only misplaces it?
3. The suite reaches 100% coverage on the first engine step. What kind of test would have to
   exist for coverage to mean anything about this contract?

---

## What the mode changed

The default review of this module — read it, note it looks reasonable, see 8 passing tests
and 100% coverage — approves it. Everything visible in a single step is correct, and the
generated tests only look at single steps.

Three constraints changed the output:

- **Find the oracle before reading the code.** The extension point has a written contract
  and a shipped reference implementation. Checks written from `interface.py` fail on things
  no amount of staring at `generated_logits_processor.py` flags as suspicious, because the
  code is self-consistent — it is consistent with the wrong model of the engine.
- **Never treat coverage as evidence of correctness.** 100% here is a fact about line
  execution and says nothing about the temporal dimension where every defect lives. The
  suite's shape — one step, static batch — is the actual finding about the tests.
- **Control the checks.** Three of six failing is only meaningful because a correct
  implementation of the same feature passes all six. Without that control, "2/6" is as
  likely to indict the checks as the subject.
