#!/usr/bin/env python3
"""
Download Standard Ebooks compatible EPUB files and convert them to clean TXT.

Features:
- Crawls https://standardebooks.org/ebooks using explicit page-number pagination
- Collects ebook page links across listing pages
- Retries listing-page fetches with backoff on transient failures
- Finds the preferred Compatible EPUB download link
- Appends ?source=download to the EPUB URL
- Downloads EPUB files
- Verifies the file is a real EPUB (ZIP signature check)
- Saves debug HTML if the server returns a webpage instead of EPUB
- Extracts clean text from EPUB
- Preserves paragraph breaks
- Removes common hidden Unicode artifacts
- Saves only clean .txt files
- Stops automatically when total TXT size reaches the configured quota
- Handles HTTP 429 Too Many Requests with retry + backoff
- Stops early after too many consecutive rate-limit responses
- Skips already-downloaded books using a manifest file

Dependencies:
    pip install requests beautifulsoup4 ebooklib lxml
"""

from __future__ import annotations

import html
import logging
import random
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT

# ============================================================
# Configuration
# ============================================================

BASE_URL = "https://standardebooks.org"
START_URL = "https://standardebooks.org/ebooks"

OUTPUT_DIR = Path("standard_ebooks_output")
EPUB_DIR = OUTPUT_DIR / "epub"
CLEAN_DIR = OUTPUT_DIR / "txt_clean"
MANIFEST_FILE = OUTPUT_DIR / "downloaded_books.txt"
LOG_FILE = OUTPUT_DIR / "download.log"

TARGET_TOTAL_TXT_MB = 700
TARGET_TOTAL_TXT_BYTES = TARGET_TOTAL_TXT_MB * 1024 * 1024

REQUEST_TIMEOUT = 30
SLEEP_RANGE = (5.0, 10.0)
OVERWRITE_EXISTING = False
SAVE_EPUB = True

NORMALIZE_QUOTES = True
NORMALIZE_DASHES = True
REMOVE_EXTRA_BLANK_LINES = False
MIN_TEXT_CHARS = 3000

MAX_DOWNLOAD_RETRIES = 6
BACKOFF_BASE_SECONDS = 20
MAX_CONSECUTIVE_429S = 5

MAX_HTML_RETRIES = 5
HTML_BACKOFF_BASE_SECONDS = 10

# Stop crawl after this many consecutive listing pages add no new books
# or fail to fetch.
MAX_CONSECUTIVE_EMPTY_PAGES = 3

USER_AGENT = (
    "Mozilla/5.0 (compatible; StandardEbooksTextDownloader/1.0; +research-use)"
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
# Helpers
# ============================================================

def ensure_dirs() -> None:
    EPUB_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)


def polite_sleep() -> None:
    time.sleep(random.uniform(*SLEEP_RANGE))


def slugify_filename(text: str, max_len: int = 180) -> str:
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def fetch_html(url: str) -> Optional[str]:
    for attempt in range(1, MAX_HTML_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            return response.text

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None

            if status == 429:
                retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                if retry_after and retry_after.isdigit():
                    wait_time = int(retry_after)
                else:
                    wait_time = HTML_BACKOFF_BASE_SECONDS * attempt

                logging.warning(
                    "429 while fetching HTML %s | retry %d/%d | waiting %.1f seconds",
                    url,
                    attempt,
                    MAX_HTML_RETRIES,
                    wait_time
                )
                time.sleep(wait_time)
                continue

            logging.warning("Failed to fetch %s (%s)", url, exc)
            return None

        except requests.RequestException as exc:
            wait_time = HTML_BACKOFF_BASE_SECONDS * attempt
            logging.warning(
                "Transient fetch error for %s (%s) | retry %d/%d | waiting %.1f seconds",
                url,
                exc,
                attempt,
                MAX_HTML_RETRIES,
                wait_time
            )
            time.sleep(wait_time)
            continue

        except Exception as exc:
            logging.warning("Failed to fetch %s (%s)", url, exc)
            return None

    logging.warning("Exceeded retry limit for HTML page: %s", url)
    return None


def normalize_standard_ebooks_download_url(url: str) -> str:
    if "?" in url:
        return url
    return url + "?source=download"


def inspect_downloaded_file(epub_path: Path) -> None:
    try:
        with open(epub_path, "rb") as f:
            head = f.read(200)

        if not head.startswith(b"PK"):
            logging.warning("File does not start with ZIP signature: %s", epub_path.name)
            logging.warning("First bytes: %r", head[:80])
    except Exception as exc:
        logging.warning("Could not inspect file %s (%s)", epub_path, exc)


def get_total_txt_size_bytes(directory: Path) -> int:
    total = 0
    for path in directory.glob("*.txt"):
        if path.is_file():
            total += path.stat().st_size
    return total


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


def is_ebook_page_path(path: str) -> bool:
    if not path.startswith("/ebooks/"):
        return False

    normalized = path.rstrip("/")

    if normalized == "/ebooks":
        return False

    if "/downloads" in normalized:
        return False

    parts = [p for p in normalized.split("/") if p]
    return len(parts) >= 3


# ============================================================
# Listing page crawling
# ============================================================

def collect_ebook_links_from_listing(listing_html: str, current_url: str) -> set[str]:
    soup = BeautifulSoup(listing_html, "html.parser")
    ebook_links: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(current_url, href)
        parsed = urlparse(full)

        if parsed.netloc and parsed.netloc != urlparse(BASE_URL).netloc:
            continue

        if is_ebook_page_path(parsed.path):
            ebook_links.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/"))

    return ebook_links


def crawl_listing_pages(start_url: str) -> list[str]:
    found_books: set[str] = set()
    page_num = 1
    consecutive_empty_pages = 0

    while True:
        current = start_url if page_num == 1 else f"{start_url}?page={page_num}"

        logging.info("Scanning listing page: %s", current)

        html_text = fetch_html(current)
        if not html_text:
            logging.warning("Failed to fetch listing page %s", current)
            consecutive_empty_pages += 1

            if consecutive_empty_pages >= MAX_CONSECUTIVE_EMPTY_PAGES:
                logging.info(
                    "Stopping crawl after %d consecutive failed/empty pages.",
                    MAX_CONSECUTIVE_EMPTY_PAGES
                )
                break

            page_num += 1
            polite_sleep()
            continue

        new_books = collect_ebook_links_from_listing(html_text, current)
        before_count = len(found_books)
        found_books.update(new_books)
        added_count = len(found_books) - before_count

        logging.info(
            "Found %d books on page %d | Added %d new | Total queued so far: %d",
            len(new_books),
            page_num,
            added_count,
            len(found_books)
        )

        if added_count == 0:
            consecutive_empty_pages += 1
        else:
            consecutive_empty_pages = 0

        if consecutive_empty_pages >= MAX_CONSECUTIVE_EMPTY_PAGES:
            logging.info(
                "No new books found for %d consecutive pages. Stopping crawl.",
                MAX_CONSECUTIVE_EMPTY_PAGES
            )
            break

        page_num += 1
        polite_sleep()

    books = sorted(found_books)
    logging.info("Total ebook pages queued: %d", len(books))
    return books


# ============================================================
# Book page parsing
# ============================================================

def extract_title_from_page(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)

    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    if soup.title and soup.title.text.strip():
        title = soup.title.text.strip()
        title = re.sub(r"\s*-\s*Standard Ebooks.*$", "", title, flags=re.I)
        return title

    return "untitled"


def choose_epub_download_link(book_page_url: str) -> tuple[Optional[str], str]:
    page_html = fetch_html(book_page_url)
    if not page_html:
        return None, "untitled"

    soup = BeautifulSoup(page_html, "html.parser")
    title = extract_title_from_page(soup)

    best_url = None
    fallback_plain_epub = None
    fallback_any_epub = None

    for a in soup.find_all("a", href=True):
        href = urljoin(book_page_url, a["href"])
        text = " ".join(a.get_text(" ", strip=True).lower().split())
        href_lower = href.lower()

        is_epub = href_lower.endswith(".epub") or ".epub?" in href_lower or "epub" in text
        if not is_epub:
            continue

        if "compatible epub" in text:
            best_url = href
            break

        if "advanced epub" not in text and fallback_plain_epub is None:
            fallback_plain_epub = href

        if fallback_any_epub is None:
            fallback_any_epub = href

    chosen = best_url or fallback_plain_epub or fallback_any_epub
    if chosen:
        chosen = normalize_standard_ebooks_download_url(chosen)

    return chosen, title


# ============================================================
# Text normalization and EPUB extraction
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
# Download handling with 429 retry/backoff
# ============================================================

def download_epub(url: str, dest: Path) -> tuple[bool, bool]:
    """
    Returns:
        (success, hit_rate_limit)
    """
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with session.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True) as response:
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = int(retry_after)
                    else:
                        wait_time = BACKOFF_BASE_SECONDS * attempt

                    logging.warning(
                        "429 Too Many Requests for %s | retry %d/%d | waiting %.1f seconds",
                        url,
                        attempt,
                        MAX_DOWNLOAD_RETRIES,
                        wait_time
                    )
                    time.sleep(wait_time)
                    continue

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
# Book processing
# ============================================================

def process_book(book_page_url: str) -> tuple[bool, bool]:
    """
    Returns:
        (success, hit_rate_limit)
    """
    logging.info("Book page: %s", book_page_url)

    epub_url, title = choose_epub_download_link(book_page_url)
    safe_title = slugify_filename(title)

    if not epub_url:
        logging.warning("No EPUB download link found for: %s", book_page_url)
        return False, False

    logging.info("Selected EPUB link: %s", epub_url)

    epub_path = EPUB_DIR / f"{safe_title}.epub"
    clean_path = CLEAN_DIR / f"{safe_title}.txt"

    if clean_path.exists() and not OVERWRITE_EXISTING:
        append_to_downloaded_manifest(book_page_url)
        logging.info("TXT already exists, skipping: %s", safe_title)
        return True, False

    if not epub_path.exists() or OVERWRITE_EXISTING:
        ok, hit_rate_limit = download_epub(epub_url, epub_path)
        if not ok:
            return False, hit_rate_limit

        inspect_downloaded_file(epub_path)
        polite_sleep()

    try:
        text_clean = epub_to_text(epub_path)
    except Exception as exc:
        logging.warning("Failed to convert EPUB to text for %s (%s)", epub_path.name, exc)
        return False, False

    if len(text_clean) < MIN_TEXT_CHARS:
        logging.warning("Extracted text too short for %s", safe_title)
        return False, False

    save_text_file(text_clean, clean_path)
    append_to_downloaded_manifest(book_page_url)
    logging.info("Saved TXT: %s", clean_path)

    if not SAVE_EPUB:
        try:
            epub_path.unlink(missing_ok=True)
        except Exception:
            pass

    return True, False


# ============================================================
# Main
# ============================================================

def main() -> None:
    ensure_dirs()
    setup_logging()

    logging.info("=" * 60)
    logging.info("NEW RUN STARTED")
    logging.info("=" * 60)

    current_total = get_total_txt_size_bytes(CLEAN_DIR)
    logging.info("Current TXT size: %.2f MB", current_total / (1024 * 1024))
    logging.info("Target TXT size: %.2f MB", TARGET_TOTAL_TXT_MB)

    if current_total >= TARGET_TOTAL_TXT_BYTES:
        logging.info("Target already reached. TXT files saved in: %s", CLEAN_DIR.resolve())
        return

    logging.info("Starting crawl from %s", START_URL)
    book_pages = crawl_listing_pages(START_URL)

    downloaded_books = load_downloaded_manifest()
    before_filter_count = len(book_pages)
    book_pages = [url for url in book_pages if normalize_book_url(url) not in downloaded_books]

    logging.info(
        "Filtered already-downloaded books: %d skipped | %d remaining",
        before_filter_count - len(book_pages),
        len(book_pages)
    )

    success = 0
    failed = 0
    consecutive_429s = 0

    for idx, book_page_url in enumerate(book_pages, start=1):
        current_total = get_total_txt_size_bytes(CLEAN_DIR)

        if current_total >= TARGET_TOTAL_TXT_BYTES:
            logging.info("Reached target total TXT size: %.2f MB", current_total / (1024 * 1024))
            break

        if consecutive_429s >= MAX_CONSECUTIVE_429S:
            logging.warning(
                "Stopping early after %d consecutive rate-limit responses. Re-run later to continue.",
                consecutive_429s
            )
            break

        logging.info(
            "Processing %d/%d | Current total: %.2f MB / %.2f MB",
            idx,
            len(book_pages),
            current_total / (1024 * 1024),
            TARGET_TOTAL_TXT_MB
        )

        try:
            ok, hit_rate_limit = process_book(book_page_url)

            if ok:
                success += 1
                consecutive_429s = 0
            else:
                failed += 1
                if hit_rate_limit:
                    consecutive_429s += 1
                else:
                    consecutive_429s = 0

        finally:
            polite_sleep()

    final_total = get_total_txt_size_bytes(CLEAN_DIR)

    logging.info("FINAL REPORT")
    logging.info("Total success: %d", success)
    logging.info("Total failed: %d", failed)
    logging.info("Final size: %.2f MB", final_total / (1024 * 1024))
    logging.info("TXT files saved in: %s", CLEAN_DIR.resolve())
    logging.info("Done.")


if __name__ == "__main__":
    main()

