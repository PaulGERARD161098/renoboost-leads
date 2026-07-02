"""Tests de la détection de signaux 'flotte / véhicule électrique' (L3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from renoboost_leads.models import LeadStage2
from renoboost_leads.stage3_contacts.enricher import EnricheurStage3
from renoboost_leads.stage3_contacts.scraper import (
    MOTS_CLES_VE,
    ResultatScraping,
    ScraperContact,
    compiler_signaux_ve,
    detecter_signaux_ve,
)


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Résout tout hôte vers une IP publique par défaut (garde-fou SSRF anti
    coupure réseau en test). Les tests SSRF dédiés surchargent ce stub."""
    from renoboost_leads.stage3_contacts import scraper as _scr

    monkeypatch.setattr(
        _scr.socket,
        "getaddrinfo",
        lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
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


class TestScrapingL3Config:
    """Validation du bloc de config `scraping_l3`."""

    def test_regex_invalide_rejetee(self):
        import pytest
        from pydantic import ValidationError

        from renoboost_leads.models import ScrapingL3

        with pytest.raises(ValidationError, match="regex invalide"):
            ScrapingL3(signaux_ve={"bug": "[unclosed"})

    def test_defaut_signaux_ve_none(self):
        from renoboost_leads.models import ScrapingL3

        assert ScrapingL3().signaux_ve is None


class TestSignauxVePilotables:
    """Les mots-clés VE sont configurables par YAML (chantier A)."""

    def test_compiler_none_renvoie_defaut(self):
        regex = compiler_signaux_ve(None)
        assert set(regex) == set(MOTS_CLES_VE)

    def test_compiler_vide_desactive_la_detection(self):
        regex = compiler_signaux_ve({})
        assert regex == {}
        html = "<p>Bornes de recharge IRVE partout.</p>"
        assert detecter_signaux_ve(html, regex) == []

    def test_mots_cles_custom_detectes(self):
        custom = {"panneaux solaires": r"\bpanneaux? solaires?\b"}
        regex = compiler_signaux_ve(custom)
        html = "<p>Installation de panneaux solaires en toiture.</p>"
        signaux = detecter_signaux_ve(html, regex)
        assert signaux == ["panneaux solaires"]
        # Les mots VE par défaut ne s'appliquent plus quand un set custom est fourni.
        assert "IRVE" not in detecter_signaux_ve("<p>IRVE</p>", regex)

    def test_scraper_utilise_les_mots_cles_custom(self):
        scraper = ScraperContact(
            rate_limit_seconds=0.0,
            signaux_ve={"hydrogène": r"\bhydrogene\b"},
        )
        scraper._fetch = lambda url: "<p>Station hydrogène.</p>"  # type: ignore[method-assign]
        scraper._verifier_robots = lambda base_url, path: True  # type: ignore[method-assign]
        result = scraper.scraper("https://exemple.fr")
        assert "hydrogène" in result.signaux_ve


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


class _SlowScraper:
    """Scraper qui dort un délai dépendant du site → l'ordre de complétion
    diffère de l'ordre d'entrée (teste réellement la préservation d'ordre)."""

    def __init__(self, delais: dict[str, float]):
        self._delais = delais

    def scraper(self, site_web: str | None) -> ResultatScraping:
        import time as _t

        _t.sleep(self._delais.get(site_web or "", 0.0))
        domaine = (site_web or "").replace("https://", "").rstrip("/")
        return ResultatScraping(domaine=domaine)


def _l2_site(place_id: str, site: str) -> LeadStage2:
    return LeadStage2(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=place_id,
        site_web=site,
    )


class TestEnricheurParallele:
    def _jeu(self):
        # Les premiers leads dorment le plus longtemps → finiraient en dernier
        # sans préservation d'ordre.
        leads = [_l2_site(f"P{i}", f"https://site{i}.fr") for i in range(6)]
        delais = {f"https://site{i}.fr": (6 - i) * 0.02 for i in range(6)}
        return leads, delais

    def test_ordre_preserve_en_parallele(self):
        leads, delais = self._jeu()
        enricheur = EnricheurStage3(scraper=_SlowScraper(delais), max_workers=4)
        res = enricheur.enrichir(leads)
        assert [l3.place_id for l3 in res] == [lead.place_id for lead in leads]

    def test_parite_sequentiel_parallele(self):
        leads, delais = self._jeu()
        seq = EnricheurStage3(scraper=_SlowScraper(delais), max_workers=1).enrichir(leads)
        par = EnricheurStage3(scraper=_SlowScraper(delais), max_workers=4).enrichir(leads)
        assert [(x.place_id, x.domaine_extrait) for x in seq] == [
            (x.place_id, x.domaine_extrait) for x in par
        ]

    def test_callback_incremental_appele_en_parallele(self):
        leads = [_l2_site(f"Q{i}", f"https://d{i}.fr") for i in range(40)]
        vus: list[int] = []
        enricheur = EnricheurStage3(
            scraper=_SlowScraper({}),
            callback_save_incremental=lambda partial: vus.append(len(partial)),
            max_workers=8,
        )
        enricheur.enrichir(leads)
        # Sauvegarde tous les 20 leads (cf. boucle enrichir).
        assert vus == [20, 40]


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


def test_403_allowlist_donne_reseau_bloque():
    """403 + mention allowlist -> raison_echec dediee (blocage reseau, pas site KO)."""
    from renoboost_leads.stage3_contacts.scraper import (
        RESEAU_BLOQUE,
        SITE_INACCESSIBLE,
        ScraperContact,
    )

    class _Resp:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

    def _scraper(resp):
        sc = ScraperContact(rate_limit_seconds=0.0)
        sc.session.get = lambda *a, **k: resp  # type: ignore[assignment]
        return sc

    res = _scraper(_Resp(403, "Host not in allowlist")).scraper("http://acme.fr")
    assert res.raison_echec == RESEAU_BLOQUE

    res2 = _scraper(_Resp(403, "Forbidden")).scraper("http://acme.fr")
    assert res2.raison_echec == SITE_INACCESSIBLE


def test_verifier_robots_utilise_timeout_et_ne_fige_pas():
    """[S3c] robots.txt lu via session.get(timeout) ; injoignable → autorisé."""
    import requests

    from renoboost_leads.stage3_contacts.scraper import (
        TIMEOUT_SECONDS,
        ScraperContact,
    )

    captured: dict = {}

    class _Resp:
        status_code = 404
        text = ""

    def _get(url, timeout=None, **k):
        captured["url"] = url
        captured["timeout"] = timeout
        return _Resp()

    sc = ScraperContact(rate_limit_seconds=0.0)
    sc.session.get = _get  # type: ignore[assignment]
    # 404 robots.txt → autorisé par défaut, avec timeout posé.
    assert sc._verifier_robots("https://acme.fr", "/contact") is True
    assert captured["timeout"] == TIMEOUT_SECONDS
    assert captured["url"].endswith("/robots.txt")

    # RequestException (ex : timeout réseau) → autorisé, jamais de levée.
    def _boom(url, timeout=None, **k):
        raise requests.RequestException("boom")

    sc2 = ScraperContact(rate_limit_seconds=0.0)
    sc2.session.get = _boom  # type: ignore[assignment]
    assert sc2._verifier_robots("https://acme.fr", "/x") is True


def test_construire_base_url_bloque_ssrf(monkeypatch):
    """[S3b] SSRF : hôte résolvant vers adresse privée/loopback → None."""
    from renoboost_leads.stage3_contacts import scraper as scr

    sc = scr.ScraperContact(rate_limit_seconds=0.0)

    mapping = {
        "public.example.com": "93.184.216.34",
        "intra.local": "10.0.0.5",
        "localhost": "127.0.0.1",
        "link.local": "169.254.1.1",
    }

    def _fake_getaddrinfo(host, *a, **k):
        return [(2, 1, 6, "", (mapping[host], 0))]

    monkeypatch.setattr(scr.socket, "getaddrinfo", _fake_getaddrinfo)

    assert (
        sc._construire_base_url("public.example.com")
        == "https://public.example.com"
    )
    assert sc._construire_base_url("http://intra.local") is None
    assert sc._construire_base_url("localhost") is None
    assert sc._construire_base_url("link.local") is None

    # Échec de résolution DNS → on laisse passer (pas un risque SSRF : aucune IP
    # interne atteinte ; le fetch échouera naturellement). Ne PAS sur-bloquer,
    # sinon tout domaine transitoirement injoignable serait rejeté à tort.
    def _boom(host, *a, **k):
        raise scr.socket.gaierror("no dns")

    monkeypatch.setattr(scr.socket, "getaddrinfo", _boom)
    assert sc._construire_base_url("http://nxdomain.invalid") == "http://nxdomain.invalid"
