import time
import psutil
import subprocess
from statistics import mean
import os
import pandas as pd

# --- Configuration ---
INPUT_FILE    = "test5.txt"
TIC_FILE    = INPUT_FILE + ".tic"
PIC_FILE    = INPUT_FILE + ".pic"
PIC_BINARY    = "./pic-v3.1"
TIC_BINARY    = "./epic-v3.1"
THREAD_FLAG   = ["-t", "1"]      # for both PIC (-l uses -t) and TIC search
TIC_THREAD_FLAG   = ["-t", "1"]      # for TIC search
PIC_THREAD_FLAG   = ["-t", "1"]      # for PIC search
SEARCH_STRING = "him"        # your search term here
TIC_SEARCH_STRING = "\"him\""        # your search term here

# --- Tool Definitions ---
COMP_TOOLS = [
    {
        "name": "PIC",
        "cmd": lambda infile, outfile: [PIC_BINARY, infile, "-c"] + THREAD_FLAG + [outfile],
        "ext": ".pic"
    }, 
    {
        "name": "TIC",
        "cmd": lambda infile, outfile: [TIC_BINARY, infile, "-c"] + THREAD_FLAG + [outfile],
        "ext": ".tic"
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

SEARCH_TOOLS = [
    {
        "name": "TIC",
        "cmd": lambda infile, outfile: [TIC_BINARY, TIC_FILE, "-l"] + THREAD_FLAG + [outfile, TIC_SEARCH_STRING],
        "ext": ".tic"
    },
    {
        "name": "PIC",
        "cmd": lambda infile, outfile: [PIC_BINARY, PIC_FILE, "-l"] + THREAD_FLAG + [outfile, TIC_SEARCH_STRING],
        "ext": ".pic"
    },
    {
        "name": "gzip",
        "decompress": lambda infile: ["gzip", "-d", "-k", infile],
        "search":    lambda txt: ["grep", "-c", SEARCH_STRING, txt],
        "ext":       ".gz"
    },
    {
        "name": "bzip2",
        "decompress": lambda infile: ["bzip2", "-d", "-k", infile],
        "search":    lambda txt: ["grep", "-c", SEARCH_STRING, txt],
        "ext":       ".bz2"
    },
    {
        "name": "lz4",
        "decompress": lambda infile: ["lz4", "-d", "-k", infile],
        "search":    lambda txt: ["grep", "-c", SEARCH_STRING, txt],
        "ext":       ".lz4"
    }
]

# --- Helper ---
def measure(command):
    """Flatten nested lists, run a command, return (runtime_s, avg_memory_MB)."""
    flat = []
    for part in command:
        if isinstance(part, (list, tuple)):
            flat.extend(part)
        else:
            flat.append(part)
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

# --- Compression Phase ---
def run_compression():
    orig_bytes = os.path.getsize(INPUT_FILE)
    orig_mb    = orig_bytes / (1024**2)
    records    = []
    baseline   = {}

    for tool in COMP_TOOLS:
        name = tool["name"]
        ext  = tool["ext"]
        out  = INPUT_FILE + ext
        if os.path.exists(out): os.remove(out)

        rt, mem = measure(tool["cmd"](INPUT_FILE, out))
        if not os.path.exists(out):
            raise RuntimeError(f"{name} failed to produce {out}")

        comp_bytes  = os.path.getsize(out)
        comp_factor = orig_bytes / comp_bytes

        rec = {
            "tool":        name,
            "orig_MB":     round(orig_mb,    3),
            "comp_factor": round(comp_factor,3),
            "runtime_s":   round(rt,        3),
            "memory_MB":   round(mem,       3)
        }
        records.append(rec)
        if name == "TIC":
            baseline = rec

    # compute speedups vs TIC
    for rec in records:
        if rec["tool"] != "TIC":
            rec["time_speedup"] = round(rec["runtime_s"] / baseline["runtime_s"], 3)
            rec["mem_speedup"]  = round(rec["memory_MB"] / baseline["memory_MB"], 3)
        else:
            rec["time_speedup"] = rec["mem_speedup"] = 1.0

    # write CSVs
    df_map = {
        "cr_results.csv":     pd.DataFrame(records)[["tool","orig_MB","comp_factor"]],
        "c_time_results.csv": pd.DataFrame(records)[["tool","orig_MB","runtime_s","time_speedup"]],
        "mem_results.csv":    pd.DataFrame(records)[["tool","orig_MB","memory_MB","mem_speedup"]],
    }
    for fname, df in df_map.items():
        df.to_csv(fname, index=False)
        print(f"Wrote {fname}")

# --- Search Phase ---
def run_search():
    records = []
    for tool in SEARCH_TOOLS:
        name = tool["name"]
        ext  = tool["ext"]
        infile = INPUT_FILE + ext
        if not os.path.exists(infile):
            raise RuntimeError(f"Compressed file not found for search: {infile}")

        if name in ("PIC","TIC"):
            print ("test1")
            out = f"search_{name}.txt"
            if os.path.exists(out): os.remove(out)
            rt, mem = measure(tool["cmd"](infile, out))
            records.append({"tool": name, "runtime_s": round(rt,3), "memory_MB": round(mem,3)})
        else:
            print ("test2")
            # decompress + grep
            # rt_d, mem_d = measure(tool["decompress"](infile))
            # rt_s, mem_s = measure(tool["search"](INPUT_FILE))
            # records.append({
            #     "tool": name,
            #     "runtime_s": round(rt_d + rt_s,3),
            #     "memory_MB": round(max(mem_d,mem_s),3)
            # })

    df = pd.DataFrame(records)[["tool","runtime_s","memory_MB"]]
    df.to_csv("search_results.csv", index=False)
    print("Wrote search_results.csv")

# --- Main ---
def main():
    # print (TIC_FILE)

    run_compression()
    run_search()
    # cleanup
    for tool in COMP_TOOLS:
        try: os.remove(INPUT_FILE + tool["ext"])
        except: pass
    for name in ("PIC","TIC"):
        try: os.remove(f"search_{name}.txt")
        except: pass

if __name__ == "__main__":
    main()
