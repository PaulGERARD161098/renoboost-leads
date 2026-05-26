"""Tests de la préparation au lancement (composition → config lançable)."""

from __future__ import annotations

from pathlib import Path

from renoboost_leads.campagne import Campagne, persister_config_lancable
from renoboost_leads.config_loader import load_campaign_config
from renoboost_leads.models import CampaignConfig
from renoboost_leads.verticale import Verticale


def _verticale(slug: str = "vert-test", l3_5: bool = True, seuil: int = 70) -> Verticale:
    return Verticale.model_validate(
        {
            "verticale": {"slug": slug, "nom": "Test", "description": "desc"},
            "cible": {"type": "b2b", "detail": "PME test"},
            "offre": {"produit": "p", "argument_principal": "a", "ticket_moyen_eur": 1000},
            "cibles": {
                "secteurs_places": [{"type": "establishment", "query": "bureaux"}],
                "filtres_entreprise": {"naf_inclus": ["47"], "effectif_min": 10},
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


def _campagne(cid: str = "camp-test", slug: str = "vert-test") -> Campagne:
    return Campagne.model_validate(
        {
            "campagne": {"id": cid, "verticale_slug": slug, "nom": "Pilote"},
            "zone": {"type": "departement", "codes": ["59", "80"]},
            "volume": {"cible": 150},
            "budget": {"max_eur": 20.0},
        }
    )


def test_persiste_un_fichier_au_bon_nom(tmp_path: Path) -> None:
    chemin = persister_config_lancable(_campagne(), _verticale(), dest_dir=tmp_path)
    assert chemin == tmp_path / "campagne-camp-test.yaml"
    assert chemin.exists()


def test_config_persistee_se_recharge_en_campaignconfig(tmp_path: Path) -> None:
    chemin = persister_config_lancable(_campagne(), _verticale(seuil=85), dest_dir=tmp_path)
    cfg = load_campaign_config(chemin)
    assert isinstance(cfg, CampaignConfig)
    assert cfg.run.client_name == "camp-test"
    assert cfg.zone.codes == ["59", "80"]
    assert cfg.claude_scoring.seuil_top_lead == 85
    assert [s.query for s in cfg.secteurs] == ["bureaux"]
    assert cfg.budget.max_eur == 20.0


def test_l3_5_desactive_reporte_dans_la_config(tmp_path: Path) -> None:
    chemin = persister_config_lancable(_campagne(), _verticale(l3_5=False), dest_dir=tmp_path)
    cfg = load_campaign_config(chemin)
    assert cfg.stages.enable_stage_3_5_enrichment is False
