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

Run from the repository root. By default this test supplies its own synthetic
dictionary via $TIC_DICT_PATH, so the historical dict.txt is NOT required.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dataset_config import DICT_PATH_ENV_VAR

from dependencies import (
    MissingDependencyError,
    check_dictionary as dep_check_dictionary,
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

# A tiny dictionary the test writes itself, so the smoke test never requires the
# historical dict.txt -- which is a third-party derivative that cannot currently
# be redistributed (docs/licensing.md section 3).
#
# The 17 leading punctuation entries mirror the historical layout; the words are
# just those in SAMPLE_TEXT. Words absent from a dictionary become "special code
# words", so the round trip stays byte-exact regardless.
#
# This validates FUNCTION only. Compressed sizes produced with it are unrelated
# to the published measurements.
SYNTHETIC_DICT_ENTRIES = [
    ",", ".", "-", ":", "?", "(", ")", "!", ";", "/", "\\", '"', "\u201c", "\u201d", "'", "\u2019", "`",
    "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
    "a", "journey", "of", "thousand", "miles", "begins", "with", "single", "step",
    "to", "be", "or", "not", "that", "is", "question",
    "all", "glitters", "gold", "and", "every", "cloud", "has", "silver", "lining",
    "rain", "in", "spain", "falls", "mainly", "on", "plain",
]


# Filler entries appended after the real words.
#
# Necessary because of a pre-existing bound in PIC: pic-v3.1.cpp:2041 rejects
# `finalSerial >= NUMBER_OF_WORDS_DICT`, but serials carry the +CODE_WORD_OFFSET
# (5) shift while NUMBER_OF_WORDS_DICT is a raw line count. The top 5 entries of
# any dictionary are therefore unusable by PIC decompression. With the
# historical 333,350-entry dictionary only the five rarest words are affected,
# so it never surfaces; with a 58-entry dictionary it fails immediately.
#
# Padding keeps every real word at a low serial. It is a property of the test
# fixture only -- no TIC or PIC behaviour is modified.
SYNTHETIC_DICT_PADDING = 64


def write_synthetic_dictionary(workdir: Path) -> Path:
    path = workdir / "synthetic_dict.txt"
    entries = list(SYNTHETIC_DICT_ENTRIES) + [
        f"zzpadding{i:04d}" for i in range(SYNTHETIC_DICT_PADDING)
    ]
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for entry in entries:
            fh.write(entry + "\n")
    return path

PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def record(status, name, detail=""):
    _results.append((status, name, detail))
    print(f"  [{status}] {name}" + (f"  {detail}" if detail else ""), flush=True)
    return status == PASS


def run(cmd, timeout=120, dict_path=None):
    """
    Run a command from the repository root. Returns (ok, stdout, stderr).

    When dict_path is given it is passed via $TIC_DICT_PATH, which is how both
    binaries resolve their dictionary.
    """
    env = None
    if dict_path is not None:
        env = dict(os.environ)
        env[DICT_PATH_ENV_VAR] = str(dict_path)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
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


def check_prerequisites(use_historical: bool) -> bool:
    print("\nPrerequisites")
    print("-------------")

    if not use_historical:
        return record(PASS, "dictionary",
                      "synthetic dictionary created by this test "
                      "(historical dict.txt not required)")

    info = dep_check_dictionary()
    if not info["is_file"]:
        return record(FAIL, "dictionary", f"--historical-dict requested but not found: {info['path']}")
    if info["matches_historical"]:
        return record(PASS, "dictionary", f"{info['path']} (SHA-256 matches historical)")
    return record(PASS, "dictionary",
                  f"{info['path']} (present; SHA-256 does NOT match the historical dictionary)")


def test_scheme(label, binary, ext, workdir: Path, dict_path=None) -> bool:
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
    good, _, err = run([f"./{binary}", "-c", "-t", "1", str(src), str(compressed)], dict_path=dict_path)
    if not good:
        return record(FAIL, "compress", err.strip()[:160])
    if not compressed.is_file() or compressed.stat().st_size == 0:
        return record(FAIL, "compress", "produced no output")
    ok &= record(PASS, "compress",
                 f"{src.stat().st_size:,} B -> {compressed.stat().st_size:,} B")

    # 2. decompress
    good, _, err = run([f"./{binary}", "-d", "-t", "1", str(compressed), str(restored)], dict_path=dict_path)
    if not good:
        return record(FAIL, "decompress", err.strip()[:160])
    ok &= record(PASS, "decompress", f"{restored.stat().st_size:,} B")

    # 3. round trip must be byte-exact
    identical = restored.is_file() and filecmp.cmp(src, restored, shallow=False)
    ok &= record(PASS if identical else FAIL, "round trip",
                 "byte-identical" if identical else "OUTPUT DIFFERS FROM INPUT")

    # 4. lookup (-l): output file argument is ignored but must be supplied
    good, out, err = run([f"./{binary}", "-l", "-t", "1", str(compressed),
                          str(workdir / "ignored.out"), SEARCH_WORD], dict_path=dict_path)
    ok &= record(PASS if good else FAIL, "lookup",
                 f'searched "{SEARCH_WORD}"' if good else err.strip()[:160])

    # 5. lookup-and-replace (-r)
    good, out, err = run([f"./{binary}", "-r", "-t", "1", str(compressed),
                          str(replaced), SEARCH_WORD, REPLACE_WORD], dict_path=dict_path)
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
    parser.add_argument("--historical-dict", action="store_true",
                        help="Use the resolved dict.txt instead of the synthetic one. "
                             "Not required: the default needs no third-party dictionary.")
    args = parser.parse_args(argv)

    print("TIC artifact -- functional smoke test")
    print("=" * 37)
    print("Tiny synthetic input. This is a correctness check, NOT a performance test.")

    try:
        require_python_version()
    except MissingDependencyError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    ok = check_prerequisites(args.historical_dict)

    if not args.no_build:
        ok &= build()
    else:
        print("\nBuild\n-----\n  [SKIP] --no-build")

    workdir = Path(tempfile.mkdtemp(prefix="tic_smoke_"))
    try:
        if args.historical_dict:
            dict_path = None          # binaries resolve it themselves
            print(f"\n[INFO] Using the resolved dictionary "
                  f"({dep_check_dictionary()['path']}).")
        else:
            dict_path = write_synthetic_dictionary(workdir)
            print(f"\n[INFO] Using a synthetic dictionary "
                  f"({len(SYNTHETIC_DICT_ENTRIES)} entries) via ${DICT_PATH_ENV_VAR}.")
            print("[INFO] Compressed sizes below are NOT comparable to published results.")

        for label, binary, ext in SCHEMES:
            ok &= test_scheme(label, binary, ext, workdir, dict_path=dict_path)
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
