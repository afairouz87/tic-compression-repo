# Benchmark Datasets

How the TIC/PIC benchmark inputs `f1.txt` … `f10.txt` are obtained, built, and validated.

**Status:** the datasets are **not distributed with this repository** (≈3.3 GB) and **are not
present in this working copy**. Everything below describes how to rebuild them and, just as
importantly, the limits on how faithfully they can be rebuilt.

> **Historical vs. regenerated.** The results committed in this repository were produced from a
> specific corpus snapshot that was never pinned. A dataset you build today is a *regenerated*
> dataset, statistically similar but **not byte-identical** to the historical one. See
> [Known limitations](#known-limitations) before comparing new numbers against the published tables.

---

## 1. Quick start

```bash
# from the repository root
python3 prepare_datasets.py check          # dependencies, local sources, disk space
python3 prepare_datasets.py                # check -> build -> verify
python3 prepare_datasets.py verify --sha256   # checksum every dataset
```

**Nothing is downloaded.** The source corpora are external inputs you supply locally (§3). Every
stage fails with a non-zero exit code rather than continuing with an incomplete dataset.

---

## 2. Directory structure

The canonical dataset directory is **`datasets/`**, relative to the repository root:

```
tic-compression-repo/
├── datasets/
│   ├── f1.txt … f10.txt        the benchmark inputs (git-ignored, ≈3.3 GB total)
│   ├── file-parallel.txt       input for the parallel experiments (see §7)
│   ├── manifest.csv            machine-readable inventory (tracked)
│   └── manifests/
│       └── fN.txt.sources.txt  the ordered source files that went into each dataset
├── standard_ebooks_output/     acquisition stage output (git-ignored)
│   ├── catalog.jsonl
│   ├── epub/
│   └── txt_clean/              ← cleaned Standard Ebooks text, read by the combine stage
└── gutenberg_ebooks/
    └── raw/                    ← Project Gutenberg text, read by the combine stage
```

**Resolution order** (`dataset_config.py`):

1. `$TIC_DATASET_DIR`, if set
2. `datasets/` — canonical
3. `../textFiles/` — legacy location used for the published results, honoured so an existing
   local copy need not be moved
4. `datasets/` — default

All paths are repository-relative. No absolute or machine-specific path appears in the pipeline.
Run every script from the repository root: the compiled binaries resolve `dict.txt` against the
working directory, so any other CWD fails.

---

## 3. Source corpora

**This repository does not download, crawl or redistribute either corpus.** The acquisition scripts
that once did were removed on 2026-08-24: a public artifact should not depend on live, changing
external catalogs. You obtain the text yourself and place it locally.

| Corpus | Expected local location | Approximate volume used |
|---|---|---|
| [Standard Ebooks](https://standardebooks.org) | `standard_ebooks_output/txt_clean/*.txt` — cleaned plain text, one file per book | ~750 MB |
| [Project Gutenberg](https://www.gutenberg.org) | `gutenberg_ebooks/raw/*.txt` — raw text; clean with `clean_gutenberg_texts.py` | remainder, up to ~1.2 GB |

Either directory alone is enough for the smaller datasets; `f10` (769 MB) needs roughly 769 MB in
total, read Standard Ebooks first, then Gutenberg.

Both are public-domain literary corpora. Standard Ebooks releases its typography and markup under
CC0; Project Gutenberg texts are public domain in the US, with trademark conditions attached to the
Project Gutenberg name and header. **Neither corpus is redistributed here.** The repository as a
whole still has no `LICENSE`; see the inspection report.

---

## 4. Preparation workflow

```
   (you supply)                            local corpora  -> standard_ebooks_output/txt_clean/
                                                          -> gutenberg_ebooks/raw/
1. clean_gutenberg_texts.py                strip PG header/footer    -> cleaned text
2. clean_gutenberg_footer.py               strip trailing PG footer
3. check_gutenberg_books.py                screen unusable books
4. make_combined_text_files.py             combine + size            -> datasets/f1..f10
5. prepare_datasets.py verify              count, sizes, checksums   -> datasets/manifest.csv
```

Every stage is local and offline. Stages 4–5 run under `prepare_datasets.py`; stages 1–3 are helper
scripts you run as needed on your own Gutenberg copy.

### The gap this replaces

Before this change the pipeline did not connect end to end:

- `make_combined_text_files.py` wrote to `combined_text_files/`, while every runner read
  `../textFiles/` — **nothing bridged the two**.
- `TARGET_FILES_MB` had `f6`–`f10` **commented out**, so the combine stage produced **five**
  datasets while the runners were configured for **ten**.
- the Gutenberg downloader defaulted to `data/raw`, but the combine stage read
  `gutenberg_ebooks/raw` and `clean_gutenberg_footer.py` read `../gutenberg_ebooks/raw` — three
  conventions for one directory.

All three are now resolved: one canonical directory, ten targets restored, and a single documented
local location per corpus.

---

## 5. The datasets

| Dataset | Target size | Target bytes |
|---|---|---|
| `f1.txt`  | 50 MB  | 52,428,800 |
| `f2.txt`  | 100 MB | 104,857,600 |
| `f3.txt`  | 137 MB | 143,654,912 |
| `f4.txt`  | 150 MB | 157,286,400 |
| `f5.txt`  | 200 MB | 209,715,200 |
| `f6.txt`  | 347 MB | 363,855,872 |
| `f7.txt`  | 400 MB | 419,430,400 |
| `f8.txt`  | 500 MB | 524,288,000 |
| `f9.txt`  | 634 MB | 664,797,184 |
| `f10.txt` | 769 MB | 806,354,944 |

"MB" means **MiB** (1024 × 1024 bytes) throughout, matching `MB = 1024 * 1024` in the pipeline and
the `Original Size (MB)` column of `cr_results.csv`. Total: **3,287 MB ≈ 3.3 GB**.

### Construction

Source files are collected from `standard_ebooks_output/txt_clean/` then `gutenberg_ebooks/raw/`,
each directory sorted by filename, and concatenated with a `\n\n` separator after per-file
normalisation (ASCII folding, CRLF→LF, non-printable stripping, sentence-per-line splitting,
1000-character line wrapping). **The normalisation functions are unchanged from the committed
version and must stay that way** — altering them changes the datasets' statistical properties and
invalidates comparison with the published results.

Two independent choices control the result:

| Option | Values | Default |
|---|---|---|
| `--mode` | `nested` \| `sequential` | `nested` |
| sizing | `--exact` \| `--whole-files` | `--exact` |

**`nested`** restarts from the first source file for every output, so `f1` is a byte-exact prefix of
`f2`, which is a prefix of `f3`, and so on. Only ~769 MB of distinct source text is needed.

**`sequential`** continues where the previous output stopped, producing ten disjoint datasets and
requiring ~3.3 GB of distinct source text.

**`--exact`** trims the final source file so the output is exactly its target size.
**`--whole-files`** stops at the first whole source file that reaches the target, overshooting by up
to one book.

---

## 6. Which construction produced the published results?

`nested` is used by default, on three independent pieces of evidence:

1. **The committed script does it.** `make_combined_text_files.py` reset the source cursor inside the
   per-output loop (`file_index = 0  # restart source files for every output file`). The
   `sequential` variant survived only as a commented-out block, i.e. as the superseded approach.
2. **The corpus budgets only fit `nested`.** The acquisition stages target ~750 MB (Standard Ebooks)
   plus ~1200 MB (Gutenberg) ≈ 1.95 GB. `sequential` needs 3.29 GB of *distinct* text — more than
   the pipeline ever acquires. `nested` needs only 769 MB.
3. **The published results show the corpus boundary exactly where `nested` predicts it.** Sources are
   read Standard Ebooks first (~750 MB), then Gutenberg. Under `nested`, `f1`–`f9` (≤634 MB) stay
   entirely inside Standard Ebooks while `f10` (769 MB) is the only dataset that crosses into
   Gutenberg. The committed results show a discontinuity at precisely `f10` and nowhere else:

   | | f1–f9 | f10 |
   |---|---|---|
   | Plaintext entropy | 4.430 – 4.436 | **4.479** |
   | TIC compression ratio | 1.818 – 1.828 | **1.780** |

   Nine datasets agreeing to ±0.006 and the tenth breaking away is what mixing in a second corpus at
   ~750 MB looks like.

### What is *not* recoverable

- **Sizing is undetermined.** `run_compression.py` records the size as
  `round(bytes_to_mb(...))` — an outer `round()` with no `ndigits`, which snaps the value to the
  nearest **integer** MB before it is written with three decimals. Every `.000` in the
  `Original Size (MB)` column is therefore an artefact of that rounding and carries **no evidence**
  about the true byte sizes. Historical files may have been exact or may have overshot by up to one
  book; the committed CSVs cannot distinguish the two. `--exact` is the default because it is
  deterministic and reproduces the stated sizes; `--whole-files` reproduces the literal behaviour of
  the committed script. `utf8_trim_to_bytes()` existed in the committed script but was never called,
  which is consistent with either history.
- **The corpus snapshot.** Which books, in which order, from which crawl date — unrecorded.
- **Whether Gutenberg was included at all.** The committed source list carried the comment
  `# change/remove if needed` against the Gutenberg entry.

None of these gaps have been guessed at. Where a value could not be recovered it is marked
`unavailable` in the manifest rather than invented.

---

## 7. `file-parallel.txt` — the parallel benchmark input

`run_parallel_benchmarks.py` takes a **single input file**, separate from `f1`–`f10`. The file behind
the published parallel results is called `file-parallel.txt`.

### 7.1 Provenance: unknown

An exhaustive search of the working tree and of the **entire Git history** (all 40+ commits, every
blob ever tracked, plus dangling and unreachable objects) established the following.

**Verified** — established directly by repository evidence:

- **No script produces it.** Nothing in the repository creates, concatenates, copies, renames, or
  truncates a file of this name. `make_combined_text_files.py` produces only `f1`–`f10`.
- **It was never tracked in Git.** No commit in any branch ever contained a file named
  `file-parallel.txt`, and no `git fsck` dangling object holds one.
- **The name appears in exactly one commit** — `33d95fb`, the artifact commit — and only as a
  configuration string in `run_parallel_benchmarks.py` and `check_longest_line.py`.
- **No documentation describes it.** `README_benchmark_verification.md` walks through
  `run_parallel_benchmarks.py` step by step (§9) and lists the required input files (§3.2), yet
  never mentions this file. `README.md` does not either.
- **`run_parallel_benchmarks.py` has no history.** It first appears, complete, in `33d95fb`, so
  there is no earlier revision in which the input might have been defined differently.

**Strongly supported** — multiple independent lines of evidence agree:

- **It is comparable in size to `f10`.** Four independent operations were measured on it at one
  thread and can be compared against the same operations across `f1`–`f10`, all of which scale
  near-linearly in input size (R² ≥ 0.992):

  | Operation | `f10` (769 MB) | parallel @ 1 thread | ratio | implied size |
  |---|---|---|---|---|
  | TIC compression | 25.964 s | 26.571 s | 1.023 | ~794 MB |
  | TIC decompression | 9.672 s | 9.592 s | 0.992 | ~779 MB |
  | TIC lookup-and-replace | 3.845 s | 3.929 s | 1.022 | ~769 MB |
  | TIC search | 0.881 s | 0.975 s | 1.107 | ~881 MB |

  Three of the four agree within 2.5 %. This is supporting evidence about *magnitude only*, and the
  implied sizes span 769–881 MB — they do not converge on a value, so **no size is recorded**. The
  manifest leaves `actual_bytes` as `unavailable` rather than carrying a number derived from timing.

- **It was purpose-prepared for the parallel experiment.** `check_longest_line.py` exists solely to
  measure the longest line of this file. TIC divides work between threads **by line**
  (`epic-v3.1.cpp`, *"Divide lines among threads"*), so line structure directly bounds how evenly
  work can be split. A dedicated tool pointed at exactly this file shows its line structure was
  checked deliberately.

**Plausible** — consistent with the evidence, but not established by it:

- It is a copy or rename of `f10`, or a separately built file of similar size. The timing data cannot
  distinguish these: any ~790 MB file of similar text would look the same. The fact that the runner
  was pointed at a distinctly named file rather than at `f10` is *suggestive* of a separate file, but
  it is not evidence.
- It came from the same normalisation pipeline as `f1`–`f10` (which wraps lines at 1000 characters),
  which would explain why a longest-line check was worth running.

**Unknown** — no evidence either way:

- Its exact size, its SHA-256, which corpus or books it contains, whether it is a concatenation, and
  when it was built.

**Nothing above has been guessed at.** Where provenance could not be established it is recorded as
`unknown` in `dataset_config.PARALLEL_DATASET_INFO` and as `unavailable` in the manifest.

### 7.2 Historical paper input vs. reproducible artifact input

These are deliberately kept distinct:

| | **Historical paper input** | **Reproducible artifact input** |
|---|---|---|
| File | `file-parallel.txt` | any file the reviewer supplies |
| Provenance | unknown, not reconstructible | chosen and stated by the reviewer |
| Reproduces the published parallel tables? | it produced them | **no** |
| How it is selected | default path | `--input PATH` |

The runner **never substitutes a dataset on its own.** If the historical input is absent it fails
with a non-zero exit code and explains the options. Silently benchmarking a different file would
redefine the experiment without saying so.

### 7.3 How the runner receives its input

```bash
# default: datasets/file-parallel.txt
python3 run_parallel_benchmarks.py

# reviewer-supplied input (recommended when the historical file is unavailable)
python3 run_parallel_benchmarks.py --input datasets/f10.txt

# report size and checksum, then exit without benchmarking
python3 run_parallel_benchmarks.py --input datasets/f10.txt --sha256 --describe-only
```

| Flag | Effect |
|---|---|
| `--input PATH` | Input for the parallel experiments. Defaults to `datasets/file-parallel.txt` |
| `--sha256` | Report the input's SHA-256 before benchmarking |
| `--describe-only` | Validate and describe the input, then exit without running anything |

`check_longest_line.py --input PATH` accepts the same override.

### 7.4 Validation behaviour

Before any measurement, the runner:

1. **fails loudly** if the input is missing, is not a regular file, or is empty — non-zero exit,
   message naming the path and offering `--input`;
2. **reports the exact byte size** (and MB) of the input;
3. **reports the SHA-256** when `--sha256` is given;
4. **labels the provenance** — `historical input; provenance unknown` when the file is named
   `file-parallel.txt`, otherwise `reviewer-supplied substitute; results are NOT comparable to the
   published parallel tables`;
5. **never falls back** to another dataset.

Tool and directory checks (`lbzip2`, log/tmp directories) are separate, so `--describe-only` neither
requires `lbzip2` nor creates any directory.

### 7.5 What to do if the historical input is unavailable

It will be unavailable to essentially every reviewer — it is not distributed and cannot be rebuilt.

**Recommended:** run against `f10`, the largest pinned dataset and the closest in magnitude to
whatever the historical input was:

```bash
python3 prepare_datasets.py            # build datasets/f1..f10
python3 run_parallel_benchmarks.py --input datasets/f10.txt --sha256
```

This is a **reproducible artifact input**, not the historical one. Any results must be reported as
such — the thread-scaling *trends* are the meaningful comparison, not the absolute seconds. Record
the input path, byte size, and SHA-256 that the runner prints alongside any numbers you publish.

Alternatively supply any other file with `--input`. Do not rename a substitute to
`file-parallel.txt`: that would make a reviewer-supplied file report itself as the historical input.

## 8. Manifest

`datasets/manifest.csv` is regenerated by `prepare_datasets.py verify` (or `manifest`):

| Column | Meaning |
|---|---|
| `dataset` | file name |
| `target_mb`, `target_bytes` | intended size |
| `actual_bytes`, `actual_mb` | measured size, or `unavailable` |
| `source_corpus` | corpora, in read order |
| `source_files` | count, pointing at `manifests/<name>.sources.txt` |
| `construction` | mode and sizing used |
| `sha256` | checksum, or `unavailable` |
| `notes` | anything qualifying the row |

Values that cannot be measured are written literally as `unavailable`. **Checksums are never
fabricated** — a dataset that is not on disk gets `unavailable`, not a placeholder hash. The manifest
currently in the repository has `unavailable` in every measured column, because no dataset is
present in this working copy.

---

## 9. Validation

```bash
python3 prepare_datasets.py verify            # count + sizes, refresh manifest
python3 prepare_datasets.py verify --sha256   # also checksum (reads every byte)
```

`verify` checks that exactly **10** datasets are present, reports each actual size against its
target, warns if `file-parallel.txt` is absent, and rewrites the manifest. A missing dataset is a
**hard error** — the intent is that a partial dataset set can never be benchmarked silently.

### Checksum procedure

Checksums are SHA-256 over the raw bytes, computed in 8 MB blocks. To confirm a rebuild matches a
previous one, keep the earlier `manifest.csv` and diff the `sha256` column:

```bash
cp datasets/manifest.csv /tmp/manifest.before.csv
python3 prepare_datasets.py verify --sha256
diff <(cut -d, -f1,9 /tmp/manifest.before.csv) <(cut -d, -f1,9 datasets/manifest.csv)
```

Identical checksums mean the rebuild is byte-identical. They will **not** match across different
corpus snapshots.

---

## 10. Known limitations

1. **Exact historical reconstruction is impossible.** Standard Ebooks and Project Gutenberg are live,
   growing catalogs. A crawl today returns a different set of books in a different order, so a
   regenerated `f1`–`f10` is **approximate, not exact**. Making reconstruction exact requires
   pinning the corpus — a file list with per-book identifiers and checksums, or an archived copy of
   the source text — none of which was recorded.
2. **No pinned manifest for the historical datasets.** No book list, no crawl date, no checksums.
3. **Historical sizing is undetermined** (§6), because of the integer-rounding artefact.
4. **`file-parallel.txt` cannot be reconstructed** (§7). Its provenance is unknown and no
   evidence in the repository establishes it. The parallel experiments can still be run, but
   only against an explicitly supplied substitute whose results are not comparable to the
   published parallel tables.
5. **Neither the datasets nor the source corpora are redistributed.** A reviewer must obtain the
   corpora independently and then rebuild — ~3.3 GB of output, plus the source text itself.
   This artifact provides the processing pipeline, not the data.
6. **Regenerated results will not match the published tables exactly.** Compression ratios and
   entropies should land close, but any comparison must state that the input corpus differs.
7. **Rebuilding does not validate the published numbers.** There is still no build stamp or
   environment capture tying a result file to a commit, a machine, or a dataset.

### Making this reproducible in future runs

Record, alongside any new result set: the dataset `manifest.csv` (with checksums), the Git commit,
the machine and OS, the compiler version, and the thread counts.

---

## 11. Related

- `dataset_config.py` — authoritative dataset layout
- `prepare_datasets.py` — pipeline entry point
- `make_combined_text_files.py` — combine stage
- `docs/repository_inspection.md` — full artifact inspection
- `README_benchmark_verification.md` — benchmark verification checklist
