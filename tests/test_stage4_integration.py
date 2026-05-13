"""Tests d'intégration L4 — hit la vraie API Anthropic si une clé est présente.

Ces tests sont automatiquement skippés si `ANTHROPIC_API_KEY` n'est pas définie
dans l'environnement (cas par défaut en CI). Ils servent à valider :
- Que le parser JSON tient face à la réponse réelle de Claude
- Que le calcul de coût correspond à la facturation réelle
- Que Haiku et Sonnet répondent au format attendu

Lancement manuel :
    pytest tests/test_stage4_integration.py -v -m integration

Coût indicatif par exécution : ~0.005 € (1 appel Haiku).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from renoboost_leads.models import ClaudeScoring, LeadStage3
from renoboost_leads.stage4_prospection.cache import CacheStage4
from renoboost_leads.stage4_prospection.client import (
    ClaudeClient,
    ClaudeClientConfig,
)
from renoboost_leads.stage4_prospection.enricher import EnricheurStage4
from renoboost_leads.stage4_prospection.prompt_template import construire_prompt

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY non défini — skipped (test d'intégration optionnel)",
    ),
]


def _lead_realiste() -> LeadStage3:
    return LeadStage3(
        place_id="ChIJ_integration_test",
        extraction_date=datetime.now(timezone.utc),
        nom="Boulangerie Dupont",
        adresse="12 rue de la Paix, 59000 Lille",
        ville="Lille",
        code_postal="59000",
        siren="402222222",
        code_naf="10.71C",
        libelle_naf="Boulangerie et boulangerie-pâtisserie",
        forme_juridique="SARL",
        tranche_effectif="11",
        libelle_effectif="6 à 9 salariés",
    )


class TestIntegrationHaiku:
    def test_appel_reel_haiku(self):
        """Smoke test : un seul appel Haiku, vérifie le parsing + coût."""
        client = ClaudeClient(
            ClaudeClientConfig(
                api_key=os.environ["ANTHROPIC_API_KEY"],
                modele="claude-haiku-4-5",
                max_tokens_sortie=400,
            )
        )
        lead = _lead_realiste()
        prompt = construire_prompt(lead, inclure_pitch=True)
        reponse = client.scorer(prompt)

        assert 0 <= reponse.score_interet <= 100
        assert reponse.raison_score
        assert reponse.pitch_propose is not None
        assert reponse.tokens_in > 0
        assert reponse.tokens_out > 0
        assert reponse.cout_eur > 0
        assert reponse.modele == "claude-haiku-4-5"


class TestIntegrationEnricherBatch:
    def test_enricher_3_leads_haiku(self, tmp_path):
        """Pipeline complet : 3 leads via Haiku, cache vérifié au 2e run."""
        client = ClaudeClient(
            ClaudeClientConfig(
                api_key=os.environ["ANTHROPIC_API_KEY"],
                modele="claude-haiku-4-5",
                max_tokens_sortie=400,
            )
        )
        cache = CacheStage4(tmp_path / "l4_integration.sqlite")
        enricher = EnricheurStage4(
            client=client,
            config=ClaudeScoring(modele="claude-haiku-4-5", inclure_pitch=False),
            cache=cache,
        )
        leads = [
            _lead_realiste(),
            LeadStage3(
                place_id="ChIJ_int_2",
                extraction_date=datetime.now(timezone.utc),
                nom="Hôtel du Centre",
                code_naf="55.10Z",
                libelle_naf="Hôtels et hébergement similaire",
                tranche_effectif="22",
                libelle_effectif="100 à 199 salariés",
            ),
            LeadStage3(
                place_id="ChIJ_int_3",
                extraction_date=datetime.now(timezone.utc),
                nom="Garage Martin",
                code_naf="45.20A",
            ),
        ]

        leads_l4 = enricher.enrichir(leads)
        assert len(leads_l4) == 3
        for l4 in leads_l4:
            assert l4.score_interet is not None
            assert l4.scoring_erreur is None
        assert enricher.cache_misses == 3
        assert enricher.cout_total_eur > 0

        # 2e enricher : cache plein, aucun appel
        enricher2 = EnricheurStage4(
            client=client,
            config=ClaudeScoring(modele="claude-haiku-4-5", inclure_pitch=False),
            cache=cache,
        )
        enricher2.enrichir(leads)
        assert enricher2.cache_hits == 3
        assert enricher2.cache_misses == 0
        assert enricher2.cout_total_eur == 0
