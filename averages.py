"""
averages.py — Calcul des moyennes de notes par joueur et par compétition.
"""

import json
import statistics
import logging
from collections import defaultdict
from pathlib import Path

from notes_parser import ArticleData, PlayerRating

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

DATA_FILE = OUTPUT_DIR / "data.json"
STATS_FILE = OUTPUT_DIR / "stats.json"


# ---------------------------------------------------------------------------
# Serialisation / désérialisation
# ---------------------------------------------------------------------------

def save_articles(articles: list[ArticleData]) -> None:
    """Sauvegarde la liste d'articles en JSON."""
    data = []
    for a in articles:
        data.append({
            "url": a.url,
            "title": a.title,
            "date": a.date,
            "competition": a.competition,
            "opponent": a.opponent,
            "players": [{"name": p.name, "note": p.note} for p in a.players],
        })
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %d articles to %s", len(articles), DATA_FILE)


def load_articles() -> list[ArticleData]:
    """Charge les articles depuis le JSON."""
    if not DATA_FILE.exists():
        return []
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    articles = []
    for item in raw:
        players = [PlayerRating(name=p["name"], note=p["note"]) for p in item["players"]]
        articles.append(ArticleData(
            url=item["url"],
            title=item["title"],
            date=item["date"],
            competition=item["competition"],
            opponent=item["opponent"],
            players=players,
        ))
    return articles


# ---------------------------------------------------------------------------
# Calcul des statistiques
# ---------------------------------------------------------------------------

def compute_stats(
    articles: list[ArticleData],
    competition_filter: str | None = None,
    player_filter: str | None = None,
) -> list[dict]:
    """
    Calcule les statistiques par joueur.

    Args:
        articles: Liste d'articles parsés.
        competition_filter: Si fourni, ne garde que cette compétition.
        player_filter: Si fourni, ne garde que ce joueur.

    Returns:
        Liste de dicts avec les stats de chaque joueur, triée par moyenne décroissante.
    """
    # Filtrage
    filtered = articles
    if competition_filter:
        filtered = [a for a in filtered if a.competition == competition_filter]

    # Agrégation: player -> competition -> list[notes]
    player_matches: dict[str, list[dict]] = defaultdict(list)

    for article in filtered:
        for player in article.players:
            if player_filter and player.name.lower() != player_filter.lower():
                continue
            player_matches[player.name].append({
                "date": article.date,
                "opponent": article.opponent,
                "competition": article.competition,
                "note": player.note,
                "url": article.url,
                "title": article.title,
            })

    results = []
    for player_name, matches in player_matches.items():
        rated = [m["note"] for m in matches if m["note"] is not None]
        nb_notes = len(rated)
        nb_non_notes = len(matches) - nb_notes

        moyenne_globale = round(statistics.mean(rated), 2) if rated else 0.0
        ecart_type = round(statistics.stdev(rated), 2) if len(rated) > 1 else 0.0

        # Ventilation par compétition
        par_competition: dict[str, dict] = {}
        comp_groups: dict[str, list[int | None]] = defaultdict(list)
        for m in matches:
            comp_groups[m["competition"]].append(m["note"])

        for comp, notes in comp_groups.items():
            comp_rated = [n for n in notes if n is not None]
            comp_non_notes = sum(1 for n in notes if n is None)
            par_competition[comp] = {
                "moyenne": round(statistics.mean(comp_rated), 2) if comp_rated else 0.0,
                "nb_matchs": len(comp_rated),
                "nb_non_notes": comp_non_notes,
                "notes": comp_rated,
            }

        # Détail matchs trié par date
        detail_matchs = sorted(matches, key=lambda m: m["date"])

        results.append({
            "player_name": player_name,
            "moyenne_globale": moyenne_globale,
            "nb_matchs": nb_notes,
            "nb_matchs_non_notes": nb_non_notes,
            "nb_matchs_total": len(matches),
            "ecart_type": ecart_type,
            "note_max": max(rated) if rated else 0,
            "note_min": min(rated) if rated else 0,
            "par_competition": par_competition,
            "detail_matchs": detail_matchs,
        })

    # Tri par moyenne décroissante, puis nb matchs décroissant
    results.sort(key=lambda x: (-x["moyenne_globale"], -x["nb_matchs"]))
    return results


def save_stats(stats: list[dict]) -> None:
    """Sauvegarde les stats en JSON."""
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved stats for %d players to %s", len(stats), STATS_FILE)


def load_stats() -> list[dict]:
    """Charge les stats depuis le JSON."""
    if not STATS_FILE.exists():
        return []
    return json.loads(STATS_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Affichage console
# ---------------------------------------------------------------------------

def print_stats_table(stats: list[dict], competition_filter: str | None = None) -> None:
    """Affiche le tableau des stats dans le terminal (sans dépendances externes)."""
    try:
        from tabulate import tabulate
        _print_with_tabulate(stats, competition_filter)
    except ImportError:
        _print_plain(stats, competition_filter)


def _print_with_tabulate(stats: list[dict], competition_filter: str | None) -> None:
    from tabulate import tabulate

    # Collecte toutes les compétitions présentes
    all_comps: set[str] = set()
    for s in stats:
        all_comps.update(s["par_competition"].keys())
    comps_sorted = sorted(all_comps)

    headers = ["Joueur", "Moy. glob.", "Notés", "Non notés", "Total", "Min", "Max", "σ"] + comps_sorted
    rows = []
    for s in stats:
        row = [
            s["player_name"],
            f"{s['moyenne_globale']:.2f}",
            s["nb_matchs"],
            s.get("nb_matchs_non_notes", 0),
            s.get("nb_matchs_total", s["nb_matchs"]),
            s["note_min"],
            s["note_max"],
            f"{s['ecart_type']:.2f}",
        ]
        for comp in comps_sorted:
            if comp in s["par_competition"]:
                cd = s["par_competition"][comp]
                nn = cd.get("nb_non_notes", 0)
                suffix = f" +{nn}nn" if nn > 0 else ""
                row.append(f"{cd['moyenne']:.1f} ({cd['nb_matchs']}{suffix})")
            else:
                row.append("-")
        rows.append(row)

    title = f"=== Stats saison 2025-2026"
    if competition_filter:
        title += f" — {competition_filter}"
    title += " ==="
    print(f"\n{title}")
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    print(f"\nTotal : {len(stats)} joueurs\n")


def _print_plain(stats: list[dict], competition_filter: str | None) -> None:
    title = "=== Stats saison 2025-2026"
    if competition_filter:
        title += f" — {competition_filter}"
    title += " ==="
    print(f"\n{title}")
    print(f"{'Joueur':<35} {'Moy':>6} {'Notés':>6} {'Non not.':>8} {'Total':>6} {'Min':>4} {'Max':>4}")
    print("-" * 72)
    for s in stats:
        print(
            f"{s['player_name']:<35} "
            f"{s['moyenne_globale']:>6.2f} "
            f"{s['nb_matchs']:>6} "
            f"{s.get('nb_matchs_non_notes', 0):>8} "
            f"{s.get('nb_matchs_total', s['nb_matchs']):>6} "
            f"{s['note_min']:>4} "
            f"{s['note_max']:>4}"
        )
    print(f"\nTotal : {len(stats)} joueurs\n")


def print_player_detail(player_stats: dict) -> None:
    """Affiche le détail d'un joueur."""
    print(f"\n=== {player_stats['player_name']} ===")
    print(f"Moyenne globale : {player_stats['moyenne_globale']:.2f}/10")
    print(f"Matchs notés   : {player_stats['nb_matchs']}")
    print(f"Non notés      : {player_stats.get('nb_matchs_non_notes', 0)}")
    print(f"Total appars.  : {player_stats.get('nb_matchs_total', player_stats['nb_matchs'])}")
    print(f"Note min / max : {player_stats['note_min']} / {player_stats['note_max']}")
    print(f"Écart-type     : {player_stats['ecart_type']:.2f}")

    if player_stats["par_competition"]:
        print("\nPar compétition :")
        for comp, data in sorted(player_stats["par_competition"].items()):
            print(f"  {comp:<30} {data['moyenne']:.2f}/10  ({data['nb_matchs']} matchs)")

    if player_stats["detail_matchs"]:
        print("\nDétail matchs :")
        print(f"  {'Date':<12} {'Adversaire':<30} {'Compétition':<25} {'Note':>4}")
        print("  " + "-" * 74)
        for m in player_stats["detail_matchs"]:
            print(
                f"  {m['date']:<12} {m['opponent']:<30} "
                f"{m['competition']:<25} {m['note']:>4}/10"
            )
    print()
