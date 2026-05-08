"""Référentiel : enseignes/chaînes connues à flaguer.

Pour ces établissements, on n'enrichit pas les patterns nominatifs car
le décideur d'achat est au siège, pas sur le lieu local.
"""

from __future__ import annotations

# Liste de mots-clés (en minuscules) qui, si présents dans le nom,
# indiquent que l'établissement appartient à une chaîne nationale/internationale.
ENSEIGNES_CHAINES: dict[str, str] = {
    # Hôtellerie — groupe Accor
    "ibis": "Groupe Accor",
    "novotel": "Groupe Accor",
    "mercure": "Groupe Accor",
    "sofitel": "Groupe Accor",
    "pullman": "Groupe Accor",
    "adagio": "Groupe Accor",
    # Hôtellerie — autres
    "campanile": "Groupe Louvre Hotels",
    "kyriad": "Groupe Louvre Hotels",
    "première classe": "Groupe Louvre Hotels",
    "premiere classe": "Groupe Louvre Hotels",
    "best western": "Best Western International",
    "holiday inn": "InterContinental Hotels Group",
    "marriott": "Marriott International",
    "hilton": "Hilton Worldwide",
    "ibis budget": "Groupe Accor",
    "b&b hôtel": "B&B Hotels",
    "b&b hotel": "B&B Hotels",
    # Grande distribution
    "carrefour": "Groupe Carrefour",
    "auchan": "Groupe Auchan",
    "leclerc": "E.Leclerc",
    "intermarche": "Les Mousquetaires (Intermarché)",
    "intermarché": "Les Mousquetaires (Intermarché)",
    "casino": "Groupe Casino",
    "monoprix": "Monoprix (Casino)",
    "franprix": "Franprix (Casino)",
    "lidl": "Lidl France",
    "aldi": "Aldi France",
    "biocoop": "Biocoop",
    "naturalia": "Naturalia (Monoprix)",
    "super u": "Système U",
    "hyper u": "Système U",
    "u express": "Système U",
    # Cliniques (chaînes)
    "ramsay": "Ramsay Santé",
    "elsan": "Groupe Elsan",
    "vivalto": "Vivalto Santé",
    "almaviva": "Almaviva Santé",
    # Auto / services
    "norauto": "Mobivia (Norauto)",
    "feu vert": "Feu Vert",
    "midas": "Midas France",
    "speedy": "Speedy France",
    "euromaster": "Euromaster",
    # Restauration (parking visible)
    "mcdonald": "McDonald's France",
    "burger king": "Burger King France",
    "kfc": "KFC France",
    "subway": "Subway France",
    "buffalo grill": "Buffalo Grill",
    "courtepaille": "Courtepaille",
    "la mie câline": "La Mie Câline",
    "la mie caline": "La Mie Câline",
    "paul": "Groupe Holder (Paul)",
}


def detecter_chaine(nom_etablissement: str) -> tuple[bool, str | None]:
    """Détecte si un nom d'établissement appartient à une chaîne connue.

    Args:
        nom_etablissement: nom du lead (ex: "Hôtel Ibis Marseille Est")

    Returns:
        (est_chaine, nom_groupe). nom_groupe vaut None si pas une chaîne.
    """
    if not nom_etablissement:
        return False, None
    nom_lower = nom_etablissement.lower()
    for keyword, groupe in ENSEIGNES_CHAINES.items():
        # Match en mot complet (avec word boundary basique)
        if (
            f" {keyword} " in f" {nom_lower} "
            or nom_lower.startswith(keyword + " ")
            or nom_lower.endswith(" " + keyword)
        ):
            return True, groupe
    return False, None


def note_chaine_standard() -> str:
    """Note standard à inscrire pour les leads chaîne."""
    return (
        "Lead appartenant à une chaîne nationale/internationale. "
        "Le décideur d'achat se trouve au siège du groupe, pas sur ce site local. "
        "À enrichir manuellement via : LinkedIn (cherche \"Directeur Achats\" + nom du groupe), "
        "ou via le site du groupe pour identifier le contact \"Développement\" / \"Immobilier\"."
    )
