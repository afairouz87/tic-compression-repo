# Artifact Readiness Audit

Independent evaluation of the TIC artifact for public artifact evaluation.

**Date:** 2026-08-24 · **Commit audited:** `6c2f42108e11665a4128b930076c2bb48f1ed98e`
**Method:** fresh `git clone` of `claude/repository-cleanup` from `github.com/afairouz87/tic-compression-repo`
into an empty directory, then the documented workflow followed from `README.md` and `LICENSE` alone.

> **Overall status at audit time: Minor documentation improvements recommended.**
> The artifact builds, validates and is correctly licensed from a clean checkout on both claimed
> platforms. Two genuine documentation defects were found (§1.3, §4.1). Neither prevented
> evaluation, and neither was fixed by the audit itself — it changed no file other than this one.
>
> **Update 2026-08-24 — both findings resolved.** §1.3 and §4.1 were addressed in a follow-up
> documentation change; see the resolution notes in each. The findings below are retained verbatim
> as the record of what was found. Recommendations 3 and 4 in §9 (CI improvements) remain open by
> choice, and the standing caveats in §9 are unchanged.

---

## 1. Fresh-clone simulation

Clone: 39 tracked files, 26 MB, no submodules, no post-clone setup.

### 1.1 What worked

Starting from `README.md` and `LICENSE` only, the following were answerable without ambiguity:

| Question | Answer found | Verified |
|---|---|---|
| What is the artifact? | Title and Overview: TIC is a dictionary-based plain-text incremental compression scheme supporting lookup and lookup-and-replace on compressed data; PIC is the baseline | — |
| How do I install it? | `./install_dependencies.sh` → `python3 check_environment.py` | ✔ |
| How do I validate the environment? | `check_environment.py`, with PASS/FAIL/WARN per dependency | ✔ ran; correctly failed on absent `pandas`/`psutil` |
| How do I build? | `make` → `epic-v3.1`, `pic-v3.1` | ✔ **build succeeded in the fresh clone** |
| How do I check it works? | `python3 smoke_test.py` | ✔ **14/14 passed**, byte-exact round trips |
| Where do outputs go? | `results/{raw,tables,figures}`, git-ignored | ✔ |
| Licence? | `LICENSE`, Apache-2.0, with scope limits stated in the README | ✔ |

A reviewer can go from clone to a passing functional check in four commands. That is the single
most important property of an artifact and it holds.

### 1.2 Ambiguity found: none blocking

The README is accurate about the two things most artifacts get wrong: it states plainly that the
first four steps need no dataset, and that experiments do.

### 1.3 **Defect — the Standard Ebooks input cannot be produced with the tools provided**

`README.md` and `docs/datasets.md` instruct the reviewer to supply:

```
standard_ebooks_output/txt_clean/*.txt   cleaned Standard Ebooks plain text, one file per book
```

The repository provides **no tool that produces this format**. Standard Ebooks distributes EPUB;
the EPUB→text conversion (`epub_to_text`) lived in `download_standard_ebooks_from_catalog.py`, which
was removed with the acquisition scripts. Gutenberg input is fine — `clean_gutenberg_texts.py` is
retained and handles raw PG text — but the Standard Ebooks half of the corpus has documented
requirements and no documented means.

- **Severity:** medium. It does not block *Functional* evaluation (build and smoke test are
  self-contained) but it obstructs any attempt at dataset reconstruction, which is what a reviewer
  pursuing *Reproduced* would attempt.
- **Not a licensing problem.** Removing the crawlers was correct; the conversion step was collateral.
- **Suggested resolution (not applied at audit time):** either state explicitly in
  `docs/datasets.md` that the reviewer must convert EPUB to plain text themselves and name a tool
  capable of it, or restore a local-only, network-free EPUB→text converter. The second is more
  useful; the first is cheaper and sufficient for honesty.

> **RESOLVED 2026-08-24 — documentation option adopted.** The author chose to keep the artifact free
> of any download or conversion capability. `README.md` and `docs/datasets.md` now state explicitly
> that the repository provides **no EPUB downloader and no EPUB-to-text converter**, that it
> processes **local plain-text input only**, that Standard Ebooks input must be supplied as
> already-prepared `.txt` in `standard_ebooks_output/txt_clean/`, and that nothing in the repository
> can produce those files. Both documents give the rationale: keeping preparation deterministic and
> independent of changing online catalogs. No tooling was added, and no document implies the files
> can be produced automatically.

---

## 2. Repository organization

**Good.** Flat root of 20 Python files plus 4 C++ files, with `docs/` for documentation and
`datasets/` holding only the tracked manifest. Every generated path (`results/`, binaries, datasets)
is git-ignored and absent from a clean checkout, so nothing in the tree is ambiguous about whether
it is input or output. That was verified: `git status` is clean immediately after `make` and after
the smoke test.

Naming is consistent: `run_*.py` for experiments, `check_*.py` for validation, `clean_*.py` and
`prepare_*.py` for data, `plot_*.py` for figures.

### Likely to confuse a reviewer

1. **`docs/repository_inspection.md` and `docs/cleanup_manifest.md` are process artifacts, not
   reviewer documentation.** They are honest and well-labelled, but they describe how the repository
   was cleaned up rather than how to use it, and a reviewer opening `docs/` sees six files with no
   indication that four are for them and two are provenance. The README's documentation table does
   distinguish them, which mitigates this.
2. **`epic-v3.1` is the TIC binary.** The scheme is called TIC everywhere but the source, the
   binary and the Makefile target are all named `epic`. The README's contents table maps them, but
   the mismatch recurs in every command a reviewer types.
3. **The version suffix `-v3.1`** on the only implementation implies there are others; there are not.

None of these justifies churn. (2) and (3) would be renames touching the Makefile, CI, smoke test and
every doc — real risk for cosmetic benefit. Recorded, not recommended.

---

## 3. Installation workflow

The README's numbered workflow matches the canonical sequence exactly:

```
1 install    ./install_dependencies.sh
2 validate   python3 check_environment.py
3 build      make
4 smoke      python3 smoke_test.py
5 datasets   python3 prepare_datasets.py
6 experiments run_compression / run_decompression / run_search /
              run_search_replace / run_parallel_benchmarks --input ...
7 figures    plot_parallel_results.py
```

Steps 1–4 were executed in the fresh clone and behave as documented. Tables are produced by the
runners themselves rather than a separate step, and the README says so rather than implying a
missing stage.

**One gap, and it is signposted:** step 5 requires local corpora that the reviewer must obtain
first. The README covers this in a dedicated "You supply the source corpora" subsection before the
workflow, and `prepare_datasets.py` fails with exit 1 and names the exact directories — verified in
the fresh clone. The residual weakness is §1.3, not the sequencing.

---

## 4. Documentation consistency

Cross-checked `README.md`, `docs/environment.md`, `docs/datasets.md`, `docs/licensing.md`,
`docs/dictionary.md` and `README_benchmark_verification.md`.

**Mechanical checks all pass:**

- every markdown link in all seven documents resolves locally — **0 broken**
- every referenced script and source file exists — **0 missing** (the only unresolved names are
  generated outputs, correctly described as such)
- no active reviewer document references a removed script, `prepare_datasets.py fetch`, or the
  legacy `../textFiles/` layout except where documenting the legacy fallback, which still exists

**No contradictions found** on the facts most likely to drift: minimum Python (3.9, consistent in
three places), `lbzip2` scoped to the parallel experiments (consistent), dictionary requirements,
and the per-compiler warning counts.

### 4.1 **Defect — `README_benchmark_verification.md` §9 cannot be followed as written**

Section 9.1 instructs:

```bash
python3 run_parallel_benchmarks.py
```

The parallel runner now requires an explicitly supplied input, because the historical
`file-parallel.txt` has unrecoverable provenance. The document **never mentions `--input` or
`file-parallel.txt` anywhere in its 685 lines**. A reviewer following it will hit a hard failure at
§9.1.

- **Severity:** low-to-medium. The failure is loud and self-explanatory — the runner names the flag
  and points at `docs/datasets.md` — so the reviewer is not stranded, merely contradicted.
- **Suggested resolution (not applied at audit time):** update §9.1 to
  `python3 run_parallel_benchmarks.py --input datasets/f10.txt` and add one sentence noting the
  substitute input does not reproduce the historical absolute values.

> **RESOLVED 2026-08-24.** All three invocations in `README_benchmark_verification.md` (§9.1, §11.3
> and the §12 full-run sequence) now pass `--input datasets/f10.txt`. Section 9.1 additionally
> records that the input must be supplied explicitly, that `file-parallel.txt` is not distributed
> and cannot be reconstructed, and that a substitute reproduces functionality and thread-scaling
> behaviour but not the exact historical absolute measurements — consistent with the README's
> parallel caveat.

### 4.2 Duplication (acceptable)

Dependency lists appear in `README.md`, `docs/environment.md`, `requirements.txt` and
`dependencies.py`. This is deliberate layering — summary, detail, machine-readable, and canonical
inventory — and the four were verified consistent. `requirements.txt` and the `dependencies.py`
inventory match exactly.

---

## 5. Artifact completeness

All 39 tracked files classified. **Nothing was removed.**

### Essential (23) — the artifact cannot be evaluated without these

`epic-v3.1.cpp`, `epic-v3.1.h`, `pic-v3.1.cpp`, `pic-v3.1.h`, `Makefile`, `dict.txt`, `LICENSE`,
`README.md`, `.gitignore`, `requirements.txt`, `install_dependencies.sh`, `check_environment.py`,
`dependencies.py`, `dataset_config.py`, `smoke_test.py`, `benchmark_utils.py`, `run_compression.py`,
`run_decompression.py`, `run_search.py`, `run_search_replace.py`, `run_parallel_benchmarks.py`,
`prepare_datasets.py`, `make_combined_text_files.py`

### Recommended (9) — materially improve evaluability

| File | Why |
|---|---|
| `docs/environment.md`, `docs/datasets.md`, `docs/dictionary.md`, `docs/licensing.md` | The substantive reviewer documentation |
| `README_benchmark_verification.md` | Script-by-script verification checklist; the most detailed validation aid, subject to §4.1 |
| `.github/workflows/ci.yml` | Continuously demonstrates the artifact builds and functions |
| `datasets/manifest.csv` | Dataset inventory with checksum discipline |
| `plot_parallel_results.py` | Regenerates the paper's four figures |
| `pre-process-dict.py` | Documents and reproduces dictionary construction; the only path to a dictionary if `dict.txt` is ever withdrawn |

### Optional (7) — defensible, none unnecessary

| File | Assessment |
|---|---|
| `plot_parallel_subset.py` | Overlaps `plot_parallel_results.py`; plots the same CSVs restricted to threads 1/2/4/6/8. Retain — it independently documents the thread counts |
| `debug_pic_tic.py` | Diagnostic; genuinely useful for a TIC/PIC mismatch |
| `check_longest_line.py` | Diagnostic; validates a reviewer-supplied parallel input, which matters given §1.3 and the parallel caveat |
| `clean_gutenberg_texts.py`, `check_gutenberg_books.py` | Only needed when building datasets, but then they are needed |
| `docs/repository_inspection.md`, `docs/cleanup_manifest.md` | Process/provenance records. Optional for evaluation; valuable for transparency (see §2.1) |

**No tracked file appears unnecessary.** Every file has a stated role, and the cleanup history shows
the obviously superfluous material has already been removed.

---

## 6. Reproducibility claims

This is the dimension artifacts most often overstate, and here it is handled unusually carefully.
The three tiers are consistently distinguished:

| Tier | Where stated | Verified honest |
|---|---|---|
| **Functional validation** | `smoke_test.py` output says "This says nothing about performance", and the README repeats it | ✔ |
| **Approximate reproduction** | README and `docs/datasets.md` both state that regenerated `f1`–`f10` are "approximate, not exact" because the corpus was never pinned | ✔ |
| **Exact reproduction** | Stated as **not achievable** for the corpus or `file-parallel.txt` | ✔ |

Specific claims spot-checked and found accurate rather than optimistic:

- the parallel caveat states a substitute input reproduces scaling behaviour but **not** absolute
  values, and the runner prints that at run time
- `docs/dictionary.md` states measurably that a different dictionary changes output (960 B vs
  1,280 B on the same input)
- `datasets/manifest.csv` records `unavailable` rather than inferred values, including for
  `file-parallel.txt`
- the README's limitations section lists six constraints including platform-specific timings

**No misleading wording found.** The only claim that could be tightened is the README's statement
that CI "runs green", which is true but branch-scoped — the badge makes the scope explicit.

---

## 7. CI review

`.github/workflows/ci.yml` — 12 steps on `ubuntu-24.04`, triggered on push and pull request.
Verified green (run 32714195668, all steps success, zero annotations).

**Adequate for its stated purpose.** It builds under real GCC 13.3.0/libstdc++, asserts both ELF
binaries exist, runs the environment checker, runs the smoke test **twice** (synthetic dictionary and
committed `dict.txt`), publishes the GCC warning audit without failing on it, and — a detail many
artifacts miss — asserts `git status --porcelain` is empty so CI cannot silently reintroduce
generated content.

### Suggested improvements (not implemented, ordered by value)

1. **Add a `macos-latest` job.** The README claims macOS/Apple Silicon as a validated platform, but
   that validation is manual and undated. A second job would make both claimed platforms
   continuously verified. Highest-value change here.
2. **Verify `dict.txt` against `dataset_config.HISTORICAL_DICT["sha256"]`.** Cheap, and it would
   catch corruption or accidental modification of the one data file the artifact ships.
3. **Test the declared minimum Python.** CI runs 3.11 while the artifact claims 3.9+; a two-entry
   matrix would make the claim real.
4. **Pin actions to commit SHAs.** Standard supply-chain hygiene; low urgency for a research
   artifact.
5. **Add a `schedule:` trigger.** Would catch environment drift (apt package changes, action
   deprecations) between pushes rather than at submission time.

---

## 8. Overall assessment

> ### Minor documentation improvements recommended

**Why not "Ready for artifact evaluation":** two genuine defects exist — the missing EPUB→text path
(§1.3) and the un-followable §9 of the verification checklist (§4.1). Both are documentation-level,
both have straightforward fixes, but declaring the artifact ready while a reviewer-facing checklist
contains an instruction that fails would not be an honest audit.

**Why not "Additional engineering required":** nothing is broken. A fresh clone builds and passes
its functional test on both claimed platforms; the licence is present and correctly scoped;
dependencies install from a canonical file; generated and tracked content are cleanly separated; CI
is green; and the reproducibility claims are accurate and conservative. The remaining work is
editing prose, not writing code.

**Strengths worth recording**, because they are unusual: the artifact fails loudly and early on
missing dependencies rather than producing zeroed measurements; it never silently substitutes a
dataset or a dictionary; it records `unavailable` where provenance could not be established instead
of inferring it; and it documents its own limitations in more detail than most artifacts document
their successes.

---

## 9. Recommendations

Only items whose absence a reviewer would actually notice.

| # | Recommendation | Effort | Rationale |
|---|---|---|---|
| 1 | ~~Document or restore an EPUB→plain-text path for Standard Ebooks input (§1.3)~~ | — | **DONE 2026-08-24** — documented; the artifact deliberately provides no converter |
| 2 | ~~Fix `README_benchmark_verification.md` §9.1 to pass `--input` (§4.1)~~ | — | **DONE 2026-08-24** — all three invocations updated |
| 3 | Add a `macos-latest` CI job (§7.1) | Low | Makes the second claimed platform continuously verified rather than manually attested |
| 4 | Verify `dict.txt`'s SHA-256 in CI (§7.2) | Trivial | Protects the one data file that ships |

**Explicitly not recommended:** renaming `epic-*` to `tic-*` (churn across the Makefile, CI, tests
and all documentation for cosmetic gain); adding SPDX headers to every source file (the top-level
licence suffices); splitting `docs/` into reviewer and provenance subdirectories (the README table
already distinguishes them); and pursuing byte-exact dataset reconstruction, which the missing
corpus snapshot makes impossible regardless of effort.

### Outstanding non-defect caveats

These are correctly documented and are **not** audit findings — they are properties of the work:

- the benchmark corpus was never pinned, so exact reproduction of the published numbers is not
  achievable
- `file-parallel.txt` provenance is unrecoverable
- `dict.txt` derives from a third-party dataset whose redistribution terms could not be established
  (`docs/licensing.md` §3) — the one remaining item with legal rather than technical exposure

---

## 10. Audit scope

This audit modified **no file other than itself**. The two defects it identifies were reported
rather than fixed, because neither prevented artifact evaluation and both were the author's call.
They were subsequently resolved in a separate documentation-only change on 2026-08-24; the findings
above are preserved verbatim, with resolution notes appended rather than substituted.

Evidence: fresh clone at `6c2f421`; `make` and `smoke_test.py` executed in that clone;
`check_environment.py`, `prepare_datasets.py` and `run_compression.py` failure paths exercised;
link and reference resolution checked mechanically across all seven documents; CI run 32714195668
inspected step by step. No benchmark was run.
