#!/usr/bin/env python3
# run_parallel_benchmarks.py

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from dataset_config import PARALLEL_DATASET_INFO, sha256_of
from dataset_config import (
    RESULTS_FIGURES_DIR,
    RESULTS_RAW_DIR,
    RESULTS_TABLES_DIR,
)
from dependencies import preflight

from benchmark_utils import (
    DEFAULT_PARALLEL_THREADS,
    PARALLEL_INPUT_FILE,
    LBZIP2_BINARY,
    build_compress_command,
    build_decompress_command,
    build_search_command,
    build_replace_command,
    ensure_compressed_file,
    get_compressed_path,
    measure_command,
    write_dataframe_csv,
)

# =====================
# User Config
# =====================

# Parallel-experiment input. This is the DEFAULT only; `--input PATH` overrides
# it at run time. Resolved through the canonical dataset directory, which is
# defined once in dataset_config.py.
#
# The historical file behind the published parallel results has unknown
# provenance and is not reconstructible. If it is unavailable, supply a
# replacement explicitly with --input. The runner never substitutes a dataset on
# its own. See docs/datasets.md section 7.
INPUT_FILE = PARALLEL_INPUT_FILE

# Thread counts for the parallel experiments: 1, 2, 4, 6, and 8 threads.
# Defined once in benchmark_utils.DEFAULT_PARALLEL_THREADS so that the
# thread-count configuration has a single authoritative source.
THREAD_COUNTS = list(DEFAULT_PARALLEL_THREADS)

NUM_RUNS = 10
WARMUP_RUNS = 1

DELAY_BETWEEN_RUNS_S = 0.5

SEARCH_QUERY = "the"
REPLACE_STRING = "THE"

# Generated output goes under results/, never the repository root.
# The layout is defined once in dataset_config.py.
RESULTS_DIR = RESULTS_RAW_DIR          # *_results.csv
TABLES_DIR = RESULTS_TABLES_DIR        # *_table.tex
FIGURES_DIR = RESULTS_FIGURES_DIR      # *.png
LOG_DIR = "results/logs/parallel"
TMP_DIR = "results/tmp/parallel"

PARALLEL_TIME_CSV = os.path.join(
    RESULTS_DIR,
    "parallel_time_results.csv"
)

PARALLEL_MEMORY_CSV = os.path.join(
    RESULTS_DIR,
    "parallel_memory_results.csv"
)

PARALLEL_SEARCH_CSV = os.path.join(
    RESULTS_DIR,
    "parallel_search_results.csv"
)

PARALLEL_REPLACE_CSV = os.path.join(
    RESULTS_DIR,
    "parallel_replace_results.csv"
)

PARALLEL_TIME_PNG = os.path.join(FIGURES_DIR, "parallel_time.png")

PARALLEL_MEMORY_PNG = os.path.join(FIGURES_DIR, "parallel_memory.png")

PARALLEL_SEARCH_PNG = os.path.join(FIGURES_DIR, "parallel_search.png")

PARALLEL_REPLACE_PNG = os.path.join(FIGURES_DIR, "parallel_replace.png")

# =====================
# Helpers
# =====================

def _write_partial_outputs(
    time_rows: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
    search_rows: list[dict[str, Any]],
    replace_rows: list[dict[str, Any]],
) -> None:

    time_df = pd.DataFrame(time_rows)
    memory_df = pd.DataFrame(memory_rows)
    search_df = pd.DataFrame(search_rows)
    replace_df = pd.DataFrame(replace_rows)

    write_dataframe_csv(time_df, PARALLEL_TIME_CSV)
    write_dataframe_csv(memory_df, PARALLEL_MEMORY_CSV)
    write_dataframe_csv(search_df, PARALLEL_SEARCH_CSV)
    write_dataframe_csv(replace_df, PARALLEL_REPLACE_CSV)

    print(
        "[INFO] Partial CSV outputs written.",
        flush=True,
    )

def _describe_input(with_sha256: bool = False) -> None:
    """Report exactly what is being benchmarked, before any measurement runs."""
    size = os.path.getsize(INPUT_FILE)
    print(f"[INPUT] path       : {INPUT_FILE}", flush=True)
    print(f"[INPUT] size       : {size} bytes ({size / (1024 ** 2):.3f} MB)", flush=True)

    if with_sha256:
        print("[INPUT] sha256     : (computing...)", flush=True)
        print(f"[INPUT] sha256     : {sha256_of(INPUT_FILE)}", flush=True)

    if os.path.basename(INPUT_FILE) == PARALLEL_DATASET_INFO["logical_name"]:
        print(
            "[INPUT] provenance : historical input; provenance unknown "
            "(see docs/datasets.md section 7)",
            flush=True,
        )
    else:
        print(
            "[INPUT] provenance : reviewer-supplied substitute; results are NOT "
            "comparable to the published parallel tables",
            flush=True,
        )


def _validate_input_file() -> None:
    """Validate only the benchmark input. Never substitutes another dataset."""

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}\n"
            f"  The parallel experiments need one input file.\n"
            f"  The historical input ({PARALLEL_DATASET_INFO['logical_name']}) has unknown\n"
            f"  provenance and cannot be rebuilt from this repository.\n"
            f"  Supply an input explicitly, for example:\n"
            f"    python3 run_parallel_benchmarks.py --input datasets/f10.txt\n"
            f"  No dataset is substituted automatically. See docs/datasets.md section 7."
        )

    if not os.path.isfile(INPUT_FILE):
        raise FileNotFoundError(f"Input path is not a regular file: {INPUT_FILE}")

    if os.path.getsize(INPUT_FILE) == 0:
        raise ValueError(f"Input file is empty: {INPUT_FILE}")


def _validate_inputs() -> None:
    """
    Full pre-run validation: input file, Python packages, external executables,
    compiled binaries and working directories -- all before any measurement.
    lbzip2 is required by these experiments ONLY; see dependencies.py.
    """

    _validate_input_file()

    preflight(
        "parallel",
        input_files=[INPUT_FILE],
        output_dirs=[RESULTS_DIR, TABLES_DIR, FIGURES_DIR, LOG_DIR, TMP_DIR],
    )


def _log_paths(
    tool: str,
    operation: str,
    threads: int,
    run_idx: int
) -> tuple[str, str]:

    stem = Path(INPUT_FILE).stem

    stdout_path = os.path.join(
        LOG_DIR,
        f"{tool}_{operation}_{stem}_t{threads}_r{run_idx}_stdout.txt",
    )

    stderr_path = os.path.join(
        LOG_DIR,
        f"{tool}_{operation}_{stem}_t{threads}_r{run_idx}_stderr.txt",
    )

    return stdout_path, stderr_path


def _tmp_path(
    tool: str,
    operation: str,
    threads: int,
    run_idx: int,
    suffix: str
) -> str:

    stem = Path(INPUT_FILE).stem

    return os.path.join(
        TMP_DIR,
        f"{stem}_{tool}_{operation}_t{threads}_r{run_idx}.{suffix}",
    )


def _ensure_rc_ok(
    result: dict[str, Any],
    allowed: tuple[int, ...],
    msg: str
) -> None:

    rc = int(result.get("return_code", -1))

    if rc not in allowed:
        raise RuntimeError(
            f"{msg}. return_code={rc}"
        )

# =====================
# Measurements
# =====================

def _measure_once(
    tool: str,
    operation: str,
    threads: int,
    run_idx: int
) -> dict[str, Any]:

    stdout_path, stderr_path = _log_paths(
        tool,
        operation,
        threads,
        run_idx,
    )

    # =====================================================
    # Compression
    # =====================================================

    if operation == "compression":

        compressed_path = get_compressed_path(
            INPUT_FILE,
            tool,
        )

        if os.path.exists(compressed_path):
            os.remove(compressed_path)

        if tool == "TIC":
            cmd = build_compress_command(
                tool,
                INPUT_FILE,
                compressed_path,
                threads=threads,
            )

        elif tool == "lbzip2":
            cmd = [
                "sh",
                "-c",
                f"{LBZIP2_BINARY} "
                f"-k -f -n {threads} "
                f"-c '{INPUT_FILE}' "
                f"> '{compressed_path}'",
            ]

        else:
            raise ValueError(
                f"Unsupported compression tool: {tool}"
            )

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        if (
            not os.path.exists(compressed_path)
            or os.path.getsize(compressed_path) == 0
        ):
            raise RuntimeError(
                f"{tool} compression failed "
                f"at threads={threads}"
            )

        return result

    # =====================================================
    # Decompression
    # =====================================================

    if operation == "decompression":

        compressed_path = ensure_compressed_file(
            tool,
            INPUT_FILE,
            threads=threads,
            force=False,
        )

        output_path = _tmp_path(
            tool,
            operation,
            threads,
            run_idx,
            "decompressed.txt",
        )

        if os.path.exists(output_path):
            os.remove(output_path)

        if tool == "TIC":

            cmd = build_decompress_command(
                tool,
                compressed_path,
                output_path,
                threads=threads,
            )

        elif tool == "lbzip2":

            cmd = [
                "sh",
                "-c",
                f"{LBZIP2_BINARY} -dc -n {threads} "
                f"'{compressed_path}' > '{output_path}'",
            ]

        else:
            raise ValueError(
                f"Unsupported decompression tool: {tool}"
            )

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        if (
            not os.path.exists(output_path)
            or os.path.getsize(output_path) == 0
        ):
            raise RuntimeError(
                f"{tool} decompression failed "
                f"at threads={threads}"
            )

        return result

    # =====================================================
    # Search
    # =====================================================

    if operation == "search":

        compressed_path = ensure_compressed_file(
            "TIC",
            INPUT_FILE,
            threads=threads,
            force=False,
        )

        dummy_out = _tmp_path(
            "TIC",
            operation,
            threads,
            run_idx,
            "out",
        )

        cmd = build_search_command(
            tool="TIC",
            compressed_path=compressed_path,
            query=SEARCH_QUERY,
            dummy_output_path=dummy_out,
            threads=threads,
        )

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            result,
            (0,),
            f"TIC search failed at threads={threads}",
        )

        return result

    # =====================================================
    # Replace
    # =====================================================

    if operation == "replace":

        compressed_path = ensure_compressed_file(
            "TIC",
            INPUT_FILE,
            threads=threads,
            force=False,
        )

        output_path = _tmp_path(
            "TIC",
            operation,
            threads,
            run_idx,
            "compressed.out",
        )

        cmd = build_replace_command(
            tool="TIC",
            compressed_path=compressed_path,
            search_string=SEARCH_QUERY,
            replace_string=REPLACE_STRING,
            output_path=output_path,
            threads=threads,
        )

        result = measure_command(
            cmd,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        _ensure_rc_ok(
            result,
            (0,),
            f"TIC replace failed at threads={threads}",
        )

        return result

    raise ValueError(
        f"Unsupported operation: {operation}"
    )


def _repeat_operation(
    tool: str,
    operation: str,
    threads: int
) -> dict[str, Any]:

    times = []
    peak_memories = []

    for run_idx in range(NUM_RUNS):

        print(
            f"      run={run_idx+1}/{NUM_RUNS} "
            f"tool={tool} "
            f"operation={operation} "
            f"threads={threads}",
            flush=True,
        )

        result = _measure_once(
            tool,
            operation,
            threads,
            run_idx,
        )

        if run_idx < WARMUP_RUNS:
            time.sleep(DELAY_BETWEEN_RUNS_S)
            continue

        times.append(
            float(result["wall_time_s"])
        )

        peak_memories.append(
            float(result["peak_memory_mb"])
        )

        time.sleep(DELAY_BETWEEN_RUNS_S)

    avg_time = sum(times) / len(times)

    avg_peak_memory = (
        sum(peak_memories) / len(peak_memories)
    )

    print(
        f"    {tool} {operation}: "
        f"avg_time={avg_time:.6f}s "
        f"avg_peak_memory={avg_peak_memory:.3f} MB "
        f"over {len(times)} runs "
        f"(warmup={WARMUP_RUNS})",
        flush=True,
    )

    return {
        "avg_wall_time_s": round(avg_time, 6),
        "avg_peak_memory_mb": round(avg_peak_memory, 6),
    }

# =====================
# Plotting
# =====================

def _plot_dataframe(
    df: pd.DataFrame,
    figure_path: str,
    title: str,
    ylabel: str,
) -> None:

    import matplotlib.pyplot as plt

    markers = [
        "o",
        "s",
        "^",
        "D",
        "x",
        "*",
    ]

    linestyles = [
        "-",
        "--",
        "-.",
        ":",
        (0, (5, 2)),
        (0, (3, 1, 1, 1)),
    ]

    plt.figure(figsize=(8, 5))

    curve_idx = 0

    for col in df.columns:

        if col == "Threads":
            continue

        plt.plot(
            df["Threads"],
            df[col],
            label=col.replace(" ", "-"),
            marker=markers[
                curve_idx % len(markers)
            ],
            linestyle=linestyles[
                curve_idx % len(linestyles)
            ],
            linewidth=1.8,
            markersize=6,
        )

        curve_idx += 1

    plt.xlabel("Number of Threads")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(df["Threads"])

    plt.grid(
        True,
        linestyle="--",
        alpha=0.4,
    )

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        figure_path,
        dpi=300,
    )

    plt.close()


def _plot_time(
    csv_path: str,
    figure_path: str
) -> None:

    df = pd.read_csv(csv_path)

    _plot_dataframe(
        df,
        figure_path,
        "Parallel Compression and Decompression",
        "Time (s)",
    )


def _plot_memory(
    csv_path: str,
    figure_path: str
) -> None:

    df = pd.read_csv(csv_path)

    _plot_dataframe(
        df,
        figure_path,
        "Parallel Memory Utilization",
        "Peak Memory (MB)",
    )


def _plot_search(
    csv_path: str,
    figure_path: str
) -> None:

    df = pd.read_csv(csv_path)

    _plot_dataframe(
        df,
        figure_path,
        "Parallel Search",
        "Time (s)",
    )


def _plot_replace(
    csv_path: str,
    figure_path: str
) -> None:

    df = pd.read_csv(csv_path)

    _plot_dataframe(
        df,
        figure_path,
        "Parallel Search and Replace",
        "Time (s)",
    )

# =====================
# Main
# =====================

def main() -> None:

    _validate_inputs()

    time_rows = []
    memory_rows = []
    search_rows = []
    replace_rows = []

    for threads in THREAD_COUNTS:

        print(
            f"[INFO] Running benchmarks "
            f"at {threads} thread(s)...",
            flush=True,
        )

        # ============================================
        # Generate compressed files once
        # ============================================

        ensure_compressed_file(
            "TIC",
            INPUT_FILE,
            threads=threads,
            force=True,
        )

        ensure_compressed_file(
            "lbzip2",
            INPUT_FILE,
            threads=threads,
            force=True,
        )

        tic_comp = _repeat_operation(
            "TIC",
            "compression",
            threads,
        )

        tic_decomp = _repeat_operation(
            "TIC",
            "decompression",
            threads,
        )

        lbzip2_comp = _repeat_operation(
            "lbzip2",
            "compression",
            threads,
        )

        lbzip2_decomp = _repeat_operation(
            "lbzip2",
            "decompression",
            threads,
        )

        tic_search = _repeat_operation(
            "TIC",
            "search",
            threads,
        )

        tic_replace = _repeat_operation(
            "TIC",
            "replace",
            threads,
        )

        time_rows.append({
            "Threads": threads,
            "TIC Compression":
                tic_comp["avg_wall_time_s"],
            "TIC Decompression":
                tic_decomp["avg_wall_time_s"],
            "lbzip2 Compression":
                lbzip2_comp["avg_wall_time_s"],
            "lbzip2 Decompression":
                lbzip2_decomp["avg_wall_time_s"],
        })

        memory_rows.append({
            "Threads": threads,
            "TIC Compression":
                tic_comp["avg_peak_memory_mb"],
            "TIC Decompression":
                tic_decomp["avg_peak_memory_mb"],
            "lbzip2 Compression":
                lbzip2_comp["avg_peak_memory_mb"],
            "lbzip2 Decompression":
                lbzip2_decomp["avg_peak_memory_mb"],
        })

        search_rows.append({
            "Threads": threads,
            "TIC Search":
                tic_search["avg_wall_time_s"],
        })

        replace_rows.append({
            "Threads": threads,
            "TIC Lookup-and-Replace":
                tic_replace["avg_wall_time_s"],
        })

        _write_partial_outputs(
            time_rows,
            memory_rows,
            search_rows,
            replace_rows,
        )

    time_df = pd.DataFrame(time_rows)
    memory_df = pd.DataFrame(memory_rows)
    search_df = pd.DataFrame(search_rows)
    replace_df = pd.DataFrame(replace_rows)

    write_dataframe_csv(
        time_df,
        PARALLEL_TIME_CSV
    )

    write_dataframe_csv(
        memory_df,
        PARALLEL_MEMORY_CSV
    )

    write_dataframe_csv(
        search_df,
        PARALLEL_SEARCH_CSV
    )

    write_dataframe_csv(
        replace_df,
        PARALLEL_REPLACE_CSV
    )

    _plot_time(
        PARALLEL_TIME_CSV,
        PARALLEL_TIME_PNG,
    )

    _plot_memory(
        PARALLEL_MEMORY_CSV,
        PARALLEL_MEMORY_PNG,
    )

    _plot_search(
        PARALLEL_SEARCH_CSV,
        PARALLEL_SEARCH_PNG,
    )

    _plot_replace(
        PARALLEL_REPLACE_CSV,
        PARALLEL_REPLACE_PNG,
    )

    print(f"Wrote: {PARALLEL_TIME_CSV}")
    print(f"Wrote: {PARALLEL_MEMORY_CSV}")
    print(f"Wrote: {PARALLEL_SEARCH_CSV}")
    print(f"Wrote: {PARALLEL_REPLACE_CSV}")

    print(f"Wrote: {PARALLEL_TIME_PNG}")
    print(f"Wrote: {PARALLEL_MEMORY_PNG}")
    print(f"Wrote: {PARALLEL_SEARCH_PNG}")
    print(f"Wrote: {PARALLEL_REPLACE_PNG}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Run the parallel TIC/lbzip2 benchmarks over a single input file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The historical input file-parallel.txt has unknown provenance and is\n"
            "not reconstructible from this repository. Supply an input explicitly:\n"
            "  python3 run_parallel_benchmarks.py --input datasets/f10.txt\n"
            "A substitute produces results that are NOT comparable to the published\n"
            "parallel tables. See docs/datasets.md section 7."
        ),
    )
    parser.add_argument(
        "--input",
        default=INPUT_FILE,
        metavar="PATH",
        help=f"Input file for the parallel experiments (default: {INPUT_FILE}).",
    )
    parser.add_argument(
        "--sha256",
        action="store_true",
        help="Report the SHA-256 of the input before benchmarking.",
    )
    parser.add_argument(
        "--describe-only",
        action="store_true",
        help="Validate and describe the input, then exit without benchmarking.",
    )
    return parser.parse_args(argv)


def cli(argv=None) -> int:
    global INPUT_FILE

    args = parse_args(argv)
    INPUT_FILE = args.input

    try:
        _validate_input_file()
    except (FileNotFoundError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr, flush=True)
        return 1

    _describe_input(with_sha256=args.sha256)

    if args.describe_only:
        print("[INFO] --describe-only: no benchmark was run.", flush=True)
        return 0

    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())







##########################################

# #!/usr/bin/env python3
# # run_parallel_benchmarks.py script
# from __future__ import annotations

# import os
# import shutil
# from pathlib import Path
# from typing import Any
# import time

# import pandas as pd

# from benchmark_utils import (
#     LBZIP2_BINARY,
#     build_compress_command,
#     build_decompress_command,
#     build_search_command,
#     build_replace_command,
#     ensure_compressed_file,
#     get_compressed_path,
#     measure_command,
#     write_dataframe_csv,
# )

# # =====================
# # User Config
# # =====================

# INPUT_FILE = "../textFiles/file-parallel.txt"

# THREAD_COUNTS = [1, 2, 4, 6, 8]

# NUM_RUNS = 10
# WARMUP_RUNS = 1
# DELAY_BETWEEN_RUNS_S = 0.5

# SEARCH_QUERY = "the"
# REPLACE_STRING = "THE"

# RESULTS_DIR = "."
# LOG_DIR = "results/logs/parallel"
# TMP_DIR = "results/tmp/parallel"

# PARALLEL_TIME_CSV = os.path.join(RESULTS_DIR, "parallel_time_results.csv")
# PARALLEL_MEMORY_CSV = os.path.join(RESULTS_DIR, "parallel_memory_results.csv")
# PARALLEL_SEARCH_CSV = os.path.join(RESULTS_DIR, "parallel_search_results.csv")
# PARALLEL_REPLACE_CSV = os.path.join(RESULTS_DIR, "parallel_replace_results.csv")

# PARALLEL_TIME_PNG = os.path.join(FIGURES_DIR, "parallel_time.png")
# PARALLEL_MEMORY_PNG = os.path.join(FIGURES_DIR, "parallel_memory.png")
# PARALLEL_SEARCH_PNG = os.path.join(FIGURES_DIR, "parallel_search.png")
# PARALLEL_REPLACE_PNG = os.path.join(FIGURES_DIR, "parallel_replace.png")


# # =====================
# # Helpers
# # =====================

# def _validate_inputs() -> None:
#     if not os.path.exists(INPUT_FILE):
#         raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

#     if shutil.which(LBZIP2_BINARY) is None:
#         raise FileNotFoundError(
#             f"{LBZIP2_BINARY} not found in PATH. Install lbzip2 first."
#         )

#     Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
#     Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


# def _log_paths(tool: str, operation: str, threads: int, run_idx: int) -> tuple[str, str]:
#     stem = Path(INPUT_FILE).stem
#     stdout_path = os.path.join(
#         LOG_DIR,
#         f"{tool}_{operation}_{stem}_t{threads}_r{run_idx}_stdout.txt",
#     )
#     stderr_path = os.path.join(
#         LOG_DIR,
#         f"{tool}_{operation}_{stem}_t{threads}_r{run_idx}_stderr.txt",
#     )
#     return stdout_path, stderr_path


# def _tmp_path(tool: str, operation: str, threads: int, run_idx: int, suffix: str) -> str:
#     stem = Path(INPUT_FILE).stem
#     return os.path.join(
#         TMP_DIR,
#         f"{stem}_{tool}_{operation}_t{threads}_r{run_idx}.{suffix}",
#     )


# def _ensure_rc_ok(result: dict[str, Any], allowed: tuple[int, ...], msg: str) -> None:
#     rc = int(result.get("return_code", -1))
#     if rc not in allowed:
#         raise RuntimeError(f"{msg}. return_code={rc}")


# # =====================
# # Measurements
# # =====================

# def _measure_once(tool: str, operation: str, threads: int, run_idx: int) -> dict[str, Any]:
#     stdout_path, stderr_path = _log_paths(tool, operation, threads, run_idx)

#     if operation == "compression":
#         compressed_path = get_compressed_path(INPUT_FILE, tool)

#         if os.path.exists(compressed_path):
#             os.remove(compressed_path)

#         if tool == "TIC":
#             cmd = build_compress_command(tool, INPUT_FILE, compressed_path, threads=threads)

#         elif tool == "lbzip2":
#             compressed_path = get_compressed_path(INPUT_FILE, "lbzip2")
#             if os.path.exists(compressed_path):
#                 os.remove(compressed_path)
#             cmd = [
#                 "sh",
#                 "-c",
#                 f"{LBZIP2_BINARY} -k -f -n {threads} -c '{INPUT_FILE}' > '{compressed_path}'",
#             ]

#         else:
#             raise ValueError(f"Unsupported compression tool: {tool}")

#         result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)

#         if not os.path.exists(compressed_path) or os.path.getsize(compressed_path) == 0:
#             raise RuntimeError(f"{tool} compression failed at threads={threads}")

#         return result

#     if operation == "decompression":
#         compressed_path = ensure_compressed_file(tool, INPUT_FILE, threads=threads, force=False)
#         output_path = _tmp_path(tool, operation, threads, run_idx, "decompressed.txt")

#         if os.path.exists(output_path):
#             os.remove(output_path)

#         if tool == "TIC":
#             cmd = build_decompress_command(tool, compressed_path, output_path, threads=threads)

#         elif tool == "lbzip2":
#             cmd = [
#                 "sh",
#                 "-c",
#                 f"{LBZIP2_BINARY} -dc -n {threads} '{compressed_path}' > '{output_path}'",
#             ]

#         else:
#             raise ValueError(f"Unsupported decompression tool: {tool}")

#         result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)

#         if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
#             raise RuntimeError(f"{tool} decompression failed at threads={threads}")

#         return result

#     if operation == "search":
#         compressed_path = ensure_compressed_file("TIC", INPUT_FILE, threads=threads, force=False)
#         dummy_out = _tmp_path("TIC", operation, threads, run_idx, "out")

#         if os.path.exists(dummy_out):
#             os.remove(dummy_out)

#         cmd = build_search_command(
#             tool="TIC",
#             compressed_path=compressed_path,
#             query=SEARCH_QUERY,
#             dummy_output_path=dummy_out,
#             threads=threads,
#         )

#         result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)
#         _ensure_rc_ok(result, (0,), f"TIC search failed at threads={threads}")
#         return result

#     if operation == "replace":
#         compressed_path = ensure_compressed_file("TIC", INPUT_FILE, threads=threads, force=False)
#         output_path = _tmp_path("TIC", operation, threads, run_idx, "compressed.out")

#         if os.path.exists(output_path):
#             os.remove(output_path)

#         cmd = build_replace_command(
#             tool="TIC",
#             compressed_path=compressed_path,
#             search_string=SEARCH_QUERY,
#             replace_string=REPLACE_STRING,
#             output_path=output_path,
#             threads=threads,
#         )

#         result = measure_command(cmd, stdout_path=stdout_path, stderr_path=stderr_path)
#         _ensure_rc_ok(result, (0,), f"TIC lookup-and-replace failed at threads={threads}")

#         if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
#             raise RuntimeError(f"TIC lookup-and-replace output missing at threads={threads}")

#         return result

#     raise ValueError(f"Unsupported operation: {operation}")


# def _repeat_operation(tool: str, operation: str, threads: int) -> dict[str, Any]:
#     times = []
#     peak_memories = []

#     for run_idx in range(NUM_RUNS):
#         result = _measure_once(tool, operation, threads, run_idx)

#         if run_idx < WARMUP_RUNS:
#             time.sleep(DELAY_BETWEEN_RUNS_S)
#             continue

#         times.append(float(result["wall_time_s"]))
#         peak_memories.append(float(result["peak_memory_mb"]))
#         time.sleep(DELAY_BETWEEN_RUNS_S)

#     avg_time = sum(times) / len(times)
#     avg_peak_memory = sum(peak_memories) / len(peak_memories)

#     print(
#         f"    {tool} {operation}: avg_time={avg_time:.6f}s "
#         f"over {len(times)} runs (warmup={WARMUP_RUNS})",
#         flush=True,
#     )

#     return {
#         "avg_wall_time_s": round(avg_time, 6),
#         "avg_peak_memory_mb": round(avg_peak_memory, 6),
#     }


# # =====================
# # Plotting
# # =====================

# def _plot_dataframe(
#     df: pd.DataFrame,
#     figure_path: str,
#     title: str,
#     ylabel: str,
# ) -> None:
#     import matplotlib.pyplot as plt

#     markers = ["o", "s", "^", "D", "x", "*", "v"]
#     linestyles = ["-", "--", "-.", ":", (0, (5, 2)), (0, (3, 1, 1, 1))]

#     plt.figure(figsize=(8, 5))

#     curve_idx = 0

#     for col in df.columns:
#         if col == "Threads":
#             continue

#         plt.plot(
#             df["Threads"],
#             df[col],
#             label=col.replace(" ", "-"),
#             marker=markers[curve_idx % len(markers)],
#             linestyle=linestyles[curve_idx % len(linestyles)],
#             linewidth=1.8,
#             markersize=6,
#         )

#         curve_idx += 1

#     plt.xlabel("Number of Threads")
#     plt.ylabel(ylabel)
#     plt.title(title)
#     plt.xticks(df["Threads"])
#     plt.grid(True, linestyle="--", alpha=0.4)
#     plt.legend()
#     plt.tight_layout()
#     plt.savefig(figure_path, dpi=300)
#     plt.close()

# def _plot_time(csv_path: str, figure_path: str) -> None:
#     df = pd.read_csv(csv_path)
#     _plot_dataframe(
#         df,
#         figure_path,
#         "Parallel Compression and Decompression",
#         "Time (s)",
#     )


# def _plot_memory(csv_path: str, figure_path: str) -> None:
#     df = pd.read_csv(csv_path)
#     _plot_dataframe(
#         df,
#         figure_path,
#         "Parallel Memory Utilization",
#         "Peak Memory (MB)",
#     )


# def _plot_search(csv_path: str, figure_path: str) -> None:
#     df = pd.read_csv(csv_path)
#     _plot_dataframe(
#         df,
#         figure_path,
#         "Parallel Search",
#         "Time (s)",
#     )


# def _plot_replace(csv_path: str, figure_path: str) -> None:
#     df = pd.read_csv(csv_path)
#     _plot_dataframe(
#         df,
#         figure_path,
#         "Parallel Search and Replace",
#         "Time (s)",
#     )


# # =====================
# # Main
# # =====================

# def main() -> None:
#     _validate_inputs()

#     time_rows = []
#     memory_rows = []
#     search_rows = []
#     replace_rows = []

#     for threads in THREAD_COUNTS:
#         print(f"[INFO] Running parallel benchmarks at {threads} thread(s)...", flush=True)

#         tic_comp = _repeat_operation("TIC", "compression", threads)
#         tic_decomp = _repeat_operation("TIC", "decompression", threads)

#         lbzip2_comp = _repeat_operation("lbzip2", "compression", threads)
#         lbzip2_decomp = _repeat_operation("lbzip2", "decompression", threads)

#         tic_search = _repeat_operation("TIC", "search", threads)
#         tic_replace = _repeat_operation("TIC", "replace", threads)

#         time_rows.append({
#             "Threads": threads,
#             "TIC Compression": tic_comp["avg_wall_time_s"],
#             "TIC Decompression": tic_decomp["avg_wall_time_s"],
#             "lbzip2 Compression": lbzip2_comp["avg_wall_time_s"],
#             "lbzip2 Decompression": lbzip2_decomp["avg_wall_time_s"],
#         })

#         memory_rows.append({
#             "Threads": threads,
#             "TIC Compression": tic_comp["avg_peak_memory_mb"],
#             "TIC Decompression": tic_decomp["avg_peak_memory_mb"],
#             "lbzip2 Compression": lbzip2_comp["avg_peak_memory_mb"],
#             "lbzip2 Decompression": lbzip2_decomp["avg_peak_memory_mb"],
#         })

#         search_rows.append({
#             "Threads": threads,
#             "TIC Search": tic_search["avg_wall_time_s"],
#         })

#         replace_rows.append({
#             "Threads": threads,
#             "TIC Lookup-and-Replace": tic_replace["avg_wall_time_s"],
#         })

#     time_df = pd.DataFrame(time_rows)
#     memory_df = pd.DataFrame(memory_rows)
#     search_df = pd.DataFrame(search_rows)
#     replace_df = pd.DataFrame(replace_rows)

#     write_dataframe_csv(time_df, PARALLEL_TIME_CSV)
#     write_dataframe_csv(memory_df, PARALLEL_MEMORY_CSV)
#     write_dataframe_csv(search_df, PARALLEL_SEARCH_CSV)
#     write_dataframe_csv(replace_df, PARALLEL_REPLACE_CSV)

#     _plot_time(PARALLEL_TIME_CSV, PARALLEL_TIME_PNG)
#     _plot_memory(PARALLEL_MEMORY_CSV, PARALLEL_MEMORY_PNG)
#     _plot_search(PARALLEL_SEARCH_CSV, PARALLEL_SEARCH_PNG)
#     _plot_replace(PARALLEL_REPLACE_CSV, PARALLEL_REPLACE_PNG)

#     print(f"Wrote: {PARALLEL_TIME_CSV}")
#     print(f"Wrote: {PARALLEL_MEMORY_CSV}")
#     print(f"Wrote: {PARALLEL_SEARCH_CSV}")
#     print(f"Wrote: {PARALLEL_REPLACE_CSV}")
#     print(f"Wrote: {PARALLEL_TIME_PNG}")
#     print(f"Wrote: {PARALLEL_MEMORY_PNG}")
#     print(f"Wrote: {PARALLEL_SEARCH_PNG}")
#     print(f"Wrote: {PARALLEL_REPLACE_PNG}")


# if __name__ == "__main__":
#     main()
