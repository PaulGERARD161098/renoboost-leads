"""Orchestrateur étage 4 — L3 → L4 (scoring Claude + pitch).

Logique :
1. Pour chaque LeadStage3 :
   a. Calcul de la clé de cache (prompt_version, modèle, contexte, inclure_pitch)
   b. Hit cache → on reconstruit LeadStage4 sans appel API
   c. Miss → on construit le prompt, on appelle Claude, on parse, on stocke
   d. Erreur (parse, API, budget) → on garde le lead sans score (scoring_erreur posé)
2. Sauvegarde incrémentale tous les 20 leads via callback
"""

from __future__ import annotations

import time
from typing import Any

from ..common.budget_guard import BudgetExceededError
from ..common.logger import get_logger
from ..models import ClaudeScoring, Emetteur, LeadStage3, LeadStage4
from .cache import CacheStage4, calcul_cache_key, hash_prompt
from .client import ClaudeClient, ClaudeParseError
from .prompt_template import CONTEXTE_CLIENT_DEFAUT, PROMPT_VERSION, construire_prompt

logger = get_logger(__name__)


class EnricheurStage4:
    """Pipeline L3 → L4 : scoring + (optionnel) pitch via Claude."""

    def __init__(
        self,
        client: ClaudeClient,
        config: ClaudeScoring,
        cache: CacheStage4 | None = None,
        callback_save_incremental=None,
        emetteur: Emetteur | None = None,
    ):
        self.client = client
        self.config = config
        self.cache = cache
        self.callback_save = callback_save_incremental
        self.emetteur = emetteur

        self.contexte_client = config.contexte_client or CONTEXTE_CLIENT_DEFAUT
        self._cache_key = calcul_cache_key(
            prompt_version=PROMPT_VERSION,
            modele=config.modele,
            contexte_client=self.contexte_client,
            inclure_pitch=config.inclure_pitch,
        )

        # Compteurs internes (exposés via stats_l4)
        self.cache_hits = 0
        self.cache_misses = 0
        self.cout_total_eur = 0.0
        self.tokens_in_total = 0
        self.tokens_out_total = 0

    def _build_lead_l4(
        self,
        lead_l3: LeadStage3,
        score: int | None,
        raison: str | None,
        pitch: str | None,
        modele: str | None,
        erreur: str | None,
        email_objet: str | None = None,
        email_corps: str | None = None,
    ) -> LeadStage4:
        top = score is not None and score >= self.config.seuil_top_lead
        return LeadStage4(
            **lead_l3.model_dump(),
            score_interet=score,
            raison_score=raison,
            pitch_propose=pitch,
            email_objet=email_objet,
            email_corps=email_corps,
            top_lead=top,
            scoring_modele=modele,
            scoring_erreur=erreur,
        )

    def enrichir_un_lead(self, lead: LeadStage3) -> LeadStage4:
        """Enrichit un seul lead L3 → L4 (cache lookup + appel client si miss).

        Méthode publique pour permettre un streaming externe (ex: UI Streamlit
        qui veut afficher une progress bar). Pour l'enrichissement batch
        standard, utiliser `enrichir(leads)`.
        """
        # On construit le prompt d'abord : son hash entre dans la clé de cache,
        # ce qui invalide automatiquement le cache si les données du lead ont
        # changé (ex. ré-enrichissement L2 après panne data.gouv).
        prompt = construire_prompt(
            lead=lead,
            contexte_client=self.contexte_client,
            inclure_pitch=self.config.inclure_pitch,
            emetteur=self.emetteur,
        )
        lead_cache_key = f"{self._cache_key}:{hash_prompt(prompt)}"

        # 1) Cache lookup
        if self.cache:
            cached = self.cache.get(lead.place_id, lead_cache_key)
            if cached is not None:
                self.cache_hits += 1
                return self._build_lead_l4(
                    lead_l3=lead,
                    score=cached.get("score_interet"),
                    raison=cached.get("raison_score"),
                    pitch=cached.get("pitch_propose"),
                    email_objet=cached.get("email_objet"),
                    email_corps=cached.get("email_corps"),
                    modele=cached.get("scoring_modele") or self.config.modele,
                    erreur=cached.get("scoring_erreur"),
                )

        # 2) Cache miss → appel API
        self.cache_misses += 1

        try:
            reponse = self.client.scorer(prompt)
        except BudgetExceededError:
            # On laisse remonter : la boucle gère pour arrêter proprement.
            raise
        except ClaudeParseError as e:
            logger.warning("Parse error L4 sur %s : %s", lead.place_id, e)
            return self._build_lead_l4(
                lead_l3=lead,
                score=None,
                raison=None,
                pitch=None,
                modele=self.config.modele,
                erreur=f"parse_error: {e}",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Erreur API Claude sur %s : %s", lead.place_id, e)
            # On garde le message (tronqué), pas seulement le type : la cause
            # exacte (modèle invalide, payload, quota…) reste visible en base.
            return self._build_lead_l4(
                lead_l3=lead,
                score=None,
                raison=None,
                pitch=None,
                modele=self.config.modele,
                erreur=f"api_error: {type(e).__name__}: {e}"[:240],
            )

        # 3) Stockage cache + compteurs
        self.cout_total_eur += reponse.cout_eur
        self.tokens_in_total += reponse.tokens_in
        self.tokens_out_total += reponse.tokens_out

        payload = {
            "score_interet": reponse.score_interet,
            "raison_score": reponse.raison_score,
            "pitch_propose": reponse.pitch_propose,
            "email_objet": reponse.email_objet,
            "email_corps": reponse.email_corps,
            "scoring_modele": reponse.modele,
            "tokens_in": reponse.tokens_in,
            "tokens_out": reponse.tokens_out,
            "cout_eur": reponse.cout_eur,
            "scoring_erreur": None,
        }
        if self.cache:
            self.cache.store(lead.place_id, lead_cache_key, payload)

        return self._build_lead_l4(
            lead_l3=lead,
            score=reponse.score_interet,
            raison=reponse.raison_score,
            pitch=reponse.pitch_propose,
            email_objet=reponse.email_objet,
            email_corps=reponse.email_corps,
            modele=reponse.modele,
            erreur=None,
        )

    def enrichir(self, leads_l3: list[LeadStage3]) -> list[LeadStage4]:
        """Pipeline L3 → L4 sur une liste de leads."""
        logger.info(
            "=== Étage 4 — Scoring Claude (%d leads, modèle=%s, seuil=%d, pitch=%s) ===",
            len(leads_l3),
            self.config.modele,
            self.config.seuil_top_lead,
            self.config.inclure_pitch,
        )
        t0 = time.monotonic()
        leads_l4: list[LeadStage4] = []
        budget_atteint = False

        for i, lead in enumerate(leads_l3, start=1):
            if budget_atteint:
                # On garde le lead sans score plutôt que de le perdre
                leads_l4.append(
                    self._build_lead_l4(
                        lead_l3=lead,
                        score=None,
                        raison=None,
                        pitch=None,
                        modele=self.config.modele,
                        erreur="budget_exhausted",
                    )
                )
                continue

            try:
                l4 = self.enrichir_un_lead(lead)
            except BudgetExceededError as e:
                logger.error("L4 stoppé par budget guard : %s", e)
                budget_atteint = True
                leads_l4.append(
                    self._build_lead_l4(
                        lead_l3=lead,
                        score=None,
                        raison=None,
                        pitch=None,
                        modele=self.config.modele,
                        erreur=f"budget_exhausted: {e}",
                    )
                )
                continue
            except Exception as e:  # noqa: BLE001 — filet final
                logger.exception("Erreur inattendue L4 sur %s : %s", lead.place_id, e)
                l4 = self._build_lead_l4(
                    lead_l3=lead,
                    score=None,
                    raison=None,
                    pitch=None,
                    modele=self.config.modele,
                    erreur=f"unexpected_error: {type(e).__name__}",
                )

            leads_l4.append(l4)

            if i % 20 == 0 and self.callback_save:
                logger.info("→ Sauvegarde incrémentale L4 (%d/%d)", i, len(leads_l3))
                try:
                    self.callback_save(leads_l4)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Erreur sauvegarde incrémentale L4 : %s", e)

            if i % 25 == 0:
                logger.info("  L4 progress: %d/%d", i, len(leads_l3))

        duree = time.monotonic() - t0
        stats = self.stats_l4(leads_l4)
        logger.info(
            "=== Étage 4 terminé : %d leads (%.1fs) ===\n"
            "  Top leads (score ≥ %d) : %d (%.0f%%)\n"
            "  Score moyen : %.1f\n"
            "  Cache hits / miss : %d / %d\n"
            "  Coût total : %.4f € (in=%d, out=%d tokens)",
            len(leads_l3),
            duree,
            self.config.seuil_top_lead,
            stats.get("top_leads", 0),
            stats.get("top_pct", 0.0),
            stats.get("score_moyen", 0.0),
            self.cache_hits,
            self.cache_misses,
            self.cout_total_eur,
            self.tokens_in_total,
            self.tokens_out_total,
        )
        return leads_l4

    def stats_l4(self, leads_l4: list[LeadStage4]) -> dict[str, Any]:
        """Stats pour le rapport (utilisé par la CLI)."""
        n = len(leads_l4)
        if n == 0:
            return {"total": 0}
        scores = [lead.score_interet for lead in leads_l4 if lead.score_interet is not None]
        nb_scored = len(scores)
        nb_erreurs = sum(1 for lead in leads_l4 if lead.scoring_erreur)
        nb_top = sum(1 for lead in leads_l4 if lead.top_lead)
        score_moyen = sum(scores) / nb_scored if nb_scored else 0.0
        return {
            "total": n,
            "scored": nb_scored,
            "scored_pct": round(100 * nb_scored / n, 1),
            "erreurs": nb_erreurs,
            "top_leads": nb_top,
            "top_pct": round(100 * nb_top / n, 1),
            "score_moyen": round(score_moyen, 1),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cout_total_eur": round(self.cout_total_eur, 4),
            "tokens_in": self.tokens_in_total,
            "tokens_out": self.tokens_out_total,
        }
