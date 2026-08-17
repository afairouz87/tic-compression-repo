#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt

THREADS_TO_KEEP = [1, 2, 4, 6, 8]

TIME_CSV = "parallel_time_results.csv"
MEMORY_CSV = "parallel_memory_results.csv"
SEARCH_CSV = "parallel_search_results.csv"
REPLACE_CSV = "parallel_replace_results.csv"


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



def main():
    plot_csv(
        TIME_CSV,
        "parallel_time_1_2_4_6_8.png",
        "Parallel Compression and Decompression",
        "Time (s)",
    )

    plot_csv(
        MEMORY_CSV,
        "parallel_memory_1_2_4_6_8.png",
        "Parallel Memory Utilization",
        "Peak Memory (MB)",
    )

    plot_csv(
        SEARCH_CSV,
        "parallel_search_1_2_4_6_8.png",
        "Parallel Search",
        "Time (s)",
    )

    plot_csv(
        REPLACE_CSV,
        "parallel_replace_1_2_4_6_8.png",
        "Parallel Search and Replace",
        "Time (s)",
    )


if __name__ == "__main__":
    main()
