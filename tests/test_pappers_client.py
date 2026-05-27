"""Tests du client Pappers (fallback L2) : appel HTTP mocké, budget, mapping."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from renoboost_leads.common.budget_guard import BudgetExceededError, BudgetGuard
from renoboost_leads.stage2_entreprises.mapper import candidat_to_l2_fields
from renoboost_leads.stage2_entreprises.pappers_client import (
    PappersClient,
    PappersClientConfig,
    PappersError,
    PappersTransientError,
    pappers_resultat_to_candidat,
)


@dataclass
class _FakeResponse:
    status_code: int
    body: dict | None = None
    text: str = ""

    def json(self):
        if self.body is None:
            raise ValueError("non-json")
        return self.body


@dataclass
class _GetFactory:
    """Renvoie une réponse fixe et capture les arguments du dernier appel."""

    response: _FakeResponse
    calls: int = 0
    captured: dict = field(default_factory=dict)

    def __call__(self, url, *, params, headers, timeout):
        self.calls += 1
        self.captured = {"url": url, "params": params, "headers": headers, "timeout": timeout}
        return self.response


def _resultat_pappers() -> dict:
    """Échantillon calqué sur le schéma documenté de /v2/recherche."""
    return {
        "siren": "402222222",
        "nom_entreprise": "BONDUELLE",
        "code_naf": "10.39A",
        "libelle_code_naf": "Autre transformation de légumes",
        "code_forme_juridique": "5710",
        "entreprise_cessee": False,
        "categorie_entreprise": "GE",
        "tranche_effectif": "42",
        "effectif": "5000 à 9999 salariés",
        "date_creation": "1947-01-01",
        "nombre_etablissements": 12,
        "siege": {
            "siret": "40222222200015",
            "code_postal": "59650",
            "ville": "Villeneuve-d'Ascq",
            "code_naf": "10.39A",
            "libelle_code_naf": "Autre transformation de légumes",
            "numero_voie": "296",
            "type_voie": "RUE",
            "libelle_voie": "Charles Saint-Venant",
        },
        "dirigeants": [
            {"nom": "Bonduelle", "prenom": "Christophe", "qualite": "Président"},
        ],
    }


class TestRechercheParams:
    def test_params_incluent_token_query_cp(self):
        factory = _GetFactory(_FakeResponse(200, {"resultats": []}))
        client = PappersClient(
            PappersClientConfig(api_key="SECRET", http_get=factory, per_page=5)
        )
        client.rechercher("Bonduelle", code_postal="59650")
        p = factory.captured["params"]
        assert p["api_token"] == "SECRET"  # noqa: S105
        assert p["q"] == "Bonduelle"
        assert p["par_page"] == 5
        assert p["code_postal"] == "59650"

    def test_query_vide_ne_fait_aucun_appel(self):
        factory = _GetFactory(_FakeResponse(200, {"resultats": []}))
        client = PappersClient(PappersClientConfig(api_key="K", http_get=factory))
        assert client.rechercher("   ") == []
        assert factory.calls == 0

    def test_resultats_mappes_en_candidats(self):
        factory = _GetFactory(_FakeResponse(200, {"resultats": [_resultat_pappers()]}))
        client = PappersClient(PappersClientConfig(api_key="K", http_get=factory))
        candidats = client.rechercher("Bonduelle")
        assert len(candidats) == 1
        assert candidats[0]["siren"] == "402222222"
        assert candidats[0]["siege"]["code_postal"] == "59650"

    def test_cle_results_en_fallback(self):
        factory = _GetFactory(_FakeResponse(200, {"results": [_resultat_pappers()]}))
        client = PappersClient(PappersClientConfig(api_key="K", http_get=factory))
        assert len(client.rechercher("Bonduelle")) == 1


class TestRechercheStatuts:
    def test_401_credits_epuises_renvoie_vide_sans_retry(self):
        factory = _GetFactory(_FakeResponse(401, text="plus assez de crédits"))
        client = PappersClient(PappersClientConfig(api_key="K", http_get=factory))
        assert client.rechercher("Bonduelle") == []
        assert factory.calls == 1  # pas de retry sur 4xx

    def test_500_leve_transient(self):
        # On neutralise les pauses tenacity pour ne pas ralentir le test.
        PappersClient.rechercher.retry.sleep = lambda _s: None
        factory = _GetFactory(_FakeResponse(503))
        client = PappersClient(PappersClientConfig(api_key="K", http_get=factory))
        with pytest.raises(PappersTransientError):
            client.rechercher("Bonduelle")
        assert factory.calls == 3  # 3 tentatives puis abandon

    def test_non_json_leve_pappers_error(self):
        factory = _GetFactory(_FakeResponse(200, body=None))
        client = PappersClient(PappersClientConfig(api_key="K", http_get=factory))
        with pytest.raises(PappersError):
            client.rechercher("Bonduelle")


class TestBudget:
    def test_chaque_appel_debite_le_budget(self):
        factory = _GetFactory(_FakeResponse(200, {"resultats": []}))
        budget = BudgetGuard(plafond_eur=1.0)
        client = PappersClient(
            PappersClientConfig(
                api_key="K", http_get=factory, budget=budget, cout_par_appel_eur=0.02
            )
        )
        client.rechercher("a")
        client.rechercher("b")
        assert budget.nb_appels == 2
        assert budget.cout_actuel_eur == pytest.approx(0.04)

    def test_depassement_leve_budget_exceeded_avant_appel(self):
        factory = _GetFactory(_FakeResponse(200, {"resultats": []}))
        budget = BudgetGuard(plafond_eur=0.01)
        client = PappersClient(
            PappersClientConfig(
                api_key="K", http_get=factory, budget=budget, cout_par_appel_eur=0.02
            )
        )
        with pytest.raises(BudgetExceededError):
            client.rechercher("a")
        assert factory.calls == 0  # le cap empêche l'appel HTTP


class TestMapper:
    def test_mapping_complet_vers_candidat(self):
        cand = pappers_resultat_to_candidat(_resultat_pappers())
        assert cand["siren"] == "402222222"
        assert cand["nom_complet"] == "BONDUELLE"
        assert cand["etat_administratif"] == "A"  # entreprise_cessee=False
        assert cand["nature_juridique"] == "5710"
        assert cand["activite_principale"] == "10.39A"
        assert cand["siege"]["libelle_commune"] == "Villeneuve-d'Ascq"
        assert cand["dirigeants"][0]["prenoms"] == "Christophe"

    def test_entreprise_cessee_mappe_en_c(self):
        cand = pappers_resultat_to_candidat({"siren": "1", "entreprise_cessee": True})
        assert cand["etat_administratif"] == "C"

    def test_candidat_consommable_par_candidat_to_l2_fields(self):
        cand = pappers_resultat_to_candidat(_resultat_pappers())
        fields = candidat_to_l2_fields(cand)
        assert fields["siren"] == "402222222"
        assert fields["statut_actif"] is True
        assert fields["code_naf"] == "10.39A"
        assert fields["dirigeant_prenom"] == "Christophe"
        assert fields["nb_etablissements"] == 12
        assert fields["categorie_entreprise"] == "GE"

    def test_finances_a_plat_reconstruites(self):
        r = {"siren": "1", "chiffre_affaires": 1000, "resultat": 100, "annee_finances": 2024}
        cand = pappers_resultat_to_candidat(r)
        ca, res, annee = (
            candidat_to_l2_fields(cand)["chiffre_affaires"],
            candidat_to_l2_fields(cand)["resultat_net"],
            candidat_to_l2_fields(cand)["annee_finances"],
        )
        assert (ca, res, annee) == (1000, 100, "2024")

    def test_sans_finances_pas_de_bloc(self):
        cand = pappers_resultat_to_candidat({"siren": "1"})
        assert "finances" not in cand
