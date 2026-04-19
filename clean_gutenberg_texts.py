#!/usr/bin/env python3
"""
clean_gutenberg_texts.py

Clean Project Gutenberg text files by removing:
1. Everything before and including:
   *** START OF THE PROJECT GUTENBERG EBOOK ...
2. Everything from and including:
   *** END OF THE PROJECT GUTENBERG EBOOK ...

The script writes cleaned copies into a separate output directory
and keeps the original files unchanged.

Example:
    python clean_gutenberg_texts.py \
        --input-dir data/raw \
        --output-dir data/cleaned
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


START_PATTERNS = [
    re.compile(r"^\*\*\*\s*START OF THE PROJECT GUTENBERG EBOOK.*$", re.IGNORECASE),
    re.compile(r"^\*\*\*\s*START OF THIS PROJECT GUTENBERG EBOOK.*$", re.IGNORECASE),
]

END_PATTERNS = [
    re.compile(r"^\*\*\*\s*END OF THE PROJECT GUTENBERG EBOOK.*$", re.IGNORECASE),
    re.compile(r"^\*\*\*\s*END OF THIS PROJECT GUTENBERG EBOOK.*$", re.IGNORECASE),
]


@dataclass
class CleanRecord:
    input_file: str
    output_file: str
    original_size_bytes: int
    cleaned_size_bytes: int
    status: str
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean Gutenberg text files by removing Gutenberg header/footer boilerplate."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing raw Gutenberg .txt files."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write cleaned .txt files."
    )
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        default=Path("gutenberg_cleaning_results.csv"),
        help="CSV file to store cleaning metadata."
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="_cleaned",
        help="Suffix to append before .txt in output filenames."
    )
    return parser.parse_args()


def find_first_match_line(lines: list[str], patterns: list[re.Pattern]) -> Optional[int]:
    for i, line in enumerate(lines):
        for pattern in patterns:
            if pattern.match(line.strip()):
                return i
    return None


def clean_one_text(text: str) -> tuple[str, str]:
    """
    Returns (cleaned_text, note).
    """
    lines = text.splitlines(keepends=True)

    start_idx = find_first_match_line(lines, START_PATTERNS)
    end_idx = find_first_match_line(lines, END_PATTERNS)

    if start_idx is None and end_idx is None:
        return text, "No Gutenberg start/end markers found"

    if start_idx is not None:
        lines = lines[start_idx + 1:]

        # end index must be recomputed after trimming the front part
        end_idx = find_first_match_line(lines, END_PATTERNS)
    else:
        end_idx = find_first_match_line(lines, END_PATTERNS)

    if end_idx is not None:
        lines = lines[:end_idx]

    cleaned = "".join(lines).strip() + "\n"
    return cleaned, ""


def build_output_name(input_path: Path, suffix: str) -> str:
    if input_path.suffix.lower() == ".txt":
        return input_path.stem + suffix + ".txt"
    return input_path.name + suffix


def write_metadata(records: list[CleanRecord], csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "input_file",
                "output_file",
                "original_size_bytes",
                "cleaned_size_bytes",
                "status",
                "note",
            ],
        )
        writer.writeheader()
        for rec in records:
            writer.writerow(asdict(rec))


def main() -> int:
    args = parse_args()

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(args.input_dir.glob("*.txt"))
    if not input_files:
        print(f"No .txt files found in {args.input_dir}")
        return 1

    records: list[CleanRecord] = []

    for in_file in input_files:
        try:
            raw_text = in_file.read_text(encoding="utf-8", errors="ignore")
            cleaned_text, note = clean_one_text(raw_text)

            out_name = build_output_name(in_file, args.suffix)
            out_file = args.output_dir / out_name
            out_file.write_text(cleaned_text, encoding="utf-8")

            rec = CleanRecord(
                input_file=str(in_file),
                output_file=str(out_file),
                original_size_bytes=in_file.stat().st_size,
                cleaned_size_bytes=out_file.stat().st_size,
                status="cleaned",
                note=note,
            )
            records.append(rec)
            print(f"Cleaned: {in_file.name} -> {out_file.name}")

        except Exception as e:
            rec = CleanRecord(
                input_file=str(in_file),
                output_file="",
                original_size_bytes=in_file.stat().st_size if in_file.exists() else 0,
                cleaned_size_bytes=0,
                status="failed",
                note=f"{type(e).__name__}: {e}",
            )
            records.append(rec)
            print(f"Failed: {in_file.name} ({e})")

    write_metadata(records, args.metadata_csv)
    print(f"\nWrote metadata: {args.metadata_csv}")
    print(f"Cleaned files directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

