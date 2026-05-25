"""Mapping : résultat API recherche-entreprises → champs LeadStage2."""

from __future__ import annotations

from typing import Any


def _safe_get(d: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def extraire_dirigeant_principal(
    candidat: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Extrait (nom, prenom, qualité) du dirigeant principal.

    L'API peut renvoyer une liste `dirigeants` avec différentes structures.
    On prend le premier ayant une qualité parlante (gérant, président...).
    """
    dirigeants = candidat.get("dirigeants") or []
    if not dirigeants:
        return None, None, None

    # Priorité aux qualités "président", "gérant", "directeur"
    priorites = ["pr", "gé", "ge", "di"]  # début lowercase

    def _score_qualite(d: dict[str, Any]) -> int:
        q = (d.get("qualite") or "").lower()
        for i, p in enumerate(priorites):
            if q.startswith(p):
                return len(priorites) - i
        return 0

    candidats_tries = sorted(dirigeants, key=_score_qualite, reverse=True)
    chef = candidats_tries[0]

    nom = chef.get("nom") or None
    prenom = chef.get("prenoms") or chef.get("prenom") or None
    qualite = chef.get("qualite") or None

    return (nom, prenom, qualite)


def extraire_adresse_normalisee(candidat: dict[str, Any]) -> str | None:
    """Reconstruit l'adresse normalisée du siège."""
    siege = candidat.get("siege") or {}
    parts = []
    if num := siege.get("numero_voie"):
        parts.append(str(num))
    if voie := siege.get("type_voie"):
        parts.append(str(voie))
    if libelle := siege.get("libelle_voie"):
        parts.append(str(libelle))
    if cp := siege.get("code_postal"):
        parts.append(str(cp))
    if commune := (siege.get("libelle_commune") or siege.get("commune")):
        parts.append(str(commune))
    if not parts:
        return None
    return " ".join(parts).strip()


def _extraire_nb_etablissements(candidat: dict[str, Any]) -> int | None:
    """Extrait le nombre d'établissements de l'unité légale (B3 multi-sites).

    L'API expose deux champs possibles : `nombre_etablissements` (officiel) et
    parfois une liste `matching_etablissements`. On préfère l'entier officiel,
    puis on retombe sur le len de la liste si fourni.
    """
    raw = candidat.get("nombre_etablissements")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    etabs = candidat.get("matching_etablissements")
    if isinstance(etabs, list):
        return len(etabs) or None
    return None


def _extraire_finances(candidat: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
    """Extrait (chiffre_affaires, resultat_net, annee) de l'année la plus récente.

    L'API gouv expose un bloc `finances` indexé par année :
        {"2024": {"ca": 1278355060, "resultat_net": 74398429}, ...}
    Absent pour les sociétés qui ne publient pas leurs comptes (fréquent en PME).
    """
    finances = candidat.get("finances")
    if not isinstance(finances, dict) or not finances:
        return None, None, None
    annees = [a for a in finances if isinstance(finances.get(a), dict)]
    if not annees:
        return None, None, None
    annee = max(annees)  # années au format "YYYY" → tri lexical = chronologique
    bloc = finances[annee]
    ca = bloc.get("ca")
    resultat = bloc.get("resultat_net")
    ca = int(ca) if isinstance(ca, (int, float)) else None
    resultat = int(resultat) if isinstance(resultat, (int, float)) else None
    if ca is None and resultat is None:
        return None, None, None
    return ca, resultat, annee


def candidat_to_l2_fields(candidat: dict[str, Any]) -> dict[str, Any]:
    """Convertit un résultat API en dict de champs L2 prêts à fusionner avec LeadStage1."""
    nom_dir, prenom_dir, qualite_dir = extraire_dirigeant_principal(candidat)
    siege = candidat.get("siege") or {}
    ca, resultat_net, annee_finances = _extraire_finances(candidat)

    return {
        "siren": candidat.get("siren"),
        "siret": _safe_get(siege, "siret") or candidat.get("siret"),
        "code_naf": (
            _safe_get(candidat, "activite_principale") or _safe_get(siege, "activite_principale")
        ),
        "libelle_naf": (
            _safe_get(candidat, "libelle_activite_principale")
            or _safe_get(siege, "libelle_activite_principale")
        ),
        "forme_juridique": candidat.get("nature_juridique"),
        "statut_actif": (candidat.get("etat_administratif") or "").upper() == "A",
        "tranche_effectif": candidat.get("tranche_effectif_salarie"),
        "libelle_effectif": _safe_get(candidat, "libelle_tranche_effectif_salarie"),
        "dirigeant_nom": nom_dir,
        "dirigeant_prenom": prenom_dir,
        "dirigeant_qualite": qualite_dir,
        "adresse_normalisee": extraire_adresse_normalisee(candidat),
        "date_creation": candidat.get("date_creation"),
        "nb_etablissements": _extraire_nb_etablissements(candidat),
        "chiffre_affaires": ca,
        "resultat_net": resultat_net,
        "annee_finances": annee_finances,
        "categorie_entreprise": candidat.get("categorie_entreprise"),
    }
