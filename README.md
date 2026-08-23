# TIC — Generalized Plain-Text Incremental Compression

Research artifact accompanying the TIC paper.

---

## Overview

**TIC** is a dictionary-based plain-text incremental compression framework. Its distinguishing
property is that it supports operations **directly on compressed data** — in particular **lookup**
(search) and **lookup-and-replace** — without a separate full decompression step.

**PIC** is included as the comparison baseline. It is an earlier plain-text incremental compression
scheme using 6-bit code words, where TIC uses 7-bit code words and multi-threading. Both are built
and benchmarked here so the two can be measured side by side, alongside the standard tools `gzip`,
`bzip2`, `lz4`, `lbzip2`, `zgrep` and `bzgrep`.

This repository exists for **artifact reproduction**: building the implementations, validating that
they work, preparing the benchmark corpora, and re-running the measurements behind the paper's
tables and figures.

> **Read this first if you intend to reproduce the published numbers.** Generated results are no
> longer committed, and the original benchmark corpus was never pinned. See
> [Reproducibility limitations](#reproducibility-limitations).

---

## Artifact contents

| Component | What it is |
|---|---|
| **TIC implementation** | `epic-v3.1.cpp` / `epic-v3.1.h` — 7-bit code words, multi-threaded. The contribution |
| **PIC baseline** | `pic-v3.1.cpp` / `pic-v3.1.h` — 6-bit code words, the comparison scheme |
| **Benchmark runners** | Five scripts covering compression, decompression, lookup, lookup-and-replace and the parallel experiments |
| **Dataset tooling** | `prepare_datasets.py` builds the benchmark datasets from **local** source corpora; cleaning/screening helpers for Gutenberg text |
| **Dictionary tooling** | `dict.txt` plus `pre-process-dict.py` to rebuild it from a frequency CSV |
| **Environment tooling** | `install_dependencies.sh`, `check_environment.py`, `requirements.txt`, `dependencies.py` |
| **Smoke test** | `smoke_test.py` — functional correctness on a tiny synthetic input |
| **Plotting** | `plot_parallel_results.py`, `plot_parallel_subset.py` |
| **Documentation** | `docs/` and `README_benchmark_verification.md` |

---

## Repository layout

```
epic-v3.1.cpp / .h            TIC implementation
pic-v3.1.cpp  / .h            PIC baseline
Makefile                      builds both binaries
dict.txt                      dictionary required at runtime by both schemes

run_compression.py            compression ratio + compression time
run_decompression.py          decompression time
run_search.py                 lookup time, lookup memory, entropy
run_search_replace.py         lookup-and-replace
run_parallel_benchmarks.py    thread scaling (TIC vs lbzip2)
benchmark_utils.py            shared measurement and table/figure helpers

prepare_datasets.py           dataset pipeline entry point
make_combined_text_files.py   builds f1..f10 from the cleaned corpora
pre-process-dict.py           builds dict.txt from a word-frequency CSV
dataset_config.py             dataset, dictionary and results paths (single source of truth)
dependencies.py               dependency inventory and pre-flight guards

install_dependencies.sh       system + Python dependency installation
check_environment.py          environment validation
smoke_test.py                 functional smoke test
requirements.txt              Python dependencies

plot_parallel_results.py      parallel figures
plot_parallel_subset.py       parallel figures, threads 1/2/4/6/8 only

datasets/manifest.csv         dataset inventory (tracked)
docs/                         detailed documentation
```

### Generated directories

These are **created on demand and intentionally not tracked**:

```
results/
    raw/        *_results.csv   measurements
    tables/     *_table.tex     LaTeX tables
    figures/    *.png           plots
    logs/                       per-experiment stdout/stderr
    tmp/                        scratch space
datasets/       f1.txt .. f10.txt and file-parallel.txt (multi-gigabyte)
epic-v3.1, pic-v3.1             compiled binaries
```

Nothing under `results/`, no compiled binary, and no benchmark dataset is committed. Running an
experiment cannot overwrite source files or documentation.

---

## Requirements

| | |
|---|---|
| **Python** | 3.9 or newer. Tested on 3.11.7 |
| **C++** | C++17 compiler (`g++` or Apple clang) and `make` |
| **Required tools** | `gzip`, `bzip2`, `lz4`, `grep` |
| **Experiment-specific** | `zgrep`, `bzgrep` (search baselines) · `lbzip2` (**parallel experiments only**) |
| **Python packages** | `pandas`, `psutil` (required); `matplotlib` (figures). That is all — the dataset pipeline is pure standard library |

`lz4` and `lbzip2` are **not** preinstalled on either macOS or Linux.

### Platforms

- **macOS / arm64 — tested.** Build, both round trips, lookup and lookup-and-replace all verified.
- **Ubuntu / Debian — supported, not yet fully validated.** The known portability issues have been
  addressed (`-pthread`, no reliance on transitive `<filesystem>`, overridable `CXX`), but the build
  has not been executed against GCC/libstdc++ on the development machine used to prepare this
  artifact.
- Windows is not supported.

macOS ships BSD `gzip`/`bzip2`/`grep` while Linux ships the GNU versions, so **timings are not
directly comparable across the two platforms**.

Full details: **[docs/environment.md](docs/environment.md)**

---

## Installation

```bash
./install_dependencies.sh
python3 check_environment.py
```

The installer detects the operating system and uses:

- **Ubuntu/Debian** — `apt` (`build-essential gzip bzip2 grep lz4 lbzip2 python3 python3-pip`)
- **macOS** — Homebrew (`lz4 lbzip2`; the rest ship with macOS or the Xcode Command Line Tools)

It installs Python packages from `requirements.txt` and then runs `check_environment.py` itself.
`--dry-run` shows what it would install without changing anything.

**Homebrew is not installed automatically.** If it is missing on macOS the script prints the official
requirement and exits; installing it is your decision.

`check_environment.py` reports PASS/FAIL/WARN per dependency and names the affected experiment for
anything experiment-specific. It runs no benchmarks. `--quiet` and `--json` are also available.

---

## Build

```bash
make            # builds epic-v3.1 (TIC) and pic-v3.1 (PIC)
make clean      # removes both
make warnings   # compile-only warning audit, writes nothing
make CXX=g++-14 # build with a specific compiler
```

Flags are `-std=c++17 -O3 -pthread`.

**The binaries are intentionally not tracked** and are git-ignored — every reviewer builds them
locally for their own platform.

Run everything from the repository root.

---

## Smoke test

```bash
python3 smoke_test.py
```

For TIC and PIC independently, this checks that the binary builds, compression runs, decompression
runs, **the round trip is byte-identical**, lookup works and lookup-and-replace works.

**This is a functional correctness check, not a performance reproduction.** It measures no time and
no compression ratio, runs on about 10 KB of synthetic text, and needs no benchmark dataset. It also
supplies its own small dictionary, so it does not require `dict.txt`.

Options: `--no-build` (skip `make`), `--historical-dict` (use the real `dict.txt`), `--keep`.

---

## Dictionary

Both schemes load a dictionary at start-up for **every** operation — compression, decompression,
lookup and lookup-and-replace. Without it the binaries exit with an error.

The dictionary used for the paper, `dict.txt`, **is included in this repository** (333,350 entries).

Resolution order:

1. `$TIC_DICT_PATH`, if set
2. `dict.txt` relative to the current working directory (default)

```bash
TIC_DICT_PATH=/path/to/dict.txt ./epic-v3.1 -c -t 1 input.txt output.tic
```

`pre-process-dict.py --input <frequency.csv> --output dict.txt` rebuilds it from a word-frequency
CSV. Entry order is significant: a dictionary that differs in any way produces different compressed
output and will not reproduce the published measurements.

Details, fingerprint and provenance: **[docs/dictionary.md](docs/dictionary.md)** ·
**[docs/licensing.md](docs/licensing.md)**

---

## Dataset preparation

```bash
python3 prepare_datasets.py            # check -> build -> verify
python3 prepare_datasets.py check      # dependencies, local sources, disk space
python3 prepare_datasets.py build      # combine local corpora into f1..f10
python3 prepare_datasets.py verify --sha256
```

The benchmark inputs are ten text files `f1.txt` … `f10.txt` (50 MB to 769 MB, ~3.3 GB total), built
from Standard Ebooks and Project Gutenberg text. They live under **`datasets/`** and are **not
committed** because of their size. `datasets/manifest.csv` is tracked and records each dataset's
target size, measured size, checksum and construction; values that cannot be measured are recorded as
`unavailable` rather than guessed.

### You supply the source corpora

**This artifact does not download or crawl anything.** The source corpora are **external inputs**
that you provide locally; the repository neither redistributes them nor fetches them automatically,
so a reproduction never depends on a live, changing external catalog.

`prepare_datasets.py` expects, relative to the repository root:

| Directory | Contents |
|---|---|
| `standard_ebooks_output/txt_clean/*.txt` | cleaned Standard Ebooks plain text, one file per book |
| `gutenberg_ebooks/raw/*.txt` | raw Project Gutenberg text (clean it first with `clean_gutenberg_texts.py`) |

Either directory alone is enough for the smaller datasets; `f10` needs roughly 769 MB of text in
total. If neither is present the pipeline fails immediately and tells you exactly what to supply.
[Standard Ebooks](https://standardebooks.org) and [Project Gutenberg](https://www.gutenberg.org) are
the corpora used for the paper.

> **Regenerated datasets may not be byte-identical to the historical paper inputs.** Standard Ebooks
> and Project Gutenberg are live, growing catalogs, and the original corpus snapshot was never
> pinned — no book list, no crawl date, no checksums. A rebuild is statistically similar but
> **approximate, not exact**, so measurements taken on it will not match the published numbers
> exactly.

Details: **[docs/datasets.md](docs/datasets.md)**

---

## Running experiments

All runners are executed from the repository root and require the Python dependencies to be
installed. Each validates its dependencies, tools, binaries, inputs and output directories **before**
taking any measurement, so a long run fails immediately rather than halfway through.

| Command | Measures | Writes |
|---|---|---|
| `python3 run_compression.py` | compression ratio and compression time (TIC, PIC, gzip, bzip2, lz4) | `cr_results.csv`, `compression_time_results.csv` |
| `python3 run_decompression.py` | decompression time | `decompression_time_results.csv` |
| `python3 run_search.py` | lookup time (with/without recompression, streaming), lookup memory, entropy | `lookup_time_*_results.csv`, `lookup_memory_results.csv`, `entropy_results.csv` |
| `python3 run_search_replace.py` | lookup-and-replace, compressed and versus plaintext | `lookup_replace_compressed_results.csv`, `lookup_replace_vs_plaintext_results.csv` |
| `python3 run_parallel_benchmarks.py --input <file>` | thread scaling at 1, 2, 4, 6 and 8 threads (TIC vs lbzip2) | `parallel_{time,memory,search,replace}_results.csv` + figures |

The first four take **no command-line arguments** — their configuration (input files, tools, run
counts) lives in constants at the top of each script. Only `run_parallel_benchmarks.py` has a CLI:

```
--input PATH       input file for the parallel experiments
--sha256           report the input's SHA-256 before benchmarking
--describe-only    validate and describe the input, then exit
```

Every CSV is written to **`results/raw/`**, logs to `results/logs/<experiment>/`. These directories
are created automatically. A full run is long: `NUM_RUNS = 10` with one warm-up over inputs up to
769 MB.

---

## Tables and figures

**LaTeX tables** are produced by the runners themselves, alongside their CSVs, into
**`results/tables/`** — for example `run_compression.py` writes `cr_table.tex` and
`compression_time_table.tex`. There is no separate table-generation step.

**Parallel figures** are written to **`results/figures/`**:

```bash
python3 run_parallel_benchmarks.py --input <file>   # writes CSVs and the four figures
python3 plot_parallel_results.py                    # re-plot from existing CSVs
python3 plot_parallel_subset.py                     # re-plot, threads 1/2/4/6/8 only
```

Both plotting scripts read from `results/raw/`. If a required CSV is absent they report which file is
missing, name the experiment that produces it, and exit cleanly — they never fabricate or substitute
data.

---

## Parallel benchmark caveat

The parallel experiments used a single input file, `file-parallel.txt`, whose **provenance could not
be recovered**. No script in this repository produces it, it was never tracked in version control,
and no documentation describes it. Its size and construction are unknown and are recorded as
`unavailable` rather than inferred.

Reviewers can supply any input explicitly:

```bash
python3 run_parallel_benchmarks.py --input datasets/f10.txt --sha256
```

A substitute input reproduces the **functionality and the thread-scaling behaviour**, but **not the
exact historical absolute values**. The runner labels the input accordingly at run time. Record the
path, byte size and SHA-256 it prints alongside any numbers you report.

Details: **[docs/datasets.md](docs/datasets.md)** (section 7)

---

## Reproduction workflow

```bash
# 1. install dependencies
./install_dependencies.sh

# 2. validate the environment
python3 check_environment.py

# 3. build TIC and PIC
make

# 4. functional smoke test (fast, no datasets needed)
python3 smoke_test.py

# 5. prepare datasets from your local corpora (~3.3 GB of output)
#    see "Dataset preparation" for the local inputs you must supply first
python3 prepare_datasets.py

# 6. run experiments
python3 run_compression.py
python3 run_decompression.py
python3 run_search.py
python3 run_search_replace.py
python3 run_parallel_benchmarks.py --input datasets/f10.txt

# 7. re-plot figures from the generated CSVs (optional)
python3 plot_parallel_results.py
```

Steps 1–4 need no datasets and are the fastest way to confirm the artifact works.

---

## Reproducibility limitations

Stated plainly, because they affect how results should be interpreted:

1. **The benchmark corpus was never pinned.** Standard Ebooks and Project Gutenberg change over
   time, so regenerated `f1`–`f10` are approximate, not byte-identical to the paper's inputs.
2. **`file-parallel.txt` cannot be reconstructed** — provenance unknown.
3. **A different dictionary changes the output.** Compression is dictionary-dependent; only the
   included `dict.txt` reproduces the published numbers.
4. **Linux has not been fully validated** on the development machine used to prepare this artifact.
5. **Absolute timings are machine- and platform-specific.** Results were produced on macOS/arm64;
   BSD versus GNU tool implementations differ.
6. **No automated test suite or CI.** `smoke_test.py` is the functional check.

Record the machine, OS, compiler version, Git commit, dataset manifest and dictionary SHA-256
alongside any results you publish.

---

## Documentation

| Document | Covers |
|---|---|
| [docs/environment.md](docs/environment.md) | Platforms, dependencies, build, warning audit, troubleshooting |
| [docs/datasets.md](docs/datasets.md) | Corpora, dataset construction, manifest, checksums, the parallel input |
| [docs/dictionary.md](docs/dictionary.md) | How the dictionary is consumed, its fingerprint, how to supply one |
| [docs/licensing.md](docs/licensing.md) | Licensing and redistribution analysis |
| [docs/repository_inspection.md](docs/repository_inspection.md) | Dated audit of the repository |
| [docs/cleanup_manifest.md](docs/cleanup_manifest.md) | Artifact cleanup classification |
| [README_benchmark_verification.md](README_benchmark_verification.md) | Script-by-script benchmark verification checklist |

---

## License

No license file is present yet. **Licensing will be finalized before public release.** Until then no
permission to use, modify or redistribute this code is granted or implied.

Note that `dict.txt` derives from a third-party dataset whose terms are unresolved; see
[docs/licensing.md](docs/licensing.md).

---

## Citation

Citation information will be added upon publication.
