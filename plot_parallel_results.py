#!/usr/bin/env python3
"""
plot_parallel_results.py

Generate publication-quality plots from existing CSV files.

Figures:
1) Parallel Compression and Decompression
2) Parallel Memory Utilization
3) Parallel Search
4) Parallel Search and Replace

This script DOES NOT rerun benchmarks.
It only reads CSV results and generates plots.
"""

from __future__ import annotations

import os
import pandas as pd
import matplotlib.pyplot as plt

from dataset_config import RESULTS_FIGURES_DIR, results_path

# =====================================================
# INPUT CSV FILES
# =====================================================

PARALLEL_TIME_CSV = results_path("raw", "parallel_time_results.csv")
PARALLEL_MEMORY_CSV = results_path("raw", "parallel_memory_results.csv")
PARALLEL_SEARCH_CSV = results_path("raw", "parallel_search_results.csv")
PARALLEL_REPLACE_CSV = results_path("raw", "parallel_replace_results.csv")

# =====================================================
# OUTPUT FIGURES
# =====================================================

PARALLEL_TIME_PNG = results_path("figures", "parallel_time.png")
PARALLEL_MEMORY_PNG = results_path("figures", "parallel_memory.png")
PARALLEL_SEARCH_PNG = results_path("figures", "parallel_search.png")
PARALLEL_REPLACE_PNG = results_path("figures", "parallel_replace.png")

# =====================================================
# Plot Style Configuration
# =====================================================

LINE_STYLES = [
    "-",    # solid
    "--",   # dashed
    "-.",   # dash-dot
    ":",    # dotted
]

MARKERS = [
    "o",
    "s",
    "^",
    "D",
    "x",
    "*",
]

LINE_WIDTH = 1.8
MARKER_SIZE = 6

# =====================================================
# Generic Plot Function
# =====================================================

def plot_dataframe(
    csv_path: str,
    figure_path: str,
    title: str,
    ylabel: str,
) -> None:

    if not os.path.exists(csv_path):
        print(f"[SKIP] missing input: {csv_path}")
        print(f"       Generated results are no longer committed. Run the parallel "
              f"experiment first:")
        print(f"         python3 run_parallel_benchmarks.py --input datasets/f10.txt")
        return

    os.makedirs(os.path.dirname(figure_path) or ".", exist_ok=True)

    df = pd.read_csv(csv_path)

    x_col = "Threads"

    y_columns = [
        c for c in df.columns
        if c != x_col
    ]

    plt.figure(figsize=(8, 5))

    for idx, col in enumerate(y_columns):

        linestyle = LINE_STYLES[
            idx % len(LINE_STYLES)
        ]

        marker = MARKERS[
            idx % len(MARKERS)
        ]

        plt.plot(
            df[x_col],
            df[col],
            label=col,
            linestyle=linestyle,
            marker=marker,
            linewidth=LINE_WIDTH,
            markersize=MARKER_SIZE,
        )

    plt.xlabel("Number of Threads")
    plt.ylabel(ylabel)

    plt.title(title)

    plt.xticks(df[x_col])

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

    print(f"[DONE] Wrote figure: {figure_path}")

# =====================================================
# Main
# =====================================================

def main() -> None:

    # -------------------------------------------------
    # Time
    # -------------------------------------------------

    plot_dataframe(
        csv_path=PARALLEL_TIME_CSV,
        figure_path=PARALLEL_TIME_PNG,
        title="Parallel Compression and Decompression",
        ylabel="Time (s)",
    )

    # -------------------------------------------------
    # Memory
    # -------------------------------------------------

    plot_dataframe(
        csv_path=PARALLEL_MEMORY_CSV,
        figure_path=PARALLEL_MEMORY_PNG,
        title="Parallel Memory Utilization",
        ylabel="Peak Memory (MB)",
    )

    # -------------------------------------------------
    # Search
    # -------------------------------------------------

    plot_dataframe(
        csv_path=PARALLEL_SEARCH_CSV,
        figure_path=PARALLEL_SEARCH_PNG,
        title="Parallel Search",
        ylabel="Time (s)",
    )

    # -------------------------------------------------
    # Search and Replace
    # -------------------------------------------------

    plot_dataframe(
        csv_path=PARALLEL_REPLACE_CSV,
        figure_path=PARALLEL_REPLACE_PNG,
        title="Parallel Search and Replace",
        ylabel="Time (s)",
    )

    print("\n[INFO] Finished generating all plots.")


if __name__ == "__main__":
    main()