# Artifact Cleanup Manifest

Classification of every tracked file for the public TIC artifact release.

**Prepared:** 2026-08-22 · **Baseline:** `pre-artifact-cleanup` → commit `d42fc7f` · 140 tracked files

> **Partially executed — 2026-08-23.** Four directories have been removed from the release
> artifact with the author's approval: `search_outputs/` (28 files), `debug_pic_tic_outputs/`
> (16), `old_versions/` (10) and `backup_versions/` (5) — **59 files, ~6.1 MB**. Rows for these
> are marked **[REMOVED 2026-08-23]** below.
>
> **Second round executed — 2026-08-24.** Also removed: the **14** `*_results.csv`, the **10**
> `*_table.tex`, the **4** `parallel_*.png`, and the compiled binaries **`epic-v3.1`** and
> **`pic-v3.1`** — 30 further files. Generated output now lands under `results/{raw,tables,figures}`
> and the tree is git-ignored; binaries are built with `make`.
>
> **Third round executed — 2026-08-24.** All **9** external dataset acquisition scripts removed:
> `build_standard_ebooks_catalog.py`, `download_gutenberg_texts.py`,
> `download_standard_ebooks_from_catalog{,_v1}.py` and `download_standard_ebooks_to_txt{,_v1..v4}.py`.
> The artifact no longer downloads or crawls anything; source corpora are external inputs supplied
> locally. `requests`, `beautifulsoup4`, `lxml` and `ebooklib` were dropped with them.
>
> **Fourth round executed — 2026-08-24.** Remaining development-only files removed: `run.py`,
> `measureTime.py`, `compression_parallel_debug.py`, `run_search.py.bk`, `.vscode/settings.json`,
> `run_search_v1.py` and `clean_gutenberg_footer.py` (superseded by `clean_gutenberg_texts.py`,
> which strips both header and footer; the removed helper rewrote the reviewer's corpus in place
> from a hardcoded out-of-repo path). `debug_pic_tic.py` and `check_longest_line.py` are **KEPT**
> as reviewer diagnostics.
>
> **`dict.txt` is KEPT** by decision of the author (see `docs/dictionary.md`).
>
> Everything else in this document remains a **proposal**. Every remaining removal requires explicit
> approval (`CLAUDE.md` §10, §14).

**Recovery.** Every file listed here is recoverable from the `pre-artifact-cleanup` tag:
`git checkout pre-artifact-cleanup -- <path>`

---

## 1. Dependency analysis

Three findings determine the recommendations below.

**1. `plot_parallel_subset.py:41` is a hard dependency on four result CSVs.** It calls
`pd.read_csv(csv_path)` with **no existence guard** and crashes if they are removed. By contrast
`plot_parallel_results.py:75` guards with `os.path.exists()` and skips gracefully.

**2. The benchmark runners do *not* require the committed CSVs.** `_load_previous_df()` returns
`None` when the file is absent, and all four file-indexed runners ship with
`FORCE_*_TOOLS = set(TOOLS)`, making `rerun_all` true — previous values are never consulted.
Removing the CSVs is safe for a full run, but silently disables the **selective-rerun** feature
(re-measuring only `{"lz4"}`, per the commented-out variants).

**3. `pre-process-dict.py` is already broken.** It reads `unigram_freq.csv`, a filename that does
not exist in the repository. The only tracked copy is `backup_versions/unigram_freq_bk.csv`.

`run_parallel_benchmarks.py` reads CSVs at lines 614-659, but only ones it wrote itself moments
earlier (write 791-806, plot 811+). Not a dependency.

---

## 2. KEEP — required for the artifact

| Group | Files |
|---|---|
| Source + headers | `epic-v3.1.cpp`, `epic-v3.1.h`, `pic-v3.1.cpp`, `pic-v3.1.h` |
| Build | `Makefile` |
| Runners | `run_compression.py`, `run_decompression.py`, `run_search.py`, `run_search_replace.py`, `run_parallel_benchmarks.py`, `benchmark_utils.py` |
| Configuration | `dataset_config.py`, `dependencies.py`, `requirements.txt` |
| Dataset preparation | `prepare_datasets.py`, `make_combined_text_files.py`, `build_standard_ebooks_catalog.py`, `download_standard_ebooks_from_catalog.py`, `download_gutenberg_texts.py`, `clean_gutenberg_texts.py`, `clean_gutenberg_footer.py`, `check_gutenberg_books.py`, `pre-process-dict.py` |
| Install + validation | `install_dependencies.sh`, `check_environment.py`, `smoke_test.py` |
| Figures | `plot_parallel_results.py` |
| Documentation | `README.md` (rewrite), `README_benchmark_verification.md`, `docs/*.md` |
| Manifests / config | `datasets/manifest.csv`, `.gitignore` |

---

## 3. REMOVE — generated experimental outputs

| Path | Category | Reason | Safe to regenerate? | Needed by reviewer? | Recommendation |
|---|---|---|---|---|---|
| `search_outputs/` (28 files, 896 KB) **[REMOVED 2026-08-23]** | 2 | Run residue from superseded `run_search_v1.py`. 12 files are 0 bytes; 5 are duplicate 173 KB grep dumps. Also bundles corpus text (§6) | Yes, by rerunning search | No | **REMOVE** |
| `debug_pic_tic_outputs/` (16 files, 40 KB) **[REMOVED 2026-08-23]** | 2 | Committed `tempfile.mkdtemp()` directory with a random-token name (`debug_pic_tic_qrz8ndi6`) | Yes, via `debug_pic_tic.py` | No | **REMOVE** |
| 14 × `*_results.csv` (56 KB) | 2 | Generated benchmark results | Only by rerunning the full suite on ~3.3 GB of data | **Yes** | **RETAIN, relocated** — see §7 |
| 10 × `*_table.tex` (40 KB) | 2 | Generated from the CSVs | Same | **Yes** | **RETAIN, relocated** — see §7 |
| 4 × `*.png` (592 KB) | 2 | Generated from the parallel CSVs | Same | **Yes** | **RETAIN, relocated** — see §7 |

---

## 4. REMOVE — build artifacts

| Path | Category | Reason | Safe to regenerate? | Needed by reviewer? | Recommendation |
|---|---|---|---|---|---|
| `epic-v3.1` (126 KB) | 3 | Mach-O **arm64** binary; unusable on Linux. Also a Make target, so any build dirties the tree | Yes — `make` | No | **REMOVE**, add to `.gitignore` |
| `pic-v3.1` (143 KB) | 3 | Same | Yes — `make` | No | **REMOVE**, add to `.gitignore` |

---

## 5. REMOVE — obsolete / development

| Path | Category | Reason | Safe to regenerate? | Needed by reviewer? | Recommendation |
|---|---|---|---|---|---|
| `test-code/` | 4 | **Already removed** — see §8 | Yes, from Git history | No | **No action**; fix the stale `README.md:25` reference |
| `run_search_v1.py` | 4 | Superseded by `run_search.py`; still points at `../textFiles/`; produced the stale `search_outputs/` | Git history | No | **REMOVE** |
| `run_search.py.bk` | 4 | Editor backup | Git history | No | **REMOVE** |
| `run.py` | 4 | Ad-hoc scratch measurement; unreferenced by the pipeline | Git history | No | **REMOVE** |
| `measureTime.py` | 4 | Scratch timing; line 39 points at `./pic-v1`, which no longer exists | Git history | No | **REMOVE** |
| `compression_parallel_debug.py` | 4 | Debug loop; hardcodes `/tmp/test.tic` and `../gutenberg_ebooks/raw` | Git history | No | **REMOVE** |
| `download_standard_ebooks_to_txt.py` **[REMOVED 2026-08-24]** | 4 | **Not invoked** by `prepare_datasets.py`, which uses the `_from_catalog` route | Git history | No | **REMOVE** |
| `download_standard_ebooks_to_txt_v1.py` **[REMOVED 2026-08-24]** | 4 | Unreferenced anywhere | Git history | No | **REMOVE** |
| `download_standard_ebooks_to_txt_v2.py` **[REMOVED 2026-08-24]** | 4 | Unreferenced anywhere | Git history | No | **REMOVE** |
| `download_standard_ebooks_to_txt_v3.py` **[REMOVED 2026-08-24]** | 4 | Unreferenced anywhere | Git history | No | **REMOVE** |
| `download_standard_ebooks_to_txt_v4.py` **[REMOVED 2026-08-24]** | 4 | Unreferenced anywhere | Git history | No | **REMOVE** |
| `download_standard_ebooks_from_catalog_v1.py` **[REMOVED 2026-08-24]** | 4 | Superseded by the non-`_v1` version | Git history | No | **REMOVE** |
| `backup_versions/` (5 files, 4.9 MB) **[REMOVED 2026-08-23]** | 4 | Manual `.bk` snapshots, two dated `Makefile` copies, and `unigram_freq_bk.csv`. Git already holds this history | Git history | No | **REMOVE** (see §6 for the CSV) |
| `.vscode/settings.json` | 4 | Personal editor config, incl. `"C_Cpp.errorSquiggles": "disabled"`. Already named in `.gitignore:9` but tracked, so the rule never applies | n/a | No | **REMOVE** |

---

## 6. REMOVE OR REPLACE — licensing / provenance

See `docs/licensing.md` for the full analysis and cited sources.

| Path | Category | Reason | Safe to regenerate? | Needed by reviewer? | Recommendation |
|---|---|---|---|---|---|
| `backup_versions/unigram_freq_bk.csv` (4.8 MB) **[REMOVED 2026-08-23]** | 5 | Verbatim third-party dataset. **License could not be reliably established** — Kaggle records "Other (specified in description)", and the MIT reference covers the *generating code*, not the data. Root corpus (LDC2006T13) is licence-gated. Redundant with `dict.txt` | From Kaggle | No | **REMOVE** |
| `dict.txt` (2.7 MB) | 5 | Proven derivative of the same dataset: lines 18→end are byte-identical to column 1 of the CSV, with 17 punctuation entries prepended. Same unresolved licence | Via Kaggle + `pre-process-dict.py` | **YES — required at runtime** | **REPLACE** with an acquisition script + SHA-256 |
| Corpus text in `search_outputs/` (~865 KB) **[REMOVED 2026-08-23]** | 5 | Literary prose, identifiable as *The Blue Castle* (1926). No provenance recorded; PG/SE markers stripped by the cleaning pipeline | Yes | No | **REMOVE** (counted in §3) |

---

## 7. The published baseline — recommendation NOT taken (superseded 2026-08-24)

> **Decision:** the author chose removal. All 28 files were deleted on 2026-08-24; the scripts that
> regenerate them are kept, and the historical copies remain at `pre-artifact-cleanup`. The
> recommendation below is retained as the record of the argument that was considered and overruled.

### Original recommendation

The 14 result CSVs, 10 LaTeX tables and 4 PNG figures (688 KB total) are generated outputs, but
**the recommendation is to retain them, relocated to `results/published/`.**

Reasoning:

1. They are the paper's claimed results. Comparing a reproduction against them is the core artifact-
   evaluation task; deleting them removes the reference point.
2. They cannot be regenerated without the ~3.3 GB datasets, which are themselves not distributable
   (`docs/datasets.md` §10).
3. `docs/repository_inspection.md` §8 and `CLAUDE.md` §10 both designate them the protected
   published baseline.
4. Relocation also resolves the `plot_parallel_subset.py` hard dependency (§1).

The real defect is not their presence but that every runner sets `RESULTS_DIR = "."`, so any run
silently overwrites them. **Relocating fixes that; deleting discards the baseline to work around a
path bug.**

This is the author's decision. If they should be removed instead, reclassify all 28 files as
category 2 REMOVE.

---

## 8. `test-code/` — verification result

**Status: already removed. It is not a cleanup candidate.**

`test-code/` does **not exist** in the working tree, is **not tracked at `HEAD`**, and is **not
present in the `pre-artifact-cleanup` tag** (`git ls-tree -r pre-artifact-cleanup | grep test-code/`
returns 0 results). It was deleted in commit `33d95fb` ("Initial TIC artifact repository state",
2026-08-17), before any of the current artifact-preparation work.

### Dependency verification

All five required checks were run against the current tree:

| # | Check | Result |
|---|---|---|
| 1 | No active build process references `test-code/` | **PASS** — no match in `Makefile` or `install_dependencies.sh` |
| 2 | No Makefile target depends on it | **PASS** — targets are `all`, `pic-v3.1`, `epic-v3.1`, `pic`, `epic`, `warnings`, `clean`; prerequisites are only the `.cpp`/`.h` sources |
| 3 | No Python script invokes it | **PASS** — zero matches across all 33 `.py` files |
| 4 | No artifact-required documentation depends on it | **PASS with one defect** — see below |
| 5 | No smoke test or validation script requires it | **PASS** — no match in `smoke_test.py`, `check_environment.py`, `prepare_datasets.py`, `dependencies.py`, `dataset_config.py` |

**Classification:** REMOVE — development/testing directory not required for the public artifact.
Already satisfied; no deletion action remains.

### Contents when it last existed (commit `d7777ad`, 2026-04-19)

```
test-code/Makefile              test-code/test.cpp
test-code/Makefile_Backup       test-code/test1.txt
test-code/multithread           test-code/test_generate_file        (compiled binary)
test-code/multithread.cpp       test-code/test_generate_file.cpp
test-code/output.bin            test-code/output_text.txt
test-code/test                  (compiled binary)
```

Scratch C++ experiments plus their compiled binaries and output files. `test_generate_file.cpp`
writes eight hard-coded bytes to `output.bin` — a binary-format debug tool, unrelated to the TIC or
PIC schemes. None of it is a test suite in the automated sense; the repository still has no
automated tests (`smoke_test.py` is the first executable correctness check).

### Reason for removal

Development scratch work with no role in building, running, validating or reproducing the artifact.
It also contained compiled binaries and generated output, which are excluded on their own terms
(§4, §3).

### Reproducible from Git history?

**Yes, fully.** The last commit containing it is `d7777ad` (parent of `33d95fb`):

```bash
git show d7777ad:test-code/test.cpp          # inspect one file
git checkout d7777ad -- test-code/           # restore the whole directory
```

### Does deleting it affect any reviewer workflow?

**No.** It is already absent from the tree and from the preservation tag, so no reviewer of the
current artifact has ever seen it. No build, runner, dataset stage, validation script or smoke test
references it.

### Outstanding defect

`README.md:25` still advertises the directory:

> `1. test-code: includes all the test C++ files for testing functions.`

This documents a directory that has not existed since 2026-08-17. It is a **documentation defect,
not a cleanup item**, and is already recorded in `docs/repository_inspection.md` §11.1. It must be
fixed in the README rewrite. `docs/repository_inspection.md:254-255` already states correctly that
`test-code/` does not exist.

---

## 9. REVIEW — ambiguous, proposed KEEP

| Path | Why ambiguous | Recommendation |
|---|---|---|
| `old_versions/` (10 files, 288 KB) **[REMOVED 2026-08-23]** | Superseded C++; `CLAUDE.md` §4 marked it "Historical; do not modify". Originally recommended KEEP | **REMOVED** — the author overrode the KEEP recommendation and approved deletion. Preserved at `pre-artifact-cleanup` |
| `plot_parallel_subset.py` | Dev utility writing **untracked** `*_1_2_4_6_8.png`; unguarded `read_csv` | **KEEP but fix the guard**, or remove. Its `THREADS_TO_KEEP = [1,2,4,6,8]` independently documents the real thread counts |
| `pre-process-dict.py` | Currently broken (reads a nonexistent `unigram_freq.csv`) | **KEEP** — becomes essential if `dict.txt` ships as an acquisition script. Must be fixed |
| `check_longest_line.py` | Diagnostic for `file-parallel.txt` | **KEEP** — the only surviving evidence that the parallel input's line structure was validated |
| `debug_pic_tic.py` | Debug-only utility | **KEEP** — genuinely useful for diagnosing a TIC/PIC mismatch |
| `clean_gutenberg_texts.py`, `clean_gutenberg_footer.py`, `check_gutenberg_books.py` | Documented as pipeline stages 4-5 in `docs/datasets.md` but **not invoked** by `prepare_datasets.py` | **KEEP** — needed for Gutenberg cleaning; fix the wiring gap, do not delete |
| `README.md` | Stale and inaccurate | **KEEP** — rewrite, do not remove |

---

## 10. Dependencies that must be fixed before removal

| # | Blocker | Fix required first |
|---|---|---|
| 1 | `plot_parallel_subset.py:41` — unguarded `pd.read_csv` on four parallel CSVs | Add an existence guard, retain/relocate the CSVs, or drop the script |
| 2 | `dict.txt` — hardcoded `string dictFilename = "dict.txt"` at `epic-v3.1.cpp:76` and `pic-v3.1.cpp:76`, resolved against the CWD | Ship an acquisition script + checksum; update `check_environment.py`, `smoke_test.py` and `prepare_datasets.py` messaging; fix `pre-process-dict.py` |
| 3 | Removing the 14 CSVs disables selective rerun (`FORCE_*_TOOLS` narrowing) | Behaviour change only — document it, or retain the CSVs |
| 4 | `README.md` references `measureTime.py` and `test-code/`, neither of which belongs in the artifact | Rewrite the README after cleanup |
| 5 | ~~`docs/*.md` reference `search_outputs/`, `backup_versions/` and `run_search_v1.py` as existing paths~~ | **DONE 2026-08-23** — status banners added to `docs/repository_inspection.md` and `docs/licensing.md`; historical findings retained verbatim |
| 6 | Binaries are Make targets **and** tracked files | Untrack, then add to `.gitignore` |

---

## 11. Deletions that would break the artifact today

| Path | Breakage |
|---|---|
| **`dict.txt`** | **Total.** Both binaries exit 1 immediately. Every experiment and the smoke test stop working. Must not be removed before the replacement mechanism is in place |
| `parallel_time_results.csv`, `parallel_memory_results.csv`, `parallel_search_results.csv`, `parallel_replace_results.csv` | `plot_parallel_subset.py` crashes on an unguarded `read_csv` |

Nothing else in the removal list has a live consumer. `test-code/` has **none** — verified in §8.

---

## 12. Totals

Of **140 tracked files**:

| Disposition | Count | Size |
|---|---|---|
| REMOVE — generated outputs (`search_outputs/`, `debug_pic_tic_outputs/`) | 44 | ~936 KB |
| REMOVE — build artifacts (2 binaries) | 2 | 272 KB |
| REMOVE — obsolete / development | 18 | ~5.1 MB |
| REMOVE OR REPLACE — licensing (`dict.txt`) | 1 | 2.7 MB |
| **Total proposed for removal** | **65** | **~9.0 MB** |
| RETAIN, relocated — published baseline | 28 | 688 KB |
| REVIEW, proposed KEEP (`old_versions/` etc.) | 10 | 288 KB |
| KEEP — required | 37 | — |

`test-code/` is **not** counted: it is already absent (§8).

---

## 13. Related

- `docs/repository_inspection.md` — full inspection, 30 findings
- `docs/licensing.md` — licensing and redistribution analysis
- `docs/datasets.md` — dataset provenance and preparation
- `docs/environment.md` — dependencies, build and validation
