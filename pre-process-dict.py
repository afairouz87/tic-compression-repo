#!/usr/bin/env python3
"""
pre-process-dict.py

Build the TIC/PIC dictionary (`dict.txt`) from a word-frequency CSV.

    python3 pre-process-dict.py --input /path/to/unigram_freq.csv --output dict.txt

The frequency CSV is a third-party dataset that is NOT distributed with this
repository and is NOT downloaded by this script: its licence could not be
reliably established (docs/licensing.md section 3). The reviewer supplies it.

Transformation
--------------
Established empirically from the historical `dict.txt`, not guessed. In that
file, lines 18..end are byte-identical to column 1 of the frequency CSV, in the
CSV's own order, with 17 punctuation entries prepended. This script reproduces
exactly that:

    1. write the 17 punctuation entries, in the historical order
    2. write column 1 of every CSV row, in file order, verbatim

`--no-punctuation` writes only step 2, which is what the committed version of
this script did.

Why the details matter (all established from the C++ in
Build_Dictionary_Table_Compression / _Decompression):

  * ORDER IS SIGNIFICANT. Entry N receives code word N + CODE_WORD_OFFSET.
    Reordering, inserting or dropping a single entry renumbers everything after
    it and changes the compressed output.
  * The whole line is the entry. No comma splitting, no whitespace stripping.
  * Line endings matter: the C++ splits on '\\n' only, so a CRLF file would
    leave '\\r' at the end of every entry. This script always writes LF.

See docs/dictionary.md.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

# The 17 punctuation entries that precede the word list in the historical
# dict.txt, in their exact historical order (verified byte-for-byte).
PUNCTUATION_ENTRIES = [
    ",", ".", "-", ":", "?", "(", ")", "!", ";",
    "/", "\\", '"', "“", "”", "'", "’", "`",
]

HEADER_HINTS = {"word", "words", "term", "token"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build dict.txt from a word-frequency CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The frequency CSV is not distributed with this repository and is not\n"
            "downloaded by this script. See docs/dictionary.md."
        ),
    )
    parser.add_argument("--input", required=True, type=Path, metavar="CSV",
                        help="Word-frequency CSV. Column 1 must be the word.")
    parser.add_argument("--output", required=True, type=Path, metavar="TXT",
                        help="Dictionary file to write (e.g. dict.txt).")
    parser.add_argument("--no-punctuation", action="store_true",
                        help="Omit the 17 leading punctuation entries (the committed "
                             "script's behaviour). Produces a dictionary that does NOT "
                             "match the historical one.")
    parser.add_argument("--skip-header", action="store_true",
                        help="Skip the first CSV row. Kaggle's original file has a "
                             "'word,count' header; the historical input did not.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite the output file if it already exists.")
    return parser.parse_args(argv)


def build(input_csv: Path, output_txt: Path, punctuation=True, skip_header=False):
    """
    Deterministic: the same CSV always yields byte-identical output.
    Raises ValueError on malformed input rather than skipping rows silently.
    """
    entries: list[str] = list(PUNCTUATION_ENTRIES) if punctuation else []

    with input_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for lineno, row in enumerate(reader, start=1):
            if not row:
                raise ValueError(
                    f"{input_csv}:{lineno}: empty row. Refusing to guess -- a dropped "
                    f"row would renumber every code word after it."
                )
            word = row[0]

            if lineno == 1 and skip_header:
                continue
            if lineno == 1 and not skip_header and word.strip().lower() in HEADER_HINTS:
                raise ValueError(
                    f"{input_csv}:1: first field is {word!r}, which looks like a header.\n"
                    f"  Re-run with --skip-header, or confirm it really is a word.\n"
                    f"  Including a header row would shift every code word by one."
                )
            if word == "":
                raise ValueError(f"{input_csv}:{lineno}: empty word in column 1.")
            if "\n" in word or "\r" in word:
                raise ValueError(
                    f"{input_csv}:{lineno}: word contains an embedded newline: {word!r}"
                )
            entries.append(word)

    if not entries:
        raise ValueError(f"{input_csv}: produced no entries.")

    # Always LF, always a trailing newline -- matches the historical dict.txt.
    with output_txt.open("w", encoding="utf-8", newline="\n") as out:
        for entry in entries:
            out.write(entry + "\n")

    return entries


def main(argv=None) -> int:
    args = parse_args(argv)

    if not args.input.exists():
        print(f"[FAIL] Input file not found: {args.input}\n"
              f"       Supply a word-frequency CSV explicitly with --input.\n"
              f"       See docs/dictionary.md for how to obtain one.",
              file=sys.stderr)
        return 1
    if not args.input.is_file():
        print(f"[FAIL] Input is not a regular file: {args.input}", file=sys.stderr)
        return 1
    if args.output.exists() and not args.force:
        print(f"[FAIL] Output already exists: {args.output}\n"
              f"       Pass --force to overwrite.", file=sys.stderr)
        return 1

    try:
        entries = build(args.input, args.output,
                        punctuation=not args.no_punctuation,
                        skip_header=args.skip_header)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    data = args.output.read_bytes()
    digest = hashlib.sha256(data).hexdigest()

    print(f"[ OK ] wrote {args.output}")
    print(f"       entries : {len(entries):,}")
    print(f"       bytes   : {len(data):,}")
    print(f"       sha256  : {digest}")

    try:
        from dataset_config import HISTORICAL_DICT
        if digest == HISTORICAL_DICT["sha256"]:
            print("       MATCHES the historical artifact dictionary.")
        else:
            print("       Does NOT match the historical artifact dictionary")
            print(f"       (expected {HISTORICAL_DICT['sha256']}).")
            print("       Results produced with it will not reproduce the published")
            print("       measurements. See docs/dictionary.md.")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
