"""
fotmob_scraper.py — Récupération des données de match Real Madrid depuis FotMob.

Fetche les notes FotMob, buts, passes décisives, cartons et photos des joueurs.
Les résultats sont sauvegardés dans output/fotmob_data.json.
"""

import json
import logging
import re
import time
from pathlib import Path

import requests

from utils import normalize_name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TEAM_ID = 8633  # Real Madrid
TEAM_API_URL = f"https://www.fotmob.com/api/teams?id={TEAM_ID}"
BASE_URL = "https://www.fotmob.com"
SEASON_START = "2025-08-01"

CACHE_DIR = Path("cache/fotmob")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = Path("output/fotmob_data.json")

IMAGE_CDN = "https://images.fotmob.com/image_resources/playerimages/{player_id}.png"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.fotmob.com/",
}

_NEXT_DATA_RE = re.compile(
    r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_html(match_id: int) -> Path:
    return CACHE_DIR / f"{match_id}.html"


def _cache_fixtures() -> Path:
    return CACHE_DIR / "fixtures.json"


def _fetch(url: str, retries: int = 3, delay: float = 2.0) -> str | None:
    """HTTP GET avec retry. Retourne le texte ou None en cas d'échec."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.text
            logger.warning("HTTP %d pour %s", resp.status_code, url)
        except requests.RequestException as e:
            logger.warning("Tentative %d/%d — %s : %s", attempt + 1, retries, url, e)
        if attempt < retries - 1:
            time.sleep(delay)
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _get_fixtures(refresh: bool = False) -> list[dict]:
    """
    Retourne la liste des matchs Real Madrid terminés depuis SEASON_START.
    Chaque entrée : {match_id, page_url, date, home_id, away_id}
    """
    cache_path = _cache_fixtures()

    if not refresh and cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        text = _fetch(TEAM_API_URL)
        if not text:
            logger.error("Impossible de récupérer les fixtures FotMob.")
            return []
        raw = json.loads(text)
        cache_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        logger.info("Fixtures FotMob récupérées et mises en cache.")

    try:
        fixtures = raw["fixtures"]["allFixtures"]["fixtures"]
    except (KeyError, TypeError):
        logger.error("Structure fixtures FotMob inattendue.")
        return []

    results = []
    for f in fixtures:
        status = f.get("status") or {}
        if not status.get("finished"):
            continue
        utc = status.get("utcTime") or ""
        date = utc[:10] if utc else "0000-00-00"
        if date < SEASON_START:
            continue
        match_id = f.get("id")
        page_url = f.get("pageUrl", "")
        if not match_id or not page_url:
            continue
        results.append({
            "match_id": match_id,
            "page_url": page_url,
            "date": date,
            "home_id": (f.get("home") or {}).get("id"),
            "away_id": (f.get("away") or {}).get("id"),
        })

    logger.info("%d matchs terminés trouvés depuis %s.", len(results), SEASON_START)
    return results


# ---------------------------------------------------------------------------
# Parsing d'une page de match
# ---------------------------------------------------------------------------

def _extract_next_data(html: str) -> dict | None:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.warning("Erreur parsing __NEXT_DATA__ : %s", e)
        return None


def _count_events(events: list, event_type: str) -> int:
    """Compte les événements d'un type donné (goal, assist, yellowCard, redCard)."""
    return sum(1 for ev in (events or []) if ev.get("type") == event_type)


def _parse_player(p: dict) -> dict | None:
    """
    Extrait les données d'un joueur depuis l'entrée FotMob lineup.
    Retourne None si le nom est vide ou _COACH_.
    """
    raw_name = p.get("name") or ""
    if not raw_name:
        return None

    name = normalize_name(raw_name)
    if not name or name == "_COACH_":
        return None

    player_id = p.get("id")
    performance = p.get("performance") or {}

    # Note FotMob : float > 0, sinon None (0 = non noté)
    rating_raw = performance.get("rating")
    try:
        rating = float(rating_raw) if rating_raw is not None else None
        if rating == 0.0:
            rating = None
    except (TypeError, ValueError):
        rating = None

    events = performance.get("events") or []
    goals = _count_events(events, "goal")
    assists = _count_events(events, "assist")
    yellow_cards = _count_events(events, "yellowCard")
    red_cards = _count_events(events, "redCard")

    return {
        "name": name,
        "player_id": player_id,
        "rating": rating,
        "goals": goals,
        "assists": assists,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "image_url": IMAGE_CDN.format(player_id=player_id) if player_id else None,
    }


def _parse_match_page(match_id: int, html: str, date: str) -> dict | None:
    """
    Parse le __NEXT_DATA__ d'une page de match FotMob.
    Retourne un dict match ou None si le parsing échoue.
    """
    data = _extract_next_data(html)
    if not data:
        return None

    try:
        pp = data["props"]["pageProps"]
        general = pp.get("general") or {}
        content = pp.get("content") or {}
        header = pp.get("header") or {}

        # Date depuis general (plus précise que la fixture API)
        utc = general.get("matchTimeUTCDate") or ""
        match_date = utc[:10] if utc else date

        # Compétition
        competition = general.get("leagueName") or None

        # Score
        status = header.get("status") or {}
        score = status.get("scoreStr")

        # Adversaire (équipe qui n'est pas Real Madrid)
        teams = header.get("teams") or []
        opponent = next(
            (t.get("name") for t in teams if t.get("id") != TEAM_ID),
            None,
        )

        # Lineup
        lineup = content.get("lineup") or {}
        home_team = lineup.get("homeTeam") or {}
        away_team = lineup.get("awayTeam") or {}

        rm_lineup = (
            home_team if home_team.get("id") == TEAM_ID
            else away_team if away_team.get("id") == TEAM_ID
            else None
        )
        if not rm_lineup:
            logger.warning("Real Madrid introuvable dans le lineup du match %d.", match_id)
            return None

        players = []
        for p in list(rm_lineup.get("starters") or []) + list(rm_lineup.get("subs") or []):
            parsed = _parse_player(p)
            if parsed:
                players.append(parsed)

        if not players:
            logger.warning("Aucun joueur trouvé pour le match %d.", match_id)
            return None

        return {
            "match_id": match_id,
            "date": match_date,
            "competition": competition,
            "opponent": opponent,
            "score": score,
            "players": players,
        }

    except Exception as e:
        logger.exception("Erreur parsing match %d : %s", match_id, e)
        return None


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def scrape_fotmob(refresh: bool = False) -> list[dict]:
    """
    Scrape les données FotMob pour tous les matchs Real Madrid depuis SEASON_START.

    - refresh=False : réutilise le cache HTML des pages de match
    - refresh=True  : re-fetch les fixtures ET les pages de match

    Sauvegarde les résultats dans output/fotmob_data.json et les retourne.
    """
    fixtures = _get_fixtures(refresh=refresh)
    if not fixtures:
        return []

    results = []
    for f in fixtures:
        match_id = f["match_id"]
        cache_path = _cache_html(match_id)

        # Charger depuis le cache ou fetcher
        if not refresh and cache_path.exists():
            html = cache_path.read_text(encoding="utf-8")
        else:
            url = f"{BASE_URL}{f['page_url']}"
            logger.info("Fetching FotMob match %d — %s", match_id, url)
            html = _fetch(url)
            if not html:
                logger.warning("Échec fetch match %d, ignoré.", match_id)
                continue
            cache_path.write_text(html, encoding="utf-8")
            time.sleep(1.5)

        match_data = _parse_match_page(match_id, html, f["date"])
        if match_data:
            results.append(match_data)
        else:
            logger.debug("Match %d ignoré (parsing vide).", match_id)

    results.sort(key=lambda x: x["date"], reverse=True)

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("FotMob : %d matchs sauvegardés dans %s.", len(results), OUTPUT_FILE)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    data = scrape_fotmob()
    print(f"Scraped {len(data)} matches from FotMob.")
