"""Référentiel : enseignes/chaînes connues à flaguer.

Pour ces établissements, on n'enrichit pas les patterns nominatifs car
le décideur d'achat est au siège, pas sur le lieu local.

Version 0.2.1 — élargie suite au diagnostic des cas non détectés
(NH Hotels, Marriott brands, Choice Hotels, aparthotels, résidences services...).
"""

from __future__ import annotations

# Liste de mots-clés (en minuscules) qui, si présents dans le nom,
# indiquent que l'établissement appartient à une chaîne nationale/internationale.
ENSEIGNES_CHAINES: dict[str, str] = {
    # ════════════════════════════════════════════════════════════════
    # HÔTELLERIE
    # ════════════════════════════════════════════════════════════════

    # Groupe Accor
    "ibis": "Groupe Accor",
    "ibis budget": "Groupe Accor",
    "ibis styles": "Groupe Accor",
    "novotel": "Groupe Accor",
    "mercure": "Groupe Accor",
    "sofitel": "Groupe Accor",
    "pullman": "Groupe Accor",
    "adagio": "Groupe Accor",
    "aparthotel adagio": "Groupe Accor",
    "mgallery": "Groupe Accor",
    "swissôtel": "Groupe Accor",
    "swissotel": "Groupe Accor",
    "raffles": "Groupe Accor",
    "fairmont": "Groupe Accor",
    "thalassa": "Groupe Accor",
    "hotelf1": "Groupe Accor",
    "hôtelf1": "Groupe Accor",
    "f1": "Groupe Accor (à vérifier)",  # ambigu

    # Marriott International (toutes marques)
    "marriott": "Marriott International",
    "ac hotel": "Marriott International (AC Hotels)",
    "courtyard": "Marriott International (Courtyard)",
    "residence inn": "Marriott International (Residence Inn)",
    "moxy": "Marriott International (Moxy)",
    "aloft": "Marriott International (Aloft)",
    "renaissance hotel": "Marriott International (Renaissance)",
    "le méridien": "Marriott International (Le Méridien)",
    "le meridien": "Marriott International (Le Méridien)",
    "westin": "Marriott International (Westin)",
    "sheraton": "Marriott International (Sheraton)",
    "ritz-carlton": "Marriott International (Ritz-Carlton)",
    "ritz carlton": "Marriott International (Ritz-Carlton)",
    "w hotel": "Marriott International (W Hotels)",
    "st. regis": "Marriott International (St. Regis)",
    "st regis": "Marriott International (St. Regis)",

    # Hilton Worldwide
    "hilton": "Hilton Worldwide",
    "hilton garden inn": "Hilton Worldwide",
    "hampton by hilton": "Hilton Worldwide",
    "doubletree": "Hilton Worldwide",
    "double tree": "Hilton Worldwide",
    "embassy suites": "Hilton Worldwide",
    "waldorf astoria": "Hilton Worldwide",
    "conrad": "Hilton Worldwide (Conrad)",
    "canopy": "Hilton Worldwide (Canopy)",

    # InterContinental Hotels Group (IHG)
    "intercontinental": "IHG (InterContinental)",
    "holiday inn": "IHG (Holiday Inn)",
    "holiday inn express": "IHG (Holiday Inn Express)",
    "crowne plaza": "IHG (Crowne Plaza)",
    "kimpton": "IHG (Kimpton)",
    "indigo": "IHG (Hotel Indigo)",
    "voco": "IHG (voco)",

    # Hyatt
    "hyatt": "Hyatt Hotels Corporation",
    "hyatt regency": "Hyatt Hotels Corporation",
    "andaz": "Hyatt Hotels Corporation (Andaz)",
    "park hyatt": "Hyatt Hotels Corporation",
    "grand hyatt": "Hyatt Hotels Corporation",

    # Wyndham
    "wyndham": "Wyndham Hotels & Resorts",
    "ramada": "Wyndham Hotels & Resorts",
    "days inn": "Wyndham Hotels & Resorts",
    "super 8": "Wyndham Hotels & Resorts",
    "tryp": "Wyndham Hotels & Resorts",

    # Choice Hotels
    "comfort": "Choice Hotels",
    "comfort inn": "Choice Hotels",
    "comfort hotel": "Choice Hotels",
    "comfort suites": "Choice Hotels",
    "comfort aparthotel": "Choice Hotels",
    "quality inn": "Choice Hotels",
    "quality hotel": "Choice Hotels",
    "clarion": "Choice Hotels",
    "econo lodge": "Choice Hotels",
    "sleep inn": "Choice Hotels",

    # NH Hotel Group
    "nh hotel": "NH Hotel Group",
    "nh collection": "NH Hotel Group",
    "nhow": "NH Hotel Group",
    "nh ": "NH Hotel Group",  # début avec NH suivi d'espace

    # Best Western
    "best western": "Best Western International",
    "best western plus": "Best Western International",
    "best western premier": "Best Western International",

    # Louvre Hotels Group
    "campanile": "Groupe Louvre Hotels",
    "kyriad": "Groupe Louvre Hotels",
    "kyriad prestige": "Groupe Louvre Hotels",
    "première classe": "Groupe Louvre Hotels",
    "premiere classe": "Groupe Louvre Hotels",
    "tulip inn": "Groupe Louvre Hotels",
    "golden tulip": "Groupe Louvre Hotels",

    # B&B Hotels
    "b&b hôtel": "B&B Hotels",
    "b&b hotel": "B&B Hotels",
    "b et b hotel": "B&B Hotels",

    # Aparthotels et résidences hôtelières
    "appart'city": "Appart'City",
    "appart city": "Appart'City",
    "staycity": "Staycity Aparthotels",
    "citadines": "The Ascott Limited (Citadines)",
    "ascott": "The Ascott Limited",
    "all suites": "All Suites Appart Hotel",
    "résidhome": "Réside Études (Résidhome)",
    "residhome": "Réside Études (Résidhome)",

    # Résidences services seniors
    "domitys": "Domitys",
    "les girandières": "Senioriales / Girandières",
    "girandières": "Senioriales / Girandières",
    "girandieres": "Senioriales / Girandières",
    "medicis": "Médicis Résidences (à vérifier)",
    "les jardins d'arcadie": "Les Jardins d'Arcadie",
    "jardins d'arcadie": "Les Jardins d'Arcadie",
    "espace & vie": "Espace et Vie",
    "ovelia": "Ovelia",
    "senioriales": "Senioriales",
    "cogedim club": "Cogedim Club",
    "villavie": "Villavie",
    "villavita": "Villavita",

    # Auberges / autres marques hôtelières
    "première classe": "Groupe Louvre Hotels",
    "fasthotel": "Fasthôtel",
    "ace hotel": "Ace Hôtel France",
    "p'tit dej hotel": "P'tit Dej Hôtel",
    "kyriad direct": "Groupe Louvre Hotels",
    "balladins": "Balladins",
    "the originals": "The Originals Hotels",
    "logis hotels": "Logis Hôtels",

    # ════════════════════════════════════════════════════════════════
    # GRANDE DISTRIBUTION (alimentaire)
    # ════════════════════════════════════════════════════════════════

    # Carrefour
    "carrefour": "Groupe Carrefour",
    "carrefour market": "Groupe Carrefour",
    "carrefour city": "Groupe Carrefour",
    "carrefour express": "Groupe Carrefour",
    "carrefour contact": "Groupe Carrefour",
    "carrefour voyages": "Groupe Carrefour (Voyages)",

    # Auchan
    "auchan": "Groupe Auchan",
    "auchan supermarché": "Groupe Auchan",
    "auchan drive": "Groupe Auchan",

    # E.Leclerc
    "leclerc": "E.Leclerc",
    "e.leclerc": "E.Leclerc",
    "e leclerc": "E.Leclerc",

    # Mousquetaires
    "intermarche": "Les Mousquetaires (Intermarché)",
    "intermarché": "Les Mousquetaires (Intermarché)",
    "netto": "Les Mousquetaires (Netto)",
    "bricomarché": "Les Mousquetaires (Bricomarché)",
    "bricomarche": "Les Mousquetaires (Bricomarché)",

    # Casino
    "casino supermarché": "Groupe Casino",
    "géant casino": "Groupe Casino",
    "geant casino": "Groupe Casino",
    "monoprix": "Monoprix (Casino)",
    "franprix": "Franprix (Casino)",
    "naturalia": "Naturalia (Monoprix)",
    "casino shop": "Groupe Casino",
    "petit casino": "Groupe Casino",
    "spar": "Groupe Casino (Spar)",
    "vival": "Groupe Casino (Vival)",

    # Autres distributeurs
    "lidl": "Lidl France",
    "aldi": "Aldi France",
    "biocoop": "Biocoop",
    "super u": "Système U",
    "hyper u": "Système U",
    "u express": "Système U",
    "marché u": "Système U",
    "naturhouse": "NaturHouse",
    "picard": "Picard Surgelés",
    "grand frais": "Grand Frais",

    # ════════════════════════════════════════════════════════════════
    # SANTÉ — Cliniques privées (chaînes)
    # ════════════════════════════════════════════════════════════════

    "ramsay": "Ramsay Santé",
    "ramsay santé": "Ramsay Santé",
    "ramsay sante": "Ramsay Santé",
    "elsan": "Groupe Elsan",
    "vivalto": "Vivalto Santé",
    "almaviva": "Almaviva Santé",
    "korian": "Korian (santé)",
    "orpea": "Orpea (santé)",

    # ════════════════════════════════════════════════════════════════
    # AUTOMOBILE / Services
    # ════════════════════════════════════════════════════════════════

    "norauto": "Mobivia (Norauto)",
    "feu vert": "Feu Vert",
    "midas": "Midas France",
    "speedy": "Speedy France",
    "euromaster": "Euromaster",
    "point s": "Point S",

    # ════════════════════════════════════════════════════════════════
    # RESTAURATION (chaînes avec parking)
    # ════════════════════════════════════════════════════════════════

    "mcdonald": "McDonald's France",
    "mcdo": "McDonald's France",
    "burger king": "Burger King France",
    "kfc": "KFC France",
    "subway": "Subway France",
    "buffalo grill": "Buffalo Grill",
    "courtepaille": "Courtepaille",
    "la mie câline": "La Mie Câline",
    "la mie caline": "La Mie Câline",
    "paul": "Groupe Holder (Paul)",
    "brioche dorée": "Brioche Dorée",
    "brioche doree": "Brioche Dorée",
    "starbucks": "Starbucks France",
    "domino's": "Domino's Pizza France",
    "dominos pizza": "Domino's Pizza France",
    "pizza hut": "Pizza Hut France",
    "léon de bruxelles": "Léon de Bruxelles",
    "leon de bruxelles": "Léon de Bruxelles",
    "del arte": "Del Arte (Le Duff)",
    "hippopotamus": "Hippopotamus",
    "le bistro": "à vérifier",
    "flunch": "Flunch",
    "crescendo": "Crescendo Restauration",
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

    # On boucle dans l'ordre du dict (Python 3.7+ préserve l'ordre)
    # → les keywords plus spécifiques (ex: "ibis budget") matchent avant
    #   les plus génériques (ex: "ibis"). Ici l'ordre du dict reflète
    #   les groupes par taille (Accor d'abord, etc.) — on garde la logique
    #   de match "première occurrence trouvée".

    # Tri pour matcher d'abord les keywords les plus longs (plus spécifiques)
    keywords_ordonnes = sorted(ENSEIGNES_CHAINES.keys(), key=len, reverse=True)

    for keyword in keywords_ordonnes:
        groupe = ENSEIGNES_CHAINES[keyword]
        # Match avec word boundary basique :
        # - keyword entouré d'espaces dans le nom (ex: " ibis ")
        # - OU keyword en début de nom suivi d'espace (ex: "ibis ...")
        # - OU keyword en fin de nom précédé d'espace (ex: "... ibis")
        # - OU le nom == keyword exactement (rare mais possible)
        if (
            f" {keyword} " in f" {nom_lower} "
            or nom_lower.startswith(keyword + " ")
            or nom_lower.endswith(" " + keyword)
            or nom_lower == keyword
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
