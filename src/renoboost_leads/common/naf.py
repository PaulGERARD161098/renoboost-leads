"""Libellés NAF (nomenclature rev. 2) au niveau division — fallback local.

L'API recherche-entreprises renvoie le **code** NAF (ex. ``10.13A``) mais pas
toujours son libellé. Pour l'affichage CRM, on complète avec le libellé de la
**division** (2 premiers chiffres du code), toujours disponible localement.

Granularité division (88 entrées) : suffisant pour catégoriser un lead
(« Industries alimentaires » pour ``10.13A``) sans embarquer les 732 sous-classes.
Le libellé précis, s'il est fourni par une source (Pappers, Societeinfo), reste
prioritaire — cette table n'est qu'un repli.
"""

from __future__ import annotations

import re

# Divisions NAF rev. 2 (code à 2 chiffres → libellé).
NAF_DIVISIONS: dict[str, str] = {
    "01": "Culture et production animale, chasse et services annexes",
    "02": "Sylviculture et exploitation forestière",
    "03": "Pêche et aquaculture",
    "05": "Extraction de houille et de lignite",
    "06": "Extraction d'hydrocarbures",
    "07": "Extraction de minerais métalliques",
    "08": "Autres industries extractives",
    "09": "Services de soutien aux industries extractives",
    "10": "Industries alimentaires",
    "11": "Fabrication de boissons",
    "12": "Fabrication de produits à base de tabac",
    "13": "Fabrication de textiles",
    "14": "Industrie de l'habillement",
    "15": "Industrie du cuir et de la chaussure",
    "16": "Travail du bois et fabrication d'articles en bois et en liège",
    "17": "Industrie du papier et du carton",
    "18": "Imprimerie et reproduction d'enregistrements",
    "19": "Cokéfaction et raffinage",
    "20": "Industrie chimique",
    "21": "Industrie pharmaceutique",
    "22": "Fabrication de produits en caoutchouc et en plastique",
    "23": "Fabrication d'autres produits minéraux non métalliques",
    "24": "Métallurgie",
    "25": "Fabrication de produits métalliques, sauf machines et équipements",
    "26": "Fabrication de produits informatiques, électroniques et optiques",
    "27": "Fabrication d'équipements électriques",
    "28": "Fabrication de machines et équipements n.c.a.",
    "29": "Industrie automobile",
    "30": "Fabrication d'autres matériels de transport",
    "31": "Fabrication de meubles",
    "32": "Autres industries manufacturières",
    "33": "Réparation et installation de machines et d'équipements",
    "35": "Production et distribution d'électricité, de gaz, de vapeur et d'air conditionné",
    "36": "Captage, traitement et distribution d'eau",
    "37": "Collecte et traitement des eaux usées",
    "38": "Collecte, traitement et élimination des déchets ; récupération",
    "39": "Dépollution et autres services de gestion des déchets",
    "41": "Construction de bâtiments",
    "42": "Génie civil",
    "43": "Travaux de construction spécialisés",
    "45": "Commerce et réparation d'automobiles et de motocycles",
    "46": "Commerce de gros, à l'exception des automobiles et des motocycles",
    "47": "Commerce de détail, à l'exception des automobiles et des motocycles",
    "49": "Transports terrestres et transport par conduites",
    "50": "Transports par eau",
    "51": "Transports aériens",
    "52": "Entreposage et services auxiliaires des transports",
    "53": "Activités de poste et de courrier",
    "55": "Hébergement",
    "56": "Restauration",
    "58": "Édition",
    "59": "Production de films cinématographiques, de vidéo et de programmes de télévision",
    "60": "Programmation et diffusion",
    "61": "Télécommunications",
    "62": "Programmation, conseil et autres activités informatiques",
    "63": "Services d'information",
    "64": "Activités des services financiers, hors assurance et caisses de retraite",
    "65": "Assurance",
    "66": "Activités auxiliaires de services financiers et d'assurance",
    "68": "Activités immobilières",
    "69": "Activités juridiques et comptables",
    "70": "Activités des sièges sociaux ; conseil de gestion",
    "71": "Activités d'architecture et d'ingénierie ; contrôle et analyses techniques",
    "72": "Recherche-développement scientifique",
    "73": "Publicité et études de marché",
    "74": "Autres activités spécialisées, scientifiques et techniques",
    "75": "Activités vétérinaires",
    "77": "Activités de location et location-bail",
    "78": "Activités liées à l'emploi",
    "79": "Activités des agences de voyage, voyagistes et services de réservation",
    "80": "Enquêtes et sécurité",
    "81": "Services relatifs aux bâtiments et aménagement paysager",
    "82": "Activités administratives et autres activités de soutien aux entreprises",
    "84": "Administration publique et défense ; sécurité sociale obligatoire",
    "85": "Enseignement",
    "86": "Activités pour la santé humaine",
    "87": "Hébergement médico-social et social",
    "88": "Action sociale sans hébergement",
    "90": "Activités créatives, artistiques et de spectacle",
    "91": "Bibliothèques, archives, musées et autres activités culturelles",
    "92": "Organisation de jeux de hasard et d'argent",
    "93": "Activités sportives, récréatives et de loisirs",
    "94": "Activités des organisations associatives",
    "95": "Réparation d'ordinateurs et de biens personnels et domestiques",
    "96": "Autres services personnels",
    "97": "Activités des ménages en tant qu'employeurs de personnel domestique",
    "98": "Activités indifférenciées des ménages en tant que producteurs",
    "99": "Activités des organisations et organismes extraterritoriaux",
}


def libelle_naf_pour_code(code_naf: str | None) -> str | None:
    """Renvoie le libellé de la division NAF d'un code, ou None si introuvable.

    Tolère les formats ``10``, ``10.13A``, ``1013A`` (on lit les 2 premiers
    chiffres). Repli local quand l'API ne fournit pas le libellé.
    """
    if not code_naf:
        return None
    chiffres = "".join(c for c in code_naf if c.isdigit())
    if len(chiffres) < 2:
        return None
    return NAF_DIVISIONS.get(chiffres[:2])


# ─────────────────────────────────────────────────────────────────────────────
# Sections NAF rev. 2 — bornes de divisions (int) → lettre A..U.
# Utile pour la découverte SIRENE-first : l'API recherche-entreprises ne filtre
# pas sur les divisions/préfixes NAF (« 10 », « 70.10 ») via activite_principale,
# seulement sur des codes APE complets ; on élargit alors à la section.
# Source : nomenclature NAF rev. 2 (INSEE).
# ─────────────────────────────────────────────────────────────────────────────
_SECTIONS_RANGES: tuple[tuple[int, int, str], ...] = (
    (1, 3, "A"), (5, 9, "B"), (10, 33, "C"), (35, 35, "D"), (36, 39, "E"),
    (41, 43, "F"), (45, 47, "G"), (49, 53, "H"), (55, 56, "I"), (58, 63, "J"),
    (64, 66, "K"), (68, 68, "L"), (69, 75, "M"), (77, 82, "N"), (84, 84, "O"),
    (85, 85, "P"), (86, 88, "Q"), (90, 93, "R"), (94, 96, "S"), (97, 98, "T"),
    (99, 99, "U"),
)

# Code APE complet : 2 chiffres + 2 chiffres + 1 lettre (ex « 25.11Z », « 2511Z »).
_RE_APE_COMPLET = re.compile(r"^\d{2}\.?\d{2}[A-Za-z]$")


def est_code_ape_complet(code: str | None) -> bool:
    """True si `code` est un code APE complet (« 25.11Z »), pas un préfixe.

    Les divisions/classes (« 25 », « 70.10 », « 6820 ») renvoient False : elles
    ne sont pas acceptées par l'API en `activite_principale`.
    """
    return bool(code and _RE_APE_COMPLET.match(code.strip()))


def section_pour_code(code: str | None) -> str | None:
    """Section NAF (lettre A–U) couvrant un code/préfixe, via sa division."""
    if not code:
        return None
    chiffres = "".join(c for c in code if c.isdigit())
    if len(chiffres) < 2:
        return None
    n = int(chiffres[:2])
    for lo, hi, lettre in _SECTIONS_RANGES:
        if lo <= n <= hi:
            return lettre
    return None


def sections_pour_codes(codes: list[str]) -> list[str]:
    """Sections NAF distinctes (triées) couvrant une liste de codes/préfixes."""
    sections = {s for c in codes if (s := section_pour_code(c))}
    return sorted(sections)


__all__ = [
    "NAF_DIVISIONS",
    "est_code_ape_complet",
    "libelle_naf_pour_code",
    "section_pour_code",
    "sections_pour_codes",
]
