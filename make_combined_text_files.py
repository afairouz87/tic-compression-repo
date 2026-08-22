#!/usr/bin/env python3
"""
make_combined_text_files.py

Stage 6 of the dataset pipeline: combine the cleaned source corpora into the
benchmark datasets f1.txt ... f10.txt.

Normally invoked through `prepare_datasets.py`, which validates dependencies
and sources first. It can still be run directly.

Construction (see docs/datasets.md for the evidence behind this):

  nested (default)  Every output file restarts from the beginning of the sorted
                    source list, so f1 is a prefix of f2 is a prefix of f3, and
                    so on. This is what the committed version of this script
                    did, and it is consistent with the published results.

  sequential        Each output file continues where the previous one stopped,
                    producing ten disjoint datasets. This was an earlier variant
                    (it survived as a commented-out block in the committed file)
                    and needs ~3.3 GB of distinct source text rather than ~769 MB.

Sizing:

  --exact (default) Trim each output to exactly its target size, so the datasets
                    are byte-reproducible and match the sizes in the paper.
  --whole-files     Stop at the first whole source file that reaches the target,
                    overshooting slightly. This is the literal behaviour of the
                    committed script.

The text-normalisation functions below are unchanged from the committed version
and must stay that way: altering them would change the datasets' statistical
properties and invalidate comparison against the published results.
"""

from pathlib import Path
import argparse
import re
import sys
import textwrap
import unicodedata

from dataset_config import (
    BENCHMARK_DATASET_TARGET_MB,
    CANONICAL_DATASET_DIR,
    MB,
    SOURCE_DIRS,
)

# =========================
# CONFIG
# =========================

# Source directories, in the order they are read. The order determines the
# content of every output file and must not be changed casually.
INPUT_DIRS = [Path(d) for d in SOURCE_DIRS]

# Canonical dataset directory (see dataset_config.py).
OUTPUT_DIR = Path(CANONICAL_DATASET_DIR)

# Target sizes in MiB. Defined once in dataset_config.py.
TARGET_FILES_MB = dict(BENCHMARK_DATASET_TARGET_MB)

SEPARATOR = "\n\n"


# =========================
# HELPERS
# =========================

def normalize_ascii_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text

def collect_txt_files(input_dirs):
    files = []

    for folder in input_dirs:
        if not folder.exists():
            print(f"[WARNING] Folder not found: {folder}")
            continue

        files.extend(sorted(folder.glob("*.txt")))

    return files


# def normalize_text(text: str) -> str:
#     text = text.replace("\ufeff", "")
#     text = text.replace("\r\n", "\n").replace("\r", "\n")
#     text = re.sub(r"[ \t]+\n", "\n", text)
#     text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", text)
#     return text.strip() + "\n"
def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Convert to ASCII-only text
    text = text.encode("ascii", "ignore").decode("ascii")

    # Remove non-printable ASCII characters
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", text)

    # Remove trailing spaces before newlines
    text = re.sub(r"[ \t]+\n", "\n", text)

    # Put sentence-ending punctuation on separate lines
    text = re.sub(r'([.!?]["\']?)\s+', r"\1\n", text)

    # Safety wrapper for very long lines
    wrapped_lines = []
    MAX_LINE_LENGTH = 1000

    for line in text.splitlines():
        if len(line) > MAX_LINE_LENGTH:
            wrapped_lines.extend(
                textwrap.wrap(
                    line,
                    width=MAX_LINE_LENGTH,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
            )
        else:
            wrapped_lines.append(line)

    return "\n".join(wrapped_lines).strip() + "\n"


def utf8_trim_to_bytes(text: str, max_bytes: int) -> str:
    """
    Trim text to fit within max_bytes without breaking UTF-8 characters.
    """
    encoded = text.encode("utf-8")

    if len(encoded) <= max_bytes:
        return text

    trimmed = encoded[:max_bytes]

    while True:
        try:
            return trimmed.decode("utf-8")
        except UnicodeDecodeError:
            trimmed = trimmed[:-1]


def file_size_mb(path: Path) -> float:
    return path.stat().st_size / MB


# =========================
# MAIN
# =========================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Combine cleaned source corpora into benchmark datasets f1..f10.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Destination directory (default: {OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--mode",
        choices=("nested", "sequential"),
        default="nested",
        help=(
            "nested: every output restarts from the first source file, so f1 is a "
            "prefix of f2 (default, matches the committed script). "
            "sequential: outputs are disjoint and consume the corpus in order."
        ),
    )
    size = parser.add_mutually_exclusive_group()
    size.add_argument(
        "--exact",
        dest="exact",
        action="store_true",
        default=True,
        help="Trim each output to exactly its target size (default).",
    )
    size.add_argument(
        "--whole-files",
        dest="exact",
        action="store_false",
        help="Stop at a whole-file boundary, overshooting the target slightly.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="NAME",
        help="Build only these datasets (e.g. --only f1.txt f2.txt).",
    )
    return parser.parse_args(argv)


def build_datasets(output_dir, mode="nested", exact=True, only=None):
    """
    Build the benchmark datasets. Returns the list of paths written.

    Raises RuntimeError if the source corpora cannot supply enough text; the
    caller is expected to fail loudly rather than continue with a short dataset.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    source_files = collect_txt_files(INPUT_DIRS)

    if not source_files:
        raise RuntimeError(
            "No input .txt files found. Expected cleaned corpora in: "
            + ", ".join(str(d) for d in INPUT_DIRS)
        )

    print(f"[INFO] Found {len(source_files)} source text files.")
    print(f"[INFO] Mode: {mode}; sizing: {'exact' if exact else 'whole-files'}")
    print(f"[INFO] Output directory: {output_dir}")

    targets = dict(TARGET_FILES_MB)
    if only:
        missing = [n for n in only if n not in targets]
        if missing:
            raise RuntimeError(f"Unknown dataset name(s): {', '.join(missing)}")
        targets = {n: targets[n] for n in only}

    written_paths = []

    # In sequential mode the source cursor persists across output files.
    file_index = 0

    for output_name, target_mb in targets.items():
        if mode == "nested":
            file_index = 0  # restart source files for every output file

        target_bytes = target_mb * MB
        output_path = output_dir / output_name

        print(f"\n[INFO] Creating {output_name} with target size {target_mb} MB")

        written_bytes = 0

        # Per-dataset source lists live in a subdirectory so they never collide
        # with a *.txt glob over the dataset directory itself.
        manifest_dir = output_dir / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"{output_name}.sources.txt"

        with open(output_path, "w", encoding="utf-8") as out, open(manifest_path, "w", encoding="utf-8") as manifest:
            while written_bytes < target_bytes:
                if file_index >= len(source_files):
                    raise RuntimeError(
                        f"Not enough source text to reach the target size for "
                        f"{output_name} ({target_mb} MB). Reached "
                        f"{written_bytes / MB:.2f} MB after consuming all "
                        f"{len(source_files)} source files. Acquire more source "
                        f"text before rebuilding; do not use a short dataset."
                    )

                src_path = source_files[file_index]
                file_index += 1

                manifest.write(f"{src_path}\n")
                print(f"[DEBUG] {output_name}: adding {src_path}", flush=True)

                try:
                    text = src_path.read_text(encoding="utf-8", errors="ignore")
                except Exception as exc:
                    print(f"[WARNING] Skipping {src_path}: {exc}")
                    continue

                text = normalize_text(text)
                text = normalize_ascii_text(text)


                if not text:
                    continue

                text_to_add = text + SEPARATOR

                if exact:
                    remaining = target_bytes - written_bytes
                    if len(text_to_add.encode("utf-8")) > remaining:
                        text_to_add = utf8_trim_to_bytes(text_to_add, remaining)

                out.write(text_to_add)
                out.flush()

                written_bytes += len(text_to_add.encode("utf-8"))

        actual = output_path.stat().st_size
        status = "exact" if actual == target_bytes else f"{actual - target_bytes:+d} B vs target"
        print(f"[DONE] {output_name}: {file_size_mb(output_path):.2f} MB ({status})")
        written_paths.append(output_path)

    return written_paths


def main(argv=None):
    args = parse_args(argv)

    try:
        written = build_datasets(
            output_dir=args.output_dir,
            mode=args.mode,
            exact=args.exact,
            only=args.only,
        )
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"\n[INFO] Finished creating {len(written)} combined text file(s).")
    print(f"[INFO] Output folder: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

