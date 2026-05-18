"""Tests des outils agent cold_mail (Instantly mocké, sessions fake)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import cold_mail as cm
from renoboost_leads.agent.tools import leads as ld
from renoboost_leads.agent.tools import sessions as sess
from renoboost_leads.instantly.staging import StagingStore


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(ld, "OUTPUT_ROOT", root)
    return root


def _ecrire_l4(d: Path, rows: list[dict]) -> None:
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with (d / "etage4_prospection.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def test_stage_secteur_inconnu(fake_root: Path) -> None:
    (fake_root / "s1").mkdir()
    _ecrire_l4(fake_root / "s1", [{"nom": "A", "email_dropcontact": "a@x.fr"}])
    res = cm.stage_cold_emails("s1", secteur="inexistant")
    assert "error" in res
    assert "indisponible" in res["error"] or "absent" in res["error"]


def test_stage_aucun_lead_avec_email(fake_root: Path) -> None:
    (fake_root / "s2").mkdir()
    _ecrire_l4(fake_root / "s2", [{"nom": "A"}, {"nom": "B"}])
    res = cm.stage_cold_emails("s2", secteur="compta")
    assert "warning" in res
    assert "aucun lead" in res["warning"]


def test_stage_drafte_et_persiste(fake_root: Path) -> None:
    d = fake_root / "s3"
    d.mkdir()
    _ecrire_l4(
        d,
        [
            {
                "nom": "ABC SARL",
                "siren": "100",
                "email_dropcontact": "marie@abc.fr",
                "nom_dirigeant_dropcontact": "Marie Dupont",
                "score_interet": "80",
            },
            {
                "nom": "XYZ SAS",
                "siren": "200",
                "email_dropcontact": "jean@xyz.fr",
                "nom_dirigeant_dropcontact": "Jean Martin",
                "score_interet": "75",
            },
        ],
    )
    res = cm.stage_cold_emails(
        "s3",
        secteur="compta",
        top_n=10,
        from_email="paul@x.fr",
        variables_globales={"telephone_paul": "06.11.22.33.44"},
    )
    assert res["items_count"] == 2
    assert res["staging_id"].startswith("stg_")
    # Vérifie persistance
    store = StagingStore()
    staging = store.load(res["staging_id"])
    assert staging.secteur == "compta"
    assert len(staging.items) == 2
    # Variable injectée présente dans le corps
    assert "06.11.22.33.44" in staging.items[0].corps
    # Personnalisation : prénom dans le corps
    corps_alice = next(i for i in staging.items if "marie@abc.fr" in i.email_dest)
    assert "Marie" in corps_alice.corps or "Marie Dupont" in corps_alice.corps


def test_list_stagings(fake_root: Path) -> None:
    d = fake_root / "s4"
    d.mkdir()
    _ecrire_l4(d, [{"nom": "A", "email_dropcontact": "a@x.fr", "score_interet": "90"}])
    cm.stage_cold_emails("s4", secteur="compta")
    res = cm.list_stagings()
    assert res["count"] >= 1
    assert "stagings" in res


def test_send_validated_aucun_valide(fake_root: Path) -> None:
    d = fake_root / "s5"
    d.mkdir()
    _ecrire_l4(d, [{"nom": "A", "email_dropcontact": "a@x.fr", "score_interet": "90"}])
    res = cm.stage_cold_emails("s5", secteur="compta")
    stg_id = res["staging_id"]
    # Aucun item n'est validé → send_validated ne doit rien envoyer
    envoi = cm.send_validated(stg_id)
    assert "warning" in envoi
    assert "rien à envoyer" in envoi["warning"]


def test_send_validated_pousse_a_instantly_dry_run(fake_root: Path) -> None:
    d = fake_root / "s6"
    d.mkdir()
    _ecrire_l4(
        d,
        [
            {"nom": "A", "siren": "100", "email_dropcontact": "a@x.fr",
             "nom_dirigeant_dropcontact": "Alice", "score_interet": "90"},
            {"nom": "B", "siren": "200", "email_dropcontact": "b@x.fr",
             "nom_dirigeant_dropcontact": "Bob", "score_interet": "85"},
        ],
    )
    res = cm.stage_cold_emails("s6", secteur="compta")
    stg_id = res["staging_id"]
    store = StagingStore()
    # Validate uniquement le premier
    store.set_etat(stg_id, "100", "valide")
    # Envoi
    envoi = cm.send_validated(stg_id)
    assert envoi["envoyes"] == 1
    assert envoi["dry_run"] is True
    assert envoi["campaign_id"].startswith("dry-")
    # L'item est marqué envoyé
    rechargé = store.load(stg_id)
    item_envoye = next(i for i in rechargé.items if i.lead_id == "100")
    assert item_envoye.etat == "envoye"
    assert item_envoye.campagne_instantly_id == envoi["campaign_id"]
    # L'autre reste en attente
    item_attente = next(i for i in rechargé.items if i.lead_id == "200")
    assert item_attente.etat == "en_attente"


def test_send_validated_staging_inexistant() -> None:
    res = cm.send_validated("stg_fantome")
    assert "error" in res


def test_read_metrics_dry_run() -> None:
    res = cm.read_campaign_metrics("any-id")
    assert "sent" in res
    assert res["dry_run"] is True


def test_pause_dry_run() -> None:
    res = cm.pause_campaign("any-id")
    assert res["status"] == "paused"


def test_outils_dans_registry() -> None:
    from renoboost_leads.agent import tools

    noms = {s["name"] for s in tools.all_schemas()}
    for nom in (
        "stage_cold_emails",
        "list_stagings",
        "send_validated",
        "read_campaign_metrics",
        "pause_campaign",
    ):
        assert nom in noms
    # Tous les noms ont aussi un dispatch
    dispatch = tools.all_dispatch()
    for nom in (
        "stage_cold_emails",
        "list_stagings",
        "send_validated",
        "read_campaign_metrics",
        "pause_campaign",
    ):
        assert nom in dispatch
