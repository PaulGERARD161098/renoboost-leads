"""Tests de la découverte SIRENE-first via recherche-entreprises.api.gouv.fr.

Approche : monkeypatch sur `session.get` pour intercepter chaque appel HTTP
et renvoyer une réponse mockée. On vérifie les params transmis, la pagination,
le filtre post-réception siege.departement, et le plafonnement max_results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from renoboost_leads.common.rate_limiter import RateLimiter
from renoboost_leads.stage2_entreprises.recherche_client import (
    RechercheClientConfig,
    RechercheEntreprisesClient,
)


@dataclass
class _FakeResponse:
    status_code: int
    body: dict | None = None

    def json(self) -> dict:
        if self.body is None:
            raise ValueError("non-json")
        return self.body


@dataclass
class _PagedSessionMock:
    """Simule une API paginée. Chaque appel renvoie la page suivante."""

    pages: list[dict[str, Any]]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> _FakeResponse:
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        page = int(params.get("page", 1))
        idx = page - 1
        if idx >= len(self.pages):
            return _FakeResponse(200, {"results": [], "total_pages": len(self.pages), "total_results": 0})
        return _FakeResponse(200, self.pages[idx])


def _client(session: _PagedSessionMock) -> RechercheEntreprisesClient:
    config = RechercheClientConfig(rate_limiter=RateLimiter(max_requests_per_minute=600))
    client = RechercheEntreprisesClient(config)
    client.session = session  # type: ignore[assignment]
    return client


def _entreprise(siren: str, dept_siege: str, nom: str = "TEST SAS") -> dict[str, Any]:
    return {
        "siren": siren,
        "nom_complet": nom,
        "siege": {
            "departement": dept_siege,
            "code_postal": f"{dept_siege}000",
            "activite_principale": "49.41A",
        },
    }


class TestDecouvrirParams:
    def test_filtres_natifs_passes_a_lapi(self):
        session = _PagedSessionMock(pages=[{"results": [], "total_pages": 0, "total_results": 0}])
        client = _client(session)

        list(client.decouvrir(
            departements=["59", "62"],
            activite_principale=["49.41A", "77.11A"],
            tranche_effectif_salarie=["02", "03", "11", "12"],
            ca_min=500_000,
            ca_max=5_000_000,
            categorie_entreprise=["PME"],
            etat_administratif="A",
        ))

        assert len(session.calls) == 1
        params = session.calls[0]["params"]
        assert params["departement"] == "59,62"
        assert params["activite_principale"] == "49.41A,77.11A"
        assert params["tranche_effectif_salarie"] == "02,03,11,12"
        assert params["ca_min"] == 500_000
        assert params["ca_max"] == 5_000_000
        assert params["categorie_entreprise"] == "PME"
        assert params["etat_administratif"] == "A"
        assert params["per_page"] == 25
        assert params["page"] == 1

    def test_per_page_plafonne_a_25(self):
        session = _PagedSessionMock(pages=[{"results": [], "total_pages": 0, "total_results": 0}])
        client = _client(session)
        list(client.decouvrir(departements=["59"], per_page=100))
        assert session.calls[0]["params"]["per_page"] == 25

    def test_departements_vide_court_circuit(self):
        session = _PagedSessionMock(pages=[])
        client = _client(session)
        assert list(client.decouvrir(departements=[])) == []
        assert session.calls == []

    def test_max_results_zero_court_circuit(self):
        session = _PagedSessionMock(pages=[])
        client = _client(session)
        assert list(client.decouvrir(departements=["59"], max_results=0)) == []
        assert session.calls == []


class TestPagination:
    def test_parcourt_les_pages_jusqua_total_pages(self):
        page1 = {"results": [_entreprise("111", "59"), _entreprise("222", "59")], "total_pages": 2, "total_results": 4}
        page2 = {"results": [_entreprise("333", "59"), _entreprise("444", "59")], "total_pages": 2, "total_results": 4}
        session = _PagedSessionMock(pages=[page1, page2])
        client = _client(session)

        results = list(client.decouvrir(departements=["59"]))

        assert [r["siren"] for r in results] == ["111", "222", "333", "444"]
        assert [c["params"]["page"] for c in session.calls] == [1, 2]

    def test_arret_a_max_results(self):
        page1 = {"results": [_entreprise(f"{i:03d}", "59") for i in range(25)], "total_pages": 10, "total_results": 250}
        page2 = {"results": [_entreprise(f"{i:03d}", "59") for i in range(25, 50)], "total_pages": 10, "total_results": 250}
        session = _PagedSessionMock(pages=[page1, page2])
        client = _client(session)

        results = list(client.decouvrir(departements=["59"], max_results=30))

        assert len(results) == 30
        assert len(session.calls) == 2  # page 1 saturée + 5 résultats de page 2

    def test_arret_quand_results_vide(self):
        page1 = {"results": [_entreprise("111", "59")], "total_pages": 5, "total_results": 1}
        page2 = {"results": [], "total_pages": 5, "total_results": 1}
        session = _PagedSessionMock(pages=[page1, page2])
        client = _client(session)

        results = list(client.decouvrir(departements=["59"]))

        assert len(results) == 1
        assert len(session.calls) == 2


class TestFiltreSiege:
    def test_siege_only_evince_dept_etranger(self):
        # L'API filtre par établissements : on peut recevoir une SAS dont le siège
        # est dans le 75 mais qui a un établissement dans le 59.
        page1 = {
            "results": [
                _entreprise("111", "75", "PARIS SAS"),
                _entreprise("222", "59", "LILLE SAS"),
                _entreprise("333", "62", "ARRAS SAS"),
                _entreprise("444", "13", "MARSEILLE SAS"),
            ],
            "total_pages": 1,
            "total_results": 4,
        }
        session = _PagedSessionMock(pages=[page1])
        client = _client(session)

        results = list(client.decouvrir(departements=["59", "62"], siege_only=True))

        assert [r["siren"] for r in results] == ["222", "333"]

    def test_siege_only_false_garde_tout(self):
        page1 = {
            "results": [
                _entreprise("111", "75"),
                _entreprise("222", "59"),
            ],
            "total_pages": 1,
            "total_results": 2,
        }
        session = _PagedSessionMock(pages=[page1])
        client = _client(session)

        results = list(client.decouvrir(departements=["59"], siege_only=False))

        assert [r["siren"] for r in results] == ["111", "222"]


class TestErreurs:
    def test_http_4xx_renvoie_resultats_vides(self):
        # _search_page swallow le 4xx (sauf 429) et retourne dict vide
        class _FailSession:
            def __init__(self):
                self.calls = 0

            def get(self, url, *, params, timeout):  # noqa: ARG002
                self.calls += 1
                return _FakeResponse(400)

        client = _client(_PagedSessionMock(pages=[]))
        client.session = _FailSession()  # type: ignore[assignment]

        results = list(client.decouvrir(departements=["59"]))
        assert results == []
