#!/usr/bin/env python3
"""
plot_parallel_subset.py

Re-plot the parallel results restricted to thread counts 1, 2, 4, 6 and 8.

Reads the CSVs produced by run_parallel_benchmarks.py from results/raw/ and
writes figures to results/figures/. It generates nothing on its own: if the
input CSVs are absent it reports which experiment must be run first and exits
cleanly, rather than fabricating or substituting data.

    python3 run_parallel_benchmarks.py --input datasets/f10.txt   # produces the CSVs
    python3 plot_parallel_subset.py                               # then plot
"""

import os
import sys

import pandas as pd
import matplotlib.pyplot as plt

from dataset_config import RESULTS_FIGURES_DIR, RESULTS_RAW_DIR, results_path

THREADS_TO_KEEP = [1, 2, 4, 6, 8]

TIME_CSV = results_path("raw", "parallel_time_results.csv")
MEMORY_CSV = results_path("raw", "parallel_memory_results.csv")
SEARCH_CSV = results_path("raw", "parallel_search_results.csv")
REPLACE_CSV = results_path("raw", "parallel_replace_results.csv")

# The experiment that produces every input this script consumes.
PRODUCER = "run_parallel_benchmarks.py"


def filter_threads(df):
    return df[df["Threads"].isin(THREADS_TO_KEEP)]


# def plot_csv(csv_path, output_png, title, ylabel):
#     df = filter_threads(pd.read_csv(csv_path))

#     plt.figure(figsize=(8, 5))

#     for col in df.columns:
#         if col == "Threads":
#             continue
#         plt.plot(df["Threads"], df[col], marker="o", linewidth=1.8, label=col)

#     plt.xlabel("Number of Threads")
#     plt.ylabel(ylabel)
#     plt.title(title)
#     plt.xticks(THREADS_TO_KEEP)
#     plt.grid(True, linestyle="--", alpha=0.4)
#     plt.legend()
#     plt.tight_layout()
#     plt.savefig(output_png, dpi=300)
#     plt.close()

#     print(f"Wrote: {output_png}")

def plot_csv(csv_path, output_png, title, ylabel):
    """Plot one CSV. Returns True if a figure was written, False if input was missing."""
    if not os.path.isfile(csv_path):
        print(f"[SKIP] missing input: {csv_path}", file=sys.stderr)
        return False

    os.makedirs(os.path.dirname(output_png) or ".", exist_ok=True)
    df = filter_threads(pd.read_csv(csv_path))

    plt.figure(figsize=(8, 5))

    markers = ["o", "s", "^", "D", "x", "*", "v"]

    linestyles = [
        "-",
        "--",
        "-.",
        ":",
        # (0, (3, 1, 1, 1)),
        # (0, (5, 2)),
        # (0, (1, 1)),
    ]

    curve_idx = 0

    for col in df.columns:
        if col == "Threads":
            continue

        plt.plot(
            df["Threads"],
            df[col],
            marker=markers[curve_idx % len(markers)],
            linestyle=linestyles[curve_idx % len(linestyles)],
            linewidth=1.8,
            markersize=6,
            label=col,
        )

        curve_idx += 1

    # for idx, col in enumerate(df.columns):
    #     if col == "Threads":
    #         continue

    #     plt.plot(
    #         df["Threads"],
    #         df[col],
    #         marker=markers[idx % len(markers)],
    #         linestyle=linestyles[idx % len(linestyles)],
    #         linewidth=1.8,
    #         markersize=6,
    #         label=col,
    #     )

    plt.xlabel("Number of Threads")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(THREADS_TO_KEEP)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()

    print(f"Wrote: {output_png}")
    return True


PLOTS = [
    (TIME_CSV, "parallel_time_1_2_4_6_8.png",
     "Parallel Compression and Decompression", "Time (s)"),
    (MEMORY_CSV, "parallel_memory_1_2_4_6_8.png",
     "Parallel Memory Utilization", "Peak Memory (MB)"),
    (SEARCH_CSV, "parallel_search_1_2_4_6_8.png",
     "Parallel Search", "Time (s)"),
    (REPLACE_CSV, "parallel_replace_1_2_4_6_8.png",
     "Parallel Search and Replace", "Time (s)"),
]


def main() -> int:
    written = 0
    missing = []

    for csv_path, png_name, title, ylabel in PLOTS:
        out = results_path("figures", png_name)
        if plot_csv(csv_path, out, title, ylabel):
            written += 1
        else:
            missing.append(csv_path)

    if missing:
        print(
            f"\n[INFO] {len(missing)} of {len(PLOTS)} input file(s) were missing "
            f"from {RESULTS_RAW_DIR}/:",
            file=sys.stderr,
        )
        for m in missing:
            print(f"         {m}", file=sys.stderr)
        print(
            f"\n[INFO] These are generated results and are no longer committed.\n"
            f"       Run the parallel experiment first:\n"
            f"         python3 {PRODUCER} --input datasets/f10.txt\n"
            f"       Then re-run this script. No data was fabricated or substituted.",
            file=sys.stderr,
        )

    if written:
        print(f"\n[ OK ] wrote {written} figure(s) to {RESULTS_FIGURES_DIR}/")
    else:
        print(f"[INFO] nothing to plot.", file=sys.stderr)

    # Missing generated input is a clean, expected exit -- not a crash.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
