#!/usr/bin/env python3

from pathlib import Path

# =====================================================
# CONFIG
# =====================================================

INPUT_DIR = Path("../gutenberg_ebooks/raw")

PATTERN = "*** END OF"

# =====================================================
# MAIN
# =====================================================

def clean_file(path: Path):
    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception as e:
        print(f"[ERROR] Failed reading {path}: {e}")
        return

    lines = text.splitlines()

    cleaned_lines = []

    found = False

    for line in lines:

        if PATTERN in line:
            found = True
            break

        cleaned_lines.append(line)

    if found:
        path.write_text(
            "\n".join(cleaned_lines).strip() + "\n",
            encoding="utf-8"
        )

        print(f"[CLEANED] {path}")

    else:
        print(f"[SKIPPED] {path}")


def main():

    if not INPUT_DIR.exists():
        print(f"[ERROR] Folder not found: {INPUT_DIR}")
        return

    txt_files = sorted(INPUT_DIR.glob("*.txt"))

    print(f"[INFO] Found {len(txt_files)} txt files.")

    for txt in txt_files:
        clean_file(txt)

    print("[INFO] Done.")


if __name__ == "__main__":
    main()