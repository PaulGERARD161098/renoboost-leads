"""Orchestrateur Étage 2 — enrichissement des leads L1 → L2.

Logique :
1. Lit le CSV L1 (etage1_decouverte.csv) ou prend les leads en mémoire
2. Pour chaque lead :
   a. Détection chaîne (Accor, Carrefour...) → flag + note manuelle, pas d'API
   b. Sinon : appel API Recherche d'entreprises avec nom + CP
   c. Scoring des candidats, sélection du meilleur
   d. Mapping → LeadStage2
3. Sauvegarde incrémentale tous les 20 leads
4. Backup horodaté à la fin
5. Cache SQLite pour éviter les re-paiements
"""

from __future__ import annotations

import time
from typing import Any

from ..common.cache import SessionCache
from ..common.logger import get_logger
from ..models import LeadStage1, LeadStage2
from .mapper import candidat_to_l2_fields
from .matcher import selectionner_meilleur_candidat
from .recherche_client import RechercheEntreprisesClient
from .referentiel_chaines import detecter_chaine, note_chaine_standard

logger = get_logger(__name__)


class EnricheurStage2:
    """Pipeline d'enrichissement L1 → L2."""

    def __init__(
        self,
        client: RechercheEntreprisesClient,
        cache: SessionCache | None = None,
        callback_save_incremental=None,
    ):
        """
        Args:
            client: instance du client API
            cache: cache SQLite pour éviter les re-paiements
            callback_save_incremental: fonction appelée tous les 20 leads (pour sauvegarde)
        """
        self.client = client
        self.cache = cache
        self.callback_save = callback_save_incremental

    def _chercher_avec_cache(self, lead: LeadStage1) -> list[dict[str, Any]]:
        """Recherche entreprise avec cache (évite re-paiement)."""
        # Clé de cache basée sur nom + CP
        cache_key = f"{(lead.nom or '').lower()}|{lead.code_postal or 'noCP'}"

        if self.cache:
            cached = self.cache.get_place(place_id=cache_key, stage="stage2_search")
            if cached is not None:
                return cached.get("results", [])

        # Construction de la query
        query = lead.nom or ""
        if lead.ville:
            query = f"{query} {lead.ville}"

        try:
            results = self.client.rechercher(
                query=query,
                code_postal=lead.code_postal,
                per_page=10,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Erreur API pour %r : %s", lead.nom, e)
            results = []

        # Stockage en cache
        if self.cache:
            self.cache.store_place(
                place_id=cache_key,
                stage="stage2_search",
                payload={"results": results},
            )

        return results

    def _enrichir_un_lead(self, lead: LeadStage1) -> LeadStage2:
        """Enrichit un lead L1 → L2."""
        # Étape 1 — Détection chaîne
        est_chaine, groupe = detecter_chaine(lead.nom)
        if est_chaine:
            return LeadStage2(
                **lead.model_dump(),
                flag_chaine=True,
                note_chaine=f"{note_chaine_standard()} Groupe identifié : {groupe}.",
                match_incertain=True,  # Pas de SIREN local fiable
            )

        # Étape 2 — Recherche API
        candidats = self._chercher_avec_cache(lead)

        # Étape 3 — Scoring
        best, score, incertain = selectionner_meilleur_candidat(
            candidats=candidats,
            nom_cible=lead.nom,
            code_postal_cible=lead.code_postal,
            ville_cible=lead.ville,
        )

        # Étape 4 — Mapping
        if best is None:
            return LeadStage2(
                **lead.model_dump(),
                score_matching=0.0,
                match_incertain=True,
            )

        l2_fields = candidat_to_l2_fields(best)
        return LeadStage2(
            **lead.model_dump(),
            **l2_fields,
            score_matching=round(score, 1),
            match_incertain=incertain,
        )

    def enrichir(self, leads: list[LeadStage1]) -> list[LeadStage2]:
        """Enrichit une liste de leads L1 → L2.

        Sauvegarde incrémentale tous les 20 leads via le callback fourni.
        """
        logger.info("=== Étage 2 — Enrichissement entreprise (%d leads) ===", len(leads))
        t0 = time.monotonic()
        leads_l2: list[LeadStage2] = []
        nb_chaines = 0
        nb_match_ok = 0
        nb_match_incertain = 0
        nb_no_match = 0

        for i, lead in enumerate(leads, start=1):
            try:
                l2 = self._enrichir_un_lead(lead)
            except Exception as e:  # noqa: BLE001
                logger.exception("Erreur sur lead %s : %s", lead.place_id, e)
                # Fallback : on garde le lead en L1 avec les flags par défaut
                l2 = LeadStage2(**lead.model_dump(), match_incertain=True)

            leads_l2.append(l2)

            if l2.flag_chaine:
                nb_chaines += 1
            elif l2.siren is None:
                nb_no_match += 1
            elif l2.match_incertain:
                nb_match_incertain += 1
            else:
                nb_match_ok += 1

            # Sauvegarde incrémentale tous les 20
            if i % 20 == 0 and self.callback_save:
                logger.info("→ Sauvegarde incrémentale (%d/%d)", i, len(leads))
                try:
                    self.callback_save(leads_l2)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Erreur sauvegarde incrémentale : %s", e)

            # Petit log de progression toutes les 50
            if i % 50 == 0:
                logger.info("  L2 progress: %d/%d", i, len(leads))

        duree = time.monotonic() - t0
        logger.info(
            "=== Étage 2 terminé : %d leads (%.1fs) ===\n"
            "  Match confiant : %d (%.0f%%)\n"
            "  Match incertain : %d (%.0f%%)\n"
            "  Pas de SIREN trouvé : %d (%.0f%%)\n"
            "  Chaînes flaguées : %d (%.0f%%)",
            len(leads),
            duree,
            nb_match_ok,
            100 * nb_match_ok / max(1, len(leads)),
            nb_match_incertain,
            100 * nb_match_incertain / max(1, len(leads)),
            nb_no_match,
            100 * nb_no_match / max(1, len(leads)),
            nb_chaines,
            100 * nb_chaines / max(1, len(leads)),
        )

        return leads_l2

    @staticmethod
    def stats_l2(leads_l2: list[LeadStage2]) -> dict[str, Any]:
        """Retourne des stats L2 pour le rapport."""
        n = len(leads_l2)
        if n == 0:
            return {"total": 0}
        nb_siren = sum(1 for lead in leads_l2 if lead.siren)
        nb_chaines = sum(1 for lead in leads_l2 if lead.flag_chaine)
        nb_dirigeant = sum(1 for lead in leads_l2 if lead.dirigeant_nom)
        return {
            "total": n,
            "siren_trouve": nb_siren,
            "siren_pct": round(100 * nb_siren / n, 1),
            "chaines": nb_chaines,
            "chaines_pct": round(100 * nb_chaines / n, 1),
            "dirigeant_trouve": nb_dirigeant,
            "dirigeant_pct": round(100 * nb_dirigeant / n, 1),
        }
