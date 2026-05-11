"""Matcher : algo de scoring nom + adresse → SIREN.

Algorithme :
- Match adresse (CP + ville exacts) : +50 pts
- Match nom (Levenshtein > 0.8) : +30 pts
- Statut "actif" (pas radié) : +20 pts
- Forme juridique commerciale > association > autoentreprise : +10 pts
- Seuil de confiance : 60 pts
- Si score < 60 → flag `match_incertain=True`
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..common.logger import get_logger

logger = get_logger(__name__)


# Formes juridiques considérées comme "commerciales prioritaires"
FORMES_COMMERCIALES_PRIORITAIRES = {
    # Code → catégorie
    "5710": "SAS",
    "5720": "SAS Unipersonnelle",
    "5499": "SARL",
    "5498": "SARL",
    "5410": "SA",
    "5470": "SA",
    "6540": "SCI",  # SCI = OK pour parking commercial
    "5202": "SNC",
    "5306": "SE",
}

# Formes "moyennes"
FORMES_MOYENNES = {
    "5191": "Société européenne",
    "5599": "SA Coopérative",
    "9220": "Association",
    "9230": "Association",
}


# ════════════════════════════════════════════════════════════════
# Helpers de comparaison
# ════════════════════════════════════════════════════════════════


def _normaliser(s: str | None) -> str:
    """Minuscules, sans accents, sans ponctuation pour comparer."""
    if not s:
        return ""
    s = s.lower().strip()
    # Suppr accents simples (é → e, è → e, etc.)
    accents = {
        "à": "a",
        "â": "a",
        "ä": "a",
        "ç": "c",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ÿ": "y",
        "œ": "oe",
        "æ": "ae",
    }
    for a, b in accents.items():
        s = s.replace(a, b)
    # Suppr ponctuation
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Mots descriptifs (métiers, secteurs, fonctions) qui pollutent les noms
# commerciaux et empêchent un matching Levenshtein contre la raison sociale
# courte d'INSEE. La présence d'un de ces mots en position >= 1 signe la fin
# de la "marque" et le début de la description.
_MOTS_DESCRIPTIFS = frozenset(
    {
        # Métiers / savoir-faire industriels
        "mecanique",
        "outillage",
        "precision",
        "fraisage",
        "tournage",
        "usinage",
        "soudure",
        "soudage",
        "chaudronnerie",
        "metallerie",
        "metallurgie",
        "decoupe",
        "decoupage",
        "emboutissage",
        "forge",
        # Secteurs / activités
        "industrie",
        "industriel",
        "industrielle",
        "industries",
        "industrials",
        "technique",
        "techniques",
        "technologie",
        "technologies",
        "ingenierie",
        "fabrication",
        "production",
        "conception",
        # Mots fonctionnels génériques
        "services",
        "solutions",
        "conseil",
        "conseils",
        "etude",
        "etudes",
        "distribution",
        "negoce",
        "import",
        "export",
        "commerce",
        "vente",
        "ventes",
        # Lieux / structures
        "atelier",
        "ateliers",
        "usine",
        "site",
        "sites",
        "succursale",
        "agence",
        "laboratoire",
        "centre",
    }
)


def _nettoyer_nom_commercial(nom: str | None) -> str:
    """Coupe un nom commercial au 1er mot descriptif rencontré (B6).

    Conserve les mots avant le 1er token figurant dans `_MOTS_DESCRIPTIFS`,
    à condition qu'au moins un token utile précède (sinon on retournerait
    une chaîne vide qui matcherait tout).

    Exemples :
        "SMI mécanique et outillage de précision" → "SMI"
        "Hôtel Le Sud" → "Hôtel Le Sud"  (aucun mot stop)
        "Mécanique Précision SARL" → "Mécanique Précision SARL"  (mot stop en pos 0)
    """
    if not nom:
        return ""
    tokens = nom.split()
    if not tokens:
        return ""
    # Le nom normalisé sert uniquement à comparer chaque token au stop-set ;
    # on conserve les tokens originaux pour le résultat.
    tokens_normalises = _normaliser(nom).split()
    coupure: int | None = None
    for i, t in enumerate(tokens_normalises):
        if i == 0 or t not in _MOTS_DESCRIPTIFS:
            continue
        # Ne coupe que si au moins un token non-descriptif précède la coupure,
        # sinon on retournerait une marque vide ou tronquée à un autre mot stop.
        if any(p not in _MOTS_DESCRIPTIFS for p in tokens_normalises[:i]):
            coupure = i
            break
    if coupure is None:
        return nom.strip()
    return " ".join(tokens[:coupure])


def _levenshtein_similarity(a: str, b: str) -> float:
    """Similarité 0-1 basée sur la distance de Levenshtein.

    Implémentation simple sans dépendance externe (rapidfuzz pas requis).
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    a, b = _normaliser(a), _normaliser(b)
    if a == b:
        return 1.0

    # Algo classique en O(len_a * len_b)
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0

    prev = list(range(len_b + 1))
    curr = [0] * (len_b + 1)
    for i, ca in enumerate(a, start=1):
        curr[0] = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    distance = prev[len_b]

    # Normalisation
    max_len = max(len_a, len_b)
    return 1.0 - (distance / max_len)


def _extraire_cp_ville_de_resultat(result: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extrait CP et ville depuis un résultat de l'API."""
    siege = result.get("siege") or {}
    cp = siege.get("code_postal")
    ville = siege.get("libelle_commune") or siege.get("commune")
    return (cp, ville)


# ════════════════════════════════════════════════════════════════
# Scoring d'un candidat
# ════════════════════════════════════════════════════════════════


@dataclass
class ScoreDetail:
    score: float
    detail: dict[str, float]


def scorer_candidat(
    candidat: dict[str, Any],
    nom_cible: str,
    code_postal_cible: str | None,
    ville_cible: str | None,
) -> ScoreDetail:
    """Calcule le score de matching d'un candidat de l'API."""
    detail: dict[str, float] = {
        "adresse": 0.0,
        "nom": 0.0,
        "statut": 0.0,
        "forme": 0.0,
    }

    # 1. Match adresse (CP + ville)
    cp_cand, ville_cand = _extraire_cp_ville_de_resultat(candidat)
    if cp_cand and code_postal_cible and cp_cand == code_postal_cible:
        if ville_cand and ville_cible and _normaliser(ville_cand) == _normaliser(ville_cible):
            detail["adresse"] = 50.0
        else:
            # CP exact mais ville différente (limitrophe) → demi-score
            detail["adresse"] = 25.0
    elif cp_cand and code_postal_cible and cp_cand[:2] == code_postal_cible[:2]:
        # Même département → 1/5 du score
        detail["adresse"] = 10.0

    # 2. Match nom commercial — B6 : on nettoie les deux côtés des mots
    # descriptifs verbeux pour que Levenshtein compare les marques entre elles.
    nom_cand = candidat.get("nom_complet") or candidat.get("nom_raison_sociale") or ""
    nom_cible_clean = _nettoyer_nom_commercial(nom_cible)
    nom_cand_clean = _nettoyer_nom_commercial(nom_cand)
    similarity = _levenshtein_similarity(nom_cible_clean, nom_cand_clean)
    if similarity >= 0.8:
        detail["nom"] = 30.0
    elif similarity >= 0.6:
        detail["nom"] = 18.0
    elif similarity >= 0.4:
        detail["nom"] = 8.0

    # 3. Statut actif (pas radié)
    etat = (candidat.get("etat_administratif") or "").upper()
    if etat == "A":  # A = Actif
        detail["statut"] = 20.0

    # 4. Forme juridique
    code_forme = str(candidat.get("nature_juridique") or "")
    if code_forme in FORMES_COMMERCIALES_PRIORITAIRES:
        detail["forme"] = 10.0
    elif code_forme in FORMES_MOYENNES:
        detail["forme"] = 5.0
    elif code_forme:
        detail["forme"] = 2.0  # Autre forme reconnue

    score_total = sum(detail.values())
    return ScoreDetail(score=score_total, detail=detail)


# ════════════════════════════════════════════════════════════════
# Sélection du meilleur candidat
# ════════════════════════════════════════════════════════════════


SEUIL_CONFIANCE = 60.0


def selectionner_meilleur_candidat(
    candidats: list[dict[str, Any]],
    nom_cible: str,
    code_postal_cible: str | None,
    ville_cible: str | None,
) -> tuple[dict[str, Any] | None, float, bool]:
    """Choisit le candidat avec le score le plus haut.

    Returns:
        (candidat_choisi, score, match_incertain)
        - candidat_choisi : dict du résultat retenu, ou None si liste vide
        - score : 0-110 (somme pondérée)
        - match_incertain : True si score < SEUIL_CONFIANCE
    """
    if not candidats:
        return None, 0.0, True

    scores: list[tuple[dict[str, Any], float, dict[str, float]]] = []
    for c in candidats:
        sd = scorer_candidat(c, nom_cible, code_postal_cible, ville_cible)
        scores.append((c, sd.score, sd.detail))

    # Tri par score décroissant
    scores.sort(key=lambda x: x[1], reverse=True)
    best, best_score, _ = scores[0]
    incertain = best_score < SEUIL_CONFIANCE

    if incertain:
        logger.debug(
            "Match incertain pour %r (score=%.1f<%.0f)", nom_cible, best_score, SEUIL_CONFIANCE
        )

    return best, best_score, incertain
