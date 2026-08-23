# Repository Inspection — tic-compression-repo

**Inspection date:** 2026-08-20
**Mode:** read-only. No file in the repository was modified; the only file created is this report.
**Branch:** `claude/repository-cleanup` · **HEAD:** `33d95fb` ("Initial TIC artifact repository state")
**Remote:** `git@github.com:afairouz87/tic-compression-repo.git` · **Working tree:** clean
**Inspection host:** macOS 25.5.0, arm64; `/usr/bin/g++` = Apple clang 21.0.0; Python 3.11.7 (pyenv shim)

**Scope note.** No benchmark was run and `make` was never invoked (both binaries are tracked files
and a build would dirty the tree). C++ sources were checked with `g++ -fsyntax-only`, which writes
nothing.

> **Status update — 2026-08-23.** Four directories discussed below have since been **removed from
> the release artifact**: `search_outputs/`, `debug_pic_tic_outputs/`, `old_versions/` and
> `backup_versions/`. This document is a dated audit and its findings are retained verbatim as
> historical evidence; paths it describes are no longer present in the working tree. Their exact
> pre-removal state is preserved at the Git tag `pre-artifact-cleanup`
> (`git checkout pre-artifact-cleanup -- <path>`). See `docs/cleanup_manifest.md`.

> **Status update — 2026-08-24.** The committed generated artifacts described below have since been
> **removed from the release artifact**: the 14 `*_results.csv` files, the 10 `*_table.tex` tables,
> the 4 `parallel_*.png` figures, and the compiled binaries `epic-v3.1` / `pic-v3.1`. Experiment
> output now goes to `results/raw`, `results/tables` and `results/figures`, never the repository
> root, and the whole `results/` tree is git-ignored. Binaries are built locally with `make`.
> Findings below are retained verbatim as dated evidence; their exact pre-removal state is preserved
> at the Git tag `pre-artifact-cleanup`. See `docs/cleanup_manifest.md`.

---

## 1. Current directory tree

```
tic-compression-repo/                       72 entries at root, 128 tracked files, 32 MB (.git = 22 MB)
├── .claude/                                agent state — untracked, ignored (.gitignore:6)
│   ├── decisions.md
│   ├── status.md
│   ├── tasks.md
│   └── reports/
│       └── repository-inspection.md        prior inspection, 2026-08-18
├── .vscode/
│   └── settings.json                       TRACKED (editor-local config)
├── backup_versions/                        5 entries, 4.8 MB
│   ├── Makefile_backup
│   ├── Makefile_backup_31Jul2025
│   ├── epic-v3.1.cpp.bk
│   ├── epic-v3.1.h.bk
│   └── unigram_freq_bk.csv                 4.8 MB — largest tracked file
├── debug_pic_tic_outputs/
│   └── debug_pic_tic_qrz8ndi6/             16 files: a committed tempfile.mkdtemp() run
├── old_versions/                           9 superseded C++ files + a misfiled README
├── search_outputs/                         28 committed stdout/stderr captures
├── docs/                                   NEW — contains only this report
│
├── CLAUDE.md                               untracked, ignored (.gitignore:5)
├── .gitignore
├── Makefile
├── README.md                               stale
├── README_benchmark_verification.md        686 lines
│
├── epic-v3.1.cpp / .h / epic-v3.1          TIC — source, header, committed arm64 binary
├── pic-v3.1.cpp  / .h / pic-v3.1           PIC — source, header, committed arm64 binary
├── dict.txt                                333,350 lines, 2.7 MB
│
├── benchmark_utils.py                      1,077 lines — shared harness
├── run_compression.py  run_decompression.py
├── run_search.py  run_search_v1.py  run_search.py.bk
├── run_search_replace.py  run_parallel_benchmarks.py
├── run.py  measureTime.py  debug_pic_tic.py  compression_parallel_debug.py
├── plot_parallel_results.py  plot_parallel_subset.py
├── pre-process-dict.py  make_combined_text_files.py
├── build_standard_ebooks_catalog.py
├── check_gutenberg_books.py  check_longest_line.py
├── clean_gutenberg_footer.py  clean_gutenberg_texts.py
├── download_gutenberg_texts.py
├── download_standard_ebooks_from_catalog.py       (+ _v1)
├── download_standard_ebooks_to_txt.py             (+ _v1 _v2 _v3 _v4)
│
├── *_results.csv                           14 files
├── *_table.tex                             10 files
└── parallel_{time,memory,search,replace}.png     4 files
```

Everything lives flat at the root; there is no `src/`, `scripts/`, `results/`, `data/`, or `tests/`.

## 2. Purpose of each directory

| Directory | Purpose | Tracked? |
|---|---|---|
| *(root)* | All source, all runners, all published results, the dictionary, both binaries | yes |
| `old_versions/` | Superseded PIC/EPIC C++ (v1–v3), ~7.9 k lines. Historical reference, not built | yes |
| `backup_versions/` | Manual `.bk` snapshots of the current sources plus two dated `Makefile` copies and the raw Kaggle unigram CSV | yes |
| `search_outputs/` | 28 stdout/stderr captures from `run_search_v1.py --output-dir search_outputs` for query `"the"` on `test0`/`test4` | yes |
| `debug_pic_tic_outputs/debug_pic_tic_qrz8ndi6/` | One `tempfile.mkdtemp()` directory from `debug_pic_tic.py`, committed with its `.pic`/`.tic` artifacts and decompressed text | yes |
| `.vscode/` | Editor settings (font size, zoom level, `errorSquiggles: disabled`) | yes — but also listed in `.gitignore:9`, so the ignore rule is inert |
| `.claude/` | Project-agent state and the 2026-08-18 inspection | no (ignored) |
| `docs/` | Created by this inspection to hold this report | new |

## 3. Important source files

**C++ (the contribution).** Both are single translation units; the headers are `#include`d, not compiled separately.

| File | Lines/size | Role |
|---|---|---|
| `epic-v3.1.cpp` | 94 KB | **TIC** — 7-bit code words, multi-threaded (`std::thread`, `epic-v3.1.cpp:2224-2341`) |
| `epic-v3.1.h` | 5.5 KB | TIC constants: `CODE_WORD_OFFSET`, byte-range bounds, reserved codes |
| `pic-v3.1.cpp` | 105 KB | **PIC** — 6-bit code words, the comparison scheme |
| `pic-v3.1.h` | 5.7 KB | PIC constants |

CLI contract (`epic-v3.1.cpp:130`): `./epic-v3.1 -[c,d,l,r] -t <num_threads> <in> <out> ["<search>"] ["<replace>"]`.

**Python — the five published runners.**

| File | Lines | Produces |
|---|---|---|
| `benchmark_utils.py` | 1,077 | Command construction, timing, RSS sampling, entropy, CSV/LaTeX/plot builders |
| `run_compression.py` | — | `cr_results.csv`, `cr_table.tex`, `compression_time_*` |
| `run_decompression.py` | — | `decompression_time_*` |
| `run_search.py` | 1,570 | `lookup_time_{no_recompression,with_recompression,streaming}_*`, `lookup_memory_*`, `entropy_*` |
| `run_search_replace.py` | — | `lookup_replace_compressed_*`, `lookup_replace_vs_plaintext_*` |
| `run_parallel_benchmarks.py` | — | `parallel_{time,memory,search,replace}_results.csv` + 4 PNGs |

**Python — corpus acquisition pipeline** (11 scripts): `build_standard_ebooks_catalog.py` →
`download_standard_ebooks_{to_txt,from_catalog}*.py` / `download_gutenberg_texts.py` →
`clean_gutenberg_{texts,footer}.py` → `check_gutenberg_books.py`, `check_longest_line.py` →
`make_combined_text_files.py`.

**Utilities:** `pre-process-dict.py` (builds `dict.txt`), `debug_pic_tic.py`, `plot_parallel_*.py`,
`measureTime.py`, `run.py`, `compression_parallel_debug.py`.

**Data:** `dict.txt` — 333,350 lines, frequency-ordered, punctuation first (`,`, `.`, `-`, …).

## 4. Build system

`Makefile`, 26 lines:

```make
CXX = g++
CXXFLAGS = -std=c++17 -O3
TARGETS = pic-v3.1 epic-v3.1
```

Targets: `all` (default), `pic-v3.1`, `epic-v3.1`, aliases `pic`/`epic`, `clean` (`rm -f $(TARGETS)`).

Verified this session with `g++ -std=c++17 -fsyntax-only`: **both sources compile cleanly, exit 0.**
Under `-Wall -Wextra`: **11 warnings in epic, 5 in pic** (none fatal).

Defects in the build system:

1. **No header dependency.** `pic-v3.1: pic-v3.1.cpp` omits the `.h`. Editing a header produces no
   rebuild; the binary silently goes stale. Requires `make clean` first.
2. **Targets are also tracked files.** `epic-v3.1` and `pic-v3.1` are committed Mach-O arm64
   executables *and* Make targets, so a plain `make` dirties the working tree.
3. **`-pthread` is absent** from `CXXFLAGS` although `epic-v3.1.cpp` launches `std::thread`. Benign
   under Apple clang/libc++; on Linux/GCC this is the classic link-or-runtime failure mode.
4. No `install`, `test`, `check`, or `.PHONY` declarations. `clean` and `all` would break against a
   file of the same name.
5. `CXX = g++` is hardcoded — on this machine `g++` resolves to Apple clang, not GCC.

## 5. External dependencies

**Compile-time:** none beyond the C++17 standard library.

**Runtime CLI tools** — invoked by name via `subprocess`, never version-pinned, and (with one
exception) never checked for presence:

| Tool | Occurrences | Present on this host |
|---|---|---|
| `gzip` | 121 | ✅ `/usr/bin/gzip` |
| `lz4` | 118 | ❌ **MISSING** |
| `bzip2` | 117 | ✅ `/usr/bin/bzip2` |
| `zgrep` | 30 | ✅ `/usr/bin/zgrep` |
| `bzgrep` | 28 | ✅ `/usr/bin/bzgrep` |
| `lbzip2` | 19 | ❌ **MISSING** |
| `grep` | 12 | ✅ |

Only `lbzip2` is guarded (`run_parallel_benchmarks.py:119`, `shutil.which`). A missing `lz4` surfaces
as a raw `FileNotFoundError` mid-run. Note also that macOS `gzip`/`bzip2`/`grep` are BSD builds while
Linux ships GNU builds — a silent cross-platform variable in the published timings.

## 6. Python requirements

**There is no `requirements.txt`, `environment.yml`, `pyproject.toml`, `setup.py`, `Pipfile`, or
`setup.cfg`.** Confirmed by directory listing.

**No declared minimum Python version.** All 18 files using PEP 585/604 generics carry
`from __future__ import annotations`, so nothing hard-requires 3.10. Realistic floor: **Python 3.7+**;
verified working interpreter: **3.11.7**.

Installed-package audit on this host — **all seven third-party packages are absent**:

| Package | Status here |
|---|---|
| pandas, matplotlib, psutil, requests, bs4, lxml, ebooklib | ❌ not installed |

Consequence: no runner can execute on this machine as-is, independent of the missing dataset.

## 7. Third-party libraries

| Package | Imported by | Failure mode if absent |
|---|---|---|
| **pandas** | `benchmark_utils.py`, all 5 runners, both plotters, `run.py`, `run_search_v1.py` | Hard `ImportError` — top-level, unguarded |
| **matplotlib** | `benchmark_utils.py`, `run_parallel_benchmarks.py`, both plotters | Guarded in `benchmark_utils.py:32-35` (`plt = None`); **unguarded** in the other three |
| **psutil** | `benchmark_utils.py`, `run_search_v1.py`, `run.py` | **Silently swallowed** in `benchmark_utils.py:81-86` / `_process_tree_memory_mb` returns `(0.0, 0.0)` → every memory column fills with **zeros and the run still "succeeds"**. Unguarded top-level import in `run.py:2` |
| **requests** | 8 download scripts | Hard `ImportError` |
| **beautifulsoup4** (`bs4`) | 8 download scripts | Hard `ImportError` |
| **ebooklib** | 7 download scripts | Hard `ImportError` |
| **lxml** | Not imported directly; named in 5 docstring install lines as a bs4 parser backend | Runtime parser error |

The psutil path is the most damaging: it converts a missing dependency into **plausible, wrong,
publication-bound numbers** rather than an error.

## 8. Generated files

62 of 128 tracked files are machine-generated and committed as the published baseline.

- **14 result CSVs.** Ten file-indexed sets (`cr`, `compression_time`, `decompression_time`,
  `entropy`, `lookup_memory`, `lookup_replace_compressed`, `lookup_replace_vs_plaintext`,
  `lookup_time_no_recompression`, `lookup_time_streaming`, `lookup_time_with_recompression`) each with
  11 rows (`f1..f10` + `Average`); four thread-indexed parallel sets with 5 rows (threads 1, 2, 4, 6, 8).
- **10 LaTeX tables** (`*_table.tex`) — direct renderings of the CSVs.
- **4 PNG figures** — `parallel_{time,memory,search,replace}.png`.
- **2 compiled binaries** — `epic-v3.1`, `pic-v3.1` (Mach-O arm64).
- **`search_outputs/` (28 files)** and **`debug_pic_tic_outputs/…/` (16 files)** — captured process output.
- `backup_versions/unigram_freq_bk.csv` — the raw upstream corpus from which `dict.txt` is derived.

**Overwrite hazard.** Every runner sets `RESULTS_DIR = "."`
(`run_compression.py:88`, `run_decompression.py:78`, `run_search.py:109`,
`run_search_replace.py:82`, `run_parallel_benchmarks.py:42`). Any benchmark run **overwrites the
published baseline in place**, and since the binaries are also Make targets, a build does the same.

## 9. Temporary files

- **`debug_pic_tic_outputs/debug_pic_tic_qrz8ndi6/`** — the suffix is a `tempfile.mkdtemp()` token
  (`debug_pic_tic.py:194`). A scratch directory that was committed, including `small.txt.pic`,
  `small.txt.tic`, and both decompressed outputs.
- **`search_outputs/`** — 28 captures; 12 of them are **zero-byte** stderr/stdout files, and five are
  identical 173 KB `grep` dumps of the word "the". Produced by `run_search_v1.py`, itself superseded.
- **`run_search.py.bk`**, **`backup_versions/*.bk`**, `Makefile_backup`, `Makefile_backup_31Jul2025` —
  editor/manual snapshots serving as a second, informal version-control system alongside Git.
- Runtime temp dirs are created correctly via `tempfile.mkdtemp()` in `run_search.py:584`,
  `run_search_replace.py:559`, `run_search_v1.py:427` — these are fine; only the committed one is a problem.
- Two hardcoded `/tmp` paths: `compression_parallel_debug.py:10`, `check_gutenberg_books.py:21`.
- Clean: no `.DS_Store`, no `__pycache__`, no `*.dSYM` anywhere in the tree.

## 10. Candidates that should NOT be in the public artifact

Ordered by strength of case. **None of these should be deleted without explicit approval** (`CLAUDE.md` §10).

| Candidate | Size | Reason |
|---|---|---|
| `debug_pic_tic_outputs/` | 16 files | Committed temp directory with a random-token name. No reviewer value |
| `search_outputs/` | 28 files, 900 KB | Run residue from a superseded script; 12 files are empty, 5 are duplicate 173 KB grep dumps |
| `backup_versions/*.bk`, `Makefile_backup*` | 113 KB | Git already holds this history |
| `run_search.py.bk` | 6 KB | Same |
| `epic-v3.1`, `pic-v3.1` | 273 KB | Compiled **macOS arm64** binaries. Non-portable, and their presence as Make targets guarantees a dirty tree. Should be untracked and `.gitignore`d |
| `.vscode/settings.json` | 478 B | Personal editor config; already named in `.gitignore:9` but tracked anyway, so the rule never applies. `"C_Cpp.errorSquiggles": "disabled"` is a personal preference |
| `run_search_v1.py`, `download_standard_ebooks_to_txt_{v1..v4}.py`, `download_standard_ebooks_from_catalog_v1.py` | 6 files, ~100 KB | Superseded siblings of the live script sitting beside it at the root. A reviewer cannot tell which is authoritative |
| `run.py`, `measureTime.py`, `compression_parallel_debug.py` | — | Ad-hoc scratch measurement scripts, unreferenced by the published pipeline. `measureTime.py:39` still points at `./pic-v1`, a binary that no longer exists |
| `backup_versions/unigram_freq_bk.csv` | 4.8 MB | 15 % of the repository. Legitimate as dictionary provenance — but then it belongs in `data/` with a stated source and license, not in a folder named "backup" |
| `CLAUDE.md`, `.claude/` | — | Correctly ignored already; verify they stay out of any release tarball |

**Keep, do not remove:** `old_versions/` (documented historical policy), `dict.txt`, the 14 CSVs,
10 `.tex` tables, 4 PNGs (the published baseline), `README_benchmark_verification.md`.

## 11. Missing documentation

1. **`README.md` is wrong.** It describes PIC only, at an earlier version. It contains **zero
   occurrences of "TIC"** — the repository's actual contribution is undocumented. It advertises
   `pic-v1.cpp`, `epic-v1.cpp`, and a `test-code/` directory; the first two live in `old_versions/`
   and `test-code/` **does not exist**. It has two sections numbered "3". No build, run, benchmark,
   citation, license, or dataset section.
2. **`old_versions/README.md` is misfiled.** It is not about old versions — it is a "TIC Claude Code
   Setup" guide describing `prompts/01_inspect_only.md` … `06_commit_and_release_prep.md`, none of
   which exist in this repository. It instructs the reader to review `docs/repository-inspection.md`,
   a path that did not exist before this report.
3. **No CLI reference.** The `-c/-d/-l/-r` flags, `-t`, and argument order exist only in a `cerr`
   usage string at `epic-v3.1.cpp:130`.
4. **No file-format specification.** The `.tic`/`.pic` container layout, the 7-bit vs 6-bit code-word
   distinction, and the reserved codes (`SPACE_CODE`, `NEXT_CAPITAL_CODE`, `NEXT_SPECIAL_CODE`, …)
   are documented only as `#define`s and inline comment blocks.
5. **No dataset documentation.** No manifest, no checksums, no sizes, no acquisition date for
   `f1..f10` — and no statement anywhere that `../textFiles/` must exist outside the repository root.
6. **No `dict.txt` documentation.** Format, ordering, provenance, and the regeneration path via
   `pre-process-dict.py` are all unstated.
7. **No results provenance.** No CSV/table describes the machine, OS, compiler, commit, or date that
   produced it.
8. **No `CONTRIBUTING.md`, `CHANGELOG.md`, or `CITATION.cff`.**
9. **No mapping from artifact to paper.** Ten tables and four figures exist; nothing states which
   `.tex` file is which numbered table in the paper.

`README_benchmark_verification.md` (686 lines, 60+ numbered checks) is the one strong document here —
but it is a verification checklist, not an entry point, and it presupposes a working environment.

## 12. Missing build instructions

- No build section in `README.md` at all; `make` is documented nowhere a reviewer would look.
- No prerequisites: required compiler, minimum standard, Python version, or the six CLI tools.
- **The CWD requirement is undocumented.** `pic-v3.1.cpp:76` and `epic-v3.1.cpp:76` both hardcode
  `string dictFilename = "dict.txt";` — resolved against the *current working directory*. Run from
  anywhere but the repository root, both binaries exit 1. Nothing in the repository says so.
- The stale-header trap (§4.1) is undocumented, so an editor of `.h` gets a silently stale binary.
- No install/uninstall path, no smoke test, no expected-output sample, no "how to verify your build
  is correct" round trip.
- No Docker image, VM, Nix/Conda spec, or CI workflow — nothing pins the environment.

## 13. Missing scripts

1. **The pipeline has a hole between stage 5 and stage 6.** `make_combined_text_files.py:19-29`
   writes `combined_text_files/f1..f5.txt`; every runner reads `../textFiles/f1..f10.txt`. **No script
   bridges the two**, and the runners are configured for **10** input files (verified: 10 active
   entries in each of the four file-indexed runners) while the generator emits **5** — `f6..f10` are
   commented out at `make_combined_text_files.py:26-29`. The committed CSVs nonetheless contain all
   ten rows.
   **Resolved 2026-08-21:** `f6`–`f10` restored, `datasets/` made the single canonical dataset
   directory, and all five runners repointed at it via `dataset_config.py`. See `docs/datasets.md`.
2. **No top-level driver.** Reproducing the paper means running five scripts by hand in an unstated
   order. There is no `run_all.sh`, no `Makefile` benchmark target.
3. **No environment/setup script** — no `setup.sh`, no dependency installer, no tool-presence check.
4. **No test suite and no CI.** Zero test files; no `.github/workflows/`. Not even a round-trip
   assertion script, though `README_benchmark_verification.md` describes the checks in prose.
5. **No dataset fetch/verify script** — no manifest download, no checksum verification.
6. **No baseline-protection script.** Given `RESULTS_DIR = "."`, a `save-baseline` / `diff-baseline`
   pair is the obvious missing safeguard.
7. **No table→paper mapping generator**, and no script regenerating the `.tex` files from CSVs
   independently of a full benchmark run.

## 14. Potential portability issues (Linux/macOS)

Verified platform is macOS/arm64 only. **Linux x86-64 is untested.** Concrete risks:

1. **`namespace fs = std::filesystem;` without `#include <filesystem>`** —
   `epic-v3.1.h:26` and `pic-v3.1.h:25`. Verified this session: under Apple clang/libc++ the header
   arrives transitively and compiles. Under GCC/libstdc++ that guarantee does not hold, and this is a
   likely **hard compile error on Linux**. The alias is never used (`fs::` occurrences: **0** in both
   `.cpp` files) — it is dead code that only creates a portability hazard.
2. **`-pthread` missing** while `std::thread` is used. On Linux/GCC this classically yields a link
   error or a runtime `std::system_error` at the first thread launch.
3. **`CXX = g++` hardcoded.** Resolves to Apple clang here, GCC on Linux — a different compiler,
   different optimizer, and different `-O3` performance behind the same published numbers.
4. **Committed binaries are Mach-O arm64.** Unusable on Linux; a reviewer who skips `make` gets
   "cannot execute binary file".
5. **BSD vs GNU CLI divergence.** `gzip`, `bzip2`, `grep` differ in implementation and flags between
   macOS and Linux; timings are not comparable across the two.
6. **`lz4` and `lbzip2` are not installed here**, and neither ships by default on either OS — an
   undeclared, unchecked prerequisite.
7. **No platform detection anywhere.** A grep for `sys.platform`, `platform`, `uname`, `/proc/`,
   `sysctl`, `nproc`, `vm_stat` across all Python returned **zero hits**. Nothing adapts, and nothing
   records which OS produced a result.
8. **Memory semantics differ.** RSS on macOS and RSS on Linux are not the same quantity; the memory
   tables silently assume they are.
9. `/tmp` hardcoded twice (§9) — works on both, but breaks under a read-only or redirected `TMPDIR`.
10. Everything relies on POSIX path separators and the shell; Windows is out of scope, which is fine
    but unstated.

## 15. Hardcoded paths

**Inside the C++ (the highest-impact one):**

| Location | Path | Effect |
|---|---|---|
| `epic-v3.1.cpp:76`, `pic-v3.1.cpp:76` | `"dict.txt"` | CWD-relative, no override flag, no env var. Any CWD other than the repository root → exit 1 |

**Inside Python — dataset paths that escape the repository:**

| Location | Path |
|---|---|
| `run_compression.py:52-61`, `run_decompression.py:48-57`, `run_search.py:68-77`, `run_search_replace.py:51-60` | `"../textFiles/f1.txt"` … `f10.txt` (10 entries each) |
| `run_parallel_benchmarks.py:30` | `"../textFiles/file-parallel.txt"` |
| `check_longest_line.py:9` | `"../textFiles/file-parallel.txt"` |
| `check_gutenberg_books.py:14-15` | `"../standard_ebooks_output/txt_clean"`, `"../standard_ebooks_output/bad_books"` |
| `clean_gutenberg_footer.py:9`, `compression_parallel_debug.py:7` | `"../gutenberg_ebooks/raw"` |

Every one points **outside the repository**, to a sibling directory that ships with nothing and is
documented nowhere.

**Inconsistent even internally:** `make_combined_text_files.py:13-14` uses `standard_ebooks_output/…`
and `gutenberg_ebooks/raw` *without* `../`, while the consumers above use `../`. The two halves of the
pipeline disagree about where the corpus lives.

**Binary paths:** `"./pic-v3.1"` / `"./epic-v3.1"` in `benchmark_utils.py:41-42`, `debug_pic_tic.py:35-36`,
`check_gutenberg_books.py:17`, `compression_parallel_debug.py:17`, `run.py:14-15` — CWD-relative, hardcoded
in six places, no single source of truth.

**Output paths:** `RESULTS_DIR = "."` in all five runners (§8). Log paths `results/logs/{compression,
decompression,search,search_replace,parallel}` and `results/tmp/…` are hardcoded — note these reference a
`results/` directory that **does not exist** in the tree.

**Stale path:** `measureTime.py:39` → `"./pic-v1"`, a binary that no longer exists.

**Absolute paths:** only two, both `/tmp` (§9). No `/Users/afairouz` or other machine-specific absolute
path appears anywhere in the tracked sources — that much is clean.

**No configuration layer exists.** Not one path is settable by CLI flag, environment variable, or
config file. Changing the dataset location means editing four runners by hand.

## 16. Missing licenses

**There is no `LICENSE` file, no `COPYING`, and no `NOTICE`.** Verified by directory listing.
No SPDX identifier or copyright header appears in any `.cpp`, `.h`, `.py`, or `.md` file.

This is a **hard blocker for artifact evaluation**: with no license, the repository is "all rights
reserved" by default, and reviewers have no explicit permission to run, modify, or redistribute it.
The *Available* badge cannot be awarded, and the code is currently non-reusable in the legal sense
despite being on a public-facing remote.

Three separate licensing questions are open, and only the first is about the authors' own code:

1. **The authors' code** — no license chosen (C++, Python, Makefile, docs).
2. **`dict.txt` and `backup_versions/unigram_freq_bk.csv`** — derived from a Kaggle dataset
   (`pic-v3.1.cpp:24`: `rtatman/english-word-frequency`). The upstream terms, retrieval date, and
   whether redistribution of a derived form is permitted are all **unstated**. A 2.7 MB derived data
   file is being redistributed under unknown terms.
3. **The corpora** — Standard Ebooks (public-domain, CC0-dedicated typography) and Project Gutenberg
   (US public domain, with trademark conditions on the PG name/header). The download scripts fetch
   them; no license note or attribution accompanies the fetch.

## 17. Missing citations

1. **No `CITATION.cff`, no `.bib`, no BibTeX block** anywhere.
2. **The paper itself is never identified** — no title, authors, venue, year, DOI, or arXiv ID in any
   file. A reviewer cannot connect the artifact to the publication it supports.
3. **`dict.txt` provenance is a bare URL in a C++ comment block** (`pic-v3.1.cpp:24`), with no author
   credit (Rachael Tatman), no dataset title, no version, no retrieval date, and no license line. The
   equivalent comment is absent from `epic-v3.1.cpp`, so the TIC source cites nothing at all.
4. **Corpus sources are hardcoded URLs, not citations.** `https://standardebooks.org/ebooks` appears
   as `BASE_URL`/`START_URL` in five download scripts; Project Gutenberg appears only as directory
   names (`gutenberg_ebooks/raw`). Neither project is credited in prose or given its requested
   attribution form.
5. **No citations for the baselines.** gzip (DEFLATE, RFC 1951), bzip2 (BWT), lz4, and lbzip2 are
   benchmarked against without a single reference.
6. **No prior-art citation for PIC.** PIC is presented as the comparison scheme with no reference to
   where it was published, and `README.md` describes it as if it were the contribution.
7. **`old_versions/README.md`** references six prompt files as if they were part of a documented
   workflow; none exist here.

## 18. Reproducibility concerns

Ordered by severity.

**Blocking**

1. **The dataset does not exist and cannot be regenerated.** `f1..f10` (~3.3 GB) live in
   `../textFiles/`, outside the repository, with no manifest, no checksums, and no size table. The
   only acquisition path is a **live crawl** of Standard Ebooks and Project Gutenberg whose output
   depends on when it is run — those catalogs grow. Even a perfect re-run yields a *different* corpus,
   so the published numbers are not reproducible even in principle. Compounding this, the pipeline is
   **broken between stage 5 and stage 6** (§13.1) and generates 5 files where the runners need 10.
   **Partly addressed 2026-08-21:** the pipeline is now connected end to end and driven by
   `prepare_datasets.py`, with a manifest at `datasets/manifest.csv` and full documentation in
   `docs/datasets.md`. The underlying blocker stands: the historical corpus was never pinned, so a
   rebuild is *approximate, not exact*, and `file-parallel.txt` still cannot be reconstructed.
2. **No license** (§16) — reviewers lack permission to run the artifact at all.
3. **No dependency declaration** (§6). Seven Python packages and six CLI tools, unpinned and
   undeclared; on this host **all seven packages and two of the six tools are absent**.

**Data-integrity**

4. **The committed results contradict the committed configuration.**
   `run_parallel_benchmarks.py:32` sets `THREAD_COUNTS = [1]`, yet all four `parallel_*_results.csv`
   contain rows for threads **1, 2, 4, 6, 8**. A third value, `DEFAULT_PARALLEL_THREADS = [1, 2, 4, 8, 16]`
   (`benchmark_utils.py:47`), matches neither — and **6 appears in no list in the repository**. The
   code in the artifact provably did not produce the numbers in the artifact.
   **Resolved 2026-08-21** (configuration only, no results regenerated): the author confirmed the
   paper's parallel experiments used **1, 2, 4, 6, and 8 threads**. `DEFAULT_PARALLEL_THREADS`
   (`benchmark_utils.py:50`) is now the single authoritative definition at `[1, 2, 4, 6, 8]`, and
   `run_parallel_benchmarks.py:36` derives `THREAD_COUNTS` from it. The `[1]` and `[1, 2, 4, 8, 16]`
   values are gone. Note this reconciles the *configuration* with the committed CSVs; it does not by
   itself re-verify that the CSVs were produced by this code, since concerns 7 and 10 (no build stamp,
   no environment capture) still stand.
5. **`psutil` failure is silent** (§7). A missing package produces zeroed memory columns and a
   successful-looking run. Every memory table is exposed to this.
6. **The baseline is overwritten in place.** `RESULTS_DIR = "."` in all five runners; a single
   accidental run destroys the published numbers with no backup and no warning.
7. **The committed binaries may not match the committed sources.** Both are tracked *and* Make
   targets, there is no header dependency, and there is no build stamp — so nothing proves
   `epic-v3.1` was built from the current `epic-v3.1.cpp`.

**Methodological**

8. **Means only, no spread.** `NUM_RUNS = 10`, `WARMUP_RUNS = 1`, and only the mean is recorded — no
   standard deviation, min/max, or confidence interval. Overlapping distributions are indistinguishable.
9. **50 ms RSS polling** (`DEFAULT_SAMPLE_INTERVAL = 0.05`) systematically under-reports peak memory
   for fast tools; an lz4 run finishing in ~100 ms is characterized by one or two samples.
10. **No environment capture.** Not one result file records machine, CPU, core count, RAM, OS,
    compiler version, Git commit, or timestamp.
11. **Page-cache policy is undocumented.** A warmup run implies warm-cache measurement; no script
    drops or controls the cache (grep for `purge`/`drop_caches`: **zero hits**), and the policy is
    stated nowhere.
12. **No load isolation.** No check that the machine is otherwise idle; `DELAY_BETWEEN_RUNS_S = 0.5`
    is the only pacing control.
13. **Single-machine, single-architecture results** (macOS/arm64) presented without that qualifier.

**Structural**

14. **No tests, no CI.** Nothing verifies a compress→decompress round trip automatically, so no change
    can be validated beyond "it compiled".
15. **Dead code obscures what actually ran.** `run_search.py` is 1,570 lines of which **617 are
    comments or commented-out code**, with the last live function ending near line 890 and `__main__`
    at 888 — roughly the final 40 % of the file is inert. `run_parallel_benchmarks.py` carries a
    commented duplicate config block at lines 825-860 that disagrees with the live one.
16. **Version ambiguity at the root.** `run_search.py` sits beside `run_search_v1.py` and
    `run_search.py.bk`; five `download_standard_ebooks_to_txt*` variants sit side by side. Nothing marks
    which produced the published results.
17. **`search_outputs/` is stale evidence** — captured by `run_search_v1.py`, the superseded runner,
    yet committed as if it documented the current one.

---

## Summary

The core contribution is sound: both C++ sources compile cleanly at C++17 (11 + 5 warnings under
`-Wall -Wextra`, none fatal), the scheme is real, and `README_benchmark_verification.md` shows genuine
methodological care.

What stands between this and an evaluable artifact is almost entirely packaging and provenance:

| Blocker | Nature |
|---|---|
| No `LICENSE` | Legal — one decision, one file |
| Dataset unobtainable and unpinnable | **Structural — the hardest problem here** |
| Seven Python packages + six CLI tools undeclared | Mechanical |
| Parallel results contradict parallel config | **Data integrity — must be explained or re-measured** |
| `README.md` documents the wrong scheme | Mechanical |
| Binaries tracked; macOS-arm64-only | Mechanical |
| `std::filesystem` alias without its header; no `-pthread` | Portability — likely a Linux build failure |
| Silent `psutil` zero-fill | Correctness of published memory numbers |
| No tests, no CI, no environment capture | Process |

The dataset and the thread-count contradiction are the two that cannot be fixed by tidying — both need
a decision from the authors before any of the mechanical work is worth doing.

---

*Read-only inspection. No repository file was modified; `docs/repository_inspection.md` is the sole
addition. `make` was not run; C++ verification used `g++ -fsyntax-only`, which writes no output.*
