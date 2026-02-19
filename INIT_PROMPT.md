# Scraper de notes Real Madrid — lejournaldureal.fr

## Contexte & objectif
Créer un outil Python qui scrape tous les articles de notes du Real Madrid sur https://lejournaldureal.fr depuis le début de la saison 2025-2026 (août 2025), calcule la moyenne des notes par joueur, et les ventile par compétition (Liga, Ligue des Champions, Coupe du Roi, etc.).

---

## Analyse technique du site (Next.js App Router + WordPress backend)

### 1. Page de recherche
URL : `https://lejournaldureal.fr/search?q=note&page={N}`
- Renvoie du HTML standard (pas de JSON/API GraphQL publique)
- Les articles de notes sont des liens au format `/YYYY/MM/DD/slug`
- Filtrer les slugs contenant `note` ou `notes`
- La saison 2025-2026 couvre les pages 1 à ~4 (filtrer par année ≥ 2025 et mois ≥ 08 pour 2025)
- Chaque page contient ~12 articles, itérer jusqu'à atteindre des dates antérieures à août 2025

### 2. Structure HTML d'un article de notes
URL d'exemple : `https://lejournaldureal.fr/2026/02/17/benfica-real-madrid-notes-2`
```html
<article>
  <h1>Benfica - Real Madrid (0-1) : les notes du match !</h1>
  <div class="article-content">
    <p>Texte d'introduction mentionnant la compétition...</p>
    <h2>Les notes des titulaires du Real Madrid</h2>
    <p><strong>Thibaut Courtois (7/10)</strong> : commentaire...</p>
    <p><strong>Alvaro Carreras, remplacé à la 99e minute (6/10)</strong> : commentaire...</p>
    <p><strong>Vinicius Jr, remplacé à la 90e minute (8/10)</strong> : commentaire...</p>
    <h2>La note de l'entraîneur</h2>
    <p><strong>Alvaro Arbeloa (7/10)</strong> : commentaire...</p>
    <h2>Les notes des remplaçants</h2>
    <p>Brahim Diaz, entré en jeu à la 86e minute : Non noté.</p>
  </div>
</article>
```

**Regex d'extraction des notes :**
```python
import re
pattern = r'<strong>([^<]+?)\\s*(?:,\\s*(?:remplacé|entré)[^(]*)?\\((\\d+)/10\\)</strong>'
# group(1) = nom brut, group(2) = note (int)
```

**Nettoyage du nom :**
```python
name = re.sub(r',?\\s*(?:remplacé|entré)[^(]*$', '', raw_name).strip()
```

**Important :** Certains articles utilisent le nom complet (`Thibaut Courtois`), d'autres seulement le nom de famille (`Courtois`, `Valverde`, `Tchouameni`). Créer un dictionnaire de normalisation.

**Remplaçants non notés :** lignes avec `Non noté` → ignorer pour les moyennes.

**Exclure l'entraîneur** (Xabi Alonso / Alvaro Arbeloa) des stats joueurs, ou les traiter séparément.

### 3. Détection de la compétition (ordre de priorité)

**Priorité 1 — og:image filename** (très fiable, présent dans le `<head>`) :
```python
og_image = re.search(r'<meta\\s+property="og:image"\\s+content="([^"]+)"', html)
filename = og_image.group(1).split('/')[-1].lower() if og_image else ''

if 'laliga' in filename or 'laliga-ea-sports' in filename:
    competition = 'Liga'
elif 'champions-league' in filename or 'uefa-champions-league' in filename:
    competition = 'Ligue des Champions'
elif 'spanish-super-cup' in filename or 'supercopa' in filename:
    competition = 'Supercoupe d\\'Espagne'
elif 'copa-del-rey' in filename:
    competition = 'Coupe du Roi'
elif 'pre-season' in filename or 'friendly' in filename:
    competition = 'Amical'
elif 'intercontinental' in filename:
    competition = 'Coupe Intercontinentale'
```

**Priorité 2 — Texte intégral de l'article** (fallback quand l'image est générique comme `Nouveau-projet-XX.webp`) :
```python
body_text = re.sub(r'<[^>]+>', ' ', html)
body_text_lower = body_text.lower()

if 'ligue des champions' in body_text_lower or 'champions league' in body_text_lower \\
   or 'phase de ligue' in body_text_lower or 'barrage' in body_text_lower \\
   or 'huitième de finale' in body_text_lower:
    competition = 'Ligue des Champions'
elif re.search(r'\\bliga\\b|\\blaliga\\b|\\bchampionnat\\b', body_text_lower):
    competition = 'Liga'
elif 'supercoupe' in body_text_lower:
    competition = 'Supercoupe d\\'Espagne'
elif 'coupe du roi' in body_text_lower or 'copa del rey' in body_text_lower:
    competition = 'Coupe du Roi'
else:
    competition = 'Inconnue'
```

---

## Normalisation des noms de joueurs
Créer un dict de normalisation pour fusionner les variantes :
```python
NAME_ALIASES = {
    'Courtois': 'Thibaut Courtois',
    'Valverde': 'Federico Valverde',
    'Tchouameni': 'Aurélien Tchouaméni',
    'Tchouaméni': 'Aurélien Tchouaméni',
    'Vinicius Jr.': 'Vinicius Jr',
    'Militao': 'Éder Militão',
    'Militão': 'Éder Militão',
    'Camavinga': 'Eduardo Camavinga',
    'Güler': 'Arda Güler',
    'Mbappé': 'Kylian Mbappé',
    'Mbappe': 'Kylian Mbappé',
    'Huijsen': 'Dean Huijsen',
    'Asencio': 'Raul Asencio',
    'Carreras': 'Alvaro Carreras',
    'Rudiger': 'Antonio Rüdiger',
    'Rüdiger': 'Antonio Rüdiger',
    'Lunin': 'Andriy Lunin',
    'Carvajal': 'Dani Carvajal',
    'Brahim': 'Brahim Diaz',
    'Brahim Diaz': 'Brahim Diaz',
    'Ceballos': 'Dani Ceballos',
    'Mendy': 'Ferland Mendy',
    'Arnold': 'Trent Alexander-Arnold',
    # entraîneurs (à exclure des stats joueurs)
    'Xabi Alonso': '_COACH_',
    'Alvaro Arbeloa': '_COACH_',
}
```

---

## Structure de données attendue
```python
# Par article
{
    'url': str,
    'title': str,
    'date': str,          # ex: '2026-02-17'
    'competition': str,   # Liga / Ligue des Champions / Coupe du Roi / etc.
    'players': [
        {'name': str, 'note': int}
    ]
}

# Output final (par joueur)
{
    'player_name': str,
    'moyenne_globale': float,
    'nb_matchs': int,
    'par_competition': {
        'Liga': {'moyenne': float, 'nb_matchs': int},
        'Ligue des Champions': {'moyenne': float, 'nb_matchs': int},
        ...
    },
    'detail_matchs': [
        {'date': str, 'adversaire': str, 'competition': str, 'note': int}
    ]
}
```

---

## Implémentation

### Dépendances
requests
beautifulsoup4  # optionnel, regex suffisant vu la structure simple

### Scraping éthique
- Délai de 1-2 secondes entre les requêtes (`time.sleep(1.5)`)
- User-Agent standard
- Gérer les erreurs HTTP (retry × 3)
- Cache local des pages HTML dans un dossier `cache/` pour éviter de re-scraper

### Fichiers à créer
1. `scraper.py` — Récupération de toutes les URLs de notes depuis la recherche + fetch des articles
2. `parser.py` — Extraction des notes et détection de compétition depuis le HTML brut
3. `averages.py` — Calcul des moyennes + normalisation des noms
4. `main.py` — Point d'entrée CLI avec options `--saison`, `--competition`, `--joueur`
5. `output/` — Export JSON + affichage tableau console (librairie `rich` ou `tabulate`)

### UI de visualisation
Créer une interface web légère avec **Streamlit** (zero-config, pas de frontend séparé).

Fichier : `app.py`
```bash
pip install streamlit plotly pandas
streamlit run app.py
```

#### Composants de l'UI

**Sidebar (filtres globaux)**
- Multiselect `Compétition` (Liga / LdC / Coupe du Roi / Supercoupe / Tout)
- Multiselect `Joueurs` (liste dynamique issue des données)
- Bouton `🔄 Rafraîchir les données` (relance le scraper)

**Onglet 1 — Tableau général**
- `st.dataframe` avec le tableau joueur × (moyenne globale, nb matchs, moyenne Liga, moyenne LdC, etc.), triable sur toutes les colonnes
- Mise en couleur conditionnelle via `df.style` : vert ≥ 7, orange 5-6, rouge ≤ 4

**Onglet 2 — Évolution temporelle**
- Graphe `plotly express` `line` : axe X = date des matchs, axe Y = note, une ligne par joueur sélectionné
- Ajouter les points avec tooltip (adversaire, compétition, note)
- Possibilité d'afficher la moyenne glissante (fenêtre 5 matchs) en trait pointillé

**Onglet 3 — Comparaison joueurs**
- `plotly express bar` groupé : un groupe par compétition, une barre par joueur sélectionné
- En dessous : radar chart (`plotly graph_objects Scatterpolar`) pour comparer les profils (moyenne Liga, LdC, Coupe du Roi, régularité = écart-type inversé)

**Onglet 4 — Détail par match**
- Table filtrée par joueur + compétition
- Colonnes : Date | Adversaire | Compétition | Note | 🏆 (icône selon compétition)

### CLI usage
```bash
python main.py                          # Toutes compétitions, tous joueurs
python main.py --competition Liga       # Filtre Liga uniquement
python main.py --joueur "Vinicius Jr"   # Stats d'un joueur
python main.py --refresh                # Re-scrape (ignore le cache)
```

---

## Points d'attention
- **Saison 2025-2026** : articles de août 2025 (inclus) à aujourd'hui. Le premier match de Liga était le 19 août 2025 (Real Madrid - Osasuna).
- **Coupe Intercontinentale FIFA 2025** (juin-juillet 2025) : hors saison régulière, à exclure ou catégoriser séparément.
- **Supercoupe d'Espagne** (janvier 2026, Arabie Saoudite) : compétition distincte à part.
- **Matchs amicaux de pré-saison** (juillet-août 2025, WSG Tirol etc.) : inclure ou exclure selon préférence.
- Certaines pages search retournent aussi des articles non-notes (news, mercato) avec le mot "note" dans le texte — filtrer strictement sur le slug contenant `note` + vérifier que l'article contient bien des `(X/10)`.
- Le site n'a pas d'API publique GraphQL exploitable directement, utiliser du parsing HTML pur.