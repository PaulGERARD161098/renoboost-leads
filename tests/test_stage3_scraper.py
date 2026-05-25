"""Tests du scraper L3 — détection d'un hôte bloqué par l'allowlist réseau."""

from __future__ import annotations

from dataclasses import dataclass

from renoboost_leads.stage3_contacts.scraper import ScraperContact


@dataclass
class _FakeResponse:
    status_code: int
    text: str = ""


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.headers: dict[str, str] = {}

    def get(self, url, *, timeout=None, allow_redirects=True):
        return self._response


class TestScraperReseauBloque:
    def test_403_allowlist_signale_reseau_bloque(self):
        scraper = ScraperContact(rate_limit_seconds=0.0)
        scraper.session = _FakeSession(_FakeResponse(403, "Host not in allowlist"))

        result = scraper.scraper("https://acme.fr")

        assert scraper.reseau_bloque is True
        assert result.raison_echec == "reseau_bloque_allowlist"
        assert result.emails == []

    def test_autre_echec_reste_site_inaccessible(self):
        scraper = ScraperContact(rate_limit_seconds=0.0)
        scraper.session = _FakeSession(_FakeResponse(500, "boom"))

        result = scraper.scraper("https://acme.fr")

        assert scraper.reseau_bloque is False
        assert result.raison_echec == "site_inaccessible"
