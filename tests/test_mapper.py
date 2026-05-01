"""Tests unitaires du mapper Places → LeadStage1."""

from __future__ import annotations

from renoboost_leads.stage1_decouverte.mapper import _extract_cp_ville, place_to_lead


class TestExtractCpVille:
    def test_adresse_classique(self):
        cp, ville = _extract_cp_ville("12 av. Foch, 34000 Montpellier, France")
        assert cp == "34000"
        assert ville == "Montpellier"

    def test_adresse_paris(self):
        cp, ville = _extract_cp_ville("23 rue de Rivoli, 75001 Paris, France")
        assert cp == "75001"
        assert ville == "Paris"

    def test_adresse_sans_cp(self):
        cp, ville = _extract_cp_ville("Champs Élysées, Paris")
        assert cp is None
        assert ville is None

    def test_adresse_none(self):
        cp, ville = _extract_cp_ville(None)
        assert cp is None
        assert ville is None


class TestPlaceToLead:
    def test_lead_complet(self):
        place = {
            "id": "ChIJtest123",
            "displayName": {"text": "Hôtel Le Sud"},
            "formattedAddress": "12 av. Foch, 34000 Montpellier, France",
            "location": {"latitude": 43.61, "longitude": 3.88},
            "nationalPhoneNumber": "04 67 12 34 56",
            "websiteUri": "https://www.hotellesud.fr",
            "rating": 4.2,
            "userRatingCount": 156,
            "primaryType": "lodging",
            "types": ["lodging", "establishment"],
            "businessStatus": "OPERATIONAL",
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "googleMapsUri": "https://maps.google.com/?cid=123",
        }
        lead = place_to_lead(place, secteur_recherche="lodging", requete_origine="hôtel")
        assert lead is not None
        assert lead.place_id == "ChIJtest123"
        assert lead.nom == "Hôtel Le Sud"
        assert lead.code_postal == "34000"
        assert lead.ville == "Montpellier"
        assert lead.note == 4.2
        assert lead.nb_avis == 156
        assert lead.niveau_prix == 2  # MODERATE
        assert "lodging" in lead.types
        assert lead.statut_business == "OPERATIONAL"

    def test_sans_place_id_renvoie_none(self):
        place = {"displayName": {"text": "Sans ID"}}
        assert place_to_lead(place) is None

    def test_sans_nom_renvoie_none(self):
        place = {"id": "ChIJ123"}
        assert place_to_lead(place) is None

    def test_champs_optionnels_absents(self):
        place = {
            "id": "ChIJmin",
            "displayName": {"text": "Minimal"},
        }
        lead = place_to_lead(place)
        assert lead is not None
        assert lead.nom == "Minimal"
        assert lead.note is None
        assert lead.telephone is None
        assert lead.types == []

    def test_telephone_international_fallback(self):
        # Si pas de national, utilise l'international
        place = {
            "id": "ChIJ1",
            "displayName": {"text": "Test"},
            "internationalPhoneNumber": "+33 4 67 12 34 56",
        }
        lead = place_to_lead(place)
        assert lead is not None
        assert lead.telephone == "+33 4 67 12 34 56"
