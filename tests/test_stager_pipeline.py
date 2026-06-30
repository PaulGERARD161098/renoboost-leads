"""Tests du stager cold-mail du pipeline principal (L4 → staging)."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.instantly.stager import stager_leads_l4
from renoboost_leads.instantly.staging import StagingStore
from renoboost_leads.models import LeadStage4


def _lead(**kw) -> LeadStage4:
    base = dict(
        place_id=kw.pop("place_id", "p1"),
        extraction_date=datetime.now(timezone.utc),
        nom=kw.pop("nom", "TRANSPORTS DUPONT"),
    )
    base.update(kw)
    return LeadStage4(**base)


def test_stage_retient_top_lead_avec_email(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    leads = [
        _lead(
            siren="111",
            dirigeant_prenom="Jean",
            dirigeant_nom="Martin",
            email_dropcontact="jean.martin@dupont.fr",
            top_lead=True,
            score_interet=80,
            email_objet="Objet test",
            email_corps="Bonjour Jean,\n\nCorps.",
        ),
    ]
    res = stager_leads_l4(
        leads, secteur="flotte", session_id="s1", from_email="henry@x.fr", store=store
    )
    assert res.nb_stages == 1
    s = store.load(res.staging_id)
    assert s.from_email == "henry@x.fr"
    it = s.items[0]
    assert it.lead_id == "111"
    assert it.email_dest == "jean.martin@dupont.fr"
    assert it.nom_dest == "Jean Martin"
    assert it.sujet == "Objet test"
    assert it.etat == "en_attente"


def test_stage_ecarte_sans_email_et_hors_filtre(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    leads = [
        _lead(siren="1", top_lead=True, score_interet=90),  # pas d'email
        _lead(
            siren="2",
            top_lead=True,
            score_interet=90,
            email_dropcontact="a@b.fr",
            hors_filtre_entreprise=True,  # jamais cold-mailé
        ),
    ]
    res = stager_leads_l4(
        leads, secteur="x", session_id="s", from_email="h@x.fr", store=store
    )
    assert res.nb_stages == 0
    assert res.nb_sans_email == 1
    assert res.nb_sous_seuil == 1  # le hors-filtre


def test_stage_min_score_elargit(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    leads = [
        _lead(siren="1", top_lead=False, score_interet=60, email_dropcontact="a@b.fr"),
    ]
    # sans min_score : non retenu (pas top_lead)
    r1 = stager_leads_l4(
        leads, secteur="x", session_id="s", from_email="h@x.fr", store=store
    )
    assert r1.nb_stages == 0
    # avec min_score=50 : retenu
    r2 = stager_leads_l4(
        leads, secteur="x", session_id="s", from_email="h@x.fr", min_score=50, store=store
    )
    assert r2.nb_stages == 1
