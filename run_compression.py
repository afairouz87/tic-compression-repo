#!/usr/bin/env python3
import os, time, subprocess
from statistics import mean
import pandas as pd

# =====================
# User Config
# =====================
INPUT_FILE_NAME  = "test4.txt"
INPUT_FILE_PATH  = "../textFiles/" + INPUT_FILE_NAME

# Ensure TIC appears before PIC
TOOLS_ORDER      = ["TIC", "PIC", "gzip", "bzip2", "lz4"]

LATEX_CAPTION_CR   = "Compression Ratio (CR)."
LATEX_CAPTION_TIME = "Compression Runtime: TIC absolute in sec, others as ratios vs TIC."
LATEX_CAPTION_MEM  = "Memory Utilization: TIC absolute in MB, others as ratios vs TIC."

# ---- LaTeX headers you can edit freely (add \\ where you want line breaks) ----
CR_HEADERS   = ["File Name", "File Size (MB)"] + TOOLS_ORDER
TIME_HEADERS = ["File name", "File Size (MB)", "TIC (s)", "PIC", "gzip", "bzip2", "lz4"]
MEM_HEADERS  = ["File name", "TIC (MB)", "PIC", "gzip", "bzip2", "lz4"]
# ------------------------------------------------------------------------------

PIC_BINARY       = "./pic-v3.1"
TIC_BINARY       = "./epic-v3.1"
PIC_FLAGS        = ["-c", "-t", "1"]
TIC_FLAGS        = ["-c", "-t", "1"]

TOOLS = {
    "gzip":  lambda infile, out: ["gzip", "-kf", infile],
    "bzip2": lambda infile, out: ["bzip2", "-kf", infile],
    "lz4":   lambda infile, out: ["lz4", "-kf", infile],
    "PIC":   lambda infile, out: [PIC_BINARY, *PIC_FLAGS, infile, out],
    "TIC":   lambda infile, out: [TIC_BINARY, *TIC_FLAGS, infile, out],
}

EXT = {"gzip": ".gz", "bzip2": ".bz2", "lz4": ".lz4", "PIC": ".pic", "TIC": ".tic"}

# CSV outputs
CR_RESULTS_CSV = "cr_results.csv"
C_TIME_CSV     = "c_time_results.csv"
MEM_CSV        = "mem_results.csv"

# LaTeX outputs
LATEX_CR_FILE   = "cr_table.tex"
LATEX_TIME_FILE = "c_time_table.tex"
LATEX_MEM_FILE  = "mem_table.tex"


def _try_import_psutil():
    try:
        import psutil
        return psutil
    except Exception:
        return None


def measure(command):
    """
    Run a command and return (runtime_s, avg_memory_MB, stdout, stderr).
    If psutil is unavailable, memory is 0.0.
    """
    psutil = _try_import_psutil()
    start = time.time()
    proc  = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid   = proc.pid
    rss_samples = []
    if psutil is not None:
        while proc.poll() is None:
            try:
                p = psutil.Process(pid)
                rss_samples.append(p.memory_info().rss / (1024**2))
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
    """Format numbers to 3 decimals; pass through blanks/strings."""
    if x == "" or x is None:
        return ""
    if isinstance(x, (int, float)):
        return f"{x:.3f}"
    try:
        v = float(x)
        return f"{v:.3f}"
    except Exception:
        return _latex_escape(str(x))


# For headers we DO NOT escape backslashes, so you can add manual \\ line breaks.
def _makecell_header(s: str) -> str:
    return r"\makecell{" + s + "}"


def build_cr_latex_table(wide_df, tools_order, caption, tex_path=LATEX_CR_FILE):
    r"""
    Build LaTeX table for compression ratios using \makecell headers.
    Columns: headers from CR_HEADERS.
    """
    headers = CR_HEADERS
    colspec = "c" * len(headers)

    header_row = " & ".join(_makecell_header(h) for h in headers) + r" \\"

    lines = []
    for _, row in wide_df.iterrows():
        cells = [
            _latex_escape(row["File Name"]),
            _format_cell(row["File Size (MB)"]),
            *(_format_cell(row[t]) for t in tools_order),
        ]
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
        r"\label{tab:cr}" "\n"
        r"\end{table}" "\n"
    )
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)


def build_time_latex_table(time_df, caption, tex_path=LATEX_TIME_FILE):
    r"""
    Build LaTeX table for runtime CSV using \makecell headers.
    Columns: headers from TIME_HEADERS.
    """
    cols    = TIME_HEADERS
    colspec = "c" * len(cols)

    header_row = " & ".join(_makecell_header(h) for h in cols) + r" \\"

    lines = []
    for _, row in time_df.iterrows():
        cells = [row[c] for c in cols]  # keep order
        cells[0] = _latex_escape(str(cells[0]))         # filename escape
        cells = [_format_cell(c) if i != 0 else cells[0] for i, c in enumerate(cells)]
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
        r"\label{tab:runtime}" "\n"
        r"\end{table}" "\n"
    )
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)


def build_mem_latex_table(mem_df, caption, tex_path=LATEX_MEM_FILE):
    r"""
    Build LaTeX table for memory CSV using \makecell headers.
    Columns: headers from MEM_HEADERS.
    """
    cols    = MEM_HEADERS
    colspec = "c" * len(cols)

    header_row = " & ".join(_makecell_header(h) for h in cols) + r" \\"

    lines = []
    for _, row in mem_df.iterrows():
        cells = [row[c] for c in cols]
        cells[0] = _latex_escape(str(cells[0]))         # filename escape
        cells = [_format_cell(c) if i != 0 else cells[0] for i, c in enumerate(cells)]
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
        r"\label{tab:memory}" "\n"
        r"\end{table}" "\n"
    )
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)


def _safe_ratio(numer, denom):
    if denom and denom != 0:
        return round(numer / denom, 3)
    return ""


def main():
    if not os.path.exists(INPUT_FILE_PATH):
        raise RuntimeError(f"Input file not found: {INPUT_FILE_PATH}")

    # Original size
    orig_bytes = os.path.getsize(INPUT_FILE_PATH)
    orig_mb    = round(orig_bytes / (1024**2), 3)

    # Run tools and collect sizes + metrics
    comp_sizes = {}
    metrics    = {}

    for name in TOOLS_ORDER:
        if name not in TOOLS:
            raise RuntimeError(f"Unknown tool in TOOLS_ORDER: {name}")

        out_path = INPUT_FILE_PATH + EXT[name]
        try:
            os.remove(out_path)
        except OSError:
            pass

        cmd = TOOLS[name](INPUT_FILE_PATH, out_path)
        runtime_s, mem_mb, so, se = measure(cmd)

        if not os.path.exists(out_path):
            raise RuntimeError(f"{name} failed to produce {out_path}\nSTDERR:\n{se}")

        comp_sizes[name] = os.path.getsize(out_path)
        metrics[name]    = {"runtime_s": runtime_s, "memory_MB": mem_mb}

    # ---------- CSV 1: compression ratios ----------
    row = {"File Name": INPUT_FILE_NAME, "File Size (MB)": orig_mb}
    for t in TOOLS_ORDER:
        cb = comp_sizes.get(t, 0)
        row[t] = round(orig_bytes / cb, 3) if cb else ""
    wide_df = pd.DataFrame([row])[["File Name", "File Size (MB)"] + TOOLS_ORDER]
    wide_df.to_csv(CR_RESULTS_CSV, index=False)

    # ---------- CSV 2: c_time_results.csv ----------
    tic_time = metrics.get("TIC", {}).get("runtime_s", 0.0)
    time_row = {
        "File name": INPUT_FILE_NAME,
        "File Size (MB)": orig_mb,
        "TIC (s)": round(tic_time, 3),
        "PIC":   _safe_ratio(metrics.get("PIC",   {}).get("runtime_s", 0.0), tic_time),
        "gzip":  _safe_ratio(metrics.get("gzip",  {}).get("runtime_s", 0.0), tic_time),
        "bzip2": _safe_ratio(metrics.get("bzip2", {}).get("runtime_s", 0.0), tic_time),
        "lz4":   _safe_ratio(metrics.get("lz4",   {}).get("runtime_s", 0.0), tic_time),
    }
    time_df = pd.DataFrame([time_row])[TIME_HEADERS]
    time_df.to_csv(C_TIME_CSV, index=False)

    # ---------- CSV 3: mem_results.csv ----------
    tic_mem = metrics.get("TIC", {}).get("memory_MB", 0.0)
    mem_row = {
        "File name": INPUT_FILE_NAME,
        "TIC (MB)": round(tic_mem, 3),
        "PIC":   _safe_ratio(metrics.get("PIC",   {}).get("memory_MB", 0.0), tic_mem),
        "gzip":  _safe_ratio(metrics.get("gzip",  {}).get("memory_MB", 0.0), tic_mem),
        "bzip2": _safe_ratio(metrics.get("bzip2", {}).get("memory_MB", 0.0), tic_mem),
        "lz4":   _safe_ratio(metrics.get("lz4",   {}).get("memory_MB", 0.0), tic_mem),
    }
    mem_df = pd.DataFrame([mem_row])[MEM_HEADERS]
    mem_df.to_csv(MEM_CSV, index=False)

    # ---------- LaTeX tables ----------
    build_cr_latex_table(wide_df, TOOLS_ORDER, LATEX_CAPTION_CR, tex_path=LATEX_CR_FILE)
    build_time_latex_table(time_df, LATEX_CAPTION_TIME, tex_path=LATEX_TIME_FILE)
    build_mem_latex_table(mem_df, LATEX_CAPTION_MEM, tex_path=LATEX_MEM_FILE)

    print(
        f"Wrote: {CR_RESULTS_CSV}, {C_TIME_CSV}, {MEM_CSV}, "
        f"{LATEX_CR_FILE}, {LATEX_TIME_FILE}, {LATEX_MEM_FILE}"
    )


if __name__ == "__main__":
    main()
