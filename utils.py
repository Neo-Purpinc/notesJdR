"""
utils.py — Normalisation partagée des noms de joueurs (JDR + FotMob).

Source unique de vérité pour NAME_ALIASES, PLAYER_NAME_MAPPING et normalize_name().
Toujours modifier ici — ne jamais dupliquer dans notes_parser.py ou fotmob_scraper.py.
"""

import re

# ---------------------------------------------------------------------------
# Variantes de noms complets → nom canonique
# (FotMob retourne souvent le nom accentué complet)
# ---------------------------------------------------------------------------
PLAYER_NAME_MAPPING: dict[str, str] = {
    "Mastantuono": "Franco Mastantuono",
    # FotMob full-name variants
    "Vinícius Júnior": "Vinicius Jr",
    "Vinicius Junior": "Vinicius Jr",
    "Vinícius": "Vinicius Jr",
    "Kylian Mbappe": "Kylian Mbappé",
    "Luka Modric": "Luka Modrić",
    "Eder Militao": "Éder Militão",
    "Antonio Rudiger": "Antonio Rüdiger",
    "Aurelien Tchouameni": "Aurélien Tchouaméni",
    "Arda Guler": "Arda Güler",
    "Brahim Díaz": "Brahim Diaz",
    "Rodrygo Goes": "Rodrygo",
    "Fede Valverde": "Federico Valverde",
    "Raúl Asencio": "Raul Asencio",
}

# ---------------------------------------------------------------------------
# Aliases courts / noms de famille → nom canonique
# Utilisé par JDR (noms abrégés dans les articles) ET FotMob (noms courts)
# ---------------------------------------------------------------------------
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
    "Camvinga": "Eduardo Camavinga",
    "Modric": "Luka Modrić",
    "Modrić": "Luka Modrić",
    "Kroos": "Toni Kroos",
    "Ceballos": "Dani Ceballos",
    "Arnold": "Trent Alexander-Arnold",
    "Trent": "Trent Alexander-Arnold",
    "Trent Arnold": "Trent Alexander-Arnold",
    "Bellingham": "Jude Bellingham",
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
    # Entraîneurs / staff — exclus des stats joueurs
    "Ancelotti": "_COACH_",
    "Carlo Ancelotti": "_COACH_",
    "Arbeloa": "_COACH_",
    "Alvaro Arbeloa": "_COACH_",
    "Álvaro Arbeloa": "_COACH_",
    "Xabi Alonso": "_COACH_",
}

# Supprime les mentions de substitution résiduelles dans les noms bruts
_SUBST_RE = re.compile(
    r",?\s*(?:remplacé|entré en jeu|sorti|exclu)[^(,]*?(?=\s*$|\s*\()",
    re.IGNORECASE,
)


def normalize_name(raw: str) -> str:
    """Nettoie et normalise un nom de joueur vers sa forme canonique.

    Ordre de priorité :
      1. Match exact dans NAME_ALIASES
      2. Match sur le dernier mot (nom de famille) dans NAME_ALIASES
      3. Match exact dans PLAYER_NAME_MAPPING
      4. Match sur le dernier mot dans PLAYER_NAME_MAPPING
      5. Nom tel quel (après nettoyage)
    """
    name = _SUBST_RE.sub("", raw).strip().strip(",").strip()
    name = re.sub(r"\s+", " ", name)

    if name in NAME_ALIASES:
        return NAME_ALIASES[name]

    last = name.split()[-1] if name else name
    if last in NAME_ALIASES:
        return NAME_ALIASES[last]

    if name in PLAYER_NAME_MAPPING:
        return PLAYER_NAME_MAPPING[name]

    if last in PLAYER_NAME_MAPPING:
        return PLAYER_NAME_MAPPING[last]

    return name
