"""
averages.py — Calcul des moyennes de notes par joueur (JDR + FotMob fusionnés).
"""

import json
import statistics
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

DATA_FILE = OUTPUT_DIR / "data.json"
FOTMOB_FILE = OUTPUT_DIR / "fotmob_data.json"
STATS_FILE = OUTPUT_DIR / "stats.json"


# ---------------------------------------------------------------------------
# Sérialisation / désérialisation
# ---------------------------------------------------------------------------

def save_articles(articles: list) -> None:
    """Sauvegarde la liste d'articles en JSON. Accepte ArticleData objects ou dicts."""
    data = []
    for a in articles:
        if hasattr(a, "url"):  # ArticleData object
            data.append({
                "url": a.url,
                "title": a.title,
                "date": a.date,
                "competition": a.competition,
                "opponent": a.opponent,
                "players": [{"name": p.name, "note": p.note} for p in a.players],
            })
        else:  # dict
            data.append(a)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %d articles to %s", len(data), DATA_FILE)


def load_articles() -> list[dict]:
    """Charge les articles depuis le JSON. Retourne des dicts (pas des ArticleData)."""
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_fotmob_data() -> list[dict]:
    """Charge les matchs FotMob depuis le JSON."""
    if not FOTMOB_FILE.exists():
        return []
    return json.loads(FOTMOB_FILE.read_text(encoding="utf-8"))


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
# Index FotMob
# ---------------------------------------------------------------------------

def _build_fotmob_index(fotmob_matches: list[dict]) -> dict[tuple, dict]:
    """
    Construit un index (player_name, date) → données joueur FotMob.
    Permet la jointure avec les articles JDR.
    """
    index: dict[tuple, dict] = {}
    for match in fotmob_matches:
        date = match.get("date", "")
        competition = match.get("competition")
        opponent = match.get("opponent")
        for player in match.get("players", []):
            key = (player["name"], date)
            index[key] = {
                "rating": player.get("rating"),
                "goals": player.get("goals", 0),
                "assists": player.get("assists", 0),
                "yellow_cards": player.get("yellow_cards", 0),
                "red_cards": player.get("red_cards", 0),
                "image_url": player.get("image_url"),
                "player_id": player.get("player_id"),
                # Infos match (fallback si absent côté JDR)
                "competition": competition,
                "opponent": opponent,
            }
    return index


# ---------------------------------------------------------------------------
# Calcul des statistiques
# ---------------------------------------------------------------------------

def compute_stats(
    articles: list,
    competition_filter: str | None = None,
    player_filter: str | None = None,
    fotmob_matches: list[dict] | None = None,
) -> list[dict]:
    """
    Calcule les statistiques par joueur en fusionnant JDR et FotMob.

    Args:
        articles: Liste d'articles (dicts ou ArticleData objects).
        competition_filter: Si fourni, ne garde que cette compétition.
        player_filter: Si fourni, ne garde que ce joueur.
        fotmob_matches: Données FotMob pré-chargées. Si None, charge depuis le fichier.

    Returns:
        Liste de dicts stats par joueur, triée par moyenne_globale décroissante.
    """
    if fotmob_matches is None:
        fotmob_matches = load_fotmob_data()

    fotmob_index = _build_fotmob_index(fotmob_matches)

    # Suivi de l'image_url par joueur (on prend la première trouvée)
    player_images: dict[str, str] = {}

    # Agrégation JDR : player → liste de matchs avec toutes les données
    player_matches: dict[str, list[dict]] = defaultdict(list)

    for article in articles:
        # Support ArticleData objects ET dicts
        if hasattr(article, "date"):
            date = article.date
            competition = article.competition
            opponent = article.opponent
            url = article.url
            title = article.title
            players_list = article.players
        else:
            date = article["date"]
            competition = article.get("competition", "Liga")
            opponent = article.get("opponent", "?")
            url = article.get("url", "")
            title = article.get("title", "")
            players_list = article.get("players", [])

        if competition_filter and competition != competition_filter:
            continue

        for player in players_list:
            if hasattr(player, "name"):
                p_name = player.name
                jdr_note = player.note
            else:
                p_name = player["name"]
                jdr_note = player.get("note")

            if player_filter and p_name.lower() != player_filter.lower():
                continue

            # Recherche données FotMob pour ce joueur/date
            fm = fotmob_index.get((p_name, date)) or {}

            # Mise à jour image_url (première valeur non-None retenue)
            if fm.get("image_url") and p_name not in player_images:
                player_images[p_name] = fm["image_url"]

            # Calcul note combinée (moyenne JDR + FotMob disponibles)
            fm_note = fm.get("rating")
            available = []
            if jdr_note is not None:
                available.append(float(jdr_note))
            if fm_note is not None:
                available.append(float(fm_note))
            combined = round(sum(available) / len(available), 2) if available else None

            player_matches[p_name].append({
                "date": date,
                "opponent": opponent,
                "competition": competition,
                "note": combined,       # Note combinée (pour tri, radar, etc.)
                "jdr_note": jdr_note,   # Note JDR brute (int ou None)
                "fotmob_note": fm_note, # Note FotMob brute (float ou None)
                "goals": fm.get("goals", 0),
                "assists": fm.get("assists", 0),
                "yellow_cards": fm.get("yellow_cards", 0),
                "red_cards": fm.get("red_cards", 0),
                "url": url,
                "title": title,
            })

    results = []
    for player_name, matches in player_matches.items():
        rated = [m["note"] for m in matches if m["note"] is not None]
        jdr_rated = [m["jdr_note"] for m in matches if m["jdr_note"] is not None]
        fm_rated = [m["fotmob_note"] for m in matches if m["fotmob_note"] is not None]
        nb_notes = len(rated)
        nb_non_notes = len(matches) - nb_notes

        moyenne_globale = round(statistics.mean(rated), 2) if rated else 0.0
        moyenne_jdr = round(statistics.mean(jdr_rated), 2) if jdr_rated else 0.0
        moyenne_fotmob = round(statistics.mean(fm_rated), 2) if fm_rated else 0.0
        ecart_type = round(statistics.stdev(rated), 2) if len(rated) > 1 else 0.0

        # Ventilation par compétition (basée sur la note combinée)
        comp_groups: dict[str, list] = defaultdict(list)
        for m in matches:
            if m["note"] is not None:
                comp_groups[m["competition"]].append(m["note"])

        par_competition = {
            comp: {
                "moyenne": round(statistics.mean(notes), 2),
                "nb_matchs": len(notes),
                "nb_non_notes": sum(
                    1 for m in matches
                    if m["competition"] == comp and m["note"] is None
                ),
                "notes": notes,
            }
            for comp, notes in comp_groups.items()
        }

        # Stats cumulées FotMob
        total_goals = sum(m["goals"] for m in matches)
        total_assists = sum(m["assists"] for m in matches)
        total_yellow = sum(m["yellow_cards"] for m in matches)
        total_red = sum(m["red_cards"] for m in matches)

        detail_matchs = sorted(matches, key=lambda m: m["date"])

        results.append({
            "player_name": player_name,
            "image_url": player_images.get(player_name),
            "moyenne_globale": moyenne_globale,
            "moyenne_jdr": moyenne_jdr,
            "moyenne_fotmob": moyenne_fotmob,
            "nb_matchs": nb_notes,
            "nb_matchs_non_notes": nb_non_notes,
            "nb_matchs_total": len(matches),
            "ecart_type": ecart_type,
            "note_max": max(rated) if rated else 0,
            "note_min": min(rated) if rated else 0,
            "total_goals": total_goals,
            "total_assists": total_assists,
            "total_yellow_cards": total_yellow,
            "total_red_cards": total_red,
            "par_competition": par_competition,
            "detail_matchs": detail_matchs,
        })

    results.sort(key=lambda x: (-x["moyenne_globale"], -x["nb_matchs"]))
    return results


# ---------------------------------------------------------------------------
# Affichage console
# ---------------------------------------------------------------------------

def print_stats_table(stats: list[dict], competition_filter: str | None = None) -> None:
    """Affiche le tableau des stats dans le terminal."""
    try:
        from tabulate import tabulate
        _print_with_tabulate(stats, competition_filter)
    except ImportError:
        _print_plain(stats, competition_filter)


def _print_with_tabulate(stats: list[dict], competition_filter: str | None) -> None:
    from tabulate import tabulate

    all_comps: set[str] = set()
    for s in stats:
        all_comps.update(s["par_competition"].keys())
    comps_sorted = sorted(all_comps)

    headers = (
        ["Joueur", "Moy.", "JDR", "FotMob", "Notés", "Non notés", "Total",
         "Min", "Max", "σ", "Buts", "Passes"]
        + comps_sorted
    )
    rows = []
    for s in stats:
        row = [
            s["player_name"],
            f"{s['moyenne_globale']:.2f}",
            f"{s['moyenne_jdr']:.2f}" if s.get("moyenne_jdr") else "—",
            f"{s['moyenne_fotmob']:.2f}" if s.get("moyenne_fotmob") else "—",
            s["nb_matchs"],
            s.get("nb_matchs_non_notes", 0),
            s.get("nb_matchs_total", s["nb_matchs"]),
            s["note_min"],
            s["note_max"],
            f"{s['ecart_type']:.2f}",
            s.get("total_goals", 0),
            s.get("total_assists", 0),
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

    title = "=== Stats saison 2025-2026"
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
    print(f"{'Joueur':<35} {'Moy':>6} {'JDR':>6} {'FotMob':>7} {'Notés':>6} {'Total':>6}")
    print("-" * 72)
    for s in stats:
        jdr = f"{s['moyenne_jdr']:.2f}" if s.get("moyenne_jdr") else "—"
        fm = f"{s['moyenne_fotmob']:.2f}" if s.get("moyenne_fotmob") else "—"
        print(
            f"{s['player_name']:<35} "
            f"{s['moyenne_globale']:>6.2f} "
            f"{jdr:>6} {fm:>7} "
            f"{s['nb_matchs']:>6} "
            f"{s.get('nb_matchs_total', s['nb_matchs']):>6}"
        )
    print(f"\nTotal : {len(stats)} joueurs\n")


def print_player_detail(player_stats: dict) -> None:
    """Affiche le détail d'un joueur."""
    print(f"\n=== {player_stats['player_name']} ===")
    print(f"Moyenne globale : {player_stats['moyenne_globale']:.2f}/10")
    moy_jdr = player_stats.get("moyenne_jdr", 0)
    moy_fm = player_stats.get("moyenne_fotmob", 0)
    if moy_jdr:
        print(f"  └ JDR    : {moy_jdr:.2f}")
    if moy_fm:
        print(f"  └ FotMob : {moy_fm:.2f}")
    print(f"Matchs notés   : {player_stats['nb_matchs']}")
    print(f"Non notés      : {player_stats.get('nb_matchs_non_notes', 0)}")
    print(f"Total appars.  : {player_stats.get('nb_matchs_total', player_stats['nb_matchs'])}")
    print(f"Note min / max : {player_stats['note_min']} / {player_stats['note_max']}")
    print(f"Écart-type     : {player_stats['ecart_type']:.2f}")
    goals = player_stats.get("total_goals", 0)
    assists = player_stats.get("total_assists", 0)
    if goals or assists:
        print(f"Buts / Passes  : {goals} / {assists}")

    if player_stats["par_competition"]:
        print("\nPar compétition :")
        for comp, data in sorted(player_stats["par_competition"].items()):
            print(f"  {comp:<30} {data['moyenne']:.2f}/10  ({data['nb_matchs']} matchs)")

    if player_stats["detail_matchs"]:
        print("\nDétail matchs :")
        print(f"  {'Date':<12} {'Adversaire':<25} {'Compétition':<22} {'JDR':>4} {'FotMob':>7} {'Combiné':>8}")
        print("  " + "-" * 80)
        for m in player_stats["detail_matchs"]:
            jdr = f"{m['jdr_note']}" if m.get("jdr_note") is not None else "—"
            fm = f"{m['fotmob_note']:.1f}" if m.get("fotmob_note") is not None else "—"
            note = f"{m['note']:.2f}" if m.get("note") is not None else "—"
            print(
                f"  {m['date']:<12} {(m['opponent'] or '?'):<25} "
                f"{m['competition']:<22} {jdr:>4} {fm:>7} {note:>8}"
            )
    print()
