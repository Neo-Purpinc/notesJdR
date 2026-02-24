"""
parser.py — Extraction des notes et détection de compétition depuis le HTML brut.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalisation des noms
# ---------------------------------------------------------------------------

# Mapping variantes de noms → nom canonique (à compléter au fil du temps)
PLAYER_NAME_MAPPING: dict[str, str] = {
    "Mastantuono": "Franco Mastantuono",
}

NAME_ALIASES: dict[str, str] = {
    # Gardiens
    "Courtois": "Thibaut Courtois",
    "Lunin": "Andriy Lunin",
    "Fran Gonzalez": "Fran González",
    # Défenseurs
    "Carvajal": "Dani Carvajal",
    "Militao": "Éder Militão",
    "Militão": "Éder Militão",
    "Alaba": "David Alaba",
    "Rudiger": "Antonio Rüdiger",
    "Rüdiger": "Antonio Rüdiger",
    "Asencio": "Raul Asencio",
    "Huijsen": "Dean Huijsen",
    "Carreras": "Alvaro Carreras",
    "Mendy": "Ferland Mendy",
    "Gonzalo Garcia": "Gonzalo García",
    "Gonzalo": "Gonzalo García",
    "Fran Garcia": "Fran García",
    # Milieux
    "Valverde": "Federico Valverde",
    "Tchouameni": "Aurélien Tchouaméni",
    "Tchouaméni": "Aurélien Tchouaméni",
    "Camavinga": "Eduardo Camavinga",
    "Camvinga": "Eduardo Camavinga",   # typo récurrent sur le site
    "Modric": "Luka Modrić",
    "Modrić": "Luka Modrić",
    "Kroos": "Toni Kroos",
    "Ceballos": "Dani Ceballos",
    "Arnold": "Trent Alexander-Arnold",
    "Trent": "Trent Alexander-Arnold",
    "Trent Arnold": "Trent Alexander-Arnold",
    # Attaquants
    "Vinicius Jr.": "Vinicius Jr",
    "Vinicius": "Vinicius Jr",
    "Mbappé": "Kylian Mbappé",
    "Mbappe": "Kylian Mbappé",
    "Rodrygo Goes": "Rodrygo",
    "Güler": "Arda Güler",
    "Guler": "Arda Güler",
    "Brahim": "Brahim Diaz",
    "Brahim Diaz": "Brahim Diaz",
    "Brahim Díaz": "Brahim Diaz",
    "Endrick": "Endrick Felipe",
    # Entraîneurs (exclus des stats joueurs)
    "Xabi Alonso": "_COACH_",
    "Ancelotti": "_COACH_",
    "Carlo Ancelotti": "_COACH_",
    "Alvaro Arbeloa": "_COACH_",
    "Álvaro Arbeloa": "_COACH_",
    "Arbeloa": "_COACH_",
}

# Regex pour capturer : <strong>Nom Prénom[, remplacé/entré ...] (N/10)</strong>
# group 1 = nom brut (peut inclure info substitution)
# group 2 = note
_NOTE_RE = re.compile(
    r"<strong>\s*([^<(]+?)\s*(?:,\s*(?:remplacé|entré|sorti|exclu)[^(]*)?\((\d+)/10\)\s*</strong>",
    re.IGNORECASE,
)

# Lignes "Non noté" à ignorer dans _NOTE_RE (sécurité)
_NON_NOTE_RE = re.compile(r"Non\s+not[ée]", re.IGNORECASE)

# Structure réelle : <p><strong>Nom, entré...</strong>: Non noté.</p>
# → on capte tout le bloc <p>, puis on nettoie les balises
_NON_NOTE_BLOCK_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


def _extract_non_noted_name(block_html: str) -> str | None:
    """Extrait le nom depuis le HTML d'un bloc <p> contenant 'Non noté'."""
    text = re.sub(r"<[^>]+>", "", block_html)       # supprime les balises
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    # Nom = tout ce qui précède la première virgule, parenthèse ou deux-points
    m = re.match(r"([^:,(]+?)(?=[,:(]|$)", text)
    return m.group(1).strip() if m else None

# Nettoyage du nom brut (supprime la partie substitution qui resterait)
_SUBST_RE = re.compile(
    r",?\s*(?:remplacé|entré en jeu|sorti|exclu)[^(,]*?(?=\s*$|\s*\()",
    re.IGNORECASE,
)


def normalize_name(raw: str) -> str:
    """Nettoie et normalise un nom de joueur."""
    # Supprime les infos de substitution résiduelles
    name = _SUBST_RE.sub("", raw).strip().strip(",").strip()
    # Normalise les espaces multiples
    name = re.sub(r"\s+", " ", name)
    # Cherche dans le dict d'alias (exact match d'abord)
    if name in NAME_ALIASES:
        return NAME_ALIASES[name]
    # Cherche par nom de famille seul (dernier mot)
    last_name = name.split()[-1] if name else name
    if last_name in NAME_ALIASES:
        return NAME_ALIASES[last_name]
    # Applique PLAYER_NAME_MAPPING (variantes de noms complets)
    if name in PLAYER_NAME_MAPPING:
        return PLAYER_NAME_MAPPING[name]
    if last_name in PLAYER_NAME_MAPPING:
        return PLAYER_NAME_MAPPING[last_name]
    return name


# ---------------------------------------------------------------------------
# Détection de la compétition
# ---------------------------------------------------------------------------

_OG_IMAGE_RE = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Priorité 0 : détection depuis le titre (la plus fiable)
_TITLE_COMP_RULES = [
    (re.compile(r"ligue\s+des\s+champions|champions\s+league", re.IGNORECASE), "Ligue des Champions"),
    (re.compile(r"supercoupe|supercopa", re.IGNORECASE), "Supercoupe d'Espagne"),
    (re.compile(r"coupe\s+du\s+roi|copa\s+del\s+rey", re.IGNORECASE), "Coupe du Roi"),
    (re.compile(r"intercontinental", re.IGNORECASE), "Coupe Intercontinentale"),
    (re.compile(r"\bamical\b|friendly", re.IGNORECASE), "Amical"),
]

# Priorité 1 : tags WordPress dans le payload RSC (très fiable — posés par le rédacteur)
# Le payload Next.js contient du JSON doublement échappé : \" devient \" dans la string Python.
# On recherche \"tags\":[ et on inspecte les 800 premiers octets (les tags de l'article courant).
_WP_TAGS_RE = re.compile(r'\\"tags\\":\[')

_WP_TAGS_COMP_MAP = [
    ("ligue-des-champions", "Ligue des Champions"),
    ("supercoupe", "Supercoupe d'Espagne"),
    ("supercopa", "Supercoupe d'Espagne"),
    ("copa-del-rey", "Coupe du Roi"),
    ("coupe-du-roi", "Coupe du Roi"),
    ("intercontinental", "Coupe Intercontinentale"),
    ("pre-season", "Amical"),
    ("friendly", "Amical"),
    ("amical", "Amical"),
]

# Mapping fichier og:image → compétition
_OG_COMPETITION_MAP = [
    (["laliga", "laliga-ea-sports", "la-liga"], "Liga"),
    (["champions-league", "uefa-champions-league", "ligue-des-champions"], "Ligue des Champions"),
    (["spanish-super-cup", "supercopa"], "Supercoupe d'Espagne"),
    (["copa-del-rey", "coupe-du-roi"], "Coupe du Roi"),
    (["intercontinental"], "Coupe Intercontinentale"),
    (["pre-season", "friendly", "amical", "preseason"], "Amical"),
]

# Mapping texte article → compétition
_TEXT_COMPETITION_RULES = [
    # Ordre important : plus spécifique d'abord
    (
        re.compile(
            r"ligue\s+des\s+champions|champions\s+league|phase\s+de\s+ligue"
            r"|barrage|huitième\s+de\s+finale|quart\s+de\s+finale"
            r"|demi-finale\s+(?:de\s+la\s+)?ligue|finale\s+(?:de\s+la\s+)?ligue\s+des\s+champions",
            re.IGNORECASE,
        ),
        "Ligue des Champions",
    ),
    (
        re.compile(r"\bsupercoupe\b|\bsupercopa\b|\bsuper\s+cup\b", re.IGNORECASE),
        "Supercoupe d'Espagne",
    ),
    (
        re.compile(r"coupe\s+du\s+roi|copa\s+del\s+rey", re.IGNORECASE),
        "Coupe du Roi",
    ),
    (
        re.compile(r"intercontinental", re.IGNORECASE),
        "Coupe Intercontinentale",
    ),
    (
        re.compile(r"\bamical\b|match\s+de\s+pr[eé]-saison|pr[eé]-saison|friendly", re.IGNORECASE),
        "Amical",
    ),
    (
        re.compile(r"\bliga\b|\blaliga\b|\bchampionnat\b|\bla\s+liga\b", re.IGNORECASE),
        "Liga",
    ),
]


def detect_competition(html: str, title: str = "") -> str:
    """Détecte la compétition via le titre, tags WP, og:image, puis le corps de l'article."""
    # Priorité 0 : titre (le plus fiable — écrit par le journaliste)
    if title:
        for pattern, competition in _TITLE_COMP_RULES:
            if pattern.search(title):
                return competition

    # Priorité 1 : tags WordPress dans le payload RSC
    # On inspecte les 800 premiers octets après \"tags\":[ pour rester dans les tags
    # de l'article courant (les articles liés apparaissent bien plus loin).
    tags_m = _WP_TAGS_RE.search(html)
    if tags_m:
        tags_window = html[tags_m.start(): tags_m.start() + 800]
        for slug, competition in _WP_TAGS_COMP_MAP:
            if slug in tags_window:
                return competition

    # Priorité 3 : og:image filename
    og_match = _OG_IMAGE_RE.search(html)
    if og_match:
        filename = og_match.group(1).split("/")[-1].lower()
        is_generic = re.match(r"nouveau-projet[-_]?\d*\.", filename) or re.match(r"image[-_]?\d*\.", filename)
        if not is_generic:
            for keywords, competition in _OG_COMPETITION_MAP:
                if any(kw in filename for kw in keywords):
                    return competition

    # Priorité 4 : texte du corps de l'article uniquement (évite les faux positifs
    # de la sidebar/footer qui peut mentionner d'autres compétitions)
    article_m = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
    body_text = re.sub(r"<[^>]+>", " ", article_m.group(1) if article_m else html)

    for pattern, competition in _TEXT_COMPETITION_RULES:
        if pattern.search(body_text):
            return competition

    return "Liga"  # défaut : toutes les autres rencontres sont en Liga


# ---------------------------------------------------------------------------
# Extraction du titre et de l'adversaire
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.IGNORECASE)
_OG_TITLE_RE = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def extract_title(html: str) -> str:
    """Extrait le titre de l'article."""
    m = _OG_TITLE_RE.search(html)
    if m:
        return m.group(1).strip()
    m = _TITLE_RE.search(html)
    if m:
        return m.group(1).strip()
    return "Sans titre"


def extract_opponent(title: str) -> str:
    """Extrait l'adversaire depuis le titre de l'article."""
    # Format typique : "Real Madrid - Adversaire (X-Y) : les notes..."
    # ou "Adversaire - Real Madrid (X-Y) : les notes..."
    m = re.match(
        r"^(.+?)\s*[-–]\s*(.+?)\s*[\(\[]?\s*\d+\s*[-–]\s*\d+",
        title,
        re.IGNORECASE,
    )
    if m:
        team1 = m.group(1).strip()
        team2 = m.group(2).strip()
        # Retourner l'équipe qui n'est pas le Real Madrid
        real_variants = re.compile(r"real\s+madrid", re.IGNORECASE)
        if real_variants.search(team1):
            return team2
        return team1
    return title


# ---------------------------------------------------------------------------
# Structure de données
# ---------------------------------------------------------------------------

@dataclass
class PlayerRating:
    name: str
    note: int | None  # None = "Non noté" (remplaçant entré très tard)


@dataclass
class ArticleData:
    url: str
    title: str
    date: str
    competition: str
    opponent: str
    players: list[PlayerRating] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def parse_article(url: str, html: str, date: str) -> ArticleData | None:
    """Parse un article HTML et retourne les données structurées."""
    # Vérification rapide : l'article doit contenir des notes /10
    if "(/10)" not in html and "/10)" not in html:
        # Cherche avec regex
        if not _NOTE_RE.search(html):
            logger.debug("No ratings found in %s, skipping.", url)
            return None

    title = extract_title(html)
    competition = detect_competition(html, title=title)
    opponent = extract_opponent(title)

    players: list[PlayerRating] = []
    seen_names: set[str] = set()

    for m in _NOTE_RE.finditer(html):
        raw_name = m.group(1).strip()
        note_str = m.group(2)

        # Ignorer les lignes "Non noté" (ne devraient pas matcher le regex mais par sécurité)
        if _NON_NOTE_RE.search(raw_name):
            continue

        note = int(note_str)
        if note < 0 or note > 10:
            logger.warning("Invalid rating %d for %s in %s", note, raw_name, url)
            continue

        canonical = normalize_name(raw_name)

        # Exclure les entraîneurs
        if canonical == "_COACH_":
            logger.debug("Skipping coach: %s", raw_name)
            continue

        # Dédoublonnage par article (même joueur noté 2 fois)
        if canonical in seen_names:
            logger.debug("Duplicate player %s in %s, keeping first.", canonical, url)
            continue

        seen_names.add(canonical)
        players.append(PlayerRating(name=canonical, note=note))

    # --- Joueurs non notés ("Non noté") ---
    # Structure réelle : <p><strong>Nom, entré...</strong>: Non noté.</p>
    for block_m in _NON_NOTE_BLOCK_RE.finditer(html):
        block = block_m.group(1)
        if not _NON_NOTE_RE.search(block):
            continue
        raw_name = _extract_non_noted_name(block)
        if not raw_name:
            continue
        canonical = normalize_name(raw_name)
        if canonical == "_COACH_":
            continue
        if canonical in seen_names:
            continue  # déjà noté dans cet article
        seen_names.add(canonical)
        players.append(PlayerRating(name=canonical, note=None))
        logger.debug("Non-rated player: %s in %s", canonical, url)

    if not players:
        logger.info("No valid player ratings found in %s", url)
        return None

    return ArticleData(
        url=url,
        title=title,
        date=date,
        competition=competition,
        opponent=opponent,
        players=players,
    )
