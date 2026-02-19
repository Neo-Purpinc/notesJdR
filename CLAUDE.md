# CLAUDE.md — Scraper de notes Real Madrid

## Contexte
Scraper les articles de notes du Real Madrid sur `lejournaldureal.fr` (saison 2025-2026, depuis août 2025), calculer les moyennes par joueur et par compétition, et les visualiser via une interface Streamlit.

## Architecture

```
scraper.py      — Découverte des URLs + fetch HTML (cache local dans cache/)
notes_parser.py — Parsing HTML : extraction des notes + détection compétition
averages.py     — Calcul des moyennes + sérialisation JSON + affichage console
main.py         — CLI (argparse) + pipeline scrape → parse → stats
app.py          — Interface Streamlit (4 onglets)
output/         — data.json (articles bruts) + stats.json (moyennes calculées)
cache/          — Pages HTML cachées (gitignorées)
```

## Commandes

```bash
# Toujours utiliser -X utf8 sur Windows (noms accentués)
python -X utf8 main.py                        # Charger cache ou scraper + afficher stats
python -X utf8 main.py --refresh              # Re-scraper depuis le site (ignore le cache)
python -X utf8 main.py --competition Liga     # Filtrer par compétition
python -X utf8 main.py --joueur "Vinicius Jr" # Détail d'un joueur
python -X utf8 main.py --min-matchs 5         # Joueurs avec ≥ 5 matchs
python -X utf8 main.py --list-competitions    # Lister les compétitions détectées
python -X utf8 main.py --list-joueurs         # Lister tous les joueurs

python -X utf8 -m streamlit run app.py        # Lancer l'interface web
```

## Points clés

### Scraping
- URL de recherche : `https://lejournaldureal.fr/search?q=note&page={N}`
- Filtre : slug contenant `note` + date ≥ août 2025
- Délai 1.5s entre requêtes, retry ×3, cache MD5 dans `cache/`
- Saison 2025-2026 : environ 4-5 pages de recherche (~37 articles)

### Parsing des notes
- Regex `_NOTE_RE` dans `notes_parser.py` : capture `<strong>Nom (N/10)</strong>`
- Gère les variantes de substitution : `remplacé`, `entré`, `sorti`, `exclu`
- Détection compétition : priorité 1 = `og:image` filename, priorité 2 = texte article

### Normalisation des noms
- `NAME_ALIASES` dans `notes_parser.py` : dict nom court → nom canonique
- Exclure entraîneurs : mapper vers `"_COACH_"`
- Dédoublonnage par article (même joueur noté deux fois → garder le premier)

### Données
- `output/data.json` : liste d'articles (url, title, date, competition, opponent, players[])
- `output/stats.json` : stats par joueur (moyenne globale, par compétition, détail matchs)
- Ces fichiers sont commités dans git pour le déploiement Streamlit Cloud

## Déploiement (Streamlit Cloud)
- Repo GitHub public requis
- Fichier principal : `app.py`
- Les données `output/` sont dans le repo → app opérationnelle immédiatement
- Le bouton "Rafraîchir" re-scrape en live mais les données ne persistent pas après redémarrage
- Pour mettre à jour les données en prod : `python -X utf8 main.py --refresh` en local puis `git push`

## Dépendances
```
requests, tabulate, streamlit, plotly, pandas
```
Toutes déjà installées (Python 3.14, Windows). Voir `requirements.txt`.

## Pièges connus
- **Encodage Windows** : utiliser `python -X utf8` ou `PYTHONUTF8=1` — les noms accentués (Mbappé, Tchouaméni…) cassent cp1252
- **Filesystem éphémère** sur Streamlit Cloud : `cache/` est vide à chaque démarrage
- **Nouvelles variantes de substitution** (ex: `exclu`) : à ajouter dans `_NOTE_RE` et `_SUBST_RE` dans `notes_parser.py`
- **Nouveaux joueurs** : ajouter les alias dans `NAME_ALIASES` si le site utilise des variantes de noms
