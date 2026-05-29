"""Enricheur Societeinfo : LeadStage2 → LeadSocieteinfo.

Flag-not-drop : aucun lead n'est supprimé. Les leads non éligibles ou non
trouvés ressortent en LeadSocieteinfo avec les champs `societeinfo_*` à None.

Stratégie de ciblage (`only_incertain`) :
- True (défaut) : on n'appelle l'API QUE pour les leads dont le match SIREN
  gratuit est absent ou incertain (`siren` vide ou `match_incertain=True`),
  et qui passent les filtres entreprise. Maximise le ROI (on paie là où le
  gratuit a échoué).
- False : on enrichit tous les leads fournis (mode « base de données »).
"""

from __future__ import annotations

from ..common.logger import get_logger
from ..models import LeadSocieteinfo, LeadStage2
from .client import SocieteinfoClient

logger = get_logger(__name__)


class EnricheurSocieteinfo:
    """Pipeline d'enrichissement firmographique via Societeinfo."""

    def __init__(self, client: SocieteinfoClient, only_incertain: bool = True):
        self.client = client
        self.only_incertain = only_incertain
        self.nb_enrichis = 0
        self.nb_trouves = 0
        self.cout_total_eur = 0.0

    def _eligible(self, lead: LeadStage2) -> bool:
        if getattr(lead, "hors_filtre_entreprise", False):
            return False
        if not self.only_incertain:
            return True
        return (not lead.siren) or bool(getattr(lead, "match_incertain", False))

    def enrichir(self, leads: list[LeadStage2]) -> list[LeadSocieteinfo]:
        resultats: list[LeadSocieteinfo] = []
        cout_unit = getattr(self.client, "cout_par_lead_eur", None)
        if cout_unit is None:
            cout_unit = getattr(getattr(self.client, "config", None), "cout_par_lead_eur", 0.0)

        for lead in leads:
            base = LeadSocieteinfo(**lead.model_dump())
            if not self._eligible(lead):
                resultats.append(base)
                continue

            try:
                res = self.client.enrichir(
                    nom=lead.nom,
                    siren=lead.siren,
                    code_postal=lead.code_postal,
                    site_web=lead.site_web,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Societeinfo KO pour %s : %s", lead.nom, e)
                base.enrichi_societeinfo = True
                base.societeinfo_erreur = str(e)[:200]
                self.nb_enrichis += 1
                resultats.append(base)
                continue

            self.nb_enrichis += 1
            self.cout_total_eur += cout_unit
            base.enrichi_societeinfo = True
            base.cout_societeinfo_eur = cout_unit
            if res.trouve:
                self.nb_trouves += 1
                base.societeinfo_siren = res.siren
                base.societeinfo_naf = res.naf
                base.societeinfo_libelle_naf = res.libelle_naf
                base.societeinfo_effectif = res.effectif
                base.societeinfo_chiffre_affaires = res.chiffre_affaires
                base.societeinfo_dirigeant = res.dirigeant
                base.societeinfo_email = res.email
                base.societeinfo_emails = res.emails or []
                base.societeinfo_telephone = res.telephone
                base.societeinfo_site_web = res.site_web
                base.societeinfo_linkedin = res.linkedin
                # Comble le SIREN manquant du lead avec celui de Societeinfo.
                if not base.siren and res.siren:
                    base.siren = res.siren
            resultats.append(base)

        logger.info(
            "Societeinfo : %d enrichis / %d leads (%d trouvés), coût %.2f €",
            self.nb_enrichis,
            len(leads),
            self.nb_trouves,
            self.cout_total_eur,
        )
        return resultats
