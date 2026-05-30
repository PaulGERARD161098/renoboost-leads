"""Orchestrateur de l'étage de complétion (3.7).

Pour chaque lead :
- détecte les **trous** laissés par le pipeline classique (SIREN, dirigeant,
  NAF, effectif, CA, emails, téléphone) ;
- selon le ciblage, interroge le provider et **comble uniquement les champs
  vides** (*fill-if-empty*) — on ne réécrit jamais une valeur déjà trouvée ;
- trace la provenance et le coût. Flag-not-drop : aucun lead supprimé.
"""

from __future__ import annotations

from ..common.logger import get_logger
from ..models import LeadStage2
from .models import LeadComplete
from .provider import ProviderCompletion, ResultatCompletion

logger = get_logger(__name__)


class EtageCompletion:
    """Étage de complétion générique, piloté par un `ProviderCompletion`."""

    def __init__(self, provider: ProviderCompletion, only_gaps: bool = True):
        self.provider = provider
        # only_gaps=True : on n'appelle le provider QUE pour les leads à trous
        # (maximise le ROI). False : on complète tout (mode base de données).
        self.only_gaps = only_gaps
        self.nb_appeles = 0
        self.nb_repeches = 0
        self.cout_total_eur = 0.0

    # ── Détection des trous ───────────────────────────────────────
    @staticmethod
    def trous(lead: LeadStage2) -> list[str]:
        """Liste des champs de base manquants/incertains pour ce lead."""
        manques: list[str] = []
        if not lead.siren or getattr(lead, "match_incertain", False):
            manques.append("siren")
        if not lead.dirigeant_nom:
            manques.append("dirigeant_nom")
        if not lead.libelle_naf:
            manques.append("libelle_naf")
        if not lead.tranche_effectif and not lead.libelle_effectif:
            manques.append("tranche_effectif")
        if lead.chiffre_affaires is None:
            manques.append("chiffre_affaires")
        emails_pipeline = bool(getattr(lead, "emails_verifies", None)) or bool(
            getattr(lead, "email_dropcontact", None)
        )
        if not emails_pipeline:
            manques.append("emails")
        if not lead.telephone:
            manques.append("telephone")
        return manques

    def _eligible(self, lead: LeadStage2) -> bool:
        if getattr(lead, "hors_filtre_entreprise", False):
            return False
        if not self.only_gaps:
            return True
        return bool(self.trous(lead))

    # ── Remplissage fill-if-empty ─────────────────────────────────
    @staticmethod
    def _backfill(base: LeadComplete, res: ResultatCompletion) -> list[str]:
        """Comble les champs vides de `base` avec `res`. Retourne les champs remplis."""
        remplis: list[str] = []

        def _str_vide(v: object) -> bool:
            return v is None or (isinstance(v, str) and not v.strip())

        if _str_vide(base.siren) and res.siren:
            base.siren = res.siren
            remplis.append("siren")
        if _str_vide(base.dirigeant_nom) and res.dirigeant_nom:
            base.dirigeant_nom = res.dirigeant_nom
            remplis.append("dirigeant_nom")
        if _str_vide(base.dirigeant_prenom) and res.dirigeant_prenom:
            base.dirigeant_prenom = res.dirigeant_prenom
            remplis.append("dirigeant_prenom")
        if _str_vide(base.dirigeant_qualite) and res.dirigeant_qualite:
            base.dirigeant_qualite = res.dirigeant_qualite
            remplis.append("dirigeant_qualite")
        if _str_vide(base.code_naf) and res.code_naf:
            base.code_naf = res.code_naf
            remplis.append("code_naf")
        if _str_vide(base.libelle_naf) and res.libelle_naf:
            base.libelle_naf = res.libelle_naf
            remplis.append("libelle_naf")
        if _str_vide(base.tranche_effectif) and res.tranche_effectif:
            base.tranche_effectif = res.tranche_effectif
            remplis.append("tranche_effectif")
        if base.chiffre_affaires is None and res.chiffre_affaires is not None:
            base.chiffre_affaires = res.chiffre_affaires
            remplis.append("chiffre_affaires")
        if not base.emails_verifies and res.emails:
            base.emails_verifies = list(res.emails)
            base.nb_emails_verifies = len(res.emails)
            remplis.append("emails")
        if _str_vide(base.telephone) and res.telephone:
            base.telephone = res.telephone
            remplis.append("telephone")
        if _str_vide(base.site_web) and res.site_web:
            base.site_web = res.site_web
            remplis.append("site_web")
        if _str_vide(base.completion_linkedin) and res.linkedin:
            base.completion_linkedin = res.linkedin
            remplis.append("linkedin")
        return remplis

    # ── Boucle principale ─────────────────────────────────────────
    def enrichir(self, leads: list[LeadStage2]) -> list[LeadComplete]:
        resultats: list[LeadComplete] = []
        for lead in leads:
            base = LeadComplete(**lead.model_dump())
            if not self._eligible(lead):
                resultats.append(base)
                continue

            base.complete = True
            base.completion_provider = self.provider.nom
            self.nb_appeles += 1
            try:
                res = self.provider.chercher(
                    nom=lead.nom,
                    siren=lead.siren,
                    code_postal=lead.code_postal,
                    site_web=lead.site_web,
                )
            except Exception as e:  # noqa: BLE001 — un KO provider ne casse pas le run
                logger.warning("Complétion KO pour %s : %s", lead.nom, e)
                base.completion_erreur = str(e)[:200]
                resultats.append(base)
                continue

            self.cout_total_eur += self.provider.cout_par_lead_eur
            base.cout_completion_eur = self.provider.cout_par_lead_eur
            if res.trouve:
                remplis = self._backfill(base, res)
                base.completion_champs_remplis = remplis
                if remplis:
                    self.nb_repeches += 1
            resultats.append(base)

        logger.info(
            "Complétion (%s) : %d appelés / %d leads, %d repêchés, coût %.2f €",
            self.provider.nom,
            self.nb_appeles,
            len(leads),
            self.nb_repeches,
            self.cout_total_eur,
        )
        return resultats
