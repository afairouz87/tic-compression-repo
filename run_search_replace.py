#!/usr/bin/env python3
"""
run_search_replace.py

Generate:
- Table 8: Lookup-and-Replace (L-R) Time on a compressed file in TIC and PIC,
           compared to a Plain Text File.
- Table 9: Lookup-and-Replace Time on a Compressed File.

Measurement policy:
- Table 8:
    TIC/PIC: native compressed-domain lookup-and-replace.
    Plain Text: direct plaintext lookup-and-replace.
- Table 9:
    TIC/PIC: native compressed-domain lookup-and-replace.
    gzip/bzip2/lz4: decompress -> plaintext replace -> recompress.

Important:
- Compression/decompression timings are measured directly inside this script.
- No compression/decompression timing CSVs are reused.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd

from benchmark_utils import (
    build_grouped_latex_table,
    build_replace_command,
    ensure_compressed_files,
    format_number,
    get_compressed_path,
    get_log_paths,
    measure_command,
    safe_ratio,
    write_dataframe_csv,
)

# =====================
# User Config
# =====================

INPUT_FILES = [
    "../textFiles/f1.txt",
    "../textFiles/f2.txt",
    "../textFiles/f3.txt",
    "../textFiles/f4.txt",
    "../textFiles/f5.txt",
    "../textFiles/f6.txt",
    "../textFiles/f7.txt",
    "../textFiles/f8.txt",
    "../textFiles/f9.txt",
    "../textFiles/f10.txt",
]
# INPUT_FILES = [
#     "../textFiles/f1.txt",
#     "../textFiles/f2.txt",
# ]

# RUN_TOOLS = ["PIC", "TIC", "gzip", "bzip2", "lz4"]
RUN_TOOLS = ["TIC", "PIC", "gzip", "bzip2", "lz4"]

THREADS = 1
DECIMALS = 3

NUM_RUNS = 10
WARMUP_RUNS = 1

SEARCH_STRING = "the"
REPLACE_STRING = "THE"

# SEARCH_STRING = "interviewing"
# REPLACE_STRING = "questioning"

RESULTS_DIR = "."
LOG_DIR = "results/logs/search_replace"

TABLE8_CSV = os.path.join(RESULTS_DIR, "lookup_replace_vs_plaintext_results.csv")
TABLE8_TEX = os.path.join(RESULTS_DIR, "lookup_replace_vs_plaintext_table.tex")

TABLE9_CSV = os.path.join(RESULTS_DIR, "lookup_replace_compressed_results.csv")
TABLE9_TEX = os.path.join(RESULTS_DIR, "lookup_replace_compressed_table.tex")

TABLE8_CAPTION = (
    "Lookup-and-Replace (L-R) Time on a compressed file in TIC and PIC, "
    "compared to a Plain Text File."
)
TABLE8_LABEL = "tab:lookup_replace_vs_plaintext"

TABLE9_CAPTION = "Lookup-and-Replace Time on a Compressed File."
TABLE9_LABEL = "tab:lookup_replace_compressed"


# =====================
# Validation / helpers
# =====================

def _validate_inputs() -> None:
    missing = [p for p in INPUT_FILES if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"Missing input files: {missing}")


def _append_average_row(df: pd.DataFrame, first_col: str = "File Name") -> pd.DataFrame:
    avg_row: dict[str, Any] = {first_col: "Average"}

    for col in df.columns:
        if col == first_col:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            avg_row[col] = df[col].mean()
        else:
            avg_row[col] = ""

    return pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)


def _ensure_rc_ok(result: dict[str, Any], allowed: tuple[int, ...], msg: str) -> None:
    rc = int(result.get("return_code", -1))
    if rc not in allowed:
        raise RuntimeError(f"{msg}. return_code={rc}")


def _decompress_cmd(tool: str, compressed_path: str) -> list[str]:
    if tool == "gzip":
        return ["gzip", "-dc", compressed_path]
    if tool == "bzip2":
        return ["bzip2", "-dc", compressed_path]
    if tool == "lz4":
        return ["lz4", "-dc", compressed_path]

    raise ValueError(f"Unsupported decompression tool: {tool}")


def _recompress_cmd(tool: str, plain_path: str) -> list[str]:
    if tool == "gzip":
        return ["gzip", "-c", plain_path]
    if tool == "bzip2":
        return ["bzip2", "-c", plain_path]
    if tool == "lz4":
        return ["lz4", "-c", plain_path]

    raise ValueError(f"Unsupported recompression tool: {tool}")


# =====================
# Measurements
# =====================

def _measure_plaintext_replace(
    input_path: str,
    search_string: str,
    replace_string: str,
    tmp_dir: str
) -> dict[str, Any]:
    """
    Plain-text lookup-and-replace benchmark using standard sed tool.

    Uses:
    - multiple benchmark runs
    - warm-up run skipping
    - average runtime measurement
    """

    in_path = Path(input_path)

    out_path = (
        Path(tmp_dir)
        / f"{in_path.stem}_plain_replace.txt"
    )

    stdout_path, stderr_path = get_log_paths(
        output_dir=LOG_DIR,
        tool="PlainText",
        operation="replace",
        file_stem=in_path.stem,
    )

    times = []

    for run_idx in range(NUM_RUNS):

        # -----------------------------------------
        # Remove previous output file
        # -----------------------------------------
        if out_path.exists():
            out_path.unlink()

        cmd = [
            "sh",
            "-c",
            (
                f"sed 's/{search_string}/{replace_string}/g' "
                f"'{input_path}' > '{out_path}'"
            )
        ]

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            result,
            allowed=(0,),
            msg=f"Plain-text replacement failed for {input_path}",
        )

        # -----------------------------------------
        # Verify output file
        # -----------------------------------------
        if (
            not out_path.exists()
            or out_path.stat().st_size == 0
        ):
            raise RuntimeError(
                f"Plain-text replacement failed to produce output: "
                f"{out_path}"
            )

        # -----------------------------------------
        # Skip warm-up runs
        # -----------------------------------------
        if run_idx < WARMUP_RUNS:
            continue

        times.append(float(result["wall_time_s"]))

    avg_time = sum(times) / len(times)

    print(
        f"    PlainText: avg_time={avg_time:.6f}s "
        f"over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    return {
        "return_code": 0,
        "wall_time_s": round(avg_time, 6),
        "avg_memory_mb": 0.0,
        "peak_memory_mb": 0.0,
        "output_path": str(out_path),
    }

def _measure_native_replace(
    tool: str,
    input_path: str,
    search_string: str,
    replace_string: str,
    tmp_dir: str,
) -> dict[str, Any]:
    """
    Measure native compressed-domain lookup-and-replace for TIC/PIC.

    Uses:
    - multiple benchmark runs
    - warm-up run skipping
    - average runtime / memory measurement
    """

    compressed_path = get_compressed_path(input_path, tool)

    output_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool.lower()}_replace.out",
    )

    stdout_path, stderr_path = get_log_paths(
        output_dir=LOG_DIR,
        tool=tool,
        operation="replace",
        file_stem=Path(input_path).stem,
    )

    cmd = build_replace_command(
        tool=tool,
        compressed_path=compressed_path,
        search_string=search_string,
        replace_string=replace_string,
        output_path=output_path,
        threads=THREADS,
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):

        # -----------------------------------------
        # Remove previous output file
        # -----------------------------------------
        if os.path.exists(output_path):
            os.remove(output_path)

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            result,
            allowed=(0,),
            msg=f"{tool} lookup-and-replace failed for {input_path}. "
                f"Check logs: {stdout_path}, {stderr_path}",
        )

        # -----------------------------------------
        # Verify output file exists
        # -----------------------------------------
        if (
            not os.path.exists(output_path)
            or os.path.getsize(output_path) == 0
        ):
            raise RuntimeError(
                f"{tool} failed to produce replacement output: "
                f"{output_path}"
            )

        # -----------------------------------------
        # Skip warm-up runs
        # -----------------------------------------
        if run_idx < WARMUP_RUNS:
            continue

        times.append(float(result["wall_time_s"]))
        peak_memories.append(float(result["peak_memory_mb"]))

    avg_time = sum(times) / len(times)
    avg_peak_memory = sum(peak_memories) / len(peak_memories)

    print(
        f"    {tool}: avg_time={avg_time:.6f}s "
        f"over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    result["wall_time_s"] = round(avg_time, 6)
    result["peak_memory_mb"] = round(avg_peak_memory, 6)

    result["output_path"] = output_path
    result["stdout_path"] = stdout_path
    result["stderr_path"] = stderr_path

    return result


def _measure_decompress_replace_recompress(
    tool: str,
    input_path: str,
    search_string: str,
    replace_string: str,
    tmp_dir: str,
) -> dict[str, Any]:
    """
    Measure full conventional workflow:
        decompress compressed file -> plaintext replace -> recompress modified plaintext.
    """

    compressed_path = get_compressed_path(input_path, tool)

    decompressed_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_decompressed.txt",
    )

    modified_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_modified.txt",
    )

    recompressed_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_modified_recompressed.out",
    )

    verify_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_verify.txt",
    )

    stdout_path, stderr_path = get_log_paths(
        output_dir=LOG_DIR,
        tool=tool,
        operation="decompress_replace_recompress",
        file_stem=Path(input_path).stem,
    )

    # -----------------------------
    # Step 1: Decompress
    # -----------------------------
    decomp_result = measure_command(
        _decompress_cmd(tool, compressed_path),
        stdout_path=decompressed_path,
        stderr_path=stderr_path,
    )

    _ensure_rc_ok(
        decomp_result,
        allowed=(0,),
        msg=f"{tool} decompression failed for {input_path}. Check logs: {stderr_path}",
    )

    if not os.path.exists(decompressed_path) or os.path.getsize(decompressed_path) == 0:
        raise RuntimeError(f"{tool} failed to produce decompressed file: {decompressed_path}")

    # -----------------------------
    # Step 2: Plaintext replace using sed
    # -----------------------------
    replace_result = measure_command(
        [
            "sh",
            "-c",
            (
                f"sed 's/{search_string}/{replace_string}/g' "
                f"'{decompressed_path}' > '{modified_path}'"
            )
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )

    _ensure_rc_ok(
        replace_result,
        allowed=(0,),
        msg=f"{tool} sed replace failed for {input_path}",
    )

    if (
        not os.path.exists(modified_path)
        or os.path.getsize(modified_path) == 0
    ):
        raise RuntimeError(
            f"{tool} failed to produce modified plaintext file: "
            f"{modified_path}"
        )

    # -----------------------------
    # Step 3: Recompress modified plaintext
    # -----------------------------
    recomp_result = measure_command(
        _recompress_cmd(tool, modified_path),
        stdout_path=recompressed_path,
        stderr_path=stderr_path,
    )

    _ensure_rc_ok(
        recomp_result,
        allowed=(0,),
        msg=f"{tool} recompression failed for {input_path}. Check logs: {stderr_path}",
    )

    if not os.path.exists(recompressed_path) or os.path.getsize(recompressed_path) == 0:
        raise RuntimeError(f"{tool} failed to produce recompressed file: {recompressed_path}")

    # -----------------------------
    # Step 4: Verify recompressed output can be decompressed
    # Not included in reported time.
    # -----------------------------
    verify_result = measure_command(
        _decompress_cmd(tool, recompressed_path),
        stdout_path=verify_path,
        stderr_path=stderr_path,
    )

    _ensure_rc_ok(
        verify_result,
        allowed=(0,),
        msg=f"{tool} recompressed output verification failed for {input_path}. "
            f"Check logs: {stderr_path}",
    )

    if not os.path.exists(verify_path) or os.path.getsize(verify_path) == 0:
        raise RuntimeError(f"{tool} failed to verify recompressed output: {verify_path}")

    total_time = (
        float(decomp_result["wall_time_s"])
        + float(replace_result["wall_time_s"])
        + float(recomp_result["wall_time_s"])
    )

    peak_memory_mb = max(
        float(decomp_result["peak_memory_mb"]),
        float(recomp_result["peak_memory_mb"]),
    )

    return {
        "return_code": 0,
        "wall_time_s": round(total_time, 6),
        "peak_memory_mb": round(peak_memory_mb, 6),
        "decompressed_path": decompressed_path,
        "modified_path": modified_path,
        "recompressed_path": recompressed_path,
        "verify_path": verify_path,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


# =====================
# Formatting
# =====================

def _format_table8(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["TIC (s)"] = out["TIC (s)"].apply(
        lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
    )

    for col in ["PIC", "Plain Text"]:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )

    return out


def _format_table9(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["TIC (s)"] = out["TIC (s)"].apply(
        lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
    )

    for col in ["PIC", "gzip", "bzip2", "lz4"]:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )

    return out


# =====================
# Main
# =====================

def main() -> None:
    _validate_inputs()

    print("[INFO] Ensuring compressed files exist...", flush=True)
    for input_path in INPUT_FILES:
        ensure_compressed_files(RUN_TOOLS, input_path, threads=THREADS, force=False)

    table8_rows: list[dict[str, Any]] = []
    table9_rows: list[dict[str, Any]] = []

    tmp_dir = tempfile.mkdtemp(prefix="run_search_replace_")

    try:
        for file_idx, input_path in enumerate(INPUT_FILES, start=1):
            file_name = Path(input_path).name

            print(f"[INFO] File {file_idx}/{len(INPUT_FILES)}: {file_name}", flush=True)

            # =========================
            # Native compressed-domain L-R
            # =========================
            print("  [INFO] TIC -> native compressed lookup-and-replace...", flush=True)
            tic_lr = _measure_native_replace(
                "TIC",
                input_path,
                SEARCH_STRING,
                REPLACE_STRING,
                tmp_dir,
            )
            tic_lr_time = float(tic_lr["wall_time_s"])
            print(
                f"  [DONE] TIC L-R: time={tic_lr_time:.3f}s, "
                f"peak_mem={float(tic_lr['peak_memory_mb']):.3f} MB",
                flush=True,
            )

            print("  [INFO] PIC -> native compressed lookup-and-replace...", flush=True)
            pic_lr = _measure_native_replace(
                "PIC",
                input_path,
                SEARCH_STRING,
                REPLACE_STRING,
                tmp_dir,
            )
            pic_lr_time = float(pic_lr["wall_time_s"])
            print(
                f"  [DONE] PIC L-R: time={pic_lr_time:.3f}s, "
                f"peak_mem={float(pic_lr['peak_memory_mb']):.3f} MB",
                flush=True,
            )

            # =========================
            # Plain text L-R
            # =========================
            print("  [INFO] Plain Text -> lookup-and-replace...", flush=True)
            plain_lr = _measure_plaintext_replace(
                input_path,
                SEARCH_STRING,
                REPLACE_STRING,
                tmp_dir,
            )
            plain_lr_time = float(plain_lr["wall_time_s"])
            print(f"  [DONE] Plain Text L-R: time={plain_lr_time:.3f}s", flush=True)

            # =========================
            # Conventional compressed workflows
            # =========================
            conventional_results: dict[str, dict[str, Any]] = {}

            for tool in ["gzip", "bzip2", "lz4"]:
                print(f"  [INFO] {tool} -> decompress + replace + recompress...", flush=True)
                res = _measure_decompress_replace_recompress(
                    tool,
                    input_path,
                    SEARCH_STRING,
                    REPLACE_STRING,
                    tmp_dir,
                )
                conventional_results[tool] = res

                print(
                    f"  [DONE] {tool} workflow: "
                    f"time={float(res['wall_time_s']):.3f}s, "
                    f"peak_mem={float(res['peak_memory_mb']):.3f} MB, "
                    f"output={res['recompressed_path']}",
                    flush=True,
                )

            # =========================
            # Table 8
            # =========================
            table8_rows.append({
                "File Name": file_name,
                "TIC (s)": round(tic_lr_time, DECIMALS),
                "PIC": safe_ratio(pic_lr_time, tic_lr_time, decimals=DECIMALS),
                "Plain Text": safe_ratio(plain_lr_time, tic_lr_time, decimals=DECIMALS),
            })

            # =========================
            # Table 9
            # =========================
            table9_rows.append({
                "File Name": file_name,
                "TIC (s)": round(tic_lr_time, DECIMALS),
                "PIC": safe_ratio(pic_lr_time, tic_lr_time, decimals=DECIMALS),
                "gzip": safe_ratio(conventional_results["gzip"]["wall_time_s"], tic_lr_time, decimals=DECIMALS),
                "bzip2": safe_ratio(conventional_results["bzip2"]["wall_time_s"], tic_lr_time, decimals=DECIMALS),
                "lz4": safe_ratio(conventional_results["lz4"]["wall_time_s"], tic_lr_time, decimals=DECIMALS),
            })

        table8_df = pd.DataFrame(table8_rows)[
            ["File Name", "TIC (s)", "PIC", "Plain Text"]
        ]

        table9_df = pd.DataFrame(table9_rows)[
            ["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]
        ]

        table8_df = _append_average_row(table8_df)
        table9_df = _append_average_row(table9_df)

        table8_out = _format_table8(table8_df)
        table9_out = _format_table9(table9_df)

        print("[INFO] Writing CSV and LaTeX outputs...", flush=True)

        write_dataframe_csv(table8_out, TABLE8_CSV)
        write_dataframe_csv(table9_out, TABLE9_CSV)

        build_grouped_latex_table(
            df=table8_out,
            tex_path=TABLE8_TEX,
            caption=TABLE8_CAPTION,
            label=TABLE8_LABEL,
            group_headers=[
                ("File Name", 1),
                ("Absolute (s)", 1),
                ("Relative to TIC", 2),
            ],
            column_headers=["File Name", "TIC (s)", "PIC", "Plain Text"],
            align_spec="cccc",
        )

        build_grouped_latex_table(
            df=table9_out,
            tex_path=TABLE9_TEX,
            caption=TABLE9_CAPTION,
            label=TABLE9_LABEL,
            group_headers=[
                ("File Name", 1),
                ("Absolute (s)", 1),
                ("Relative to TIC", 4),
            ],
            column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
            align_spec="cccccc",
        )

        print(f"Wrote: {TABLE8_CSV}")
        print(f"Wrote: {TABLE8_TEX}")
        print(f"Wrote: {TABLE9_CSV}")
        print(f"Wrote: {TABLE9_TEX}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
