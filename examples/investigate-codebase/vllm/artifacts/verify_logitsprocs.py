#!/usr/bin/env python3
"""Independent checks for a custom vLLM logits processor, written from the contract.

The checks come from `vllm/v1/sample/logits_processor/interface.py` and
`docs/features/custom_logitsprocs.md` at the pinned revision — not from reading
`generated_logits_processor.py`. Each one states the rule it tests.

A correctly-implemented reference is checked too, as a negative control: if the
reference does not score 6/6 the checks are wrong, not the subject.

    PYTHONPATH=/path/to/vllm python verify_logitsprocs.py

Exits non-zero if the generated module fails any check.

Anchored to vllm-project/vllm b1388b1fbf5aaef47937fabe98931211684666a6 (tag v0.19.1).
"""

import torch

from vllm.sampling_params import SamplingParams
from vllm.v1.sample.logits_processor.builtin import process_dict_updates
from vllm.v1.sample.logits_processor.interface import (
    BatchUpdate,
    LogitsProcessor,
    MoveDirectionality,
)

from generated_logits_processor import RepetitionGuardLogitsProcessor

VOCAB = 8
BANNED = float("-inf")


class ReferenceRepetitionGuard(LogitsProcessor):
    """Same feature, implemented on vLLM's own `process_dict_updates` helper.

    This exists only as the negative control for the checks below.
    """

    def __init__(self, vllm_config, device, is_pin_memory) -> None:
        self.req_info: dict[int, tuple[int, list[int]]] = {}

    @staticmethod
    def _new_state(params, _prompt_tok_ids, output_tok_ids):
        extra_args = params.extra_args or {}
        max_repeats = extra_args.get("max_token_repeats")
        if max_repeats is None:
            return None
        # Keep the reference, not a copy: the contract says this list is live.
        return int(max_repeats), output_tok_ids

    def is_argmax_invariant(self) -> bool:
        return False

    def update_state(self, batch_update: BatchUpdate | None) -> None:
        process_dict_updates(self.req_info, batch_update, self._new_state)

    def apply(self, logits: torch.Tensor) -> torch.Tensor:
        for index, (max_repeats, output_tok_ids) in self.req_info.items():
            if index >= logits.shape[0]:
                continue
            counts: dict[int, int] = {}
            for tok in output_tok_ids:
                counts[tok] = counts.get(tok, 0) + 1
            banned = [tok for tok, n in counts.items() if n >= max_repeats]
            if banned:
                logits[index, banned] = BANNED
        return logits


def params(max_token_repeats=None, **kw):
    extra = {"max_token_repeats": max_token_repeats} if max_token_repeats else None
    return SamplingParams(max_tokens=16, extra_args=extra, **kw)


def masked(proc, batch_size: int) -> list[set[int]]:
    """Which token ids each batch row has banned."""
    out = proc.apply(torch.zeros(batch_size, VOCAB))
    return [{t for t in range(VOCAB) if out[i, t] == BANNED} for i in range(batch_size)]


# --- checks -----------------------------------------------------------------
# Each returns (ok, detail). The rule each one encodes is in its docstring.


def c1_live_output_reference(make):
    """interface.py: `output_tok_ids` in an Add "is a reference to the request's
    running output tokens list; via this reference, the logits processors always
    see the latest list of generated output tokens"."""
    proc = make()
    output: list[int] = [5]
    proc.update_state(
        BatchUpdate(batch_size=1, removed=[], added=[(0, params(2), None, output)], moved=[])
    )
    before = masked(proc, 1)[0]
    output.append(5)  # the engine appends the next generated token in place
    proc.update_state(None)  # no batch change this step
    after = masked(proc, 1)[0]
    ok = before == set() and after == {5}
    return ok, f"before={sorted(before)} after={sorted(after)} (want [] then [5])"


def c2_swap_move(make):
    """custom_logitsprocs.md: reordering applies Swap Moves; state must follow the
    request, so a swap of rows 0 and 1 must swap which row is masked."""
    proc = make()
    proc.update_state(
        BatchUpdate(
            batch_size=2,
            removed=[],
            added=[(0, params(1), None, [1]), (1, params(1), None, [2])],
            moved=[],
        )
    )
    proc.update_state(
        BatchUpdate(
            batch_size=2, removed=[], added=[], moved=[(0, 1, MoveDirectionality.SWAP)]
        )
    )
    got = masked(proc, 2)
    ok = got == [{2}, {1}]
    return ok, f"row0={sorted(got[0])} row1={sorted(got[1])} (want [2] then [1])"


def c3_condense_move(make):
    """custom_logitsprocs.md: after a Remove the batch is condensed with
    Unidirectional Moves from the highest non-empty slot into the empty slot."""
    proc = make()
    proc.update_state(
        BatchUpdate(
            batch_size=3,
            removed=[],
            added=[
                (0, params(1), None, [1]),
                (1, params(1), None, [2]),
                (2, params(1), None, [3]),
            ],
            moved=[],
        )
    )
    # Request at index 0 finishes; index 2 moves down to fill the hole.
    proc.update_state(
        BatchUpdate(
            batch_size=2,
            removed=[0],
            added=[],
            moved=[(2, 0, MoveDirectionality.UNIDIRECTIONAL)],
        )
    )
    got = masked(proc, 2)
    ok = got == [{3}, {2}]
    return ok, f"row0={sorted(got[0])} row1={sorted(got[1])} (want [3] then [2])"


def c4_argmax_invariance_is_honest(make):
    """interface.py: `is_argmax_invariant()` is True only if the processor "has no
    impact on the argmax computation in greedy sampling"; vLLM skips the processor
    entirely for all-greedy batches when it is True."""
    proc = make()
    proc.update_state(
        BatchUpdate(batch_size=1, removed=[], added=[(0, params(1), None, [7])], moved=[])
    )
    logits = torch.zeros(1, VOCAB)
    logits[0, 7] = 10.0  # token 7 is the argmax, and is also the banned token
    before = int(torch.argmax(logits[0]))
    after = int(torch.argmax(proc.apply(logits)[0]))
    claims_invariant = proc.is_argmax_invariant()
    ok = not (claims_invariant and before != after)
    return ok, (
        f"is_argmax_invariant()={claims_invariant}, argmax {before} -> {after}"
    )


def c5_none_update_preserves_state(make):
    """custom_logitsprocs.md: a `None` batch update means no batch change — state
    must survive it."""
    proc = make()
    proc.update_state(
        BatchUpdate(batch_size=1, removed=[], added=[(0, params(1), None, [4])], moved=[])
    )
    proc.update_state(None)
    got = masked(proc, 1)[0]
    return got == {4}, f"row0={sorted(got)} (want [4])"


def c6_add_replaces_existing_index(make):
    """interface.py: "Added or moved requests may replace existing requests with the
    same index" — an Add of an unconfigured request must clear that index."""
    proc = make()
    proc.update_state(
        BatchUpdate(batch_size=1, removed=[], added=[(0, params(1), None, [4])], moved=[])
    )
    proc.update_state(
        BatchUpdate(batch_size=1, removed=[], added=[(0, params(), None, [4, 4])], moved=[])
    )
    got = masked(proc, 1)[0]
    return got == set(), f"row0={sorted(got)} (want [])"


CHECKS = [
    ("C1 live output_tok_ids reference", c1_live_output_reference),
    ("C2 swap move follows the request", c2_swap_move),
    ("C3 condense move follows the request", c3_condense_move),
    ("C4 is_argmax_invariant() is honest", c4_argmax_invariance_is_honest),
    ("C5 None update preserves state", c5_none_update_preserves_state),
    ("C6 Add replaces the same index", c6_add_replaces_existing_index),
]


def run(label: str, cls) -> int:
    def make():
        return cls(vllm_config=None, device=torch.device("cpu"), is_pin_memory=False)

    print(f"\n{label}")
    print("-" * len(label))
    passed = 0
    for name, check in CHECKS:
        try:
            ok, detail = check(make)
        except Exception as exc:  # a crash is a failure, not an error to hide
            ok, detail = False, f"raised {type(exc).__name__}: {exc}"
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<38} {detail}")
    print(f"  {passed}/{len(CHECKS)} checks passed")
    return passed


def consequence() -> None:
    """What a failing C2 does to a request that never opted in."""
    print("\nconsequence of C2 for a request that never opted in")
    print("-" * 50)
    proc = RepetitionGuardLogitsProcessor(
        vllm_config=None, device=torch.device("cpu"), is_pin_memory=False
    )
    proc.update_state(
        BatchUpdate(
            batch_size=2,
            removed=[],
            added=[
                (0, params(1), None, [1, 1, 1]),  # request A opted in
                (1, params(), None, [2, 2, 2]),  # request B did not
            ],
            moved=[],
        )
    )
    print(f"  before swap: rowA={sorted(masked(proc, 2)[0])} rowB={sorted(masked(proc, 2)[1])}")
    proc.update_state(
        BatchUpdate(
            batch_size=2, removed=[], added=[], moved=[(0, 1, MoveDirectionality.SWAP)]
        )
    )
    got = masked(proc, 2)
    print(f"  after swap:  rowA={sorted(got[1])} rowB={sorted(got[0])}")
    print(
        "  request B now has token 1 banned although it set no max_token_repeats, "
        "and request A has no guard at all"
    )


def main() -> int:
    generated = run("generated_logits_processor.py", RepetitionGuardLogitsProcessor)
    reference = run(
        "negative control: reference on vLLM's process_dict_updates",
        ReferenceRepetitionGuard,
    )
    consequence()
    if reference != len(CHECKS):
        print("\ncontrol failed: the checks are wrong, not the subject")
        return 2
    print("\ncontrol passed: every check is satisfiable by a correct implementation")
    return 0 if generated == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
