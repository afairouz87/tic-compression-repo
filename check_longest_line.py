#!/usr/bin/env python3

import argparse
from pathlib import Path

from dataset_config import PARALLEL_INPUT_FILE

# =====================================================
# CONFIG
# =====================================================

# Default only; --input overrides it. Resolved through the canonical dataset
# directory (dataset_config.py).
#
# TIC divides work between threads by line (epic-v3.1.cpp, "Divide lines among
# threads"), so the longest line in the parallel input bounds how evenly work
# can be split. That is what this utility measures.
FILE = PARALLEL_INPUT_FILE

# =====================================================
# MAIN
# =====================================================

def main():

    parser = argparse.ArgumentParser(
        description="Report the longest line of a parallel-benchmark input file.",
    )
    parser.add_argument(
        "--input",
        default=FILE,
        metavar="PATH",
        help=f"File to analyse (default: {FILE}).",
    )
    args = parser.parse_args()

    p = Path(args.input)

    if not p.exists():
        print(f"[ERROR] File not found: {args.input}")
        return 1

    max_len = 0
    max_line_no = 0
    max_preview = ""

    total_lines = 0

    with p.open(
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        for i, line in enumerate(f, 1):

            total_lines += 1

            line_len = len(line)

            if line_len > max_len:

                max_len = line_len
                max_line_no = i

                max_preview = (
                    line[:200]
                    .replace("\n", " ")
                    .replace("\r", " ")
                )

    print("\n===== FILE ANALYSIS =====")
    print(f"File            : {args.input}")
    print(f"Total lines     : {total_lines}")
    print(f"Longest line no : {max_line_no}")
    print(f"Longest length  : {max_len}")

    print("\n===== LINE PREVIEW =====")
    print(max_preview)

    print("\n========================")


if __name__ == "__main__":
    main()