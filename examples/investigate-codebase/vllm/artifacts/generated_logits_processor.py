#!/usr/bin/env python3
"""AI-generated custom logits processor for vLLM V1 — the module under verification.

Task it was generated from (ticket LP-204):

    Add a custom logits processor that stops a request from repeating itself: once a
    token id has already been emitted `max_token_repeats` times in that request's
    output, ban it for the rest of the request. Requests opt in per request via
    `SamplingParams.extra_args["max_token_repeats"]`; requests that do not set it are
    unaffected. Follow vLLM's custom logits processor interface.

This file is kept as generated. It is the subject of the example, not a utility to
reuse — see 04-verify-generated-logitsproc.md for what is wrong with it.
"""

import torch

from vllm.v1.sample.logits_processor.interface import BatchUpdate, LogitsProcessor


class RepetitionGuardLogitsProcessor(LogitsProcessor):
    """Ban token ids that a request has already emitted `max_token_repeats` times."""

    def __init__(self, vllm_config, device: torch.device, is_pin_memory: bool) -> None:
        self.device = device
        self.is_pin_memory = is_pin_memory
        # batch index -> (max_repeats, output token ids)
        self.req_info: dict[int, tuple[int, list[int]]] = {}

    def is_argmax_invariant(self) -> bool:
        # Repetition guarding only removes tokens the request has already used, so
        # the highest-scoring remaining token is unchanged.
        return True

    def update_state(self, batch_update: BatchUpdate | None) -> None:
        if batch_update is None:
            return

        # Drop requests that left the batch.
        for index in batch_update.removed:
            self.req_info.pop(index, None)

        # Register requests that joined the batch.
        for index, params, _prompt_tok_ids, output_tok_ids in batch_update.added:
            extra_args = params.extra_args or {}
            max_repeats = extra_args.get("max_token_repeats")
            if max_repeats is None:
                self.req_info.pop(index, None)
                continue
            self.req_info[index] = (int(max_repeats), list(output_tok_ids))

    def apply(self, logits: torch.Tensor) -> torch.Tensor:
        if not self.req_info:
            return logits

        for index, (max_repeats, output_tok_ids) in self.req_info.items():
            if index >= logits.shape[0]:
                continue
            counts: dict[int, int] = {}
            for tok in output_tok_ids:
                counts[tok] = counts.get(tok, 0) + 1
            banned = [tok for tok, n in counts.items() if n >= max_repeats]
            if banned:
                logits[index, banned] = float("-inf")
        return logits
