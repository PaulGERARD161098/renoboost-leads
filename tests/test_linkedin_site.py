"""Tests : extraction + appariement LinkedIn depuis le site (gratuit, vérifié)."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.exporter import _ligne_coordonnees, export_coordonnees_csv
from renoboost_leads.models import LeadStage35
from renoboost_leads.stage3_contacts.scraper import (
    apparier_linkedin,
    extraire_linkedin_du_html,
)


class TestExtractionLinkedIn:
    def test_extrait_profil_et_entreprise(self):
        html = """
        <footer>
          <a href="https://fr.linkedin.com/in/jean-dupont-12ab34/">LinkedIn</a>
          <a href="https://www.linkedin.com/company/acme-transports/">Société</a>
        </footer>
        """
        urls = extraire_linkedin_du_html(html)
        assert "https://www.linkedin.com/in/jean-dupont-12ab34" in urls
        assert "https://www.linkedin.com/company/acme-transports" in urls
        # profils /in/ avant /company/
        assert urls.index("https://www.linkedin.com/in/jean-dupont-12ab34") < urls.index(
            "https://www.linkedin.com/company/acme-transports"
        )

    def test_dedup_et_normalise(self):
        html = (
            'a <a href="http://linkedin.com/in/marie-martin">x</a> '
            'b https://www.linkedin.com/in/marie-martin/ c'
        )
        urls = extraire_linkedin_du_html(html)
        assert urls == ["https://www.linkedin.com/in/marie-martin"]

    def test_html_vide(self):
        assert extraire_linkedin_du_html("") == []
        assert extraire_linkedin_du_html("aucun lien ici") == []


class TestAppariementNom:
    def test_profil_dirigeant_matche_prenom_et_nom(self):
        urls = [
            "https://www.linkedin.com/in/jean-dupont-123",
            "https://www.linkedin.com/company/acme",
        ]
        dirigeant, entreprise = apparier_linkedin(urls, "Jean", "Dupont")
        assert dirigeant == "https://www.linkedin.com/in/jean-dupont-123"
        assert entreprise == "https://www.linkedin.com/company/acme"

    def test_profil_employe_non_attribue_au_dirigeant(self):
        # Le profil /in/ ne matche pas le dirigeant → on ne l'attribue pas
        # (fiabilité : pas de faux positif).
        urls = ["https://www.linkedin.com/in/sophie-durand-987"]
        dirigeant, entreprise = apparier_linkedin(urls, "Jean", "Dupont")
        assert dirigeant is None
        assert entreprise is None

    def test_accents_et_prenom_compose(self):
        urls = ["https://www.linkedin.com/in/jean-christophe-mery"]
        dirigeant, _ = apparier_linkedin(urls, "Jean-Christophe", "Méry")
        assert dirigeant == "https://www.linkedin.com/in/jean-christophe-mery"

    def test_nom_trop_court_ou_absent(self):
        urls = ["https://www.linkedin.com/in/jean-do"]
        assert apparier_linkedin(urls, "Jean", "Do") == (None, None)  # nom < 3
        assert apparier_linkedin(urls, None, None) == (None, None)


class TestExportCoordonnees:
    def _lead(self, **kw) -> LeadStage35:
        base = dict(
            place_id=kw.pop("place_id", "p1"),
            extraction_date=datetime.now(timezone.utc),
            nom=kw.pop("nom", "ACME TRANSPORTS"),
        )
        base.update(kw)
        return LeadStage35(**base)

    def test_linkedin_site_utilise_si_pas_de_dropcontact(self):
        lead = self._lead(
            dirigeant_prenom="Jean",
            dirigeant_nom="Dupont",
            dirigeant_qualite="Gérant",
            linkedin_dirigeant_site="https://www.linkedin.com/in/jean-dupont-123",
        )
        d = _ligne_coordonnees(lead.model_dump())
        assert d["linkedin_url"] == "https://www.linkedin.com/in/jean-dupont-123"
        assert d["prenom"] == "Jean"
        assert d["poste"] == "Gérant"

    def test_dropcontact_prioritaire_sur_site(self):
        lead = self._lead(
            dirigeant_prenom="Jean",
            dirigeant_nom="Dupont",
            linkedin_dirigeant_dropcontact="https://www.linkedin.com/in/verifie",
            linkedin_dirigeant_site="https://www.linkedin.com/in/site",
        )
        d = _ligne_coordonnees(lead.model_dump())
        assert d["linkedin_url"] == "https://www.linkedin.com/in/verifie"

    def test_email_verifie_seulement_pas_de_pattern(self):
        # Fiabilité : un pattern deviné ne doit JAMAIS remplir la colonne email
        # du livrable coordonnées (vérifié ou vide).
        lead = self._lead(dirigeant_prenom="Jean", dirigeant_nom="Dupont",
                          emails_candidats=["jean.dupont@acme.fr"])  # pattern seul
        d = _ligne_coordonnees(lead.model_dump())
        assert d["email"] is None
        # avec un email Dropcontact vérifié → il remplit
        lead2 = self._lead(email_dropcontact="verifie@acme.fr",
                           emails_candidats=["pattern@acme.fr"])
        assert _ligne_coordonnees(lead2.model_dump())["email"] == "verifie@acme.fr"

    def test_export_csv_colonnes_et_departement(self, tmp_path):
        lead = self._lead(code_postal="59000", ville="Lille", siren="123456789")
        p = export_coordonnees_csv([lead], tmp_path / "coord.csv")
        import csv as _csv

        rows = list(_csv.DictReader(open(p, encoding="utf-8-sig")))
        assert rows[0]["departement"] == "59"
        assert rows[0]["entreprise"] == "ACME TRANSPORTS"
        assert "linkedin_url" in rows[0]
