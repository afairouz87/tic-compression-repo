#!/usr/bin/env python3
# run_search.py
# - Search a string across compressed artifacts produced by all tools.
# - TIC/PIC: native in-file search (format: -l -t 1 <in> <dummy_out> <query>)
# - gzip/bzip2/lz4: INCLUDE decompression + grep together in one measurement
# - gzip/bzip2: also on-the-fly zgrep/bzgrep (separate modes)
# - Measures runtime & average memory (includes all processes; pipelines supported)
# - Outputs CSVs + LaTeX tables (makecell headers, configurable, ONLY "File name")
# - Optional: --record-outputs to write search outputs to files safely (no deadlocks)

import os, time, subprocess, tempfile, shutil, argparse, re
from statistics import mean
import pandas as pd

# =====================
# User Defaults (can be overridden by CLI)
# =====================
INPUT_FILE_NAME   = "test8.txt"
INPUT_FILE_PATH   = "../textFiles/" + INPUT_FILE_NAME
SEARCH_STRING     = "the"  # default query

# Order for reporting (TIC baseline first)
TOOLS_BASE_ORDER  = ["TIC", "PIC", "gzip", "zgrep", "bzip2", "bzgrep", "lz4"]

# Compression executables / flags (used only to ensure artifacts exist)
PIC_BINARY        = "./pic-v3.1"
TIC_BINARY        = "./epic-v3.1"
PIC_FLAGS_COMP    = ["-c", "-t", "1"]
TIC_FLAGS_COMP    = ["-c", "-t", "1"]

# TIC/PIC native search commands (your format)
# binary -l -t 1 <compressed_input> <dummy_output> <search_string>
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
TIME_HEADERS = ["File name", "TIC (s)", "PIC", "gzip", "zgrep", "bzip2", "bzgrep", "lz4"]
MEM_HEADERS  = ["File name", "TIC (MB)", "PIC", "gzip", "zgrep", "bzip2", "bzgrep", "lz4"]
LATEX_CAPTION_TIME = "Search runtime: TIC absolute (s); others as ratios vs TIC."
LATEX_CAPTION_MEM  = "Search memory: TIC absolute (MB); others as ratios vs TIC."
# -----------------------------------------------------------------------

# Runtime sampling knobs (can be set via --timeout)
MAX_MEASURE_SECONDS = None
SAMPLE_INTERVAL = 0.05


def _try_import_psutil():
    try:
        import psutil  # type: ignore
        return psutil
    except Exception:
        return None


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def measure(command, out_path=None, err_path=None, timeout_s=MAX_MEASURE_SECONDS):
    """
    Run a single command and return (runtime_s, avg_memory_MB, "", "").
    - If out_path/err_path given, stream outputs to files (safe).
    - Otherwise, redirect to DEVNULL (prevents pipe backpressure deadlocks).
    Memory samples include the process and all its children recursively.
    """
    psutil = _try_import_psutil()

    # Open files if requested
    out_target = subprocess.DEVNULL
    err_target = subprocess.DEVNULL
    out_fh = err_fh = None
    try:
        if out_path is not None:
            out_fh = open(out_path, "wb")
            out_target = out_fh
        if err_path is not None:
            err_fh = open(err_path, "wb")
            err_target = err_fh

        start = time.time()
        proc  = subprocess.Popen(command, stdout=out_target, stderr=err_target)
        pid   = proc.pid

        rss_samples = []
        while True:
            if timeout_s is not None and (time.time() - start) > timeout_s:
                # kill process tree
                try:
                    if psutil is not None:
                        p = psutil.Process(pid)
                        for c in p.children(recursive=True):
                            try: c.kill()
                            except Exception: pass
                        try: p.kill()
                        except Exception: pass
                    else:
                        proc.kill()
                except Exception:
                    pass
                break

            if proc.poll() is not None:
                break

            if psutil is not None:
                try:
                    p = psutil.Process(pid)
                    procs = [p] + p.children(recursive=True)
                    rss = 0
                    for q in procs:
                        try:
                            rss += q.memory_info().rss
                        except Exception:
                            pass
                    rss_samples.append(rss / (1024**2))
                except Exception:
                    pass

            time.sleep(SAMPLE_INTERVAL)

        try: proc.wait(timeout=1)
        except Exception: pass

        runtime = round(time.time() - start, 3)
        avg_mb  = round(mean(rss_samples), 3) if rss_samples else 0.0
        return runtime, avg_mb, "", ""
    finally:
        if out_fh: 
            try: out_fh.close()
            except Exception: pass
        if err_fh:
            try: err_fh.close()
            except Exception: pass


def measure_pipeline(commands, out_path=None, err_path=None, timeout_s=MAX_MEASURE_SECONDS):
    """
    Run a pipeline (e.g., [["gzip","-cd",f], ["grep","-F",q]]) and return (runtime_s, avg_memory_MB, "", "").
    - stdout of the LAST stage goes to out_path (or DEVNULL).
    - stderr of the LAST stage goes to err_path (or DEVNULL).
    - earlier stages' stderr to DEVNULL.
    Memory sampling covers ALL live pipeline processes.
    """
    psutil = _try_import_psutil()
    start = time.time()
    procs = []
    prev  = None

    out_fh = err_fh = None
    try:
        out_target_last = subprocess.DEVNULL
        err_target_last = subprocess.DEVNULL
        if out_path is not None:
            out_fh = open(out_path, "wb")
            out_target_last = out_fh
        if err_path is not None:
            err_fh = open(err_path, "wb")
            err_target_last = err_fh

        for i, cmd in enumerate(commands):
            is_last = (i == len(commands) - 1)
            p = subprocess.Popen(
                cmd,
                stdin=None if prev is None else prev.stdout,
                stdout=out_target_last if is_last else subprocess.PIPE,
                stderr=err_target_last if is_last else subprocess.DEVNULL,
            )
            if prev is not None and prev.stdout is not None:
                prev.stdout.close()  # allow SIGPIPE on prev if last exits early
            procs.append(p)
            prev = p

        rss_samples = []
        while True:
            all_done = True
            for p in procs:
                if p.poll() is None:
                    all_done = False
                    break
            if all_done:
                break

            if timeout_s is not None and (time.time() - start) > timeout_s:
                # kill whole pipeline
                if psutil is not None:
                    for p in procs:
                        try:
                            pr = psutil.Process(p.pid)
                            for c in pr.children(recursive=True):
                                try: c.kill()
                                except Exception: pass
                            try: pr.kill()
                            except Exception: pass
                        except Exception:
                            pass
                else:
                    for p in procs:
                        try: p.kill()
                        except Exception: pass
                break

            if psutil is not None:
                try:
                    seen = set()
                    rss = 0
                    for p in procs:
                        if p.poll() is not None:
                            continue
                        try:
                            root = psutil.Process(p.pid)
                        except Exception:
                            continue
                        stack = [root]
                        while stack:
                            q = stack.pop()
                            if q.pid in seen:
                                continue
                            seen.add(q.pid)
                            try:
                                rss += q.memory_info().rss
                            except Exception:
                                pass
                            try:
                                stack.extend(q.children(recursive=False))
                            except Exception:
                                pass
                    rss_samples.append(rss / (1024**2))
                except Exception:
                    pass

            time.sleep(SAMPLE_INTERVAL)

        for p in procs:
            try: p.wait(timeout=1)
            except Exception: pass

        runtime = round(time.time() - start, 3)
        avg_mb  = round(mean(rss_samples), 3) if rss_samples else 0.0
        return runtime, avg_mb, "", ""
    finally:
        if out_fh:
            try: out_fh.close()
            except Exception: pass
        if err_fh:
            try: err_fh.close()
            except Exception: pass


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
        cells = [cells[0]] + [_format_cell(c) for c in cells[1:]]
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
        cells = [cells[0]] + [_format_cell(c) for c in cells[1:]]
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


def parse_args():
    p = argparse.ArgumentParser(description="Run search across compressed files and report time/memory.")
    p.add_argument("-f", "--file", default=INPUT_FILE_PATH, help="Path to the input text file.")
    p.add_argument("-q", "--query", default=SEARCH_STRING, help="Search string.")
    p.add_argument("--record-outputs", action="store_true", help="If set, write tool outputs to files.")
    p.add_argument("-o", "--output-dir", default="search_outputs", help="Directory to store outputs when recording.")
    p.add_argument("--timeout", type=int, default=None, help="Max seconds per tool (kill if exceeded).")
    return p.parse_args()


def main():
    global INPUT_FILE_PATH, INPUT_FILE_NAME, SEARCH_STRING, MAX_MEASURE_SECONDS

    args = parse_args()
    INPUT_FILE_PATH = args.file
    INPUT_FILE_NAME = os.path.basename(args.file)
    SEARCH_STRING   = args.query
    MAX_MEASURE_SECONDS = args.timeout

    # Ensure all compressed inputs exist (not measured)
    for t in ["TIC", "PIC", "gzip", "bzip2", "lz4"]:
        _ensure_compressed(t)

    # Optional output recording setup
    out_dir = None
    base    = os.path.splitext(os.path.basename(INPUT_FILE_PATH))[0]
    qslug   = _slug(SEARCH_STRING)
    if args.record_outputs:
        out_dir = args.output_dir
        os.makedirs(out_dir, exist_ok=True)

    def outpaths(tool):
        if not out_dir:
            return None, None
        return (
            os.path.join(out_dir, f"{tool}_stdout_{base}_{qslug}.txt"),
            os.path.join(out_dir, f"{tool}_stderr_{base}_{qslug}.txt"),
        )

    # Temp dir for dummy outputs (TIC/PIC search)
    tmp_dir = tempfile.mkdtemp(prefix="search_work_")

    try:
        metrics = {}  # tool -> {runtime_s, memory_MB}

        # --- TIC native search (baseline) ---
        tic_cfile = _compressed_path("TIC")
        tic_dummy = os.path.join(tmp_dir, "tic_search.out")
        out_p, err_p = outpaths("TIC")
        runtime, mem, *_ = measure(TIC_SEARCH_CMD(tic_cfile, tic_dummy, SEARCH_STRING),
                                   out_path=out_p, err_path=err_p)
        metrics["TIC"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- PIC native search ---
        pic_cfile = _compressed_path("PIC")
        pic_dummy = os.path.join(tmp_dir, "pic_search.out")
        out_p, err_p = outpaths("PIC")
        runtime, mem, *_ = measure(PIC_SEARCH_CMD(pic_cfile, pic_dummy, SEARCH_STRING),
                                   out_path=out_p, err_path=err_p)
        metrics["PIC"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- gzip: INCLUDE decompression + grep together ---
        gz_cfile = _compressed_path("gzip")
        out_p, err_p = outpaths("gzip")
        runtime, mem, *_ = measure_pipeline(
            [["gzip", "-cd", gz_cfile], ["grep", "-F", SEARCH_STRING]],
            out_path=out_p, err_path=err_p
        )
        metrics["gzip"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- zgrep on-the-fly ---
        out_p, err_p = outpaths("zgrep")
        runtime, mem, *_ = measure(["zgrep", "-F", SEARCH_STRING, gz_cfile],
                                   out_path=out_p, err_path=err_p)
        metrics["zgrep"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- bzip2: INCLUDE decompression + grep together ---
        bz_cfile = _compressed_path("bzip2")
        out_p, err_p = outpaths("bzip2")
        runtime, mem, *_ = measure_pipeline(
            [["bzip2", "-cd", bz_cfile], ["grep", "-F", SEARCH_STRING]],
            out_path=out_p, err_path=err_p
        )
        metrics["bzip2"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- bzgrep on-the-fly ---
        out_p, err_p = outpaths("bzgrep")
        runtime, mem, *_ = measure(["bzgrep", "-F", SEARCH_STRING, bz_cfile],
                                   out_path=out_p, err_path=err_p)
        metrics["bzgrep"] = {"runtime_s": runtime, "memory_MB": mem}

        # --- lz4: INCLUDE decompression + grep together ---
        lz4_cfile = _compressed_path("lz4")
        out_p, err_p = outpaths("lz4")
        runtime, mem, *_ = measure_pipeline(
            [["lz4", "-d", "-c", lz4_cfile], ["grep", "-F", SEARCH_STRING]],
            out_path=out_p, err_path=err_p
        )
        metrics["lz4"] = {"runtime_s": runtime, "memory_MB": mem}

        # ---------- CSV: search time (TIC absolute, others as ratios) ----------
        time_row = {"File name": INPUT_FILE_NAME, "TIC (s)": round(metrics["TIC"]["runtime_s"], 3)}
        for t in TOOLS_BASE_ORDER:
            if t == "TIC":
                continue
            time_row[t] = _safe_ratio(metrics.get(t, {}).get("runtime_s", 0.0),
                                      metrics["TIC"]["runtime_s"])
        time_df = pd.DataFrame([time_row])[TIME_HEADERS]
        time_df.to_csv(TIME_CSV, index=False)

        # ---------- CSV: search memory (TIC absolute, others as ratios) ----------
        mem_row = {"File name": INPUT_FILE_NAME, "TIC (MB)": round(metrics["TIC"]["memory_MB"], 3)}
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
        if args.record_outputs:
            print(f"Captured outputs in: {out_dir}")

    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    main()
