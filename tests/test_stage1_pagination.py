"""Tests de la pagination Text Search de l'étage 1 (volume.max_pages)."""

from __future__ import annotations

from typing import Any

from renoboost_leads.models import (
    Budget,
    CampaignConfig,
    RunInfo,
    SecteurCible,
    StagesFlags,
    Volume,
    Zone,
)
from renoboost_leads.stage1_decouverte.extractor import ExtracteurStage1


def _config(
    *, max_pages: int = 1, cible: int = 1000, secteur_type: str = "comptable"
) -> CampaignConfig:
    return CampaignConfig(
        run=RunInfo(client_name="t", description="d", campaign_date="2026-01-01"),
        stages=StagesFlags(),
        secteurs=[SecteurCible(type=secteur_type, query="expert comptable")],
        zone=Zone(type="departement", codes=["59"]),
        volume=Volume(cible=cible, max_pages=max_pages),
        budget=Budget(max_eur=100),
    )


class _FakeClient:
    """Client Places factice : Text Search paginé scripté, Nearby non paginé."""

    def __init__(self, pages: list[dict[str, Any]]):
        self._pages = pages
        self.text_calls: list[str | None] = []
        self.nearby_calls = 0

    def text_search(self, *, query, latitude, longitude, rayon_metres,
                    max_results=20, page_token=None):
        # Sert la page indexée par le rang d'appel (ignore la valeur du token).
        idx = len(self.text_calls)
        self.text_calls.append(page_token)
        return self._pages[idx] if idx < len(self._pages) else {"places": []}

    def nearby_search(self, *, latitude, longitude, rayon_metres,
                      included_types=None, max_results=20):
        self.nearby_calls += 1
        return {"places": [_place(f"n{self.nearby_calls}")]}


def _place(pid: str) -> dict[str, Any]:
    """Fiche Places minimale exploitable par `place_to_lead` (CP 59 = en zone)."""
    return {
        "id": pid,
        "displayName": {"text": f"Cabinet {pid}"},
        "formattedAddress": "1 rue Test, 59000 Lille",
        "businessStatus": "OPERATIONAL",
    }


class TestPaginationTextSearch:
    def test_defaut_une_seule_page(self):
        pages = [{"places": [_place("a"), _place("b")], "nextPageToken": "tok2"}]
        client = _FakeClient(pages)
        cfg = _config(max_pages=1, cible=2)
        ExtracteurStage1(client=client, config=cfg, cache=None).extraire()
        # max_pages=1 → on ne suit JAMAIS le nextPageToken : aucun token transmis.
        assert all(tok is None for tok in client.text_calls)

    def test_suit_le_nextpagetoken_jusqua_max_pages(self):
        pages = [
            {"places": [_place("a")], "nextPageToken": "tok2"},
            {"places": [_place("b")], "nextPageToken": "tok3"},
            {"places": [_place("c")]},  # plus de token → stop
        ]
        client = _FakeClient(pages)
        cfg = _config(max_pages=3, cible=3)
        leads = ExtracteurStage1(client=client, config=cfg, cache=None).extraire()
        # 3 appels, le 2e et 3e portant le token de la page précédente.
        assert client.text_calls[:3] == [None, "tok2", "tok3"]
        assert {lead.place_id for lead in leads} == {"a", "b", "c"}

    def test_stop_anticipe_si_pas_de_token(self):
        # Une seule page sans token : on s'arrête même si max_pages=3.
        pages = [{"places": [_place("a")]}]
        client = _FakeClient(pages)
        cfg = _config(max_pages=3, cible=1)
        ExtracteurStage1(client=client, config=cfg, cache=None).extraire()
        assert client.text_calls == [None]

    def test_type_natif_non_pagine(self):
        # Type natif → Nearby Search, jamais de pagination même avec max_pages=3.
        client = _FakeClient([])
        cfg = _config(max_pages=3, cible=1, secteur_type="restaurant")
        ExtracteurStage1(client=client, config=cfg, cache=None).extraire()
        assert client.nearby_calls >= 1
        assert client.text_calls == []
