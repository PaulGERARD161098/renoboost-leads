"""Porte d — Societeinfo comme provider L2 alternatif (au lieu de data.gouv).

Le L2 standard interroge `recherche-entreprises.api.gouv.fr` (gratuit). Ce client
expose la **même interface** (`rechercher(query, code_postal, per_page) -> list[dict]`)
adossée à Societeinfo (registres officiels, meilleur taux de match), de sorte
qu'il s'injecte tel quel dans `EnricheurStage2` (duck typing — aucun changement
du matcher/mapper).

La réponse Societeinfo (un `ResultatSocieteinfo`) est convertie en **dict candidat**
au format data.gouv attendu par `matcher` et `candidat_to_l2_fields` : `siren`,
`nom_complet`, `siege`, `etat_administratif`, `activite_principale`,
`tranche_effectif_salarie`, `dirigeants`, `finances`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..societeinfo_enrichment.client import (
    ResultatSocieteinfo,
    SocieteinfoClient,
    SocieteinfoError,
)


def societeinfo_resultat_to_candidat(
    res: ResultatSocieteinfo,
    *,
    nom: str,
    code_postal: str | None,
) -> dict[str, Any]:
    """Convertit un `ResultatSocieteinfo` en candidat au format data.gouv."""
    dirigeants: list[dict[str, Any]] = []
    if res.dirigeant:
        dirigeants.append({"nom": res.dirigeant, "qualite": "Dirigeant"})

    finances: dict[str, Any] = {}
    if res.chiffre_affaires is not None:
        # Societeinfo donne un CA sans millésime → rattaché à l'année courante.
        finances[str(datetime.now().year)] = {"ca": res.chiffre_affaires}

    return {
        "siren": res.siren,
        # SI ne renvoie pas la raison sociale ; on garde le nom cible (SI a déjà
        # fait le matching), ce qui donne un score nom maximal côté matcher.
        "nom_complet": nom,
        "siege": {
            "code_postal": code_postal,
            "siret": (f"{res.siren}00000" if res.siren else None),
        },
        "etat_administratif": "A",
        "activite_principale": res.naf,
        "libelle_activite_principale": res.libelle_naf,
        "tranche_effectif_salarie": res.effectif,
        "dirigeants": dirigeants,
        "finances": finances,
        "_source_l2": "societeinfo",
    }


class SocieteinfoL2Client:
    """Adaptateur L2 : même interface que `RechercheEntreprisesClient`."""

    def __init__(self, client: SocieteinfoClient):
        self.client = client

    @property
    def cout_total_eur(self) -> float:
        """Coût cumulé engagé par les appels Societeinfo (0 en dry-run)."""
        return self.client.cout_total_eur

    def rechercher(
        self,
        query: str,
        code_postal: str | None = None,
        per_page: int = 10,  # noqa: ARG002 — signature compatible, SI renvoie 1 match
    ) -> list[dict[str, Any]]:
        res = self.client.enrichir(nom=query, code_postal=code_postal)
        if not res.trouve:
            return []
        return [societeinfo_resultat_to_candidat(res, nom=query, code_postal=code_postal)]

    def health_check(self) -> tuple[bool, str]:
        try:
            return self.client.health_check()
        except SocieteinfoError as e:
            return False, str(e)


__all__ = ["SocieteinfoL2Client", "societeinfo_resultat_to_candidat"]
