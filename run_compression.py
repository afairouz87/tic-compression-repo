#!/usr/bin/env python3

# run_compression.py
# - Runs multiple compressors on an input file
# - Writes a wide CSV (cr_results.csv): File Name, File Size (MB), <tools...>
# - Generates a LaTeX table (cr_table.tex) with:
#     * \multirow on "File Name" and "File Size (MB)" over the two header rows
#     * \multicolumn over the "Compression Ratio" group across tool columns

# Note: The LaTeX table uses \multirow; remember to include \usepackage{multirow} in your preamble.


import os
import time
import subprocess
from statistics import mean
import pandas as pd

# =====================
# User Config
# =====================
# Path to the input file and its name (used in the CSV)

INPUT_FILE_NAME  = "test4.txt"   # <-- this is used in the CSV/LaTeX
INPUT_FILE_PATH  = "../textFiles/" + INPUT_FILE_NAME

# Tool order for CSV columns and LaTeX columns
TOOLS_ORDER      = ["PIC", "TIC", "gzip", "bzip2", "lz4"]

# Table caption
LATEX_CAPTION    = "Compression ratios across tools (higher is better)."

# Binaries / commands (adjust paths/flags as needed for your environment)
PIC_BINARY       = "./pic-v3.1"
TIC_BINARY       = "./epic-v3.1"
PIC_FLAGS        = ["-c", "-t", "1"]           # example flags
TIC_FLAGS        = ["-c", "-t", "1"]           # example flags

# Tool definitions: return a command list (argv) to run the compressor
TOOLS = {
    "gzip":  lambda infile, out: ["gzip", "-kf", infile],
    "bzip2": lambda infile, out: ["bzip2", "-kf", infile],
    "lz4":   lambda infile, out: ["lz4", "-kf", infile],
    "PIC":   lambda infile, out: [PIC_BINARY, *PIC_FLAGS, infile, out],
    "TIC":   lambda infile, out: [TIC_BINARY, *TIC_FLAGS, infile, out],
}

# Output extension per tool
EXT = { "gzip": ".gz", "bzip2": ".bz2", "lz4": ".lz4", "PIC": ".pic", "TIC": ".tic" }

# Output file names
CR_RESULTS_CSV = "cr_results.csv"
C_TIME_CSV     = "c_time_results.csv"
MEM_CSV        = "mem_results.csv"
LATEX_FILE     = "cr_table.tex"


def _try_import_psutil():
    try:
        import psutil  # type: ignore
        return psutil
    except Exception:
        return None


def measure(command):
    """
    Run a command (list) and return (runtime_s, avg_memory_MB).
    If 'psutil' is unavailable, only runtime is measured and memory is 0.0.
    """
    psutil = _try_import_psutil()
    start = time.time()
    proc  = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid   = proc.pid
    rss_samples = []
    if psutil is not None:
        while proc.poll() is None:
            try:
                p = psutil.Process(pid)
                rss_samples.append(p.memory_info().rss / (1024**2))
            except psutil.NoSuchProcess:
                break
            time.sleep(0.05)
    stdout, stderr = proc.communicate()
    runtime = round(time.time() - start, 3)
    avg_mb  = round(mean(rss_samples), 3) if rss_samples else 0.0
    return runtime, avg_mb, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


def build_latex_table(wide_df, tools_order, caption, tex_path=LATEX_FILE):
    """
    Generate LaTeX with:
      - Two header rows
      - \multirow for the first two columns
      - \multicolumn spanning the tool columns as "Compression Ratio"
    """
    n_tools = len(tools_order)
    # Column specification: l l then r repeated for each tool
    colspec = "ll" + "r"*n_tools

    # Header rows (use multirow for the first two columns spanning 2 rows)
    header1 = (
        r"\multirow{2}{*}{File Name} & "
        r"\multirow{2}{*}{File Size (MB)} & "
        r"\multicolumn{" + str(n_tools) + r"}{c}{Compression Ratio} \\ "
    )
    header2 = " & ".join([r"\multicolumn{1}{c}{" + t + "}" for t in tools_order]) + r" \\"

    # Body rows
    lines = []
    for _, row in wide_df.iterrows():
        right = " & ".join([str(row[t]) for t in tools_order])
        lines.append(f"{row['File Name']} & {row['File Size (MB)']} & {right} \\\\")

    latex = r"""\begin{table}[ht]
\centering
\begin{tabular}{""" + colspec + r"""}
\hline
""" + header1 + "\n" + header2 + r"""
\hline
""" + "\n".join(lines) + r"""
\hline
\end{tabular}
\caption{""" + caption + r"""}
\label{tab:cr}
\end{table}
"""
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)


def main():
    if not os.path.exists(INPUT_FILE_PATH):
        raise RuntimeError(f"Input file not found: {INPUT_FILE_PATH}")

    # Original size
    orig_bytes = os.path.getsize(INPUT_FILE_PATH)
    orig_mb    = round(orig_bytes / (1024**2), 3)

    # Run tools and collect sizes + metrics
    comp_sizes = {}
    metrics    = {}

    for name in TOOLS_ORDER:
        if name not in TOOLS:
            raise RuntimeError(f"Unknown tool in TOOLS_ORDER: {name}")

        out_path = INPUT_FILE_PATH + EXT[name]

        # Clean previous output
        try:
            os.remove(out_path)
        except OSError:
            pass

        cmd = TOOLS[name](INPUT_FILE_PATH, out_path)
        runtime_s, mem_mb, so, se = measure(cmd)

        if not os.path.exists(out_path):
            raise RuntimeError(f"{name} failed to produce {out_path}\nSTDERR:\n{se}")

        comp_bytes  = os.path.getsize(out_path)
        comp_factor = round(orig_bytes / comp_bytes, 3) if comp_bytes else 0.0

        comp_sizes[name] = comp_bytes
        metrics[name]    = {"runtime_s": runtime_s, "memory_MB": mem_mb}

    # Build wide-format CSV row (use INPUT_FILE_NAME explicitly)
    row = { "File Name": INPUT_FILE_NAME, "File Size (MB)": orig_mb }
    for t in TOOLS_ORDER:
        cb = comp_sizes.get(t, 0)
        row[t] = round(orig_bytes / cb, 3) if cb else ""

    wide_df = pd.DataFrame([row])
    wide_df = wide_df[["File Name","File Size (MB)"] + TOOLS_ORDER]
    wide_df.to_csv(CR_RESULTS_CSV, index=False)

    # Optional: write time/memory side tables
    pd.DataFrame(
        [{"Tool": t, "Runtime (s)": metrics[t]["runtime_s"]} for t in TOOLS_ORDER]
    ).to_csv(C_TIME_CSV, index=False)

    pd.DataFrame(
        [{"Tool": t, "Memory (MB)": metrics[t]["memory_MB"]} for t in TOOLS_ORDER]
    ).to_csv(MEM_CSV, index=False)

    # Generate LaTeX table from the fresh results
    build_latex_table(wide_df, TOOLS_ORDER, LATEX_CAPTION, tex_path=LATEX_FILE)

    print(f"Wrote: {CR_RESULTS_CSV}, {C_TIME_CSV}, {MEM_CSV}, {LATEX_FILE}")


if __name__ == "__main__":
    main()







# import time
# import psutil
# import subprocess
# from statistics import mean
# import os
# import pandas as pd

# # --- Configuration ---
# INPUT_FILE_PATH    = "../textFiles/test6.txt"
# INPUT_FILE_NAME    = "test6.txt"
# PIC_BINARY    = "./pic-v3.1"
# TIC_BINARY    = "./epic-v3.1"
# TIC_THREAD_FLAG   = ["-c", "-t", "1"]  # only used by TIC
# PIC_THREAD_FLAG   = ["-c", "-t", "1"]  # only used by PIC

# TOOLS = [
#     {
#         "name": "TIC",
#         "cmd": lambda infile, outfile: [TIC_BINARY, infile] + TIC_THREAD_FLAG + [outfile],
#         "ext": ".bin"
#     },
#     {
#         "name": "PIC",
#         "cmd": lambda infile, outfile: [PIC_BINARY, infile, PIC_THREAD_FLAG, outfile],
#         "ext": ".picbin"
#     },
#     {
#         "name": "gzip",
#         "cmd": lambda infile, _: ["gzip", "-kf", infile],
#         "ext": ".gz"
#     },
#     {
#         "name": "bzip2",
#         "cmd": lambda infile, _: ["bzip2", "-kf", infile],
#         "ext": ".bz2"
#     },
#     {
#         "name": "lz4",
#         "cmd": lambda infile, _: ["lz4", "-kf", infile],
#         "ext": ".lz4"
#     }
# ]

# # def measure(command):
# #     """Run a command, return (runtime_s, avg_memory_MB)."""
# #     start = time.time()
# #     proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
# #     pid  = proc.pid
# #     mem  = []
# #     while proc.poll() is None:
# #         try:
# #             p = psutil.Process(pid)
# #             mem.append(p.memory_info().rss / (1024**2))
# #         except psutil.NoSuchProcess:
# #             break
# #         time.sleep(0.05)
# #     proc.communicate()
# #     return time.time() - start, (mean(mem) if mem else 0)

# def measure(command):
#     """
#     Run a command (possibly nested list), return (runtime_s, avg_memory_MB).
#     Flattens any nested list in `command` so Popen always gets List[str].
#     """
#     # 1) Flatten
#     flat = []
#     for part in command:
#         if isinstance(part, (list, tuple)):
#             flat.extend(part)
#         else:
#             flat.append(part)
#     # 2) Run
#     start = time.time()
#     proc = subprocess.Popen(flat, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     pid  = proc.pid
#     mem  = []
#     while proc.poll() is None:
#         try:
#             p = psutil.Process(pid)
#             mem.append(p.memory_info().rss / (1024**2))
#         except psutil.NoSuchProcess:
#             break
#         time.sleep(0.05)
#     proc.communicate()
#     return time.time() - start, (mean(mem) if mem else 0)


# def main():
#     # Ensure input file exists
#     if not os.path.exists(INPUT_FILE_PATH):
#         raise RuntimeError(f"Input file not found: {INPUT_FILE_PATH}")

#     # Gather baseline sizes
#     orig_bytes = os.path.getsize(INPUT_FILE_PATH)
#     orig_mb    = orig_bytes / (1024**2)

#     records   = []
#     baseline  = {}

#     # Run each tool
#     for tool in TOOLS:
#         name    = tool["name"]
#         ext     = tool["ext"]
#         out     = INPUT_FILE_PATH + ext

#         # Clean up any previous output
#         if os.path.exists(out):
#             os.remove(out)

#         # Measure runtime & memory
#         cmd = tool["cmd"](INPUT_FILE_PATH, out)
#         # runtime_s, memory_mb = measure(tool["cmd"](INPUT_FILE_PATH, out))
#         runtime_s, memory_mb = measure(cmd)

#         # Verify output produced
#         if not os.path.exists(out):
#             raise RuntimeError(f"{name} failed to produce {out}")

#         # Compute compression factor
#         comp_bytes   = os.path.getsize(out)
#         comp_factor  = orig_bytes / comp_bytes

#         rec = {
#             "tool":        name,
#             "orig_MB":     round(orig_mb,    3),
#             "comp_factor": round(comp_factor,3),
#             "runtime_s":   round(runtime_s,  3),
#             "memory_MB":   round(memory_mb,  3)
#         }
#         records.append(rec)

#         # Save TIC as baseline for speedups
#         if name == "TIC":
#             baseline = rec

#     # Compute speedups relative to TIC
#     for rec in records:
#         if rec["tool"] != "TIC":
#             rec["time_speedup"] = round(rec["runtime_s"] / baseline["runtime_s"], 3)
#             rec["mem_speedup"]  = round(rec["memory_MB"] / baseline["memory_MB"], 3)
#         else:
#             rec["time_speedup"] = 1.0
#             rec["mem_speedup"]  = 1.0

#     # Build DataFrames mapped to output CSV names
#     df_map = {
#         "cr_results.csv":     pd.DataFrame(records)[["tool","orig_MB","comp_factor"]],
#         "c_time_results.csv": pd.DataFrame(records)[["tool","orig_MB","runtime_s","time_speedup"]],
#         "mem_results.csv":    pd.DataFrame(records)[["tool","orig_MB","memory_MB","mem_speedup"]],
#     }

#     # Write each CSV
#     for fname, df in df_map.items():
#         df.to_csv(fname, index=False)
#         print(f"Wrote {fname}")

#     # Cleanup generated files
#     for tool in TOOLS:
#         try:
#             os.remove(INPUT_FILE_PATH + tool["ext"])
#         except OSError:
#             pass

# if __name__ == "__main__":
#     main()
