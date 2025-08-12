#!/usr/bin/env python3
# run_search.py
# - Search a string across compressed artifacts produced by all tools.
# - TIC/PIC: native in-file search (your format: -l -t 1 <in> <dummy_out> <query>)
# - gzip/bzip2/lz4: decompress to temp file, then grep
# - gzip/bzip2: also on-the-fly zgrep/bzgrep
# - Measures runtime & average memory (includes child processes)
# - Outputs CSVs + LaTeX tables (makecell headers, configurable)

import os, time, subprocess, tempfile, shutil
from statistics import mean
import pandas as pd

# =====================
# User Config
# =====================
INPUT_FILE_NAME   = "test4.txt"
INPUT_FILE_PATH   = "../textFiles/" + INPUT_FILE_NAME
SEARCH_STRING     = "the"  # <-- set your query

# Order for reporting (TIC baseline first)
TOOLS_BASE_ORDER  = ["TIC", "PIC", "gzip", "zgrep", "bzip2", "bzgrep", "lz4"]

# Compression executables / flags (used only to ensure artifacts exist)
PIC_BINARY        = "./pic-v3.1"
TIC_BINARY        = "./epic-v3.1"
PIC_FLAGS_COMP    = ["-c", "-t", "1"]
TIC_FLAGS_COMP    = ["-c", "-t", "1"]

# TIC/PIC native search commands (per your spec)
# Format: binary -l -t 1 <compressed_input> <dummy_output> <search_string>
def PIC_SEARCH_CMD(cfile, dummy_out, query):
    return [PIC_BINARY, "-l", "-t", "1", cfile, dummy_out, query]

def TIC_SEARCH_CMD(cfile, dummy_out, query):
    return [TIC_BINARY, "-l", "-t", "1", cfile, dummy_out, query]

# Ensure compressed artifacts exist (not measured)
COMPRESSORS = {
    "gzip":  lambda infile, out: ["gzip", "-kf", infile],
    "bzip2": lambda infile, out: ["bzip2", "-kf", infile],
    "lz4":   lambda infile, out: ["lz4", "-kf", infile],
    "PIC":   lambda infile, out: [PIC_BINARY, *PIC_FLAGS_COMP, infile, out],
    "TIC":   lambda infile, out: [TIC_BINARY, *TIC_FLAGS_COMP, infile, out],
}
EXT = {"gzip": ".gz", "bzip2": ".bz2", "lz4": ".lz4", "PIC": ".pic", "TIC": ".tic"}

# CSV outputs
TIME_CSV = "search_time_results.csv"
MEM_CSV  = "search_mem_results.csv"

# LaTeX outputs
LATEX_TIME_FILE = "search_time_table.tex"
LATEX_MEM_FILE  = "search_mem_table.tex"

# ---- LaTeX headers (edit freely; add \\ where you want line breaks) ----
TIME_HEADERS = ["File name", "String", "File Size (MB)", "TIC (s)", "PIC", "gzip", "zgrep", "bzip2", "bzgrep", "lz4"]
MEM_HEADERS  = ["File name", "String", "TIC (MB)", "PIC", "gzip", "zgrep", "bzip2", "bzgrep", "lz4"]
LATEX_CAPTION_TIME = "Search runtime: TIC absolute (s); others as ratios vs TIC."
LATEX_CAPTION_MEM  = "Search memory: TIC absolute (MB); others as ratios vs TIC."
# -----------------------------------------------------------------------


def _try_import_psutil():
    try:
        import psutil  # type: ignore
        return psutil
    except Exception:
        return None


def measure(command):
    """
    Run a command and return (runtime_s, avg_memory_MB, stdout, stderr).
    Memory samples include the process and all its children recursively.
    If psutil is unavailable, memory is 0.0.
    """
    psutil = _try_import_psutil()
    start = time.time()
    proc  = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid   = proc.pid

    rss_samples = []
    if psutil is not None:
        P = psutil.Process
        while proc.poll() is None:
            try:
                p = P(pid)
                procs = [p] + p.children(recursive=True)
                rss = 0
                for q in procs:
                    try:
                        rss += q.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                rss_samples.append(rss / (1024**2))
            except psutil.NoSuchProcess:
                break
            time.sleep(0.05)

    stdout, stderr = proc.communicate()
    runtime = round(time.time() - start, 3)
    avg_mb  = round(mean(rss_samples), 3) if rss_samples else 0.0
    return runtime, avg_mb, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


def _latex_escape(s: str) -> str:
    repl = {
        "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
    }
    return "".join(repl.get(ch, ch) for ch in str(s))


def _format_cell(x):
    if x == "" or x is None:
        return ""
    if isinstance(x, (int, float)):
        return f"{x:.3f}"
    try:
        v = float(x)
        return f"{v:.3f}"
    except Exception:
        return _latex_escape(str(x))


def _makecell_header(s: str) -> str:
    # headers are NOT escaped so you can add manual "\\" or LaTeX macros
    return r"\makecell{" + s + "}"


def build_time_latex_table(df, caption, tex_path=LATEX_TIME_FILE):
    r"""
    Build LaTeX table for search runtime using \makecell headers.
    """
    cols    = TIME_HEADERS
    colspec = "c" * len(cols)
    header_row = " & ".join(_makecell_header(h) for h in cols) + r" \\"

    lines = []
    for _, row in df.iterrows():
        cells = [row[c] for c in cols]
        cells[0] = _latex_escape(str(cells[0]))  # filename
        cells[1] = _latex_escape(str(cells[1]))  # query
        cells = [cells[0], cells[1]] + [_format_cell(c) for c in cells[2:]]
        lines.append(" & ".join(cells) + r" \\")

    latex = (
        r"\begin{table}[ht]" "\n"
        r"\centering" "\n"
        r"\begin{tabular}{" + colspec + r"}" "\n"
        r"\hline" "\n" +
        header_row + "\n" +
        r"\hline" "\n" +
        "\n".join(lines) + "\n" +
        r"\hline" "\n"
        r"\end{tabular}" "\n"
        r"\caption{" + _latex_escape(caption) + r"}" "\n"
        r"\label{tab:search_time}" "\n"
        r"\end{table}" "\n"
    )
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)


def build_mem_latex_table(df, caption, tex_path=LATEX_MEM_FILE):
    r"""
    Build LaTeX table for search memory using \makecell headers.
    """
    cols    = MEM_HEADERS
    colspec = "c" * len(cols)
    header_row = " & ".join(_makecell_header(h) for h in cols) + r" \\"

    lines = []
    for _, row in df.iterrows():
        cells = [row[c] for c in cols]
        cells[0] = _latex_escape(str(cells[0]))  # filename
        cells[1] = _latex_escape(str(cells[1]))  # query
        cells = [cells[0], cells[1]] + [_format_cell(c) for c in cells[2:]]
        lines.append(" & ".join(cells) + r" \\")

    latex = (
        r"\begin{table}[ht]" "\n"
        r"\centering" "\n"
        r"\begin{tabular}{" + colspec + r"}" "\n"
        r"\hline" "\n" +
        header_row + "\n" +
        r"\hline" "\n" +
        "\n".join(lines) + "\n" +
        r"\hline" "\n"
        r"\end{tabular}" "\n"
        r"\caption{" + _latex_escape(caption) + r"}" "\n"
        r"\label{tab:search_mem}" "\n"
        r"\end{table}" "\n"
    )
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)


def _safe_ratio(numer, denom):
    if denom and denom != 0:
        return round(numer / denom, 3)
    return ""


def _compressed_path(tool):
    return INPUT_FILE_PATH + EXT[tool]


def _ensure_compressed(tool):
    """
    Make sure the compressed artifact for `tool` exists.
    Not measured; just prepares inputs for the search runs.
    """
    if tool not in EXT:
        return
    cpath = _compressed_path(tool)
    if os.path.exists(cpath):
        return
    cmd = COMPRESSORS[tool](INPUT_FILE_PATH, cpath)
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _decompress_to_temp(tool, tmp_dir):
    """
    Decompress a compressed artifact into tmp_dir and return the decompressed file path.
    We stream to disk (not measured) so the measured step is only grep.
    """
    src = _compressed_path(tool)
    if not os.path.exists(src):
        _ensure_compressed(tool)
    if not os.path.exists(src):
        raise RuntimeError(f"Missing compressed file for {tool}: {src}")

    base = os.path.basename(INPUT_FILE_PATH)
    out_path = os.path.join(tmp_dir, f"{base}.{tool}.decomp")

    if tool == "gzip":
        with open(out_path, "wb") as f:
            subprocess.run(["gzip", "-cd", src], stdout=f, check=False)
    elif tool == "bzip2":
        with open(out_path, "wb") as f:
            subprocess.run(["bzip2", "-cd", src], stdout=f, check=False)
    elif tool == "lz4":
        with open(out_path, "wb") as f:
            subprocess.run(["lz4", "-d", "-c", src], stdout=f, check=False)
    else:
        raise ValueError(f"Unsupported tool for decompression: {tool}")

    if not os.path.exists(out_path):
        raise RuntimeError(f"Decompression failed for {tool}: {src} -> {out_path}")
    return out_path


def main():
    if not os.path.exists(INPUT_FILE_PATH):
        raise RuntimeError(f"Input file not found: {INPUT_FILE_PATH}")

    # File size (for reporting)
    orig_bytes = os.path.getsize(INPUT_FILE_PATH)
    orig_mb    = round(orig_bytes / (1024**2), 3)

    # Ensure all compressed inputs exist (not measured)
    for t in ["TIC", "PIC", "gzip", "bzip2", "lz4"]:
        _ensure_compressed(t)

    # Temp dir for offline decompressions & dummy outputs
    tmp_dir = tempfile.mkdtemp(prefix="search_work_")

    try:
        metrics = {}  # tool -> {runtime_s, memory_MB}

        # --- TIC native search ---
        tic_cfile = _compressed_path("TIC")
        tic_dummy = os.path.join(tmp_dir, "tic_search.out")
        runtime, mem, so, se = measure(TIC_SEARCH_CMD(tic_cfile, tic_dummy, SEARCH_STRING))
        metrics["TIC"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- PIC native search ---
        pic_cfile = _compressed_path("PIC")
        pic_dummy = os.path.join(tmp_dir, "pic_search.out")
        runtime, mem, so, se = measure(PIC_SEARCH_CMD(pic_cfile, pic_dummy, SEARCH_STRING))
        metrics["PIC"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- gzip: offline grep (decompress, then grep) ---
        gz_dec = _decompress_to_temp("gzip", tmp_dir)
        runtime, mem, so, se = measure(["grep", "-F", SEARCH_STRING, gz_dec])
        metrics["gzip"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- zgrep on-the-fly ---
        gz_cfile = _compressed_path("gzip")
        runtime, mem, so, se = measure(["zgrep", "-F", SEARCH_STRING, gz_cfile])
        metrics["zgrep"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- bzip2: offline grep ---
        bz_dec = _decompress_to_temp("bzip2", tmp_dir)
        runtime, mem, so, se = measure(["grep", "-F", SEARCH_STRING, bz_dec])
        metrics["bzip2"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- bzgrep on-the-fly ---
        bz_cfile = _compressed_path("bzip2")
        runtime, mem, so, se = measure(["bzgrep", "-F", SEARCH_STRING, bz_cfile])
        metrics["bzgrep"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- lz4: offline grep ---
        lz4_dec = _decompress_to_temp("lz4", tmp_dir)
        runtime, mem, so, se = measure(["grep", "-F", SEARCH_STRING, lz4_dec])
        metrics["lz4"] = {"runtime_s": runtime, "memory_MB": mem}

        # ---------- CSV: search time (TIC absolute, others as ratios) ----------
        time_row = {
            "File name": INPUT_FILE_NAME,
            "String": SEARCH_STRING,
            "File Size (MB)": orig_mb,
            "TIC (s)": round(metrics["TIC"]["runtime_s"], 3),
        }
        for t in TOOLS_BASE_ORDER:
            if t == "TIC":
                continue
            time_row[t] = _safe_ratio(metrics.get(t, {}).get("runtime_s", 0.0),
                                      metrics["TIC"]["runtime_s"])
        time_df = pd.DataFrame([time_row])[TIME_HEADERS]
        time_df.to_csv(TIME_CSV, index=False)

        # ---------- CSV: search memory (TIC absolute, others as ratios) ----------
        mem_row = {
            "File name": INPUT_FILE_NAME,
            "String": SEARCH_STRING,
            "TIC (MB)": round(metrics["TIC"]["memory_MB"], 3),
        }
        for t in TOOLS_BASE_ORDER:
            if t == "TIC":
                continue
            mem_row[t] = _safe_ratio(metrics.get(t, {}).get("memory_MB", 0.0),
                                     metrics["TIC"]["memory_MB"])
        mem_df = pd.DataFrame([mem_row])[MEM_HEADERS]
        mem_df.to_csv(MEM_CSV, index=False)

        # ---------- LaTeX tables ----------
        build_time_latex_table(time_df, LATEX_CAPTION_TIME, tex_path=LATEX_TIME_FILE)
        build_mem_latex_table(mem_df, LATEX_CAPTION_MEM, tex_path=LATEX_MEM_FILE)

        print(f"Wrote: {TIME_CSV}, {MEM_CSV}, {LATEX_TIME_FILE}, {LATEX_MEM_FILE}")

    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    main()
