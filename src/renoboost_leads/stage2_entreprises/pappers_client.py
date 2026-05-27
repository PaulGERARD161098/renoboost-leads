"""Client API Pappers (api.pappers.fr) — fallback ciblé de l'étage 2.

N'est interrogé QUE lorsque le matching gratuit (recherche-entreprises.api.gouv.fr)
échoue ou reste incertain, pour relever le taux de match SIREN sans payer chaque
lead. Chaque appel /v2/recherche consomme des jetons → budget surveillé.

Endpoint : https://api.pappers.fr/v2/recherche
Auth : paramètre de requête `api_token`.

Conçu pour être mockable : on injecte `http_get` (par défaut `requests.get`),
sur le modèle de `stage3_5_enrichment/client.py`.

⚠️ Les noms de champs du mapper ci-dessous sont calqués sur le schéma documenté
de Pappers v2. Ils diffèrent parfois de ceux de data.gouv et doivent être
re-vérifiés sur une vraie réponse live (le mapping est défensif avec fallbacks).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..common.budget_guard import BudgetGuard
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)

PAPPERS_RECHERCHE_URL = "https://api.pappers.fr/v2/recherche"


# ════════════════════════════════════════════════════════════════
# Exceptions
# ════════════════════════════════════════════════════════════════


class PappersError(Exception):
    """Erreur générique d'appel Pappers (4xx, parsing)."""


class PappersTransientError(PappersError):
    """Erreur réseau/5xx/429 — retryable."""


# ════════════════════════════════════════════════════════════════
# Config
# ════════════════════════════════════════════════════════════════


@dataclass
class PappersClientConfig:
    api_key: str
    base_url: str = PAPPERS_RECHERCHE_URL
    timeout_seconds: float = 20.0
    per_page: int = 5
    cout_par_appel_eur: float = 0.02
    rate_limiter: RateLimiter | None = None
    budget: BudgetGuard | None = None
    # Hook injectable pour les tests (mock sans monkeypatch global).
    http_get: Callable[..., requests.Response] | None = None
    user_agent: str = "RenoboostLeadsBot/0.1 (+contact@renoboost.fr)"


# ════════════════════════════════════════════════════════════════
# Client
# ════════════════════════════════════════════════════════════════


class PappersClient:
    """Wrapper de l'endpoint /v2/recherche de Pappers."""

    def __init__(self, config: PappersClientConfig):
        self.config = config
        self._get = config.http_get or requests.get

    @retry(
        retry=retry_if_exception_type(PappersTransientError),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def rechercher(
        self,
        query: str,
        code_postal: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recherche d'entreprises chez Pappers, mappées en forme "candidat".

        Args:
            query: nom (+ ville idéalement), ex "Hôtel Le Sud Montpellier"
            code_postal: filtre additionnel (réduit le bruit)

        Returns:
            Liste de candidats au format attendu par le matcher data.gouv
            (peut être vide). Chaque appel réussi consomme du budget.
        """
        if not query or not query.strip():
            return []

        params: dict[str, Any] = {
            "api_token": self.config.api_key,
            "q": query.strip(),
            "par_page": self.config.per_page,
        }
        if code_postal:
            params["code_postal"] = code_postal

        if self.config.budget is not None:
            # Budget AVANT l'appel : peut lever BudgetExceededError (cap dur).
            self.config.budget.ajouter_cout(
                self.config.cout_par_appel_eur,
                contexte=f"L2 Pappers fallback ({query!r})",
            )

        if self.config.rate_limiter is not None:
            self.config.rate_limiter.acquire()

        logger.debug("Pappers /recherche : %s (cp=%s)", query, code_postal)

        try:
            resp = self._get(
                self.config.base_url,
                params=params,
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise PappersTransientError(f"Erreur réseau Pappers : {e}") from e

        if 500 <= resp.status_code < 600:
            raise PappersTransientError(f"HTTP {resp.status_code}")
        if resp.status_code == 429:
            raise PappersTransientError("HTTP 429 rate-limited")
        if resp.status_code != 200:
            # 401 (crédits épuisés), 400, etc. : pas retryable, on log et renvoie vide.
            logger.warning(
                "Pappers HTTP %s pour query=%r : %s",
                resp.status_code,
                query,
                resp.text[:200],
            )
            return []

        try:
            data = resp.json()
        except ValueError as e:
            raise PappersError(f"Réponse Pappers non-JSON : {e}") from e

        resultats = data.get("resultats") or data.get("results") or []
        return [pappers_resultat_to_candidat(r) for r in resultats if isinstance(r, dict)]


# ════════════════════════════════════════════════════════════════
# Mapping Pappers v2 → forme "candidat" data.gouv
# ════════════════════════════════════════════════════════════════


def _etat_administratif(resultat: dict[str, Any]) -> str:
    """Dérive l'état administratif au format data.gouv ('A' actif / 'C' cessée).

    Pappers expose `entreprise_cessee` (bool). On retombe sur un éventuel
    `etat_administratif` déjà au bon format si fourni.
    """
    etat = resultat.get("etat_administratif")
    if isinstance(etat, str) and etat:
        return etat.upper()
    cessee = resultat.get("entreprise_cessee")
    if cessee is True:
        return "C"
    if cessee is False:
        return "A"
    return ""


def _dirigeants(resultat: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise les dirigeants Pappers vers la forme lue par le mapper.

    Le mapper data.gouv lit `nom`, `prenoms`/`prenom`, `qualite`. Pappers
    utilise `prenom` (singulier) → on alimente les deux pour robustesse.
    """
    bruts = resultat.get("dirigeants") or []
    out: list[dict[str, Any]] = []
    for d in bruts:
        if not isinstance(d, dict):
            continue
        prenom = d.get("prenom") or d.get("prenoms")
        out.append(
            {
                "nom": d.get("nom"),
                "prenom": prenom,
                "prenoms": prenom,
                "qualite": d.get("qualite") or d.get("qualité"),
            }
        )
    return out


def _finances(resultat: dict[str, Any]) -> dict[str, Any] | None:
    """Reconstruit un bloc `finances` si /recherche renvoie CA/résultat à plat.

    Forme cible (data.gouv) : {"YYYY": {"ca": ..., "resultat_net": ...}}.
    Absent le plus souvent sur /recherche → renvoie None (CA reste couvert
    par data.gouv #22).
    """
    ca = resultat.get("chiffre_affaires")
    resultat_net = resultat.get("resultat") or resultat.get("resultat_net")
    if not isinstance(ca, (int, float)) and not isinstance(resultat_net, (int, float)):
        return None
    annee = resultat.get("annee_finances") or resultat.get("annee_chiffre_affaires")
    cle = str(annee) if annee else "0000"
    bloc: dict[str, Any] = {}
    if isinstance(ca, (int, float)):
        bloc["ca"] = ca
    if isinstance(resultat_net, (int, float)):
        bloc["resultat_net"] = resultat_net
    return {cle: bloc}


def pappers_resultat_to_candidat(resultat: dict[str, Any]) -> dict[str, Any]:
    """Convertit un résultat Pappers v2 en dict "candidat" forme data.gouv.

    Le dict produit est consommé tel quel par `selectionner_meilleur_candidat`
    (matcher) et `candidat_to_l2_fields` (mapper), sans modifier ces modules.
    """
    siege_src = resultat.get("siege") or {}

    nom_complet = (
        resultat.get("nom_entreprise")
        or resultat.get("denomination")
        or resultat.get("nom")
        or resultat.get("nom_complet")
    )

    siege = {
        "siret": siege_src.get("siret"),
        "code_postal": siege_src.get("code_postal"),
        "libelle_commune": siege_src.get("ville") or siege_src.get("libelle_commune"),
        "commune": siege_src.get("ville") or siege_src.get("commune"),
        "activite_principale": siege_src.get("code_naf") or siege_src.get("activite_principale"),
        "libelle_activite_principale": (
            siege_src.get("libelle_code_naf") or siege_src.get("libelle_activite_principale")
        ),
        "numero_voie": siege_src.get("numero_voie"),
        "type_voie": siege_src.get("type_voie"),
        "libelle_voie": siege_src.get("libelle_voie"),
    }

    candidat: dict[str, Any] = {
        "siren": resultat.get("siren"),
        "siret": resultat.get("siret") or siege_src.get("siret"),
        "nom_complet": nom_complet,
        "nom_raison_sociale": nom_complet,
        "siege": siege,
        "activite_principale": resultat.get("code_naf") or resultat.get("activite_principale"),
        "libelle_activite_principale": (
            resultat.get("libelle_code_naf") or resultat.get("libelle_activite_principale")
        ),
        "nature_juridique": (
            resultat.get("code_forme_juridique") or resultat.get("nature_juridique")
        ),
        "etat_administratif": _etat_administratif(resultat),
        "tranche_effectif_salarie": (
            resultat.get("tranche_effectif") or resultat.get("tranche_effectif_salarie")
        ),
        "libelle_tranche_effectif_salarie": (
            resultat.get("effectif") or resultat.get("libelle_tranche_effectif_salarie")
        ),
        "dirigeants": _dirigeants(resultat),
        "date_creation": resultat.get("date_creation"),
        "nombre_etablissements": resultat.get("nombre_etablissements"),
        "categorie_entreprise": resultat.get("categorie_entreprise"),
    }

    finances = _finances(resultat)
    if finances is not None:
        candidat["finances"] = finances

    return candidat


__all__ = [
    "PappersClient",
    "PappersClientConfig",
    "PappersError",
    "PappersTransientError",
    "pappers_resultat_to_candidat",
    "PAPPERS_RECHERCHE_URL",
]
