#!/usr/bin/env python3
"""Base/head differential for vLLM PR #36708 — multimodal prefix-cache key format.

Runs against whichever vLLM source tree is on `PYTHONPATH`, dumps what that revision
computes, and compares two dumps. Nothing is reimplemented: the values come from
`generate_block_hash_extra_keys` and `Request.block_hashes` at each revision.

    PYTHONHASHSEED=0 PYTHONPATH=/path/to/vllm-base python mm_hash_key_differential.py probe base.json
    PYTHONHASHSEED=0 PYTHONPATH=/path/to/vllm-head python mm_hash_key_differential.py probe head.json
    python mm_hash_key_differential.py compare base.json head.json

`PYTHONHASHSEED` must be set: without it `init_none_hash` seeds the hash chain from
`os.urandom`, and block hashes are not comparable between two processes.

Exits non-zero from `compare` if any text-only block hash changed — that is the
invariant the change must not break.

Base e5a77a5015e663784119d88d7ff9e77ce7419aef, head 269bf46d99f1df74e4d779f9c52c74002e057a17.
"""

import json
import sys

BLOCK_SIZE = 16
PLACEHOLDER = 32000  # a typical <image> placeholder token id
TEXT = 100


def _imports():
    from vllm.multimodal.inputs import (
        MultiModalFeatureSpec,
        MultiModalKwargsItem,
        PlaceholderRange,
    )
    from vllm.sampling_params import SamplingParams
    from vllm.utils.hashing import sha256
    from vllm.v1.core.kv_cache_utils import (
        generate_block_hash_extra_keys,
        get_request_block_hasher,
        init_none_hash,
    )
    from vllm.v1.request import Request

    return (
        MultiModalFeatureSpec,
        MultiModalKwargsItem,
        PlaceholderRange,
        SamplingParams,
        sha256,
        generate_block_hash_extra_keys,
        get_request_block_hasher,
        init_none_hash,
        Request,
    )


def make_request(mm_items, num_tokens, request_id="r"):
    """Build a Request whose token ids are placeholders wherever an mm item sits.

    mm_items: list of (identifier, offset, length).
    """
    (
        MultiModalFeatureSpec,
        MultiModalKwargsItem,
        PlaceholderRange,
        SamplingParams,
        sha256,
        _,
        get_request_block_hasher,
        _,
        Request,
    ) = _imports()

    tokens = [TEXT] * num_tokens
    features = []
    for identifier, offset, length in mm_items:
        for i in range(offset, min(offset + length, num_tokens)):
            tokens[i] = PLACEHOLDER
        features.append(
            MultiModalFeatureSpec(
                data=MultiModalKwargsItem.dummy(),
                mm_position=PlaceholderRange(offset=offset, length=length),
                identifier=identifier,
                modality="image",
            )
        )

    params = SamplingParams(max_tokens=1)
    params.update_from_generation_config({}, eos_token_id=100)
    return Request(
        request_id=request_id,
        prompt_token_ids=tokens,
        mm_features=features or None,
        sampling_params=params,
        pooling_params=None,
        lora_request=None,
        cache_salt=None,
        block_hasher=get_request_block_hasher(BLOCK_SIZE, sha256),
    )


# Request shapes. Each is (name, mm_items, num_tokens).
# `img` items of the same identifier are the same image; length is a property of
# the image, so the same identifier always carries the same length.
SHAPES = [
    ("text_only_32", [], 32),
    ("text_only_64", [], 64),
    ("img_at_0_len16", [("img_a", 0, 16)], 64),
    ("img_at_8_len16", [("img_a", 8, 16)], 64),
    ("img_at_16_len16", [("img_a", 16, 16)], 64),
    ("img_at_0_len32", [("img_b", 0, 32)], 64),
    ("img_at_4_len32", [("img_b", 4, 32)], 64),
    ("two_imgs_0_16", [("img_a", 0, 16), ("img_a", 16, 16)], 64),
    ("two_imgs_0_24", [("img_a", 0, 16), ("img_a", 24, 16)], 64),
    ("img_a_then_c", [("img_a", 0, 16), ("img_c", 16, 16)], 64),
    ("img_spans_blocks", [("img_b", 8, 32)], 64),
    # Adversarial pair: same identifiers, different lengths, so both requests have
    # identical token ids in blocks 0 and 1 while the items are aligned differently.
    # This deliberately violates the implicit "identifier determines length" rule --
    # see the example's reachability discussion.
    ("adversarial_len16", [("img_x", 0, 16), ("img_y", 16, 16)], 64),
    ("adversarial_len20", [("img_x", 0, 20), ("img_y", 20, 16)], 64),
]

# Block windows probed directly against generate_block_hash_extra_keys, chosen to
# straddle the two boundary comparisons the PR changed. curr_mm_idx is threaded
# across them the way the real hasher threads it.
WINDOWS = [(0, 16), (16, 32), (32, 48), (48, 64)]


def probe(out_path: str) -> int:
    import os

    if os.getenv("PYTHONHASHSEED") is None:
        print("refusing to run: set PYTHONHASHSEED so block hashes are comparable")
        return 2

    imports = _imports()
    sha256 = imports[4]
    generate_block_hash_extra_keys = imports[5]
    init_none_hash = imports[7]
    init_none_hash(sha256)

    result = {"extra_keys": {}, "block_hashes": {}}
    for name, mm_items, num_tokens in SHAPES:
        req = make_request(mm_items, num_tokens, request_id=name)

        # Thread curr_mm_idx across windows exactly as `request_block_hasher` does:
        # it starts at 0 for a fresh prompt and feeds each call's result to the next.
        per_window = []
        curr_mm_idx = 0
        for start, end in WINDOWS:
            keys, curr_mm_idx = generate_block_hash_extra_keys(
                req, start, end, curr_mm_idx
            )
            per_window.append(
                {"window": [start, end], "keys": repr(keys), "next_mm_idx": curr_mm_idx}
            )
        result["extra_keys"][name] = per_window

        # The decode path: `request_block_hasher` passes start_mm_idx = -1 for any
        # block whose hashing starts after the prompt, i.e. blocks completed by
        # generated tokens. Those calls are not threaded from 0.
        decode = []
        for start, end in WINDOWS:
            keys, next_idx = generate_block_hash_extra_keys(req, start, end, -1)
            decode.append(
                {"window": [start, end], "keys": repr(keys), "next_mm_idx": next_idx}
            )
        result.setdefault("decode_keys", {})[name] = decode

        result["block_hashes"][name] = [h.hex() for h in req.block_hashes]

    with open(out_path, "w") as f:
        json.dump(result, f, indent=1, sort_keys=True)
    print(f"wrote {out_path}: {len(SHAPES)} shapes")
    return 0


def _collisions(block_hashes: dict[str, list[str]]) -> list[tuple[str, str, int]]:
    """Distinct shapes that produce the same hash at the same block index."""
    found = []
    names = list(block_hashes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            for idx, (ha, hb) in enumerate(zip(block_hashes[a], block_hashes[b])):
                if ha == hb:
                    found.append((a, b, idx))
    return found


def compare(base_path: str, head_path: str) -> int:
    base = json.load(open(base_path))
    head = json.load(open(head_path))

    print("=" * 78)
    print("1. extra keys per block window (generate_block_hash_extra_keys)")
    print("=" * 78)
    changed = same = 0
    for name in base["extra_keys"]:
        for b, h in zip(base["extra_keys"][name], head["extra_keys"][name]):
            if b["keys"] == h["keys"] and b["next_mm_idx"] == h["next_mm_idx"]:
                same += 1
                continue
            changed += 1
            w = f"{name} [{b['window'][0]:>2}:{b['window'][1]:<2}]"
            print(f"  {w:<34} base {b['keys']:<28} -> head {h['keys']}")
            if b["next_mm_idx"] != h["next_mm_idx"]:
                print(
                    f"  {'':<34} next_mm_idx {b['next_mm_idx']} -> {h['next_mm_idx']}"
                )
    print(f"  {changed} window(s) changed, {same} unchanged")

    print()
    print("=" * 78)
    print("1b. same windows on the decode path (start_mm_idx = -1)")
    print("=" * 78)
    dchanged = dsame = 0
    for name in base.get("decode_keys", {}):
        for b, h in zip(base["decode_keys"][name], head["decode_keys"][name]):
            if b["keys"] == h["keys"]:
                dsame += 1
                continue
            dchanged += 1
            w = f"{name} [{b['window'][0]:>2}:{b['window'][1]:<2}]"
            print(f"  {w:<34} base {b['keys']:<28} -> head {h['keys']}")
    print(f"  {dchanged} window(s) changed, {dsame} unchanged")

    print()
    print("=" * 78)
    print("2. block hashes: which request shapes changed between base and head")
    print("=" * 78)
    violations, changed_shapes, stable_shapes = [], [], []
    for name in base["block_hashes"]:
        b_hashes, h_hashes = base["block_hashes"][name], head["block_hashes"][name]
        identical = b_hashes == h_hashes
        (stable_shapes if identical else changed_shapes).append(name)
        if name.startswith("text_only") and not identical:
            violations.append(name)
        n_diff = sum(1 for x, y in zip(b_hashes, h_hashes) if x != y)
        flag = "same" if identical else f"{n_diff}/{len(b_hashes)} block hashes differ"
        print(f"  {name:<22} {flag}")
    print()
    print(f"  unchanged shapes: {len(stable_shapes)}  ({', '.join(stable_shapes)})")
    print(f"  changed shapes:   {len(changed_shapes)}")
    if violations:
        print(f"  INVARIANT VIOLATED — text-only hashes changed: {violations}")
    else:
        print("  invariant holds: every text-only shape keeps its exact block hashes")

    print()
    print("=" * 78)
    print("3. cross-shape hash collisions within one revision")
    print("=" * 78)
    base_col = {(a, b, i) for a, b, i in _collisions(base["block_hashes"])}
    head_col = {(a, b, i) for a, b, i in _collisions(head["block_hashes"])}
    for label, cols in (("base", base_col), ("head", head_col)):
        print(f"  {label}: {len(cols)} collision(s)")
        for a, b, idx in sorted(cols):
            print(f"    block {idx}: {a} == {b}")
    fixed = base_col - head_col
    introduced = head_col - base_col
    print(f"  fixed by the change:      {len(fixed)}")
    for a, b, idx in sorted(fixed):
        print(f"    block {idx}: {a} == {b}")
    print(f"  introduced by the change: {len(introduced)}")
    for a, b, idx in sorted(introduced):
        print(f"    block {idx}: {a} == {b}")

    return 1 if violations or introduced else 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "probe":
        return probe(argv[2])
    if len(argv) >= 4 and argv[1] == "compare":
        return compare(argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
