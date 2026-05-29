"""Tests de l'enrichisseur Places (mode SIRENE-first)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from renoboost_leads.common.budget_guard import BudgetExceededError
from renoboost_leads.models import LeadStage2
from renoboost_leads.stage0_sirene_first.places_enricher import (
    EnrichisseurPlaces,
    villes_correspondent,
)
from renoboost_leads.stage1_decouverte.places_client import PlacesAPIError


def _lead_sirene(siren: str = "111111111", ville: str = "Lille") -> LeadStage2:
    return LeadStage2(
        place_id=f"sirene:{siren}",
        extraction_date=datetime.now(timezone.utc),
        nom="MON BEL ATELIER SAS",
        adresse="10 rue de la Paix",
        ville=ville,
        code_postal="59000",
        pays="France",
        siren=siren,
        siret=f"{siren}00015",
        score_matching=100.0,
    )


def _place_brute(
    place_id: str = "ChIJabc",
    nom: str = "MON BEL ATELIER SAS",
    cp: str = "59000",
    ville: str = "Lille",
    site: str | None = "https://atelier.fr",
    tel: str | None = "+33320001122",
    note: float | None = 4.5,
    nb_avis: int | None = 42,
) -> dict[str, Any]:
    return {
        "id": place_id,
        "displayName": {"text": nom},
        "formattedAddress": f"10 rue de la Paix, {cp} {ville}, France",
        "location": {"latitude": 50.6, "longitude": 3.0},
        "websiteUri": site,
        "nationalPhoneNumber": tel,
        "rating": note,
        "userRatingCount": nb_avis,
        "businessStatus": "OPERATIONAL",
        "primaryType": "industry",
        "types": ["industry", "establishment"],
        "googleMapsUri": "https://maps.google.com/?cid=123",
    }


class _FakePlacesClient:
    """Mock minimal du PlacesClient : text_search renvoie une réponse fixe."""

    def __init__(self, response: dict | None = None, exception: Exception | None = None):
        self.response = response if response is not None else {"places": []}
        self.exception = exception
        self.calls: list[dict] = []

    def text_search(self, *, query: str, max_results: int = 20, **kwargs) -> dict:
        self.calls.append({"query": query, "max_results": max_results, **kwargs})
        if self.exception:
            raise self.exception
        return self.response


class TestVillesCorrespondent:
    def test_strict(self):
        assert villes_correspondent("Lille", "Lille")

    def test_casse_et_accents_ignores_pour_lower(self):
        assert villes_correspondent("Lille", "lille")

    def test_tirets_et_apostrophes(self):
        assert villes_correspondent("Villeneuve-d'Ascq", "Villeneuve d Ascq")

    def test_inclusion_metropole(self):
        assert villes_correspondent("Lille", "Lille Métropole")
        assert villes_correspondent("Paris 14", "Paris")

    def test_mismatch(self):
        assert not villes_correspondent("Lille", "Marseille")

    def test_none_ou_vide(self):
        assert not villes_correspondent(None, "Lille")
        assert not villes_correspondent("", "Lille")


class TestEnrichirSuccess:
    def test_lead_enrichi_avec_site_et_tel(self):
        client = _FakePlacesClient({"places": [_place_brute()]})
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]

        lead_in = _lead_sirene(ville="Lille")
        lead_out = e.enrichir(lead_in)

        assert lead_out.place_id == "ChIJabc"  # remplace le sentinel
        assert lead_out.site_web == "https://atelier.fr"
        assert lead_out.telephone == "+33320001122"
        assert lead_out.note == 4.5
        assert lead_out.nb_avis == 42
        # Identité SIRENE conservée
        assert lead_out.siren == "111111111"
        assert lead_out.ville == "Lille"

    def test_query_combine_nom_et_ville(self):
        client = _FakePlacesClient({"places": [_place_brute()]})
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]
        e.enrichir(_lead_sirene(ville="Lille"))
        assert client.calls[0]["query"] == "MON BEL ATELIER SAS Lille"


class TestEnrichirEchecsGracieux:
    def test_aucun_resultat_renvoie_lead_inchange(self):
        client = _FakePlacesClient({"places": []})
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]
        lead_in = _lead_sirene()
        lead_out = e.enrichir(lead_in)
        assert lead_out.place_id == "sirene:111111111"
        assert lead_out.site_web is None

    def test_erreur_api_renvoie_lead_inchange(self):
        client = _FakePlacesClient(exception=PlacesAPIError("boom"))
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]
        lead_out = e.enrichir(_lead_sirene())
        assert lead_out.place_id == "sirene:111111111"

    def test_mismatch_ville_garde_lead_inchange(self):
        # Places renvoie une fiche à Marseille pour une recherche "MON BEL ATELIER Lille"
        client = _FakePlacesClient({"places": [_place_brute(ville="Marseille")]})
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]
        lead_out = e.enrichir(_lead_sirene(ville="Lille"))
        assert lead_out.place_id == "sirene:111111111"
        assert lead_out.site_web is None

    def test_lead_sans_nom_court_circuit(self):
        client = _FakePlacesClient()
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]
        # nom est requis par LeadStage1 (Pydantic) → on simule en mock direct
        lead = _lead_sirene()
        lead = lead.model_copy(update={"nom": ""})
        lead_out = e.enrichir(lead)
        # Le client ne doit pas avoir été appelé
        assert client.calls == []
        assert lead_out is lead


class TestEnrichirLot:
    def test_lot_traite_chacun(self):
        client = _FakePlacesClient({"places": [_place_brute()]})
        e = EnrichisseurPlaces(client)  # type: ignore[arg-type]
        leads = [_lead_sirene("111"), _lead_sirene("222"), _lead_sirene("333")]
        sortie = e.enrichir_lot(leads)
        assert len(sortie) == 3
        # Tous enrichis (même réponse Places, mais sont différents leads SIRENE)
        for lead in sortie:
            assert lead.place_id == "ChIJabc"

    def test_budget_exceeded_garde_le_reste_non_enrichi(self):
        """Si le budget casse au 2e lead, les leads suivants restent dans la liste."""
        appels = {"n": 0}

        class _BudgetBreaker:
            calls: list = []

            def text_search(self, *, query: str, max_results: int = 20, **kwargs):
                self.calls.append(query)
                appels["n"] += 1
                if appels["n"] >= 2:
                    raise BudgetExceededError("plafond atteint")
                return {"places": [_place_brute()]}

        e = EnrichisseurPlaces(_BudgetBreaker())  # type: ignore[arg-type]
        leads = [_lead_sirene("111"), _lead_sirene("222"), _lead_sirene("333")]
        sortie = e.enrichir_lot(leads)

        assert len(sortie) == 3
        assert sortie[0].place_id == "ChIJabc"            # premier enrichi
        assert sortie[1].place_id == "sirene:222"         # deuxième non enrichi (budget)
        assert sortie[2].place_id == "sirene:333"         # troisième non tenté
