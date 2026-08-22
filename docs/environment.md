# Environment, Dependencies and Build

Everything needed to get the TIC artifact running on a fresh machine, what is
required versus optional, and what to do when something is missing.

**Three separate things, in order.** Do not confuse them:

| | Command | Answers | Needs datasets? |
|---|---|---|---|
| **1. Environment validation** | `python3 check_environment.py` | *Is my machine set up?* | no |
| **2. Functional smoke test** | `python3 smoke_test.py` | *Does the code work at all?* | no — tiny synthetic input |
| **3. Full experiment reproduction** | `python3 run_*.py` | *Do the published numbers reproduce?* | yes — ~3.3 GB |

Only step 3 is a performance claim. Steps 1 and 2 say nothing about compression
ratio or speed.

---

## 1. Fresh-machine workflow

```bash
git clone <repository>
cd tic-compression-repo

./install_dependencies.sh        # system packages + requirements.txt, then verifies
python3 check_environment.py     # PASS/FAIL per dependency
make                             # build epic-v3.1 (TIC) and pic-v3.1 (PIC)
python3 smoke_test.py            # functional correctness, tiny synthetic input

python3 prepare_datasets.py      # datasets (see docs/datasets.md) -- hours, ~3.3 GB
python3 run_compression.py       # ... and the other runners
```

Run everything **from the repository root**: the compiled binaries resolve
`dict.txt` against the current working directory and exit 1 from anywhere else.

---

## 2. Supported operating systems

| Platform | Status |
|---|---|
| macOS (Apple clang / libc++), arm64 | **Verified.** Build, round trip, lookup and lookup-and-replace all pass |
| Ubuntu/Debian Linux (GCC / libstdc++), x86-64 | **Supported but untested here.** No GCC was available on the machine used to prepare this; the known libstdc++ hazard has been removed (§6), but the build has not been executed against libstdc++ |
| Other Linux distributions | Should work; `install_dependencies.sh` only automates apt, and exits 2 with a manual package list elsewhere |
| Windows | Not supported |

The published results were produced on macOS/arm64. macOS ships BSD
`gzip`/`bzip2`/`grep` while Linux ships the GNU versions, so **timings are not
comparable across the two platforms.**

---

## 3. Python requirements

**Minimum: Python 3.9.** The source itself only needs 3.7 — every PEP 585/604
annotation is guarded by `from __future__ import annotations` — but current
pandas and matplotlib require 3.9+. Verified on **3.11.7**.

```bash
python3 -m pip install -r requirements.txt
```

| Package | Classification | Needed for |
|---|---|---|
| `pandas` | **required** | every benchmark runner; tables and CSV I/O |
| `psutil` | **required** | all memory measurements (see §5) |
| `matplotlib` | experiment | parallel experiments (figures), `plot_parallel_*.py` |
| `requests` | experiment | dataset acquisition (`prepare_datasets.py fetch`) |
| `beautifulsoup4` (`bs4`) | experiment | dataset acquisition |
| `lxml` | experiment | dataset acquisition (parser backend) |
| `ebooklib` | experiment | dataset acquisition (EPUB conversion) |
| `numpy` | *not a direct dependency* | never imported here; arrives with pandas/matplotlib |

Pinning is **lower-bound only**, so the artifact keeps installing on newer
toolchains. Pin exactly only if you need bit-reproducible figures.

The canonical inventory — with classifications and per-experiment attribution —
is `dependencies.py`. `requirements.txt` mirrors its Python half.

---

## 4. System dependencies

macOS and Linux package names are **not** the same. Both lists below are what
`install_dependencies.sh` actually installs.

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y build-essential gzip bzip2 grep lz4 lbzip2 python3 python3-pip
```

`build-essential` supplies `g++` and `make`. `gzip` also provides `zgrep`;
`bzip2` also provides `bzgrep`.

### macOS (Homebrew)

```bash
xcode-select --install      # g++ and make, if not already present
brew install lz4 lbzip2
```

Only `lz4` and `lbzip2` are genuinely missing on a stock macOS system. **Homebrew's
GNU `gzip`/`grep` are deliberately not installed** — swapping the system BSD tools
for GNU ones would change which implementation the benchmarks measure.

`install_dependencies.sh` will not install Homebrew for you. If it is absent the
script prints the official requirement (https://brew.sh) and exits 2.

### What needs what

| Tool | Class | Preinstalled? | Experiments affected if missing |
|---|---|---|---|
| `g++`, `make` | required | macOS: Xcode CLT · Linux: no | building both binaries — everything |
| `gzip`, `bzip2`, `grep` | required | **yes**, both platforms | compression, decompression, search, search-and-replace |
| `lz4` | required | **no**, neither platform | compression, decompression, search, search-and-replace |
| `zgrep`, `bzgrep` | experiment | yes (with gzip/bzip2) | search — streaming baselines |
| **`lbzip2`** | experiment | **no**, neither platform | **parallel experiments ONLY** |
| `sh` | required | yes | decompression, search-and-replace, parallel pipelines |

**`lbzip2` is needed only by `run_parallel_benchmarks.py`.** Compression,
decompression, search and search-and-replace all run without it.

---

## 5. Fail-fast behaviour

Every runner calls `dependencies.preflight()` before its first measurement. It
validates the Python packages, external executables, compiled binaries, input
datasets and output directories **up front**, so a multi-hour benchmark never
dies halfway through because a tool was missing.

### psutil — silent zeros eliminated

`psutil` used to be imported inside a bare `try/except` that returned `None` on
failure, after which `_process_tree_memory_mb()` returned `0.0`. Every memory
column filled with zeros **and the run still reported success** — a missing
dependency silently became publishable numbers.

It now raises `MissingDependencyError` instead. A numeric zero never stands for
an unavailable measurement.

One zero remains legitimate: when a sampled process has already exited, `0.0` is
recorded because that is a genuine measurement of "no resident memory at this
instant", not a missing dependency. That is a separate, pre-existing
methodological limitation of 50 ms RSS polling, documented in
`docs/repository_inspection.md`.

### lz4, lbzip2 and the rest

`lz4` and `lbzip2` used to surface as a raw `FileNotFoundError` partway through a
run (`lbzip2` was checked, `lz4` was not). Both — along with `gzip`, `bzip2`,
`grep`, `zgrep`, `bzgrep` and `sh` — are now validated in `preflight()` before
anything is measured, with the apt and brew package names in the error message.

---

## 6. Build

```bash
make            # builds pic-v3.1 and epic-v3.1
make clean      # removes both binaries
make warnings   # compile-only warning audit; writes nothing
make CXX=g++-14 # build with a specific compiler
```

Flags: `-std=c++17 -O3 -pthread`.

### Portability fixes applied

- **Removed the dead `std::filesystem` aliases.** `epic-v3.1.h` and `pic-v3.1.h`
  each declared `namespace fs = std::filesystem;` **without including
  `<filesystem>`**, relying on a transitive include that libc++ happens to
  provide and libstdc++ does not guarantee — a likely hard compile failure on
  Linux/GCC. Neither alias was ever used (`fs::` appears **0** times in either
  translation unit), so both were removed rather than adding the include. No
  behavioural effect.
- **Added `-pthread`.** Both binaries use `std::thread`. Its absence is harmless
  on Apple clang but classically causes a link error or a runtime
  `std::system_error` on Linux/GCC.
- **`CXX` is now overridable.** `?=` cannot be used here — make predefines
  `CXX=c++`, so `?=` never fires. The Makefile overrides only when the value came
  from make's built-in default, so `make CXX=g++-14` and an exported `$CXX` both
  work.
- **Declared header dependencies.** Editing a `.h` previously triggered no
  rebuild and the binary silently went stale. `make clean` is no longer needed
  after a header edit.
- **Added `.PHONY`** for `all`, `pic`, `epic`, `warnings`, `clean`.

Audited and found clean: no macOS-only headers, no compiler-specific extensions,
no `#pragma`, no inline assembly, no architecture assumptions.

The committed `epic-v3.1` and `pic-v3.1` are **macOS arm64** binaries and will
not run on Linux. Run `make` first.

---

## 7. Warning audit

```bash
make warnings          # or: g++ -std=c++17 -Wall -Wextra -fsyntax-only epic-v3.1.cpp
```

**This artifact does not compile warning-free, and does not claim to.** With
`-std=c++17 -Wall -Wextra`:

| File | Warnings |
|---|---|
| `epic-v3.1.cpp` | **10** (was 11) |
| `pic-v3.1.cpp` | **4** (was 5) |

### Fixed

- `unused variable 'roughStart'` in both files — an orphaned declaration with a
  side-effect-free initialiser and no other reference anywhere. Removed.

### Remaining, deliberately

| Warning | Where | Why it was left |
|---|---|---|
| `variable 'sumAllMatch' set but not used` ×2 | `epic:3016, 3099` | Assigned in loops; removing the writes could change behaviour. Debug scaffolding |
| `variable 'tmpSerial' set but not used` | `epic:1676`, `pic:1867` | Same |
| `variable 'startsWithUppercase' set but not used` | `epic:1358`, `pic:1531` | Same |
| `variable 'matchStart' / 'matchingActive' set but not used` | `epic:395, 396` | Same |
| `variable 'lineNumber' set but not used` | `epic:2079` | Same |
| `unused variable 'previousPos'` | `epic:1158` | Dead, but referenced by an adjacent commented-out debug block. Left so that block stays usable |
| `unused parameter 'outputFile'` | `epic:2956`, `pic:3008` | Removing it changes a function signature that callers depend on |
| **`comparison of integers of different signs`** | `epic:2238`, `pic:2865` | **A genuine portability hazard.** `int i` compared against an unsigned `remainder` while dividing lines between threads. Fixing it correctly requires deciding the intended semantics for the signed operand — an author decision, not a mechanical cleanup |

The sign-compare pair is the only one with correctness implications. It is left
untouched deliberately: silencing it with a cast could change thread work
division, and no speculative algorithmic change was made merely to reach zero
warnings.

---

## 8. Environment validation

```bash
python3 check_environment.py            # full report
python3 check_environment.py --quiet    # failures and summary only
python3 check_environment.py --json     # machine-readable
```

Reports PASS/FAIL/WARN for the platform, Python interpreter and packages, the
compiler (including a live `-std=c++17 -pthread` probe), every external
executable, both compiled binaries, `dict.txt`, dataset availability and output
directories. Experiment-specific gaps name the affected experiment.

Exit code **0** when every *required* check passes; **1** otherwise. Experiment-
specific gaps are warnings, not failures — a missing `lbzip2` does not block the
non-parallel experiments. It runs no benchmarks and writes nothing.

---

## 9. Functional smoke test

```bash
python3 smoke_test.py             # builds, then tests both schemes
python3 smoke_test.py --no-build  # test existing binaries
python3 smoke_test.py --keep      # keep the temp working directory
```

For TIC and PIC independently: the binary builds, compression runs, decompression
runs, **the round trip is byte-identical**, lookup works, and lookup-and-replace
works. It uses ~10 KB of synthetic English text and needs no dataset.

**It is not a performance test.** It measures no time and no ratio.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `MissingDependencyError: psutil is required...` | psutil absent | `pip install -r requirements.txt`. It refuses to run rather than emit zeros |
| `Missing required executable(s): lz4` | lz4 absent | `apt install lz4` / `brew install lz4` |
| `Missing required executable(s) for the parallel experiment: lbzip2` | lbzip2 absent | Install it, or run the non-parallel experiments, which do not need it |
| Binary exits 1 immediately, no message | Wrong working directory | Run from the repository root; `dict.txt` is CWD-relative |
| `cannot execute binary file` on Linux | The committed binaries are macOS arm64 | `make` |
| `namespace fs = std::filesystem` compile error | Stale checkout predating the fix | Update; the dead aliases were removed |
| `std::system_error` at first thread launch | `-pthread` missing | Update; it is in `CXXFLAGS` now |
| `make` reports nothing to do after a header edit | Stale checkout | Update; header dependencies are declared now |
| `Missing required input file(s)` | Datasets absent | `python3 prepare_datasets.py`; see `docs/datasets.md` |
| Homebrew missing on macOS | By design, not auto-installed | Install from https://brew.sh, then re-run the installer |
| `Unsupported operating system` (exit 2) | Not Ubuntu/Debian or macOS | Install the §4 packages manually, then `check_environment.py` |

---

## 11. Related

- `dependencies.py` — canonical inventory and the `preflight()` guards
- `requirements.txt` — canonical Python dependency list
- `install_dependencies.sh` — system + Python installation
- `check_environment.py` — environment validation
- `smoke_test.py` — functional smoke test
- `docs/datasets.md` — dataset preparation
- `docs/repository_inspection.md` — full artifact inspection
