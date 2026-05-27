"""Tests du fallback Pappers dans EnricheurStage2.

Déclenchement attendu : Pappers n'est interrogé QUE quand le match gratuit
est absent (best=None) ou incertain (score < SEUIL_CONFIANCE), jamais quand le
gratuit est confiant, et jamais sans client Pappers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from renoboost_leads.common.budget_guard import BudgetExceededError
from renoboost_leads.models import LeadStage1
from renoboost_leads.stage2_entreprises.enricher import EnricheurStage2


def _lead_l1(nom: str, cp: str = "59000") -> LeadStage1:
    return LeadStage1(
        place_id=f"ChIJ_{nom}",
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        code_postal=cp,
        ville="Lille",
    )


class _FakeRechercheClient:
    def __init__(self, par_query: dict[str, list[dict]] | None = None):
        self.par_query = par_query or {}

    def rechercher(self, query: str, code_postal: str | None = None, per_page: int = 10):
        return self.par_query.get(query, [])


class _FakePappers:
    """Stub Pappers : déjà mappé en forme candidat data.gouv."""

    def __init__(self, par_query=None, raise_budget=False, cout=0.02):
        self.par_query = par_query or {}
        self.raise_budget = raise_budget
        self.queries: list[str] = []
        self.config = SimpleNamespace(cout_par_appel_eur=cout)

    def rechercher(self, query: str, code_postal: str | None = None):
        self.queries.append(query)
        if self.raise_budget:
            raise BudgetExceededError("cap atteint")
        return self.par_query.get(query, [])


def _candidat_fort(siren: str) -> dict:
    """Score ~100 : adresse (50) + nom (30) + statut actif (20)."""
    return {
        "siren": siren,
        "nom_complet": "SMI INDUSTRIE SAS",
        "etat_administratif": "A",
        "nature_juridique": "5710",
        "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
    }


class TestFallbackDeclenchement:
    def test_fallback_si_best_none(self):
        # Gratuit ne trouve rien → Pappers fournit un match fort.
        rech = _FakeRechercheClient({})
        pappers = _FakePappers({"SMI Industrie Lille": [_candidat_fort("402222222")]})
        enr = EnricheurStage2(client=rech, pappers_client=pappers)

        leads = enr.enrichir([_lead_l1("SMI Industrie")])
        assert leads[0].siren == "402222222"
        assert enr.nb_fallback_pappers == 1
        assert enr.cout_pappers_eur == 0.02
        assert pappers.queries == ["SMI Industrie Lille"]

    def test_fallback_si_incertain_garde_le_meilleur(self):
        # Gratuit trouve un candidat faible (dept seul → 10 pts, incertain).
        faible = {
            "siren": "111111111",
            "nom_complet": "Autre Chose",
            "siege": {"code_postal": "59500", "libelle_commune": "Douai"},
        }
        rech = _FakeRechercheClient({"SMI Industrie Lille": [faible]})
        pappers = _FakePappers({"SMI Industrie Lille": [_candidat_fort("402222222")]})
        enr = EnricheurStage2(client=rech, pappers_client=pappers)

        leads = enr.enrichir([_lead_l1("SMI Industrie")])
        # Pappers fait mieux → on garde son SIREN.
        assert leads[0].siren == "402222222"
        assert enr.nb_fallback_pappers == 1

    def test_pas_de_fallback_si_match_confiant(self):
        rech = _FakeRechercheClient({"SMI Industrie Lille": [_candidat_fort("999999999")]})
        pappers = _FakePappers({"SMI Industrie Lille": [_candidat_fort("402222222")]})
        enr = EnricheurStage2(client=rech, pappers_client=pappers)

        leads = enr.enrichir([_lead_l1("SMI Industrie")])
        assert leads[0].siren == "999999999"  # match gratuit conservé
        assert enr.nb_fallback_pappers == 0
        assert pappers.queries == []  # Pappers jamais appelé

    def test_aucun_appel_si_pappers_absent(self):
        rech = _FakeRechercheClient({})
        enr = EnricheurStage2(client=rech)  # pas de pappers_client
        leads = enr.enrichir([_lead_l1("Inconnu")])
        assert leads[0].siren is None
        assert enr.nb_fallback_pappers == 0


class TestFallbackPappersVide:
    def test_pappers_vide_garde_le_resultat_gratuit(self):
        faible = {
            "siren": "111111111",
            "nom_complet": "Autre Chose",
            "siege": {"code_postal": "59500", "libelle_commune": "Douai"},
        }
        rech = _FakeRechercheClient({"SMI Industrie Lille": [faible]})
        pappers = _FakePappers({})  # Pappers ne renvoie rien
        enr = EnricheurStage2(client=rech, pappers_client=pappers)

        leads = enr.enrichir([_lead_l1("SMI Industrie")])
        assert leads[0].siren == "111111111"  # on conserve le faible match gratuit
        assert enr.nb_fallback_pappers == 1  # l'appel a quand même été facturé


class TestFallbackBudget:
    def test_budget_epuise_desactive_les_appels_suivants(self):
        rech = _FakeRechercheClient({})
        pappers = _FakePappers(raise_budget=True)
        enr = EnricheurStage2(client=rech, pappers_client=pappers)

        leads = enr.enrichir([_lead_l1("Alpha"), _lead_l1("Beta")])
        # Le 1er lead déclenche l'exception budget → coupe-circuit pour le 2e.
        assert len(pappers.queries) == 1
        assert enr.nb_fallback_pappers == 0  # rien facturé (cap avant appel)
        assert all(lead.siren is None for lead in leads)
        assert len(leads) == 2  # le run se termine proprement
