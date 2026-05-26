"""Tests de la composition Campagne + Verticale → CampaignConfig."""

from __future__ import annotations

import pytest

from renoboost_leads.campagne import Campagne, composer_campaign_config
from renoboost_leads.models import CampaignConfig
from renoboost_leads.verticale import Verticale


def _verticale(slug: str = "vert-test", l3_5: bool = True, seuil: int = 70) -> Verticale:
    return Verticale.model_validate(
        {
            "verticale": {"slug": slug, "nom": "Test", "description": "desc"},
            "cible": {"type": "b2b", "detail": "PME tertiaires test"},
            "offre": {
                "produit": "clim réversible",
                "argument_principal": "confort + économies",
                "ticket_moyen_eur": 15000,
            },
            "cibles": {
                "secteurs_places": [
                    {"type": "establishment", "query": "bureaux"},
                    {"type": "restaurant", "query": "restaurant"},
                ],
                "filtres_entreprise": {"naf_inclus": ["47", "56"], "effectif_min": 10},
            },
            "signaux": ["signal"],
            "qualification": {"seuil_score_top": seuil, "criteres_top": ["c1"]},
            "enrichissements": {"l3_5_dropcontact": l3_5},
            "ton_mail": {"registre": "pro", "longueur_mots": 100, "attaque": "a", "cta": "c"},
            "sequence": {"j0": {"template": "t", "sujet": "s"}},
            "budget_typique": {
                "volume_cible": 100,
                "cout_pipeline_eur": 10,
                "cout_avec_l3_5_eur": 20,
            },
        }
    )


def _campagne(slug: str = "vert-test") -> Campagne:
    return Campagne.model_validate(
        {
            "campagne": {"id": "camp-test", "verticale_slug": slug, "nom": "Pilote"},
            "zone": {"type": "departement", "codes": ["59", "80"]},
            "volume": {"cible": 150},
            "budget": {"max_eur": 20.0},
        }
    )


def test_compose_produit_config_valide() -> None:
    cfg = composer_campaign_config(_campagne(), _verticale())
    assert isinstance(cfg, CampaignConfig)
    assert cfg.run.client_name == "camp-test"
    # secteurs + filtres viennent de la verticale
    assert [s.query for s in cfg.secteurs] == ["bureaux", "restaurant"]
    assert cfg.filtres_entreprise.naf_inclus == ["47", "56"]
    # zone / volume / budget viennent de la campagne
    assert cfg.zone.codes == ["59", "80"]
    assert cfg.volume.cible == 150
    assert cfg.budget.max_eur == 20.0


def test_seuil_repris_de_la_verticale() -> None:
    cfg = composer_campaign_config(_campagne(), _verticale(seuil=85))
    assert cfg.claude_scoring.seuil_top_lead == 85


def test_l3_5_actif_suit_la_verticale() -> None:
    assert composer_campaign_config(
        _campagne(), _verticale(l3_5=True)
    ).stages.enable_stage_3_5_enrichment is True
    assert composer_campaign_config(
        _campagne(), _verticale(l3_5=False)
    ).stages.enable_stage_3_5_enrichment is False


def test_contexte_client_injecte() -> None:
    cfg = composer_campaign_config(_campagne(), _verticale())
    assert cfg.claude_scoring.contexte_client is not None
    assert "clim réversible" in cfg.claude_scoring.contexte_client


def test_slug_mismatch_leve_valueerror() -> None:
    with pytest.raises(ValueError, match="≠ campagne.verticale_slug"):
        composer_campaign_config(_campagne("vert-test"), _verticale("autre-slug"))
