#!/usr/bin/env python3
"""Tests generated alongside `generated_logits_processor.py`. All of them pass.

Kept exactly as generated. They are evidence about the tests, not about the module —
see 04-verify-generated-logitsproc.md.

    PYTHONPATH=/path/to/vllm python -m pytest -q \
        --cov=generated_logits_processor --cov-report=term-missing
"""

import torch

from vllm.sampling_params import SamplingParams
from vllm.v1.sample.logits_processor.interface import BatchUpdate

from generated_logits_processor import RepetitionGuardLogitsProcessor

VOCAB = 8


def make_params(max_token_repeats=None):
    extra_args = (
        {"max_token_repeats": max_token_repeats} if max_token_repeats is not None else None
    )
    return SamplingParams(max_tokens=16, extra_args=extra_args)


def make_proc():
    return RepetitionGuardLogitsProcessor(
        vllm_config=None, device=torch.device("cpu"), is_pin_memory=False
    )


def add(index, params, output_tok_ids):
    return BatchUpdate(
        batch_size=index + 1,
        removed=[],
        added=[(index, params, None, output_tok_ids)],
        moved=[],
    )


def test_no_config_means_no_masking():
    proc = make_proc()
    proc.update_state(add(0, make_params(), [3, 3, 3]))
    logits = torch.zeros(1, VOCAB)
    out = proc.apply(logits)
    assert torch.isfinite(out).all()


def test_token_banned_after_threshold():
    proc = make_proc()
    proc.update_state(add(0, make_params(max_token_repeats=2), [5, 5]))
    out = proc.apply(torch.zeros(1, VOCAB))
    assert out[0, 5] == float("-inf")
    assert torch.isfinite(out[0, [0, 1, 2, 3, 4, 6, 7]]).all()


def test_token_below_threshold_is_kept():
    proc = make_proc()
    proc.update_state(add(0, make_params(max_token_repeats=3), [5, 5]))
    out = proc.apply(torch.zeros(1, VOCAB))
    assert torch.isfinite(out).all()


def test_two_requests_are_independent():
    proc = make_proc()
    proc.update_state(
        BatchUpdate(
            batch_size=2,
            removed=[],
            added=[
                (0, make_params(max_token_repeats=1), None, [1]),
                (1, make_params(max_token_repeats=1), None, [2]),
            ],
            moved=[],
        )
    )
    out = proc.apply(torch.zeros(2, VOCAB))
    assert out[0, 1] == float("-inf")
    assert torch.isfinite(out[0, 2])
    assert out[1, 2] == float("-inf")
    assert torch.isfinite(out[1, 1])


def test_removed_request_stops_being_masked():
    proc = make_proc()
    proc.update_state(add(0, make_params(max_token_repeats=1), [4]))
    proc.update_state(BatchUpdate(batch_size=0, removed=[0], added=[], moved=[]))
    out = proc.apply(torch.zeros(1, VOCAB))
    assert torch.isfinite(out).all()


def test_none_batch_update_is_safe():
    proc = make_proc()
    proc.update_state(add(0, make_params(max_token_repeats=1), [4]))
    proc.update_state(None)
    out = proc.apply(torch.zeros(1, VOCAB))
    assert out[0, 4] == float("-inf")


def test_apply_returns_tensor_and_is_argmax_invariant_flag_set():
    proc = make_proc()
    logits = torch.zeros(1, VOCAB)
    assert proc.apply(logits) is logits
    assert proc.is_argmax_invariant() is True


def test_index_beyond_batch_is_ignored():
    proc = make_proc()
    proc.update_state(add(3, make_params(max_token_repeats=1), [4]))
    out = proc.apply(torch.zeros(1, VOCAB))
    assert torch.isfinite(out).all()
