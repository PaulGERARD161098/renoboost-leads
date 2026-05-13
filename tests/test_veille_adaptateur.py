"""Tests conversion LigneAAA → LeadStage1."""

from __future__ import annotations

from datetime import date

from renoboost_leads.models import LeadStage1
from renoboost_leads.veille_immatriculations.adaptateur_lead_l2 import (
    lignaaa_vers_lead_stage1,
)
from renoboost_leads.veille_immatriculations.models import LigneAAA


def _ligne_complete() -> LigneAAA:
    return LigneAAA(
        date_immatriculation=date(2026, 5, 13),
        marque="TESLA",
        modele="MODEL Y",
        energie="EL",
        type_acquereur="M",
        siren="402111111",
        raison_sociale="SMI INDUSTRIE",
        code_postal="59100",
        commune="ROUBAIX",
    )


class TestAdaptateur:
    def test_retourne_lead_stage1(self):
        lead = lignaaa_vers_lead_stage1(_ligne_complete())
        assert isinstance(lead, LeadStage1)

    def test_nom_prend_raison_sociale(self):
        lead = lignaaa_vers_lead_stage1(_ligne_complete())
        assert lead.nom == "SMI INDUSTRIE"

    def test_nom_fallback_marque_modele_si_pas_raison(self):
        ligne = _ligne_complete()
        ligne.raison_sociale = None
        lead = lignaaa_vers_lead_stage1(ligne)
        assert lead.nom == "TESLA MODEL Y"

    def test_place_id_factice_stable(self):
        lead1 = lignaaa_vers_lead_stage1(_ligne_complete())
        lead2 = lignaaa_vers_lead_stage1(_ligne_complete())
        assert lead1.place_id == lead2.place_id
        assert lead1.place_id.startswith("AAA_2026-05-13_")
        assert "402111111" in lead1.place_id

    def test_secteur_recherche_inclut_energie(self):
        lead = lignaaa_vers_lead_stage1(_ligne_complete())
        assert "ve_el" in lead.secteur_recherche

    def test_ville_cp_repris(self):
        lead = lignaaa_vers_lead_stage1(_ligne_complete())
        assert lead.ville == "ROUBAIX"
        assert lead.code_postal == "59100"
