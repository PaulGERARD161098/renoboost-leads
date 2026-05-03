"""Génération de patterns d'emails candidats (à vérifier ensuite via NeverBounce/ZeroBounce).

Stratégie 3 — combinaison :
- Nominatifs : si dirigeant connu (et pas chaîne) → prenom.nom@, pnom@, prenom@, nom@
- Fonctionnels : direction@, contact@, commercial@, communication@

Tous les patterns générés ont un statut "candidats", à différencier des emails scrapés
qui sont déjà connus exister sur le site.
"""

from __future__ import annotations

import re

# Patterns fonctionnels génériques (prioritaires pour B2B)
PATTERNS_FONCTIONNELS = [
    "direction",
    "contact",
    "commercial",
    "communication",
]


def _normaliser_nom_pour_email(s: str | None) -> str | None:
    """Convertit un nom en chaîne utilisable dans une partie locale d'email.

    Exemples :
    - "Marie-Claire" → "marieclaire"
    - "Dupont" → "dupont"
    - "DE LA TOUR" → "delatour"
    """
    if not s:
        return None
    s = s.strip().lower()

    # Suppr accents
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

    # Garde uniquement lettres et chiffres
    s = re.sub(r"[^a-z0-9]", "", s)
    return s or None


def generer_patterns_nominatifs(
    prenom: str | None,
    nom: str | None,
    domaine: str | None,
) -> list[str]:
    """Génère les variantes nominatives standard.

    Patterns générés (par ordre de fréquence en France) :
    - prenom.nom@domaine
    - p.nom@domaine
    - pnom@domaine
    - prenom@domaine
    - nom@domaine

    Returns:
        Liste sans doublons, triée par probabilité décroissante.
    """
    if not domaine:
        return []

    p = _normaliser_nom_pour_email(prenom)
    n = _normaliser_nom_pour_email(nom)

    candidats: list[str] = []

    if p and n:
        candidats.append(f"{p}.{n}@{domaine}")  # marie.dupont
        candidats.append(f"{p[0]}.{n}@{domaine}")  # m.dupont
        candidats.append(f"{p[0]}{n}@{domaine}")  # mdupont
        candidats.append(f"{p}{n}@{domaine}")  # mariedupont
        candidats.append(f"{n}.{p}@{domaine}")  # dupont.marie
    if p:
        candidats.append(f"{p}@{domaine}")  # marie
    if n:
        candidats.append(f"{n}@{domaine}")  # dupont

    # Dédup en gardant l'ordre
    vu: set[str] = set()
    resultat: list[str] = []
    for c in candidats:
        if c not in vu:
            vu.add(c)
            resultat.append(c)

    return resultat


def generer_patterns_fonctionnels(domaine: str | None) -> list[str]:
    """Génère les patterns fonctionnels génériques B2B."""
    if not domaine:
        return []
    return [f"{p}@{domaine}" for p in PATTERNS_FONCTIONNELS]


def generer_tous_patterns(
    prenom: str | None,
    nom: str | None,
    domaine: str | None,
    inclure_nominatifs: bool = True,
    inclure_fonctionnels: bool = True,
) -> tuple[list[str], bool]:
    """Génère tous les patterns selon la config.

    Returns:
        (liste_emails, contient_dirigeant_pattern)
        - liste_emails: candidats dans l'ordre de priorité
        - contient_dirigeant_pattern: True si on a généré des nominatifs
    """
    if not domaine:
        return [], False

    candidats: list[str] = []
    contient_dirigeant = False

    if inclure_nominatifs and (prenom or nom):
        nominatifs = generer_patterns_nominatifs(prenom, nom, domaine)
        candidats.extend(nominatifs)
        contient_dirigeant = bool(nominatifs)

    if inclure_fonctionnels:
        candidats.extend(generer_patterns_fonctionnels(domaine))

    # Dédup en gardant l'ordre
    vu: set[str] = set()
    resultat: list[str] = []
    for c in candidats:
        if c not in vu:
            vu.add(c)
            resultat.append(c)

    return resultat, contient_dirigeant
