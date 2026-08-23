# The Dictionary (`dict.txt`)

Why TIC and PIC need a dictionary, exactly how they consume it, the fingerprint of the historical
one, and how a reviewer supplies their own.

---

## 1. Why it is required

Both schemes are **dictionary-based**. Every operation — compression, decompression, lookup and
lookup-and-replace — loads the dictionary at start-up and assigns each entry a code word by its
position in the file. Without it neither binary can do anything; both exit 1.

The dictionary is therefore not optional data. It is part of the codec.

---

## 2. Exactly how it is consumed

Established from the source, not inferred. The relevant functions are
`Build_Dictionary_Table_Compression()` and `Build_Dictionary_Table_Decompression()` in
`epic-v3.1.cpp` and `pic-v3.1.cpp`.

```cpp
while (getline(file, line))            // split on '\n' only
{
    stringstream ss(line);
    getline(ss, word, '\n');           // the WHOLE line becomes the entry
    dictMapWord[word] = serial;        // compression:   word  -> code word
    dictMapCodeArray[serial] = word;   // decompression: code word -> word
    serial++;
}
```

`serial` starts at `CODE_WORD_OFFSET` (5), reserving code words 0-4 for space, newline,
next-capital, next-special and end-special.

| Question | Answer | Evidence |
|---|---|---|
| **Required filename/path** | `$TIC_DICT_PATH`, else `dict.txt` relative to the CWD | `resolveDictionaryPath()` in both sources |
| **Does order matter?** | **Yes, critically.** Entry *N* becomes code word *N* + 5. Inserting, removing or reordering one entry renumbers everything after it and changes the compressed output | `serial++` per line |
| **Do duplicates matter?** | **Yes.** Compression is a hash map, so a repeated word keeps only the **last** serial; decompression stores every serial. The round trip still succeeds, but a duplicate wastes a code word and shifts all later entries. The historical dictionary has **0 duplicates** | `dictMapWord[word] = serial` overwrites |
| **Do the leading punctuation entries matter?** | **Yes.** They occupy the first 17 slots (code words 5-21). Removing them shifts every word by 17 | measured: `dict.txt` lines 1-17 |
| **Do line endings matter?** | **Yes.** The C++ splits on `'\n'` only. A CRLF file leaves a trailing `'\r'` on **every** entry, so no word would ever match. Must be **LF** | `getline(file, line)` |
| **Is whitespace stripped?** | **No.** The entire line is the entry, verbatim. The comma-splitting code is commented out, so a raw `word,count` CSV would **not** work | `getline(ss, word, '\n')` |
| **Is case significant?** | **Partly.** Only the first character is lowercased before lookup (`tmpWord[0] = tolower(tmpWord[0])`), so entries should be lowercase-initial; the remaining characters are matched case-sensitively. The historical dictionary is entirely lowercase | `epic-v3.1.cpp:1482` |
| **Does changing the dictionary change compressed output?** | **Yes — measured.** The same 1,720-byte input compressed to **960 B** with the historical dictionary and **1,280 B** with a 23-entry synthetic one | direct experiment |
| **Do TIC and PIC use it identically?** | **Yes.** Diffing both functions between the two sources shows only `uint32_t` vs `uint64_t` for the counter, error-message wording, and diagnostic prints. Parsing, ordering and the offset are identical | function-level diff |

### A pre-existing PIC bound worth knowing

`pic-v3.1.cpp:2041` rejects `finalSerial >= NUMBER_OF_WORDS_DICT`, but serials carry the +5 offset
while `NUMBER_OF_WORDS_DICT` is a raw line count. **PIC therefore cannot decode the top 5 entries of
any dictionary.** With the historical 333,350-entry file only the five rarest words are affected, so
it never surfaces in practice. With a small dictionary it fails immediately.

This is a pre-existing defect, **left unmodified** — fixing it would change PIC's behaviour. It is
worked around in the smoke test by padding its synthetic dictionary. Anyone building a small
dictionary should append at least 5 unused filler entries.

---

## 3. Historical fingerprint

The dictionary that produced the published results, measured 2026-08-23 from the tracked file:

| Property | Value |
|---|---|
| **SHA-256** | `9b1d044dcca20e959a241656ecdeff0d59f37fe0a59499cec77a19d355cae3b8` |
| **MD5** | `5d2675ec8e89076d018255aaa0c4dfa6` |
| **Size** | 2,823,482 bytes |
| **Entries** | 333,350 |
| **Newlines** | LF only (0 CRLF, 0 lone CR), trailing newline present |
| **Structure** | 17 punctuation entries, then 333,333 words in frequency-rank order |
| **Duplicates** | 0 |
| **Empty entries** | 0 |
| **Entries containing whitespace** | 0 |
| **Entries with uppercase** | 0 |
| **Non-ASCII entries** | 3 (the curly quotes `“ ” ’`) |
| **First 17 entries** | `,` `.` `-` `:` `?` `(` `)` `!` `;` `/` `\` `"` `“` `”` `'` `’` `` ` `` |
| **Entries 18-20** | `the`, `of`, `and` |

Recorded in code as `dataset_config.HISTORICAL_DICT`. **This fingerprint identifies the file; it is
not a licence grant and does not authorise redistributing its contents.**

---

## 4. Provenance and why it cannot currently be redistributed

`dict.txt` is a **proven derivative** of the Kaggle "English Word Frequency" dataset: lines 18 to the
end are byte-identical to column 1 of that CSV, in order.

The licence chain does not permit redistribution:

- Kaggle records the dataset licence as **"Other (specified in description)"** — not a standard open
  licence.
- The description states *"The code used to generate this dataset is distributed under the MIT
  License."* That covers the **generating code, not the data**.
- Peter Norvig's page says the same independently: *"Code copyright (c) 2008-2009 by Peter Norvig.
  You are free to use this code under the MIT license"* — with **no** licence for the data files.
- The root corpus (Google Web Trillion Word Corpus, **LDC2006T13**) is distributed under a specific
  LDC agreement and is **not freely redistributable**.

**Conclusion: the licence could not be reliably established.** No claim is made here beyond what
those sources state. Full analysis and citations: `docs/licensing.md` §3.

This is why `dict.txt` is a candidate for removal from the public artifact, and why this document
exists.

---

## 5. Supplying a dictionary

### Where the binaries look

1. `$TIC_DICT_PATH`, if set and non-empty
2. `dict.txt`, relative to the current working directory (historical default, retained for
   backward compatibility)

```bash
TIC_DICT_PATH=/path/to/dict.txt ./epic-v3.1 -c -t 1 input.txt output.tic
export TIC_DICT_PATH=/data/dict.txt          # applies to a whole session
```

The environment variable was chosen over a `--dict` flag because the argument parser validates
`argc` strictly (6, 7 or 8); a new flag would change every existing command. **All documented
invocations keep working unchanged**, and the same dictionary bytes always produce the same output.

### Building one from a frequency CSV

```bash
python3 pre-process-dict.py --input /path/to/unigram_freq.csv --output dict.txt
```

The script expects a CSV whose **first column is the word**, and writes:

1. the 17 punctuation entries, in their historical order;
2. column 1 of every row, verbatim, in file order.

It **never downloads anything** — the frequency CSV is a third-party dataset whose licence is
unresolved, so the reviewer supplies it. Options:

| Flag | Effect |
|---|---|
| `--skip-header` | Skip row 1. Kaggle's original file has a `word,count` header; the historical input did not |
| `--no-punctuation` | Omit the 17 leading entries (what the committed script did). Does **not** match the historical dictionary |
| `--force` | Overwrite an existing output file |

It fails loudly on a missing input, an empty row, an empty word, an embedded newline, or a first
field that looks like a header — because silently dropping or adding one row renumbers every code
word after it.

**Verified:** running it against the historical frequency CSV reproduces `dict.txt`
**byte-for-byte**, SHA-256 `9b1d044d…` — so this route genuinely reconstructs the historical
dictionary for anyone holding the source CSV.

### Checking what you have

```bash
python3 check_environment.py
```

Three distinct outcomes, never conflated:

| State | Report |
|---|---|
| Present, SHA-256 matches | **PASS** — the historical dictionary |
| Present, SHA-256 differs | **WARN** — usable, but will **not** reproduce the published measurements; both hashes are printed |
| Missing / not a file / empty / unreadable | **FAIL** — names the path and `$TIC_DICT_PATH` |

Experiment runners call `dependencies.preflight()`, which enforces exists / regular file / non-empty
/ readable before any measurement. `preflight(..., historical_dict=True)` additionally **fails** on a
hash mismatch, for historical-reproduction runs.

---

## 6. A different dictionary does not reproduce the paper

Stated plainly, because it is easy to get wrong:

> A dictionary other than the one fingerprinted in §3 produces **different compressed output**,
> different compression ratios, and different timings. Results obtained with a substitute are valid
> measurements of *that* configuration; they are **not** a reproduction of the published numbers.

Measured, not asserted: the same input compressed to 960 B with the historical dictionary and
1,280 B with a synthetic one.

If you publish numbers from a substitute dictionary, state its SHA-256 alongside them.

---

## 7. Smoke testing without the historical dictionary

```bash
python3 smoke_test.py                      # synthetic dictionary, written by the test
python3 smoke_test.py --historical-dict    # use the resolved dict.txt instead
```

The default writes a small dictionary into its own temporary directory and passes it via
`$TIC_DICT_PATH`. **Functional validation therefore never requires the historical dictionary**, so it
is not a redistribution prerequisite for checking that the artifact works.

Words absent from a dictionary become "special code words", so the round trip stays byte-exact
regardless of dictionary size. Compressed sizes from the synthetic dictionary are meaningless for
comparison.

---

## 8. Status

`dict.txt` is **still tracked**. Before it can be removed, all of these must hold:

| Requirement | Status |
|---|---|
| Runtime path configurable | **Done** — `$TIC_DICT_PATH`, verified byte-identical output |
| Environment checks handle absence | **Done** — three distinguished states |
| Smoke testing works without it | **Done** — 11/11 with a synthetic dictionary |
| Documentation explains acquisition | **Done** — this file |
| No active script assumes it is committed | **Done** — all paths resolve through `resolve_dict_path()` |
| **A reviewer can actually obtain a dictionary** | **OPEN** — depends on the unresolved licence (§4) |

The last row is the remaining blocker: the acquisition route works, but it requires the reviewer to
obtain the frequency CSV from Kaggle themselves, and that dataset's redistribution terms are
unresolved. Removing `dict.txt` before that is settled would leave the artifact unrunnable for
anyone who cannot get the source data.

---

## 9. Related

- `docs/licensing.md` §3 — full licence analysis with citations
- `docs/cleanup_manifest.md` — cleanup classification
- `docs/environment.md` — dependencies, build and validation
- `dataset_config.py` — `HISTORICAL_DICT`, `resolve_dict_path()`
- `dependencies.py` — `check_dictionary()`, `require_dictionary()`
