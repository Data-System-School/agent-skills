#!/usr/bin/env python3
"""Measure vLLM's shape, and check three claims a directory listing would get wrong.

Structural counts come from the checkout; the identity and registry checks come from
importing the package, so they report what actually resolves rather than what the
layout suggests.

    PYTHONPATH=/path/to/vllm python vllm_repo_map.py [/path/to/vllm]

Anchored to vllm-project/vllm b1388b1fbf5aaef47937fabe98931211684666a6 (tag v0.19.1).
"""

import pathlib
import sys
import time


def count(root: pathlib.Path, pattern: str = "*.py") -> tuple[int, int]:
    files = list(root.rglob(pattern))
    lines = 0
    for f in files:
        try:
            lines += len(f.read_bytes().splitlines())
        except OSError:
            pass
    return len(files), lines


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def main(argv: list[str]) -> int:
    t0 = time.perf_counter()
    import vllm

    import_seconds = time.perf_counter() - t0

    pkg = pathlib.Path(vllm.__file__).parent
    repo = pathlib.Path(argv[1]) if len(argv) > 1 else pkg.parent

    section("1. where the Python actually is")
    rows = []
    for child in sorted(pkg.iterdir()):
        if child.is_dir() and not child.name.startswith("__"):
            n, l = count(child)
            if n:
                rows.append((l, n, f"vllm/{child.name}/"))
    total_files, total_lines = count(pkg)
    for lines, files, name in sorted(rows, reverse=True)[:10]:
        print(f"  {name:<28} {files:>5} files  {lines:>8} lines  {lines / total_lines:6.1%}")
    print(f"  {'vllm/ (all)':<28} {total_files:>5} files  {total_lines:>8} lines")

    models = pkg / "model_executor" / "models"
    if models.is_dir():
        n, l = count(models)
        print(
            f"\n  of which vllm/model_executor/models/: {n} files, {l} lines "
            f"({l / total_lines:.1%} of the package) — one file per architecture"
        )

    csrc = repo / "csrc"
    if csrc.is_dir():
        kernels = sum(len(list(csrc.rglob(p))) for p in ("*.cu", "*.cpp", "*.h", "*.cuh"))
        print(f"  csrc/ (CUDA/C++):            {kernels} files")
    tests = repo / "tests"
    if tests.is_dir():
        print(f"  tests/:                      {len(list(tests.rglob('test_*.py')))} test files")

    section("2. does the directory name tell you where the engine is?")
    import vllm.engine.llm_engine as legacy
    import vllm.v1.engine.llm_engine as v1

    same = legacy.LLMEngine is v1.LLMEngine
    legacy_path = pathlib.Path(legacy.__file__)
    print(f"  vllm/engine/llm_engine.py                {len(legacy_path.read_text().splitlines()):>5} lines")
    print(f"  vllm/v1/engine/llm_engine.py             {len(pathlib.Path(v1.__file__).read_text().splitlines()):>5} lines")
    print(f"  vllm.engine.llm_engine.LLMEngine is vllm.v1.engine.llm_engine.LLMEngine: {same}")
    arg_utils = pkg / "engine" / "arg_utils.py"
    if arg_utils.exists():
        print(
            f"  but vllm/engine/arg_utils.py still holds "
            f"{len(arg_utils.read_text().splitlines())} lines of live config surface"
        )

    section("3. how much of vLLM is dispatch you cannot see in the tree")
    from vllm.model_executor.models.registry import ModelRegistry

    archs = list(ModelRegistry.get_supported_archs())
    print(f"  registered model architectures:  {len(archs)}")
    print(f"  (sample: {', '.join(sorted(archs)[:3])} ...)")

    from vllm.platforms import current_platform

    print(f"  resolved platform:               {type(current_platform).__name__}")

    executors = pkg / "v1" / "executor"
    if executors.is_dir():
        names = sorted(p.stem for p in executors.glob("*executor*.py"))
        print(f"  executor implementations:        {len(names)} ({', '.join(names)})")

    backends = pkg / "v1" / "attention" / "backends"
    if backends.is_dir():
        print(f"  attention backend modules:       {len(list(backends.glob('*.py')))}")

    print(f"\n  `import vllm` took {import_seconds:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
