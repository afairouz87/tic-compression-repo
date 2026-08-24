#!/usr/bin/env python3
"""
debug_pic_tic.py

Debug PIC and TIC for:
- compression
- decompression
- search

It runs each tool separately and records:
- return code
- stdout
- stderr
- output file existence
- file sizes
- decompression diff result
- search summary output

Usage examples:
    python3 debug_pic_tic.py --file datasets/f1.txt --query "the"
    python3 debug_pic_tic.py --file small.txt --query "the" --keep-files
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dataset_config import results_path


PIC_BINARY = "./pic-v3.1"
TIC_BINARY = "./epic-v3.1"
THREADS = "1"


def parse_args():
    parser = argparse.ArgumentParser(description="Debug PIC and TIC compression/decompression/search.")
    parser.add_argument("--file", required=True, help="Input text file")
    parser.add_argument("--query", required=True, help="Search string")
    parser.add_argument("--keep-files", action="store_true", help="Keep temp/debug files")
    parser.add_argument(
        "--output-dir",
        default=results_path("tmp", "debug_pic_tic"),
        help="Directory for logs/results (default: under results/tmp, which is git-ignored).",
    )
    return parser.parse_args()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text_safe(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def run_command(cmd: list[str], stdout_path: str, stderr_path: str) -> int:
    with open(stdout_path, "wb") as out_f, open(stderr_path, "wb") as err_f:
        proc = subprocess.run(cmd, stdout=out_f, stderr=err_f)
    return proc.returncode


def print_section(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_command(label: str, cmd: list[str]):
    print(f"{label}: {' '.join(cmd)}")


def compare_files(original: str, other: str) -> tuple[bool, str]:
    if not os.path.exists(other):
        return False, "Decompressed file does not exist"

    orig_size = os.path.getsize(original)
    other_size = os.path.getsize(other)
    if orig_size != other_size:
        return False, f"Size mismatch: original={orig_size}, other={other_size}"

    orig_hash = sha256_file(original)
    other_hash = sha256_file(other)
    if orig_hash != other_hash:
        return False, f"SHA256 mismatch:\n  original={orig_hash}\n  other   ={other_hash}"

    return True, f"Match OK (size={orig_size}, sha256={orig_hash})"


def summarize_log(stdout_path: str, stderr_path: str):
    stdout_text = read_text_safe(stdout_path).strip()
    stderr_text = read_text_safe(stderr_path).strip()

    print(f"stdout file: {stdout_path}")
    print(f"stderr file: {stderr_path}")

    print("\nstdout:")
    print(stdout_text if stdout_text else "<empty>")

    print("\nstderr:")
    print(stderr_text if stderr_text else "<empty>")


def debug_one_tool(
    tool_name: str,
    binary: str,
    input_file: str,
    comp_ext: str,
    query: str,
    work_dir: str,
):
    print_section(f"{tool_name} DEBUG")

    compressed_file = os.path.join(work_dir, f"{Path(input_file).name}{comp_ext}")
    decompressed_file = os.path.join(work_dir, f"{tool_name.lower()}_decompressed.txt")
    search_dummy_out = os.path.join(work_dir, f"{tool_name.lower()}_search_dummy.txt")

    # -------------------------
    # 1) Compression
    # -------------------------
    comp_stdout = os.path.join(work_dir, f"{tool_name.lower()}_compress_stdout.txt")
    comp_stderr = os.path.join(work_dir, f"{tool_name.lower()}_compress_stderr.txt")
    compress_cmd = [binary, "-c", "-t", THREADS, input_file, compressed_file]

    print_command("compress cmd", compress_cmd)
    comp_rc = run_command(compress_cmd, comp_stdout, comp_stderr)
    print(f"compress rc: {comp_rc}")
    print(f"compressed exists: {os.path.exists(compressed_file)}")
    if os.path.exists(compressed_file):
        print(f"compressed size: {os.path.getsize(compressed_file)} bytes")
    summarize_log(comp_stdout, comp_stderr)

    # -------------------------
    # 2) Decompression
    # -------------------------
    decomp_stdout = os.path.join(work_dir, f"{tool_name.lower()}_decompress_stdout.txt")
    decomp_stderr = os.path.join(work_dir, f"{tool_name.lower()}_decompress_stderr.txt")
    decompress_cmd = [binary, "-d", "-t", THREADS, compressed_file, decompressed_file]

    print_command("decompress cmd", decompress_cmd)
    decomp_rc = run_command(decompress_cmd, decomp_stdout, decomp_stderr)
    print(f"decompress rc: {decomp_rc}")
    print(f"decompressed exists: {os.path.exists(decompressed_file)}")
    if os.path.exists(decompressed_file):
        print(f"decompressed size: {os.path.getsize(decompressed_file)} bytes")
    summarize_log(decomp_stdout, decomp_stderr)

    ok, msg = compare_files(input_file, decompressed_file)
    print(f"\ndecompression comparison: {'PASS' if ok else 'FAIL'}")
    print(msg)

    # -------------------------
    # 3) Search
    # -------------------------
    search_stdout = os.path.join(work_dir, f"{tool_name.lower()}_search_stdout.txt")
    search_stderr = os.path.join(work_dir, f"{tool_name.lower()}_search_stderr.txt")
    search_cmd = [binary, "-l", "-t", THREADS, compressed_file, search_dummy_out, query]

    print_command("search cmd", search_cmd)
    search_rc = run_command(search_cmd, search_stdout, search_stderr)
    print(f"search rc: {search_rc}")
    print(f"search dummy output exists: {os.path.exists(search_dummy_out)}")
    summarize_log(search_stdout, search_stderr)

    return {
        "tool": tool_name,
        "compress_rc": comp_rc,
        "decompress_rc": decomp_rc,
        "search_rc": search_rc,
        "compressed_file": compressed_file,
        "decompressed_file": decompressed_file,
        "search_dummy_out": search_dummy_out,
    }


def main():
    args = parse_args()

    input_file = args.file
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    os.makedirs(args.output_dir, exist_ok=True)

    temp_dir = tempfile.mkdtemp(prefix="debug_pic_tic_", dir=args.output_dir)
    print(f"Working directory: {temp_dir}")
    print(f"Input file: {input_file}")
    print(f"Input size: {os.path.getsize(input_file)} bytes")
    print(f"Query: {args.query}")

    try:
        pic_result = debug_one_tool(
            tool_name="PIC",
            binary=PIC_BINARY,
            input_file=input_file,
            comp_ext=".pic",
            query=args.query,
            work_dir=temp_dir,
        )

        tic_result = debug_one_tool(
            tool_name="TIC",
            binary=TIC_BINARY,
            input_file=input_file,
            comp_ext=".tic",
            query=args.query,
            work_dir=temp_dir,
        )

        print_section("SUMMARY")
        for r in [pic_result, tic_result]:
            print(
                f"{r['tool']}: "
                f"compress_rc={r['compress_rc']}, "
                f"decompress_rc={r['decompress_rc']}, "
                f"search_rc={r['search_rc']}"
            )

        print(f"\nAll logs/files are in: {temp_dir}")

        if args.keep_files:
            print("Keeping files as requested.")
        else:
            print("Temporary files will be removed.")

    finally:
        if args.keep_files:
            return
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

