#!/usr/bin/env python3
"""
run_compression.py

Generate:
- Table 1: Compression Ratio (CR) for all schemes
- Table 5: Compression Time

Outputs:
- cr_results.csv
- cr_table.tex
- compression_time_results.csv
- compression_time_table.tex

Features:
- TIC is the absolute baseline for compression time.
- CR values are absolute.
- Original Size (MB) is shown as an integer.
- CR values use 2 decimal places.
- Compression-time table uses 3 decimals for TIC absolute time and
  3 decimals for relative columns.
- Supports selective recompression of specific tools only.
- Reuses previous CSV values for skipped tools when available.
- Adds an Average row to both tables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

from dependencies import preflight

from benchmark_utils import (
    BENCHMARK_INPUT_FILES,
    build_compress_command,
    build_grouped_latex_table,
    bytes_to_mb,
    compute_compression_ratio,
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
#  ]

TOOLS = ["PIC", "TIC", "gzip", "bzip2", "lz4"]
TABLE_TOOLS = ["TIC", "PIC", "gzip", "bzip2", "lz4"]
THREADS = 1
DECIMALS = 3

NUM_RUNS = 10
WARMUP_RUNS = 1

# Recompress only selected tools.
# Examples:
#   set()                         -> rerun nothing, reuse prior CSV values where possible
#   {"lz4"}                       -> rerun only lz4
#   {"TIC", "PIC", "gzip"}        -> rerun selected tools
#   {"TIC", "PIC", "gzip", "bzip2", "lz4"} -> rerun all tools
# FORCE_RECOMPRESS_TOOLS = {"lz4"}
# FORCE_RECOMPRESS_TOOLS = set()
# FORCE_RECOMPRESS_TOOLS = {"TIC", "PIC", "gzip", "bzip2", "lz4"}
FORCE_RECOMPRESS_TOOLS = set(TOOLS)

RESULTS_DIR = "."
LOG_DIR = "results/logs/compression"

CR_RESULTS_CSV = os.path.join(RESULTS_DIR, "cr_results.csv")
CR_TABLE_TEX = os.path.join(RESULTS_DIR, "cr_table.tex")

COMPRESSION_TIME_RESULTS_CSV = os.path.join(RESULTS_DIR, "compression_time_results.csv")
COMPRESSION_TIME_TABLE_TEX = os.path.join(RESULTS_DIR, "compression_time_table.tex")

CR_TABLE_CAPTION = "Compression Ratio (CR) for all schemes."
CR_TABLE_LABEL = "tab:cr"

COMPRESSION_TIME_TABLE_CAPTION = "Compression Time."
COMPRESSION_TIME_TABLE_LABEL = "tab:compression_time"


def _validate_inputs() -> None:
    """
    Pre-flight check. Validates Python packages, external executables, the
    compiled binaries, every input dataset and the output directories BEFORE
    any measurement starts, so a long run never dies halfway through because a
    tool was missing. Requirements live in dependencies.EXPERIMENT_REQUIREMENTS.
    """
    preflight(
        "compression",
        input_files=INPUT_FILES,
        output_dirs=[RESULTS_DIR, LOG_DIR],
    )


def _log_paths(file_name: str, tool: str) -> tuple[str, str]:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    stem = Path(file_name).stem
    stdout_path = os.path.join(LOG_DIR, f"{tool}_compress_{stem}_stdout.txt")
    stderr_path = os.path.join(LOG_DIR, f"{tool}_compress_{stem}_stderr.txt")
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


def _compress_one(tool: str, input_path: str) -> dict[str, Any]:

    compressed_path = get_compressed_path(input_path, tool)

    stdout_path, stderr_path = _log_paths(
        Path(input_path).name,
        tool,
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):

        # -----------------------------------------
        # Remove previous compressed output
        # -----------------------------------------
        if os.path.exists(compressed_path):
            os.remove(compressed_path)

        cmd = build_compress_command(
            tool,
            input_path,
            compressed_path,
            threads=THREADS,
        )

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        if not os.path.exists(compressed_path):
            raise RuntimeError(
                f"{tool} failed to produce compressed output for {input_path}. "
                f"Check logs: {stdout_path}, {stderr_path}"
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

    result["compressed_path"] = compressed_path
    result["stdout_path"] = stdout_path
    result["stderr_path"] = stderr_path
    result["skipped"] = False

    return result


def _build_cr_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    ordered_cols = ["File Name", "Original Size (MB)"] + TABLE_TOOLS
    return df[ordered_cols]


def _build_compression_time_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    ordered_cols = ["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]
    return df[ordered_cols]


def _format_cr_dataframe_for_output(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def _fmt_size(v: Any) -> str:
        if v == "" or pd.isna(v):
            return ""
        return format_number(float(v), DECIMALS)

    out["Original Size (MB)"] = out["Original Size (MB)"].apply(_fmt_size)

    for col in ["TIC", "PIC", "gzip", "bzip2", "lz4"]:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )
    return out


def _format_time_dataframe_for_output(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["TIC (s)"] = out["TIC (s)"].apply(
        lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
    )
    for col in ["PIC", "gzip", "bzip2", "lz4"]:
        out[col] = out[col].apply(
            lambda x: format_number(x, DECIMALS) if x != "" and not pd.isna(x) else ""
        )
    return out


def main() -> None:
    _validate_inputs()

    prev_cr_df = _load_previous_df(CR_RESULTS_CSV)
    prev_time_df = _load_previous_df(COMPRESSION_TIME_RESULTS_CSV)

    cr_rows: list[dict[str, Any]] = []
    time_rows: list[dict[str, Any]] = []

    rerun_all = FORCE_RECOMPRESS_TOOLS == set(TOOLS)

    for file_idx, input_path in enumerate(INPUT_FILES, start=1):
        file_name = Path(input_path).name
        original_size_mb = round(bytes_to_mb(Path(input_path).stat().st_size, decimals=DECIMALS))

        print(
            f"[INFO] File {file_idx}/{len(INPUT_FILES)}: {file_name} "
            f"({original_size_mb:.3f} MB)",
            flush=True,
        )

        tool_results: dict[str, dict[str, Any]] = {}
        cr_row: dict[str, Any] = {
            "File Name": file_name,
            "Original Size (MB)": round(original_size_mb, DECIMALS),
        }
        time_row: dict[str, Any] = {
            "File Name": file_name,
        }

        tic_time_value: float | None = None

        for tool_idx, tool in enumerate(TOOLS, start=1):
            should_rerun = rerun_all or (tool in FORCE_RECOMPRESS_TOOLS)

            if should_rerun:
                print(
                    f"  [INFO] Tool {tool_idx}/{len(TOOLS)}: {tool} -> compressing...",
                    flush=True,
                )

                tool_results[tool] = _compress_one(tool, input_path)

                comp_path = tool_results[tool]["compressed_path"]
                comp_size_mb = Path(comp_path).stat().st_size / (1024 ** 2)
                cr_val = compute_compression_ratio(input_path, comp_path, decimals=DECIMALS)
                cr_row[tool] = cr_val

                wall_time = float(tool_results[tool]["wall_time_s"])
                if tool == "TIC":
                    tic_time_value = wall_time
                    time_row["TIC (s)"] = round(wall_time, DECIMALS)

                print(
                    f"  [DONE] {tool}: "
                    f"time={tool_results[tool]['wall_time_s']:.3f}s, "
                    f"peak_mem={tool_results[tool]['peak_memory_mb']:.3f} MB, "
                    f"output={comp_path}, "
                    f"size={comp_size_mb:.3f} MB, "
                    f"CR={cr_val}",
                    flush=True,
                )
            else:
                prev_cr = _lookup_previous_value(prev_cr_df, file_name, tool)
                cr_row[tool] = prev_cr if prev_cr is not None else ""

                if tool == "TIC":
                    prev_tic_time = _lookup_previous_value(prev_time_df, file_name, "TIC (s)")
                    if prev_tic_time is None:
                        raise RuntimeError(
                            f"Cannot reuse TIC for {file_name}: missing prior TIC time in "
                            f"{COMPRESSION_TIME_RESULTS_CSV}. Either rerun TIC or restore prior CSV."
                        )
                    tic_time_value = float(prev_tic_time)
                    time_row["TIC (s)"] = tic_time_value

                print(
                    f"  [SKIP] {tool}: reused previous CSV values for {file_name}",
                    flush=True,
                )

        if tic_time_value is None or time_row.get("TIC (s)", "") == "":
            raise RuntimeError(f"TIC baseline missing for file {file_name}")

        # Fill relative timing columns
        for tool in ["PIC", "gzip", "bzip2", "lz4"]:
            if rerun_all or (tool in FORCE_RECOMPRESS_TOOLS):
                rel = safe_ratio(tool_results[tool]["wall_time_s"], tic_time_value, decimals=DECIMALS)
                time_row[tool] = rel
            else:
                prev_rel = _lookup_previous_value(prev_time_df, file_name, tool)
                time_row[tool] = prev_rel if prev_rel is not None else ""

        cr_rows.append(cr_row)
        time_rows.append(time_row)

    cr_df = _build_cr_dataframe(cr_rows)
    time_df = _build_compression_time_dataframe(time_rows)

    cr_df = _append_average_row(cr_df)
    time_df = _append_average_row(time_df)

    # Average row for original size should stay blank
    cr_df.loc[cr_df["File Name"] == "Average", "Original Size (MB)"] = ""

    cr_out_df = _format_cr_dataframe_for_output(cr_df)
    time_out_df = _format_time_dataframe_for_output(time_df)

    print("[INFO] Writing CSV and LaTeX outputs...", flush=True)

    write_dataframe_csv(cr_out_df, CR_RESULTS_CSV)
    write_dataframe_csv(time_out_df, COMPRESSION_TIME_RESULTS_CSV)

    build_grouped_latex_table(
        df=cr_out_df,
        tex_path=CR_TABLE_TEX,
        caption=CR_TABLE_CAPTION,
        label=CR_TABLE_LABEL,
        group_headers=[
            ("File Name", 1),
            ("Original Size (MB)", 1),
            ("CR", 5),
        ],
        column_headers=["File Name", "Original Size (MB)", "TIC", "PIC", "gzip", "bzip2", "lz4"],
        align_spec="ccccccc",
    )

    build_grouped_latex_table(
        df=time_out_df,
        tex_path=COMPRESSION_TIME_TABLE_TEX,
        caption=COMPRESSION_TIME_TABLE_CAPTION,
        label=COMPRESSION_TIME_TABLE_LABEL,
        group_headers=[
            ("File Name", 1),
            ("Absolute (s)", 1),
            ("Relative to TIC", 4),
        ],
        column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
        align_spec="cccccc",
    )

    print(f"Wrote: {CR_RESULTS_CSV}")
    print(f"Wrote: {CR_TABLE_TEX}")
    print(f"Wrote: {COMPRESSION_TIME_RESULTS_CSV}")
    print(f"Wrote: {COMPRESSION_TIME_TABLE_TEX}")


if __name__ == "__main__":
    main()
