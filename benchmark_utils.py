#!/usr/bin/env python3
"""
benchmark_utils.py

Shared helper utilities for benchmarking:
- compression / decompression / search / search-and-replace
- CSV and LaTeX generation
- entropy calculation
- parallel plotting

Design goals:
- keep command construction centralized
- keep setup separate from measured benchmark scope
- support TIC, PIC, gzip, bzip2, lz4, lbzip2, zgrep, bzgrep
- provide stable formatting for tables and figures
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Optional

import pandas as pd

# Dataset layout is defined once in dataset_config.py (standard library only)
# and re-exported here so runners may import it from either module.
from dependencies import (  # noqa: F401
    MissingDependencyError,
    preflight,
    require_binaries,
    require_executables,
    require_input_files,
    require_python_packages,
    require_writable_dir,
)
from dataset_config import (  # noqa: F401
    BENCHMARK_DATASET_NAMES,
    BENCHMARK_DATASET_TARGET_MB,
    BENCHMARK_INPUT_FILES,
    DATASET_DIR,
    EXPECTED_DATASET_COUNT,
    PARALLEL_INPUT_FILE,
    benchmark_input_files,
    dataset_path,
    parallel_input_file,
    results_path,
)

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None  # plotting helpers will raise if used without matplotlib

# =====================
# Configuration
# =====================

PIC_BINARY = "./pic-v3.1"
TIC_BINARY = "./epic-v3.1"
LBZIP2_BINARY = "lbzip2"

DEFAULT_SAMPLE_INTERVAL = 0.05
DEFAULT_TIMEOUT_S: Optional[int] = None
# Authoritative thread-count configuration for the parallel experiments.
# The parallel experiments use 1, 2, 4, 6, and 8 threads; the committed
# parallel_*_results.csv files were produced with exactly these counts.
DEFAULT_PARALLEL_THREADS = [1, 2, 4, 6, 8]

TOOL_EXTENSIONS: dict[str, str] = {
    "TIC": ".tic",
    "PIC": ".pic",
    "gzip": ".gz",
    "bzip2": ".bz2",
    "lz4": ".lz4",
    "lbzip2": ".bz2",
}

# Use unique colors and markers for each curve.
# The exact colors are intentionally fixed for reproducibility in figures.
PLOT_STYLE_MAP: dict[str, dict[str, str]] = {
    "TIC-Compression": {"color": "#1f77b4", "marker": "o"},
    "TIC-Decompression": {"color": "#4f9cd6", "marker": "s"},
    "PIC-Compression": {"color": "#d62728", "marker": "^"},
    "PIC-Decompression": {"color": "#ff7f0e", "marker": "D"},
    "lbzip2-Compression": {"color": "#2ca02c", "marker": "x"},
    "lbzip2-Decompression": {"color": "#9467bd", "marker": "+"},
    "TIC-Search": {"color": "#1f77b4", "marker": "o"},
    "PIC-Search": {"color": "#d62728", "marker": "s"},
}


# =====================
# Internal helpers
# =====================

def _require_supported_tool(tool: str, supported: set[str]) -> None:
    if tool not in supported:
        raise ValueError(f"Unsupported tool '{tool}'. Supported tools: {sorted(supported)}")


_PSUTIL = None
_PSUTIL_RESOLVED = False


def _require_psutil():
    """
    Return the psutil module, or fail loudly.

    psutil is REQUIRED for every memory measurement. It used to be imported
    inside a bare try/except that returned None on failure, after which
    _process_tree_memory_mb() returned 0.0 and every memory column in the
    generated CSVs filled with zeros while the run still reported success --
    a missing dependency silently became publishable numbers.

    A numeric zero must never stand for an unavailable measurement, so this
    now raises instead. Runners call preflight() at start-up, so in practice
    the failure happens before any measurement begins.
    """
    global _PSUTIL, _PSUTIL_RESOLVED

    if not _PSUTIL_RESOLVED:
        try:
            import psutil  # type: ignore
            _PSUTIL = psutil
        except Exception:
            _PSUTIL = None
        _PSUTIL_RESOLVED = True

    if _PSUTIL is None:
        raise MissingDependencyError(
            "psutil is required for memory measurements but is not installed.\n"
            "  Refusing to continue: without it every memory column would be "
            "filled with zeros,\n"
            "  which would look like a successful measurement of 0 MB.\n"
            "  Install with: python3 -m pip install psutil\n"
            "  Or install everything: python3 -m pip install -r requirements.txt\n"
            "  Then re-check with: python3 check_environment.py"
        )
    return _PSUTIL


def _safe_unlink(path: str | Path) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def _process_tree_memory_mb(root_pid: int) -> tuple[float, float]:
    """
    Return (rss_sum_mb, peak_rss_sum_mb_this_sample).
    In a single sample, both are identical; kept separate for readability upstream.
    """
    psutil = _require_psutil()

    try:
        root = psutil.Process(root_pid)
    except Exception:
        # The process already exited before this sample. This is a genuine
        # measurement of "no resident memory at this instant", not a missing
        # dependency, so 0.0 is the correct value to record here.
        return 0.0, 0.0

    rss = 0
    seen = set()
    stack = [root]
    while stack:
        proc = stack.pop()
        try:
            if proc.pid in seen:
                continue
            seen.add(proc.pid)
            rss += proc.memory_info().rss
            stack.extend(proc.children(recursive=False))
        except Exception:
            continue

    rss_mb = rss / (1024 ** 2)
    return rss_mb, rss_mb


# =====================
# 1. Tool and path helpers
# =====================

def get_tool_extension(tool: str) -> str:
    """
    Return the file extension used by a compressed artifact for a given tool.
    """
    _require_supported_tool(tool, set(TOOL_EXTENSIONS.keys()))
    return TOOL_EXTENSIONS[tool]


def get_compressed_path(input_path: str, tool: str) -> str:
    """
    Construct the canonical compressed-file path for an input file and tool.
    Example:
        datasets/f1.txt + TIC -> datasets/f1.txt.tic
    """
    return input_path + get_tool_extension(tool)


def get_decompressed_output_path(input_path: str, tool: str, output_dir: str) -> str:
    """
    Construct a decompressed output path under output_dir.
    """
    input_stem = Path(input_path).name
    return str(Path(output_dir) / f"{input_stem}.{tool}.decompressed.txt")


def get_log_paths(output_dir: str, tool: str, operation: str, file_stem: str) -> tuple[str, str]:
    """
    Return (stdout_path, stderr_path) for a tool/operation/file_stem combination.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stdout_path = str(Path(output_dir) / f"{tool}_{operation}_{file_stem}_stdout.txt")
    stderr_path = str(Path(output_dir) / f"{tool}_{operation}_{file_stem}_stderr.txt")
    return stdout_path, stderr_path


# =====================
# 2. Command builders
# =====================

def build_compress_command(tool: str, input_path: str, output_path: str, threads: int = 1) -> list[str]:
    """
    Build a compression command.
    """
    _require_supported_tool(tool, {"TIC", "PIC", "gzip", "bzip2", "lz4", "lbzip2"})

    if tool == "TIC":
        return [TIC_BINARY, "-c", "-t", str(threads), input_path, output_path]
    if tool == "PIC":
        return [PIC_BINARY, "-c", "-t", str(threads), input_path, output_path]
    if tool == "gzip":
        # gzip writes to input.gz by default; output_path is expected to match that
        return ["gzip", "-kf", input_path]
    if tool == "bzip2":
        return ["bzip2", "-kf", input_path]
    if tool == "lz4":
        return ["lz4", "-kf", input_path]
    if tool == "lbzip2":
        return [LBZIP2_BINARY, "-k", "-f", "-n", str(threads), input_path]

    raise AssertionError("unreachable")


def build_decompress_command(tool: str, input_path: str, output_path: str, threads: int = 1) -> list[str]:
    """
    Build a decompression command.
    """
    _require_supported_tool(tool, {"TIC", "PIC", "gzip", "bzip2", "lz4", "lbzip2"})

    if tool == "TIC":
        return [TIC_BINARY, "-d", "-t", str(threads), input_path, output_path]
    if tool == "PIC":
        return [PIC_BINARY, "-d", "-t", str(threads), input_path, output_path]
    if tool == "gzip":
        return ["gzip", "-cd", input_path]
    if tool == "bzip2":
        return ["bzip2", "-cd", input_path]
    if tool == "lz4":
        return ["lz4", "-d", "-c", input_path]
    if tool == "lbzip2":
        return [LBZIP2_BINARY, "-d", "-c", "-n", str(threads), input_path]

    raise AssertionError("unreachable")


def build_search_command(
    tool: str,
    compressed_path: str,
    query: str,
    dummy_output_path: str | None = None,
    threads: int = 1,
) -> list[str]:
    """
    Build a search command for:
    - TIC / PIC native search
    - zgrep / bzgrep streaming search
    """
    _require_supported_tool(tool, {"TIC", "PIC", "zgrep", "bzgrep"})

    if tool == "TIC":
        if dummy_output_path is None:
            raise ValueError("dummy_output_path is required for TIC search")
        return [TIC_BINARY, "-l", "-t", str(threads), compressed_path, dummy_output_path, query]

    if tool == "PIC":
        if dummy_output_path is None:
            raise ValueError("dummy_output_path is required for PIC search")
        return [PIC_BINARY, "-l", "-t", str(threads), compressed_path, dummy_output_path, query]

    if tool == "zgrep":
        return ["zgrep", "-F", query, compressed_path]

    if tool == "bzgrep":
        return ["bzgrep", "-F", query, compressed_path]

    raise AssertionError("unreachable")


def build_replace_command(
    tool: str,
    compressed_path: str,
    search_string: str,
    replace_string: str,
    output_path: str,
    threads: int = 1,
) -> list[str]:
    """
    Build a native lookup-and-replace command for TIC / PIC.
    """
    _require_supported_tool(tool, {"TIC", "PIC"})

    if tool == "TIC":
        return [
            TIC_BINARY, "-r", "-t", str(threads), compressed_path, output_path,
            search_string, replace_string
        ]
    if tool == "PIC":
        return [
            PIC_BINARY, "-r", "-t", str(threads), compressed_path, output_path,
            search_string, replace_string
        ]

    raise AssertionError("unreachable")


def build_grep_pipeline(tool: str, compressed_path: str, query: str) -> list[list[str]]:
    """
    Build a decompression + grep pipeline for gzip / bzip2 / lz4.
    Example:
        [["gzip", "-cd", file.gz], ["grep", "-F", "needle"]]
    """
    _require_supported_tool(tool, {"gzip", "bzip2", "lz4", "lbzip2"})

    if tool == "gzip":
        return [["gzip", "-cd", compressed_path], ["grep", "-F", query]]
    if tool == "bzip2":
        return [["bzip2", "-cd", compressed_path], ["grep", "-F", query]]
    if tool == "lz4":
        return [["lz4", "-d", "-c", compressed_path], ["grep", "-F", query]]
    if tool == "lbzip2":
        return [[LBZIP2_BINARY, "-d", "-c", compressed_path], ["grep", "-F", query]]

    raise AssertionError("unreachable")


# =====================
# 3. Setup helpers
# =====================

def ensure_compressed_file(tool: str, input_path: str, threads: int = 1, force: bool = False) -> str:
    """
    Ensure a compressed file exists. If it is missing, create it.
    Returns the compressed path.

    This is a setup helper only. Its runtime should not be used as a measured
    benchmark result unless called explicitly by a benchmark script.
    """
    compressed_path = get_compressed_path(input_path, tool)
    if os.path.exists(compressed_path) and not force:
        return compressed_path

    _safe_unlink(compressed_path)
    cmd = build_compress_command(tool, input_path, compressed_path, threads=threads)

    # gzip/bzip2/lz4/lbzip2 write to their own conventional output locations.
    if tool in {"gzip", "bzip2", "lz4", "lbzip2"}:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    if not os.path.exists(compressed_path):
        raise RuntimeError(f"Failed to create compressed file: {compressed_path} (tool={tool})")

    return compressed_path


def ensure_compressed_files(
    tools: list[str],
    input_path: str,
    threads: int = 1,
    force: bool = False,
) -> dict[str, str]:
    """
    Ensure compressed files exist for all requested tools.
    Returns a dict mapping tool -> compressed path.
    """
    result: dict[str, str] = {}
    for tool in tools:
        result[tool] = ensure_compressed_file(tool, input_path, threads=threads, force=force)
    return result


# =====================
# 4. Measurement helpers
# =====================

def measure_command(
    command: list[str],
    stdout_path: str | None = None,
    stderr_path: str | None = None,
    timeout_s: int | None = DEFAULT_TIMEOUT_S,
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL,
) -> dict[str, Any]:
    """
    Run a single command and measure:
    - return code
    - wall-clock time
    - average sampled memory
    - peak sampled memory

    If stdout_path / stderr_path are None, outputs are discarded.
    """
    stdout_target = subprocess.DEVNULL
    stderr_target = subprocess.DEVNULL
    out_fh = err_fh = None

    try:
        if stdout_path is not None:
            Path(stdout_path).parent.mkdir(parents=True, exist_ok=True)
            out_fh = open(stdout_path, "wb")
            stdout_target = out_fh
        if stderr_path is not None:
            Path(stderr_path).parent.mkdir(parents=True, exist_ok=True)
            err_fh = open(stderr_path, "wb")
            stderr_target = err_fh

        start = time.perf_counter()
        proc = subprocess.Popen(command, stdout=stdout_target, stderr=stderr_target)

        samples: list[float] = []
        peak_mb = 0.0
        timed_out = False

        while True:
            if timeout_s is not None and (time.perf_counter() - start) > timeout_s:
                timed_out = True
                try:
                    psutil = _try_import_psutil()
                    if psutil is not None:
                        p = psutil.Process(proc.pid)
                        for child in p.children(recursive=True):
                            try:
                                child.kill()
                            except Exception:
                                pass
                        try:
                            p.kill()
                        except Exception:
                            pass
                    else:
                        proc.kill()
                except Exception:
                    pass
                break

            if proc.poll() is not None:
                break

            rss_mb, peak_sample_mb = _process_tree_memory_mb(proc.pid)
            samples.append(rss_mb)
            peak_mb = max(peak_mb, peak_sample_mb)

            time.sleep(sample_interval)

        try:
            return_code = proc.wait(timeout=1)
        except Exception:
            return_code = proc.poll()

        wall_time_s = time.perf_counter() - start
        avg_memory_mb = mean(samples) if samples else 0.0

        if timed_out and return_code is None:
            return_code = -9

        return {
            "return_code": return_code,
            "wall_time_s": round(wall_time_s, 6),
            "avg_memory_mb": round(avg_memory_mb, 6),
            "peak_memory_mb": round(peak_mb, 6),
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }
    finally:
        if out_fh is not None:
            out_fh.close()
        if err_fh is not None:
            err_fh.close()


def measure_pipeline(
    commands: list[list[str]],
    stdout_path: str | None = None,
    stderr_path: str | None = None,
    timeout_s: int | None = DEFAULT_TIMEOUT_S,
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL,
) -> dict[str, Any]:
    """
    Run a pipeline such as:
        [["gzip", "-cd", file.gz], ["grep", "-F", "needle"]]

    The reported return code is the return code of the final command
    (typically grep), which is the most relevant for search semantics.
    """
    if not commands:
        raise ValueError("commands must not be empty")

    stdout_target_last = subprocess.DEVNULL
    stderr_target_last = subprocess.DEVNULL
    out_fh = err_fh = None

    try:
        if stdout_path is not None:
            Path(stdout_path).parent.mkdir(parents=True, exist_ok=True)
            out_fh = open(stdout_path, "wb")
            stdout_target_last = out_fh
        if stderr_path is not None:
            Path(stderr_path).parent.mkdir(parents=True, exist_ok=True)
            err_fh = open(stderr_path, "wb")
            stderr_target_last = err_fh

        start = time.perf_counter()
        procs: list[subprocess.Popen] = []
        prev = None

        for idx, cmd in enumerate(commands):
            is_last = (idx == len(commands) - 1)
            proc = subprocess.Popen(
                cmd,
                stdin=None if prev is None else prev.stdout,
                stdout=stdout_target_last if is_last else subprocess.PIPE,
                stderr=stderr_target_last if is_last else subprocess.DEVNULL,
            )
            if prev is not None and prev.stdout is not None:
                prev.stdout.close()
            procs.append(proc)
            prev = proc

        samples: list[float] = []
        peak_mb = 0.0
        timed_out = False

        while True:
            if timeout_s is not None and (time.perf_counter() - start) > timeout_s:
                timed_out = True
                psutil = _try_import_psutil()
                if psutil is not None:
                    for proc in procs:
                        try:
                            p = psutil.Process(proc.pid)
                            for child in p.children(recursive=True):
                                try:
                                    child.kill()
                                except Exception:
                                    pass
                            try:
                                p.kill()
                            except Exception:
                                pass
                        except Exception:
                            pass
                else:
                    for proc in procs:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                break

            if all(proc.poll() is not None for proc in procs):
                break

            rss_sum = 0.0
            peak_sample = 0.0
            for proc in procs:
                if proc.poll() is None:
                    rss_mb, peak_sample_mb = _process_tree_memory_mb(proc.pid)
                    rss_sum += rss_mb
                    peak_sample = max(peak_sample, peak_sample_mb)
            samples.append(rss_sum)
            peak_mb = max(peak_mb, peak_sample)

            time.sleep(sample_interval)

        exit_codes: list[Optional[int]] = []
        for proc in procs:
            try:
                exit_codes.append(proc.wait(timeout=1))
            except Exception:
                exit_codes.append(proc.poll())

        wall_time_s = time.perf_counter() - start
        avg_memory_mb = mean(samples) if samples else 0.0
        return_code = exit_codes[-1] if exit_codes else None

        if timed_out and return_code is None:
            return_code = -9

        return {
            "return_code": return_code,
            "wall_time_s": round(wall_time_s, 6),
            "avg_memory_mb": round(avg_memory_mb, 6),
            "peak_memory_mb": round(peak_mb, 6),
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }
    finally:
        if out_fh is not None:
            out_fh.close()
        if err_fh is not None:
            err_fh.close()


def repeat_measurement(measure_fn: Callable[[], dict[str, Any]], repeats: int = 5) -> dict[str, Any]:
    """
    Repeat a measurement function and aggregate average wall-clock time,
    average sampled memory, and average peak memory.

    Returns:
    {
        "avg_wall_time_s": float,
        "avg_avg_memory_mb": float,
        "avg_peak_memory_mb": float,
        "all_runs": list[dict],
    }
    """
    if repeats <= 0:
        raise ValueError("repeats must be positive")

    all_runs = [measure_fn() for _ in range(repeats)]

    return {
        "avg_wall_time_s": round(mean(run["wall_time_s"] for run in all_runs), 6),
        "avg_avg_memory_mb": round(mean(run["avg_memory_mb"] for run in all_runs), 6),
        "avg_peak_memory_mb": round(mean(run["peak_memory_mb"] for run in all_runs), 6),
        "all_runs": all_runs,
    }


# =====================
# 5. File/statistics helpers
# =====================

def get_file_size_bytes(path: str) -> int:
    return Path(path).stat().st_size


def bytes_to_mb(value_bytes: int, decimals: int = 3) -> float:
    return round(value_bytes / (1024 ** 2), decimals)


def safe_ratio(
    numerator: float | int | None,
    denominator: float | int | None,
    decimals: int = 2,
) -> float | str:
    """
    Return rounded numerator/denominator or "" if invalid.
    """
    if numerator is None or denominator is None:
        return ""
    if denominator == 0:
        return ""
    return round(float(numerator) / float(denominator), decimals)


def compute_compression_ratio(original_path: str, compressed_path: str, decimals: int = 2) -> float | str:
    """
    CR = original_size / compressed_size
    """
    if not os.path.exists(original_path) or not os.path.exists(compressed_path):
        return ""
    compressed_bytes = get_file_size_bytes(compressed_path)
    if compressed_bytes == 0:
        return ""
    return round(get_file_size_bytes(original_path) / compressed_bytes, decimals)


def compute_file_entropy(path: str, decimals: int = 3) -> float:
    """
    Compute Shannon entropy over the raw byte stream of the file:
        H = -sum(p_i * log2(p_i))
    """
    data = Path(path).read_bytes()
    if not data:
        return 0.0

    counts = Counter(data)
    total = len(data)

    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)

    return round(entropy, decimals)


# =====================
# 6. Validation/debug helpers
# =====================

def compare_files_exact(path_a: str, path_b: str) -> tuple[bool, str]:
    """
    Compare two files byte-for-byte.
    """
    if not os.path.exists(path_a):
        return False, f"Missing file: {path_a}"
    if not os.path.exists(path_b):
        return False, f"Missing file: {path_b}"

    size_a = get_file_size_bytes(path_a)
    size_b = get_file_size_bytes(path_b)
    if size_a != size_b:
        return False, f"Size mismatch: {size_a} vs {size_b}"

    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        while True:
            ba = fa.read(1024 * 1024)
            bb = fb.read(1024 * 1024)
            if ba != bb:
                return False, "Byte mismatch"
            if not ba:
                break

    return True, "Files match exactly"


def count_output_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def extract_first_integer(path: str) -> int | None:
    import re

    if not os.path.exists(path):
        return None
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"(-?\d+)", text)
    return int(m.group(1)) if m else None


def read_text_safe(path: str, max_chars: int | None = None) -> str:
    if not os.path.exists(path):
        return ""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars]
    return text


# =====================
# 7. CSV loading helpers
# =====================

def load_csv_results(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def lookup_result_value(df: pd.DataFrame, file_name: str, column_name: str) -> Any:
    rows = df[df["File Name"] == file_name]
    if rows.empty or column_name not in rows.columns:
        return None
    return rows.iloc[0][column_name]


def load_compression_metrics(
    csv_path: str = None,
) -> pd.DataFrame:
    if csv_path is None:
        csv_path = results_path("raw", "compression_time_results.csv")
    return load_csv_results(csv_path)


def load_decompression_metrics(
    csv_path: str = None,
) -> pd.DataFrame:
    if csv_path is None:
        csv_path = results_path("raw", "decompression_time_results.csv")
    return load_csv_results(csv_path)


# =====================
# 8. CSV writing helpers
# =====================

def write_dataframe_csv(df: pd.DataFrame, csv_path: str) -> None:
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)


# =====================
# 9. LaTeX helpers
# =====================

def latex_escape(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
    return "".join(replacements.get(ch, ch) for ch in str(text))


def format_number(value: Any, decimals: int) -> str:
    if value == "" or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return latex_escape(str(value))


def build_grouped_latex_table(
    df: pd.DataFrame,
    tex_path: str,
    caption: str,
    label: str,
    group_headers: list[tuple[str, int]],
    column_headers: list[str],
    align_spec: str | None = None,
) -> None:
    """
    Build a LaTeX table with a grouped first header row.

    group_headers example:
        [("File Name", 1), ("Original Size (MB)", 1), ("CR", 5)]

    column_headers example:
        ["File Name", "Original Size (MB)", "TIC", "PIC", "gzip", "bzip2", "lz4"]

    Notes:
    - If a group spans 1 column, its second-row header cell is left blank.
    - Uses \\multicolumn for grouped headers.
    """
    if not align_spec:
        align_spec = "c" * len(column_headers)

    Path(tex_path).parent.mkdir(parents=True, exist_ok=True)

    # Header row 1
    row1_parts = []
    for title, span in group_headers:
        if span == 1:
            row1_parts.append(latex_escape(title))
        else:
            row1_parts.append(rf"\multicolumn{{{span}}}{{c}}{{{latex_escape(title)}}}")
    header_row_1 = " & ".join(row1_parts) + r" \\"

    # Header row 2
    row2_cells = []
    idx = 0
    for _, span in group_headers:
        if span == 1:
            row2_cells.append("")
            idx += 1
        else:
            for _ in range(span):
                row2_cells.append(latex_escape(column_headers[idx]))
                idx += 1
    header_row_2 = " & ".join(row2_cells) + r" \\"

    # Body
    body_lines = []
    for _, row in df.iterrows():
        cells = []
        for col in column_headers:
            val = row[col]
            if isinstance(val, str):
                cells.append(latex_escape(val))
            else:
                cells.append(str(val) if pd.notna(val) else "")
        body_lines.append(" & ".join(cells) + r" \\")

    latex = (
        r"\begin{table}[ht]" "\n"
        r"\centering" "\n"
        rf"\begin{{tabular}}{{{align_spec}}}" "\n"
        r"\hline" "\n"
        f"{header_row_1}\n"
        f"{header_row_2}\n"
        r"\hline" "\n"
        + "\n".join(body_lines) + "\n"
        + r"\hline" "\n"
        + r"\end{tabular}" "\n"
        + rf"\caption{{{latex_escape(caption)}}}" "\n"
        + rf"\label{{{latex_escape(label)}}}" "\n"
        + r"\end{table}" "\n"
    )
    Path(tex_path).write_text(latex, encoding="utf-8")


def build_simple_latex_table(
    df: pd.DataFrame,
    tex_path: str,
    caption: str,
    label: str,
    column_headers: list[str],
    align_spec: str | None = None,
) -> None:
    """
    Build a simple one-header-row LaTeX table.
    """
    if not align_spec:
        align_spec = "c" * len(column_headers)

    Path(tex_path).parent.mkdir(parents=True, exist_ok=True)

    header_row = " & ".join(latex_escape(h) for h in column_headers) + r" \\"

    body_lines = []
    for _, row in df.iterrows():
        cells = []
        for col in column_headers:
            val = row[col]
            if isinstance(val, str):
                cells.append(latex_escape(val))
            else:
                cells.append(str(val) if pd.notna(val) else "")
        body_lines.append(" & ".join(cells) + r" \\")

    latex = (
        r"\begin{table}[ht]" "\n"
        r"\centering" "\n"
        rf"\begin{{tabular}}{{{align_spec}}}" "\n"
        r"\hline" "\n"
        f"{header_row}\n"
        r"\hline" "\n"
        + "\n".join(body_lines) + "\n"
        + r"\hline" "\n"
        + r"\end{tabular}" "\n"
        + rf"\caption{{{latex_escape(caption)}}}" "\n"
        + rf"\label{{{latex_escape(label)}}}" "\n"
        + r"\end{table}" "\n"
    )
    Path(tex_path).write_text(latex, encoding="utf-8")


# =====================
# 10. Plotting helpers
# =====================

def get_plot_style_map() -> dict[str, dict[str, str]]:
    return dict(PLOT_STYLE_MAP)


def _require_matplotlib() -> None:
    if plt is None:
        raise RuntimeError("matplotlib is required for plotting helpers")


def plot_parallel_time(csv_path: str, figure_path: str, title: str = "Parallel Compression and Decompression") -> None:
    _require_matplotlib()
    df = pd.read_csv(csv_path)

    curves = [
        "TIC Compression",
        "TIC Decompression",
        "PIC Compression",
        "PIC Decompression",
        "lbzip2 Compression",
        "lbzip2 Decompression",
    ]

    plt.figure(figsize=(8, 5))
    for curve in curves:
        style_key = curve.replace(" ", "-")
        style = PLOT_STYLE_MAP[style_key]
        plt.plot(
            df["Threads"],
            df[curve],
            label=style_key,
            color=style["color"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=6,
        )

    plt.xlabel("Number of threads")
    plt.ylabel("Time (s)")
    plt.title(title)
    plt.xticks(df["Threads"])
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    Path(figure_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(figure_path, dpi=300)
    plt.close()


def plot_parallel_memory(csv_path: str, figure_path: str, title: str = "Parallel Memory Utilization") -> None:
    _require_matplotlib()
    df = pd.read_csv(csv_path)

    curves = [
        "TIC Compression",
        "TIC Decompression",
        "PIC Compression",
        "PIC Decompression",
        "lbzip2 Compression",
        "lbzip2 Decompression",
    ]

    plt.figure(figsize=(8, 5))
    for curve in curves:
        style_key = curve.replace(" ", "-")
        style = PLOT_STYLE_MAP[style_key]
        plt.plot(
            df["Threads"],
            df[curve],
            label=style_key,
            color=style["color"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=6,
        )

    plt.xlabel("Number of threads")
    plt.ylabel("Memory (MB)")
    plt.title(title)
    plt.xticks(df["Threads"])
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    Path(figure_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(figure_path, dpi=300)
    plt.close()


def plot_parallel_search(csv_path: str, figure_path: str, title: str = "TIC and PIC Parallel Search") -> None:
    _require_matplotlib()
    df = pd.read_csv(csv_path)

    curves = ["TIC Search", "PIC Search"]

    plt.figure(figsize=(8, 5))
    for curve in curves:
        style_key = curve.replace(" ", "-")
        style = PLOT_STYLE_MAP[style_key]
        plt.plot(
            df["Threads"],
            df[curve],
            label=style_key,
            color=style["color"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=6,
        )

    plt.xlabel("Number of threads")
    plt.ylabel("Time (s)")
    plt.title(title)
    plt.xticks(df["Threads"])
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    Path(figure_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(figure_path, dpi=300)
    plt.close()


# =====================
# Convenience exports
# =====================

__all__ = [
    # dataset layout (re-exported from dataset_config)
    "DATASET_DIR",
    "BENCHMARK_DATASET_NAMES",
    "BENCHMARK_DATASET_TARGET_MB",
    "BENCHMARK_INPUT_FILES",
    "PARALLEL_INPUT_FILE",
    "EXPECTED_DATASET_COUNT",
    "dataset_path",
    "benchmark_input_files",
    "parallel_input_file",
    # configuration
    "PIC_BINARY",
    "TIC_BINARY",
    "LBZIP2_BINARY",
    "DEFAULT_SAMPLE_INTERVAL",
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_PARALLEL_THREADS",
    # tool/path helpers
    "get_tool_extension",
    "get_compressed_path",
    "get_decompressed_output_path",
    "get_log_paths",
    # command builders
    "build_compress_command",
    "build_decompress_command",
    "build_search_command",
    "build_replace_command",
    "build_grep_pipeline",
    # setup helpers
    "ensure_compressed_file",
    "ensure_compressed_files",
    # measurement helpers
    "measure_command",
    "measure_pipeline",
    "repeat_measurement",
    # file/stat helpers
    "get_file_size_bytes",
    "bytes_to_mb",
    "safe_ratio",
    "compute_compression_ratio",
    "compute_file_entropy",
    # validation/debug helpers
    "compare_files_exact",
    "count_output_lines",
    "extract_first_integer",
    "read_text_safe",
    # CSV loading helpers
    "load_csv_results",
    "lookup_result_value",
    "load_compression_metrics",
    "load_decompression_metrics",
    # CSV writing helpers
    "write_dataframe_csv",
    # latex helpers
    "latex_escape",
    "format_number",
    "build_grouped_latex_table",
    "build_simple_latex_table",
    # plotting helpers
    "get_plot_style_map",
    "plot_parallel_time",
    "plot_parallel_memory",
    "plot_parallel_search",
]
