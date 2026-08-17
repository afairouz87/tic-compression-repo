#!/usr/bin/env python3

from pathlib import Path
import re
import unicodedata
import textwrap

# =========================
# CONFIG
# =========================

INPUT_DIRS = [
    Path("standard_ebooks_output/txt_clean"),
    Path("gutenberg_ebooks/raw"),   # change/remove if needed
]

OUTPUT_DIR = Path("combined_text_files")

TARGET_FILES_MB = {
    "f1.txt": 50,
    "f2.txt": 100,
    "f3.txt": 137,
    "f4.txt": 150,
    "f5.txt": 200,
    # "f6.txt": 347,
    # "f7.txt": 400,
    # "f8.txt": 500,
    # "f9.txt": 634,
    # "f10.txt": 769,
}

MB = 1024 * 1024

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

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    source_files = collect_txt_files(INPUT_DIRS)

    if not source_files:
        print("[ERROR] No input .txt files found.")
        return

    print(f"[INFO] Found {len(source_files)} source text files.")

    #file_index = 0

    #for output_name, target_mb in TARGET_FILES_MB.items():
    #    target_bytes = target_mb * MB
    #    output_path = OUTPUT_DIR / output_name

    for output_name, target_mb in TARGET_FILES_MB.items():
        file_index = 0  # restart source files for every output file

        target_bytes = target_mb * MB
        output_path = OUTPUT_DIR / output_name

        print(f"\n[INFO] Creating {output_name} with target size {target_mb} MB")

        written_bytes = 0

        manifest_path = OUTPUT_DIR / f"{output_name}.manifest.txt"

        with open(output_path, "w", encoding="utf-8") as out, open(manifest_path, "w", encoding="utf-8") as manifest:
            while written_bytes < target_bytes:
                if file_index >= len(source_files):
                    print("[ERROR] Not enough source text to reach target sizes.")
                    return

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

                out.write(text_to_add)
                out.flush()

                written_bytes += len(text_to_add.encode("utf-8"))

        print(f"[DONE] {output_name}: {file_size_mb(output_path):.2f} MB")

    print("\n[INFO] Finished creating all combined text files.")
    print(f"[INFO] Output folder: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

