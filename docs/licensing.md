# Licensing, Attribution and Redistribution

Legal-readiness review of the TIC artifact for public release and artifact evaluation.

**Prepared:** 2026-08-22 · **Scope:** licensing only. No algorithm, result, dataset, plot or table
was modified.

> **Not legal advice.** This is an engineering review of what the repository contains and what its
> upstream sources publicly state. Where terms could not be established from an authoritative source,
> that is recorded as unresolved rather than guessed. Final decisions are the author's.

**Status: the repository has no license and is therefore not yet suitable for public release.**

---

## 1. Existing project license: none

**No license has ever existed in this repository.** Verified by:

| Search | Result |
|---|---|
| `LICENSE`, `COPYING`, `NOTICE`, `*copyright*` in the working tree | none |
| Every path ever tracked in Git, all branches, all ~40 commits | none |
| `SPDX`, `All rights reserved`, `Permission is hereby granted` across all history (`git log -S`) | never present in any commit |
| Copyright or licence headers in `.cpp`, `.h`, `.py`, `Makefile` | none |
| `README.md`, `README_benchmark_verification.md` | no licensing section |
| Package metadata (`setup.py`, `pyproject.toml`, …) | no such files exist |

Incidental matches were checked and excluded: dictionary entries in `dict.txt` (`license`, `bsd`,
`gpl`), `"copyright-page"` as an EPUB section name the download scripts strip, BSD/GNU tool names in
`dependencies.py`, and the word "license" occurring inside committed corpus text.

**Consequence.** Under the Berne Convention a work with no licence is "all rights reserved" by
default. Reviewers therefore have **no explicit permission to run, copy, modify or redistribute this
artifact**, even though it is on a public remote. This blocks artifact evaluation and is the single
highest-priority item in this document.

---

## 2. Recommended repository licence

All three candidates are permissive, OSI-approved, and standard for academic research software. They
differ mainly in **patent** handling and in how much ceremony redistribution requires.

### MIT

- **Redistribution:** grants the right to "use, copy, modify, merge, publish, distribute,
  sublicense, and/or sell" without restriction.
- **Attribution:** one condition only — the copyright notice and permission notice must be included
  in all copies or substantial portions.
- **Patents:** **no patent grant.** The text does not mention patents at all.
- **Suitability:** the most common licence for academic code. Shortest, most familiar to reviewers,
  lowest friction for reuse.

### BSD-3-Clause

- **Redistribution:** permitted in source and binary form, with or without modification.
- **Attribution:** retain the copyright notice, conditions and disclaimer in source; reproduce them
  in documentation for binary distribution.
- **Patents:** **no patent grant.** No reference to patents.
- **Extra clause:** clause 3 forbids using the copyright holder's or contributors' names to endorse
  or promote derived products without prior written permission.
- **Suitability:** functionally close to MIT. The non-endorsement clause is the only practical
  difference — occasionally valued by universities that do not want institutional names implying
  endorsement.

### Apache-2.0

- **Redistribution:** permitted, with four obligations (§4): supply the licence, mark modified files
  with prominent notices of change, retain existing notices, and propagate any `NOTICE` file.
- **Attribution:** the most demanding of the three, including the "state your changes" requirement.
- **Patents:** **an express patent grant** (§3) — perpetual, worldwide, royalty-free, irrevocable —
  with a retaliation clause: initiating patent litigation alleging the Work infringes terminates
  your patent licence.
- **Suitability:** preferred where the work may be patentable or where institutional policy requires
  an explicit patent position.

### Comparison

| | MIT | BSD-3-Clause | Apache-2.0 |
|---|---|---|---|
| Redistribution | unrestricted | unrestricted | unrestricted |
| Attribution burden | minimal | minimal | moderate (+ state changes) |
| Express patent grant | no | no | **yes** |
| Patent retaliation | n/a | n/a | yes |
| Non-endorsement clause | no | **yes** | trademark section |
| Length | ~170 words | ~220 words | ~2,900 words |

### Recommendation

**Apache-2.0 if a patent filing on TIC is contemplated or possible; MIT otherwise.**

TIC is a novel compression scheme, which is exactly the category where an express patent grant
matters — it tells reviewers and adopters where they stand rather than leaving patent rights
unstated. If no patent is contemplated and lowest friction is the priority, **MIT** is the
conventional and entirely defensible choice.

**BSD-3-Clause is not recommended here** — it carries MIT's patent silence *plus* an extra clause,
without a corresponding benefit for this artifact.

**This is a decision for the author, and it may require institutional input** (universities often
have IP policy governing licence choice for research output). **No `LICENSE` file has been created.**

Sources: [MIT (SPDX)](https://spdx.org/licenses/MIT.html) ·
[BSD-3-Clause (SPDX)](https://spdx.org/licenses/BSD-3-Clause.html) ·
[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)

---

## 3. `dict.txt` and `unigram_freq_bk.csv`

### 3.1 They are the same data

Proven in this repository, not inferred:

- `backup_versions/unigram_freq_bk.csv` — 333,333 rows of `word,count`, beginning
  `the,23135851162`.
- `dict.txt` — 333,350 lines. **Lines 18 to the end are byte-identical to column 1 of the CSV, in
  order.** The first 17 lines are punctuation marks (`,` `.` `-` `:` `?` `(` `)` `!` `;` `/` `\` `"`
  `“` `”` `'` `’` `` ` ``) prepended by the project.
- `pre-process-dict.py` performs exactly this transformation: read `unigram_freq.csv`, write column 1
  to `dict.txt`.

**`dict.txt` is a derivative work of the CSV.** Its licence status is whatever the CSV's is.

### 3.2 Upstream chain

`epic-v3.1.cpp:24` and `pic-v3.1.cpp:24` both cite:
`https://www.kaggle.com/datasets/rtatman/english-word-frequency`

| Layer | What it is | Stated terms |
|---|---|---|
| Kaggle dataset "English Word Frequency" | Owner **Rachael Tatman**. 333,333 rows — matches our file exactly | Kaggle license field: **"Other (specified in description)"** |
| The description's licence sentence | — | *"The code used to generate this dataset is distributed under the MIT License."* |
| Peter Norvig, `norvig.com/ngrams` | Produced the derived frequency files | *"Code copyright (c) 2008-2009 by Peter Norvig. You are free to use this code under the MIT license."* **No licence or redistribution statement for the data files.** |
| Google Web Trillion Word Corpus (Brants & Franz), LDC2006T13 | The underlying corpus | Distributed by the Linguistic Data Consortium under a specific **"Web 1T 5-gram Version 1 Agreement"**, gated by membership/non-member licensing. **Not freely redistributable.** |

### 3.3 Conclusion: **License could not be reliably established.**

The MIT reference at both the Kaggle and Norvig layers applies to **the code that generated the
data, not to the data itself**. This is the critical distinction. At no point in the chain does any
authoritative source grant permission to redistribute the frequency data, and the root corpus is
explicitly licence-gated by the LDC.

Availability on Kaggle is not a redistribution grant: Kaggle's own metadata declines to assert a
standard licence for this dataset ("Other"), and platform access terms are not dataset licensing.

### 3.4 Recommended treatment

| File | Recommendation |
|---|---|
| `backup_versions/unigram_freq_bk.csv` (4.8 MB) | **Exclude from the public artifact.** It is a verbatim copy of a third-party dataset with no established redistribution permission, and it is redundant — `dict.txt` is derived from it |
| `dict.txt` (2.7 MB) | **Exclude, or obtain permission.** As a derivative of the same data it inherits the same unresolved status. Replace with an acquisition script plus a SHA-256 checksum so reviewers fetch it themselves and can verify they got the right file |

`dict.txt` is **required at runtime** — both binaries load it from the working directory — so
excluding it means the artifact cannot run until the reviewer acquires it. That cost is real, and it
argues for resolving the licence rather than simply deleting the file.

**Options, most to least conservative:**

1. **Acquisition script + checksum.** Reviewers download from Kaggle themselves and run
   `pre-process-dict.py`. Legally safest; adds a Kaggle account requirement.
2. **Seek written permission** from Rachael Tatman, and confirm the LDC position on redistributing
   derived unigram counts. Best outcome if granted: bundle with a clear notice.
3. **Substitute a clearly-licensed frequency list** — for example one distributed under a documented
   open licence. This changes `dict.txt`, so **it would change the published results** and must not
   be done silently.
4. **Bundle as-is.** Not recommended while §3.3 stands.

---

## 4. Corpora: Project Gutenberg and Standard Ebooks

Four different acts must be kept apart; they do not have the same answer.

| Act | Project Gutenberg | Standard Ebooks |
|---|---|---|
| **Download for experiments** | Permitted | Permitted |
| **Redistribute source text in this repo** | Permitted for US-PD works, with caveats | Permitted (CC0) |
| **Redistribute generated `f1`–`f10`** | Same as source text | Permitted (CC0) |
| **Publish only scripts/manifests** | Always safe | Always safe |

### Project Gutenberg

Its permission policy states: *"you can freely redistribute any eBook, anywhere, any time, with or
without the 'Project Gutenberg' trademark included"* and *"The vast majority of Project Gutenberg
eBooks are in the public domain in the US."*

Two caveats:

- **Jurisdiction.** PG follows US copyright law and notes that *"Not all items that are public domain
  in the US are public domain in other countries."* A redistributed corpus may not be PD for
  non-US readers.
- **Trademark.** Redistribution without the PG trademark is explicitly allowed — and this pipeline
  strips PG headers and footers (`clean_gutenberg_texts.py`), so the trademark is removed. Royalty
  obligations attach only to commercially trading on the Project Gutenberg *name*, which this
  artifact does not do.
- **"Vast majority", not all.** PG's own wording is not a blanket guarantee for every item. Per-work
  status matters, and this repository records no per-work provenance.

### Standard Ebooks

*"Content produced by or for Standard Ebooks L³C is dedicated to the public domain via the CC0 1.0
Universal Public Domain Dedication."* CC0 imposes **no attribution requirement**, and Standard Ebooks
releases *"the entirety of each ebook file into the public domain."* Their source texts are
*"already believed to be in the U.S. public domain."*

Standard Ebooks is therefore the **least encumbered** of the two.

### Safest distribution strategy

**Publish the acquisition scripts and a pinned manifest; do not bundle corpus text.**

This is already the repository's direction — `datasets/` is git-ignored and `docs/datasets.md`
documents rebuilding from source. The recommendation is to keep it that way. Rationale:

1. Per-work PD status varies and is **not recorded** anywhere in this repository.
2. PD status is **US-specific**; an artifact has international readers.
3. The datasets are ~3.3 GB — impractical to bundle regardless.
4. A pinned manifest with per-book identifiers and checksums solves reproducibility (see
   `docs/datasets.md` §10) **without** raising any redistribution question.

### One inconsistency to resolve

`search_outputs/` currently commits **~865 KB of literary prose** — five ~173 KB files that are grep
output over corpus text, plus `debug_pic_tic_outputs/` (trivial, 43 bytes of decompressed text).

The prose is identifiable as *The Blue Castle* by L. M. Montgomery (1926) from the character name
"Valancy" — a work available from both PG and Standard Ebooks and understood to be US public domain.
But **the repository records no provenance for it**: PG/SE headers were stripped by the cleaning
pipeline, and grep found **zero** "Project Gutenberg" or "Standard Ebooks" markers in these files. So
neither the source nor the per-work status can be verified from the repository itself.

This contradicts the "do not bundle corpus text" policy. These files were already deletion candidates
in `docs/repository_inspection.md` §10 as stale run residue from the superseded `run_search_v1.py`.
**Recommendation: exclude from the public artifact** — which resolves the licensing question and the
tidiness question together.

---

## 5. Source-code ownership

| Check | Result |
|---|---|
| Authorship header | `epic-v3.1.cpp:4` and `pic-v3.1.cpp:4`: `Author: Abbas A. Fairouz` |
| Third-party markers (`adapted from`, `based on`, `taken from`, `stackoverflow`, `github.com`, `@author`, …) | **none** in either source or header |
| Embedded licence notices | **none** |
| Copyright notices | **none** (nothing to preserve — and nothing was removed) |
| Vendored/bundled third-party code | none |
| External libraries | none; C++17 standard library only |

**All C++ and Python source can reasonably be treated as project-authored.** The only external
reference is the Kaggle URL in the header comment, which is a data citation, not code provenance.

No copyright or licence notice was removed by this review — there were none to remove.

---

## 6. Licensing inventory

**Verified** = confirmed against an authoritative source, cited in §9.
**Unresolved** = could not be established; treated conservatively.

| Component | Source | Current location | License | Redistribution allowed? | Attribution required? | Recommended artifact treatment |
|---|---|---|---|---|---|---|
| **TIC source** | Project-authored (A. A. Fairouz) | `epic-v3.1.cpp`, `epic-v3.1.h` | **None yet** — author's to choose | Author's decision | Per chosen licence | **Retain.** Add top-level `LICENSE` (§2) |
| **PIC source** | Project-authored | `pic-v3.1.cpp`, `pic-v3.1.h` | **None yet** | Author's decision | Per chosen licence | **Retain** under the same licence |
| **Superseded C++** | Project-authored | `old_versions/` | **None yet** | Author's decision | Per chosen licence | **Retain** (covered by the same licence) |
| **Python scripts** (runners, pipeline, tooling) | Project-authored | repo root | **None yet** | Author's decision | Per chosen licence | **Retain** under the same licence |
| **Build files / docs** | Project-authored | `Makefile`, `docs/`, `README*.md` | **None yet** | Author's decision | Per chosen licence | **Retain** |
| **`dict.txt`** | Derived from the Kaggle word-frequency CSV (proven, §3.1) | `dict.txt` (2.7 MB) | **Unresolved — License could not be reliably established** | **Unknown** | Unknown | **Replace with acquisition script + SHA-256**, or obtain permission (§3.4) |
| **`unigram_freq_bk.csv`** | Kaggle "English Word Frequency", owner Rachael Tatman; ← Norvig ← Google Web Trillion Word Corpus / LDC2006T13 | `backup_versions/` (4.8 MB) | **Unresolved — License could not be reliably established** | **Unknown**; root corpus is LDC licence-gated | Unknown | **Exclude from the public artifact** (also redundant) |
| **Project Gutenberg inputs** | gutenberg.org | Not in repo (git-ignored) | US public domain; PG grants free redistribution | Yes, for US-PD works; jurisdiction-dependent | No (trademark conditions only if trading on the PG name) | **Require reviewer to obtain separately** via `prepare_datasets.py fetch` |
| **Standard Ebooks inputs** | standardebooks.org | Not in repo (git-ignored) | **CC0 1.0 Universal** | **Yes** | **No** | **Require reviewer to obtain separately** |
| **Generated `f1`–`f10`** | Derived from both corpora | Not in repo (git-ignored) | Inherits corpus status | Mixed / unrecorded per work | No | **Exclude**; rebuild via `prepare_datasets.py` |
| **`file-parallel.txt`** | **Provenance unknown** (`docs/datasets.md` §7) | Not in repo | **Unresolved** | Unknown | Unknown | **Exclude**; reviewer supplies via `--input` |
| **Committed corpus text** | Unrecorded; identifiable as *The Blue Castle* (1926) | `search_outputs/` (~865 KB), `debug_pic_tic_outputs/` | Likely US PD, **not verifiable from the repository** | Probably, but unverified | No | **Exclude from the public artifact** (§4) |
| **`.vscode/settings.json`** | Project-authored editor config | `.vscode/` | **None yet** | n/a | No | **Exclude** (personal config; already a deletion candidate) |
| **External CLI tools** (`gzip`, `bzip2`, `lz4`, `lbzip2`, `grep`) | System packages | Not bundled — invoked only | Their own licences | n/a — **not redistributed** | No | **Retain as dependencies**; installed by `install_dependencies.sh` |
| **Python packages** (pandas, psutil, …) | PyPI | Not bundled — `requirements.txt` only | Their own licences | n/a — **not redistributed** | No | **Retain as dependencies** |

No third-party **code** is bundled anywhere in this repository. Every unresolved row is data, not code.

---

## 7. Third-party notices

**No `THIRD_PARTY_NOTICES.md` is required, and none has been created.**

Reasoning, component by component:

- **No third-party source code is bundled** (§5), so there is nothing with a notice-preservation
  obligation.
- **Standard Ebooks** is CC0 — attribution is **not required**. (Crediting them anyway is courteous
  and recommended in the README, but it is not a licence obligation.)
- **Project Gutenberg** requires no permission and no attribution to redistribute; only trading on
  the PG trademark triggers obligations, which this artifact does not do.
- **`dict.txt` / `unigram_freq_bk.csv`** have **no established licence**, so no attribution
  requirement can be established either. A notices file cannot cure a missing permission — the
  recommendation is exclusion (§3.4), not attribution.
- **External tools and Python packages** are dependencies, not redistributed content.

**This changes if the recommendation in §3.4 option 2 is taken.** If permission to bundle the
frequency data is obtained, that permission will almost certainly carry attribution terms, and
`THIRD_PARTY_NOTICES.md` should then be created to carry them.

---

## 8. Redistribution recommendations

| File / component | Recommendation |
|---|---|
| `epic-v3.1.*`, `pic-v3.1.*`, `old_versions/`, all Python, `Makefile`, `docs/` | **Retain in public repository** under the chosen licence |
| `dict.txt` | **Replace with acquisition script** (+ SHA-256), or retain with attribution *only if* permission is obtained |
| `backup_versions/unigram_freq_bk.csv` | **Exclude from public repository** |
| `search_outputs/` (~865 KB corpus text) | **Exclude from public repository** |
| `debug_pic_tic_outputs/` | **Exclude from public repository** |
| `f1`–`f10`, `file-parallel.txt`, source corpora | **Require reviewer to obtain separately** (already git-ignored) |
| `.vscode/settings.json` | **Exclude from public repository** |
| Compiled binaries `epic-v3.1`, `pic-v3.1` | **Exclude** — macOS-arm64 only; unrelated to licensing but they should not ship |

Where licensing is ambiguous the conservative option was chosen in every case.

---

## 9. Sources

Every external licensing claim above traces to one of these, retrieved 2026-08-22:

| Claim | Source |
|---|---|
| Kaggle licence field "Other (specified in description)"; owner Rachael Tatman; 333,333 rows; description text | `https://www.kaggle.com/api/v1/datasets/view/rtatman/english-word-frequency` (page HTML is JS-rendered; the API returns the metadata) |
| Norvig: MIT covers the **code**, no data licence | `http://norvig.com/ngrams/` |
| Root corpus is LDC-gated under the "Web 1T 5-gram Version 1 Agreement" | `https://catalog.ldc.upenn.edu/LDC2006T13` |
| PG redistribution permission, US-PD basis, trademark position | `https://www.gutenberg.org/policy/permission.html` |
| Standard Ebooks CC0 dedication | `https://standardebooks.org/about` |
| MIT text and conditions | `https://spdx.org/licenses/MIT.html` |
| BSD-3-Clause text and three clauses | `https://spdx.org/licenses/BSD-3-Clause.html` |
| Apache-2.0 §3 patent grant, §4 redistribution | `https://www.apache.org/licenses/LICENSE-2.0` |

**Retrieval note.** The ACM artifact review and badging policy page returned HTTP 403 and could not
be retrieved. No claim in this document rests on it. The artifact-evaluation argument in §1 rests on
default copyright, not on any quoted ACM requirement.

All other statements derive from evidence inside this repository (Git history, file contents, byte
comparison) and are reproducible with the commands recorded in §1 and §3.1.

---

## 10. README implications

`README.md` is currently inaccurate and will be rewritten separately. **This document does not modify
it.** When it is rewritten it must gain:

1. **A licence section** naming the chosen licence, with an SPDX identifier and a pointer to
   `LICENSE`.
2. **A copyright line** — `Copyright (c) 2026 Abbas A. Fairouz` (or the institutional holder, if
   university IP policy applies).
3. **A data-provenance section** stating that `dict.txt` derives from the Kaggle English Word
   Frequency dataset, with the URL, and — plainly — that **its licence is unresolved**, plus whatever
   acquisition route §3.4 settles on.
4. **A corpus section** stating that benchmark inputs are **not distributed**, naming Project
   Gutenberg and Standard Ebooks, noting Standard Ebooks' CC0 dedication, and pointing at
   `docs/datasets.md`.
5. **A scope note** that the licence covers the project's own code and documentation, **not** the
   third-party data or corpora.
6. **A citation section** — how to cite the paper and the artifact (currently absent everywhere; see
   `docs/repository_inspection.md` §17).

---

## 11. Open questions for the author

1. **Which licence?** MIT or Apache-2.0 (§2). Does your institution have an IP policy governing this?
2. **Is a patent contemplated on TIC?** Decides MIT vs Apache-2.0.
3. **Who is the copyright holder** — you personally, or your institution?
4. **`dict.txt`:** pursue permission, ship an acquisition script, or substitute a clearly-licensed
   frequency list? Option 3 would change the published results.
5. **May the deletion candidates be removed** — `backup_versions/`, `search_outputs/`,
   `debug_pic_tic_outputs/`, `.vscode/`? These require explicit approval per `CLAUDE.md` §10.
6. **What are the paper's citation details** (title, authors, venue, year, DOI)? Needed for
   `CITATION.cff` and the README.

---

## 12. Related

- `docs/repository_inspection.md` — full artifact inspection (§16 licences, §17 citations)
- `docs/datasets.md` — dataset provenance and acquisition
- `docs/environment.md` — dependencies and build
