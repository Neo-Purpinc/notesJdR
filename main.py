"""
main.py — Point d'entrée CLI du scraper de notes Real Madrid.

Usage:
    python main.py                              # Scrape + stats globales
    python main.py --competition Liga           # Filtre par compétition
    python main.py --joueur "Vinicius Jr"       # Stats d'un joueur
    python main.py --refresh                    # Re-scrape (ignore le cache)
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

def run_scrape(refresh: bool = False) -> list:
    """Lance le scraping complet et retourne les articles parsés."""
    logger.info("=== Découverte des URLs ===")
    urls = discover_article_urls(max_pages=20, use_cache=not refresh, refresh=refresh)
    logger.info("URLs trouvées : %d", len(urls))

    if not urls:
        logger.warning("Aucune URL trouvée. Vérifiez la connexion ou les filtres de date.")
        return []

    logger.info("=== Téléchargement des articles ===")
    html_map = fetch_all_articles(urls, use_cache=not refresh)
    logger.info("Articles téléchargés : %d", len(html_map))

    logger.info("=== Parsing des notes ===")
    articles = []
    skipped = 0
    for url, html in html_map.items():
        date = extract_date_from_url(url) or "0000-00-00"
        article = parse_article(url, html, date)
        if article:
            articles.append(article)
            logger.info(
                "OK  [%s] %s — %d joueurs notés",
                article.date,
                article.competition,
                len(article.players),
            )
        else:
            skipped += 1
            logger.debug("Skipped (no ratings): %s", url)

    logger.info("Articles avec notes : %d | Ignorés : %d", len(articles), skipped)

    # Sauvegarde JDR
    save_articles(articles)

    # Scraping FotMob (sauvegarde lui-même dans output/fotmob_data.json)
    try:
        scrape_fotmob(refresh=refresh)
    except Exception as e:
        logger.error("FotMob scraping failed: %s", e)

    # Retourne des dicts (load_articles) pour compatibilité avec compute_stats()
    articles_dicts = load_articles()
    stats = compute_stats(articles_dicts)
    save_stats(stats)

    return articles_dicts


def load_or_scrape(refresh: bool = False) -> list:
    """Charge les données existantes ou lance un scraping si nécessaire."""
    if not refresh:
        articles = load_articles()
        if articles:
            logger.info("Données chargées depuis le cache (%d articles)", len(articles))
            return articles
        logger.info("Aucune donnée en cache, lancement du scraping...")

    return run_scrape(refresh=refresh)


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
        help="Ignore le cache et re-scrape tout depuis le site.",
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
    articles = load_or_scrape(refresh=args.refresh)

    if not articles:
        print("Aucun article trouvé. Lancez avec --refresh pour re-scraper.")
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
