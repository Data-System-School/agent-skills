#!/usr/bin/env python3
"""Probe vLLM V1 prefix-cache hit accounting without a GPU, a model, or vLLM installed.

Everything below drives vLLM's *own* classes (`KVCacheManager`, `Request`, the block
hasher) taken from a source checkout on `PYTHONPATH`. No vLLM logic is re-implemented
here; only the harness (`make_request`, `make_kv_cache_config`) is local, and it is
copied from `tests/v1/core/test_prefix_caching.py` at the same revision.

Usage:
    PYTHONPATH=/path/to/vllm python vllm_prefix_cache_probe.py

Anchored to vllm-project/vllm b1388b1fbf5aaef47937fabe98931211684666a6 (tag v0.19.1).
"""

import os
import sys

import torch

from vllm.sampling_params import SamplingParams
from vllm.utils.hashing import sha256
from vllm.v1.core.kv_cache_manager import KVCacheManager
from vllm.v1.core.kv_cache_utils import get_request_block_hasher, init_none_hash
from vllm.v1.kv_cache_interface import (
    FullAttentionSpec,
    KVCacheConfig,
    KVCacheGroupSpec,
)
from vllm.v1.request import Request

HASH_FN = sha256


def make_request(
    request_id: str,
    prompt_token_ids: list[int],
    block_size: int,
    prompt_logprobs: int | None = None,
    cache_salt: str | None = None,
) -> Request:
    """Same construction as tests/v1/core/test_prefix_caching.py::make_request."""
    sampling_params = SamplingParams(max_tokens=17, prompt_logprobs=prompt_logprobs)
    sampling_params.update_from_generation_config({}, eos_token_id=100)
    return Request(
        request_id=request_id,
        prompt_token_ids=prompt_token_ids,
        mm_features=None,
        sampling_params=sampling_params,
        pooling_params=None,
        lora_request=None,
        cache_salt=cache_salt,
        block_hasher=get_request_block_hasher(block_size, HASH_FN),
    )


def make_kv_cache_config(block_size: int, num_blocks: int) -> KVCacheConfig:
    """Same construction as tests/v1/core/test_prefix_caching.py."""
    return KVCacheConfig(
        num_blocks=num_blocks,
        kv_cache_tensors=[],
        kv_cache_groups=[
            KVCacheGroupSpec(
                ["layer"],
                FullAttentionSpec(
                    block_size=block_size,
                    num_kv_heads=1,
                    head_size=1,
                    dtype=torch.float32,
                ),
            )
        ],
    )


def new_manager(block_size: int, num_blocks: int = 4096) -> KVCacheManager:
    return KVCacheManager(
        make_kv_cache_config(block_size, num_blocks),
        max_model_len=8192,
        hash_block_size=block_size,
        enable_caching=True,
        log_stats=True,
    )


def warm(manager: KVCacheManager, tokens: list[int], block_size: int) -> None:
    """Run one request all the way through allocation so its full blocks get cached."""
    req = make_request("warm", tokens, block_size)
    blocks, hit = manager.get_computed_blocks(req)
    assert hit == 0, f"expected a cold manager, got {hit} cached tokens"
    assert manager.allocate_slots(req, len(tokens), hit, blocks) is not None


def probe(
    manager: KVCacheManager,
    tokens: list[int],
    block_size: int,
    prompt_logprobs: int | None = None,
    cache_salt: str | None = None,
) -> int:
    """Ask the manager how many tokens of `tokens` it considers already computed."""
    req = make_request(
        "probe", tokens, block_size, prompt_logprobs=prompt_logprobs, cache_salt=cache_salt
    )
    _, hit = manager.get_computed_blocks(req)
    return hit


def pct(hit: int, total: int) -> str:
    return f"{100.0 * hit / total:6.2f}%"


def row(label: str, prompt_len: int, hit: int, note: str = "") -> None:
    print(
        f"  {label:<34} {prompt_len:>6} {hit:>7} {pct(hit, prompt_len):>9}   {note}"
    )


def case_a_exact_repeat(block_size: int = 16, n: int = 512) -> None:
    print("\nA. exact repeat of the same prompt")
    print(f"  {'case':<34} {'prompt':>6} {'hit':>7} {'ratio':>9}")
    tokens = list(range(n))
    m = new_manager(block_size)
    warm(m, tokens, block_size)
    hit = probe(m, tokens, block_size)
    row("identical prompt, second request", n, hit)
    print(
        f"  -> {n - hit} tokens ({(n - hit) // block_size} block(s) of {block_size}) "
        f"are recomputed even though every token was cached."
    )
    stats = m.prefix_cache_stats
    print(f"  -> PrefixCacheStats: queries={stats.queries} hits={stats.hits}")


def case_b_short_shared_prefix(block_size: int = 16) -> None:
    print("\nB. shared prefix shorter than one block")
    print(f"  {'shared prefix len':<34} {'prompt':>6} {'hit':>7} {'ratio':>9}")
    for shared in (12, 15, 16, 17, 32):
        m = new_manager(block_size)
        first = list(range(shared)) + [900_000 + i for i in range(64)]
        second = list(range(shared)) + [800_000 + i for i in range(64)]
        warm(m, first, block_size)
        hit = probe(m, second, block_size)
        row(f"shared={shared:<3} (block_size={block_size})", len(second), hit)


def case_c_prompt_logprobs(block_size: int = 16, n: int = 512) -> None:
    print("\nC. identical prompt, but the request asks for prompt logprobs")
    print(f"  {'case':<34} {'prompt':>6} {'hit':>7} {'ratio':>9}")
    tokens = list(range(n))
    m = new_manager(block_size)
    warm(m, tokens, block_size)
    row("prompt_logprobs=None", n, probe(m, tokens, block_size))
    row("prompt_logprobs=1", n, probe(m, tokens, block_size, prompt_logprobs=1))
    row("cache_salt='tenant-b'", n, probe(m, tokens, block_size, cache_salt="tenant-b"))


def case_d_one_more_token(block_size: int = 16, n: int = 512) -> None:
    """Manipulation: the ceiling should move if `num_tokens - 1` is what causes it."""
    print("\nD. manipulation — same cache, one extra token on the query")
    print(f"  {'query length':<34} {'prompt':>6} {'hit':>7} {'ratio':>9}")
    tokens = list(range(n))
    m = new_manager(block_size)
    warm(m, tokens, block_size)
    for extra in (0, 1, 2, 15, 16):
        q = tokens + [777_000 + i for i in range(extra)]
        row(f"{n} cached + {extra:>2} new token(s)", len(q), probe(m, q, block_size))


def case_e_block_size_sweep(n: int = 512) -> None:
    print("\nE. same 512-token repeat, different block_size")
    print(f"  {'block_size':<34} {'prompt':>6} {'hit':>7} {'ratio':>9}")
    tokens = list(range(n))
    for block_size in (1, 16, 32, 64, 128, 256):
        m = new_manager(block_size, num_blocks=4096)
        warm(m, tokens, block_size)
        row(f"block_size={block_size}", n, probe(m, tokens, block_size))


def case_f_negative_control(block_size: int = 16, n: int = 512) -> None:
    print("\nF. negative control — a prompt that shares nothing")
    print(f"  {'case':<34} {'prompt':>6} {'hit':>7} {'ratio':>9}")
    m = new_manager(block_size)
    warm(m, list(range(n)), block_size)
    other = [500_000 + i for i in range(n)]
    hit = probe(m, other, block_size)
    row("disjoint prompt, same length", n, hit)
    assert hit == 0, "negative control failed: disjoint prompt reported a cache hit"
    print("  -> control passed (0 hits), so the probe can distinguish hit from miss.")


def case_g_hash_seed(block_size: int = 16) -> None:
    print("\nG. block-hash stability across processes")
    tokens = list(range(block_size * 2))
    init_none_hash(HASH_FN)
    first = make_request("g1", tokens, block_size).block_hashes[0]
    init_none_hash(HASH_FN)
    second = make_request("g2", tokens, block_size).block_hashes[0]
    same = first == second
    print(f"  PYTHONHASHSEED={os.getenv('PYTHONHASHSEED')!r}  hash_algo={HASH_FN.__name__}")
    print(f"  block[0] hash, first  init_none_hash: {first.hex()[:32]}...")
    print(f"  block[0] hash, second init_none_hash: {second.hex()[:32]}...")
    print(f"  identical: {same}")

    # Control: the same two inits with a fixed seed should agree.
    os.environ["PYTHONHASHSEED"] = "0"
    init_none_hash(HASH_FN)
    third = make_request("g3", tokens, block_size).block_hashes[0]
    init_none_hash(HASH_FN)
    fourth = make_request("g4", tokens, block_size).block_hashes[0]
    del os.environ["PYTHONHASHSEED"]
    print(f"  with PYTHONHASHSEED='0' set, identical: {third == fourth}")


def main() -> int:
    init_none_hash(HASH_FN)
    print(f"torch {torch.__version__} | cuda_available={torch.cuda.is_available()}")
    print(f"python {sys.version.split()[0]} | vllm source: {sys.modules['vllm'].__file__}")
    case_a_exact_repeat()
    case_b_short_shared_prefix()
    case_c_prompt_logprobs()
    case_d_one_more_token()
    case_e_block_size_sweep()
    case_f_negative_control()
    case_g_hash_seed()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
