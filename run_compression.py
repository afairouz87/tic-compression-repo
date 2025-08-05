import time
import psutil
import subprocess
from statistics import mean
import os
import pandas as pd

# --- Configuration ---
INPUT_FILE    = "test4.txt"
PIC_BINARY    = "./pic-v3.1"
TIC_BINARY    = "./epic-v3.1"
TIC_THREAD_FLAG   = ["-c", "-t", "1"]  # only used by TIC
PIC_THREAD_FLAG   = ["-c", "-t", "1"]  # only used by TIC

TOOLS = [
    {
        "name": "TIC",
        "cmd": lambda infile, outfile: [TIC_BINARY, infile] + TIC_THREAD_FLAG + [outfile],
        "ext": ".bin"
    },
    {
        "name": "PIC",
        "cmd": lambda infile, outfile: [PIC_BINARY, infile, PIC_THREAD_FLAG, outfile],
        "ext": ".picbin"
    },
    {
        "name": "gzip",
        "cmd": lambda infile, _: ["gzip", "-kf", infile],
        "ext": ".gz"
    },
    {
        "name": "bzip2",
        "cmd": lambda infile, _: ["bzip2", "-kf", infile],
        "ext": ".bz2"
    },
    {
        "name": "lz4",
        "cmd": lambda infile, _: ["lz4", "-kf", infile],
        "ext": ".lz4"
    }
]

# def measure(command):
#     """Run a command, return (runtime_s, avg_memory_MB)."""
#     start = time.time()
#     proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

def measure(command):
    """
    Run a command (possibly nested list), return (runtime_s, avg_memory_MB).
    Flattens any nested list in `command` so Popen always gets List[str].
    """
    # 1) Flatten
    flat = []
    for part in command:
        if isinstance(part, (list, tuple)):
            flat.extend(part)
        else:
            flat.append(part)
    # 2) Run
    start = time.time()
    proc = subprocess.Popen(flat, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid  = proc.pid
    mem  = []
    while proc.poll() is None:
        try:
            p = psutil.Process(pid)
            mem.append(p.memory_info().rss / (1024**2))
        except psutil.NoSuchProcess:
            break
        time.sleep(0.05)
    proc.communicate()
    return time.time() - start, (mean(mem) if mem else 0)


def main():
    # Ensure input file exists
    if not os.path.exists(INPUT_FILE):
        raise RuntimeError(f"Input file not found: {INPUT_FILE}")

    # Gather baseline sizes
    orig_bytes = os.path.getsize(INPUT_FILE)
    orig_mb    = orig_bytes / (1024**2)

    records   = []
    baseline  = {}

    # Run each tool
    for tool in TOOLS:
        name    = tool["name"]
        ext     = tool["ext"]
        out     = INPUT_FILE + ext

        # Clean up any previous output
        if os.path.exists(out):
            os.remove(out)

        # Measure runtime & memory
        cmd = tool["cmd"](INPUT_FILE, out)
        # runtime_s, memory_mb = measure(tool["cmd"](INPUT_FILE, out))
        runtime_s, memory_mb = measure(cmd)

        # Verify output produced
        if not os.path.exists(out):
            raise RuntimeError(f"{name} failed to produce {out}")

        # Compute compression factor
        comp_bytes   = os.path.getsize(out)
        comp_factor  = orig_bytes / comp_bytes

        rec = {
            "tool":        name,
            "orig_MB":     round(orig_mb,    3),
            "comp_factor": round(comp_factor,3),
            "runtime_s":   round(runtime_s,  3),
            "memory_MB":   round(memory_mb,  3)
        }
        records.append(rec)

        # Save TIC as baseline for speedups
        if name == "TIC":
            baseline = rec

    # Compute speedups relative to TIC
    for rec in records:
        if rec["tool"] != "TIC":
            rec["time_speedup"] = round(rec["runtime_s"] / baseline["runtime_s"], 3)
            rec["mem_speedup"]  = round(rec["memory_MB"] / baseline["memory_MB"], 3)
        else:
            rec["time_speedup"] = 1.0
            rec["mem_speedup"]  = 1.0

    # Build DataFrames mapped to output CSV names
    df_map = {
        "cr_results.csv":     pd.DataFrame(records)[["tool","orig_MB","comp_factor"]],
        "c_time_results.csv": pd.DataFrame(records)[["tool","orig_MB","runtime_s","time_speedup"]],
        "mem_results.csv":    pd.DataFrame(records)[["tool","orig_MB","memory_MB","mem_speedup"]],
    }

    # Write each CSV
    for fname, df in df_map.items():
        df.to_csv(fname, index=False)
        print(f"Wrote {fname}")

    # Cleanup generated files
    for tool in TOOLS:
        try:
            os.remove(INPUT_FILE + tool["ext"])
        except OSError:
            pass

if __name__ == "__main__":
    main()
