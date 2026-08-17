#!/usr/bin/env python3

from pathlib import Path

# =====================================================
# CONFIG
# =====================================================

FILE = "../textFiles/file-parallel.txt"

# =====================================================
# MAIN
# =====================================================

def main():

    p = Path(FILE)

    if not p.exists():
        print(f"[ERROR] File not found: {FILE}")
        return

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
    print(f"File            : {FILE}")
    print(f"Total lines     : {total_lines}")
    print(f"Longest line no : {max_line_no}")
    print(f"Longest length  : {max_len}")

    print("\n===== LINE PREVIEW =====")
    print(max_preview)

    print("\n========================")


if __name__ == "__main__":
    main()