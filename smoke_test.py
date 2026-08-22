#!/usr/bin/env python3
"""
smoke_test.py

Functional smoke test for the TIC and PIC binaries, using a tiny synthetic
input. Answers one question: does the artifact work at all?

    python3 smoke_test.py            # build if needed, then test both schemes
    python3 smoke_test.py --no-build # test whatever binaries already exist
    python3 smoke_test.py --keep     # keep the temporary working directory

THIS IS NOT A PERFORMANCE TEST. It measures nothing, produces no timings, and
its results say nothing about compression ratio or speed. It runs on a few
kilobytes of synthetic text and needs none of the multi-gigabyte datasets.

For performance and the published tables, see docs/datasets.md and the
benchmark runners -- those need the real datasets.

Checks, for TIC (epic-v3.1) and PIC (pic-v3.1) independently:
    1. the binary builds
    2. compression runs and produces a non-empty file
    3. decompression runs
    4. the decompressed output is byte-identical to the original
    5. lookup (-l) works
    6. lookup-and-replace (-r) works

Exit codes: 0 all checks passed, 1 something failed.

Run from the repository root: the binaries resolve dict.txt against the CWD.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dependencies import (
    MissingDependencyError,
    PIC_BINARY_NAME,
    TIC_BINARY_NAME,
    require_executables,
    require_python_version,
)

# Common English words, so the dictionary-based schemes have real work to do.
SAMPLE_TEXT = (
    "the quick brown fox jumps over the lazy dog.\n"
    "a journey of a thousand miles begins with a single step.\n"
    "to be or not to be that is the question.\n"
    "all that glitters is not gold and every cloud has a silver lining.\n"
    "the rain in spain falls mainly on the plain.\n"
) * 40

SEARCH_WORD = "the"
REPLACE_WORD = "THE"

SCHEMES = [("TIC", TIC_BINARY_NAME, ".tic"), ("PIC", PIC_BINARY_NAME, ".pic")]

PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def record(status, name, detail=""):
    _results.append((status, name, detail))
    print(f"  [{status}] {name}" + (f"  {detail}" if detail else ""), flush=True)
    return status == PASS


def run(cmd, timeout=120):
    """Run a command from the repository root. Returns (ok, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", f"timed out after {timeout}s"
    except FileNotFoundError as exc:
        return False, "", str(exc)
    return p.returncode == 0, p.stdout, p.stderr


def build() -> bool:
    print("\nBuild")
    print("-----")
    try:
        require_executables(["make", "g++"], purpose="building the binaries")
    except MissingDependencyError as exc:
        record(FAIL, "toolchain", str(exc).splitlines()[0])
        return False

    ok, _, err = run(["make"], timeout=600)
    if not ok:
        return record(FAIL, "make", err.strip()[:200])
    record(PASS, "make", "both binaries built")

    all_ok = True
    for label, binary, _ in SCHEMES:
        all_ok &= record(PASS if Path(binary).is_file() else FAIL,
                         f"{label} binary", binary)
    return all_ok


def check_prerequisites() -> bool:
    print("\nPrerequisites")
    print("-------------")
    ok = record(PASS if Path("dict.txt").is_file() else FAIL, "dict.txt",
                "run from the repository root" if not Path("dict.txt").is_file() else "present")
    return ok


def test_scheme(label, binary, ext, workdir: Path) -> bool:
    print(f"\n{label} ({binary})")
    print("-" * (len(label) + len(binary) + 3))

    if not Path(binary).is_file():
        return record(FAIL, f"{label} binary", "not built (run: make)")

    src = workdir / f"{label.lower()}_input.txt"
    src.write_text(SAMPLE_TEXT, encoding="utf-8")
    compressed = workdir / f"{label.lower()}_input.txt{ext}"
    restored = workdir / f"{label.lower()}_restored.txt"
    replaced = workdir / f"{label.lower()}_replaced{ext}"

    ok = True

    # 1. compress
    good, _, err = run([f"./{binary}", "-c", "-t", "1", str(src), str(compressed)])
    if not good:
        return record(FAIL, "compress", err.strip()[:160])
    if not compressed.is_file() or compressed.stat().st_size == 0:
        return record(FAIL, "compress", "produced no output")
    ok &= record(PASS, "compress",
                 f"{src.stat().st_size:,} B -> {compressed.stat().st_size:,} B")

    # 2. decompress
    good, _, err = run([f"./{binary}", "-d", "-t", "1", str(compressed), str(restored)])
    if not good:
        return record(FAIL, "decompress", err.strip()[:160])
    ok &= record(PASS, "decompress", f"{restored.stat().st_size:,} B")

    # 3. round trip must be byte-exact
    identical = restored.is_file() and filecmp.cmp(src, restored, shallow=False)
    ok &= record(PASS if identical else FAIL, "round trip",
                 "byte-identical" if identical else "OUTPUT DIFFERS FROM INPUT")

    # 4. lookup (-l): output file argument is ignored but must be supplied
    good, out, err = run([f"./{binary}", "-l", "-t", "1", str(compressed),
                          str(workdir / "ignored.out"), SEARCH_WORD])
    ok &= record(PASS if good else FAIL, "lookup",
                 f'searched "{SEARCH_WORD}"' if good else err.strip()[:160])

    # 5. lookup-and-replace (-r)
    good, out, err = run([f"./{binary}", "-r", "-t", "1", str(compressed),
                          str(replaced), SEARCH_WORD, REPLACE_WORD])
    ok &= record(PASS if good else FAIL, "lookup-and-replace",
                 f'"{SEARCH_WORD}" -> "{REPLACE_WORD}"' if good else err.strip()[:160])

    return ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Functional smoke test on a tiny synthetic input. Not a performance test.")
    parser.add_argument("--no-build", action="store_true",
                        help="Do not run make; test the existing binaries.")
    parser.add_argument("--keep", action="store_true",
                        help="Keep the temporary working directory.")
    args = parser.parse_args(argv)

    print("TIC artifact -- functional smoke test")
    print("=" * 37)
    print("Tiny synthetic input. This is a correctness check, NOT a performance test.")

    try:
        require_python_version()
    except MissingDependencyError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    ok = check_prerequisites()

    if not args.no_build:
        ok &= build()
    else:
        print("\nBuild\n-----\n  [SKIP] --no-build")

    workdir = Path(tempfile.mkdtemp(prefix="tic_smoke_"))
    try:
        for label, binary, ext in SCHEMES:
            ok &= test_scheme(label, binary, ext, workdir)
    finally:
        if args.keep:
            print(f"\n[INFO] Working directory kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    passed = sum(1 for s, _, _ in _results if s == PASS)
    failed = sum(1 for s, _, _ in _results if s == FAIL)

    print("\nSummary")
    print("-------")
    print(f"  {passed} passed, {failed} failed")

    if failed:
        print("\n  Failing checks:")
        for status, name, detail in _results:
            if status == FAIL:
                print(f"      - {name}: {detail}")
        print("\n  Check the environment first: python3 check_environment.py")
        return 1

    print("\n  Functional smoke test passed.")
    print("  This says nothing about performance. For the published results see")
    print("  docs/datasets.md and the benchmark runners.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
