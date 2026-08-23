#!/usr/bin/env python3
"""
prepare_datasets.py

Single entry point for preparing the TIC/PIC benchmark datasets.

    python3 prepare_datasets.py                 # check -> build -> verify
    python3 prepare_datasets.py check           # dependencies + local sources only
    python3 prepare_datasets.py build           # combine local sources into f1..f10
    python3 prepare_datasets.py verify          # count, sizes, and manifest refresh
    python3 prepare_datasets.py verify --sha256 # also checksum every dataset (slow)

Design rules:

  * Every stage fails loudly. A missing dependency, a missing source corpus or a
    short dataset is an error with a non-zero exit code, never a warning that is
    followed by a partial result.
  * Nothing is downloaded. The source corpora are external inputs that you
    supply locally; this artifact never crawls a live catalog.
  * All paths are repository-relative and come from dataset_config.py.

Run from the repository root (the compiled binaries resolve dict.txt the same
way).

See docs/datasets.md for the pipeline description and its known limitations.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import shutil
import sys
from pathlib import Path

from dataset_config import (
    BENCHMARK_DATASET_NAMES,
    BENCHMARK_DATASET_TARGET_MB,
    CANONICAL_DATASET_DIR,
    DATASET_DIR_ENV_VAR,
    EXPECTED_DATASET_COUNT,
    GUTENBERG_RAW_DIR,
    MANIFEST_CSV,
    MB,
    PARALLEL_DATASET_INFO,
    PARALLEL_DATASET_NAME,
    STANDARD_EBOOKS_CLEAN_DIR,
    resolve_dataset_dir,
    sha256_of,
)

UNAVAILABLE = "unavailable"

MANIFEST_FIELDS = [
    "dataset",
    "target_mb",
    "target_bytes",
    "actual_bytes",
    "actual_mb",
    "source_corpus",
    "source_files",
    "construction",
    "sha256",
    "notes",
]

# Python packages the *dataset pipeline* needs. The benchmark runners need more
# (pandas, matplotlib, psutil); those are not required to build datasets.
# Nothing here is third-party: the pipeline is pure standard library now that
# the network acquisition stage has been removed.
BUILD_REQUIREMENTS: list[tuple[str, str]] = []          # stdlib only


class StageError(RuntimeError):
    """A pipeline stage could not complete. Always fatal."""


# =====================
# Reporting helpers
# =====================

def info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"[ OK ] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[WARN] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr, flush=True)


def human_mb(n_bytes: int) -> str:
    return f"{n_bytes / MB:,.2f} MB"


# =====================
# Stage: check
# =====================

def missing_packages(requirements: list[tuple[str, str]]) -> list[str]:
    missing = []
    for module_name, pip_name in requirements:
        if importlib.util.find_spec(module_name) is None:
            missing.append(pip_name)
    return missing


def check_dependencies() -> None:
    info(f"Python {sys.version.split()[0]} at {sys.executable}")

    reqs = list(BUILD_REQUIREMENTS)

    if not reqs:
        ok("No third-party packages required for this stage (standard library only).")
        return

    missing = missing_packages(reqs)
    if missing:
        raise StageError(
            "Missing required Python package(s): "
            + ", ".join(missing)
            + "\n       Install them with: python3 -m pip install "
            + " ".join(missing)
        )
    ok(f"All {len(reqs)} required package(s) present.")


def check_sources(strict: bool) -> dict[str, int]:
    """
    Report the source corpora. With strict=True a missing or empty corpus is an
    error, because the build stage cannot proceed without source text.
    """
    counts: dict[str, int] = {}

    for d in (STANDARD_EBOOKS_CLEAN_DIR, GUTENBERG_RAW_DIR):
        path = Path(d)
        counts[d] = len(list(path.glob("*.txt"))) if path.is_dir() else 0

    found_any = any(counts.values())

    # A single missing corpus is only a warning: the build can proceed from the
    # other one (and will fail loudly later if the text runs out). It is fatal
    # only when no source text exists at all.
    for d, n in counts.items():
        if not Path(d).is_dir():
            warn(f"source corpus missing: {d}/")
        else:
            (ok if n else warn)(f"source corpus {d}/: {n} .txt file(s)")

    if strict and not found_any:
        raise StageError(
            "No local source text found.\n"
            "       This artifact does not download or crawl anything. The source\n"
            "       corpora are external inputs that you must supply locally.\n"
            "\n"
            "       Expected, relative to the repository root:\n"
            f"         {STANDARD_EBOOKS_CLEAN_DIR}/*.txt\n"
            "             cleaned Standard Ebooks plain text (one file per book)\n"
            f"         {GUTENBERG_RAW_DIR}/*.txt\n"
            "             raw Project Gutenberg text; clean it first with\n"
            "             clean_gutenberg_texts.py --input-dir ... --output-dir ...\n"
            "\n"
            "       Either directory alone is enough to build the smaller datasets;\n"
            "       the largest (f10, 769 MB) needs roughly 769 MB of text in total.\n"
            "       See docs/datasets.md for what these corpora are and where they\n"
            "       come from."
        )

    return counts


def check_disk_space(dataset_dir: Path, required_bytes: int) -> None:
    target = dataset_dir if dataset_dir.exists() else Path(".")
    free = shutil.disk_usage(target).free
    if free < required_bytes:
        raise StageError(
            f"Insufficient disk space in {target}/: {human_mb(free)} free, "
            f"{human_mb(required_bytes)} required for f1..f10."
        )
    ok(f"Disk space: {human_mb(free)} free, {human_mb(required_bytes)} required.")


def stage_check(dataset_dir: Path, strict_sources: bool = False) -> int:
    info("=== Stage: check ===")
    check_dependencies()

    resolved = resolve_dataset_dir()
    info(f"Canonical dataset directory : {CANONICAL_DATASET_DIR}/")
    info(f"Resolved dataset directory  : {resolved}/")
    if os.environ.get(DATASET_DIR_ENV_VAR, "").strip():
        info(f"(resolved from ${DATASET_DIR_ENV_VAR})")

    check_sources(strict=strict_sources)

    total = sum(BENCHMARK_DATASET_TARGET_MB.values()) * MB
    check_disk_space(dataset_dir, total)

    info(f"Expected datasets: {EXPECTED_DATASET_COUNT} "
         f"({BENCHMARK_DATASET_NAMES[0]} .. {BENCHMARK_DATASET_NAMES[-1]})")
    return 0


# =====================
# Source corpora
# =====================
#
# This artifact does NOT download or crawl anything. The acquisition scripts
# that once crawled Standard Ebooks and Project Gutenberg have been removed:
# a public artifact should not depend on live, changing external catalogs.
#
# The source corpora are EXTERNAL INPUTS that you supply locally. See
# docs/datasets.md for what they are and where they come from.

# =====================
# Stage: build
# =====================

def stage_build(dataset_dir: Path, mode: str, exact: bool) -> int:
    info("=== Stage: build ===")
    check_sources(strict=True)

    dataset_dir.mkdir(parents=True, exist_ok=True)

    # Imported here so `check` and `verify` stay importable even if this module
    # is edited; also keeps the dependency surface of those stages minimal.
    import make_combined_text_files as combiner

    try:
        written = combiner.build_datasets(dataset_dir, mode=mode, exact=exact)
    except RuntimeError as exc:
        raise StageError(str(exc)) from exc

    ok(f"Built {len(written)} dataset(s) in {dataset_dir}/")
    return 0


# =====================
# Stage: verify
# =====================

def read_source_list(dataset_dir: Path, name: str) -> str:
    """Number of source files recorded for a dataset by the combine stage."""
    p = dataset_dir / "manifests" / f"{name}.sources.txt"
    if not p.is_file():
        return UNAVAILABLE
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return f"{len(lines)} source files (see manifests/{name}.sources.txt)"


def collect_manifest_rows(dataset_dir: Path, with_sha256: bool, construction: str) -> list[dict]:
    rows = []
    for name in BENCHMARK_DATASET_NAMES:
        target_mb = BENCHMARK_DATASET_TARGET_MB[name]
        path = dataset_dir / name
        present = path.is_file()

        if present:
            size = path.stat().st_size
            actual_bytes: object = size
            actual_mb: object = f"{size / MB:.3f}"
            digest = sha256_of(path) if with_sha256 else UNAVAILABLE
            notes = "" if size == target_mb * MB else "size differs from target"
        else:
            actual_bytes = UNAVAILABLE
            actual_mb = UNAVAILABLE
            digest = UNAVAILABLE
            notes = "dataset not present locally"

        rows.append({
            "dataset": name,
            "target_mb": target_mb,
            "target_bytes": target_mb * MB,
            "actual_bytes": actual_bytes,
            "actual_mb": actual_mb,
            "source_corpus": "Standard Ebooks -> Project Gutenberg (read in that order)",
            "source_files": read_source_list(dataset_dir, name) if present else UNAVAILABLE,
            "construction": construction,
            "sha256": digest,
            "notes": notes,
        })

    # The parallel experiments use a separate input whose provenance was never
    # recorded. It is listed so the gap is explicit rather than invisible.
    ppath = dataset_dir / PARALLEL_DATASET_NAME
    ppresent = ppath.is_file()
    rows.append({
        "dataset": PARALLEL_DATASET_NAME,
        "target_mb": UNAVAILABLE,
        "target_bytes": UNAVAILABLE,
        "actual_bytes": ppath.stat().st_size if ppresent else UNAVAILABLE,
        "actual_mb": f"{ppath.stat().st_size / MB:.3f}" if ppresent else UNAVAILABLE,
        "source_corpus": UNAVAILABLE,
        "source_files": UNAVAILABLE,
        "construction": UNAVAILABLE,
        "sha256": sha256_of(ppath) if (ppresent and with_sha256) else UNAVAILABLE,
        "notes": (
            "Parallel benchmark input for run_parallel_benchmarks.py. "
            "HISTORICAL PROVENANCE UNKNOWN: no script in this repository produces "
            "it, it was never tracked in Git, and no documentation describes it. "
            "Size, source corpus and construction are deliberately left "
            "unavailable rather than inferred. Supply an input explicitly with "
            "--input. See docs/datasets.md section 7."
        ),
    })
    return rows


def write_manifest(dataset_dir: Path, rows: list[dict]) -> Path:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    path = dataset_dir / MANIFEST_CSV
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def stage_verify(dataset_dir: Path, with_sha256: bool, construction: str,
                 strict: bool = True) -> int:
    info("=== Stage: verify ===")
    info(f"Dataset directory: {dataset_dir}/")

    present = [n for n in BENCHMARK_DATASET_NAMES if (dataset_dir / n).is_file()]
    missing = [n for n in BENCHMARK_DATASET_NAMES if n not in present]

    for name in BENCHMARK_DATASET_NAMES:
        path = dataset_dir / name
        target = BENCHMARK_DATASET_TARGET_MB[name] * MB
        if path.is_file():
            size = path.stat().st_size
            delta = size - target
            mark = "exact" if delta == 0 else f"{delta:+,d} B vs target"
            ok(f"{name:<9} {human_mb(size):>12}  (target {human_mb(target):>12}, {mark})")
        else:
            warn(f"{name:<9} {'missing':>12}  (target {human_mb(target):>12})")

    if with_sha256 and present:
        info("Computing SHA-256 checksums (this reads every byte)...")

    rows = collect_manifest_rows(dataset_dir, with_sha256=with_sha256,
                                 construction=construction)
    manifest_path = write_manifest(dataset_dir, rows)
    ok(f"Manifest written: {manifest_path}")

    info(f"Datasets present: {len(present)}/{EXPECTED_DATASET_COUNT}")

    if missing:
        msg = (f"Expected {EXPECTED_DATASET_COUNT} datasets, found {len(present)}. "
               f"Missing: {', '.join(missing)}")
        if strict:
            raise StageError(
                msg + "\n       Run `python3 prepare_datasets.py build` after the "
                      "source corpora are in place. Do not benchmark a partial set."
            )
        warn(msg)

    if not (dataset_dir / PARALLEL_DATASET_NAME).is_file():
        warn(f"{PARALLEL_DATASET_NAME} is absent; run_parallel_benchmarks.py cannot run.")

    return 0


# =====================
# CLI
# =====================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the TIC/PIC benchmark datasets (f1..f10).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "With no subcommand: check -> build -> verify (no network access).\n"
            "See docs/datasets.md for provenance and known limitations."
        ),
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help=f"Override the dataset directory (default: ${DATASET_DIR_ENV_VAR} "
             f"or {CANONICAL_DATASET_DIR}/).",
    )
    parser.add_argument(
        "--mode",
        choices=("nested", "sequential"),
        default="nested",
        help="Dataset construction mode (default: nested; see docs/datasets.md).",
    )
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--exact", dest="exact", action="store_true", default=True,
                      help="Trim datasets to exactly their target size (default).")
    size.add_argument("--whole-files", dest="exact", action="store_false",
                      help="Stop at whole-file boundaries, overshooting the target.")
    parser.add_argument("--sha256", action="store_true",
                        help="Compute SHA-256 for every dataset during verify.")

    sub = parser.add_subparsers(dest="stage")
    sub.add_parser("check", help="Validate dependencies, sources and disk space.")
    sub.add_parser("build", help="Combine source corpora into f1..f10.")
    sub.add_parser("verify", help="Check count and sizes; refresh the manifest.")
    sub.add_parser("manifest", help="Refresh datasets/manifest.csv only.")
    sub.add_parser("all", help="check -> build -> verify (no network).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    dataset_dir = args.dataset_dir or Path(resolve_dataset_dir())
    construction = (
        f"{args.mode}; {'exact-trim' if args.exact else 'whole-file'}; "
        "make_combined_text_files.py"
    )
    stage = args.stage or "all"

    try:
        if stage == "check":
            return stage_check(dataset_dir)

        if stage == "build":
            stage_check(dataset_dir, strict_sources=True)
            return stage_build(dataset_dir, args.mode, args.exact)

        if stage == "verify":
            return stage_verify(dataset_dir, args.sha256, construction)

        if stage == "manifest":
            return stage_verify(dataset_dir, args.sha256, construction, strict=False)

        # default: all
        stage_check(dataset_dir, strict_sources=True)
        stage_build(dataset_dir, args.mode, args.exact)
        return stage_verify(dataset_dir, args.sha256, construction)

    except StageError as exc:
        fail(str(exc))
        return 1
    except KeyboardInterrupt:
        fail("Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
