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

import re
import time
from typing import Any

from ..common.budget_guard import BudgetExceededError
from ..common.cache import SessionCache
from ..common.logger import get_logger
from ..models import FiltresEntreprise, LeadStage1, LeadStage2
from .filters import evaluer_filtres_entreprise
from .mapper import candidat_to_l2_fields
from .matcher import selectionner_meilleur_candidat
from .pappers_client import PappersClient, PappersError
from .recherche_client import RechercheEntreprisesClient
from .referentiel_chaines import detecter_chaine, note_chaine_standard

logger = get_logger(__name__)

# Sépare la "marque" des qualificatifs de site Google (" - Siège social",
# " | Logistique", " — Usine"...). On exige des espaces autour du séparateur
# pour ne PAS couper les noms à trait d'union collé (Saint-Gobain, Neuville-en-F).
_SEP_QUALIFICATIF = re.compile(r"\s+[-–—|]\s+.*$")

# Qualificatif de site SANS tiret, fréquent sur les gros sites industriels
# ("Candia Usine de Cambrai", "X Plateforme logistique", "Y Site de Lens") :
# on coupe à partir du qualificatif pour ne garder que la marque qui précède.
_SITE_QUALIFICATIF = re.compile(
    r"\s+(usine|site|plate?-?forme|entrep[ôo]t|d[ée]p[ôo]t|[ée]tablissement)\b.*$",
    flags=re.IGNORECASE,
)

# Descripteurs d'activité industrielle en tête de nom ("Sucrerie Tereos" → Tereos).
# Liste volontairement restreinte à des mots qui ne sont presque jamais la raison
# sociale elle-même (≠ "Établissements", "Compagnie", "Société"...).
_LEADING_ACTIVITE = re.compile(
    r"^(sucrerie|laiterie|fromagerie|brasserie|distillerie|raffinerie|abattoir|"
    r"minoterie|malterie|conserverie|fonderie|aci[ée]rie|verrerie|cimenterie|"
    r"papeterie|scierie|tannerie|tuilerie|huilerie)\s+(?=\S)",
    flags=re.IGNORECASE,
)


def nettoyer_nom_pour_recherche(nom: str | None) -> str:
    """Nettoie un nom Google pour une recherche SIREN de repli.

    Retire le contenu entre parenthèses, coupe aux qualificatifs de site (avec ou
    sans tiret), enlève les descripteurs d'activité en tête et quelques mots
    parasites ('France', 'siège social'). Sert UNIQUEMENT au fallback : ne
    remplace pas la requête primaire, et un éventuel sur-nettoyage est rattrapé
    par le score de matching (flag match_incertain si < seuil).
    """
    if not nom:
        return ""
    s = re.sub(r"\([^)]*\)", " ", nom)
    s = _SEP_QUALIFICATIF.sub("", s)
    s = _SITE_QUALIFICATIF.sub("", s)
    s = re.sub(r"\b(france|si[èe]ge social)\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    # Strip d'un descripteur d'activité en tête seulement s'il reste un nom derrière.
    s_sans_activite = _LEADING_ACTIVITE.sub("", s).strip()
    if s_sans_activite:
        s = s_sans_activite
    return s or nom.strip()


class EnricheurStage2:
    """Pipeline d'enrichissement L1 → L2."""

    def __init__(
        self,
        client: RechercheEntreprisesClient,
        cache: SessionCache | None = None,
        callback_save_incremental=None,
        filtres_entreprise: FiltresEntreprise | None = None,
        pappers_client: PappersClient | None = None,
    ):
        """
        Args:
            client: instance du client API
            cache: cache SQLite pour éviter les re-paiements
            callback_save_incremental: fonction appelée tous les 20 leads (pour sauvegarde)
            filtres_entreprise: filtres B3 à appliquer après enrichissement
                (default = FiltresEntreprise() vide → aucun flag posé)
            pappers_client: client Pappers optionnel. Si fourni, il est interrogé
                en fallback PAYANT quand le matching gratuit échoue ou reste
                incertain. Absent → aucun appel Pappers.
        """
        self.client = client
        self.cache = cache
        self.callback_save = callback_save_incremental
        self.filtres_entreprise = filtres_entreprise or FiltresEntreprise()
        self.pappers_client = pappers_client
        # Métriques fallback Pappers (lues par le CLI pour les stats/budget).
        self.nb_fallback_pappers = 0
        self.cout_pappers_eur = 0.0
        # Coupe-circuit : passe à True dès que le budget Pappers est épuisé,
        # pour ne plus retenter d'appels sur les leads suivants.
        self._pappers_budget_epuise = False

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
        query = query.strip()
        nom_clean = nettoyer_nom_pour_recherche(lead.nom)

        try:
            results = self.client.rechercher(
                query=query,
                code_postal=lead.code_postal,
                per_page=10,
            )
            # Fallback ADDITIF : si la requête primaire ne renvoie rien, on retente
            # avec le nom nettoyé (sans ville ni qualificatif de site). Ne se
            # déclenche que sur résultat vide → ne peut pas faire régresser.
            if not results and nom_clean and nom_clean != query:
                results = self.client.rechercher(
                    query=nom_clean,
                    code_postal=lead.code_postal,
                    per_page=10,
                )
        except Exception as e:  # noqa: BLE001
            # Échec API (5xx/429/réseau, déjà retryé côté client) : on NE cache PAS.
            # Sinon une relance après panne data.gouv lirait un résultat vide en
            # cache et n'interrogerait jamais l'API rétablie.
            logger.warning("Erreur API pour %r : %s — non mis en cache", lead.nom, e)
            return []

        # Stockage en cache : uniquement les réponses réussies (y compris une
        # liste vide légitime = "aucune entreprise trouvée" pour cette query).
        if self.cache:
            self.cache.store_place(
                place_id=cache_key,
                stage="stage2_search",
                payload={"results": results},
            )

        return results

    def _appliquer_filtres(self, lead_l2: LeadStage2) -> LeadStage2:
        """Évalue les filtres entreprise (B3) et pose le flag hors_filtre si besoin.

        On évalue toujours, y compris pour les chaînes — si filtres_entreprise
        est vide (défaut), aucun flag n'est posé. Pour les chaînes / leads sans
        SIREN, les filtres "données manquantes" déclencheront naturellement le
        flag avec une raison parlante (ex: "effectif inconnu ; naf=None ...").
        """
        passe, raison = evaluer_filtres_entreprise(lead_l2, self.filtres_entreprise)
        if not passe:
            lead_l2.hors_filtre_entreprise = True
            lead_l2.raison_hors_filtre = raison
        return lead_l2

    def _fallback_pappers(
        self,
        lead: LeadStage1,
        best: dict[str, Any] | None,
        score: float,
        incertain: bool,
    ) -> tuple[dict[str, Any] | None, float, bool]:
        """Interroge Pappers en repli et garde le MEILLEUR des deux scores.

        Ne fait rien (renvoie l'entrée inchangée) si aucun client Pappers n'est
        fourni ou si le budget Pappers est déjà épuisé. Best-effort : toute
        erreur Pappers est loguée sans interrompre le run.
        """
        if self.pappers_client is None or self._pappers_budget_epuise:
            return best, score, incertain

        query = nettoyer_nom_pour_recherche(lead.nom) or (lead.nom or "")
        if lead.ville:
            query = f"{query} {lead.ville}".strip()

        try:
            candidats_pappers = self.pappers_client.rechercher(
                query=query,
                code_postal=lead.code_postal,
            )
        except BudgetExceededError as e:
            logger.warning("Budget Pappers épuisé, fallback désactivé : %s", e)
            self._pappers_budget_epuise = True
            return best, score, incertain
        except PappersError as e:
            logger.warning("Échec fallback Pappers pour %r : %s", lead.nom, e)
            return best, score, incertain

        # L'appel a été facturé (budget débité côté client) → on comptabilise.
        self.nb_fallback_pappers += 1
        self.cout_pappers_eur += self.pappers_client.config.cout_par_appel_eur

        if not candidats_pappers:
            return best, score, incertain

        p_best, p_score, p_incertain = selectionner_meilleur_candidat(
            candidats=candidats_pappers,
            nom_cible=lead.nom,
            code_postal_cible=lead.code_postal,
            ville_cible=lead.ville,
        )

        # On ne remplace que si Pappers fait STRICTEMENT mieux.
        if p_best is not None and p_score > score:
            return p_best, p_score, p_incertain
        return best, score, incertain

    def _enrichir_un_lead(self, lead: LeadStage1) -> LeadStage2:
        """Enrichit un lead L1 → L2."""
        # Étape 1 — Détection chaîne
        est_chaine, groupe = detecter_chaine(lead.nom)
        if est_chaine:
            return self._appliquer_filtres(
                LeadStage2(
                    **lead.model_dump(),
                    flag_chaine=True,
                    note_chaine=f"{note_chaine_standard()} Groupe identifié : {groupe}.",
                    match_incertain=True,  # Pas de SIREN local fiable
                )
            )

        # Étape 2 — Recherche API gratuite (data.gouv)
        candidats = self._chercher_avec_cache(lead)

        # Étape 3 — Scoring
        best, score, incertain = selectionner_meilleur_candidat(
            candidats=candidats,
            nom_cible=lead.nom,
            code_postal_cible=lead.code_postal,
            ville_cible=lead.ville,
        )

        # Étape 3 bis — Fallback Pappers (PAYANT) si le gratuit échoue/doute.
        if best is None or incertain:
            best, score, incertain = self._fallback_pappers(lead, best, score, incertain)

        # Étape 4 — Mapping
        if best is None:
            return self._appliquer_filtres(
                LeadStage2(
                    **lead.model_dump(),
                    score_matching=0.0,
                    match_incertain=True,
                )
            )

        l2_fields = candidat_to_l2_fields(best)
        return self._appliquer_filtres(
            LeadStage2(
                **lead.model_dump(),
                **l2_fields,
                score_matching=round(score, 1),
                match_incertain=incertain,
            )
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
        # BUG B4 fix : exclure chaines du denominateur pour SIREN et dirigeant
        n_non_chaines = n - nb_chaines
        denom = n_non_chaines if n_non_chaines > 0 else 1
        return {
            "total": n,
            "siren_trouve": nb_siren,
            "siren_pct": round(100 * nb_siren / denom, 1),
            "chaines": nb_chaines,
            "chaines_pct": round(100 * nb_chaines / n, 1),
            "dirigeant_trouve": nb_dirigeant,
            "dirigeant_pct": round(100 * nb_dirigeant / denom, 1),
        }
