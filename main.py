"""
main.py — Point d'entrée CLI du scraper de notes Real Madrid.

Usage:
    python main.py                              # Charge le cache + affiche stats
    python main.py --refresh                    # Scrape incrémental (nouveaux articles seulement)
    python main.py --hard-refresh               # Re-scrape intégral (ignore tout le cache)
    python main.py --competition Liga           # Filtre par compétition
    python main.py --joueur "Vinicius Jr"       # Stats d'un joueur
    python main.py --list-competitions          # Liste les compétitions trouvées
    python main.py --list-joueurs               # Liste tous les joueurs
"""

import argparse
import logging
import sys
import io
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from scraper import discover_article_urls, fetch_all_articles, extract_date_from_url
from notes_parser import parse_article
from fotmob_scraper import scrape_fotmob
from averages import (
    compute_stats,
    load_articles,
    load_stats,
    print_stats_table,
    print_player_detail,
    save_articles,
    save_stats,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def _parse_and_log(html_map: dict) -> tuple[list, int]:
    """Parse un dict url->html, retourne (articles ArticleData, nb ignorés)."""
    articles = []
    skipped = 0
    for url, html in html_map.items():
        date = extract_date_from_url(url) or "0000-00-00"
        article = parse_article(url, html, date)
        if article:
            articles.append(article)
            logger.info(
                "OK  [%s] %s — %d joueurs notés",
                article.date, article.competition, len(article.players),
            )
        else:
            skipped += 1
            logger.debug("Skipped (no ratings): %s", url)
    return articles, skipped


def run_scrape(hard: bool = False) -> list:
    """Scraping intégral : re-télécharge tout depuis le site (--hard-refresh)."""
    logger.info("=== Découverte des URLs ===")
    urls = discover_article_urls(max_pages=20, use_cache=False, refresh=True)
    logger.info("URLs trouvées : %d", len(urls))

    if not urls:
        logger.warning("Aucune URL trouvée. Vérifiez la connexion ou les filtres de date.")
        return []

    logger.info("=== Téléchargement des articles ===")
    html_map = fetch_all_articles(urls, use_cache=False)
    logger.info("Articles téléchargés : %d", len(html_map))

    logger.info("=== Parsing des notes ===")
    articles, skipped = _parse_and_log(html_map)
    logger.info("Articles avec notes : %d | Ignorés : %d", len(articles), skipped)

    save_articles(articles)

    try:
        scrape_fotmob(refresh=True)
    except Exception as e:
        logger.error("FotMob scraping failed: %s", e)

    articles_dicts = load_articles()
    save_stats(compute_stats(articles_dicts))
    return articles_dicts


def run_scrape_incremental() -> list:
    """Scraping incrémental : découvre les nouvelles URLs et ne traite que celles-ci."""
    logger.info("=== Découverte des URLs (incrémental) ===")
    urls = discover_article_urls(max_pages=20, use_cache=False, refresh=False)
    logger.info("URLs trouvées : %d", len(urls))

    existing_articles = load_articles()
    existing_urls = {a["url"] for a in existing_articles}

    new_urls = [u for u in urls if u not in existing_urls]
    logger.info("Nouveaux articles : %d (déjà connus : %d)", len(new_urls), len(existing_urls))

    if new_urls:
        logger.info("=== Téléchargement des nouveaux articles ===")
        html_map = fetch_all_articles(new_urls, use_cache=True)

        logger.info("=== Parsing des notes ===")
        new_articles, skipped = _parse_and_log(html_map)
        logger.info("Nouveaux articles avec notes : %d | Ignorés : %d", len(new_articles), skipped)

        # Merge : existing dicts + new ArticleData objects (save_articles handles both)
        save_articles(existing_articles + new_articles)
    else:
        logger.info("Aucun nouvel article — mise à jour FotMob + stats uniquement.")

    try:
        scrape_fotmob(refresh=False)
    except Exception as e:
        logger.error("FotMob scraping failed: %s", e)

    articles_dicts = load_articles()
    save_stats(compute_stats(articles_dicts))
    return articles_dicts


def load_or_scrape(refresh: bool = False, hard_refresh: bool = False) -> list:
    """Charge les données existantes ou lance un scraping selon le mode."""
    if hard_refresh:
        return run_scrape(hard=True)
    if refresh:
        return run_scrape_incremental()

    articles = load_articles()
    if articles:
        logger.info("Données chargées depuis le cache (%d articles)", len(articles))
        return articles
    logger.info("Aucune donnée en cache, lancement du scraping incrémental...")
    return run_scrape_incremental()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scraper de notes Real Madrid — lejournaldureal.fr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--refresh",
        action="store_true",
        help="Scraping incrémental : découvre les nouveaux articles et les ajoute aux données existantes.",
    )
    p.add_argument(
        "--hard-refresh",
        action="store_true",
        dest="hard_refresh",
        help="Re-scrape intégral : ignore tout le cache et retélécharge tous les articles.",
    )
    p.add_argument(
        "--competition",
        metavar="NOM",
        help="Filtre les stats pour une compétition (ex: Liga, 'Ligue des Champions').",
    )
    p.add_argument(
        "--joueur",
        metavar="NOM",
        help="Affiche le détail d'un joueur (ex: 'Vinicius Jr').",
    )
    p.add_argument(
        "--list-competitions",
        action="store_true",
        help="Liste toutes les compétitions trouvées dans les données.",
    )
    p.add_argument(
        "--list-joueurs",
        action="store_true",
        help="Liste tous les joueurs trouvés dans les données.",
    )
    p.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help="Affiche seulement les N premiers joueurs du tableau.",
    )
    p.add_argument(
        "--min-matchs",
        type=int,
        default=1,
        metavar="N",
        help="Filtre les joueurs avec au moins N matchs (défaut: 1).",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Affichage détaillé (DEBUG).",
    )
    p.add_argument(
        "--scrape-only",
        action="store_true",
        help="Lance le scraping sans afficher les stats.",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Chargement / scraping
    articles = load_or_scrape(refresh=args.refresh, hard_refresh=args.hard_refresh)

    if not articles:
        print("Aucun article trouvé. Lancez avec --refresh pour scraper les données.")
        return 1

    if args.scrape_only:
        print(f"\nScraping terminé : {len(articles)} articles récupérés.")
        return 0

    # Liste des compétitions
    if args.list_competitions:
        comps = sorted({a["competition"] for a in articles})
        print("\nCompétitions trouvées :")
        for comp in comps:
            count = sum(1 for a in articles if a["competition"] == comp)
            print(f"  {comp:<35} ({count} matchs)")
        return 0

    # Liste des joueurs
    if args.list_joueurs:
        stats = compute_stats(articles)
        print(f"\nJoueurs trouvés ({len(stats)}) :")
        for s in stats:
            print(f"  {s['player_name']:<35} {s['nb_matchs']:>3} matchs  {s['moyenne_globale']:.2f}/10")
        return 0

    # Calcul des stats
    stats = compute_stats(
        articles,
        competition_filter=args.competition,
        player_filter=args.joueur,
    )

    # Filtre min-matchs
    if args.min_matchs > 1:
        stats = [s for s in stats if s["nb_matchs"] >= args.min_matchs]

    # Détail d'un joueur
    if args.joueur:
        if not stats:
            print(f"Joueur '{args.joueur}' non trouvé dans les données.")
            return 1
        for s in stats:
            print_player_detail(s)
        return 0

    # Tableau général
    if args.top:
        stats = stats[:args.top]

    print_stats_table(stats, competition_filter=args.competition)

    # Sauvegarde des stats filtrées si demandé
    save_stats(compute_stats(articles))  # toujours sauvegarder les stats complètes

    return 0


if __name__ == "__main__":
    sys.exit(main())
