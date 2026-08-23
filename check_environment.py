#!/usr/bin/env python3
"""
check_environment.py

Reviewer-facing environment validation for the TIC artifact.

    python3 check_environment.py            # full report
    python3 check_environment.py --quiet    # only failures and the summary
    python3 check_environment.py --json     # machine-readable

Reports PASS / FAIL / WARN for the Python interpreter, Python packages, the
compiler toolchain, external executables, the compiled binaries, dataset
availability and required directories. Where something is needed by only one
experiment, the affected experiment is named.

This command NEVER runs a benchmark and never writes into the repository.

Exit codes:
    0  every REQUIRED check passed (experiment-specific gaps may remain)
    1  at least one REQUIRED check failed

Related:
    ./install_dependencies.sh   install system + Python dependencies
    python3 smoke_test.py       functional correctness on a tiny synthetic file
    docs/environment.md         full environment documentation
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from dependencies import (
    EXECUTABLES,
    check_dictionary as dep_check_dictionary,
    MIN_PYTHON,
    PIC_BINARY_NAME,
    PYTHON_PACKAGES,
    TIC_BINARY_NAME,
    have_executable,
    have_python_package,
)
from dataset_config import (
    BENCHMARK_DATASET_NAMES,
    RESULTS_FIGURES_DIR,
    RESULTS_LOGS_DIR,
    RESULTS_RAW_DIR,
    RESULTS_TABLES_DIR,
    RESULTS_TMP_DIR,
    DICT_PATH_ENV_VAR,
    HISTORICAL_DICT,
    DATASET_DIR,
    PARALLEL_DATASET_NAME,
    dataset_path,
)

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _colour(status: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return status
    return {PASS: GREEN, FAIL: RED, WARN: YELLOW, INFO: DIM}.get(status, "") + status + RESET


class Report:
    def __init__(self, quiet: bool = False, silent: bool = False):
        self.rows: list[dict] = []
        self.quiet = quiet
        # silent suppresses ALL human output, so --json emits pure JSON.
        self.silent = silent

    def add(self, status, category, name, detail="", affects="", required=True):
        row = {
            "status": status, "category": category, "name": name,
            "detail": detail, "affects": affects, "required": required,
        }
        self.rows.append(row)
        if self.silent or (self.quiet and status == PASS):
            return
        line = f"  [{_colour(status)}] {name:<26} {detail}"
        print(line)
        if affects and status != PASS:
            print(f"         {DIM if sys.stdout.isatty() else ''}affects: {affects}"
                  f"{RESET if sys.stdout.isatty() else ''}")

    def section(self, title):
        if not self.quiet and not self.silent:
            print(f"\n{title}")
            print("-" * len(title))

    @property
    def required_failures(self):
        return [r for r in self.rows if r["status"] == FAIL and r["required"]]

    @property
    def optional_failures(self):
        return [r for r in self.rows if r["status"] in (FAIL, WARN) and not r["required"]]


# =====================
# Checks
# =====================

def check_platform(rep: Report) -> None:
    rep.section("Platform")
    system = platform.system()
    detail = f"{system} {platform.release()} ({platform.machine()})"
    if system in ("Linux", "Darwin"):
        rep.add(PASS, "platform", "operating system", detail)
    else:
        rep.add(WARN, "platform", "operating system", detail + " -- untested",
                affects="everything; only Linux and macOS are supported", required=False)


def check_python(rep: Report) -> None:
    rep.section("Python")
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    rep.add(PASS if ok else FAIL, "python", "interpreter",
            f"{platform.python_version()} at {sys.executable}",
            affects=f"everything; {'.'.join(map(str, MIN_PYTHON))}+ required")

    for dep in PYTHON_PACKAGES:
        name, cls = dep["name"], dep["classification"]
        if cls == "optional":
            continue
        present = have_python_package(name)
        required = cls == "required"
        if present:
            rep.add(PASS, "python-package", name, _package_version(name), required=required)
        else:
            rep.add(FAIL if required else WARN, "python-package", name,
                    f"not installed  (pip install {dep['pip']})",
                    affects=", ".join(dep["required_for"]), required=required)


def _package_version(name: str) -> str:
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version(name if name != "bs4" else "beautifulsoup4")
        except PackageNotFoundError:
            return "installed"
    except Exception:
        return "installed"


def check_executables(rep: Report) -> None:
    rep.section("External executables")
    for dep in EXECUTABLES:
        name, cls = dep["name"], dep["classification"]
        required = cls == "required"
        if have_executable(name):
            rep.add(PASS, "executable", name, shutil.which(name), required=required)
        else:
            hint = dep["packages"]
            fix = f"apt install {hint.get('apt', name)} | brew install {hint.get('brew', name)}" if hint else ""
            rep.add(FAIL if required else WARN, "executable", name,
                    f"not found in PATH   {fix}",
                    affects=", ".join(dep["required_for"]), required=required)


def check_compiler(rep: Report) -> None:
    rep.section("Compiler toolchain")
    cxx = os.environ.get("CXX") or "g++"
    if not have_executable(cxx):
        rep.add(FAIL, "compiler", "C++ compiler", f"{cxx} not found",
                affects="building epic-v3.1 and pic-v3.1")
        return
    try:
        out = subprocess.run([cxx, "--version"], capture_output=True, text=True, timeout=15)
        first = out.stdout.splitlines()[0] if out.stdout else cxx
    except Exception as exc:                                  # pragma: no cover
        rep.add(WARN, "compiler", "C++ compiler", f"{cxx}: {exc}", required=False)
        return
    rep.add(PASS, "compiler", "C++ compiler", first)

    probe = "#include <thread>\n#include <string>\nint main(){ return 0; }\n"
    try:
        res = subprocess.run([cxx, "-std=c++17", "-pthread", "-x", "c++", "-fsyntax-only", "-"],
                             input=probe, capture_output=True, text=True, timeout=60)
        rep.add(PASS if res.returncode == 0 else FAIL, "compiler", "C++17 + pthread",
                "accepted" if res.returncode == 0 else res.stderr.strip()[:120],
                affects="building epic-v3.1 and pic-v3.1")
    except Exception as exc:                                  # pragma: no cover
        rep.add(WARN, "compiler", "C++17 + pthread", str(exc), required=False)


def check_binaries(rep: Report) -> None:
    rep.section("Compiled binaries")
    for name in (TIC_BINARY_NAME, PIC_BINARY_NAME):
        p = Path(name)
        if p.is_file() and os.access(p, os.X_OK):
            rep.add(PASS, "binary", name, f"{p.stat().st_size:,} bytes")
        elif p.is_file():
            rep.add(FAIL, "binary", name, "present but not executable",
                    affects="all experiments")
        else:
            rep.add(FAIL, "binary", name, "not built  (run: make)",
                    affects="all experiments")


def check_dictionary(rep: Report) -> None:
    """
    Three distinct outcomes, never conflated:
      PASS  present and the SHA-256 matches the historical artifact dictionary
      WARN  present but a different dictionary -> does NOT reproduce the paper
      FAIL  missing, unreadable, empty, or not a regular file
    """
    rep.section("Dictionary")

    info = dep_check_dictionary()
    path = info["path"]
    src = (f"${DICT_PATH_ENV_VAR}" if os.environ.get(DICT_PATH_ENV_VAR, "").strip()
           else "default, CWD-relative")
    rep.add(INFO, "data", "dictionary path", f"{path}  ({src})", required=False)

    if not info["exists"]:
        rep.add(FAIL, "data", "dictionary",
                f"not found: {path}   (set ${DICT_PATH_ENV_VAR}, or see docs/dictionary.md)",
                affects="all experiments; every TIC/PIC operation loads it")
        return
    if not info["is_file"]:
        rep.add(FAIL, "data", "dictionary", f"not a regular file: {path}",
                affects="all experiments")
        return
    if info["empty"]:
        rep.add(FAIL, "data", "dictionary", f"empty file: {path}", affects="all experiments")
        return
    if not info["readable"]:
        rep.add(FAIL, "data", "dictionary", f"not readable: {path}", affects="all experiments")
        return

    if info["matches_historical"]:
        rep.add(PASS, "data", "dictionary",
                f"{info['size']:,} bytes, SHA-256 matches the historical artifact dictionary")
    else:
        rep.add(WARN, "data", "dictionary",
                f"{info['size']:,} bytes, SHA-256 does NOT match the historical dictionary",
                affects="results will not reproduce the published measurements "
                        "(a different dictionary changes compressed output). "
                        "See docs/dictionary.md",
                required=False)
        rep.add(INFO, "data", "  expected sha256", HISTORICAL_DICT["sha256"], required=False)
        rep.add(INFO, "data", "  actual sha256", info["sha256"], required=False)


def check_datasets(rep: Report) -> None:
    rep.section("Datasets")
    rep.add(INFO, "data", "dataset directory", f"{DATASET_DIR}/", required=False)

    present = [n for n in BENCHMARK_DATASET_NAMES if Path(dataset_path(n)).is_file()]
    detail = f"{len(present)}/{len(BENCHMARK_DATASET_NAMES)} present"
    if len(present) == len(BENCHMARK_DATASET_NAMES):
        rep.add(PASS, "data", "f1..f10", detail, required=False)
    else:
        rep.add(WARN, "data", "f1..f10",
                detail + "  (build: python3 prepare_datasets.py)",
                affects="compression, decompression, search, search-and-replace experiments",
                required=False)

    if Path(dataset_path(PARALLEL_DATASET_NAME)).is_file():
        rep.add(PASS, "data", PARALLEL_DATASET_NAME, "present", required=False)
    else:
        rep.add(WARN, "data", PARALLEL_DATASET_NAME,
                "absent (provenance unknown; supply one with --input)",
                affects="parallel experiments -- see docs/datasets.md section 7",
                required=False)


def check_directories(rep: Report) -> None:
    rep.section("Output directories")
    for d in (".", RESULTS_RAW_DIR, RESULTS_TABLES_DIR, RESULTS_FIGURES_DIR,
              RESULTS_LOGS_DIR, RESULTS_TMP_DIR):
        p = Path(d)
        if p.exists():
            status = PASS if os.access(p, os.W_OK) else FAIL
            rep.add(status, "directory", d,
                    "writable" if status == PASS else "NOT writable",
                    affects="all experiments write results and logs")
        else:
            rep.add(INFO, "directory", d, "will be created on first run", required=False)


# =====================
# Main
# =====================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the environment for the TIC artifact. Runs no benchmarks.")
    parser.add_argument("--quiet", action="store_true", help="Show only failures and the summary.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    rep = Report(quiet=args.quiet, silent=args.json)

    if not args.json:
        print("TIC artifact -- environment check")
        print("=" * 34)

    for check in (check_platform, check_python, check_executables, check_compiler,
                  check_binaries, check_dictionary, check_datasets, check_directories):
        check(rep)

    required_failed = rep.required_failures
    optional_failed = rep.optional_failures

    if args.json:
        print(json.dumps({
            "rows": rep.rows,
            "required_failures": len(required_failed),
            "optional_failures": len(optional_failed),
            "result": "FAIL" if required_failed else "PASS",
        }, indent=2))
        return 1 if required_failed else 0

    print("\nSummary")
    print("-------")
    counts = {}
    for r in rep.rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("  " + "   ".join(f"{k}: {v}" for k, v in sorted(counts.items())))

    if required_failed:
        print(f"\n  {_colour(FAIL)}  {len(required_failed)} required check(s) failed:")
        for r in required_failed:
            print(f"      - {r['name']}: {r['detail']}")
        print("\n  Fix with: ./install_dependencies.sh   (then: make)")
        print("  Details:  docs/environment.md")
        return 1

    print(f"\n  {_colour(PASS)}  All required checks passed.")
    if optional_failed:
        print(f"  {_colour(WARN)}  {len(optional_failed)} experiment-specific item(s) unavailable:")
        for r in optional_failed:
            print(f"      - {r['name']}: {r['detail']}")
            if r["affects"]:
                print(f"        affects: {r['affects']}")
    print("\n  Next: python3 smoke_test.py   (functional check, tiny synthetic input)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
