"""Wrapper API Societeinfo pour l'enrichissement firmographique.

L'API Societeinfo expose un enrichissement par identité (nom + localisation) ou
par SIREN, renvoyant firmographie (NAF, effectif, CA), dirigeant et contacts.
Le endpoint exact dépend du plan ; il est donc paramétrable (`base_url`,
`endpoint`) pour s'adapter sans toucher au code.

Conçu pour être mockable : on injecte `http_get` / `http_post` (par défaut wrap
autour de `requests`). Un client `SocieteinfoClientDryRun` renvoie des données
synthétiques pour valider le flux sans abonnement.

⚠️ Le mapping des champs (`_parse_resultat`) suit la nomenclature documentée par
Societeinfo ; à reconfirmer contre la doc du plan souscrit avant la prod.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..common.budget_guard import BudgetGuard
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)

SOCIETEINFO_BASE_URL = "https://societeinfo.com/app/rest/api/v3"


class SocieteinfoError(RuntimeError):
    """Erreur générique d'appel Societeinfo (réseau, 4xx, 5xx, parsing)."""


@dataclass
class ResultatSocieteinfo:
    """Champs firmographiques normalisés renvoyés pour un lead."""

    siren: str | None = None
    naf: str | None = None
    libelle_naf: str | None = None
    effectif: str | None = None
    chiffre_affaires: int | None = None
    dirigeant: str | None = None
    email: str | None = None
    emails: list[str] | None = None
    telephone: str | None = None
    site_web: str | None = None
    linkedin: str | None = None
    trouve: bool = False
    brut: dict[str, Any] | None = None


@dataclass
class SocieteinfoClientConfig:
    api_key: str
    base_url: str = SOCIETEINFO_BASE_URL
    endpoint: str = "/enrich"  # ajustable selon le plan
    cout_par_lead_eur: float = 0.10
    timeout_s: float = 20.0
    rate_limiter: RateLimiter | None = None
    budget: BudgetGuard | None = None
    http_get: Callable[..., requests.Response] | None = None
    http_post: Callable[..., requests.Response] | None = None


class SocieteinfoClient:
    """Façade Societeinfo — enrichissement unitaire d'un lead."""

    def __init__(self, config: SocieteinfoClientConfig):
        self.config = config
        self._get = config.http_get or requests.get
        self._post = config.http_post or requests.post

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _appeler(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.config.rate_limiter:
            self.config.rate_limiter.acquire()
        url = f"{self.config.base_url}{self.config.endpoint}"
        resp = self._get(
            url, params=params, headers=self._headers(), timeout=self.config.timeout_s
        )
        if resp.status_code >= 400:
            raise SocieteinfoError(
                f"GET {self.config.endpoint} HTTP {resp.status_code} : {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError as e:
            raise SocieteinfoError(f"Réponse non-JSON : {e}") from e

    def enrichir(
        self,
        *,
        nom: str | None = None,
        siren: str | None = None,
        code_postal: str | None = None,
        site_web: str | None = None,
    ) -> ResultatSocieteinfo:
        """Enrichit un lead par SIREN (prioritaire) ou nom + code postal."""
        if not siren and not (nom or site_web):
            return ResultatSocieteinfo(trouve=False)

        cout = self.config.cout_par_lead_eur
        if self.config.budget:
            self.config.budget.ajouter_cout(cout, contexte="Societeinfo enrich")

        params: dict[str, Any] = {}
        if siren:
            params["siren"] = siren
        if nom:
            params["name"] = nom
        if code_postal:
            params["postal_code"] = code_postal
        if site_web:
            params["website"] = site_web

        data = self._appeler(params)
        return self._parse_resultat(data)

    @staticmethod
    def _parse_resultat(data: dict[str, Any]) -> ResultatSocieteinfo:
        """Mappe la réponse Societeinfo vers ResultatSocieteinfo (défensif)."""
        # Societeinfo renvoie typiquement {"result": {...}} ou une liste.
        bloc = data.get("result") if isinstance(data, dict) else None
        if bloc is None and isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list) and results:
                bloc = results[0]
        if not isinstance(bloc, dict):
            return ResultatSocieteinfo(trouve=False, brut=data)

        def _first_email(b: dict[str, Any]) -> tuple[str | None, list[str]]:
            emails = b.get("emails") or []
            if isinstance(emails, list) and emails:
                liste = [str(e) for e in emails if e]
                return (liste[0] if liste else None), liste
            single = b.get("email")
            return (single, [single] if single else [])

        email, emails = _first_email(bloc)
        ca = bloc.get("turnover") or bloc.get("chiffre_affaires")
        try:
            ca_int = int(ca) if ca is not None else None
        except (TypeError, ValueError):
            ca_int = None

        return ResultatSocieteinfo(
            siren=bloc.get("siren"),
            naf=bloc.get("naf") or bloc.get("ape"),
            libelle_naf=bloc.get("naf_label") or bloc.get("libelle_naf"),
            effectif=str(bloc["effectif"]) if bloc.get("effectif") is not None else None,
            chiffre_affaires=ca_int,
            dirigeant=bloc.get("manager") or bloc.get("dirigeant"),
            email=email,
            emails=emails or None,
            telephone=bloc.get("phone") or bloc.get("telephone"),
            site_web=bloc.get("website") or bloc.get("site_web"),
            linkedin=bloc.get("linkedin"),
            trouve=True,
            brut=bloc,
        )

    @property
    def cout_total_eur(self) -> float:
        """Coût cumulé réellement engagé (0 en dry-run ou sans BudgetGuard)."""
        budget = getattr(getattr(self, "config", None), "budget", None)
        return budget.cout_actuel_eur if budget is not None else 0.0

    def health_check(self) -> tuple[bool, str]:
        try:
            self._appeler({"siren": "552100554"})  # SIREN test (EDF)
            return True, "OK"
        except SocieteinfoError as e:
            return False, str(e)
        except Exception as e:  # noqa: BLE001
            return False, f"Erreur inattendue: {type(e).__name__}: {e}"


class SocieteinfoClientDryRun(SocieteinfoClient):
    """Client simulé : renvoie des données synthétiques, aucun appel réseau."""

    def __init__(self, cout_par_lead_eur: float = 0.0):
        # On NE PAS appelle super().__init__ (pas de clé requise en dry-run).
        self.cout_par_lead_eur = cout_par_lead_eur

    def enrichir(
        self,
        *,
        nom: str | None = None,
        siren: str | None = None,
        code_postal: str | None = None,
        site_web: str | None = None,
    ) -> ResultatSocieteinfo:
        if not siren and not (nom or site_web):
            return ResultatSocieteinfo(trouve=False)
        base = (nom or site_web or "lead").strip().lower().replace(" ", "")[:20]
        domaine = (site_web or f"{base}.fr").replace("https://", "").replace("http://", "")
        return ResultatSocieteinfo(
            siren=siren or "000000000",
            naf="42.99Z",
            libelle_naf="[DRY-RUN] Construction d'ouvrages",
            effectif="50 à 99 salariés",
            chiffre_affaires=5_000_000,
            dirigeant="[DRY-RUN] Dirigeant Test",
            email=f"contact@{domaine}",
            emails=[f"contact@{domaine}"],
            telephone="+33100000000",
            site_web=site_web or f"https://{domaine}",
            linkedin=None,
            trouve=True,
            brut={"dry_run": True},
        )

    def health_check(self) -> tuple[bool, str]:
        return True, "OK (dry-run)"


__all__ = [
    "SocieteinfoClient",
    "SocieteinfoClientDryRun",
    "SocieteinfoClientConfig",
    "SocieteinfoError",
    "ResultatSocieteinfo",
]
