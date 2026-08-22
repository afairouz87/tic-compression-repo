#!/usr/bin/env python3
"""
dependencies.py

Single authoritative inventory of everything the TIC artifact needs, plus the
validation helpers that enforce it.

Standard library only, so `check_environment.py`, `prepare_datasets.py` and the
smoke test can all use it without first installing anything.

Two things live here:

  1. The INVENTORY: PYTHON_PACKAGES and EXECUTABLES, each entry classified and
     attributed to the experiments that need it. `check_environment.py` renders
     it; `requirements.txt` is generated from the same data.
  2. The GUARDS: require_* helpers that fail loudly, before a long-running
     experiment starts, rather than midway through it.

Classifications
---------------
  required            needed by every artifact workflow
  experiment          needed only by specific experiments (see `required_for`)
  optional            improves output but nothing fails without it
  development         used while developing, not to reproduce results
  obsolete            only referenced by superseded scripts
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

MIN_PYTHON = (3, 9)

# =====================
# Inventory
# =====================


class Dep(dict):
    """A dependency record. dict-based so it stays trivially serialisable."""

    def __init__(self, name, classification, required_for, notes="", pip=None,
                 packages=None, min_version=None):
        super().__init__(
            name=name,
            classification=classification,
            required_for=required_for,
            notes=notes,
            pip=pip or name,
            packages=packages or {},
            min_version=min_version,
        )

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


PYTHON_PACKAGES = [
    Dep("pandas", "required",
        ["all benchmark runners", "table generation"],
        "Imported unguarded at module import time by benchmark_utils and every runner."),
    Dep("matplotlib", "experiment",
        ["parallel experiments (figures)", "plot_parallel_*.py"],
        "Guarded in benchmark_utils (plt=None) but imported unguarded by "
        "run_parallel_benchmarks.py and both plotting scripts."),
    Dep("psutil", "required",
        ["memory measurements in search, parallel and compression runners"],
        "Required whenever memory columns are produced. A missing psutil used to "
        "yield silent zeros; it is now a hard failure. See docs/environment.md."),
    Dep("requests", "experiment",
        ["dataset acquisition (prepare_datasets.py fetch)"],
        "Not needed to build datasets from an existing corpus, nor to benchmark."),
    Dep("bs4", "experiment",
        ["dataset acquisition (prepare_datasets.py fetch)"],
        "Imported as `bs4`.", pip="beautifulsoup4"),
    Dep("ebooklib", "experiment",
        ["dataset acquisition: Standard Ebooks EPUB conversion"]),
    Dep("lxml", "experiment",
        ["dataset acquisition: HTML/XML parser backend for beautifulsoup4"],
        "Never imported directly; named as the parser in the download scripts."),
    Dep("numpy", "optional",
        [],
        "Not imported anywhere in this repository. Present only transitively as a "
        "dependency of pandas and matplotlib; it is not a direct requirement."),
]

EXECUTABLES = [
    Dep("g++", "required", ["building epic-v3.1 and pic-v3.1"],
        "Any C++17 compiler. Override with `make CXX=...`. Apple clang works.",
        packages={"apt": "g++", "brew": "(bundled with Xcode Command Line Tools)"}),
    Dep("make", "required", ["building epic-v3.1 and pic-v3.1"],
        packages={"apt": "make", "brew": "(bundled with Xcode Command Line Tools)"}),
    Dep("gzip", "required",
        ["compression", "decompression", "search", "search-and-replace"],
        "Preinstalled on both platforms; BSD gzip on macOS, GNU gzip on Linux.",
        packages={"apt": "gzip", "brew": "gzip"}),
    Dep("bzip2", "required",
        ["compression", "decompression", "search", "search-and-replace"],
        "Preinstalled on both platforms.",
        packages={"apt": "bzip2", "brew": "bzip2"}),
    Dep("lz4", "required",
        ["compression", "decompression", "search", "search-and-replace"],
        "NOT preinstalled on either platform. Must be installed explicitly.",
        packages={"apt": "lz4", "brew": "lz4"}),
    Dep("grep", "required",
        ["search", "search-and-replace (decompress | grep pipelines)"],
        "Preinstalled. BSD grep on macOS, GNU grep on Linux.",
        packages={"apt": "grep", "brew": "grep"}),
    Dep("zgrep", "experiment", ["search (streaming search baseline)"],
        "Ships with gzip on both platforms.",
        packages={"apt": "gzip", "brew": "gzip"}),
    Dep("bzgrep", "experiment", ["search (streaming search baseline)"],
        "Ships with bzip2 on both platforms.",
        packages={"apt": "bzip2", "brew": "bzip2"}),
    Dep("lbzip2", "experiment", ["parallel experiments ONLY"],
        "run_parallel_benchmarks.py is the only consumer. Not needed for "
        "compression, decompression, search or search-and-replace. NOT "
        "preinstalled on either platform.",
        packages={"apt": "lbzip2", "brew": "lbzip2"}),
    Dep("sh", "required",
        ["decompression, search-and-replace and parallel runners (pipelines)"],
        "POSIX shell; always present.",
        packages={"apt": "(base system)", "brew": "(base system)"}),
]

# Per-experiment requirements, used by the runners' pre-flight checks.
EXPERIMENT_REQUIREMENTS = {
    "compression":       {"executables": ["gzip", "bzip2", "lz4"],
                          "python": ["pandas", "psutil"]},
    "decompression":     {"executables": ["gzip", "bzip2", "lz4", "sh"],
                          "python": ["pandas", "psutil"]},
    "search":            {"executables": ["gzip", "bzip2", "lz4", "grep", "zgrep", "bzgrep"],
                          "python": ["pandas", "psutil"]},
    "search_replace":    {"executables": ["gzip", "bzip2", "lz4", "grep", "sh"],
                          "python": ["pandas", "psutil"]},
    "parallel":          {"executables": ["lbzip2", "sh"],
                          "python": ["pandas", "psutil", "matplotlib"]},
    "dataset_build":     {"executables": [], "python": []},
    "dataset_fetch":     {"executables": [],
                          "python": ["requests", "bs4", "ebooklib", "lxml"]},
}

TIC_BINARY_NAME = "epic-v3.1"
PIC_BINARY_NAME = "pic-v3.1"


class MissingDependencyError(RuntimeError):
    """A required dependency is absent. Always fatal, always raised up front."""


# =====================
# Lookup helpers
# =====================

def _find(inventory, name):
    for dep in inventory:
        if dep["name"] == name:
            return dep
    return None


def python_package(name):
    return _find(PYTHON_PACKAGES, name)


def executable(name):
    return _find(EXECUTABLES, name)


def have_python_package(name) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def have_executable(name) -> bool:
    return shutil.which(name) is not None


# =====================
# Guards
# =====================

def require_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        raise MissingDependencyError(
            f"Python {'.'.join(map(str, MIN_PYTHON))}+ is required; "
            f"this is {sys.version.split()[0]}."
        )


def require_python_packages(names, purpose: str = "") -> None:
    missing = [n for n in names if not have_python_package(n)]
    if not missing:
        return
    pips = []
    for n in missing:
        dep = python_package(n)
        pips.append(dep["pip"] if dep else n)
    where = f" for {purpose}" if purpose else ""
    raise MissingDependencyError(
        f"Missing required Python package(s){where}: {', '.join(missing)}\n"
        f"  Install with: python3 -m pip install {' '.join(pips)}\n"
        f"  Or install everything: python3 -m pip install -r requirements.txt\n"
        f"  Then re-check with: python3 check_environment.py"
    )


def require_executables(names, purpose: str = "") -> None:
    missing = [n for n in names if not have_executable(n)]
    if not missing:
        return

    lines = [f"Missing required executable(s)"
             + (f" for {purpose}" if purpose else "") + f": {', '.join(missing)}"]
    for n in missing:
        dep = executable(n)
        if dep and dep["packages"]:
            lines.append(f"  {n}:  apt install {dep['packages'].get('apt', n)}"
                         f"   |   brew install {dep['packages'].get('brew', n)}")
    lines.append("  Or run: ./install_dependencies.sh")
    lines.append("  Then re-check with: python3 check_environment.py")
    raise MissingDependencyError("\n".join(lines))


def require_input_files(paths, purpose: str = "") -> None:
    missing = [str(p) for p in paths if not Path(p).is_file()]
    if not missing:
        return
    shown = missing[:6]
    more = "" if len(missing) <= 6 else f"\n  ... and {len(missing) - 6} more"
    where = f" for {purpose}" if purpose else ""
    raise MissingDependencyError(
        f"Missing required input file(s){where}: {len(missing)} of {len(list(paths))}\n  "
        + "\n  ".join(shown) + more
        + "\n  Build the datasets with: python3 prepare_datasets.py"
        + "\n  See docs/datasets.md."
    )


def require_binaries(names=(TIC_BINARY_NAME, PIC_BINARY_NAME)) -> None:
    missing = [n for n in names if not Path(n).is_file()]
    if missing:
        raise MissingDependencyError(
            f"Missing compiled binary/binaries: {', '.join(missing)}\n"
            f"  Build them with: make\n"
            f"  Run from the repository root: the binaries resolve dict.txt "
            f"against the working directory."
        )


def require_writable_dir(path, purpose: str = "") -> None:
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MissingDependencyError(
            f"Cannot create directory {p}"
            + (f" for {purpose}" if purpose else "") + f": {exc}"
        ) from exc
    if not os.access(p, os.W_OK):
        raise MissingDependencyError(
            f"Directory is not writable: {p}"
            + (f" (needed for {purpose})" if purpose else "")
        )


def preflight(experiment: str, input_files=(), output_dirs=(), binaries=True) -> None:
    """
    Validate everything an experiment needs, before it starts.

    Raises MissingDependencyError on the first category that fails. Runners call
    this once at start-up so a three-hour benchmark never dies halfway through
    because lz4 was not installed.
    """
    spec = EXPERIMENT_REQUIREMENTS.get(experiment)
    if spec is None:
        raise KeyError(f"Unknown experiment '{experiment}'. "
                       f"Known: {sorted(EXPERIMENT_REQUIREMENTS)}")

    require_python_version()
    require_python_packages(spec["python"], purpose=f"the {experiment} experiment")
    require_executables(spec["executables"], purpose=f"the {experiment} experiment")
    if binaries:
        require_binaries()
    if input_files:
        require_input_files(input_files, purpose=f"the {experiment} experiment")
    for d in output_dirs:
        require_writable_dir(d, purpose=f"the {experiment} experiment")
