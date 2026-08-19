#!/usr/bin/env python3
"""Drive vLLM's real V1 `Scheduler` on CPU to see how many tokens a cached prompt costs.

This is the end of the vertical slice that `vllm_prefix_cache_probe.py` starts: the
KV-cache manager reports a block-aligned hit, and the scheduler turns that into the
number of tokens the model is actually asked to run.

No GPU and no model weights are involved. `create_scheduler` / `create_requests` are
vLLM's own test helpers, so the scheduler under test is the real one. Constructing
`ModelConfig` reads `facebook/opt-125m`'s config from the HuggingFace cache or network.

Usage:
    PYTHONPATH=/path/to/vllm python vllm_scheduler_probe.py

Requires vLLM's `tests/` package importable (run with the source tree root on
PYTHONPATH) and a resolvable `current_platform` — see the example's environment notes.

Anchored to vllm-project/vllm b1388b1fbf5aaef47937fabe98931211684666a6 (tag v0.19.1).
"""

import sys

from tests.v1.core.utils import create_requests, create_scheduler

from vllm.v1.request import RequestStatus

BLOCK_SIZE = 16
PROMPT_LEN = 512


def run(enable_prefix_caching: bool) -> dict[str, int]:
    scheduler = create_scheduler(
        enable_prefix_caching=enable_prefix_caching,
        block_size=BLOCK_SIZE,
        max_num_batched_tokens=8192,
    )
    r0, r1 = create_requests(
        2, num_tokens=PROMPT_LEN, same_prompt=True, block_size=BLOCK_SIZE
    )

    scheduler.add_request(r0)
    first = scheduler.schedule()
    first_tokens = first.num_scheduled_tokens[r0.request_id]

    # Full blocks are hashed and cached at allocation time, so the cache is warm
    # once the first request has been scheduled; no model output is needed.
    scheduler.finish_requests(r0.request_id, RequestStatus.FINISHED_ABORTED)

    scheduler.add_request(r1)
    second = scheduler.schedule()
    second_tokens = second.num_scheduled_tokens[r1.request_id]

    stats = scheduler.kv_cache_manager.prefix_cache_stats
    return {
        "first": first_tokens,
        "second": second_tokens,
        "queries": stats.queries if stats else -1,
        "hits": stats.hits if stats else -1,
    }


def run_without_the_minus_one() -> str:
    """Manipulation: give back the one token `get_computed_blocks` deliberately withholds.

    `KVCacheManager.get_computed_blocks` caps the lookup at `request.num_tokens - 1`.
    Rather than re-implementing it, this adds the 1 back at the coordinator boundary,
    which is the narrowest place to undo exactly that subtraction.
    """
    from vllm.v1.core.kv_cache_coordinator import UnitaryKVCacheCoordinator

    original = UnitaryKVCacheCoordinator.find_longest_cache_hit

    def patched(self, block_hashes, max_cache_hit_length):
        return original(self, block_hashes, max_cache_hit_length + 1)

    UnitaryKVCacheCoordinator.find_longest_cache_hit = patched
    try:
        result = run(enable_prefix_caching=True)
        return f"no error; req 2 scheduled {result['second']} tokens"
    except AssertionError as exc:
        tb = exc.__traceback__
        while tb.tb_next is not None:
            tb = tb.tb_next
        frame = tb.tb_frame
        where = f"{'vllm/' + frame.f_code.co_filename.split('/vllm/vllm/')[-1]}:{tb.tb_lineno}"
        return f"AssertionError at {where}"
    finally:
        UnitaryKVCacheCoordinator.find_longest_cache_hit = original


def main() -> int:
    print(f"prompt = {PROMPT_LEN} tokens, block_size = {BLOCK_SIZE}, same prompt twice\n")
    header = f"  {'enable_prefix_caching':<24} {'req 1 tokens':>13} {'req 2 tokens':>13} {'queries':>9} {'hits':>7}"
    print(header)
    for apc in (False, True):
        r = run(apc)
        print(
            f"  {str(apc):<24} {r['first']:>13} {r['second']:>13} "
            f"{r['queries']:>9} {r['hits']:>7}"
        )
    print(f"\n  manipulation: cache lookup capped at num_tokens instead of num_tokens - 1")
    print(f"    -> {run_without_the_minus_one()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
