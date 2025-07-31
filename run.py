import time
import psutil
import subprocess
from statistics import mean
import os
import pandas as pd

# --- Configuration ---
input_file_txt      = "test4.txt"
compressed_epic     = input_file_txt + ".bin"
compressed_gzip     = input_file_txt + ".gz"
compressed_bzip2    = input_file_txt + ".bz2"
compressed_lz4      = input_file_txt + ".lz4"
epic_binary_compression = "./epic-v3.1"

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
    # 1) EPIC compression
    epic_time, epic_mem = measure([
        epic_binary_compression,
        input_file_txt,
        "-c", "-t", "1",
        compressed_epic
    ])
    if not os.path.exists(compressed_epic):
        raise RuntimeError(f"EPIC output not found: {compressed_epic}")

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
    epic_size     = os.path.getsize(compressed_epic)
    gzip_size     = os.path.getsize(compressed_gzip)
    bzip2_size    = os.path.getsize(compressed_bzip2)
    lz4_size      = os.path.getsize(compressed_lz4)
    orig_size_MB  = orig_size / (1024**2)

    epic_factor   = orig_size / epic_size
    gzip_factor   = orig_size / gzip_size
    bzip2_factor  = orig_size / bzip2_size
    lz4_factor    = orig_size / lz4_size

    # Compute runtime enhancements vs EPIC
    gzip_speedup  = gzip_time / epic_time
    bzip2_speedup = bzip2_time / epic_time
    lz4_speedup   = lz4_time / epic_time

    # Compute memory enhancements vs EPIC
    gzip_mem_speedup  = gzip_mem  / epic_mem
    bzip2_mem_speedup = bzip2_mem / epic_mem
    lz4_mem_speedup   = lz4_mem   / epic_mem

    # Prepare CSV data
    results_cr = [{
        "File Name": input_file_txt,
        "Original Size (MB)": round(orig_size_MB, 3),
        "EPIC": round(epic_factor, 3),
        "gzip": round(gzip_factor, 3),
        "bzip2": round(bzip2_factor, 3),
        "lz4": round(lz4_factor, 3)
    }]

    results_time = [{
        "File Name": input_file_txt,
        "Original Size (MB)": round(orig_size_MB, 3),
        "EPIC time (s)": round(epic_time, 3),
        "gzip/EPIC": round(gzip_speedup, 3),
        "bzip2/EPIC": round(bzip2_speedup, 3),
        "lz4/EPIC": round(lz4_speedup, 3)
    }]

    results_mem = [{
        "File Name": input_file_txt,
        "Original Size (MB)": round(orig_size_MB, 3),
        "EPIC MEM (MB)": round(epic_mem, 3),
        "gzip/EPIC": round(gzip_mem_speedup, 3),
        "bzip2/EPIC": round(bzip2_mem_speedup, 3),
        "lz4/EPIC": round(lz4_mem_speedup, 3)
    }]

    # Write CSVs
    pd.DataFrame(results_cr).to_csv("cr_results.csv", index=False)
    pd.DataFrame(results_time).to_csv("c_time_results.csv", index=False)
    pd.DataFrame(results_mem).to_csv("mem_results.csv", index=False)
    print("Wrote: cr_results.csv, c_time_results.csv, mem_results.csv")

    # Clean up compressed files
    for f in [compressed_gzip, compressed_bzip2, compressed_lz4, compressed_epic]:
        try:
            os.remove(f)
        except OSError:
            pass

if __name__ == "__main__":
    main()














# import time
# import psutil
# import subprocess
# from statistics import mean
# import os
# import pandas as pd

# # --- Configuration ---
# input_file_txt = "test4.txt"
# compressed_epic = input_file_txt + ".bin"
# compressed_gzip = input_file_txt + ".gz"
# epic_binary_compression = "./epic-v3.1"

# # --- Measurement Helper ---
# def measure(command):
#     """Run a command, returning (runtime_s, avg_memory_MB)."""
#     start = time.time()
#     proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     pid = proc.pid
#     mem_samples = []

#     while proc.poll() is None:
#         try:
#             p = psutil.Process(pid)
#             mem_samples.append(p.memory_info().rss / (1024**2))
#         except psutil.NoSuchProcess:
#             break
#         time.sleep(0.05)

#     proc.communicate()
#     runtime = time.time() - start
#     avg_mem = mean(mem_samples) if mem_samples else 0
#     return runtime, avg_mem

# def main():
#     # EPIC compression
#     epic_time, epic_mem = measure([
#         epic_binary_compression, 
#         input_file_txt, 
#         "-c", 
#         "-t", "1", 
#         compressed_epic
#     ])
#     if not os.path.exists(compressed_epic):
#         raise RuntimeError(f"EPIC output not found: {compressed_epic}")

#     # gzip compression
#     gzip_time, gzip_mem = measure([
#         "gzip", "-k", input_file_txt
#     ])
#     if not os.path.exists(compressed_gzip):
#         raise RuntimeError(f"gzip output not found: {compressed_gzip}")

#     # Compute sizes & factors
#     orig_size = os.path.getsize(input_file_txt)
#     epic_size = os.path.getsize(compressed_epic)
#     gzip_size = os.path.getsize(compressed_gzip)
#     orig_size_MB = round(os.path.getsize(input_file_txt) / (1024 ** 2), 3)

#     epic_factor = round(orig_size / epic_size, 3)
#     gzip_factor = round(orig_size / gzip_size, 3)

#     # Compute runtime and speedup
#     gzip_t_over_epic = round(gzip_time / epic_time, 3)

#     # Compute memory utilization performance
#     gzip_mem_over_epic = round(gzip_mem / epic_mem, 3)

#     #### Collect results ###

#     # Compression Ratio
#     results_cr = [
#         {
#             "File Name": input_file_txt,
#             "Original Size (MB)": orig_size_MB,
#             "epic": epic_factor,
#             "gzip": gzip_factor
#         }
#     ]

#     # Compression Time
#     results_c_time = [
#         {
#             "File Name": input_file_txt,
#             "Original Size (MB)": orig_size_MB,
#             "epic": round(epic_time, 3),
#             "gzip/epic": gzip_t_over_epic
#         }
#     ]
    
#     # Memory Utilization
#     results_mem_util = [
#         {
#             "File Name": input_file_txt,
#             "Original Size (MB)": orig_size_MB,
#             "epic (MB)": round(epic_mem, 3),
#             "gzip/epic": gzip_mem_over_epic
#         }
#     ]

#     ### Save to CSV files ###

#     # Compression Ratio
#     df = pd.DataFrame(results_cr)
#     df.to_csv("cr_results.csv", index=False)
#     print("Compression ratio (CR) results written to cr_results.csv")

#     # Runtime and speedup
#     df = pd.DataFrame(results_c_time)
#     df.to_csv("c_time_results.csv", index=False)
#     print("Runtime and speedup results written to c_time_results.csv")

#     # Memory utilization
#     df = pd.DataFrame(results_mem_util)
#     df.to_csv("mem_results.csv", index=False)
#     print("Memory utilization results written to mem_results.csv")

#     # Clean up if needed
#     if os.path.exists(compressed_gzip):
#         os.remove(compressed_gzip)
        
#     if os.path.exists(compressed_epic):    
#         os.remove(compressed_epic)

# if __name__ == "__main__":
#     main()
