import time
import psutil
import subprocess
from statistics import mean
import os
import pandas as pd

# --- Configuration ---
input_file_txt      = "test4.txt"
compressed_tic     = input_file_txt + ".tic"
compressed_pic     = input_file_txt + ".pic"
compressed_gzip     = input_file_txt + ".gz"
compressed_bzip2    = input_file_txt + ".bz2"
compressed_lz4      = input_file_txt + ".lz4"
tic_binary_compression = "./epic-v3.1"
pic_binary_compression = "./pic-v3.1"

# --- Measurement Helper ---
def measure(command):
    """Run a command, returning (runtime_s, avg_memory_MB)."""
    start = time.time()
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid = proc.pid
    mem_samples = []

    while proc.poll() is None:
        try:
            p = psutil.Process(pid)
            mem_samples.append(p.memory_info().rss / (1024**2))
        except psutil.NoSuchProcess:
            break
        time.sleep(0.05)

    proc.communicate()
    runtime = time.time() - start
    avg_mem = mean(mem_samples) if mem_samples else 0
    return runtime, avg_mem

def main():
    # 1.1) PIC compression
    pic_time, pic_mem = measure([
        pic_binary_compression,
        input_file_txt,
        "-c", "-t", "1",
        compressed_pic
    ])
    if not os.path.exists(compressed_pic):
        raise RuntimeError(f"PIC output not found: {compressed_pic}")
    
    # 1) TIC compression
    tic_time, tic_mem = measure([
        tic_binary_compression,
        input_file_txt,
        "-c", "-t", "1",
        compressed_tic
    ])
    if not os.path.exists(compressed_tic):
        raise RuntimeError(f"TIC output not found: {compressed_tic}")

    # 2) gzip compression
    gzip_time, gzip_mem = measure(["gzip", "-kf", input_file_txt])
    if not os.path.exists(compressed_gzip):
        raise RuntimeError(f"gzip output not found: {compressed_gzip}")

    # 3) bzip2 compression
    bzip2_time, bzip2_mem = measure(["bzip2", "-kf", input_file_txt])
    if not os.path.exists(compressed_bzip2):
        raise RuntimeError(f"bzip2 output not found: {compressed_bzip2}")

    # 4) lz4 compression
    lz4_time, lz4_mem = measure(["lz4", "-kf", input_file_txt])
    if not os.path.exists(compressed_lz4):
        raise RuntimeError(f"lz4 output not found: {compressed_lz4}")

    # Compute sizes & factors
    orig_size     = os.path.getsize(input_file_txt)
    tic_size     = os.path.getsize(compressed_tic)
    pic_size     = os.path.getsize(compressed_pic)
    gzip_size     = os.path.getsize(compressed_gzip)
    bzip2_size    = os.path.getsize(compressed_bzip2)
    lz4_size      = os.path.getsize(compressed_lz4)
    orig_size_MB  = orig_size / (1024**2)

    tic_factor   = orig_size / tic_size
    pic_factor   = orig_size / pic_size
    gzip_factor   = orig_size / gzip_size
    bzip2_factor  = orig_size / bzip2_size
    lz4_factor    = orig_size / lz4_size

    # Compute runtime enhancements vs TIC
    pic_speedup  = pic_time / tic_time
    gzip_speedup  = gzip_time / tic_time
    bzip2_speedup = bzip2_time / tic_time
    lz4_speedup   = lz4_time / tic_time

    # Compute memory enhancements vs TIC
    pic_mem_speedup  = pic_mem  / tic_mem
    gzip_mem_speedup  = gzip_mem  / tic_mem
    bzip2_mem_speedup = bzip2_mem / tic_mem
    lz4_mem_speedup   = lz4_mem   / tic_mem

    # Prepare CSV data
    results_cr = [{
        "File Name": input_file_txt,
        "Original Size (MB)": round(orig_size_MB, 3),
        "TIC": round(tic_factor, 3),
        "PIC": round(pic_factor, 3),
        "gzip": round(gzip_factor, 3),
        "bzip2": round(bzip2_factor, 3),
        "lz4": round(lz4_factor, 3)
    }]

    results_time = [{
        "File Name": input_file_txt,
        "Original Size (MB)": round(orig_size_MB, 3),
        "TIC time (s)": round(tic_time, 3),
        "PIC/TIC": round(pic_speedup, 3),
        "gzip/TIC": round(gzip_speedup, 3),
        "bzip2/TIC": round(bzip2_speedup, 3),
        "lz4/TIC": round(lz4_speedup, 3)
    }]

    results_mem = [{
        "File Name": input_file_txt,
        "Original Size (MB)": round(orig_size_MB, 3),
        "TIC MEM (MB)": round(tic_mem, 3),
        "PIC/TIC": round(pic_mem_speedup, 3),
        "gzip/TIC": round(gzip_mem_speedup, 3),
        "bzip2/TIC": round(bzip2_mem_speedup, 3),
        "lz4/TIC": round(lz4_mem_speedup, 3)
    }]

    # Write CSVs
    pd.DataFrame(results_cr).to_csv("cr_results.csv", index=False)
    pd.DataFrame(results_time).to_csv("c_time_results.csv", index=False)
    pd.DataFrame(results_mem).to_csv("mem_results.csv", index=False)
    print("Wrote: cr_results.csv, c_time_results.csv, mem_results.csv")

    # Clean up compressed files
    for f in [compressed_gzip, compressed_bzip2, compressed_lz4, compressed_tic, compressed_pic]:
        try:
            os.remove(f)
        except OSError:
            pass

if __name__ == "__main__":
    main()








