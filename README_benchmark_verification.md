# Benchmark Suite Verification Plan

This README provides a script-by-script verification checklist for the benchmark suite.

## Scripts covered

- `benchmark_utils.py`
- `run_compression.py`
- `run_decompression.py`
- `run_search.py`
- `run_search_replace.py`
- `run_parallel_benchmarks.py`

---

## 1. Verification goals

We verify:

1. **Functional correctness**
   - each script runs
   - required files are created
   - commands are formed correctly
   - compressed/decompressed/search outputs are valid

2. **Formula correctness**
   - every CSV value matches the agreed formula
   - TIC is the absolute baseline where required
   - relative values are computed correctly

3. **Cross-script consistency**
   - later scripts correctly reuse outputs from earlier scripts
   - file naming and CSV column naming are consistent

4. **Reproducibility**
   - repeated runs do not silently corrupt outputs
   - setup compression is not mixed into unrelated benchmark timing

---

## 2. Verification order

Verify in this order:

1. `benchmark_utils.py`
2. `run_compression.py`
3. `run_decompression.py`
4. `run_search.py`
5. `run_search_replace.py`
6. `run_parallel_benchmarks.py`
7. full cross-script consistency audit

---

## 3. Test environment preparation

### 3.1 Verify binaries

```bash
./epic-v3.1
./pic-v3.1
gzip --version
bzip2 --version
lz4 --version
lbzip2 --version
zgrep --version
bzgrep --version
```

Expected:
- `epic-v3.1` and `pic-v3.1` print usage text when run without arguments
- all other tools report their version successfully

### 3.2 Verify input files

```bash
ls -lh datasets/f1.txt datasets/f2.txt datasets/f3.txt datasets/f4.txt datasets/f5.txt datasets/f6.txt datasets/f7.txt datasets/f8.txt datasets/f9.txt datasets/f10.txt
```

### 3.3 Clean old generated results

```bash
rm -rf results/raw results/tables results/figures results/logs results/tmp
mkdir -p results/raw results/tables results/figures results/logs results/tmp
```

---

## 4. Verify `benchmark_utils.py`

### 4.1 Quick import test

```bash
python3 - <<'PY'
import benchmark_utils
print("benchmark_utils import: OK")
PY
```

### 4.2 Check extensions and paths

```bash
python3 - <<'PY'
from benchmark_utils import get_tool_extension, get_compressed_path
print(get_tool_extension("TIC"))
print(get_tool_extension("PIC"))
print(get_tool_extension("gzip"))
print(get_tool_extension("bzip2"))
print(get_tool_extension("lz4"))
print(get_compressed_path("datasets/f1.txt", "TIC"))
print(get_compressed_path("datasets/f1.txt", "gzip"))
PY
```

### 4.3 Check entropy helper on a tiny file

```bash
printf 'AAAAAA' > /tmp/test_entropy_a.txt
printf 'ABABABAB' > /tmp/test_entropy_b.txt

python3 - <<'PY'
from benchmark_utils import compute_file_entropy
print("A entropy =", compute_file_entropy("/tmp/test_entropy_a.txt"))
print("B entropy =", compute_file_entropy("/tmp/test_entropy_b.txt"))
PY
```

Expected:
- entropy of `AAAAAA` is close to `0`
- entropy of `ABABABAB` is greater than the first file

### 4.4 Check LaTeX builders

```bash
python3 - <<'PY'
import pandas as pd
from benchmark_utils import build_grouped_latex_table, build_simple_latex_table

df1 = pd.DataFrame([{
    "File Name": "f1.txt",
    "Original Size (MB)": 50,
    "TIC": "2.00",
    "PIC": "1.90",
    "gzip": "2.70",
    "bzip2": "3.80",
    "lz4": "1.60",
}])

build_grouped_latex_table(
    df=df1,
    tex_path="/tmp/test_grouped.tex",
    caption="Test grouped",
    label="tab:test_grouped",
    group_headers=[("File Name",1),("Original Size (MB)",1),("CR",5)],
    column_headers=["File Name","Original Size (MB)","TIC","PIC","gzip","bzip2","lz4"],
    align_spec="ccccccc",
)

df2 = pd.DataFrame([{
    "File Name": "f1.txt",
    "Plain Text": "4.500",
    "TIC": "6.200",
    "PIC": "6.100",
    "gzip": "7.900",
    "bzip2": "7.950",
    "lz4": "6.800",
}])

build_simple_latex_table(
    df=df2,
    tex_path="/tmp/test_simple.tex",
    caption="Test simple",
    label="tab:test_simple",
    column_headers=["File Name","Plain Text","TIC","PIC","gzip","bzip2","lz4"],
    align_spec="ccccccc",
)

print("Created:", "/tmp/test_grouped.tex", "/tmp/test_simple.tex")
PY
```

### 4.5 Inspect generated test LaTeX

```bash
sed -n '1,120p' /tmp/test_grouped.tex
sed -n '1,120p' /tmp/test_simple.tex
```

### 4.6 Check plotting helpers

```bash
python3 - <<'PY'
import pandas as pd
from benchmark_utils import plot_parallel_time, plot_parallel_memory, plot_parallel_search

pd.DataFrame({
    "Threads": [1,2,4],
    "TIC Compression": [10,7,5],
    "TIC Decompression": [4,3,2],
    "lbzip2 Compression": [8,6,4],
    "lbzip2 Decompression": [5,4,3],
}).to_csv("/tmp/parallel_time_test.csv", index=False)

pd.DataFrame({
    "Threads": [1,2,4],
    "TIC Compression": [100,105,110],
    "TIC Decompression": [90,95,100],
    "lbzip2 Compression": [80,90,100],
    "lbzip2 Decompression": [85,92,99],
}).to_csv("/tmp/parallel_memory_test.csv", index=False)

pd.DataFrame({
    "Threads": [1,2,4],
    "TIC Search": [1.0,0.7,0.4],
}).to_csv("/tmp/parallel_search_test.csv", index=False)

plot_parallel_time("/tmp/parallel_time_test.csv", "/tmp/parallel_time_test.png")
plot_parallel_memory("/tmp/parallel_memory_test.csv", "/tmp/parallel_memory_test.png")
plot_parallel_search("/tmp/parallel_search_test.csv", "/tmp/parallel_search_test.png")
print("Created plot test files.")
PY
```

---

## 5. Verify `run_compression.py`

### 5.1 Run script

```bash
python3 run_compression.py
```

### 5.2 Check output files exist

```bash
ls -lh results/raw/cr_results.csv results/tables/cr_table.tex results/raw/compression_time_results.csv results/tables/compression_time_table.tex
```

### 5.3 Check compressed files exist

```bash
ls -lh datasets/f1.txt.tic datasets/f1.txt.pic datasets/f1.txt.gz datasets/f1.txt.bz2 datasets/f1.txt.lz4
```

### 5.4 Inspect CSV headers

```bash
python3 - <<'PY'
import pandas as pd
print(pd.read_csv("results/raw/cr_results.csv").columns.tolist())
print(pd.read_csv("results/raw/compression_time_results.csv").columns.tolist())
PY
```

### 5.5 Spot-check first few rows

```bash
python3 - <<'PY'
import pandas as pd
print(pd.read_csv("results/raw/cr_results.csv").head())
print(pd.read_csv("results/raw/compression_time_results.csv").head())
PY
```

### 5.6 Manual CR verification for `f1.txt`

```bash
python3 - <<'PY'
from pathlib import Path
orig = Path("datasets/f1.txt").stat().st_size
for ext, name in [(".tic","TIC"),(".pic","PIC"),(".gz","gzip"),(".bz2","bzip2"),(".lz4","lz4")]:
    comp = Path("datasets/f1.txt" + ext).stat().st_size
    print(name, round(orig/comp, 2))
PY
```

### 5.7 Inspect generated LaTeX

```bash
sed -n '1,200p' results/tables/cr_table.tex
sed -n '1,200p' results/tables/compression_time_table.tex
```

---

## 6. Verify `run_decompression.py`

### 6.1 Run script

```bash
python3 run_decompression.py
```

### 6.2 Check output files exist

```bash
ls -lh results/raw/decompression_time_results.csv results/tables/decompression_time_table.tex
```

### 6.3 Inspect CSV header and first rows

```bash
python3 - <<'PY'
import pandas as pd
df = pd.read_csv("results/raw/decompression_time_results.csv")
print(df.columns.tolist())
print(df.head())
PY
```

### 6.4 Inspect generated LaTeX

```bash
sed -n '1,200p' results/tables/decompression_time_table.tex
```

### 6.5 Check setup regeneration behavior

Delete one compressed file and rerun:

```bash
rm -f datasets/f1.txt.tic
python3 run_decompression.py
ls -lh datasets/f1.txt.tic
```

Expected:
- `f1.txt.tic` is regenerated
- the script still completes successfully

---

## 7. Verify `run_search.py`

### 7.1 Run script

```bash
python3 run_search.py
```

### 7.2 Check output files exist

```bash
ls -lh results/raw/lookup_time_no_recompression_results.csv results/tables/lookup_time_no_recompression_table.tex results/raw/lookup_time_with_recompression_results.csv results/tables/lookup_time_with_recompression_table.tex results/raw/lookup_memory_results.csv results/tables/lookup_memory_table.tex results/raw/lookup_time_streaming_results.csv results/tables/lookup_time_streaming_table.tex results/raw/entropy_results.csv results/tables/entropy_table.tex
```

### 7.3 Inspect CSV headers

```bash
python3 - <<'PY'
import pandas as pd
for f in [
    "results/raw/lookup_time_no_recompression_results.csv",
    "results/raw/lookup_time_with_recompression_results.csv",
    "results/raw/lookup_memory_results.csv",
    "results/raw/lookup_time_streaming_results.csv",
    "results/raw/entropy_results.csv",
]:
    df = pd.read_csv(f)
    print(f, "->", df.columns.tolist())
PY
```

### 7.4 Inspect first rows

```bash
python3 - <<'PY'
import pandas as pd
for f in [
    "results/raw/lookup_time_no_recompression_results.csv",
    "results/raw/lookup_time_with_recompression_results.csv",
    "results/raw/lookup_memory_results.csv",
    "results/raw/lookup_time_streaming_results.csv",
    "results/raw/entropy_results.csv",
]:
    print("\n====", f, "====")
    print(pd.read_csv(f).head())
PY
```

### 7.5 Manual Table 2 spot-check for `f1.txt`

```bash
python3 - <<'PY'
import pandas as pd
comp = pd.read_csv("results/raw/compression_time_results.csv")
decomp = pd.read_csv("results/raw/decompression_time_results.csv")
lookup = pd.read_csv("results/raw/lookup_time_no_recompression_results.csv")

row = lookup[lookup["File Name"]=="f1.txt"].iloc[0]
print("Table2 row:", row.to_dict())

drow = decomp[decomp["File Name"]=="f1.txt"].iloc[0]
print("Decompression row:", drow.to_dict())
PY
```

### 7.6 Inspect search logs

```bash
find results/logs/search -type f | sort | head -40
```

### 7.7 Inspect sample TIC/PIC/zgrep/bzgrep logs

```bash
for f in results/logs/search/*f1*; do
  echo "===== $f ====="
  sed -n '1,80p' "$f"
done
```

### 7.8 Inspect generated LaTeX

```bash
sed -n '1,200p' results/tables/lookup_time_no_recompression_table.tex
sed -n '1,200p' results/tables/lookup_time_with_recompression_table.tex
sed -n '1,200p' results/tables/lookup_memory_table.tex
sed -n '1,200p' results/tables/lookup_time_streaming_table.tex
sed -n '1,200p' results/tables/entropy_table.tex
```

### 7.9 Manual entropy spot-check for `f1.txt`

```bash
python3 - <<'PY'
from benchmark_utils import compute_file_entropy
print("Plain:", compute_file_entropy("datasets/f1.txt"))
print("TIC:", compute_file_entropy("datasets/f1.txt.tic"))
print("PIC:", compute_file_entropy("datasets/f1.txt.pic"))
print("gzip:", compute_file_entropy("datasets/f1.txt.gz"))
print("bzip2:", compute_file_entropy("datasets/f1.txt.bz2"))
print("lz4:", compute_file_entropy("datasets/f1.txt.lz4"))
PY
```

### 7.10 Check auto-regeneration of missing compressed artifacts

```bash
rm -f datasets/f2.txt.pic
python3 run_search.py
ls -lh datasets/f2.txt.pic
```

---

## 8. Verify `run_search_replace.py`

### 8.1 Run script

```bash
python3 run_search_replace.py
```

### 8.2 Check output files exist

```bash
ls -lh results/raw/lookup_replace_vs_plaintext_results.csv results/tables/lookup_replace_vs_plaintext_table.tex results/raw/lookup_replace_compressed_results.csv results/tables/lookup_replace_compressed_table.tex
```

### 8.3 Inspect CSV headers and first rows

```bash
python3 - <<'PY'
import pandas as pd
for f in [
    "results/raw/lookup_replace_vs_plaintext_results.csv",
    "results/raw/lookup_replace_compressed_results.csv",
]:
    df = pd.read_csv(f)
    print(f, "->", df.columns.tolist())
    print(df.head())
PY
```

### 8.4 Inspect L-R logs

```bash
find results/logs/search_replace -type f | sort | head -40
```

### 8.5 Inspect generated LaTeX

```bash
sed -n '1,200p' results/tables/lookup_replace_vs_plaintext_table.tex
sed -n '1,200p' results/tables/lookup_replace_compressed_table.tex
```

### 8.6 Manual spot-check on one row

```bash
python3 - <<'PY'
import pandas as pd
print(pd.read_csv("results/raw/lookup_replace_vs_plaintext_results.csv").query("`File Name`=='f1.txt'"))
print(pd.read_csv("results/raw/lookup_replace_compressed_results.csv").query("`File Name`=='f1.txt'"))
PY
```

---

## 9. Verify `run_parallel_benchmarks.py`

### 9.1 Run script

```bash
python3 run_parallel_benchmarks.py
```

### 9.2 Check output files exist

```bash
ls -lh results/raw/parallel_time_results.csv results/raw/parallel_memory_results.csv results/raw/parallel_search_results.csv results/figures/parallel_time.png results/figures/parallel_memory.png results/figures/parallel_search.png
```

### 9.3 Inspect CSV headers and rows

```bash
python3 - <<'PY'
import pandas as pd
for f in [
    "results/raw/parallel_time_results.csv",
    "results/raw/parallel_memory_results.csv",
    "results/raw/parallel_search_results.csv",
]:
    df = pd.read_csv(f)
    print("\n====", f, "====")
    print(df.columns.tolist())
    print(df)
PY
```

### 9.4 Open figures (macOS)

```bash
open results/figures/parallel_time.png
open results/figures/parallel_memory.png
open results/figures/parallel_search.png
```

### 9.5 Inspect parallel logs

```bash
find results/logs/parallel -type f | sort | head -80
```

---

## 10. Cross-script consistency checks

### 10.1 Verify all expected files were produced

```bash
ls -1 results/raw/*.csv results/tables/*.tex results/figures/*.png
```

### 10.2 Verify TIC baseline column exists where expected

```bash
python3 - <<'PY'
import pandas as pd
files = [
    "results/raw/compression_time_results.csv",
    "results/raw/decompression_time_results.csv",
    "results/raw/lookup_time_no_recompression_results.csv",
    "results/raw/lookup_time_with_recompression_results.csv",
    "results/raw/lookup_memory_results.csv",
    "results/raw/lookup_time_streaming_results.csv",
    "results/raw/lookup_replace_vs_plaintext_results.csv",
    "results/raw/lookup_replace_compressed_results.csv",
]
for f in files:
    df = pd.read_csv(f)
    print(f, "TIC columns:", [c for c in df.columns if "TIC" in c])
PY
```

### 10.3 Verify file-name consistency

```bash
python3 - <<'PY'
import pandas as pd
files = [
    "results/raw/cr_results.csv",
    "results/raw/compression_time_results.csv",
    "results/raw/decompression_time_results.csv",
    "results/raw/lookup_time_no_recompression_results.csv",
    "results/raw/lookup_time_with_recompression_results.csv",
    "results/raw/lookup_memory_results.csv",
    "results/raw/lookup_time_streaming_results.csv",
    "results/raw/lookup_replace_vs_plaintext_results.csv",
    "results/raw/lookup_replace_compressed_results.csv",
    "results/raw/entropy_results.csv",
]
for f in files:
    df = pd.read_csv(f)
    print(f, sorted(df["File Name"].tolist())[:3], "...", sorted(df["File Name"].tolist())[-3:])
PY
```

### 10.4 Verify no missing values in main tables

```bash
python3 - <<'PY'
import pandas as pd
files = [
    "results/raw/cr_results.csv",
    "results/raw/compression_time_results.csv",
    "results/raw/decompression_time_results.csv",
    "results/raw/lookup_time_no_recompression_results.csv",
    "results/raw/lookup_time_with_recompression_results.csv",
    "results/raw/lookup_memory_results.csv",
    "results/raw/lookup_time_streaming_results.csv",
    "results/raw/lookup_replace_vs_plaintext_results.csv",
    "results/raw/lookup_replace_compressed_results.csv",
    "results/raw/entropy_results.csv",
]
for f in files:
    df = pd.read_csv(f)
    print(f, "missing values =", int(df.isna().sum().sum()))
PY
```

---

## 11. Failure-mode checks

### 11.1 Missing prerequisite CSV

```bash
mv results/raw/compression_time_results.csv results/raw/compression_time_results.csv.bak
python3 run_search.py
mv results/raw/compression_time_results.csv.bak results/raw/compression_time_results.csv
```

Expected:
- `run_search.py` fails clearly and reports that `results/raw/compression_time_results.csv` is missing

### 11.2 Missing compressed artifact auto-regeneration

```bash
rm -f datasets/f3.txt.gz
python3 run_search.py
ls -lh datasets/f3.txt.gz
```

### 11.3 Missing input file

```bash
mv datasets/f10.txt datasets/f10.txt.bak
python3 run_parallel_benchmarks.py
mv datasets/f10.txt.bak datasets/f10.txt
```

Expected:
- the script fails clearly because the input file is missing

---

## 12. Final full run sequence

Run everything in order after the checks pass:

```bash
python3 run_compression.py
python3 run_decompression.py
python3 run_search.py
python3 run_search_replace.py
python3 run_parallel_benchmarks.py
```

---

## 13. Important note

During verification, inspect **Table 4 in `run_search.py`** carefully.

The agreed formula for Table 4 is the peak memory as the maximum of:
- compression
- decompression
- search

for each tool.

The current implementation should be checked against that requirement explicitly.
