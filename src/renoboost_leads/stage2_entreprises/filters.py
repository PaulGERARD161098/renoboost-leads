"""Filtres entreprise — appliqués entre L2 et L3 (Bloc 3).

Stratégie : on flag les leads qui ne passent pas les filtres au lieu de les
rejeter. L3 (scraping/patterns) tourne sur tous les leads, l'export sépare
ensuite les qualifiés des flagués pour éviter le mélange.

Filtres supportés :
- effectif (min/max ou codes tranche INSEE bruts)
- NAF (préfixe libre, inclus + exclus)
- forme juridique (labels SAS/SARL... ou codes INSEE)
- chiffre d'affaires (ca_min/ca_max, source API gouv `finances`)
- catégorie entreprise (PME/ETI/GE)
- multi_sites_only (nb_etablissements > 1)
"""

from __future__ import annotations

from ..models import FiltresEntreprise, LeadStage2

# ─────────────────────────────────────────────────────────────────────────────
# Mappings INSEE
# ─────────────────────────────────────────────────────────────────────────────

# Tranches d'effectif salarié INSEE — code → (min_inclusif, max_inclusif | None)
# Source : https://www.insee.fr/fr/information/2028417
_TRANCHES_INSEE: dict[str, tuple[int, int | None]] = {
    "00": (0, 0),
    "01": (1, 2),
    "02": (3, 5),
    "03": (6, 9),
    "11": (10, 19),
    "12": (20, 49),
    "21": (50, 99),
    "22": (100, 199),
    "31": (200, 249),
    "32": (250, 499),
    "41": (500, 999),
    "42": (1000, 1999),
    "51": (2000, 4999),
    "52": (5000, 9999),
    "53": (10000, None),
}

# Labels → codes nature juridique INSEE (sous-ensemble utile en B2B)
# Source : https://www.insee.fr/fr/information/2028129
_LABELS_FORME_JURIDIQUE: dict[str, set[str]] = {
    "SAS": {"5710"},
    "SASU": {"5720"},
    "SARL": {"5499", "5498", "5485", "5410"},
    "SA": {"5510", "5515", "5520", "5530", "5540", "5550", "5560", "5570", "5585"},
    "SCI": {"6540"},
    "SNC": {"5202", "5203"},
    "SE": {"5306"},
    "EI": {"1000"},
    "EIRL": {"1100"},
    "EURL": {"5498"},
    "AUTOENTREPRENEUR": {"1000"},
    "ASSOCIATION": {"9220", "9230", "9210", "9240", "9260"},
    "COOPERATIVE": {"5599", "5485"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de résolution
# ─────────────────────────────────────────────────────────────────────────────


def _tranche_overlap_range(
    tranche_code: str, effectif_min: int | None, effectif_max: int | None
) -> bool:
    """Vrai si la tranche INSEE intersecte la plage [effectif_min, effectif_max]."""
    bornes = _TRANCHES_INSEE.get(tranche_code)
    if bornes is None:
        return False
    t_min, t_max = bornes
    if effectif_min is not None:
        tranche_haut = t_max if t_max is not None else effectif_min
        if tranche_haut < effectif_min:
            return False
    if effectif_max is not None and t_min > effectif_max:
        return False
    return True


def _resoudre_codes_formes(items: list[str]) -> set[str]:
    """Convertit une liste mixte (labels et/ou codes) en set de codes INSEE.

    Un item est traité comme un code s'il est tout numérique, sinon comme
    un label (case-insensitive).
    """
    codes: set[str] = set()
    for item in items:
        if not item:
            continue
        cleaned = item.strip()
        if cleaned.isdigit():
            codes.add(cleaned)
        else:
            label_codes = _LABELS_FORME_JURIDIQUE.get(cleaned.upper())
            if label_codes:
                codes.update(label_codes)
    return codes


def _match_naf_prefixe(code_naf: str | None, prefixes: list[str]) -> bool:
    """Vrai si `code_naf` commence par l'un des préfixes."""
    if not code_naf or not prefixes:
        return False
    for p in prefixes:
        if p and code_naf.startswith(p):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Évaluation des filtres
# ─────────────────────────────────────────────────────────────────────────────


def _verifier_effectif(lead: LeadStage2, filtres: FiltresEntreprise) -> str | None:
    """Renvoie une raison de rejet, ou None si OK."""
    tranche = lead.tranche_effectif

    # Priorité aux codes explicites
    if filtres.tranche_effectif_inclus:
        if tranche is None:
            return "effectif inconnu" if filtres.rejeter_effectif_inconnu else None
        if tranche not in filtres.tranche_effectif_inclus:
            return f"tranche_effectif={tranche} pas dans {filtres.tranche_effectif_inclus}"
        return None

    # Sinon min/max user-friendly
    if filtres.effectif_min is None and filtres.effectif_max is None:
        return None
    if tranche is None:
        return "effectif inconnu" if filtres.rejeter_effectif_inconnu else None
    if not _tranche_overlap_range(tranche, filtres.effectif_min, filtres.effectif_max):
        bornes = _TRANCHES_INSEE.get(tranche, ("?", "?"))
        return (
            f"effectif tranche={tranche} ({bornes[0]}-{bornes[1]}) "
            f"hors [{filtres.effectif_min},{filtres.effectif_max}]"
        )
    return None


def _verifier_naf(lead: LeadStage2, filtres: FiltresEntreprise) -> str | None:
    code = lead.code_naf
    if filtres.naf_inclus and not _match_naf_prefixe(code, filtres.naf_inclus):
        return f"naf={code} pas dans {filtres.naf_inclus}"
    if filtres.naf_exclus and _match_naf_prefixe(code, filtres.naf_exclus):
        return f"naf={code} exclu par {filtres.naf_exclus}"
    return None


def _verifier_forme_juridique(lead: LeadStage2, filtres: FiltresEntreprise) -> str | None:
    if not filtres.forme_juridique_inclus and not filtres.forme_juridique_exclus:
        return None
    code = lead.forme_juridique
    if filtres.forme_juridique_inclus:
        codes_ok = _resoudre_codes_formes(filtres.forme_juridique_inclus)
        if code is None or code not in codes_ok:
            return f"forme={code} pas dans {filtres.forme_juridique_inclus}"
    if filtres.forme_juridique_exclus and code is not None:
        codes_ko = _resoudre_codes_formes(filtres.forme_juridique_exclus)
        if code in codes_ko:
            return f"forme={code} exclue par {filtres.forme_juridique_exclus}"
    return None


def _verifier_ca(lead: LeadStage2, filtres: FiltresEntreprise) -> str | None:
    if filtres.ca_min is None and filtres.ca_max is None:
        return None
    ca = lead.chiffre_affaires
    if ca is None:
        return "CA inconnu" if filtres.rejeter_ca_inconnu else None
    if filtres.ca_min is not None and ca < filtres.ca_min:
        return f"CA={ca} < min {filtres.ca_min}"
    if filtres.ca_max is not None and ca > filtres.ca_max:
        return f"CA={ca} > max {filtres.ca_max}"
    return None


def _verifier_categorie(lead: LeadStage2, filtres: FiltresEntreprise) -> str | None:
    if not filtres.categorie_entreprise_inclus:
        return None
    cat = lead.categorie_entreprise
    if cat is None:
        return None  # catégorie inconnue → on n'évince pas (cohérent CA)
    autorisees = {c.upper() for c in filtres.categorie_entreprise_inclus}
    if cat.upper() not in autorisees:
        return f"catégorie={cat} pas dans {filtres.categorie_entreprise_inclus}"
    return None


def _verifier_multi_sites(lead: LeadStage2, filtres: FiltresEntreprise) -> str | None:
    if not filtres.multi_sites_only:
        return None
    nb = lead.nb_etablissements
    if nb is None:
        return "nb_etablissements inconnu"
    if nb <= 1:
        return f"mono-site (nb_etablissements={nb})"
    return None


def evaluer_filtres_entreprise(lead: LeadStage2, filtres: FiltresEntreprise) -> tuple[bool, str]:
    """Évalue tous les filtres entreprise sur un lead L2.

    Returns:
        (passe, raison)
        - passe=True si le lead satisfait tous les filtres actifs
        - raison : chaîne agrégée des motifs de rejet (vide si passe)
    """
    raisons: list[str] = []
    for check in (
        _verifier_effectif,
        _verifier_naf,
        _verifier_forme_juridique,
        _verifier_ca,
        _verifier_categorie,
        _verifier_multi_sites,
    ):
        r = check(lead, filtres)
        if r:
            raisons.append(r)
    if raisons:
        return False, " ; ".join(raisons)
    return True, ""
