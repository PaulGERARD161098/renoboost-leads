"""Phase C — résolution géographique parking → SIREN exploitant.

Quand une ligne d'inventaire ne porte ni enseigne (nom/raison_sociale) ni SIREN
mais des coordonnées (latitude/longitude), on interroge l'endpoint `near_point`
de recherche-entreprises (gratuit) pour retrouver l'établissement exploitant le
plus probable dans un petit rayon, puis on enrichit la ligne (raison_sociale +
SIREN). Le pipeline L2/L3/L4 existant prend ensuite le relais normalement.

Heuristique de choix : parmi les entreprises trouvées autour du point, on retient
celle dont le SIÈGE est le plus proche du parking ; à défaut, le premier résultat
renvoyé par l'API (trié par pertinence/distance). On privilégie un établissement
« ancre » plausible (grand effectif) quand l'info est disponible.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..common.logger import get_logger
from .models import LigneParking

logger = get_logger(__name__)


class _ClientNearPoint(Protocol):
    """Sous-ensemble de RechercheEntreprisesClient utilisé ici (duck typing)."""

    def decouvrir_near_point(
        self, latitude: float, longitude: float, radius_km: float, **kwargs: Any
    ) -> Any: ...


def ligne_a_resoudre(ligne: LigneParking) -> bool:
    """True si la ligne n'a aucune identité exploitable mais a des coordonnées."""
    a_identite = bool(ligne.siren or ligne.raison_sociale or ligne.nom)
    a_coords = ligne.latitude is not None and ligne.longitude is not None
    return (not a_identite) and a_coords


def _tranche_effectif_rang(entreprise: dict[str, Any]) -> int:
    """Rang grossier de la tranche d'effectif INSEE (plus grand = plus gros)."""
    tranche = entreprise.get("tranche_effectif_salarie")
    try:
        return int(tranche) if tranche is not None else -1
    except (TypeError, ValueError):
        return -1


def _cle_tri_candidat(entreprise: dict[str, Any]) -> tuple[int, str]:
    """Clé de tri DÉTERMINISTE : effectif décroissant, puis SIREN croissant.

    Le SIREN départage les ex-aequo. Sans lui, `max`/un tri instable rendait
    l'issue dépendante de l'ordre (non garanti) renvoyé par l'API : un même
    point pouvait résoudre vers un SIREN — donc un NAF — différent d'un run à
    l'autre, et faire basculer le lead hors-filtre. Dégradation silencieuse.
    """
    return (-_tranche_effectif_rang(entreprise), str(entreprise.get("siren") or ""))


def _choisir_exploitant(candidats: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choisit l'entreprise exploitante la plus probable parmi les candidats.

    Un seul candidat → on le retient. Plusieurs → tri déterministe par effectif
    décroissant (une ancre — hyper, foncière — est plus plausible qu'une micro-
    boutique voisine), SIREN croissant pour départager.

    Garde-fou confiance : avec plusieurs candidats, on n'attribue un SIREN que si
    le meilleur a un effectif CONNU (ancre plausible). Si aucun n'a d'effectif
    renseigné, le choix relèverait du pur hasard entre voisins → on laisse le
    parking NON résolu plutôt que de poser un SIREN faux (un SIREN manquant est
    honnête ; un SIREN erroné corrompt le NAF et le filtrage en silence).
    """
    if not candidats:
        return None
    if len(candidats) == 1:
        return candidats[0]
    meilleur = min(candidats, key=_cle_tri_candidat)
    if _tranche_effectif_rang(meilleur) < 0:
        return None
    return meilleur


def resoudre_siren_geo(
    ligne: LigneParking,
    client: _ClientNearPoint,
    *,
    rayon_km: float = 0.2,
    max_candidats: int = 5,
) -> tuple[str | None, str | None]:
    """Tente de retrouver (siren, nom) de l'exploitant d'un parking par géoloc.

    Renvoie (None, None) si pas de coordonnées ou aucun candidat trouvé.
    """
    if ligne.latitude is None or ligne.longitude is None:
        return None, None

    candidats = list(
        client.decouvrir_near_point(
            latitude=ligne.latitude,
            longitude=ligne.longitude,
            radius_km=rayon_km,
            etat_administratif="A",
            siege_only=False,
            max_results=max_candidats,
        )
    )
    exploitant = _choisir_exploitant(candidats)
    if exploitant is None:
        return None, None

    siren = exploitant.get("siren")
    nom = exploitant.get("nom_complet") or exploitant.get("nom_raison_sociale")
    return siren, nom


def resoudre_lignes_sans_enseigne(
    lignes: list[LigneParking],
    client: _ClientNearPoint,
    *,
    rayon_km: float = 0.2,
    max_candidats: int = 5,
) -> dict[str, int]:
    """Enrichit en place les lignes sans identité via la géoloc (Phase C).

    Mutation : pose `siren` et `raison_sociale` sur les lignes résolues, ce qui
    suffit pour que l'enrichissement L2 retrouve l'entreprise.

    Returns:
        Stats {tente, resolu} pour le récapitulatif du run.
    """
    stats = {"tente": 0, "resolu": 0}
    for ligne in lignes:
        if not ligne_a_resoudre(ligne):
            continue
        stats["tente"] += 1
        siren, nom = resoudre_siren_geo(
            ligne, client, rayon_km=rayon_km, max_candidats=max_candidats
        )
        if not (siren or nom):
            continue
        if siren:
            ligne.siren = siren
        if nom:
            ligne.raison_sociale = nom
        stats["resolu"] += 1
        logger.info(
            "Phase C : parking %s résolu par géoloc → %s (SIREN %s)",
            ligne.identifiant_stable(),
            nom or "?",
            siren or "?",
        )
    if stats["tente"]:
        logger.info(
            "Phase C terminée : %d/%d parkings sans enseigne résolus par géoloc",
            stats["resolu"],
            stats["tente"],
        )
    return stats


__all__ = [
    "ligne_a_resoudre",
    "resoudre_siren_geo",
    "resoudre_lignes_sans_enseigne",
]
