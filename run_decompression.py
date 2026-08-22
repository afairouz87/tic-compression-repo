#!/usr/bin/env python3
"""
run_decompression.py

Generate:
- Table 6: Decompression Time

Outputs:
- decompression_time_results.csv
- decompression_time_table.tex

Features:
- TIC is the absolute baseline for decompression time.
- TIC absolute time uses 3 decimals.
- Relative values use 3 decimals.
- Supports selective rerun of specific tools only.
- Reuses previous CSV values for skipped tools when available.
- Adds an Average row.
- Prints progress to terminal.
- If required compressed files are missing, they are created in setup only.
  That setup compression time is NOT included in Table 6.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

from dependencies import preflight

from benchmark_utils import (
    BENCHMARK_INPUT_FILES,
    build_decompress_command,
    build_grouped_latex_table,
    ensure_compressed_files,
    format_number,
    get_compressed_path,
    get_decompressed_output_path,
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

TOOLS = ["PIC", "TIC", "gzip", "bzip2", "lz4"]
TABLE_TOOLS = ["TIC", "PIC", "gzip", "bzip2", "lz4"]
THREADS = 1
DECIMALS = 3

NUM_RUNS = 10
WARMUP_RUNS = 1

# Re-run only selected tools.
# Examples:
#   set() -> rerun nothing, reuse previous CSV values where possible
#   {"lz4"} -> rerun only lz4
#   {"TIC", "PIC", "gzip", "bzip2", "lz4"} -> rerun all
# FORCE_RERUN_TOOLS = set()
# FORCE_RERUN_TOOLS = {"TIC", "PIC", "gzip", "bzip2", "lz4"}
FORCE_RERUN_TOOLS = set(TOOLS)

RESULTS_DIR = "."
LOG_DIR = "results/logs/decompression"
TMP_DIR = "results/tmp/decompression"

DECOMPRESSION_TIME_RESULTS_CSV = os.path.join(RESULTS_DIR, "decompression_time_results.csv")
DECOMPRESSION_TIME_TABLE_TEX = os.path.join(RESULTS_DIR, "decompression_time_table.tex")

DECOMPRESSION_TIME_TABLE_CAPTION = "Decompression Time."
DECOMPRESSION_TIME_TABLE_LABEL = "tab:decompression_time"


def _validate_inputs() -> None:
    """
    Pre-flight check. Validates Python packages, external executables, the
    compiled binaries, every input dataset and the output directories BEFORE
    any measurement starts, so a long run never dies halfway through because a
    tool was missing. Requirements live in dependencies.EXPERIMENT_REQUIREMENTS.
    """
    preflight(
        "decompression",
        input_files=INPUT_FILES,
        output_dirs=[RESULTS_DIR, LOG_DIR],
    )


def _log_paths(file_name: str, tool: str) -> tuple[str, str]:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    stem = Path(file_name).stem
    stdout_path = os.path.join(LOG_DIR, f"{tool}_decompress_{stem}_stdout.txt")
    stderr_path = os.path.join(LOG_DIR, f"{tool}_decompress_{stem}_stderr.txt")
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


def _decompress_one(tool: str, input_path: str) -> dict[str, Any]:

    Path(TMP_DIR).mkdir(parents=True, exist_ok=True)

    compressed_path = get_compressed_path(input_path, tool)

    decompressed_path = os.path.join(
        TMP_DIR,
        f"{Path(input_path).stem}_{tool}_decompressed.tmp"
    )

    stdout_path, stderr_path = _log_paths(
        Path(input_path).name,
        tool,
    )

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):

        # -----------------------------------------
        # Remove previous output file
        # -----------------------------------------
        if os.path.exists(decompressed_path):
            os.remove(decompressed_path)

        # -----------------------------------------
        # PIC / TIC
        # These tools internally write to output file
        # -----------------------------------------
        if tool in {"PIC", "TIC"}:

            cmd = build_decompress_command(
                tool,
                compressed_path,
                decompressed_path,
                threads=THREADS,
            )

        # -----------------------------------------
        # gzip
        # -----------------------------------------
        elif tool == "gzip":

            cmd = [
                "sh",
                "-c",
                f"gzip -dc '{compressed_path}' > '{decompressed_path}'"
            ]

        # -----------------------------------------
        # bzip2
        # -----------------------------------------
        elif tool == "bzip2":

            cmd = [
                "sh",
                "-c",
                f"bzip2 -dc '{compressed_path}' > '{decompressed_path}'"
            ]

        # -----------------------------------------
        # lz4
        # -----------------------------------------
        elif tool == "lz4":

            cmd = [
                "sh",
                "-c",
                f"lz4 -dc '{compressed_path}' > '{decompressed_path}'"
            ]

        else:
            raise ValueError(f"Unsupported tool: {tool}")

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        # -----------------------------------------
        # Validate output file
        # -----------------------------------------
        if (
            not os.path.exists(decompressed_path)
            or os.path.getsize(decompressed_path) == 0
        ):
            raise RuntimeError(
                f"{tool} failed to produce decompressed output "
                f"for {input_path}. "
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

    result["decompressed_path"] = decompressed_path
    result["stdout_path"] = stdout_path
    result["stderr_path"] = stderr_path
    result["skipped"] = False

    return result


def _build_decompression_time_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    ordered_cols = ["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]
    return df[ordered_cols]


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

    prev_time_df = _load_previous_df(DECOMPRESSION_TIME_RESULTS_CSV)

    # Ensure all compressed files exist first.
    print("[INFO] Ensuring compressed files exist...", flush=True)
    for input_path in INPUT_FILES:
        ensure_compressed_files(TOOLS, input_path, threads=THREADS, force=False)

    time_rows: list[dict[str, Any]] = []
    rerun_all = FORCE_RERUN_TOOLS == set(TOOLS)

    for file_idx, input_path in enumerate(INPUT_FILES, start=1):
        file_name = Path(input_path).name
        print(f"[INFO] File {file_idx}/{len(INPUT_FILES)}: {file_name}", flush=True)

        tool_results: dict[str, dict[str, Any]] = {}
        time_row: dict[str, Any] = {"File Name": file_name}

        tic_time_value: float | None = None

        for tool_idx, tool in enumerate(TOOLS, start=1):
            should_rerun = rerun_all or (tool in FORCE_RERUN_TOOLS)

            if should_rerun:
                print(
                    f"  [INFO] Tool {tool_idx}/{len(TOOLS)}: {tool} -> decompressing...",
                    flush=True,
                )

                tool_results[tool] = _decompress_one(tool, input_path)

                wall_time = float(tool_results[tool]["wall_time_s"])
                out_path = tool_results[tool]["decompressed_path"]
                out_size_mb = Path(out_path).stat().st_size / (1024 ** 2)

                if tool == "TIC":
                    tic_time_value = wall_time
                    time_row["TIC (s)"] = round(wall_time, DECIMALS)

                print(
                    f"  [DONE] {tool}: "
                    f"time={wall_time:.3f}s, "
                    f"peak_mem={tool_results[tool]['peak_memory_mb']:.3f} MB, "
                    f"output={out_path}, "
                    f"size={out_size_mb:.3f} MB",
                    flush=True,
                )
            else:
                if tool == "TIC":
                    prev_tic_time = _lookup_previous_value(prev_time_df, file_name, "TIC (s)")
                    if prev_tic_time is None:
                        raise RuntimeError(
                            f"Cannot reuse TIC for {file_name}: missing prior TIC time in "
                            f"{DECOMPRESSION_TIME_RESULTS_CSV}. Either rerun TIC or restore prior CSV."
                        )
                    tic_time_value = float(prev_tic_time)
                    time_row["TIC (s)"] = tic_time_value

                print(
                    f"  [SKIP] {tool}: reused previous CSV values for {file_name}",
                    flush=True,
                )

        if tic_time_value is None or time_row.get("TIC (s)", "") == "":
            raise RuntimeError(f"TIC baseline missing for file {file_name}")

        for tool in ["PIC", "gzip", "bzip2", "lz4"]:
            if rerun_all or (tool in FORCE_RERUN_TOOLS):
                rel = safe_ratio(tool_results[tool]["wall_time_s"], tic_time_value, decimals=DECIMALS)
                time_row[tool] = rel
            else:
                prev_rel = _lookup_previous_value(prev_time_df, file_name, tool)
                time_row[tool] = prev_rel if prev_rel is not None else ""

        time_rows.append(time_row)

    time_df = _build_decompression_time_dataframe(time_rows)
    time_df = _append_average_row(time_df)
    time_out_df = _format_time_dataframe_for_output(time_df)

    print("[INFO] Writing CSV and LaTeX outputs...", flush=True)

    write_dataframe_csv(time_out_df, DECOMPRESSION_TIME_RESULTS_CSV)

    build_grouped_latex_table(
        df=time_out_df,
        tex_path=DECOMPRESSION_TIME_TABLE_TEX,
        caption=DECOMPRESSION_TIME_TABLE_CAPTION,
        label=DECOMPRESSION_TIME_TABLE_LABEL,
        group_headers=[
            ("File Name", 1),
            ("Absolute (s)", 1),
            ("Relative to TIC", 4),
        ],
        column_headers=["File Name", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"],
        align_spec="cccccc",
    )

    print(f"Wrote: {DECOMPRESSION_TIME_RESULTS_CSV}")
    print(f"Wrote: {DECOMPRESSION_TIME_TABLE_TEX}")


if __name__ == "__main__":
    main()
