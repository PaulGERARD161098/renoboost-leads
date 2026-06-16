"""Client API Recherche d'entreprises (recherche-entreprises.api.gouv.fr).

API publique gratuite, sans authentification.
Documentation : https://recherche-entreprises.api.gouv.fr/

Limites :
- 7 requêtes/seconde par IP
- Réponse JSON paginée
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..common.logger import get_logger
from ..common.naf import est_code_ape_complet, sections_pour_codes
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)

# Endpoints
RECHERCHE_URL = "https://recherche-entreprises.api.gouv.fr/search"
# Recherche géographique autour d'un point (lat/long/radius en km).
NEAR_POINT_URL = "https://recherche-entreprises.api.gouv.fr/near_point"


# ════════════════════════════════════════════════════════════════
# Exceptions
# ════════════════════════════════════════════════════════════════


class RechercheEntreprisesError(Exception):
    """Erreur générique."""


class RechercheEntreprisesTransientError(RechercheEntreprisesError):
    """Erreur réseau/5xx — retryable."""


# ════════════════════════════════════════════════════════════════
# Config
# ════════════════════════════════════════════════════════════════


@dataclass
class RechercheClientConfig:
    rate_limiter: RateLimiter
    timeout_seconds: float = 12.0
    user_agent: str = "RenoboostLeadsBot/0.1 (+contact@renoboost.fr)"


# ════════════════════════════════════════════════════════════════
# Client
# ════════════════════════════════════════════════════════════════


class RechercheEntreprisesClient:
    """Wrapper de l'API recherche-entreprises.api.gouv.fr."""

    def __init__(self, config: RechercheClientConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    @retry(
        retry=retry_if_exception_type(
            (RechercheEntreprisesTransientError, requests.RequestException)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def rechercher(
        self,
        query: str,
        code_postal: str | None = None,
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Recherche des entreprises par requête textuelle (nom + ville/CP idéalement).

        Args:
            query: ex "Hôtel Le Sud Montpellier"
            code_postal: filtre additionnel (ex: "34000") — réduit le bruit
            per_page: nb résultats (max 25)

        Returns:
            Liste des résultats bruts (peut être vide).
        """
        if not query or not query.strip():
            return []

        params: dict[str, Any] = {
            "q": query.strip(),
            "per_page": min(per_page, 25),
        }
        if code_postal:
            params["code_postal"] = code_postal

        # Politesse
        self.config.rate_limiter.acquire()

        logger.debug("Recherche entreprises: %s (cp=%s)", query, code_postal)

        try:
            resp = self.session.get(
                RECHERCHE_URL,
                params=params,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise RechercheEntreprisesTransientError(f"Erreur réseau: {e}") from e

        if 500 <= resp.status_code < 600:
            raise RechercheEntreprisesTransientError(f"HTTP {resp.status_code}")

        if resp.status_code == 429:
            # Rate limit côté serveur — on relance après pause
            raise RechercheEntreprisesTransientError("HTTP 429 rate-limited")

        if resp.status_code != 200:
            logger.warning("HTTP %s pour query=%r", resp.status_code, query)
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.warning("Réponse non-JSON pour query=%r", query)
            return []

        return data.get("results", []) or []

    @retry(
        retry=retry_if_exception_type(
            (RechercheEntreprisesTransientError, requests.RequestException)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def _search_page(
        self, params: dict[str, Any], url: str = RECHERCHE_URL
    ) -> dict[str, Any]:
        """Appel d'une page (/search ou /near_point). Lève sur 5xx/429 (retry tenacity)."""
        self.config.rate_limiter.acquire()
        try:
            resp = self.session.get(
                url,
                params=params,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise RechercheEntreprisesTransientError(f"Erreur réseau: {e}") from e

        if 500 <= resp.status_code < 600:
            raise RechercheEntreprisesTransientError(f"HTTP {resp.status_code}")
        if resp.status_code == 429:
            raise RechercheEntreprisesTransientError("HTTP 429 rate-limited")
        if resp.status_code != 200:
            logger.warning("HTTP %s pour params=%r", resp.status_code, params)
            return {"results": [], "total_pages": 0, "total_results": 0}

        try:
            return resp.json()
        except ValueError:
            logger.warning("Réponse non-JSON pour params=%r", params)
            return {"results": [], "total_pages": 0, "total_results": 0}

    def decouvrir(
        self,
        departements: list[str],
        *,
        activite_principale: list[str] | None = None,
        tranche_effectif_salarie: list[str] | None = None,
        ca_min: int | None = None,
        ca_max: int | None = None,
        categorie_entreprise: list[str] | None = None,
        etat_administratif: str = "A",
        siege_only: bool = True,
        max_results: int = 1000,
        per_page: int = 25,
    ) -> Iterator[dict[str, Any]]:
        """Découverte SIRENE-first : itère sur les entreprises matchant les filtres.

        Utilise l'API recherche-entreprises avec ses filtres natifs (CA, NAF,
        tranche d'effectif, catégorie, état administratif) + filtre post-réception
        sur le département du siège si `siege_only=True` (l'API filtre les
        ÉTABLISSEMENTS sinon, ce qui ramène les entreprises nationales).

        Pagination automatique jusqu'à `max_results` ou épuisement.

        Args:
            departements: codes INSEE département (filtre établissement + siège).
            activite_principale: codes NAF/APE. Les codes complets ("49.41A")
                sont filtrés précisément ; les divisions/préfixes ("49", "70.10")
                sont élargis à la section NAF (l'API n'accepte pas les préfixes),
                puis resserrés côté extracteur.
            tranche_effectif_salarie: codes INSEE tranche ex ["02","03","11","12"]
                pour 3-49 salariés.
            ca_min, ca_max: bornes du chiffre d'affaires en €.
            categorie_entreprise: ["PME"], ["PME","ETI"], etc.
            etat_administratif: "A" actif, "C" cessé.
            siege_only: si True, écarte les entreprises dont le siège n'est pas
                dans `departements`. Recommandé pour le profil PME locale.
            max_results: plafond global du nombre de résultats yieldés.
            per_page: taille de page API (max 25).

        Yields:
            Le dict résultat brut de l'API pour chaque entreprise matchant.
        """
        if not departements:
            return
        if max_results <= 0:
            return

        base_params: dict[str, Any] = {
            "departement": ",".join(departements),
            "etat_administratif": etat_administratif,
            "per_page": min(per_page, 25),
        }
        self._appliquer_filtres(
            base_params,
            activite_principale=activite_principale,
            tranche_effectif_salarie=tranche_effectif_salarie,
            ca_min=ca_min,
            ca_max=ca_max,
            categorie_entreprise=categorie_entreprise,
        )

        siege_set = set(departements) if siege_only else None
        yielded = 0
        page = 1
        total_pages: int | None = None

        while yielded < max_results:
            params = {**base_params, "page": page}
            data = self._search_page(params)
            results = data.get("results") or []
            if total_pages is None:
                total_pages = data.get("total_pages") or 0
                logger.info(
                    "Découverte SIRENE : %s entreprises matchant (%s pages)",
                    data.get("total_results"),
                    total_pages,
                )

            if not results:
                break

            for r in results:
                if siege_set is not None:
                    siege_dept = (r.get("siege") or {}).get("departement")
                    if siege_dept not in siege_set:
                        continue
                yield r
                yielded += 1
                if yielded >= max_results:
                    return

            if total_pages and page >= total_pages:
                break
            page += 1

    @staticmethod
    def _appliquer_filtres(
        params: dict[str, Any],
        *,
        activite_principale: list[str] | None,
        tranche_effectif_salarie: list[str] | None,
        ca_min: int | None,
        ca_max: int | None,
        categorie_entreprise: list[str] | None,
    ) -> None:
        """Ajoute en place les filtres entreprise natifs aux params API.

        NAF : l'API n'accepte que des codes APE complets (« 25.11Z ») en
        `activite_principale`, pas les divisions/préfixes (« 10 », « 70.10 »).
        Si la cible contient des préfixes, on élargit à la `section` NAF
        correspondante (l'extracteur SIRENE-first resserre ensuite au préfixe
        exact). Si tous les codes sont complets, on garde le filtrage précis.
        """
        if activite_principale:
            if all(est_code_ape_complet(c) for c in activite_principale):
                params["activite_principale"] = ",".join(activite_principale)
            else:
                sections = sections_pour_codes(activite_principale)
                if sections:
                    params["section_activite_principale"] = ",".join(sections)
        if tranche_effectif_salarie:
            params["tranche_effectif_salarie"] = ",".join(tranche_effectif_salarie)
        if ca_min is not None:
            params["ca_min"] = ca_min
        if ca_max is not None:
            params["ca_max"] = ca_max
        if categorie_entreprise:
            params["categorie_entreprise"] = ",".join(categorie_entreprise)

    @staticmethod
    def _siege_dans_zone(entreprise: dict[str, Any]) -> bool:
        """True si le siège de l'entreprise est l'un des établissements du rayon.

        L'endpoint near_point renvoie pour chaque entreprise la liste
        `matching_etablissements` (ceux situés dans le cercle). On considère le
        siège « dans la zone » si l'un de ces établissements porte `est_siege`.
        Élimine les antennes locales de groupes dont le siège est ailleurs.
        """
        for etab in entreprise.get("matching_etablissements") or []:
            if etab.get("est_siege"):
                return True
        return False

    def decouvrir_near_point(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        *,
        activite_principale: list[str] | None = None,
        tranche_effectif_salarie: list[str] | None = None,
        ca_min: int | None = None,
        ca_max: int | None = None,
        categorie_entreprise: list[str] | None = None,
        etat_administratif: str = "A",
        siege_only: bool = True,
        max_results: int = 1000,
        per_page: int = 25,
    ) -> Iterator[dict[str, Any]]:
        """Découverte géographique : entreprises dans un rayon autour d'un point.

        Cible une zone d'activité précise (parc, adresse) via l'endpoint
        `near_point` et ses filtres natifs (NAF, effectif, CA, catégorie).

        Args:
            latitude, longitude: centre du cercle (degrés décimaux).
            radius_km: rayon en kilomètres.
            siege_only: si True, ne yield que les entreprises dont le SIÈGE est
                dans le rayon (via `matching_etablissements[].est_siege`), pour
                écarter les antennes locales de groupes décidant ailleurs.
            (autres args : cf. `decouvrir`).

        Yields:
            Le dict résultat brut de l'API pour chaque entreprise matchant.
        """
        if max_results <= 0:
            return

        base_params: dict[str, Any] = {
            "lat": latitude,
            "long": longitude,
            "radius": radius_km,
            "etat_administratif": etat_administratif,
            "per_page": min(per_page, 25),
        }
        self._appliquer_filtres(
            base_params,
            activite_principale=activite_principale,
            tranche_effectif_salarie=tranche_effectif_salarie,
            ca_min=ca_min,
            ca_max=ca_max,
            categorie_entreprise=categorie_entreprise,
        )

        yielded = 0
        page = 1
        total_pages: int | None = None

        while yielded < max_results:
            params = {**base_params, "page": page}
            data = self._search_page(params, url=NEAR_POINT_URL)
            results = data.get("results") or []
            if total_pages is None:
                total_pages = data.get("total_pages") or 0
                logger.info(
                    "Découverte géo (near_point) : %s entreprises dans %s km "
                    "(%s pages)",
                    data.get("total_results"),
                    radius_km,
                    total_pages,
                )

            if not results:
                break

            for r in results:
                if siege_only and not self._siege_dans_zone(r):
                    continue
                yield r
                yielded += 1
                if yielded >= max_results:
                    return

            if total_pages and page >= total_pages:
                break
            page += 1

    def health_check(self) -> tuple[bool, str]:
        """Test rapide de connectivité (gratuit)."""
        try:
            results = self.rechercher("test", per_page=1)
            return True, f"OK ({len(results)} résultats sur 'test')"
        except RechercheEntreprisesError as e:
            return False, str(e)
        except Exception as e:  # noqa: BLE001
            return False, f"Erreur inattendue: {type(e).__name__}: {e}"
