import time
import psutil
import subprocess
from statistics import mean
import os
import pandas as pd

# --- Configuration ---
input_file_txt = "test4.txt"
compressed_epic = input_file_txt + ".bin"
compressed_gzip = input_file_txt + ".gz"
cpp_binary_compression = "./epic-v3.1"

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
    cpp_time, cpp_mem = measure([
        cpp_binary_compression, 
        input_file_txt, 
        "-c", 
        "-t", "1", 
        compressed_epic
    ])

    # 2) gzip compression
    gzip_time, gzip_mem = measure([
        "gzip", "-k", input_file_txt
    ])

    # 3) Compute sizes & factors
    orig_size = os.path.getsize(input_file_txt)
    epic_size = os.path.getsize(compressed_epic)
    gzip_size = os.path.getsize(compressed_gzip)

    epic_factor = orig_size / epic_size
    gzip_factor = orig_size / gzip_size

    # 4) Collect results
    results = [
        {
            "tool": "EPIC",
            "runtime_s": cpp_time,
            "memory_MB": cpp_mem,
            "compression_factor": epic_factor
        },
        {
            "tool": "gzip",
            "runtime_s": gzip_time,
            "memory_MB": gzip_mem,
            "compression_factor": gzip_factor
        }
    ]

    # 5) Save to CSV
    df = pd.DataFrame(results)
    df.to_csv("compression_results.csv", index=False)
    print("Results written to compression_results.csv")

    # Clean up if needed
    if os.path.exists(compressed_gzip):
        os.remove(compressed_gzip)
        
    if os.path.exists(compressed_epic):    
        os.remove(compressed_epic)

if __name__ == "__main__":
    main()





# import time
# import psutil
# import subprocess
# from statistics import mean
# import shutil
# import os

# input_file_txt = "test3.txt"
# compressed_epic = input_file_txt + ".bin"
# compressed_gzip = input_file_txt + ".gz"
# cpp_binary_compression = "./epic-v3.1"

# def measure(command, label):
#     print(f"\nRunning: {label}")
#     start_time = time.time()

#     process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     pid = process.pid
#     mem_usage = []

#     while process.poll() is None:
#         try:
#             p = psutil.Process(pid)
#             mem_usage.append(p.memory_info().rss / 1024 / 1024)  # Convert bytes to MB
#         except psutil.NoSuchProcess:
#             break
#         time.sleep(0.05)

#     stdout, stderr = process.communicate()
#     end_time = time.time()

#     runtime = end_time - start_time
#     average_memory = mean(mem_usage) if mem_usage else 0

#     print(f"{label} finished.")
#     print(f"Runtime: {runtime:.3f} seconds")
#     print(f"Average Memory: {average_memory:.2f} MB")

#     return runtime, average_memory

# def main():

#     # # Ensure fresh input file for both methods
#     # shutil.copyfile(input_file, "input_cpp.txt")
#     # shutil.copyfile(input_file, "input_gzip.txt")

#     # 1. Run C++ binary
#     print("=== C++ Compression ===")
#     measure([cpp_binary_compression, input_file_txt, "-c", "-t", "1", compressed_epic], "C++ Compression")

#     # 2. Run gzip compression
#     print("\n=== gzip Compression ===")
#     measure(["gzip", "-k", input_file_txt], "gzip Compression")  # -k keeps original

#     # 1) get sizes
#     orig_size = os.path.getsize(input_file_txt)           # bytes
#     epic_size = os.path.getsize(compressed_epic)          # bytes, after epic run
#     gzip_size = os.path.getsize(compressed_gzip)          # bytes, after gzip run

#     # 2) compute factors
#     epic_factor = orig_size / epic_size
#     gzip_factor = orig_size / gzip_size

#     # 3) compute percentages
#     epic_pct   = (epic_size / orig_size) * 100
#     gzip_pct   = (gzip_size / orig_size) * 100

#     print(f"Original size: {orig_size:,} bytes")
#     print(f"EPIC compressed size: {epic_size:,} bytes → factor={epic_factor:.2f}×, {epic_pct:.1f}%")
#     print(f"gzip compressed size: {gzip_size:,} bytes → factor={gzip_factor:.2f}×, {gzip_pct:.1f}%")

#     # Clean up if needed
#     if os.path.exists(compressed_gzip):
#         os.remove(compressed_gzip)
        
#     if os.path.exists(compressed_epic):    
#         os.remove(compressed_epic)
    
        

# if __name__ == "__main__":
#     main()
