"""Tests du dispatcher par étage (sélection de stratégie selon cible.type)."""

from __future__ import annotations

import pytest

from renoboost_leads.stage1_decouverte.extractor import ExtracteurStage1
from renoboost_leads.stage1_decouverte.orchestrator import strategie_decouverte
from renoboost_leads.stage2_entreprises.enricher import EnricheurStage2
from renoboost_leads.stage2_entreprises.orchestrator import strategie_entreprises
from renoboost_leads.stage3_contacts.enricher import EnricheurStage3
from renoboost_leads.stage3_contacts.orchestrator import strategie_contacts


def test_dispatch_b2b_renvoie_les_etages_existants() -> None:
    assert strategie_decouverte("b2b") is ExtracteurStage1
    assert strategie_entreprises("b2b") is EnricheurStage2
    assert strategie_contacts("b2b") is EnricheurStage3


@pytest.mark.parametrize(
    "dispatch",
    [strategie_decouverte, strategie_entreprises, strategie_contacts],
)
def test_dispatch_b2c_indisponible_en_v0(dispatch) -> None:
    with pytest.raises(NotImplementedError):
        dispatch("b2c-particulier")


@pytest.mark.parametrize(
    "dispatch",
    [strategie_decouverte, strategie_entreprises, strategie_contacts],
)
def test_dispatch_type_inconnu_leve(dispatch) -> None:
    with pytest.raises(NotImplementedError):
        dispatch("inconnu")
