#!/usr/bin/env python3
"""
build_standard_ebooks_catalog.py

Build a persistent catalog of Standard Ebooks book pages and EPUB download URLs.

What it does:
- Crawls https://standardebooks.org/ebooks using explicit page-number pagination
- Extracts book page URLs from listing pages
- Visits each book page and finds the preferred EPUB download URL
- Saves a persistent catalog to disk
- Supports resume using a crawl state file
- Logs to both terminal and file

Output files:
- standard_ebooks_output/catalog.jsonl
- standard_ebooks_output/catalog_urls.txt
- standard_ebooks_output/catalog_state.json
- standard_ebooks_output/catalog_build.log

Dependencies:
    pip install requests beautifulsoup4 lxml
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ============================================================
# Configuration
# ============================================================

BASE_URL = "https://standardebooks.org"
START_URL = "https://standardebooks.org/ebooks"

OUTPUT_DIR = Path("standard_ebooks_output")
CATALOG_JSONL = OUTPUT_DIR / "catalog.jsonl"
CATALOG_URLS = OUTPUT_DIR / "catalog_urls.txt"
CATALOG_STATE_FILE = OUTPUT_DIR / "catalog_state.json"
LOG_FILE = OUTPUT_DIR / "catalog_build.log"

REQUEST_TIMEOUT = 30
SLEEP_RANGE = (2.0, 4.0)

MAX_HTML_RETRIES = 5
HTML_BACKOFF_BASE_SECONDS = 15
MAX_CONSECUTIVE_EMPTY_PAGES = 3

USER_AGENT = (
    "Mozilla/5.0 (compatible; StandardEbooksCatalogBuilder/1.0; +research-use)"
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
# Filesystem helpers
# ============================================================

def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def polite_sleep() -> None:
    time.sleep(random.uniform(*SLEEP_RANGE))


# ============================================================
# State helpers
# ============================================================

def normalize_book_url(url: str) -> str:
    return url.rstrip("/")


def load_catalog_urls() -> set[str]:
    if not CATALOG_URLS.exists():
        return set()

    with open(CATALOG_URLS, "r", encoding="utf-8") as f:
        return {normalize_book_url(line.strip()) for line in f if line.strip()}


def append_catalog_entry(entry: dict) -> None:
    book_page_url = normalize_book_url(entry["book_page_url"])

    existing = load_catalog_urls()
    if book_page_url in existing:
        return

    with open(CATALOG_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    with open(CATALOG_URLS, "a", encoding="utf-8") as f:
        f.write(book_page_url + "\n")


def load_catalog_state() -> dict:
    if not CATALOG_STATE_FILE.exists():
        return {
            "next_page_to_scan": 1,
            "crawl_completed": False,
            "total_cataloged": 0,
            "last_updated": None,
        }

    try:
        with open(CATALOG_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "next_page_to_scan": int(data.get("next_page_to_scan", 1)),
            "crawl_completed": bool(data.get("crawl_completed", False)),
            "total_cataloged": int(data.get("total_cataloged", 0)),
            "last_updated": data.get("last_updated"),
        }
    except Exception as exc:
        logging.warning("Failed to load catalog state (%s). Starting from page 1.", exc)
        return {
            "next_page_to_scan": 1,
            "crawl_completed": False,
            "total_cataloged": 0,
            "last_updated": None,
        }


def save_catalog_state(next_page_to_scan: int, crawl_completed: bool, total_cataloged: int) -> None:
    data = {
        "next_page_to_scan": next_page_to_scan,
        "crawl_completed": crawl_completed,
        "total_cataloged": total_cataloged,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open(CATALOG_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ============================================================
# HTTP helpers
# ============================================================

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
                    "429 while fetching %s | retry %d/%d | waiting %.1f seconds",
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


# ============================================================
# Listing-page parsing
# ============================================================

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


# ============================================================
# Book-page parsing
# ============================================================

def normalize_standard_ebooks_download_url(url: str) -> str:
    if "?" in url:
        return url
    return url + "?source=download"


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
# Main crawl
# ============================================================

def main() -> None:
    ensure_dirs()
    setup_logging()

    logging.info("=" * 60)
    logging.info("NEW CATALOG BUILD RUN STARTED")
    logging.info("=" * 60)

    catalog_state = load_catalog_state()
    known_urls = load_catalog_urls()

    logging.info("Existing catalog size: %d", len(known_urls))
    logging.info(
        "Catalog state: next_page_to_scan=%d | crawl_completed=%s | total_cataloged=%d",
        catalog_state["next_page_to_scan"],
        catalog_state["crawl_completed"],
        catalog_state["total_cataloged"],
    )

    if catalog_state["crawl_completed"]:
        logging.info("Catalog is already marked complete. Nothing to do.")
        return

    page_num = max(1, catalog_state["next_page_to_scan"])
    consecutive_empty_pages = 0
    added_this_run = 0

    while True:
        current = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
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

        book_urls = sorted(collect_ebook_links_from_listing(html_text, current))
        page_added = 0

        for book_page_url in book_urls:
            normalized_url = normalize_book_url(book_page_url)

            if normalized_url in known_urls:
                continue

            epub_url, title = choose_epub_download_link(normalized_url)
            if not epub_url:
                logging.warning("Skipping book page with no EPUB URL: %s", normalized_url)
                polite_sleep()
                continue

            entry = {
                "book_page_url": normalized_url,
                "epub_url": epub_url,
                "title": title,
                "cataloged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            append_catalog_entry(entry)
            known_urls.add(normalized_url)
            page_added += 1
            added_this_run += 1

            logging.info("Cataloged: %s", title)
            polite_sleep()

        logging.info(
            "Found %d books on page %d | Added %d new | Total cataloged so far: %d",
            len(book_urls),
            page_num,
            page_added,
            len(known_urls)
        )

        save_catalog_state(
            next_page_to_scan=page_num + 1,
            crawl_completed=False,
            total_cataloged=len(known_urls)
        )

        if page_added == 0:
            consecutive_empty_pages += 1
        else:
            consecutive_empty_pages = 0

        if consecutive_empty_pages >= MAX_CONSECUTIVE_EMPTY_PAGES:
            logging.info(
                "No new books found for %d consecutive pages. Marking catalog complete.",
                MAX_CONSECUTIVE_EMPTY_PAGES
            )
            save_catalog_state(
                next_page_to_scan=page_num + 1,
                crawl_completed=True,
                total_cataloged=len(known_urls)
            )
            break

        page_num += 1
        polite_sleep()

    final_state = load_catalog_state()

    logging.info("FINAL REPORT")
    logging.info("Added this run: %d", added_this_run)
    logging.info("Final catalog size: %d", len(known_urls))
    logging.info("Next page to scan: %d", final_state["next_page_to_scan"])
    logging.info("Crawl completed: %s", final_state["crawl_completed"])
    logging.info("Catalog JSONL: %s", CATALOG_JSONL.resolve())
    logging.info("Catalog URL list: %s", CATALOG_URLS.resolve())
    logging.info("Done.")


if __name__ == "__main__":
    main()

