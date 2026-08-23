#!/usr/bin/env python3
"""
dataset_config.py

Single authoritative definition of the benchmark dataset layout: where the
datasets live, what they are called, and how large each one is meant to be.

This module deliberately imports nothing outside the standard library so that
lightweight utilities (and `prepare_datasets.py`) can use it without pulling in
pandas or matplotlib. `benchmark_utils` re-exports these names, so benchmark
runners may import them from either module.

Canonical layout
----------------
    <repo root>/datasets/f1.txt ... f10.txt
    <repo root>/datasets/file-parallel.txt
    <repo root>/datasets/manifest.csv

Historically the published results were produced from `../textFiles/`, a
sibling directory outside the repository. That layout is still honoured as a
fallback so an existing local copy does not have to be moved, but `datasets/`
is the canonical location for new work.

All paths are repository-relative. No absolute or machine-specific path is
used anywhere in this module.
"""

from __future__ import annotations

import os

MB = 1024 * 1024

# =====================
# Dataset location
# =====================

DATASET_DIR_ENV_VAR = "TIC_DATASET_DIR"

CANONICAL_DATASET_DIR = "datasets"

# Legacy location used to produce the published results. Kept as a fallback
# only; new datasets are written to CANONICAL_DATASET_DIR.
LEGACY_DATASET_DIR = os.path.join("..", "textFiles")


def resolve_dataset_dir() -> str:
    """
    Resolve the dataset directory, in this order:

      1. $TIC_DATASET_DIR, if set and non-empty
      2. ./datasets        canonical layout
      3. ../textFiles      legacy layout, if it exists
      4. ./datasets        default when neither exists yet

    Resolution is relative to the current working directory, which for this
    repository is always the repository root (the compiled binaries resolve
    `dict.txt` the same way).
    """
    override = os.environ.get(DATASET_DIR_ENV_VAR, "").strip()
    if override:
        return override

    for candidate in (CANONICAL_DATASET_DIR, LEGACY_DATASET_DIR):
        if os.path.isdir(candidate):
            return candidate

    return CANONICAL_DATASET_DIR


DATASET_DIR = resolve_dataset_dir()


def dataset_path(name: str, dataset_dir: str | None = None) -> str:
    """Return the path to a named dataset inside the resolved dataset directory."""
    return os.path.join(dataset_dir if dataset_dir is not None else DATASET_DIR, name)


# =====================
# Dataset inventory
# =====================

# Target sizes in MiB (1 MiB = 1024 * 1024 bytes), as used by the paper.
# These are the sizes reported in the "Original Size (MB)" column of
# cr_results.csv. See docs/datasets.md for provenance.
BENCHMARK_DATASET_TARGET_MB: dict[str, int] = {
    "f1.txt": 50,
    "f2.txt": 100,
    "f3.txt": 137,
    "f4.txt": 150,
    "f5.txt": 200,
    "f6.txt": 347,
    "f7.txt": 400,
    "f8.txt": 500,
    "f9.txt": 634,
    "f10.txt": 769,
}

BENCHMARK_DATASET_NAMES: list[str] = list(BENCHMARK_DATASET_TARGET_MB)

EXPECTED_DATASET_COUNT = len(BENCHMARK_DATASET_NAMES)  # 10

# ---------------------------------------------------------------------------
# Parallel-experiment input
# ---------------------------------------------------------------------------
# run_parallel_benchmarks.py takes a single input file, separate from f1..f10.
#
# PROVENANCE: UNKNOWN. An exhaustive search of the working tree and of the full
# Git history found no script that produces this file, no commit that ever
# tracked it, and no documentation that describes it -- not even
# README_benchmark_verification.md, which otherwise covers the parallel runner
# step by step. Its size, source corpus and construction method were never
# recorded, and nothing here should be read as claiming otherwise.
#
# The one related artefact is check_longest_line.py, a utility that measures the
# longest line of exactly this file. TIC divides work between threads by line
# (epic-v3.1.cpp, "Divide lines among threads"), so line structure mattered for
# the parallel experiments.
#
# See docs/datasets.md section 7 for the full evidence and its classification.
PARALLEL_DATASET_NAME = "file-parallel.txt"

PARALLEL_DATASET_INFO = {
    "logical_name": PARALLEL_DATASET_NAME,
    "role": "parallel benchmark input",
    "required_for": "parallel compression, decompression, search and replace experiments",
    "runner": "run_parallel_benchmarks.py",
    "historical_provenance": "unknown",
    "historical_size": "unknown",
    "historical_construction": "unknown",
    "produced_by_pipeline": False,
    "notes": (
        "Not produced by make_combined_text_files.py. Never tracked in Git. "
        "Supply it explicitly with --input, or choose a reproducible substitute; "
        "see docs/datasets.md section 7."
    ),
}


def sha256_of(path, chunk: int = 8 * 1024 * 1024) -> str:
    """SHA-256 over the raw bytes of a file, read in blocks."""
    import hashlib
    from pathlib import Path as _Path

    digest = hashlib.sha256()
    with _Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def benchmark_input_files(dataset_dir: str | None = None) -> list[str]:
    """Paths to f1.txt ... f10.txt, in benchmark order."""
    return [dataset_path(n, dataset_dir) for n in BENCHMARK_DATASET_NAMES]


def parallel_input_file(dataset_dir: str | None = None) -> str:
    """Path to the parallel-experiment input file."""
    return dataset_path(PARALLEL_DATASET_NAME, dataset_dir)


BENCHMARK_INPUT_FILES: list[str] = benchmark_input_files()
PARALLEL_INPUT_FILE: str = parallel_input_file()

# =====================
# Source corpora
# =====================

# Stage outputs of the acquisition pipeline, in the order the combine step
# reads them. Order matters: it determines the content of f1..f10.
STANDARD_EBOOKS_CLEAN_DIR = os.path.join("standard_ebooks_output", "txt_clean")
GUTENBERG_RAW_DIR = os.path.join("gutenberg_ebooks", "raw")

SOURCE_DIRS = [STANDARD_EBOOKS_CLEAN_DIR, GUTENBERG_RAW_DIR]

MANIFEST_CSV = "manifest.csv"

# ---------------------------------------------------------------------------
# Generated-output layout
# ---------------------------------------------------------------------------
# Experiment output is written under results/, never into the repository root.
# Previously every runner used RESULTS_DIR = ".", so a run overwrote the
# committed baseline in place and scattered CSVs, tables and figures among the
# source files.
#
#   results/raw/      *_results.csv   measurements
#   results/tables/   *_table.tex     LaTeX tables built from the CSVs
#   results/figures/  *.png           plots built from the CSVs
#   results/logs/     per-experiment stdout/stderr captures
#   results/tmp/      scratch space
#
# All paths are repository-relative. Runners create these directories on demand
# via dependencies.require_writable_dir(). The whole tree is git-ignored.

RESULTS_ROOT = "results"
RESULTS_RAW_DIR = os.path.join(RESULTS_ROOT, "raw")
RESULTS_TABLES_DIR = os.path.join(RESULTS_ROOT, "tables")
RESULTS_FIGURES_DIR = os.path.join(RESULTS_ROOT, "figures")
RESULTS_LOGS_DIR = os.path.join(RESULTS_ROOT, "logs")
RESULTS_TMP_DIR = os.path.join(RESULTS_ROOT, "tmp")


def results_path(kind: str, name: str) -> str:
    """kind is one of: raw, tables, figures, logs, tmp."""
    dirs = {
        "raw": RESULTS_RAW_DIR, "tables": RESULTS_TABLES_DIR,
        "figures": RESULTS_FIGURES_DIR, "logs": RESULTS_LOGS_DIR,
        "tmp": RESULTS_TMP_DIR,
    }
    if kind not in dirs:
        raise KeyError(f"Unknown results kind {kind!r}; expected one of {sorted(dirs)}")
    return os.path.join(dirs[kind], name)


# ---------------------------------------------------------------------------
# Dictionary
# ---------------------------------------------------------------------------
# Both binaries load a dictionary at start-up for every operation. The path is
# resolved identically by the C++ (resolveDictionaryPath) and by this module:
#
#   1. $TIC_DICT_PATH, if set and non-empty
#   2. ./dict.txt      relative to the current working directory (historical default)
#
# See docs/dictionary.md.

DICT_PATH_ENV_VAR = "TIC_DICT_PATH"
DEFAULT_DICT_FILENAME = "dict.txt"


def resolve_dict_path() -> str:
    """Resolve the dictionary path exactly as the C++ binaries do."""
    override = os.environ.get(DICT_PATH_ENV_VAR, "").strip()
    return override if override else DEFAULT_DICT_FILENAME


# Fingerprint of the dictionary used by the published artifact, measured from
# the tracked file on 2026-08-23. This identifies the historical dictionary; it
# is NOT a licence grant and does not authorise redistribution of the contents.
# See docs/licensing.md section 3.
HISTORICAL_DICT = {
    "filename": DEFAULT_DICT_FILENAME,
    "sha256": "9b1d044dcca20e959a241656ecdeff0d59f37fe0a59499cec77a19d355cae3b8",
    "size_bytes": 2823482,
    "entries": 333350,
    "newline": "LF",
    "trailing_newline": True,
    "structure": "17 punctuation entries, then 333,333 words from the frequency CSV, in rank order",
    "provenance": "derived from the Kaggle English Word Frequency dataset; data licence unresolved",
}

__all__ = [
    "MB",
    "DATASET_DIR_ENV_VAR",
    "CANONICAL_DATASET_DIR",
    "LEGACY_DATASET_DIR",
    "DATASET_DIR",
    "resolve_dataset_dir",
    "dataset_path",
    "BENCHMARK_DATASET_TARGET_MB",
    "BENCHMARK_DATASET_NAMES",
    "EXPECTED_DATASET_COUNT",
    "PARALLEL_DATASET_NAME",
    "PARALLEL_DATASET_INFO",
    "sha256_of",
    "benchmark_input_files",
    "parallel_input_file",
    "BENCHMARK_INPUT_FILES",
    "PARALLEL_INPUT_FILE",
    "STANDARD_EBOOKS_CLEAN_DIR",
    "GUTENBERG_RAW_DIR",
    "SOURCE_DIRS",
    "MANIFEST_CSV",
    "RESULTS_ROOT",
    "RESULTS_RAW_DIR",
    "RESULTS_TABLES_DIR",
    "RESULTS_FIGURES_DIR",
    "RESULTS_LOGS_DIR",
    "RESULTS_TMP_DIR",
    "results_path",
    "DICT_PATH_ENV_VAR",
    "DEFAULT_DICT_FILENAME",
    "resolve_dict_path",
    "HISTORICAL_DICT",
]
