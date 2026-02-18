"""
scraper.py — Récupération des URLs d'articles de notes + fetch HTML.
Cache local dans cache/ pour éviter de re-scraper inutilement.
"""

import os
import re
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

BASE_URL = "https://lejournaldureal.fr"
SEARCH_URL = f"{BASE_URL}/search?q=note&page={{page}}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Début de la saison 2025-2026 : août 2025
SEASON_START = datetime(2025, 8, 1)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.html"


def _load_cache(url: str) -> str | None:
    path = _cache_path(url)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _save_cache(url: str, html: str) -> None:
    _cache_path(url).write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP fetch with retry
# ---------------------------------------------------------------------------

def fetch(url: str, use_cache: bool = True, retries: int = 3, delay: float = 1.5) -> str | None:
    """Télécharge une URL avec cache local et retry."""
    if use_cache:
        cached = _load_cache(url)
        if cached is not None:
            logger.debug("Cache hit: %s", url)
            return cached

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                html = resp.text
                if use_cache:
                    _save_cache(url, html)
                time.sleep(delay)
                return html
            elif resp.status_code == 404:
                logger.warning("404 Not Found: %s", url)
                return None
            else:
                logger.warning("HTTP %s for %s (attempt %d/%d)", resp.status_code, url, attempt, retries)
        except requests.RequestException as exc:
            logger.warning("Request error for %s (attempt %d/%d): %s", url, attempt, retries, exc)

        if attempt < retries:
            time.sleep(delay * attempt)

    logger.error("Failed to fetch %s after %d attempts", url, retries)
    return None


# ---------------------------------------------------------------------------
# Article URL discovery
# ---------------------------------------------------------------------------

# Slug must contain "note" (catches: notes-du-match, les-notes, note-du-match, etc.)
_SLUG_RE = re.compile(r'href="(/(\d{4})/(\d{2})/(\d{2})/([^"]*note[^"]*?))"', re.IGNORECASE)


def _parse_article_date(year: str, month: str, day: str) -> datetime | None:
    try:
        return datetime(int(year), int(month), int(day))
    except ValueError:
        return None


def discover_article_urls(max_pages: int = 20, use_cache: bool = True, refresh: bool = False) -> list[str]:
    """
    Parcourt les pages de recherche et retourne toutes les URLs d'articles
    de notes depuis le début de la saison 2025-2026.
    """
    if refresh:
        use_cache = False

    found: dict[str, datetime] = {}  # url -> date
    stop = False

    for page in range(1, max_pages + 1):
        url = SEARCH_URL.format(page=page)
        logger.info("Scanning search page %d: %s", page, url)

        html = fetch(url, use_cache=use_cache)
        if html is None:
            logger.warning("Empty result for search page %d, stopping.", page)
            break

        matches = _SLUG_RE.findall(html)
        if not matches:
            logger.info("No articles on page %d, stopping.", page)
            break

        page_has_recent = False

        for path, year, month, day, slug in matches:
            article_date = _parse_article_date(year, month, day)
            if article_date is None:
                continue

            full_url = BASE_URL + path

            if article_date >= SEASON_START:
                page_has_recent = True
                if full_url not in found:
                    found[full_url] = article_date
                    logger.info("Found article: %s (%s)", slug, article_date.date())
            # Si on tombe sur des articles avant la saison mais qu'il y en a
            # aussi des récents sur la même page, on continue quand même.

        # Si AUCUN article récent sur cette page => on a dépassé la saison
        if not page_has_recent and page > 1:
            logger.info("No recent articles on page %d, stopping search.", page)
            stop = True

        if stop:
            break

        time.sleep(0.5)

    # Trier par date décroissante
    sorted_urls = sorted(found.keys(), key=lambda u: found[u], reverse=True)
    logger.info("Total articles discovered: %d", len(sorted_urls))
    return sorted_urls


# ---------------------------------------------------------------------------
# Bulk fetch
# ---------------------------------------------------------------------------

def fetch_all_articles(urls: list[str], use_cache: bool = True) -> dict[str, str]:
    """
    Télécharge tous les articles et retourne un dict url -> html.
    """
    results: dict[str, str] = {}
    total = len(urls)

    for i, url in enumerate(urls, 1):
        logger.info("Fetching article %d/%d: %s", i, total, url)
        html = fetch(url, use_cache=use_cache)
        if html:
            results[url] = html
        else:
            logger.warning("Skipping (no content): %s", url)

    return results


# ---------------------------------------------------------------------------
# Utility: extract date from URL
# ---------------------------------------------------------------------------

_DATE_IN_URL_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def extract_date_from_url(url: str) -> str | None:
    m = _DATE_IN_URL_RE.search(url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None
