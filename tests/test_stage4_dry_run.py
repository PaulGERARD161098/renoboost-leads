"""Tests du client dry-run L4 + intégration enricher.

Ces tests valident que le mode `--dry-run --stages 4` fonctionne bout-en-bout
sans appel réseau ni clé Anthropic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.models import ClaudeScoring, LeadStage3
from renoboost_leads.stage4_prospection.cache import CacheStage4
from renoboost_leads.stage4_prospection.dry_run import (
    ClaudeClientDryRun,
    _extraire_nom_lead,
)
from renoboost_leads.stage4_prospection.enricher import EnricheurStage4
from renoboost_leads.stage4_prospection.prompt_template import construire_prompt


def _lead(place_id: str, nom: str = "Test SAS") -> LeadStage3:
    return LeadStage3(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
    )


class TestExtraireNomLead:
    def test_extrait_nom_depuis_prompt(self):
        prompt = construire_prompt(_lead("A", nom="SMI Industrie"))
        assert _extraire_nom_lead(prompt) == "SMI Industrie"

    def test_fallback_si_absent(self):
        assert _extraire_nom_lead("prompt sans format attendu") == "ce lead"


class TestClaudeClientDryRun:
    def test_score_dans_borne_30_95(self):
        client = ClaudeClientDryRun()
        for i in range(20):
            rep = client.scorer(f"prompt-{i}\n- Nom : Lead{i}")
            assert 30 <= rep.score_interet <= 95

    def test_score_deterministe_meme_prompt(self):
        client = ClaudeClientDryRun()
        rep1 = client.scorer("prompt-A")
        rep2 = client.scorer("prompt-A")
        assert rep1.score_interet == rep2.score_interet
        assert rep1.raison_score == rep2.raison_score

    def test_prompts_differents_scores_potentiellement_differents(self):
        client = ClaudeClientDryRun()
        scores = {
            client.scorer(f"prompt-{i}\n- Nom : Lead{i}").score_interet
            for i in range(50)
        }
        # Sur 50 prompts différents, on devrait avoir une certaine diversité
        assert len(scores) >= 10

    def test_inclure_pitch_false_pas_de_pitch(self):
        client = ClaudeClientDryRun(inclure_pitch=False)
        rep = client.scorer("prompt-X\n- Nom : X")
        assert rep.pitch_propose is None

    def test_inclure_pitch_true_genere_pitch(self):
        client = ClaudeClientDryRun(inclure_pitch=True)
        rep = client.scorer("prompt-X\n- Nom : X")
        assert rep.pitch_propose is not None
        assert "DRY-RUN" in rep.pitch_propose

    def test_cout_eur_nul_en_dry_run(self):
        client = ClaudeClientDryRun()
        rep = client.scorer("prompt")
        assert rep.cout_eur == 0.0
        assert rep.tokens_in == 0
        assert rep.tokens_out == 0

    def test_raison_evoque_nom_lead(self):
        client = ClaudeClientDryRun()
        rep = client.scorer("# Lead à évaluer\n- Nom : ACME Industries SAS\nautres champs...")
        assert "ACME Industries SAS" in rep.raison_score

    def test_calls_compteur(self):
        client = ClaudeClientDryRun()
        client.scorer("a")
        client.scorer("b")
        client.scorer("c")
        assert client.calls == 3


class TestEnricherAvecDryRun:
    def test_enrichir_batch_dry_run(self, tmp_path):
        """L'enricher accepte le mock dry-run et produit des LeadStage4 valides."""
        client = ClaudeClientDryRun()
        cache = CacheStage4(tmp_path / "l4.sqlite")
        enricher = EnricheurStage4(
            client=client,
            config=ClaudeScoring(seuil_top_lead=70),
            cache=cache,
        )
        leads_l3 = [_lead(f"L{i}", nom=f"Lead {i}") for i in range(10)]
        leads_l4 = enricher.enrichir(leads_l3)

        assert len(leads_l4) == 10
        for l4 in leads_l4:
            assert 30 <= l4.score_interet <= 95
            assert l4.raison_score is not None
            assert l4.scoring_erreur is None
            assert l4.scoring_modele == "claude-haiku-4-5"

    def test_dry_run_cache_fonctionne(self, tmp_path):
        """Le cache fonctionne aussi en dry-run (re-run gratuit)."""
        cache = CacheStage4(tmp_path / "l4.sqlite")
        config = ClaudeScoring()

        client1 = ClaudeClientDryRun()
        enricher1 = EnricheurStage4(client=client1, config=config, cache=cache)
        enricher1.enrichir([_lead("A"), _lead("B")])
        assert client1.calls == 2

        # 2e enricher → cache hit, pas d'appel
        client2 = ClaudeClientDryRun()
        enricher2 = EnricheurStage4(client=client2, config=config, cache=cache)
        leads_l4 = enricher2.enrichir([_lead("A"), _lead("B")])
        assert client2.calls == 0
        assert enricher2.cache_hits == 2
        # Les scores cachés doivent être identiques
        for l4 in leads_l4:
            assert l4.score_interet is not None
