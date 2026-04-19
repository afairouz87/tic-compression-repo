#!/usr/bin/env python3
"""
download_gutenberg_texts.py

Automatically discover and download Project Gutenberg plain-text UTF-8 ebooks,
while enforcing English both before and after download.

Behavior:
1. Discover candidate ebook IDs from an English-filtered search.
2. Download the .txt.utf-8 text file for each candidate.
3. Verify after download that the text header indicates English.
4. Keep only English books that satisfy the minimum-size threshold.
5. Stop when the local usable pool reaches the requested target size.

Example:
    python download_gutenberg_texts.py \
        --out-dir data/raw \
        --meta-dir data/metadata \
        --target-pool-mb 1200 \
        --min-book-mb 0 \
        --max-pages 40
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Set
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_OUT_DIR = Path("data/raw")
DEFAULT_META_DIR = Path("data/metadata")
DEFAULT_DELAY = 1.0
DEFAULT_TIMEOUT = 60
DEFAULT_USER_AGENT = "CompressionResearchDownloader/1.0"
DEFAULT_TARGET_POOL_MB = 1200.0
DEFAULT_MIN_BOOK_MB = 0.0
DEFAULT_MAX_PAGES = 30
DEFAULT_LANGUAGE = "en"

MB = 1024 * 1024


@dataclass
class DownloadRecord:
    gutenberg_id: int
    title: str
    source_url: str
    local_file_path: str
    downloaded_size_bytes: int
    status: str
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatically discover and download English Gutenberg plain-text UTF-8 ebooks."
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--meta-dir", type=Path, default=DEFAULT_META_DIR)
    parser.add_argument("--force", action="store_true", help="Redownload existing files.")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--user-agent", type=str, default=DEFAULT_USER_AGENT)

    parser.add_argument(
        "--target-pool-mb",
        type=float,
        default=DEFAULT_TARGET_POOL_MB,
        help="Stop downloading once total kept-book size reaches this many MB.",
    )
    parser.add_argument(
        "--min-book-mb",
        type=float,
        default=DEFAULT_MIN_BOOK_MB,
        help="Keep only books at or above this size in MB.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Maximum number of Gutenberg search-result pages to scan.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=DEFAULT_LANGUAGE,
        help="Language code used in discovery search. Default: en",
    )
    parser.add_argument(
        "--sort-order",
        type=str,
        default="downloads",
        choices=["downloads", "release_date", "title", "author"],
        help="Result ordering for discovery.",
    )
    return parser.parse_args()


def fetch_url_text(url: str, user_agent: str, timeout: int) -> str:
    req = Request(url, headers={"User-Agent": user_agent})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_url_bytes(url: str, user_agent: str, timeout: int) -> bytes:
    req = Request(url, headers={"User-Agent": user_agent})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def search_results_url(page: int, language: str, sort_order: str) -> str:
    start_index = (page - 1) * 25 + 1
    query = quote(f"language:{language}")
    return (
        "https://www.gutenberg.org/ebooks/search/"
        f"?query={query}&sort_order={sort_order}&start_index={start_index}"
    )


def extract_ebook_ids_from_html(html: str) -> List[int]:
    matches = re.findall(r'href="/ebooks/(\d+)"', html)
    ids: List[int] = []
    seen = set()
    for m in matches:
        gid = int(m)
        if gid not in seen:
            seen.add(gid)
            ids.append(gid)
    return ids


def build_text_url(gutenberg_id: int) -> str:
    return f"https://www.gutenberg.org/ebooks/{gutenberg_id}.txt.utf-8"


def build_local_filename(gutenberg_id: int) -> str:
    return f"pg_{gutenberg_id}.txt"


def extract_title_from_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()[:250] if line.strip()]
    for line in lines:
        if line.startswith("Title:"):
            return line.removeprefix("Title:").strip()
    for line in lines:
        if not line.startswith("***") and "Project Gutenberg" not in line:
            return line[:200]
    return ""


def extract_language_from_text(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines()[:300] if line.strip()]
    for line in lines:
        if line.lower().startswith("language:"):
            return line.split(":", 1)[1].strip()
    return None


def is_english_text(text: str) -> bool:
    lang = extract_language_from_text(text)
    if lang is None:
        return False
    return lang.strip().lower() == "english"


def existing_total_bytes(out_dir: Path) -> int:
    if not out_dir.exists():
        return 0
    return sum(p.stat().st_size for p in out_dir.glob("pg_*.txt") if p.is_file())


def validate_existing_file_as_english(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return is_english_text(text)
    except Exception:
        return False


def download_one(
    gutenberg_id: int,
    out_dir: Path,
    force: bool,
    user_agent: str,
    timeout: int,
    min_book_bytes: int,
) -> DownloadRecord:
    source_url = build_text_url(gutenberg_id)
    local_path = out_dir / build_local_filename(gutenberg_id)

    if local_path.exists() and not force:
        size = local_path.stat().st_size
        title = ""
        try:
            existing_text = local_path.read_text(encoding="utf-8", errors="ignore")
            title = extract_title_from_text(existing_text)
            if not is_english_text(existing_text):
                return DownloadRecord(
                    gutenberg_id=gutenberg_id,
                    title=title,
                    source_url=source_url,
                    local_file_path=str(local_path),
                    downloaded_size_bytes=size,
                    status="skipped_non_english_existing",
                    note="Existing file is not marked as English",
                )
        except Exception:
            return DownloadRecord(
                gutenberg_id=gutenberg_id,
                title="",
                source_url=source_url,
                local_file_path=str(local_path),
                downloaded_size_bytes=size,
                status="skipped_unreadable_existing",
                note="Existing file could not be validated",
            )

        if size < min_book_bytes:
            return DownloadRecord(
                gutenberg_id=gutenberg_id,
                title=title,
                source_url=source_url,
                local_file_path=str(local_path),
                downloaded_size_bytes=size,
                status="skipped_small_existing",
                note="Existing file below minimum size threshold",
            )

        return DownloadRecord(
            gutenberg_id=gutenberg_id,
            title=title,
            source_url=source_url,
            local_file_path=str(local_path),
            downloaded_size_bytes=size,
            status="skipped_existing",
            note="English file already exists",
        )

    try:
        content = fetch_url_bytes(source_url, user_agent=user_agent, timeout=timeout)
        text = content.decode("utf-8", errors="ignore")
        size = len(content)
        title = extract_title_from_text(text)

        if not is_english_text(text):
            return DownloadRecord(
                gutenberg_id=gutenberg_id,
                title=title,
                source_url=source_url,
                local_file_path=str(local_path),
                downloaded_size_bytes=size,
                status="skipped_non_english",
                note="Downloaded file is not marked as English",
            )

        if size < min_book_bytes:
            return DownloadRecord(
                gutenberg_id=gutenberg_id,
                title=title,
                source_url=source_url,
                local_file_path=str(local_path),
                downloaded_size_bytes=size,
                status="skipped_small",
                note="Downloaded English text is below minimum size threshold",
            )

        local_path.write_bytes(content)

        return DownloadRecord(
            gutenberg_id=gutenberg_id,
            title=title,
            source_url=source_url,
            local_file_path=str(local_path),
            downloaded_size_bytes=size,
            status="downloaded",
            note="",
        )

    except HTTPError as e:
        return DownloadRecord(
            gutenberg_id=gutenberg_id,
            title="",
            source_url=source_url,
            local_file_path=str(local_path),
            downloaded_size_bytes=0,
            status="failed",
            note=f"HTTPError {e.code}: {e.reason}",
        )
    except URLError as e:
        return DownloadRecord(
            gutenberg_id=gutenberg_id,
            title="",
            source_url=source_url,
            local_file_path=str(local_path),
            downloaded_size_bytes=0,
            status="failed",
            note=f"URLError: {e.reason}",
        )
    except Exception as e:
        return DownloadRecord(
            gutenberg_id=gutenberg_id,
            title="",
            source_url=source_url,
            local_file_path=str(local_path),
            downloaded_size_bytes=0,
            status="failed",
            note=f"{type(e).__name__}: {e}",
        )


def write_metadata(records: List[DownloadRecord], meta_dir: Path) -> None:
    meta_dir.mkdir(parents=True, exist_ok=True)

    csv_path = meta_dir / "gutenberg_downloads.csv"
    json_path = meta_dir / "gutenberg_downloads.json"

    fieldnames = [
        "gutenberg_id",
        "title",
        "source_url",
        "local_file_path",
        "downloaded_size_bytes",
        "status",
        "note",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))

    json_path.write_text(
        json.dumps([asdict(r) for r in records], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def discover_ids(
    max_pages: int,
    language: str,
    sort_order: str,
    user_agent: str,
    timeout: int,
    delay: float,
) -> List[int]:
    discovered: List[int] = []
    seen: Set[int] = set()

    for page in range(1, max_pages + 1):
        url = search_results_url(page, language, sort_order)
        print(f"[discover] page {page}: {url}")
        try:
            html = fetch_url_text(url, user_agent=user_agent, timeout=timeout)
        except Exception as e:
            print(f"  warning: failed to fetch page {page}: {e}")
            continue

        ids = extract_ebook_ids_from_html(html)
        new_ids = [gid for gid in ids if gid not in seen]

        if not new_ids:
            print("  no new ebook IDs found on this page")
        else:
            print(f"  found {len(new_ids)} new ebook IDs")

        for gid in new_ids:
            seen.add(gid)
            discovered.append(gid)

        if delay > 0:
            time.sleep(delay)

    return discovered


def main() -> int:
    args = parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.meta_dir.mkdir(parents=True, exist_ok=True)

    min_book_bytes = int(args.min_book_mb * MB)
    target_pool_bytes = int(args.target_pool_mb * MB)

    records: List[DownloadRecord] = []

    current_pool = existing_total_bytes(args.out_dir)
    print(f"Existing local pool size: {current_pool / MB:.2f} MB")

    if current_pool >= target_pool_bytes and not args.force:
        print("Target pool already satisfied by existing files.")
        return 0

    discovered_ids = discover_ids(
        max_pages=args.max_pages,
        language=args.language,
        sort_order=args.sort_order,
        user_agent=args.user_agent,
        timeout=args.timeout,
        delay=args.delay,
    )

    if not discovered_ids:
        print("No ebook IDs discovered.", file=sys.stderr)
        return 1

    total_ids = len(discovered_ids)
    for idx, gutenberg_id in enumerate(discovered_ids, start=1):
        print(f"[download {idx}/{total_ids}] Gutenberg ID {gutenberg_id}")

        record = download_one(
            gutenberg_id=gutenberg_id,
            out_dir=args.out_dir,
            force=args.force,
            user_agent=args.user_agent,
            timeout=args.timeout,
            min_book_bytes=min_book_bytes,
        )
        records.append(record)

        print(
            f"  status={record.status}, "
            f"size={record.downloaded_size_bytes}, "
            f"path={record.local_file_path}"
        )
        if record.note:
            print(f"  note={record.note}")

        if record.status in {"downloaded", "skipped_existing"}:
            current_pool = existing_total_bytes(args.out_dir)
            print(f"  current usable English pool: {current_pool / MB:.2f} MB")
            if current_pool >= target_pool_bytes:
                print("Target pool size reached.")
                break

        if idx < total_ids and args.delay > 0:
            time.sleep(args.delay)

    write_metadata(records, args.meta_dir)

    downloaded = sum(1 for r in records if r.status == "downloaded")
    skipped_existing = sum(1 for r in records if r.status == "skipped_existing")
    skipped_small = sum(1 for r in records if r.status in {"skipped_small", "skipped_small_existing"})
    skipped_non_english = sum(
        1 for r in records if r.status in {"skipped_non_english", "skipped_non_english_existing"}
    )
    failed = sum(1 for r in records if r.status == "failed")

    print("\nDone.")
    print(f"Downloaded:           {downloaded}")
    print(f"Skipped existing:     {skipped_existing}")
    print(f"Skipped too small:    {skipped_small}")
    print(f"Skipped non-English:  {skipped_non_english}")
    print(f"Failed:               {failed}")
    print(f"Final English pool:   {existing_total_bytes(args.out_dir) / MB:.2f} MB")
    print(f"Metadata CSV:         {args.meta_dir / 'gutenberg_downloads.csv'}")
    print(f"Metadata JSON:        {args.meta_dir / 'gutenberg_downloads.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

