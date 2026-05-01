"""Tests unitaires du générateur de patterns d'emails (étage 3)."""

from __future__ import annotations

from renoboost_leads.stage3_contacts.pattern_generator import (
    _normaliser_nom_pour_email,
    generer_patterns_fonctionnels,
    generer_patterns_nominatifs,
    generer_tous_patterns,
)


class TestNormalisation:
    def test_simple(self):
        assert _normaliser_nom_pour_email("Dupont") == "dupont"

    def test_accents(self):
        assert _normaliser_nom_pour_email("François") == "francois"
        assert _normaliser_nom_pour_email("Hervé") == "herve"

    def test_compose(self):
        assert _normaliser_nom_pour_email("Marie-Claire") == "marieclaire"

    def test_particules(self):
        assert _normaliser_nom_pour_email("DE LA TOUR") == "delatour"

    def test_vide(self):
        assert _normaliser_nom_pour_email("") is None
        assert _normaliser_nom_pour_email(None) is None


class TestPatternsNominatifs:
    def test_complet(self):
        patterns = generer_patterns_nominatifs("Marie", "Dupont", "hotel.fr")
        assert "marie.dupont@hotel.fr" in patterns
        assert "m.dupont@hotel.fr" in patterns
        assert "mdupont@hotel.fr" in patterns
        assert "marie@hotel.fr" in patterns
        assert "dupont@hotel.fr" in patterns

    def test_pas_de_doublons(self):
        patterns = generer_patterns_nominatifs("Marie", "Dupont", "hotel.fr")
        assert len(patterns) == len(set(patterns))

    def test_sans_domaine_vide(self):
        assert generer_patterns_nominatifs("Marie", "Dupont", None) == []

    def test_seulement_prenom(self):
        patterns = generer_patterns_nominatifs("Marie", None, "hotel.fr")
        assert "marie@hotel.fr" in patterns
        # Pas de pattern combiné
        assert all("@" in p for p in patterns)


class TestPatternsFonctionnels:
    def test_classique(self):
        patterns = generer_patterns_fonctionnels("hotel.fr")
        assert "direction@hotel.fr" in patterns
        assert "contact@hotel.fr" in patterns
        assert "commercial@hotel.fr" in patterns
        assert "communication@hotel.fr" in patterns

    def test_sans_domaine(self):
        assert generer_patterns_fonctionnels(None) == []
        assert generer_patterns_fonctionnels("") == []


class TestGenererTousPatterns:
    def test_complet_avec_dirigeant(self):
        patterns, contient_dir = generer_tous_patterns(
            prenom="Marie", nom="Dupont", domaine="hotel.fr"
        )
        # Au moins les nominatifs + fonctionnels
        assert "marie.dupont@hotel.fr" in patterns
        assert "direction@hotel.fr" in patterns
        assert contient_dir is True

    def test_sans_dirigeant(self):
        patterns, contient_dir = generer_tous_patterns(
            prenom=None, nom=None, domaine="hotel.fr"
        )
        # Que des fonctionnels
        assert "direction@hotel.fr" in patterns
        assert contient_dir is False

    def test_sans_domaine(self):
        patterns, contient_dir = generer_tous_patterns("Marie", "Dupont", None)
        assert patterns == []
        assert contient_dir is False

    def test_dedup(self):
        patterns, _ = generer_tous_patterns("Marie", "Dupont", "hotel.fr")
        assert len(patterns) == len(set(patterns))


class TestExtractionEmailsHtml:
    def test_email_basique(self):
        from renoboost_leads.stage3_contacts.scraper import extraire_emails_du_html
        html = "<html><body>Contactez-nous : contact@hotel.fr</body></html>"
        emails = extraire_emails_du_html(html)
        assert "contact@hotel.fr" in emails

    def test_filtre_extension_image(self):
        from renoboost_leads.stage3_contacts.scraper import email_est_valide
        # Cas typique : "logo@2x.png" capté par regex
        assert not email_est_valide("logo@2x.png")
        assert not email_est_valide("hero@1.5x.jpg")

    def test_filtre_domaines_parasites(self):
        from renoboost_leads.stage3_contacts.scraper import email_est_valide
        assert not email_est_valide("test@sentry.io")
        assert not email_est_valide("notify@wix.com")

    def test_mailto_extrait(self):
        from renoboost_leads.stage3_contacts.scraper import extraire_emails_du_html
        html = '<a href="mailto:direction@hotel.fr?subject=Hello">Contact</a>'
        emails = extraire_emails_du_html(html)
        assert "direction@hotel.fr" in emails

    def test_filtre_par_domaine(self):
        from renoboost_leads.stage3_contacts.scraper import extraire_emails_du_html
        html = "contact@hotel.fr et autre@example.com"
        emails = extraire_emails_du_html(html, domaine_attendu="hotel.fr")
        assert "contact@hotel.fr" in emails
        assert "autre@example.com" not in emails

    def test_extraire_domaine(self):
        from renoboost_leads.stage3_contacts.scraper import extraire_domaine
        assert extraire_domaine("https://www.hotel.fr/contact") == "hotel.fr"
        assert extraire_domaine("http://hotel.fr") == "hotel.fr"
        assert extraire_domaine("hotel.fr") == "hotel.fr"
        assert extraire_domaine(None) is None
