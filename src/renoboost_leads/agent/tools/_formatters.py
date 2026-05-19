"""Helpers de formatage pour le rapport HTML client.

Décodage des codes INSEE (tranches d'effectif), nettoyage des noms
d'entreprise verbeux (Google Places saisit parfois "S H C I" au lieu
de "SHCI"), format propre des dirigeants (Prénom NOM (qualité)) et
libellé NAF "code — libellé".

L'objectif est de produire des chaînes lisibles **à l'affichage** sans
modifier la donnée stockée (CSV/JSON intacts pour la traçabilité).
"""

from __future__ import annotations

import re

# Libellés officiels INSEE des tranches d'effectif salarié.
# Source : Sirene V3 — champ `tranche_effectifs`.
LIBELLES_TRANCHE_EFFECTIF: dict[str, str] = {
    "NN": "Non renseigné",
    "00": "0 salarié",
    "01": "1 ou 2 salariés",
    "02": "3 à 5 salariés",
    "03": "6 à 9 salariés",
    "11": "10 à 19 salariés",
    "12": "20 à 49 salariés",
    "21": "50 à 99 salariés",
    "22": "100 à 199 salariés",
    "31": "200 à 249 salariés",
    "32": "250 à 499 salariés",
    "41": "500 à 999 salariés",
    "42": "1 000 à 1 999 salariés",
    "51": "2 000 à 4 999 salariés",
    "52": "5 000 à 9 999 salariés",
    "53": "10 000 salariés et plus",
}


def decode_effectif(code: str | None, libelle: str | None = None) -> str:
    """Renvoie un libellé humain pour une tranche d'effectif.

    Priorité : libellé fourni par l'API > décodage du code INSEE > "—".
    """
    if libelle and str(libelle).strip():
        return str(libelle).strip()
    if code is None:
        return "—"
    key = str(code).strip()
    if not key:
        return "—"
    return LIBELLES_TRANCHE_EFFECTIF.get(key, key)


def format_naf(code: str | None, libelle: str | None = None) -> str:
    """Formate un code NAF avec son libellé : `47.91B — Vente à distance...`.

    Si seul le code est connu, renvoie le code. Si seul le libellé est
    connu, renvoie le libellé. Si rien, renvoie "—".
    """
    c = (code or "").strip()
    lib = (libelle or "").strip()
    if c and lib:
        return f"{c} — {lib}"
    return c or lib or "—"


# Reconnaît une séquence de >= 3 tokens d'une seule lettre majuscule
# (alphabétique uniquement, accents inclus) séparés par un espace.
# Ex : "S H C I", "A S D I", "S A S DUPONT" (collera "SAS" puis garde
# "DUPONT"). N'attrape pas "B & C BTP" (ampersand) ni "U S" (2 tokens).
_RE_LETTRES_ESPACEES = re.compile(
    r"(?<![^\W_])(?:[A-ZÀ-Ý]\s){2,}[A-ZÀ-Ý](?![^\W_])"
)


def nettoyer_nom_espaces(nom: str | None) -> str:
    """Recolle les séquences de lettres isolées dans un nom d'entreprise.

    Exemples :
      - "S H C I" -> "SHCI"
      - "A S D I LOGISTIQUE" -> "ASDI LOGISTIQUE"
      - "EDF FRANCE" -> inchangé
      - "B & C BTP" -> inchangé
    """
    if not nom:
        return ""
    return _RE_LETTRES_ESPACEES.sub(
        lambda m: m.group(0).replace(" ", ""), nom
    )


def _titre_prenom(prenom: str) -> str:
    """Met un prénom en title-case s'il est entièrement en majuscules.

    "GAMBATESA" -> "Gambatesa". "Pierre" -> "Pierre" (inchangé).
    Gère les composés "JEAN-PIERRE" -> "Jean-Pierre".
    """
    p = prenom.strip()
    if not p:
        return ""
    if p == p.upper():
        return "-".join(part.capitalize() for part in p.split("-"))
    return p


def format_dirigeant(
    nom: str | None,
    prenom: str | None = None,
    qualite: str | None = None,
) -> str:
    """Formate un dirigeant : `Prénom NOM (Qualité)`.

    Règles :
      - nom vide -> "—"
      - prénom vide ou identique au nom -> juste le nom
      - prénom tout-majuscule -> title-case ("GAMBATESA" -> "Gambatesa")
      - qualité fournie -> ajoutée entre parenthèses, capitalisée
        ("GÉRANT" -> "Gérant")
    """
    n = (nom or "").strip()
    p = (prenom or "").strip()
    q = (qualite or "").strip()

    if not n:
        return "—"

    base = n
    if p and p.upper() != n.upper():
        base = f"{_titre_prenom(p)} {n}"

    if q:
        return f"{base} ({q.capitalize()})"
    return base
