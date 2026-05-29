"""Tests de la détection de signaux 'flotte / véhicule électrique' (L3)."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.models import LeadStage2
from renoboost_leads.stage3_contacts.enricher import EnricheurStage3
from renoboost_leads.stage3_contacts.scraper import (
    ResultatScraping,
    ScraperContact,
    detecter_signaux_ve,
)


class TestDetecterSignauxVe:
    def test_aucun_signal_si_html_vide(self):
        assert detecter_signaux_ve(None) == []
        assert detecter_signaux_ve("") == []

    def test_aucun_signal_si_page_sans_marqueur(self):
        html = "<html><body><p>Boulangerie artisanale depuis 1985.</p></body></html>"
        assert detecter_signaux_ve(html) == []

    def test_detecte_irve_et_borne(self):
        html = (
            "<html><body><p>Nous installons des bornes de recharge "
            "(infrastructure IRVE) pour votre site.</p></body></html>"
        )
        signaux = detecter_signaux_ve(html)
        assert "IRVE" in signaux
        assert "borne de recharge" in signaux

    def test_insensible_accents_et_casse(self):
        html = "<p>Gestion de FLOTTE ÉLECTRIQUE et mobilité electrique.</p>"
        signaux = detecter_signaux_ve(html)
        assert "flotte électrique" in signaux
        assert "mobilité électrique" in signaux

    def test_pas_de_faux_positif_aper_dans_apercu(self):
        # "aperçu" ne doit pas déclencher le signal "APER" (frontière de mot).
        html = "<p>Voici un aperçu de nos services.</p>"
        assert "APER" not in detecter_signaux_ve(html)

    def test_ignore_le_contenu_des_scripts(self):
        html = "<html><body><script>var x = 'IRVE';</script><p>Hôtel.</p></body></html>"
        assert detecter_signaux_ve(html) == []

    def test_sans_doublon_singulier_pluriel(self):
        html = "<p>Des bornes de recharge et une borne de recharge.</p>"
        # Le pluriel et le singulier matchent le même libellé : un seul résultat.
        assert detecter_signaux_ve(html).count("borne de recharge") == 1


class TestScraperAccumuleSignaux:
    """scraper() doit accumuler les signaux VE sur toutes les pages visitées."""

    def _scraper_mocke(self, pages: dict[str, str]) -> ScraperContact:
        scraper = ScraperContact(rate_limit_seconds=0.0)
        scraper._fetch = lambda url: pages.get(url)  # type: ignore[method-assign]
        scraper._verifier_robots = lambda base_url, path: True  # type: ignore[method-assign]
        return scraper

    def test_signal_homepage_meme_si_email_sur_page_contact(self):
        base = "https://exemple.fr"
        pages = {
            base: "<p>Bornes de recharge sur notre parking.</p>",
            base + "/contact": "<p>Écrivez à contact@exemple.fr</p>",
        }
        scraper = self._scraper_mocke(pages)
        result = scraper.scraper(base)
        assert "contact@exemple.fr" in result.emails  # retour anticipé sur email
        assert "borne de recharge" in result.signaux_ve  # signal homepage conservé

    def test_signal_accumule_sur_page_secondaire(self):
        base = "https://exemple.fr"
        pages = {
            base: "<p>Bienvenue.</p>",
            base + "/contact": "<p>IRVE — contact@exemple.fr</p>",
        }
        scraper = self._scraper_mocke(pages)
        result = scraper.scraper(base)
        assert "IRVE" in result.signaux_ve

    def test_aucun_signal_si_site_inaccessible(self):
        scraper = self._scraper_mocke({})  # _fetch renvoie None partout
        result = scraper.scraper("https://exemple.fr")
        assert result.raison_echec == "site_inaccessible"
        assert result.signaux_ve == []


class _FakeScraper:
    """Scraper minimal renvoyant un ResultatScraping fixé."""

    def __init__(self, result: ResultatScraping):
        self._result = result

    def scraper(self, site_web: str | None) -> ResultatScraping:
        return self._result


class _FakeCache:
    """Cache en mémoire respectant l'interface get_place/store_place."""

    def __init__(self):
        self.store: dict[tuple[str, str], dict] = {}

    def get_place(self, place_id: str, stage: str):
        return self.store.get((place_id, stage))

    def store_place(self, place_id: str, stage: str, payload: dict):
        self.store[(place_id, stage)] = payload


def _l2(place_id: str = "A") -> LeadStage2:
    return LeadStage2(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=place_id,
        site_web="https://exemple.fr",
    )


class TestEnricheurPropageSignauxVe:
    def test_signaux_ve_propages_vers_l3(self):
        scraper = _FakeScraper(
            ResultatScraping(domaine="exemple.fr", signaux_ve=["IRVE"])
        )
        enricheur = EnricheurStage3(scraper=scraper)
        l3 = enricheur._enrichir_un_lead(_l2())
        assert l3.signaux_ve == ["IRVE"]

    def test_signaux_ve_survit_au_round_trip_cache(self):
        cache = _FakeCache()
        scraper = _FakeScraper(
            ResultatScraping(domaine="exemple.fr", signaux_ve=["IRVE", "ZFE"])
        )
        enricheur = EnricheurStage3(scraper=scraper, cache=cache)

        # 1er passage : scrape réel + mise en cache.
        l3a = enricheur._enrichir_un_lead(_l2())
        # 2e passage : le scraper renverrait vide, mais le cache doit restituer.
        enricheur.scraper = _FakeScraper(ResultatScraping(domaine="exemple.fr"))
        l3b = enricheur._enrichir_un_lead(_l2())

        assert l3a.signaux_ve == ["IRVE", "ZFE"]
        assert l3b.signaux_ve == ["IRVE", "ZFE"]
