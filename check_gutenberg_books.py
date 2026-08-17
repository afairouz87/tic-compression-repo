#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess

# =====================
# CONFIG
# =====================

# INPUT_DIR = Path("../gutenberg_ebooks/raw")
# BAD_DIR = Path("../gutenberg_ebooks/bad_books")

INPUT_DIR = Path("../standard_ebooks_output/txt_clean")
BAD_DIR = Path("../standard_ebooks_output/bad_books")

EPIC_BIN = "./epic-v3.1"
THREADS = "2"
TIMEOUT_SECONDS = 5

TMP_OUTPUT = "/tmp/test_standard_ebooks_book.tic"

# =====================
# MAIN
# =====================

def move_bad_file(txt: Path, reason: str) -> None:
    BAD_DIR.mkdir(parents=True, exist_ok=True)

    target = BAD_DIR / txt.name

    if target.exists():
        target.unlink()

    shutil.move(str(txt), str(target))

    print(f"[MOVED] {txt} -> {target} | reason={reason}", flush=True)


def test_book(txt: Path) -> bool:
    print(f"[TEST] {txt}", flush=True)

    tmp_path = Path(TMP_OUTPUT)
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        result = subprocess.run(
            [
                EPIC_BIN,
                "-c",
                "-t",
                THREADS,
                str(txt),
                TMP_OUTPUT,
            ],
            timeout=TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    except subprocess.TimeoutExpired:
        move_bad_file(txt, "timeout")
        return False

    if result.returncode != 0:
        move_bad_file(txt, f"return_code={result.returncode}")
        return False

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        move_bad_file(txt, "empty_output")
        return False

    print(f"[OK] {txt}", flush=True)
    return True


def main() -> None:
    if not INPUT_DIR.exists():
        print(f"[ERROR] Input folder not found: {INPUT_DIR}")
        return

    txt_files = sorted(INPUT_DIR.glob("*.txt"))

    print(f"[INFO] Found {len(txt_files)} Gutenberg files.", flush=True)

    ok_count = 0
    bad_count = 0

    for txt in txt_files:
        ok = test_book(txt)

        if ok:
            ok_count += 1
        else:
            bad_count += 1

    print("\n[SUMMARY]", flush=True)
    print(f"OK files:  {ok_count}", flush=True)
    print(f"Bad files: {bad_count}", flush=True)
    print(f"Bad folder: {BAD_DIR.resolve()}", flush=True)


if __name__ == "__main__":
    main()