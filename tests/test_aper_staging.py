"""Tests porte b — staging cold-mail Instantly depuis des leads APER."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.instantly.staging import StagingStore
from renoboost_leads.models import LeadAper
from renoboost_leads.parkings_aper.staging_instantly import stager_leads_aper


def _lead(
    nom="Parking Carrefour",
    *,
    top=True,
    score=80,
    email="dir@carrefour.fr",
    email_corps="Bonjour, vos 8000 m² de parking…",
    email_objet="Ombrières obligatoires sur votre parking",
    dirigeant_nom="Durand",
    siren="402111111",
):
    return LeadAper(
        place_id=f"p_{nom}",
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        siren=siren,
        top_lead=top,
        score_interet=score,
        emails_verifies=[email] if email else [],
        email_objet=email_objet,
        email_corps=email_corps,
        dirigeant_nom=dirigeant_nom,
        identifiant_parking="osm:way/123",
    )


def test_stage_top_leads_seulement(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    leads = [_lead(nom="A", top=True), _lead(nom="B", top=False, score=10)]
    res = stager_leads_aper(
        leads, secteur="aper_osm", session_id="sess1", from_email="paul@reno.fr", store=store
    )
    assert res.nb_stages == 1
    assert res.nb_sous_seuil == 1
    staging = store.load(res.staging_id)
    assert len(staging.items) == 1
    item = staging.items[0]
    assert item.email_dest == "dir@carrefour.fr"
    assert item.nom_dest == "Durand"
    assert item.sujet == "Ombrières obligatoires sur votre parking"
    assert item.etat == "en_attente"


def test_min_score_elargit(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    leads = [_lead(nom="B", top=False, score=65)]
    res = stager_leads_aper(
        leads, secteur="aper", session_id="s", from_email="x@y.fr", min_score=60, store=store
    )
    assert res.nb_stages == 1


def test_ecarte_sans_email(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    leads = [_lead(nom="NoMail", top=True, email=None)]
    res = stager_leads_aper(
        leads, secteur="aper", session_id="s", from_email="x@y.fr", store=store
    )
    assert res.nb_stages == 0
    assert res.nb_sans_email == 1


def test_email_dropcontact_prioritaire(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    lead = _lead(email="scrape@x.fr")
    lead.email_dropcontact = "verifie@x.fr"
    res = stager_leads_aper(
        [lead], secteur="aper", session_id="s", from_email="x@y.fr", store=store
    )
    item = store.load(res.staging_id).items[0]
    assert item.email_dest == "verifie@x.fr"


def test_fallback_objet_si_l4_absent(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    lead = _lead(nom="Parc Lidl", email_objet=None, email_corps=None)
    lead.pitch_propose = "Accroche de secours"
    res = stager_leads_aper(
        [lead], secteur="aper", session_id="s", from_email="x@y.fr", store=store
    )
    item = store.load(res.staging_id).items[0]
    assert "Parc Lidl" in item.sujet
    assert item.corps == "Accroche de secours"


def test_staging_visible_dans_le_store(tmp_path):
    store = StagingStore(dir_path=tmp_path)
    res = stager_leads_aper(
        [_lead()], secteur="aper_osm", session_id="sess", from_email="p@r.fr", store=store
    )
    listing = store.list()
    assert any(s["staging_id"] == res.staging_id for s in listing)
