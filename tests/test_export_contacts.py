"""Tests vue/export « contacts » + notion de lead joignable."""

from __future__ import annotations

import csv
from datetime import datetime, timezone

from renoboost_leads.exporter import (
    COLONNES_CONTACTS,
    export_contacts_csv,
    lead_est_joignable,
)
from renoboost_leads.models import LeadStage35


def _lead(**kw) -> LeadStage35:
    base = dict(
        place_id=kw.pop("place_id", "p1"),
        extraction_date=datetime.now(timezone.utc),
        nom=kw.pop("nom", "TRANSPORTS DUPONT"),
    )
    base.update(kw)
    return LeadStage35(**base)


class TestLigneContact:
    def test_priorite_dropcontact_et_canaux(self, tmp_path):
        lead = _lead(
            ville="Lille",
            dirigeant_prenom="Jean",   # repli
            prenom_dirigeant_dropcontact="Adélaïde",  # prioritaire
            nom_dirigeant_dropcontact="Gros",
            email_dropcontact="a.gros@dupont.fr",
            telephone_direct_dropcontact="+33 3 20 00 00 00",
            linkedin_dirigeant_dropcontact="https://linkedin.com/in/agros",
        )
        out = export_contacts_csv([lead], tmp_path / "c.csv")
        rows = list(csv.DictReader(open(out, encoding="utf-8-sig")))
        r = rows[0]
        assert r["prenom"] == "Adélaïde"   # Dropcontact prime sur le repli
        assert r["nom_contact"] == "Gros"
        assert r["email"] == "a.gros@dupont.fr"
        assert r["linkedin_url"] == "https://linkedin.com/in/agros"
        assert r["joignable"] == "VRAI"
        assert "email" in r["canaux"] and "tel" in r["canaux"] and "linkedin" in r["canaux"]

    def test_repli_dirigeant_sirene_quand_pas_de_dropcontact(self, tmp_path):
        lead = _lead(dirigeant_prenom="Marc", dirigeant_nom="Petit")
        out = export_contacts_csv([lead], tmp_path / "c.csv")
        r = list(csv.DictReader(open(out, encoding="utf-8-sig")))[0]
        assert r["prenom"] == "Marc" and r["nom_contact"] == "Petit"

    def test_colonnes_attendues(self, tmp_path):
        out = export_contacts_csv([_lead()], tmp_path / "c.csv")
        with open(out, encoding="utf-8-sig") as fh:
            header = fh.readline().strip().lstrip("﻿").split(",")
        assert header == COLONNES_CONTACTS
        assert "linkedin_url" in header and "telephone" in header


class TestJoignable:
    def test_email_seul_joignable(self):
        assert lead_est_joignable(_lead(email_dropcontact="x@y.fr")) is True

    def test_telephone_seul_joignable(self):
        # Correctif « téléphone = contact valide » : pas besoin d'email.
        assert lead_est_joignable(_lead(telephone_direct_dropcontact="+33 1 23")) is True

    def test_linkedin_seul_joignable(self):
        assert lead_est_joignable(
            _lead(linkedin_dirigeant_dropcontact="https://linkedin.com/in/x")
        ) is True

    def test_aucun_canal_non_joignable(self):
        assert lead_est_joignable(_lead(nom="SANS CONTACT")) is False
