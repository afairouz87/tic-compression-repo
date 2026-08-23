#!/usr/bin/env python3
"""
run_search.py

Generate:
- Table 2: Lookup Time (without Re-compression)
- Table 3: Lookup Time (with Re-compression)
- Table 4: Peak memory used for decompression, lookup, and re-compression
- Table 7: Lookup Time on a Compressed File Compared to zgrep and bzgrep
- Table 10: Entropy of plain text files and compressed files

Outputs:
- lookup_time_no_recompression_results.csv
- lookup_time_no_recompression_table.tex
- lookup_time_with_recompression_results.csv
- lookup_time_with_recompression_table.tex
- lookup_memory_results.csv
- lookup_memory_table.tex
- lookup_time_streaming_results.csv
- lookup_time_streaming_table.tex
- entropy_results.csv
- entropy_table.tex

Measurement policy:
- Table 2:
    TIC/PIC: direct compressed lookup
    gzip/bzip2/lz4: decompress to plaintext, then grep
- Table 3:
    TIC/PIC: direct compressed lookup
    gzip/bzip2/lz4: decompress to plaintext, grep, then recompress
- Table 7:
    TIC/PIC: direct compressed lookup
    gzip: zgrep
    bzip2: bzgrep

Important:
- This script measures decompression and recompression workflows directly.
- It does not reuse compression/decompression timing CSVs from other scripts.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from dataset_config import (
    RESULTS_FIGURES_DIR,
    RESULTS_RAW_DIR,
    RESULTS_TABLES_DIR,
)
from dependencies import preflight

from benchmark_utils import (
    BENCHMARK_INPUT_FILES,
    build_grouped_latex_table,
    build_search_command,
    build_simple_latex_table,
    compute_file_entropy,
    ensure_compressed_files,
    format_number,
    get_compressed_path,
    measure_command,
    safe_ratio,
    write_dataframe_csv,
)

# =====================
# User Config
# =====================

# Benchmark inputs f1..f10, resolved through the canonical dataset directory.
# The dataset layout is defined once in dataset_config.py; set $TIC_DATASET_DIR
# to point at a different location. See docs/datasets.md.
INPUT_FILES = list(BENCHMARK_INPUT_FILES)

# INPUT_FILES = [
#     "../textFiles/f1.txt",
#     "../textFiles/f2.txt",
# ]

RUN_TOOLS = ["PIC", "TIC", "gzip", "bzip2", "lz4"]
TABLE_TOOLS = ["TIC", "PIC", "gzip", "bzip2", "lz4"]

THREADS = 1
DECIMALS = 3

NUM_RUNS = 10
WARMUP_RUNS = 1

SEARCH_QUERY = "the"

# Supported keys:
# "TIC", "PIC", "gzip", "bzip2", "lz4", "zgrep", "bzgrep"
FORCE_RERUN_SEARCH_TOOLS = {
    "TIC",
    "PIC",
    "gzip",
    "bzip2",
    "lz4",
    "zgrep",
    "bzgrep",
}

# Generated output goes under results/, never the repository root.
# The layout is defined once in dataset_config.py.
RESULTS_DIR = RESULTS_RAW_DIR          # *_results.csv
TABLES_DIR = RESULTS_TABLES_DIR        # *_table.tex
FIGURES_DIR = RESULTS_FIGURES_DIR      # *.png
LOG_DIR = "results/logs/search"

LOOKUP_TIME_NO_RECOMP_CSV = os.path.join(RESULTS_DIR, "lookup_time_no_recompression_results.csv")
LOOKUP_TIME_NO_RECOMP_TEX = os.path.join(TABLES_DIR, "lookup_time_no_recompression_table.tex")

LOOKUP_TIME_WITH_RECOMP_CSV = os.path.join(RESULTS_DIR, "lookup_time_with_recompression_results.csv")
LOOKUP_TIME_WITH_RECOMP_TEX = os.path.join(TABLES_DIR, "lookup_time_with_recompression_table.tex")

LOOKUP_MEMORY_CSV = os.path.join(RESULTS_DIR, "lookup_memory_results.csv")
LOOKUP_MEMORY_TEX = os.path.join(TABLES_DIR, "lookup_memory_table.tex")

LOOKUP_TIME_STREAMING_CSV = os.path.join(RESULTS_DIR, "lookup_time_streaming_results.csv")
LOOKUP_TIME_STREAMING_TEX = os.path.join(TABLES_DIR, "lookup_time_streaming_table.tex")

ENTROPY_CSV = os.path.join(RESULTS_DIR, "entropy_results.csv")
ENTROPY_TEX = os.path.join(TABLES_DIR, "entropy_table.tex")

CAPTION_TABLE_2 = "Lookup Time (without Re-compression)."
LABEL_TABLE_2 = "tab:lookup_no_recompression"

CAPTION_TABLE_3 = "Lookup Time (with Re-compression)."
LABEL_TABLE_3 = "tab:lookup_with_recompression"

CAPTION_TABLE_4 = "Peak memory used for decompression, lookup and re-compression."
LABEL_TABLE_4 = "tab:lookup_memory"

CAPTION_TABLE_7 = "Lookup Time on a Compressed File Compared to zgrep and bzgrep."
LABEL_TABLE_7 = "tab:lookup_streaming"

CAPTION_TABLE_10 = "Entropy of plain text files and compressed files."
LABEL_TABLE_10 = "tab:entropy"


# =====================
# Validation / helpers
# =====================

def _validate_inputs() -> None:
    """
    Pre-flight check. Validates Python packages, external executables, the
    compiled binaries, every input dataset and the output directories BEFORE
    any measurement starts, so a long run never dies halfway through because a
    tool was missing. Requirements live in dependencies.EXPERIMENT_REQUIREMENTS.
    """
    preflight(
        "search",
        input_files=INPUT_FILES,
        output_dirs=[RESULTS_DIR, TABLES_DIR, FIGURES_DIR, LOG_DIR],
    )


def _tool_log_paths(file_name: str, suffix: str) -> tuple[str, str]:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    stem = Path(file_name).stem
    stdout_path = os.path.join(LOG_DIR, f"{suffix}_{stem}_stdout.txt")
    stderr_path = os.path.join(LOG_DIR, f"{suffix}_{stem}_stderr.txt")
    return stdout_path, stderr_path


def _load_previous_df(csv_path: str) -> pd.DataFrame | None:
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return None


def _lookup_previous_value(df: pd.DataFrame | None, file_name: str, column_name: str) -> Any:
    if df is None or column_name not in df.columns:
        return None
    rows = df[df["File Name"] == file_name]
    if rows.empty:
        return None
    value = rows.iloc[0][column_name]
    if pd.isna(value):
        return None
    return value


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


def _should_rerun(tool: str, prev_df: pd.DataFrame | None, file_name: str, column_name: str) -> bool:
    return (
        tool in FORCE_RERUN_SEARCH_TOOLS
        or prev_df is None
        or _lookup_previous_value(prev_df, file_name, column_name) is None
    )


def _ensure_rc_ok(result: dict[str, Any], allowed: tuple[int, ...], msg: str) -> None:
    rc = int(result.get("return_code", -1))
    if rc not in allowed:
        raise RuntimeError(f"{msg}. return_code={rc}")


# =====================
# Command builders for decompression/recompression
# =====================

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
# Search measurements
# =====================

def _measure_native_search(tool: str, input_path: str, query: str, tmp_dir: str) -> dict[str, Any]:
    compressed_path = get_compressed_path(input_path, tool)
    dummy_out = os.path.join(tmp_dir, f"{Path(input_path).stem}_{tool.lower()}_dummy.txt")

    stdout_path, stderr_path = _tool_log_paths(Path(input_path).name, f"{tool}_native_search")

    cmd = build_search_command(
        tool=tool,
        compressed_path=compressed_path,
        query=query,
        dummy_output_path=dummy_out,
        threads=THREADS,
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):
        if os.path.exists(dummy_out):
            os.remove(dummy_out)

        result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)

        _ensure_rc_ok(
            result,
            allowed=(0,),
            msg=f"{tool} native search failed for {input_path}. Check logs: {stdout_path}, {stderr_path}",
        )

        if run_idx < WARMUP_RUNS:
            continue

        times.append(float(result["wall_time_s"]))
        peak_memories.append(float(result["peak_memory_mb"]))

    avg_time = sum(times) / len(times)
    avg_peak_memory = sum(peak_memories) / len(peak_memories)

    print(
        f"    {tool}: avg_time={avg_time:.6f}s over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    return {
        "return_code": 0,
        "wall_time_s": round(avg_time, 6),
        "peak_memory_mb": round(avg_peak_memory, 6),
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


def _measure_decompress_search_only(tool: str, input_path: str, query: str, tmp_dir: str) -> dict[str, Any]:
    compressed_path = get_compressed_path(input_path, tool)

    decompressed_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_decompressed.txt",
    )

    stdout_path, stderr_path = _tool_log_paths(
        Path(input_path).name,
        f"{tool}_decompress_search",
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):
        if os.path.exists(decompressed_path):
            os.remove(decompressed_path)

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
            raise RuntimeError(f"{tool} failed to produce decompressed temp file: {decompressed_path}")

        grep_result = measure_command(
            ["grep", "-a", "-c", query, decompressed_path],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            grep_result,
            allowed=(0, 1),
            msg=f"grep failed after {tool} decompression for {input_path}. Check logs: {stdout_path}, {stderr_path}",
        )

        if run_idx < WARMUP_RUNS:
            continue

        times.append(
            float(decomp_result["wall_time_s"]) +
            float(grep_result["wall_time_s"])
        )

        peak_memories.append(
            max(
                float(decomp_result["peak_memory_mb"]),
                float(grep_result["peak_memory_mb"]),
            )
        )

    avg_time = sum(times) / len(times)
    avg_peak_memory = sum(peak_memories) / len(peak_memories)

    print(
        f"    {tool}: avg_time={avg_time:.6f}s over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    return {
        "wall_time_s": round(avg_time, 6),
        "peak_memory_mb": round(avg_peak_memory, 6),
        "return_code": 0,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


def _measure_decompress_search_recompress(
    tool: str,
    input_path: str,
    query: str,
    tmp_dir: str,
) -> dict[str, Any]:
    compressed_path = get_compressed_path(input_path, tool)

    decompressed_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_decompressed_for_recompression.txt",
    )

    recompressed_path = os.path.join(
        tmp_dir,
        f"{Path(input_path).stem}_{tool}_recompressed.out",
    )

    stdout_path, stderr_path = _tool_log_paths(
        Path(input_path).name,
        f"{tool}_decompress_search_recompress",
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):
        for p in [decompressed_path, recompressed_path]:
            if os.path.exists(p):
                os.remove(p)

        decomp_result = measure_command(
            _decompress_cmd(tool, compressed_path),
            stdout_path=decompressed_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            decomp_result,
            allowed=(0,),
            msg=f"{tool} decompression failed for recompression workflow on {input_path}. Check logs: {stderr_path}",
        )

        if not os.path.exists(decompressed_path) or os.path.getsize(decompressed_path) == 0:
            raise RuntimeError(f"{tool} failed to produce decompressed temp file: {decompressed_path}")

        grep_result = measure_command(
            ["grep", "-a", "-c", query, decompressed_path],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            grep_result,
            allowed=(0, 1),
            msg=f"grep failed in recompression workflow for {input_path}. Check logs: {stdout_path}, {stderr_path}",
        )

        recomp_result = measure_command(
            _recompress_cmd(tool, decompressed_path),
            stdout_path=recompressed_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            recomp_result,
            allowed=(0,),
            msg=f"{tool} recompression failed for {input_path}. Check logs: {stderr_path}",
        )

        if not os.path.exists(recompressed_path) or os.path.getsize(recompressed_path) == 0:
            raise RuntimeError(f"{tool} failed to produce recompressed temp file: {recompressed_path}")

        if run_idx < WARMUP_RUNS:
            continue

        times.append(
            float(decomp_result["wall_time_s"]) +
            float(grep_result["wall_time_s"]) +
            float(recomp_result["wall_time_s"])
        )

        peak_memories.append(
            max(
                float(decomp_result["peak_memory_mb"]),
                float(grep_result["peak_memory_mb"]),
                float(recomp_result["peak_memory_mb"]),
            )
        )

    avg_time = sum(times) / len(times)
    avg_peak_memory = sum(peak_memories) / len(peak_memories)

    print(
        f"    {tool}: avg_time={avg_time:.6f}s over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    return {
        "wall_time_s": round(avg_time, 6),
        "peak_memory_mb": round(avg_peak_memory, 6),
        "return_code": 0,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


def _measure_streaming_search(tool: str, input_path: str, query: str) -> dict[str, Any]:
    compressed_parent_tool = "gzip" if tool == "zgrep" else "bzip2"
    compressed_path = get_compressed_path(input_path, compressed_parent_tool)

    stdout_path, stderr_path = _tool_log_paths(Path(input_path).name, f"{tool}_search")

    cmd = build_search_command(
        tool=tool,
        compressed_path=compressed_path,
        query=query,
        dummy_output_path=None,
        threads=THREADS,
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):
        result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)

        _ensure_rc_ok(
            result,
            allowed=(0, 1),
            msg=f"{tool} failed for {input_path}. Check logs: {stdout_path}, {stderr_path}",
        )

        if run_idx < WARMUP_RUNS:
            continue

        times.append(float(result["wall_time_s"]))
        peak_memories.append(float(result["peak_memory_mb"]))

    avg_time = sum(times) / len(times)
    avg_peak_memory = sum(peak_memories) / len(peak_memories)

    print(
        f"    {tool}: avg_time={avg_time:.6f}s over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    return {
        "return_code": 0,
        "wall_time_s": round(avg_time, 6),
        "peak_memory_mb": round(avg_peak_memory, 6),
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


# =====================
# Formatting helpers
# =====================

def _format_time_table(df: pd.DataFrame, rel_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    out["TIC (s)"] = out["TIC (s)"].apply(
        lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
    )
    for col in rel_cols:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )
    return out


def _format_mem_table(df: pd.DataFrame, rel_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    out["TIC (MB)"] = out["TIC (MB)"].apply(
        lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
    )
    for col in rel_cols:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )
    return out


def _format_entropy_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["Plain Text", "TIC", "PIC", "gzip", "bzip2", "lz4"]:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )
    return out


# =====================
# Main
# =====================

def main() -> None:
    _validate_inputs()

    prev_table2_df = _load_previous_df(LOOKUP_TIME_NO_RECOMP_CSV)
    prev_table3_df = _load_previous_df(LOOKUP_TIME_WITH_RECOMP_CSV)
    prev_table4_df = _load_previous_df(LOOKUP_MEMORY_CSV)
    prev_table7_df = _load_previous_df(LOOKUP_TIME_STREAMING_CSV)
    prev_table10_df = _load_previous_df(ENTROPY_CSV)

    print("[INFO] Ensuring compressed files exist...", flush=True)
    for input_path in INPUT_FILES:
        ensure_compressed_files(RUN_TOOLS, input_path, threads=THREADS, force=False)

    table2_rows: list[dict[str, Any]] = []
    table3_rows: list[dict[str, Any]] = []
    table4_rows: list[dict[str, Any]] = []
    table7_rows: list[dict[str, Any]] = []
    table10_rows: list[dict[str, Any]] = []

    tmp_dir = tempfile.mkdtemp(prefix="run_search_")

    try:
        for file_idx, input_path in enumerate(INPUT_FILES, start=1):
            file_name = Path(input_path).name
            print(f"[INFO] File {file_idx}/{len(INPUT_FILES)}: {file_name}", flush=True)

            # =========================
            # TIC native lookup
            # =========================
            if _should_rerun("TIC", prev_table2_df, file_name, "TIC (s)"):
                print("  [INFO] TIC -> direct compressed lookup...", flush=True)
                tic_native = _measure_native_search("TIC", input_path, SEARCH_QUERY, tmp_dir)
                tic_search_time = float(tic_native["wall_time_s"])
                tic_search_mem = float(tic_native["peak_memory_mb"])
                print(
                    f"  [DONE] TIC lookup: time={tic_search_time:.3f}s, "
                    f"peak_mem={tic_search_mem:.3f} MB",
                    flush=True,
                )
            else:
                tic_search_time = float(_lookup_previous_value(prev_table2_df, file_name, "TIC (s)"))
                tic_search_mem = float(_lookup_previous_value(prev_table4_df, file_name, "TIC (MB)"))
                print("  [SKIP] TIC: reused previous CSV values", flush=True)

            # =========================
            # PIC native lookup
            # =========================
            if _should_rerun("PIC", prev_table2_df, file_name, "PIC"):
                print("  [INFO] PIC -> direct compressed lookup...", flush=True)
                pic_native = _measure_native_search("PIC", input_path, SEARCH_QUERY, tmp_dir)
                pic_search_time = float(pic_native["wall_time_s"])
                pic_search_mem = float(pic_native["peak_memory_mb"])
                print(
                    f"  [DONE] PIC lookup: time={pic_search_time:.3f}s, "
                    f"peak_mem={pic_search_mem:.3f} MB",
                    flush=True,
                )
            else:
                prev_ratio = float(_lookup_previous_value(prev_table2_df, file_name, "PIC"))
                prev_mem_ratio = float(_lookup_previous_value(prev_table4_df, file_name, "PIC"))
                pic_search_time = tic_search_time * prev_ratio
                pic_search_mem = tic_search_mem * prev_mem_ratio
                print("  [SKIP] PIC: reused previous CSV values", flush=True)

            # =========================
            # Table 2: decompress + search
            # =========================
            no_recomp_results: dict[str, dict[str, Any]] = {}
            for tool in ["gzip", "bzip2", "lz4"]:
                if _should_rerun(tool, prev_table2_df, file_name, tool):
                    print(f"  [INFO] {tool} -> decompress + search...", flush=True)
                    res = _measure_decompress_search_only(tool, input_path, SEARCH_QUERY, tmp_dir)
                    no_recomp_results[tool] = res
                    print(
                        f"  [DONE] {tool} no-recomp workflow: "
                        f"time={float(res['wall_time_s']):.3f}s, "
                        f"peak_mem={float(res['peak_memory_mb']):.3f} MB",
                        flush=True,
                    )
                else:
                    prev_ratio = float(_lookup_previous_value(prev_table2_df, file_name, tool))
                    prev_mem_ratio = float(_lookup_previous_value(prev_table4_df, file_name, tool))
                    no_recomp_results[tool] = {
                        "wall_time_s": tic_search_time * prev_ratio,
                        "peak_memory_mb": tic_search_mem * prev_mem_ratio,
                    }
                    print(f"  [SKIP] {tool} no-recomp: reused previous CSV values", flush=True)

            # =========================
            # Table 3: decompress + search + recompress
            # =========================
            recomp_results: dict[str, dict[str, Any]] = {}
            for tool in ["gzip", "bzip2", "lz4"]:
                if _should_rerun(tool, prev_table3_df, file_name, tool):
                    print(f"  [INFO] {tool} -> decompress + search + recompress...", flush=True)
                    res = _measure_decompress_search_recompress(tool, input_path, SEARCH_QUERY, tmp_dir)
                    recomp_results[tool] = res
                    print(
                        f"  [DONE] {tool} recomp workflow: "
                        f"time={float(res['wall_time_s']):.3f}s, "
                        f"peak_mem={float(res['peak_memory_mb']):.3f} MB",
                        flush=True,
                    )
                else:
                    prev_ratio = float(_lookup_previous_value(prev_table3_df, file_name, tool))
                    recomp_results[tool] = {
                        "wall_time_s": tic_search_time * prev_ratio,
                        "peak_memory_mb": no_recomp_results[tool]["peak_memory_mb"],
                    }
                    print(f"  [SKIP] {tool} recomp: reused previous CSV values", flush=True)

            # =========================
            # Table 7: zgrep / bzgrep streaming compressed lookup
            # =========================
            if _should_rerun("zgrep", prev_table7_df, file_name, "zgrep"):
                print("  [INFO] zgrep -> compressed lookup...", flush=True)
                zgrep_res = _measure_streaming_search("zgrep", input_path, SEARCH_QUERY)
                zgrep_time = float(zgrep_res["wall_time_s"])
                print(f"  [DONE] zgrep: time={zgrep_time:.3f}s", flush=True)
            else:
                prev_ratio = float(_lookup_previous_value(prev_table7_df, file_name, "zgrep"))
                zgrep_time = tic_search_time * prev_ratio
                print("  [SKIP] zgrep: reused previous CSV values", flush=True)

            if _should_rerun("bzgrep", prev_table7_df, file_name, "bzgrep"):
                print("  [INFO] bzgrep -> compressed lookup...", flush=True)
                bzgrep_res = _measure_streaming_search("bzgrep", input_path, SEARCH_QUERY)
                bzgrep_time = float(bzgrep_res["wall_time_s"])
                print(f"  [DONE] bzgrep: time={bzgrep_time:.3f}s", flush=True)
            else:
                prev_ratio = float(_lookup_previous_value(prev_table7_df, file_name, "bzgrep"))
                bzgrep_time = tic_search_time * prev_ratio
                print("  [SKIP] bzgrep: reused previous CSV values", flush=True)

            # =========================
            # Table rows
            # =========================

            table2_rows.append({
                "File Name": file_name,
                "TIC (s)": round(tic_search_time, DECIMALS),
                "PIC": safe_ratio(pic_search_time, tic_search_time, decimals=DECIMALS),
                "gzip": safe_ratio(no_recomp_results["gzip"]["wall_time_s"], tic_search_time, decimals=DECIMALS),
                "bzip2": safe_ratio(no_recomp_results["bzip2"]["wall_time_s"], tic_search_time, decimals=DECIMALS),
                "lz4": safe_ratio(no_recomp_results["lz4"]["wall_time_s"], tic_search_time, decimals=DECIMALS),
            })

            table3_rows.append({
                "File Name": file_name,
                "TIC (s)": round(tic_search_time, DECIMALS),
                "PIC": safe_ratio(pic_search_time, tic_search_time, decimals=DECIMALS),
                "gzip": safe_ratio(recomp_results["gzip"]["wall_time_s"], tic_search_time, decimals=DECIMALS),
                "bzip2": safe_ratio(recomp_results["bzip2"]["wall_time_s"], tic_search_time, decimals=DECIMALS),
                "lz4": safe_ratio(recomp_results["lz4"]["wall_time_s"], tic_search_time, decimals=DECIMALS),
            })

            # Table 4 memory:
            # TIC absolute memory is direct lookup memory.
            # Other tools use the maximum peak memory from the with-recompression workflow.
            table4_rows.append({
                "File Name": file_name,
                "TIC (MB)": round(tic_search_mem, DECIMALS),
                "PIC": safe_ratio(pic_search_mem, tic_search_mem, decimals=DECIMALS),
                "gzip": safe_ratio(recomp_results["gzip"]["peak_memory_mb"], tic_search_mem, decimals=DECIMALS),
                "bzip2": safe_ratio(recomp_results["bzip2"]["peak_memory_mb"], tic_search_mem, decimals=DECIMALS),
                "lz4": safe_ratio(recomp_results["lz4"]["peak_memory_mb"], tic_search_mem, decimals=DECIMALS),
            })

            table7_rows.append({
                "File Name": file_name,
                "TIC (s)": round(tic_search_time, DECIMALS),
                "PIC": safe_ratio(pic_search_time, tic_search_time, decimals=DECIMALS),
                "zgrep": safe_ratio(zgrep_time, tic_search_time, decimals=DECIMALS),
                "bzgrep": safe_ratio(bzgrep_time, tic_search_time, decimals=DECIMALS),
            })

            # =========================
            # Entropy
            # =========================
            if (
                "entropy" in FORCE_RERUN_SEARCH_TOOLS
                or prev_table10_df is None
                or _lookup_previous_value(prev_table10_df, file_name, "TIC") is None
            ):
                print("  [INFO] Computing entropy values...", flush=True)
                entropy_row = {
                    "File Name": file_name,
                    "Plain Text": compute_file_entropy(input_path, decimals=DECIMALS),
                    "TIC": compute_file_entropy(get_compressed_path(input_path, "TIC"), decimals=DECIMALS),
                    "PIC": compute_file_entropy(get_compressed_path(input_path, "PIC"), decimals=DECIMALS),
                    "gzip": compute_file_entropy(get_compressed_path(input_path, "gzip"), decimals=DECIMALS),
                    "bzip2": compute_file_entropy(get_compressed_path(input_path, "bzip2"), decimals=DECIMALS),
                    "lz4": compute_file_entropy(get_compressed_path(input_path, "lz4"), decimals=DECIMALS),
                }
                print("  [DONE] Entropy values computed", flush=True)
            else:
                entropy_row = {
                    "File Name": file_name,
                    "Plain Text": _lookup_previous_value(prev_table10_df, file_name, "Plain Text"),
                    "TIC": _lookup_previous_value(prev_table10_df, file_name, "TIC"),
                    "PIC": _lookup_previous_value(prev_table10_df, file_name, "PIC"),
                    "gzip": _lookup_previous_value(prev_table10_df, file_name, "gzip"),
                    "bzip2": _lookup_previous_value(prev_table10_df, file_name, "bzip2"),
                    "lz4": _lookup_previous_value(prev_table10_df, file_name, "lz4"),
                }
                print("  [SKIP] Entropy: reused previous CSV values", flush=True)

            table10_rows.append(entropy_row)

        # =====================
        # Build DataFrames
        # =====================

        table2_df = pd.DataFrame(table2_rows)[["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]]
        table3_df = pd.DataFrame(table3_rows)[["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]]
        table4_df = pd.DataFrame(table4_rows)[["File Name", "TIC (MB)", "PIC", "gzip", "bzip2", "lz4"]]
        table7_df = pd.DataFrame(table7_rows)[["File Name", "TIC (s)", "PIC", "zgrep", "bzgrep"]]
        table10_df = pd.DataFrame(table10_rows)[["File Name", "Plain Text", "TIC", "PIC", "gzip", "bzip2", "lz4"]]

        table2_df = _append_average_row(table2_df)
        table3_df = _append_average_row(table3_df)
        table4_df = _append_average_row(table4_df)
        table7_df = _append_average_row(table7_df)
        table10_df = _append_average_row(table10_df)

        # =====================
        # Format outputs
        # =====================

        table2_out = _format_time_table(table2_df, ["PIC", "gzip", "bzip2", "lz4"])
        table3_out = _format_time_table(table3_df, ["PIC", "gzip", "bzip2", "lz4"])
        table4_out = _format_mem_table(table4_df, ["PIC", "gzip", "bzip2", "lz4"])
        table7_out = _format_time_table(table7_df, ["PIC", "zgrep", "bzgrep"])
        table10_out = _format_entropy_table(table10_df)

        print("[INFO] Writing CSV and LaTeX outputs...", flush=True)

        write_dataframe_csv(table2_out, LOOKUP_TIME_NO_RECOMP_CSV)
        write_dataframe_csv(table3_out, LOOKUP_TIME_WITH_RECOMP_CSV)
        write_dataframe_csv(table4_out, LOOKUP_MEMORY_CSV)
        write_dataframe_csv(table7_out, LOOKUP_TIME_STREAMING_CSV)
        write_dataframe_csv(table10_out, ENTROPY_CSV)

        build_grouped_latex_table(
            df=table2_out,
            tex_path=LOOKUP_TIME_NO_RECOMP_TEX,
            caption=CAPTION_TABLE_2,
            label=LABEL_TABLE_2,
            group_headers=[
                ("File Name", 1),
                ("Absolute (s)", 1),
                ("Relative to TIC", 4),
            ],
            column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
            align_spec="cccccc",
        )

        build_grouped_latex_table(
            df=table3_out,
            tex_path=LOOKUP_TIME_WITH_RECOMP_TEX,
            caption=CAPTION_TABLE_3,
            label=LABEL_TABLE_3,
            group_headers=[
                ("File Name", 1),
                ("Absolute (s)", 1),
                ("Relative to TIC", 4),
            ],
            column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
            align_spec="cccccc",
        )

        build_grouped_latex_table(
            df=table4_out,
            tex_path=LOOKUP_MEMORY_TEX,
            caption=CAPTION_TABLE_4,
            label=LABEL_TABLE_4,
            group_headers=[
                ("File Name", 1),
                ("Absolute (MB)", 1),
                ("Relative to TIC", 4),
            ],
            column_headers=["File Name", "TIC (MB)", "PIC", "gzip", "bzip2", "lz4"],
            align_spec="cccccc",
        )

        build_grouped_latex_table(
            df=table7_out,
            tex_path=LOOKUP_TIME_STREAMING_TEX,
            caption=CAPTION_TABLE_7,
            label=LABEL_TABLE_7,
            group_headers=[
                ("File Name", 1),
                ("Absolute (s)", 1),
                ("Relative to TIC", 3),
            ],
            column_headers=["File Name", "TIC (s)", "PIC", "zgrep", "bzgrep"],
            align_spec="ccccc",
        )

        build_simple_latex_table(
            df=table10_out,
            tex_path=ENTROPY_TEX,
            caption=CAPTION_TABLE_10,
            label=LABEL_TABLE_10,
            column_headers=["File Name", "Plain Text", "TIC", "PIC", "gzip", "bzip2", "lz4"],
            align_spec="ccccccc",
        )

        print(f"Wrote: {LOOKUP_TIME_NO_RECOMP_CSV}")
        print(f"Wrote: {LOOKUP_TIME_NO_RECOMP_TEX}")
        print(f"Wrote: {LOOKUP_TIME_WITH_RECOMP_CSV}")
        print(f"Wrote: {LOOKUP_TIME_WITH_RECOMP_TEX}")
        print(f"Wrote: {LOOKUP_MEMORY_CSV}")
        print(f"Wrote: {LOOKUP_MEMORY_TEX}")
        print(f"Wrote: {LOOKUP_TIME_STREAMING_CSV}")
        print(f"Wrote: {LOOKUP_TIME_STREAMING_TEX}")
        print(f"Wrote: {ENTROPY_CSV}")
        print(f"Wrote: {ENTROPY_TEX}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()












##############################






# #!/usr/bin/env python3
# """
# run_search.py

# Generate:
# - Table 2: Lookup Time (without Re-compression)
# - Table 3: Lookup Time (with Re-compression)
# - Table 4: Peak memory used for compression, decompression, and search
# - Table 7: Lookup Time on a Compressed File Compared to zgrep and bzgrep
# - Table 10: Entropy of plain text files and compressed files

# Outputs:
# - lookup_time_no_recompression_results.csv
# - lookup_time_no_recompression_table.tex
# - lookup_time_with_recompression_results.csv
# - lookup_time_with_recompression_table.tex
# - lookup_memory_results.csv
# - lookup_memory_table.tex
# - lookup_time_streaming_results.csv
# - lookup_time_streaming_table.tex
# - entropy_results.csv
# - entropy_table.tex

# Features:
# - TIC is the absolute baseline for Tables 2, 3, 4, and 7.
# - Time tables use 3 decimals for TIC absolute and relative columns.
# - Memory table uses 2 decimals.
# - Entropy table uses 3 decimals.
# - Adds Average rows.
# - Prints progress to terminal.
# - Supports selective rerun of search-specific measurements.
# - Reuses compression/decompression CSVs generated earlier.
# """

# from __future__ import annotations

# import os
# import shutil
# import tempfile
# from pathlib import Path
# from typing import Any

# import pandas as pd

# from benchmark_utils import (
#     build_grep_pipeline,
#     build_grouped_latex_table,
#     build_search_command,
#     build_simple_latex_table,
#     compute_file_entropy,
#     ensure_compressed_files,
#     format_number,
#     get_compressed_path,
#     load_compression_metrics,
#     load_decompression_metrics,
#     lookup_result_value,
#     measure_command,
#     measure_pipeline,
#     safe_ratio,
#     write_dataframe_csv,
# )

# # =====================
# # User Config
# # =====================

# INPUT_FILES = [
#     "../textFiles/f1.txt",
#     "../textFiles/f2.txt",
#     "../textFiles/f3.txt",
#     "../textFiles/f4.txt",
#     "../textFiles/f5.txt",
#     "../textFiles/f6.txt",
#     "../textFiles/f7.txt",
#     "../textFiles/f8.txt",
#     "../textFiles/f9.txt",
#     "../textFiles/f10.txt",
# ]


# TOOLS = ["PIC", "TIC", "gzip", "bzip2", "lz4"]
# TABLE_TOOLS = ["TIC", "PIC", "gzip", "bzip2", "lz4"]

# THREADS = 1
# DECIMALS = 3

# # Lookup workload
# SEARCH_QUERY = "the"

# # Search-specific rerun controls
# # Supported keys:
# #   "TIC", "PIC", "gzip", "bzip2", "lz4", "zgrep", "bzgrep"
# FORCE_RERUN_SEARCH_TOOLS = set()

# RESULTS_DIR = "."
# LOG_DIR = "results/logs/search"

# LOOKUP_TIME_NO_RECOMP_CSV = os.path.join(RESULTS_DIR, "lookup_time_no_recompression_results.csv")
# LOOKUP_TIME_NO_RECOMP_TEX = os.path.join(TABLES_DIR, "lookup_time_no_recompression_table.tex")

# LOOKUP_TIME_WITH_RECOMP_CSV = os.path.join(RESULTS_DIR, "lookup_time_with_recompression_results.csv")
# LOOKUP_TIME_WITH_RECOMP_TEX = os.path.join(TABLES_DIR, "lookup_time_with_recompression_table.tex")

# LOOKUP_MEMORY_CSV = os.path.join(RESULTS_DIR, "lookup_memory_results.csv")
# LOOKUP_MEMORY_TEX = os.path.join(TABLES_DIR, "lookup_memory_table.tex")

# LOOKUP_TIME_STREAMING_CSV = os.path.join(RESULTS_DIR, "lookup_time_streaming_results.csv")
# LOOKUP_TIME_STREAMING_TEX = os.path.join(TABLES_DIR, "lookup_time_streaming_table.tex")

# ENTROPY_CSV = os.path.join(RESULTS_DIR, "entropy_results.csv")
# ENTROPY_TEX = os.path.join(TABLES_DIR, "entropy_table.tex")

# COMPRESSION_TIME_CSV = os.path.join(RESULTS_DIR, "compression_time_results.csv")
# DECOMPRESSION_TIME_CSV = os.path.join(RESULTS_DIR, "decompression_time_results.csv")

# CAPTION_TABLE_2 = "Lookup Time (without Re-compression)."
# LABEL_TABLE_2 = "tab:lookup_no_recompression"

# CAPTION_TABLE_3 = "Lookup Time (with Re-compression)."
# LABEL_TABLE_3 = "tab:lookup_with_recompression"

# CAPTION_TABLE_4 = "Peak memory used for compression, decompression and lookup."
# LABEL_TABLE_4 = "tab:lookup_memory"

# CAPTION_TABLE_7 = "Lookup Time on a Compressed File Compared to zgrep and bzgrep."
# LABEL_TABLE_7 = "tab:lookup_streaming"

# CAPTION_TABLE_10 = "Entropy of plain text files and compressed files."
# LABEL_TABLE_10 = "tab:entropy"


# # =====================
# # Validation / helpers
# # =====================

# def _validate_inputs() -> None:
#     missing = [p for p in INPUT_FILES if not os.path.exists(p)]
#     if missing:
#         raise FileNotFoundError(f"Missing input files: {missing}")

#     if not os.path.exists(COMPRESSION_TIME_CSV):
#         raise FileNotFoundError(
#             f"Missing prerequisite CSV: {COMPRESSION_TIME_CSV}. Run run_compression.py first."
#         )
#     if not os.path.exists(DECOMPRESSION_TIME_CSV):
#         raise FileNotFoundError(
#             f"Missing prerequisite CSV: {DECOMPRESSION_TIME_CSV}. Run run_decompression.py first."
#         )


# def _tool_log_paths(file_name: str, suffix: str) -> tuple[str, str]:
#     Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
#     stem = Path(file_name).stem
#     stdout_path = os.path.join(LOG_DIR, f"{suffix}_{stem}_stdout.txt")
#     stderr_path = os.path.join(LOG_DIR, f"{suffix}_{stem}_stderr.txt")
#     return stdout_path, stderr_path


# def _load_previous_df(csv_path: str) -> pd.DataFrame | None:
#     if os.path.exists(csv_path):
#         return pd.read_csv(csv_path)
#     return None


# def _lookup_previous_value(df: pd.DataFrame | None, file_name: str, column_name: str) -> Any:
#     if df is None or column_name not in df.columns:
#         return None
#     rows = df[df["File Name"] == file_name]
#     if rows.empty:
#         return None
#     value = rows.iloc[0][column_name]
#     if pd.isna(value):
#         return None
#     return value


# def _append_average_row(df: pd.DataFrame, first_col: str = "File Name") -> pd.DataFrame:
#     avg_row: dict[str, Any] = {first_col: "Average"}
#     for col in df.columns:
#         if col == first_col:
#             continue
#         if pd.api.types.is_numeric_dtype(df[col]):
#             avg_row[col] = df[col].mean()
#         else:
#             avg_row[col] = ""
#     return pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)


# def _require_metric(df: pd.DataFrame, file_name: str, column_name: str) -> float:
#     value = lookup_result_value(df, file_name, column_name)
#     if value is None or value == "":
#         raise RuntimeError(f"Missing metric: file={file_name}, column={column_name}")
#     return float(value)


# # =====================
# # Search measurements
# # =====================

# def _measure_native_search(tool: str, input_path: str, query: str, tmp_dir: str) -> dict[str, Any]:
#     compressed_path = get_compressed_path(input_path, tool)
#     dummy_out = os.path.join(tmp_dir, f"{Path(input_path).stem}_{tool.lower()}_dummy.txt")
#     stdout_path, stderr_path = _tool_log_paths(Path(input_path).name, f"{tool}_search")
#     cmd = build_search_command(
#         tool=tool,
#         compressed_path=compressed_path,
#         query=query,
#         dummy_output_path=dummy_out,
#         threads=THREADS,
#     )
#     result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)
#     if result["return_code"] != 0:
#         raise RuntimeError(
#             f"{tool} search failed for {input_path}. Check logs: {stdout_path}, {stderr_path}"
#         )
#     result["stdout_path"] = stdout_path
#     result["stderr_path"] = stderr_path
#     return result


# def _measure_decompress_plus_grep(tool: str, input_path: str, query: str) -> dict[str, Any]:
#     compressed_path = get_compressed_path(input_path, tool)
#     stdout_path, stderr_path = _tool_log_paths(Path(input_path).name, f"{tool}_grep_pipeline")
#     commands = build_grep_pipeline(tool, compressed_path, query)
#     result = measure_pipeline(commands, stdout_path=stdout_path, stderr_path=stderr_path)
#     rc = result["return_code"]
#     if rc not in (0, 1):
#         raise RuntimeError(
#             f"{tool} decompress+grep failed for {input_path}. Check logs: {stdout_path}, {stderr_path}"
#         )
#     result["stdout_path"] = stdout_path
#     result["stderr_path"] = stderr_path
#     return result


# def _measure_streaming_search(tool: str, input_path: str, query: str) -> dict[str, Any]:
#     compressed_parent_tool = "gzip" if tool == "zgrep" else "bzip2"
#     compressed_path = get_compressed_path(input_path, compressed_parent_tool)
#     stdout_path, stderr_path = _tool_log_paths(Path(input_path).name, f"{tool}_search")
#     cmd = build_search_command(
#         tool=tool,
#         compressed_path=compressed_path,
#         query=query,
#         dummy_output_path=None,
#         threads=THREADS,
#     )
#     result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)
#     rc = result["return_code"]
#     if rc not in (0, 1):
#         raise RuntimeError(
#             f"{tool} failed for {input_path}. Check logs: {stdout_path}, {stderr_path}"
#         )
#     result["stdout_path"] = stdout_path
#     result["stderr_path"] = stderr_path
#     return result


# # =====================
# # Formatting helpers
# # =====================

# def _format_time_table(df: pd.DataFrame, rel_cols: list[str]) -> pd.DataFrame:
#     out = df.copy()
#     out["TIC (s)"] = out["TIC (s)"].apply(
#         lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
#     )
#     for col in rel_cols:
#         out[col] = out[col].apply(
#             lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
#         )
#     return out


# def _format_mem_table(df: pd.DataFrame, rel_cols: list[str]) -> pd.DataFrame:
#     out = df.copy()
#     out["TIC (MB)"] = out["TIC (MB)"].apply(
#         lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
#     )
#     for col in rel_cols:
#         out[col] = out[col].apply(
#             lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
#         )
#     return out


# def _format_entropy_table(df: pd.DataFrame) -> pd.DataFrame:
#     out = df.copy()
#     for col in ["Plain Text", "TIC", "PIC", "gzip", "bzip2", "lz4"]:
#         out[col] = out[col].apply(
#             lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
#         )
#     return out


# # =====================
# # Main
# # =====================

# def main() -> None:
#     _validate_inputs()

#     compression_df = load_compression_metrics(COMPRESSION_TIME_CSV)
#     decompression_df = load_decompression_metrics(DECOMPRESSION_TIME_CSV)

#     prev_table2_df = _load_previous_df(LOOKUP_TIME_NO_RECOMP_CSV)
#     prev_table3_df = _load_previous_df(LOOKUP_TIME_WITH_RECOMP_CSV)
#     prev_table4_df = _load_previous_df(LOOKUP_MEMORY_CSV)
#     prev_table7_df = _load_previous_df(LOOKUP_TIME_STREAMING_CSV)
#     prev_table10_df = _load_previous_df(ENTROPY_CSV)

#     print("[INFO] Ensuring compressed files exist...", flush=True)
#     for input_path in INPUT_FILES:
#         ensure_compressed_files(TOOLS, input_path, threads=THREADS, force=False)

#     table2_rows: list[dict[str, Any]] = []
#     table3_rows: list[dict[str, Any]] = []
#     table4_rows: list[dict[str, Any]] = []
#     table7_rows: list[dict[str, Any]] = []
#     table10_rows: list[dict[str, Any]] = []

#     tmp_dir = tempfile.mkdtemp(prefix="run_search_")
#     try:
#         for file_idx, input_path in enumerate(INPUT_FILES, start=1):
#             file_name = Path(input_path).name
#             print(f"[INFO] File {file_idx}/{len(INPUT_FILES)}: {file_name}", flush=True)

#             # Prior metrics from previous scripts
#             tic_comp = _require_metric(compression_df, file_name, "TIC (s)")
#             pic_comp = tic_comp * float(_require_metric(compression_df, file_name, "PIC"))
#             gzip_comp = tic_comp * float(_require_metric(compression_df, file_name, "gzip"))
#             bzip2_comp = tic_comp * float(_require_metric(compression_df, file_name, "bzip2"))
#             lz4_comp = tic_comp * float(_require_metric(compression_df, file_name, "lz4"))

#             tic_decomp = _require_metric(decompression_df, file_name, "TIC (s)")
#             pic_decomp = tic_decomp * float(_require_metric(decompression_df, file_name, "PIC"))
#             gzip_decomp = tic_decomp * float(_require_metric(decompression_df, file_name, "gzip"))
#             bzip2_decomp = tic_decomp * float(_require_metric(decompression_df, file_name, "bzip2"))
#             lz4_decomp = tic_decomp * float(_require_metric(decompression_df, file_name, "lz4"))

#             # Search-specific measurements (or reuse prior CSV values)
#             rerun_tic = "TIC" in FORCE_RERUN_SEARCH_TOOLS
#             rerun_pic = "PIC" in FORCE_RERUN_SEARCH_TOOLS
#             rerun_gzip = "gzip" in FORCE_RERUN_SEARCH_TOOLS
#             rerun_bzip2 = "bzip2" in FORCE_RERUN_SEARCH_TOOLS
#             rerun_lz4 = "lz4" in FORCE_RERUN_SEARCH_TOOLS
#             rerun_zgrep = "zgrep" in FORCE_RERUN_SEARCH_TOOLS
#             rerun_bzgrep = "bzgrep" in FORCE_RERUN_SEARCH_TOOLS

#             # TIC
#             if rerun_tic or prev_table2_df is None or _lookup_previous_value(prev_table2_df, file_name, "TIC (s)") is None:
#                 print("  [INFO] TIC -> native search...", flush=True)
#                 tic_native = _measure_native_search("TIC", input_path, SEARCH_QUERY, tmp_dir)
#                 tic_search_time = float(tic_native["wall_time_s"])
#                 tic_search_mem = float(tic_native["peak_memory_mb"])
#                 print(
#                     f"  [DONE] TIC search: time={tic_search_time:.3f}s, "
#                     f"peak_mem={tic_search_mem:.3f} MB",
#                     flush=True,
#                 )
#             else:
#                 tic_search_time = float(_lookup_previous_value(prev_table2_df, file_name, "TIC (s)"))
#                 tic_search_mem = float(_lookup_previous_value(prev_table4_df, file_name, "TIC (MB)"))
#                 print("  [SKIP] TIC: reused previous CSV values", flush=True)

#             # PIC
#             if rerun_pic or prev_table2_df is None or _lookup_previous_value(prev_table2_df, file_name, "PIC") is None:
#                 print("  [INFO] PIC -> native search...", flush=True)
#                 pic_native = _measure_native_search("PIC", input_path, SEARCH_QUERY, tmp_dir)
#                 pic_search_time = float(pic_native["wall_time_s"])
#                 pic_search_mem = float(pic_native["peak_memory_mb"])
#                 print(
#                     f"  [DONE] PIC search: time={pic_search_time:.3f}s, "
#                     f"peak_mem={pic_search_mem:.3f} MB",
#                     flush=True,
#                 )
#             else:
#                 pic_search_time = None  # will reconstruct from ratio below only if needed in formula-free rows
#                 pic_search_mem = None
#                 print("  [SKIP] PIC: reused previous CSV values", flush=True)

#             # gzip
#             if rerun_gzip or prev_table2_df is None or _lookup_previous_value(prev_table2_df, file_name, "gzip") is None:
#                 print("  [INFO] gzip -> decompress + grep...", flush=True)
#                 gzip_grep = _measure_decompress_plus_grep("gzip", input_path, SEARCH_QUERY)
#                 gzip_search_time = float(gzip_grep["wall_time_s"])
#                 gzip_search_mem = float(gzip_grep["peak_memory_mb"])
#                 print(
#                     f"  [DONE] gzip search workflow: time={gzip_search_time:.3f}s, "
#                     f"peak_mem={gzip_search_mem:.3f} MB",
#                     flush=True,
#                 )
#             else:
#                 gzip_search_time = None
#                 gzip_search_mem = None
#                 print("  [SKIP] gzip: reused previous CSV values", flush=True)

#             # bzip2
#             if rerun_bzip2 or prev_table2_df is None or _lookup_previous_value(prev_table2_df, file_name, "bzip2") is None:
#                 print("  [INFO] bzip2 -> decompress + grep...", flush=True)
#                 bzip2_grep = _measure_decompress_plus_grep("bzip2", input_path, SEARCH_QUERY)
#                 bzip2_search_time = float(bzip2_grep["wall_time_s"])
#                 bzip2_search_mem = float(bzip2_grep["peak_memory_mb"])
#                 print(
#                     f"  [DONE] bzip2 search workflow: time={bzip2_search_time:.3f}s, "
#                     f"peak_mem={bzip2_search_mem:.3f} MB",
#                     flush=True,
#                 )
#             else:
#                 bzip2_search_time = None
#                 bzip2_search_mem = None
#                 print("  [SKIP] bzip2: reused previous CSV values", flush=True)

#             # lz4
#             if rerun_lz4 or prev_table2_df is None or _lookup_previous_value(prev_table2_df, file_name, "lz4") is None:
#                 print("  [INFO] lz4 -> decompress + grep...", flush=True)
#                 lz4_grep = _measure_decompress_plus_grep("lz4", input_path, SEARCH_QUERY)
#                 lz4_search_time = float(lz4_grep["wall_time_s"])
#                 lz4_search_mem = float(lz4_grep["peak_memory_mb"])
#                 print(
#                     f"  [DONE] lz4 search workflow: time={lz4_search_time:.3f}s, "
#                     f"peak_mem={lz4_search_mem:.3f} MB",
#                     flush=True,
#                 )
#             else:
#                 lz4_search_time = None
#                 lz4_search_mem = None
#                 print("  [SKIP] lz4: reused previous CSV values", flush=True)

#             # zgrep
#             if rerun_zgrep or prev_table7_df is None or _lookup_previous_value(prev_table7_df, file_name, "zgrep") is None:
#                 print("  [INFO] zgrep -> compressed lookup...", flush=True)
#                 zgrep_res = _measure_streaming_search("zgrep", input_path, SEARCH_QUERY)
#                 zgrep_time = float(zgrep_res["wall_time_s"])
#                 print(f"  [DONE] zgrep: time={zgrep_time:.3f}s", flush=True)
#             else:
#                 zgrep_time = None
#                 print("  [SKIP] zgrep: reused previous CSV values", flush=True)

#             # bzgrep
#             if rerun_bzgrep or prev_table7_df is None or _lookup_previous_value(prev_table7_df, file_name, "bzgrep") is None:
#                 print("  [INFO] bzgrep -> compressed lookup...", flush=True)
#                 bzgrep_res = _measure_streaming_search("bzgrep", input_path, SEARCH_QUERY)
#                 bzgrep_time = float(bzgrep_res["wall_time_s"])
#                 print(f"  [DONE] bzgrep: time={bzgrep_time:.3f}s", flush=True)
#             else:
#                 bzgrep_time = None
#                 print("  [SKIP] bzgrep: reused previous CSV values", flush=True)

#             # Reconstruct or compute ratios/values
#             if pic_search_time is None:
#                 pic_ratio_prev = _lookup_previous_value(prev_table2_df, file_name, "PIC")
#                 pic_ratio_prev = float(pic_ratio_prev) if pic_ratio_prev is not None else None
#                 pic_search_time = tic_search_time * pic_ratio_prev if pic_ratio_prev is not None else tic_search_time

#             if gzip_search_time is None:
#                 prev_ratio = _lookup_previous_value(prev_table2_df, file_name, "gzip")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 gzip_search_time = max((prev_ratio * tic_search_time) - gzip_decomp, 0.0) if prev_ratio is not None else 0.0

#             if bzip2_search_time is None:
#                 prev_ratio = _lookup_previous_value(prev_table2_df, file_name, "bzip2")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 bzip2_search_time = max((prev_ratio * tic_search_time) - bzip2_decomp, 0.0) if prev_ratio is not None else 0.0

#             if lz4_search_time is None:
#                 prev_ratio = _lookup_previous_value(prev_table2_df, file_name, "lz4")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 lz4_search_time = max((prev_ratio * tic_search_time) - lz4_decomp, 0.0) if prev_ratio is not None else 0.0

#             if pic_search_mem is None:
#                 prev_ratio = _lookup_previous_value(prev_table4_df, file_name, "PIC")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 pic_search_mem = tic_search_mem * prev_ratio if prev_ratio is not None else tic_search_mem

#             if gzip_search_mem is None:
#                 prev_ratio = _lookup_previous_value(prev_table4_df, file_name, "gzip")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 gzip_search_mem = tic_search_mem * prev_ratio if prev_ratio is not None else tic_search_mem

#             if bzip2_search_mem is None:
#                 prev_ratio = _lookup_previous_value(prev_table4_df, file_name, "bzip2")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 bzip2_search_mem = tic_search_mem * prev_ratio if prev_ratio is not None else tic_search_mem

#             if lz4_search_mem is None:
#                 prev_ratio = _lookup_previous_value(prev_table4_df, file_name, "lz4")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 lz4_search_mem = tic_search_mem * prev_ratio if prev_ratio is not None else tic_search_mem

#             if zgrep_time is None:
#                 prev_ratio = _lookup_previous_value(prev_table7_df, file_name, "zgrep")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 zgrep_time = tic_search_time * prev_ratio if prev_ratio is not None else tic_search_time

#             if bzgrep_time is None:
#                 prev_ratio = _lookup_previous_value(prev_table7_df, file_name, "bzgrep")
#                 prev_ratio = float(prev_ratio) if prev_ratio is not None else None
#                 bzgrep_time = tic_search_time * prev_ratio if prev_ratio is not None else tic_search_time

#             # Table 2
#             table2_rows.append({
#                 "File Name": file_name,
#                 "TIC (s)": round(tic_search_time, DECIMALS),
#                 "PIC": safe_ratio(pic_search_time, tic_search_time, decimals=DECIMALS),
#                 "gzip": safe_ratio(gzip_decomp + gzip_search_time, tic_search_time, decimals=DECIMALS),
#                 "bzip2": safe_ratio(bzip2_decomp + bzip2_search_time, tic_search_time, decimals=DECIMALS),
#                 "lz4": safe_ratio(lz4_decomp + lz4_search_time, tic_search_time, decimals=DECIMALS),
#             })

#             # Table 3
#             table3_rows.append({
#                 "File Name": file_name,
#                 "TIC (s)": round(tic_search_time, DECIMALS),
#                 "PIC": safe_ratio(pic_search_time, tic_search_time, decimals=DECIMALS),
#                 "gzip": safe_ratio(gzip_comp + gzip_decomp + gzip_search_time, tic_search_time, decimals=DECIMALS),
#                 "bzip2": safe_ratio(bzip2_comp + bzip2_decomp + bzip2_search_time, tic_search_time, decimals=DECIMALS),
#                 "lz4": safe_ratio(lz4_comp + lz4_decomp + lz4_search_time, tic_search_time, decimals=DECIMALS),
#             })

#             # Table 4
#             # Current implementation uses available measured/reconstructed peak search memory as the table source.
#             table4_rows.append({
#                 "File Name": file_name,
#                 "TIC (MB)": round(tic_search_mem, DECIMALS),
#                 "PIC": safe_ratio(pic_search_mem, tic_search_mem, decimals=DECIMALS),
#                 "gzip": safe_ratio(gzip_search_mem, tic_search_mem, decimals=DECIMALS),
#                 "bzip2": safe_ratio(bzip2_search_mem, tic_search_mem, decimals=DECIMALS),
#                 "lz4": safe_ratio(lz4_search_mem, tic_search_mem, decimals=DECIMALS),
#             })

#             # Table 7
#             table7_rows.append({
#                 "File Name": file_name,
#                 "TIC (s)": round(tic_search_time, DECIMALS),
#                 "PIC": safe_ratio(pic_search_time, tic_search_time, decimals=DECIMALS),
#                 "zgrep": safe_ratio(zgrep_time, tic_search_time, decimals=DECIMALS),
#                 "bzgrep": safe_ratio(bzgrep_time, tic_search_time, decimals=DECIMALS),
#             })

#             # Table 10
#             print("  [INFO] Computing entropy values...", flush=True)
#             table10_rows.append({
#                 "File Name": file_name,
#                 "Plain Text": compute_file_entropy(input_path, decimals=DECIMALS),
#                 "TIC": compute_file_entropy(get_compressed_path(input_path, "TIC"), decimals=DECIMALS),
#                 "PIC": compute_file_entropy(get_compressed_path(input_path, "PIC"), decimals=DECIMALS),
#                 "gzip": compute_file_entropy(get_compressed_path(input_path, "gzip"), decimals=DECIMALS),
#                 "bzip2": compute_file_entropy(get_compressed_path(input_path, "bzip2"), decimals=DECIMALS),
#                 "lz4": compute_file_entropy(get_compressed_path(input_path, "lz4"), decimals=DECIMALS),
#             })
#             print("  [DONE] Entropy values computed", flush=True)

#         # Build DataFrames
#         table2_df = pd.DataFrame(table2_rows)[["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]]
#         table3_df = pd.DataFrame(table3_rows)[["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]]
#         table4_df = pd.DataFrame(table4_rows)[["File Name", "TIC (MB)", "PIC", "gzip", "bzip2", "lz4"]]
#         table7_df = pd.DataFrame(table7_rows)[["File Name", "TIC (s)", "PIC", "zgrep", "bzgrep"]]
#         table10_df = pd.DataFrame(table10_rows)[["File Name", "Plain Text", "TIC", "PIC", "gzip", "bzip2", "lz4"]]

#         table2_df = _append_average_row(table2_df)
#         table3_df = _append_average_row(table3_df)
#         table4_df = _append_average_row(table4_df)
#         table7_df = _append_average_row(table7_df)
#         table10_df = _append_average_row(table10_df)

#         # Format for output
#         table2_out = _format_time_table(table2_df, ["PIC", "gzip", "bzip2", "lz4"])
#         table3_out = _format_time_table(table3_df, ["PIC", "gzip", "bzip2", "lz4"])
#         table4_out = _format_mem_table(table4_df, ["PIC", "gzip", "bzip2", "lz4"])
#         table7_out = _format_time_table(table7_df, ["PIC", "zgrep", "bzgrep"])
#         table10_out = _format_entropy_table(table10_df)

#         print("[INFO] Writing CSV and LaTeX outputs...", flush=True)

#         write_dataframe_csv(table2_out, LOOKUP_TIME_NO_RECOMP_CSV)
#         write_dataframe_csv(table3_out, LOOKUP_TIME_WITH_RECOMP_CSV)
#         write_dataframe_csv(table4_out, LOOKUP_MEMORY_CSV)
#         write_dataframe_csv(table7_out, LOOKUP_TIME_STREAMING_CSV)
#         write_dataframe_csv(table10_out, ENTROPY_CSV)

#         build_grouped_latex_table(
#             df=table2_out,
#             tex_path=LOOKUP_TIME_NO_RECOMP_TEX,
#             caption=CAPTION_TABLE_2,
#             label=LABEL_TABLE_2,
#             group_headers=[
#                 ("File Name", 1),
#                 ("Absolute (s)", 1),
#                 ("Relative to TIC", 4),
#             ],
#             column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
#             align_spec="cccccc",
#         )

#         build_grouped_latex_table(
#             df=table3_out,
#             tex_path=LOOKUP_TIME_WITH_RECOMP_TEX,
#             caption=CAPTION_TABLE_3,
#             label=LABEL_TABLE_3,
#             group_headers=[
#                 ("File Name", 1),
#                 ("Absolute (s)", 1),
#                 ("Relative to TIC", 4),
#             ],
#             column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
#             align_spec="cccccc",
#         )

#         build_grouped_latex_table(
#             df=table4_out,
#             tex_path=LOOKUP_MEMORY_TEX,
#             caption=CAPTION_TABLE_4,
#             label=LABEL_TABLE_4,
#             group_headers=[
#                 ("File Name", 1),
#                 ("Absolute (MB)", 1),
#                 ("Relative to TIC", 4),
#             ],
#             column_headers=["File Name", "TIC (MB)", "PIC", "gzip", "bzip2", "lz4"],
#             align_spec="cccccc",
#         )

#         build_grouped_latex_table(
#             df=table7_out,
#             tex_path=LOOKUP_TIME_STREAMING_TEX,
#             caption=CAPTION_TABLE_7,
#             label=LABEL_TABLE_7,
#             group_headers=[
#                 ("File Name", 1),
#                 ("Absolute (s)", 1),
#                 ("Relative to TIC", 3),
#             ],
#             column_headers=["File Name", "TIC (s)", "PIC", "zgrep", "bzgrep"],
#             align_spec="ccccc",
#         )

#         build_simple_latex_table(
#             df=table10_out,
#             tex_path=ENTROPY_TEX,
#             caption=CAPTION_TABLE_10,
#             label=LABEL_TABLE_10,
#             column_headers=["File Name", "Plain Text", "TIC", "PIC", "gzip", "bzip2", "lz4"],
#             align_spec="ccccccc",
#         )

#         print(f"Wrote: {LOOKUP_TIME_NO_RECOMP_CSV}")
#         print(f"Wrote: {LOOKUP_TIME_NO_RECOMP_TEX}")
#         print(f"Wrote: {LOOKUP_TIME_WITH_RECOMP_CSV}")
#         print(f"Wrote: {LOOKUP_TIME_WITH_RECOMP_TEX}")
#         print(f"Wrote: {LOOKUP_MEMORY_CSV}")
#         print(f"Wrote: {LOOKUP_MEMORY_TEX}")
#         print(f"Wrote: {LOOKUP_TIME_STREAMING_CSV}")
#         print(f"Wrote: {LOOKUP_TIME_STREAMING_TEX}")
#         print(f"Wrote: {ENTROPY_CSV}")
#         print(f"Wrote: {ENTROPY_TEX}")

#     finally:
#         shutil.rmtree(tmp_dir, ignore_errors=True)


# if __name__ == "__main__":
#     main()
