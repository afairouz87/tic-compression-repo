#!/usr/bin/env python3

from pathlib import Path
import subprocess

# folder = Path("../standard_ebooks_output/txt_clean")
folder = Path("../gutenberg_ebooks/raw")

for txt in sorted(folder.glob("*.txt")):
    out = "/tmp/test.tic"

    print(f"[TEST] {txt}", flush=True)

    try:
        result = subprocess.run(
            [
                "./epic-v3.1",
                "-c",
                "-t",
                "2",
                str(txt),
                out,
            ],
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        print(f"[STUCK] {txt}", flush=True)
        break

    if result.returncode != 0:
        print(f"[FAILED] {txt} return_code={result.returncode}", flush=True)
        break

    print(f"[OK] {txt}", flush=True)