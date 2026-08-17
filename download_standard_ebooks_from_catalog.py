#!/usr/bin/env python3
"""
download_standard_ebooks_from_catalog.py

Download Standard Ebooks from a saved catalog and convert them to clean TXT.

Reads:
- standard_ebooks_output/catalog.jsonl

Writes:
- standard_ebooks_output/epub/
- standard_ebooks_output/txt_clean/
- standard_ebooks_output/downloaded_books.txt
- standard_ebooks_output/download_state.json
- standard_ebooks_output/deferred_books.jsonl
- standard_ebooks_output/download_from_catalog.log

Features:
- download-only workflow (no page crawling)
- direct EPUB URL download only
- manifest-based skipping
- quota-based stopping
- repeated-429 handling with global cooldown
- defer blocked books and retry them at end of run
- still-blocked books remain deferred for future runs
"""

from __future__ import annotations

import html
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT

# ============================================================
# Configuration
# ============================================================

OUTPUT_DIR = Path("standard_ebooks_output")
CATALOG_JSONL = OUTPUT_DIR / "catalog.jsonl"
EPUB_DIR = OUTPUT_DIR / "epub"
CLEAN_DIR = OUTPUT_DIR / "txt_clean"
MANIFEST_FILE = OUTPUT_DIR / "downloaded_books.txt"
DOWNLOAD_STATE_FILE = OUTPUT_DIR / "download_state.json"
DEFERRED_FILE = OUTPUT_DIR / "deferred_books.jsonl"
LOG_FILE = OUTPUT_DIR / "download_from_catalog.log"

TARGET_TOTAL_TXT_MB = 750
TARGET_TOTAL_TXT_BYTES = TARGET_TOTAL_TXT_MB * 1024 * 1024

REQUEST_TIMEOUT = 45
SLEEP_RANGE = (4.0, 6.0)

MAX_DOWNLOAD_RETRIES = 2
BACKOFF_BASE_SECONDS = 60
GLOBAL_COOLDOWN_SECONDS = 600

OVERWRITE_EXISTING = False
SAVE_EPUB = True

NORMALIZE_QUOTES = True
NORMALIZE_DASHES = True
REMOVE_EXTRA_BLANK_LINES = False
MIN_TEXT_CHARS = 3000

USER_AGENT = (
    "Mozilla/5.0 (compatible; StandardEbooksDownloader/1.0; +research-use)"
)

# ============================================================
# Logging
# ============================================================

def setup_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# ============================================================
# Session
# ============================================================

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# ============================================================
# Filesystem / state helpers
# ============================================================

def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EPUB_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

def polite_sleep() -> None:
    time.sleep(random.uniform(*SLEEP_RANGE))

def slugify_filename(text: str, max_len: int = 180) -> str:
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]

def get_total_txt_size_bytes(directory: Path) -> int:
    total = 0
    for path in directory.glob("*.txt"):
        if path.is_file():
            total += path.stat().st_size
    return total

def quota_reached() -> bool:
    return get_total_txt_size_bytes(CLEAN_DIR) >= TARGET_TOTAL_TXT_BYTES

def normalize_book_url(url: str) -> str:
    return url.rstrip("/")

def load_downloaded_manifest() -> set[str]:
    if not MANIFEST_FILE.exists():
        return set()

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        return {normalize_book_url(line.strip()) for line in f if line.strip()}

def append_to_downloaded_manifest(book_page_url: str) -> None:
    normalized = normalize_book_url(book_page_url)
    existing = load_downloaded_manifest()

    if normalized in existing:
        return

    with open(MANIFEST_FILE, "a", encoding="utf-8") as f:
        f.write(normalized + "\n")

def load_download_state() -> dict:
    if not DOWNLOAD_STATE_FILE.exists():
        return {
            "catalog_index": 0,
            "last_updated": None,
            "last_book_url": None,
        }

    try:
        with open(DOWNLOAD_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "catalog_index": int(data.get("catalog_index", 0)),
            "last_updated": data.get("last_updated"),
            "last_book_url": data.get("last_book_url"),
        }
    except Exception as exc:
        logging.warning("Failed to load download state (%s). Starting from index 0.", exc)
        return {
            "catalog_index": 0,
            "last_updated": None,
            "last_book_url": None,
        }

def save_download_state(catalog_index: int, last_book_url: Optional[str]) -> None:
    data = {
        "catalog_index": catalog_index,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_book_url": last_book_url,
    }

    with open(DOWNLOAD_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ============================================================
# Catalog helpers
# ============================================================

def load_catalog_entries() -> list[dict]:
    if not CATALOG_JSONL.exists():
        raise FileNotFoundError(f"Catalog file not found: {CATALOG_JSONL}")

    entries: list[dict] = []

    with open(CATALOG_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            book_page_url = entry.get("book_page_url")
            epub_url = entry.get("epub_url")
            title = entry.get("title", "untitled")

            if not book_page_url or not epub_url:
                continue

            entries.append({
                "book_page_url": normalize_book_url(book_page_url),
                "epub_url": epub_url,
                "title": title,
            })

    return entries

# ============================================================
# Deferred helpers
# ============================================================

def load_deferred_entries() -> list[dict]:
    if not DEFERRED_FILE.exists():
        return []

    entries: list[dict] = []
    with open(DEFERRED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries

def save_deferred_entries(entries: list[dict]) -> None:
    with open(DEFERRED_FILE, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def append_deferred_entry(entry: dict, reason: str) -> None:
    existing = load_deferred_entries()
    existing_urls = {
        normalize_book_url(x["book_page_url"])
        for x in existing
        if "book_page_url" in x
    }

    normalized_url = normalize_book_url(entry["book_page_url"])
    if normalized_url in existing_urls:
        return

    deferred_entry = {
        "book_page_url": normalized_url,
        "epub_url": entry["epub_url"],
        "title": entry.get("title", "untitled"),
        "deferred_reason": reason,
        "deferred_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    existing.append(deferred_entry)
    save_deferred_entries(existing)

def remove_downloaded_from_deferred(downloaded_manifest: set[str]) -> None:
    entries = load_deferred_entries()
    remaining = [
        x for x in entries
        if normalize_book_url(x.get("book_page_url", "")) not in downloaded_manifest
    ]
    save_deferred_entries(remaining)

# ============================================================
# Global cooldown helpers
# ============================================================

def load_global_pause_until() -> float:
    return 0.0

def wait_if_globally_paused(pause_until: float) -> float:
    now = time.time()
    while now < pause_until:
        remaining = pause_until - now
        logging.info("Global cooldown active. Waiting %.1f more seconds.", remaining)
        time.sleep(min(10.0, remaining))
        now = time.time()
    return 0.0

# ============================================================
# Download helpers
# ============================================================

def inspect_downloaded_file(epub_path: Path) -> None:
    try:
        with open(epub_path, "rb") as f:
            head = f.read(200)

        if not head.startswith(b"PK"):
            logging.warning("File does not start with ZIP signature: %s", epub_path.name)
            logging.warning("First bytes: %r", head[:80])
    except Exception as exc:
        logging.warning("Could not inspect file %s (%s)", epub_path, exc)

def download_epub(url: str, dest: Path) -> tuple[bool, bool]:
    """
    Returns:
        (success, hit_rate_limit)
    """
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with session.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True) as response:
                #if response.status_code == 429:
                #    retry_after = response.headers.get("Retry-After")
                #    if retry_after and retry_after.isdigit():
                #        wait_time = int(retry_after)
                #    else:
                #        wait_time = BACKOFF_BASE_SECONDS * attempt

                #    logging.warning(
                #        "429 Too Many Requests for %s | retry %d/%d | waiting %.1f seconds",
                #        url,
                #        attempt,
                #        MAX_DOWNLOAD_RETRIES,
                #        wait_time
                #    )
                #    time.sleep(wait_time)
                #    continue
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = int(retry_after)
                    else:
                        wait_time = BACKOFF_BASE_SECONDS

                    logging.warning(
                        "429 Too Many Requests for %s | deferring immediately | suggested cooldown %.1f seconds",
                        url,
                        wait_time
                    )

                    return False, True

                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "").lower()
                first_chunk = None
                chunks = []

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        if first_chunk is None:
                            first_chunk = chunk
                        chunks.append(chunk)

                if first_chunk is None:
                    logging.warning("Empty response for %s", url)
                    return False, False

                if not first_chunk.startswith(b"PK"):
                    logging.warning(
                        "Downloaded file is not a real EPUB from %s | Content-Type=%s",
                        url,
                        content_type
                    )

                    debug_path = dest.with_suffix(".debug.html")
                    with open(debug_path, "wb") as f:
                        for chunk in chunks:
                            f.write(chunk)

                    logging.warning("Saved debug response to %s", debug_path)
                    return False, False

                with open(dest, "wb") as f:
                    for chunk in chunks:
                        f.write(chunk)

                return True, False

        except requests.HTTPError as exc:
            logging.warning("Failed to download %s (%s)", url, exc)
            return False, False

        except Exception as exc:
            logging.warning("Failed to download %s (%s)", url, exc)
            return False, False

    logging.warning("Exceeded retry limit after repeated 429 responses: %s", url)
    return False, True

# ============================================================
# EPUB extraction / text normalization
# ============================================================

def normalize_text(text: str) -> str:
    text = html.unescape(text)

    if NORMALIZE_QUOTES:
        text = (
            text.replace("“", '"')
                .replace("”", '"')
                .replace("‘", "'")
                .replace("’", "'")
        )

    if NORMALIZE_DASHES:
        text = text.replace("—", "--").replace("–", "-")

    text = (
        text.replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u2060", "")
            .replace("\u00ad", "")
    )

    text = text.replace("\u00a0", " ")
    text = text.replace("\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"[ ]{2,}", " ", text)

    if REMOVE_EXTRA_BLANK_LINES:
        text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def should_skip_document(item_name: str) -> bool:
    lowered = item_name.lower()
    skip_keywords = [
        "toc",
        "titlepage",
        "imprint",
        "copyright-page",
        "colophon",
        "halftitle",
        "loi",
        "endnotes",
    ]
    return any(key in lowered for key in skip_keywords)

def epub_to_text(epub_path: Path) -> str:
    book = epub.read_epub(str(epub_path))
    chunks: list[str] = []

    block_tags = {
        "p", "blockquote",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "li"
    }

    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue

        item_name = getattr(item, "file_name", "") or ""
        if should_skip_document(item_name):
            continue

        soup = BeautifulSoup(item.get_content(), "html.parser")

        for tag in soup(["script", "style", "nav"]):
            tag.decompose()

        body = soup.body if soup.body else soup
        page_blocks: list[str] = []

        for tag in body.find_all(block_tags):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue

            text = re.sub(r"\s+", " ", text).strip()
            if text:
                page_blocks.append(text)

        if page_blocks:
            chunks.append("\n\n".join(page_blocks))

    combined = "\n\n".join(chunks)
    return normalize_text(combined)

def save_text_file(text: str, dest: Path) -> None:
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)

# ============================================================
# Main processing
# ============================================================

def process_catalog_entry(entry: dict) -> tuple[bool, bool, bool]:
    """
    Returns:
        (success, hit_rate_limit, should_defer)
    """
    book_page_url = normalize_book_url(entry["book_page_url"])
    epub_url = entry["epub_url"]
    title = entry.get("title", "untitled")
    safe_title = slugify_filename(title)

    epub_path = EPUB_DIR / f"{safe_title}.epub"
    clean_path = CLEAN_DIR / f"{safe_title}.txt"

    if clean_path.exists() and not OVERWRITE_EXISTING:
        append_to_downloaded_manifest(book_page_url)
        logging.info("TXT already exists, skipping: %s", title)
        return True, False, False

    if not epub_path.exists() or OVERWRITE_EXISTING:
        logging.info("Downloading EPUB: %s", epub_url)
        ok, hit_rate_limit = download_epub(epub_url, epub_path)
        if not ok:
            if hit_rate_limit:
                return False, True, True
            return False, False, False

        inspect_downloaded_file(epub_path)
        polite_sleep()

    try:
        text_clean = epub_to_text(epub_path)
    except Exception as exc:
        logging.warning("Failed to convert EPUB to text for %s (%s)", epub_path.name, exc)
        return False, False, False

    if len(text_clean) < MIN_TEXT_CHARS:
        logging.warning("Extracted text too short for %s", title)
        return False, False, False

    save_text_file(text_clean, clean_path)
    append_to_downloaded_manifest(book_page_url)
    logging.info("Saved TXT: %s", clean_path)

    if not SAVE_EPUB:
        try:
            epub_path.unlink(missing_ok=True)
        except Exception:
            pass

    return True, False, False

def main() -> None:
    ensure_dirs()
    setup_logging()

    logging.info("=" * 60)
    logging.info("NEW DOWNLOAD RUN STARTED")
    logging.info("=" * 60)

    if not CATALOG_JSONL.exists():
        logging.error("Catalog file not found: %s", CATALOG_JSONL.resolve())
        logging.error("Run build_standard_ebooks_catalog.py first.")
        return

    current_total = get_total_txt_size_bytes(CLEAN_DIR)
    logging.info("Current TXT size: %.2f MB", current_total / (1024 * 1024))
    logging.info("Target TXT size: %.2f MB", TARGET_TOTAL_TXT_MB)

    if quota_reached():
        logging.info("Target already reached. TXT files saved in: %s", CLEAN_DIR.resolve())
        return

    catalog_entries = load_catalog_entries()
    downloaded_manifest = load_downloaded_manifest()
    download_state = load_download_state()

    logging.info("Catalog entries loaded: %d", len(catalog_entries))
    logging.info("Manifest entries loaded: %d", len(downloaded_manifest))
    logging.info(
        "Download state: catalog_index=%d | last_book_url=%s",
        download_state["catalog_index"],
        download_state["last_book_url"],
    )

    start_index = max(0, min(download_state["catalog_index"], len(catalog_entries)))
    pause_until = load_global_pause_until()

    success = 0
    failed = 0
    consecutive_429s = 0

    for idx in range(start_index, len(catalog_entries)):
        if quota_reached():
            logging.info("Reached target total TXT size.")
            break

        pause_until = wait_if_globally_paused(pause_until)

        entry = catalog_entries[idx]
        book_page_url = normalize_book_url(entry["book_page_url"])

        if book_page_url in downloaded_manifest:
            save_download_state(idx + 1, book_page_url)
            continue

        current_total = get_total_txt_size_bytes(CLEAN_DIR)

        logging.info(
            "Processing %d/%d | Current total: %.2f MB / %.2f MB | Title: %s",
            idx + 1,
            len(catalog_entries),
            current_total / (1024 * 1024),
            TARGET_TOTAL_TXT_MB,
            entry.get("title", "untitled"),
        )

        ok, hit_rate_limit, should_defer = process_catalog_entry(entry)

        if ok:
            success += 1
            consecutive_429s = 0
            downloaded_manifest.add(book_page_url)
        else:
            failed += 1

            if should_defer:
                append_deferred_entry(entry, reason="rate_limited")
                logging.warning("Deferred book for later retry: %s", entry.get("title", "untitled"))

            if hit_rate_limit:
                consecutive_429s += 1
                pause_until = max(pause_until, time.time() + GLOBAL_COOLDOWN_SECONDS)
                logging.warning(
                    "Activating global cooldown for %.1f seconds after repeated 429s.",
                    GLOBAL_COOLDOWN_SECONDS
                )
            else:
                consecutive_429s = 0

        save_download_state(idx + 1, book_page_url)

        if consecutive_429s >= 5:
            logging.warning(
                "Stopping early after %d consecutive rate-limit failures. Re-run later to continue safely.",
                consecutive_429s
            )
            break

        if quota_reached():
            logging.info("Quota reached after processing current book.")
            break

        polite_sleep()

    # Deferred retry pass
    if not quota_reached():
        deferred_entries = load_deferred_entries()

        if deferred_entries:
            logging.info("Starting deferred retry pass with %d books.", len(deferred_entries))

            remaining_deferred = []

            for entry in deferred_entries:
                if quota_reached():
                    break

                pause_until = wait_if_globally_paused(pause_until)

                book_page_url = normalize_book_url(entry["book_page_url"])
                if book_page_url in downloaded_manifest:
                    continue

                logging.info("Deferred retry: %s", entry.get("title", "untitled"))

                ok, hit_rate_limit, should_defer = process_catalog_entry(entry)

                if ok:
                    success += 1
                    consecutive_429s = 0
                    downloaded_manifest.add(book_page_url)
                else:
                    failed += 1
                    remaining_deferred.append(entry)

                    if hit_rate_limit:
                        consecutive_429s += 1
                        pause_until = max(pause_until, time.time() + GLOBAL_COOLDOWN_SECONDS)
                    else:
                        consecutive_429s = 0

                polite_sleep()

            save_deferred_entries(remaining_deferred)
            logging.info(
                "Deferred retry pass finished. Remaining deferred books: %d",
                len(remaining_deferred)
            )

    remove_downloaded_from_deferred(load_downloaded_manifest())

    final_total = get_total_txt_size_bytes(CLEAN_DIR)

    logging.info("FINAL REPORT")
    logging.info("Total success this run: %d", success)
    logging.info("Total failed this run: %d", failed)
    logging.info("Final size: %.2f MB", final_total / (1024 * 1024))
    logging.info("Manifest size: %d", len(load_downloaded_manifest()))
    logging.info("Deferred count: %d", len(load_deferred_entries()))
    logging.info("TXT files saved in: %s", CLEAN_DIR.resolve())
    logging.info("Done.")

if __name__ == "__main__":
    main()

