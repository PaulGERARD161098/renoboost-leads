"""Tests Bloc 3 — filtres entreprise paramétrables.

Couvre :
- mapping tranche effectif INSEE
- résolution labels forme juridique → codes
- préfixe NAF
- évaluation combinée sur LeadStage2
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from renoboost_leads.models import FiltresEntreprise, LeadStage2
from renoboost_leads.stage2_entreprises.filters import (
    _match_naf_prefixe,
    _resoudre_codes_formes,
    _tranche_overlap_range,
    evaluer_filtres_entreprise,
)


def _lead(**kwargs) -> LeadStage2:
    base = {
        "place_id": "ChIJ_test",
        "extraction_date": datetime.now(timezone.utc),
        "nom": "Test SAS",
    }
    base.update(kwargs)
    return LeadStage2(**base)


# ─────────────────────────────────────────────────────────────────────────────
# Mapping tranche effectif INSEE
# ─────────────────────────────────────────────────────────────────────────────


class TestTrancheEffectifOverlap:
    def test_tranche_21_50_99_dans_filtre_min_50(self):
        # tranche 21 = 50-99 salariés, filtre effectif_min=50 → overlap
        assert _tranche_overlap_range("21", effectif_min=50, effectif_max=None) is True

    def test_tranche_11_10_19_hors_filtre_min_50(self):
        # tranche 11 = 10-19, filtre min=50 → pas d'overlap
        assert _tranche_overlap_range("11", effectif_min=50, effectif_max=None) is False

    def test_tranche_22_100_199_dans_filtre_50_500(self):
        assert _tranche_overlap_range("22", effectif_min=50, effectif_max=500) is True

    def test_tranche_53_10000_plus_dans_filtre_min_5000(self):
        # tranche 53 = 10000+, max=None côté tranche
        assert _tranche_overlap_range("53", effectif_min=5000, effectif_max=None) is True

    def test_tranche_inconnue_renvoie_false(self):
        assert _tranche_overlap_range("XX", effectif_min=50, effectif_max=None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Résolution labels forme juridique
# ─────────────────────────────────────────────────────────────────────────────


class TestResolutionFormesJuridiques:
    def test_label_sas_resout_5710(self):
        assert "5710" in _resoudre_codes_formes(["SAS"])

    def test_label_sarl_resout_codes_multiples(self):
        codes = _resoudre_codes_formes(["SARL"])
        assert "5499" in codes and "5498" in codes

    def test_code_brut_pass_through(self):
        # Un code numérique est ajouté tel quel
        assert _resoudre_codes_formes(["5710"]) == {"5710"}

    def test_mix_label_et_code(self):
        codes = _resoudre_codes_formes(["SAS", "5410"])
        assert "5710" in codes and "5410" in codes

    def test_label_inconnu_ignore(self):
        assert _resoudre_codes_formes(["INCONNU"]) == set()

    def test_insensible_casse(self):
        assert _resoudre_codes_formes(["sas"]) == _resoudre_codes_formes(["SAS"])


# ─────────────────────────────────────────────────────────────────────────────
# Préfixe NAF
# ─────────────────────────────────────────────────────────────────────────────


class TestPrefixeNaf:
    def test_prefixe_court_2_chars(self):
        # "25" matche "25.62A" (industrie mécanique)
        assert _match_naf_prefixe("25.62A", ["25"]) is True

    def test_prefixe_long_code_exact(self):
        assert _match_naf_prefixe("25.62A", ["25.62A"]) is True
        assert _match_naf_prefixe("25.62B", ["25.62A"]) is False

    def test_prefixe_intermediaire(self):
        assert _match_naf_prefixe("25.62A", ["25.62"]) is True
        assert _match_naf_prefixe("25.63X", ["25.62"]) is False

    def test_code_none(self):
        assert _match_naf_prefixe(None, ["25"]) is False

    def test_liste_prefixes_vide(self):
        assert _match_naf_prefixe("25.62A", []) is False

    def test_un_prefixe_sur_plusieurs_suffit(self):
        assert _match_naf_prefixe("28.99B", ["25", "28", "29"]) is True


# ─────────────────────────────────────────────────────────────────────────────
# Évaluation complète des filtres
# ─────────────────────────────────────────────────────────────────────────────


class TestEvaluationFiltres:
    def test_filtres_vides_tout_passe(self):
        lead = _lead(tranche_effectif="01", code_naf="56.10A")
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise())
        assert ok is True
        assert raison == ""

    def test_effectif_min_50_lead_10_salaries_rejete(self):
        lead = _lead(tranche_effectif="11")  # 10-19
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(effectif_min=50))
        assert ok is False
        assert "effectif" in raison

    def test_effectif_min_50_lead_100_salaries_passe(self):
        lead = _lead(tranche_effectif="22")  # 100-199
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(effectif_min=50))
        assert ok is True

    def test_effectif_inconnu_rejete_si_option_active(self):
        lead = _lead(tranche_effectif=None)
        ok, raison = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(effectif_min=50, rejeter_effectif_inconnu=True)
        )
        assert ok is False
        assert "inconnu" in raison

    def test_effectif_inconnu_accepte_par_defaut(self):
        lead = _lead(tranche_effectif=None)
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(effectif_min=50))
        assert ok is True

    def test_tranche_nn_traitee_comme_inconnu(self):
        # INSEE code l'effectif non renseigné par "NN" : ne doit PAS être rejeté
        # comme une tranche hors plage (sinon la majorité des PME sautent).
        lead = _lead(tranche_effectif="NN")
        ok, _ = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(effectif_min=1, effectif_max=250)
        )
        assert ok is True

    def test_tranche_nn_rejetee_si_option_active(self):
        lead = _lead(tranche_effectif="NN")
        ok, raison = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(effectif_min=1, rejeter_effectif_inconnu=True)
        )
        assert ok is False
        assert "inconnu" in raison

    def test_effectif_inconnu_accepte_par_defaut_avec_tranche_inclus(self):
        lead = _lead(tranche_effectif=None)
        ok, _ = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(tranche_effectif_inclus=["22"])
        )
        assert ok is True

    def test_tranche_explicite_prioritaire_sur_min_max(self):
        # filtre min=50 (qui accepterait tranche 21) MAIS codes restreints à ["22"]
        lead = _lead(tranche_effectif="21")
        ok, _ = evaluer_filtres_entreprise(
            lead,
            FiltresEntreprise(effectif_min=50, tranche_effectif_inclus=["22"]),
        )
        assert ok is False  # tranche 21 pas dans ["22"]

    def test_naf_inclus_prefixe_court(self):
        lead = _lead(code_naf="25.62A")
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(naf_inclus=["25", "28", "29"]))
        assert ok is True

    def test_naf_inclus_lead_hors_prefixes(self):
        lead = _lead(code_naf="56.10A")
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(naf_inclus=["25", "28"]))
        assert ok is False
        assert "naf" in raison

    def test_naf_exclus(self):
        lead = _lead(code_naf="56.10A")  # restauration
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(naf_exclus=["56"]))
        assert ok is False
        assert "exclu" in raison

    def test_forme_juridique_inclus_par_label(self):
        lead = _lead(forme_juridique="5710")  # SAS
        ok, _ = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(forme_juridique_inclus=["SAS", "SA"])
        )
        assert ok is True

    def test_forme_juridique_inclus_rejette_autre(self):
        lead = _lead(forme_juridique="1000")  # EI
        ok, raison = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(forme_juridique_inclus=["SAS", "SA"])
        )
        assert ok is False
        assert "forme" in raison

    def test_forme_juridique_exclus_par_label(self):
        lead = _lead(forme_juridique="1000")  # EI
        ok, raison = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(forme_juridique_exclus=["EI", "EIRL"])
        )
        assert ok is False
        assert "exclu" in raison

    def test_forme_juridique_inclus_par_code_brut(self):
        lead = _lead(forme_juridique="5710")
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(forme_juridique_inclus=["5710"]))
        assert ok is True

    def test_multi_sites_only_lead_1_etablissement_rejete(self):
        lead = _lead(nb_etablissements=1)
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(multi_sites_only=True))
        assert ok is False
        assert "mono-site" in raison

    def test_multi_sites_only_lead_5_etablissements_passe(self):
        lead = _lead(nb_etablissements=5)
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(multi_sites_only=True))
        assert ok is True

    def test_multi_sites_only_nb_inconnu_rejete(self):
        lead = _lead(nb_etablissements=None)
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(multi_sites_only=True))
        assert ok is False
        assert "inconnu" in raison

    def test_ca_min_lead_au_dessus_passe(self):
        lead = _lead(chiffre_affaires=5_000_000)
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(ca_min=1_000_000))
        assert ok is True

    def test_ca_min_lead_en_dessous_rejete(self):
        lead = _lead(chiffre_affaires=200_000)
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(ca_min=1_000_000))
        assert ok is False
        assert "CA" in raison

    def test_ca_max_lead_au_dessus_rejete(self):
        lead = _lead(chiffre_affaires=500_000_000)
        ok, raison = evaluer_filtres_entreprise(lead, FiltresEntreprise(ca_max=50_000_000))
        assert ok is False
        assert "CA" in raison

    def test_ca_inconnu_accepte_par_defaut(self):
        lead = _lead(chiffre_affaires=None)
        ok, _ = evaluer_filtres_entreprise(lead, FiltresEntreprise(ca_min=1_000_000))
        assert ok is True

    def test_ca_inconnu_rejete_si_option_active(self):
        lead = _lead(chiffre_affaires=None)
        ok, raison = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(ca_min=1_000_000, rejeter_ca_inconnu=True)
        )
        assert ok is False
        assert "CA inconnu" in raison

    def test_categorie_inclus_passe(self):
        lead = _lead(categorie_entreprise="PME")
        ok, _ = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(categorie_entreprise_inclus=["PME", "ETI"])
        )
        assert ok is True

    def test_categorie_hors_liste_rejete(self):
        lead = _lead(categorie_entreprise="GE")
        ok, raison = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(categorie_entreprise_inclus=["PME", "ETI"])
        )
        assert ok is False
        assert "catégorie" in raison

    def test_categorie_inconnue_accepte_par_defaut(self):
        lead = _lead(categorie_entreprise=None)
        ok, _ = evaluer_filtres_entreprise(
            lead, FiltresEntreprise(categorie_entreprise_inclus=["PME"])
        )
        assert ok is True

    def test_multiples_raisons_agregees(self):
        # Effectif trop faible + mauvais NAF → 2 raisons agrégées
        lead = _lead(tranche_effectif="01", code_naf="56.10A")
        ok, raison = evaluer_filtres_entreprise(
            lead,
            FiltresEntreprise(effectif_min=50, naf_inclus=["25"]),
        )
        assert ok is False
        assert "effectif" in raison
        assert "naf" in raison
        assert " ; " in raison


# ─────────────────────────────────────────────────────────────────────────────
# Intégration : modèle CampaignConfig accepte filtres_entreprise
# ─────────────────────────────────────────────────────────────────────────────


class TestCampaignConfigIntegration:
    def test_campaign_config_accepte_filtres_entreprise(self):
        from renoboost_leads.models import CampaignConfig

        data = {
            "run": {
                "client_name": "test",
                "description": "x",
                "campaign_date": "2026-05-11",
            },
            "stages": {"enable_stage_1_decouverte": True},
            "secteurs": [{"type": "establishment", "query": "test"}],
            "zone": {"type": "departement", "codes": ["59"]},
            "volume": {"cible": 10},
            "budget": {"max_eur": 1.0},
            "filtres_entreprise": {
                "effectif_min": 50,
                "naf_inclus": ["25", "28"],
                "forme_juridique_inclus": ["SAS", "SARL"],
                "multi_sites_only": True,
            },
        }
        cfg = CampaignConfig.model_validate(data)
        assert cfg.filtres_entreprise.effectif_min == 50
        assert cfg.filtres_entreprise.naf_inclus == ["25", "28"]
        assert cfg.filtres_entreprise.multi_sites_only is True

    def test_campaign_config_filtres_entreprise_optionnel(self):
        """Backwards compat : YAML sans filtres_entreprise doit marcher."""
        from renoboost_leads.models import CampaignConfig

        data = {
            "run": {
                "client_name": "test",
                "description": "x",
                "campaign_date": "2026-05-11",
            },
            "stages": {"enable_stage_1_decouverte": True},
            "secteurs": [{"type": "establishment", "query": "test"}],
            "zone": {"type": "departement", "codes": ["59"]},
            "volume": {"cible": 10},
            "budget": {"max_eur": 1.0},
        }
        cfg = CampaignConfig.model_validate(data)
        # Filtre vide par défaut → tout passe
        assert cfg.filtres_entreprise.effectif_min is None
        assert cfg.filtres_entreprise.naf_inclus == []
        assert cfg.filtres_entreprise.multi_sites_only is False

    def test_lead_stage2_nouvelles_colonnes(self):
        lead = LeadStage2(
            place_id="x",
            extraction_date=datetime.now(timezone.utc),
            nom="Test",
        )
        assert lead.nb_etablissements is None
        assert lead.hors_filtre_entreprise is False
        assert lead.raison_hors_filtre is None


# Quick smoke test — un cas réaliste industriel Nord 59
class TestCasReelIndustrielNord:
    @pytest.fixture
    def filtres_industriels(self) -> FiltresEntreprise:
        return FiltresEntreprise(
            effectif_min=50,
            naf_inclus=["25", "28", "29"],
            forme_juridique_inclus=["SAS", "SA", "SARL"],
            forme_juridique_exclus=["EI", "EIRL"],
            multi_sites_only=False,
        )

    def test_lead_industriel_passe(self, filtres_industriels):
        lead = _lead(
            tranche_effectif="22",  # 100-199
            code_naf="25.62A",
            forme_juridique="5710",  # SAS
            nb_etablissements=1,
        )
        ok, _ = evaluer_filtres_entreprise(lead, filtres_industriels)
        assert ok is True

    def test_restaurant_rejete_naf(self, filtres_industriels):
        lead = _lead(
            tranche_effectif="22",
            code_naf="56.10A",  # restauration
            forme_juridique="5710",
        )
        ok, raison = evaluer_filtres_entreprise(lead, filtres_industriels)
        assert ok is False
        assert "naf" in raison

    def test_artisan_individuel_rejete_forme(self, filtres_industriels):
        lead = _lead(
            tranche_effectif="22",
            code_naf="25.62A",
            forme_juridique="1000",  # EI
        )
        ok, raison = evaluer_filtres_entreprise(lead, filtres_industriels)
        assert ok is False
        assert "forme" in raison
