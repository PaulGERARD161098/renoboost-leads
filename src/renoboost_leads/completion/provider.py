"""Providers de complétion — sources externes interrogées pour combler les trous.

L'étage de complétion est agnostique de la source : il parle à un
`ProviderCompletion` (Protocol). Le 1er provider concret est **Societeinfo**
(`SocieteinfoProvider`), qui réutilise le client défensif déjà construit dans
`societeinfo_enrichment`. D'autres providers (Pappers, Dropcontact…) pourront
implémenter le même protocole sans toucher à l'étage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..common.budget_guard import BudgetGuard
from ..common.rate_limiter import RateLimiter
from ..societeinfo_enrichment.client import (
    SocieteinfoClient,
    SocieteinfoClientConfig,
    SocieteinfoClientDryRun,
)


@dataclass
class ResultatCompletion:
    """Champs normalisés renvoyés par un provider pour un lead.

    Aligné sur les champs de base du pipeline pour un *fill-if-empty* direct.
    """

    siren: str | None = None
    code_naf: str | None = None
    libelle_naf: str | None = None
    tranche_effectif: str | None = None
    chiffre_affaires: int | None = None
    dirigeant_nom: str | None = None
    dirigeant_prenom: str | None = None
    dirigeant_qualite: str | None = None
    emails: list[str] = field(default_factory=list)
    telephone: str | None = None
    site_web: str | None = None
    linkedin: str | None = None
    trouve: bool = False


@runtime_checkable
class ProviderCompletion(Protocol):
    """Contrat minimal d'un provider de complétion."""

    nom: str
    cout_par_lead_eur: float

    def chercher(
        self,
        *,
        nom: str | None = None,
        siren: str | None = None,
        code_postal: str | None = None,
        site_web: str | None = None,
    ) -> ResultatCompletion:
        """Cherche la firmographie/contacts d'un lead."""
        ...


class SocieteinfoProvider:
    """Provider de complétion adossé à l'API Societeinfo."""

    nom = "societeinfo"

    def __init__(self, client: SocieteinfoClient):
        self.client = client
        # Le coût unitaire vit soit sur le client (dry-run), soit sur sa config.
        cout = getattr(client, "cout_par_lead_eur", None)
        if cout is None:
            cout = getattr(getattr(client, "config", None), "cout_par_lead_eur", 0.0)
        self.cout_par_lead_eur = cout

    def chercher(
        self,
        *,
        nom: str | None = None,
        siren: str | None = None,
        code_postal: str | None = None,
        site_web: str | None = None,
    ) -> ResultatCompletion:
        res = self.client.enrichir(
            nom=nom, siren=siren, code_postal=code_postal, site_web=site_web
        )
        emails = list(res.emails) if res.emails else ([res.email] if res.email else [])
        return ResultatCompletion(
            siren=res.siren,
            code_naf=res.naf,
            libelle_naf=res.libelle_naf,
            tranche_effectif=res.effectif,
            chiffre_affaires=res.chiffre_affaires,
            # Societeinfo renvoie un dirigeant en chaîne unique → nom complet.
            dirigeant_nom=res.dirigeant,
            emails=emails,
            telephone=res.telephone,
            site_web=res.site_web,
            linkedin=res.linkedin,
            trouve=res.trouve,
        )


def construire_provider_societeinfo(
    *,
    api_key: str | None,
    dry_run: bool = False,
    budget_eur: float = 10.0,
    rate_per_min: int = 60,
) -> SocieteinfoProvider:
    """Fabrique un `SocieteinfoProvider` (réel ou dry-run selon clé/flag)."""
    if dry_run or not api_key:
        return SocieteinfoProvider(SocieteinfoClientDryRun())
    return SocieteinfoProvider(
        SocieteinfoClient(
            SocieteinfoClientConfig(
                api_key=api_key,
                rate_limiter=RateLimiter(rate_per_min),
                budget=BudgetGuard(plafond_eur=budget_eur),
            )
        )
    )


__all__ = [
    "ResultatCompletion",
    "ProviderCompletion",
    "SocieteinfoProvider",
    "construire_provider_societeinfo",
]
