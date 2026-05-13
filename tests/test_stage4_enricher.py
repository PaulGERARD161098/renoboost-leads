"""Tests de l'enricher L4 (cache + flux d'erreur + budget + stats)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from renoboost_leads.common.budget_guard import BudgetGuard
from renoboost_leads.models import ClaudeScoring, LeadStage3
from renoboost_leads.stage4_prospection.cache import CacheStage4
from renoboost_leads.stage4_prospection.client import ClaudeClient, ClaudeClientConfig
from renoboost_leads.stage4_prospection.enricher import EnricheurStage4

# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────


def _lead(place_id: str, nom: str = "Test") -> LeadStage3:
    return LeadStage3(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
    )


@dataclass
class _FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class _FakeBlock:
    text: str


@dataclass
class _FakeMessage:
    content: list
    usage: _FakeUsage


class _ScriptedSDK:
    """SDK Anthropic mocké — joue les réponses dans l'ordre."""

    def __init__(self, reponses: list[str], exception: Exception | None = None):
        self.reponses = list(reponses)
        self.exception = exception
        self.calls = 0

        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                if outer.exception is not None and outer.calls <= 1:
                    # Lève l'exception une seule fois (gère cas retry → succès)
                    exc = outer.exception
                    outer.exception = None
                    raise exc
                if not outer.reponses:
                    raise RuntimeError("Plus de réponses scriptées")
                texte = outer.reponses.pop(0)
                return _FakeMessage(
                    content=[_FakeBlock(text=texte)],
                    usage=_FakeUsage(),
                )

        self.messages = _Messages()


def _build_client(reponses: list[str], **client_kwargs):
    sdk = _ScriptedSDK(reponses)
    cfg = ClaudeClientConfig(
        api_key="sk-fake",
        modele="claude-haiku-4-5",
        sdk_client=sdk,
        **client_kwargs,
    )
    return ClaudeClient(cfg), sdk


# ─────────────────────────────────────────────────────────────────
# Cas nominal
# ─────────────────────────────────────────────────────────────────


class TestEnricherFluxNominal:
    def test_un_lead_score_attendu(self, tmp_path):
        client, sdk = _build_client(
            ['{"score_interet": 82, "raison_score": "PME idéale", "pitch_propose": "Hello..."}']
        )
        cache = CacheStage4(tmp_path / "l4.sqlite")
        config = ClaudeScoring(modele="claude-haiku-4-5", seuil_top_lead=70)
        enricher = EnricheurStage4(client=client, config=config, cache=cache)

        leads_l4 = enricher.enrichir([_lead("A")])

        assert len(leads_l4) == 1
        l4 = leads_l4[0]
        assert l4.score_interet == 82
        assert l4.raison_score == "PME idéale"
        assert l4.pitch_propose == "Hello..."
        assert l4.top_lead is True
        assert l4.scoring_modele == "claude-haiku-4-5"
        assert l4.scoring_erreur is None

    def test_score_sous_seuil_pas_top(self, tmp_path):
        client, _ = _build_client(['{"score_interet": 30, "raison_score": "faible"}'])
        cache = CacheStage4(tmp_path / "l4.sqlite")
        config = ClaudeScoring(seuil_top_lead=70, inclure_pitch=False)
        enricher = EnricheurStage4(client=client, config=config, cache=cache)
        leads_l4 = enricher.enrichir([_lead("A")])
        assert leads_l4[0].top_lead is False

    def test_seuil_atteint_exactement_est_top(self, tmp_path):
        client, _ = _build_client(['{"score_interet": 70, "raison_score": "ok"}'])
        cache = CacheStage4(tmp_path / "l4.sqlite")
        config = ClaudeScoring(seuil_top_lead=70, inclure_pitch=False)
        enricher = EnricheurStage4(client=client, config=config, cache=cache)
        l4 = enricher.enrichir([_lead("A")])[0]
        assert l4.top_lead is True


# ─────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────


class TestEnricherCache:
    def test_cache_hit_evite_appel(self, tmp_path):
        client, sdk = _build_client(
            ['{"score_interet": 88, "raison_score": "premiere", "pitch_propose": "p1"}']
        )
        cache = CacheStage4(tmp_path / "l4.sqlite")
        config = ClaudeScoring()
        enricher1 = EnricheurStage4(client=client, config=config, cache=cache)
        enricher1.enrichir([_lead("A")])
        assert sdk.calls == 1
        assert enricher1.cache_misses == 1
        assert enricher1.cache_hits == 0

        # 2e run avec même config → cache hit, pas de nouvel appel
        enricher2 = EnricheurStage4(client=client, config=config, cache=cache)
        l4 = enricher2.enrichir([_lead("A")])[0]
        assert sdk.calls == 1
        assert enricher2.cache_hits == 1
        assert enricher2.cache_misses == 0
        assert l4.score_interet == 88

    def test_changement_modele_invalide_cache(self, tmp_path):
        # 1er run avec Haiku
        client_h, sdk_h = _build_client(
            ['{"score_interet": 50, "raison_score": "haiku"}']
        )
        cache = CacheStage4(tmp_path / "l4.sqlite")
        enricher = EnricheurStage4(
            client=client_h,
            config=ClaudeScoring(modele="claude-haiku-4-5", inclure_pitch=False),
            cache=cache,
        )
        enricher.enrichir([_lead("A")])

        # 2e run avec Sonnet → cache miss attendu
        client_s, sdk_s = _build_client(
            ['{"score_interet": 80, "raison_score": "sonnet"}']
        )
        client_s.config.modele = "claude-sonnet-4-6"
        enricher2 = EnricheurStage4(
            client=client_s,
            config=ClaudeScoring(modele="claude-sonnet-4-6", inclure_pitch=False),
            cache=cache,
        )
        l4 = enricher2.enrichir([_lead("A")])[0]
        assert sdk_s.calls == 1
        assert enricher2.cache_misses == 1
        assert l4.score_interet == 80

    def test_changement_contexte_invalide_cache(self, tmp_path):
        cache = CacheStage4(tmp_path / "l4.sqlite")
        client1, _ = _build_client(['{"score_interet": 50, "raison_score": "ctx1"}'])
        EnricheurStage4(
            client=client1,
            config=ClaudeScoring(contexte_client="Contexte A", inclure_pitch=False),
            cache=cache,
        ).enrichir([_lead("A")])

        client2, sdk2 = _build_client(['{"score_interet": 60, "raison_score": "ctx2"}'])
        e2 = EnricheurStage4(
            client=client2,
            config=ClaudeScoring(contexte_client="Contexte B", inclure_pitch=False),
            cache=cache,
        )
        l4 = e2.enrichir([_lead("A")])[0]
        assert sdk2.calls == 1  # cache invalidé
        assert l4.score_interet == 60

    def test_changement_inclure_pitch_invalide_cache(self, tmp_path):
        cache = CacheStage4(tmp_path / "l4.sqlite")
        reponse_pitch = '{"score_interet": 50, "raison_score": "a", "pitch_propose": "p"}'
        client1, _ = _build_client([reponse_pitch])
        EnricheurStage4(
            client=client1,
            config=ClaudeScoring(inclure_pitch=True),
            cache=cache,
        ).enrichir([_lead("A")])

        client2, sdk2 = _build_client(['{"score_interet": 50, "raison_score": "b"}'])
        e2 = EnricheurStage4(
            client=client2,
            config=ClaudeScoring(inclure_pitch=False),
            cache=cache,
        )
        e2.enrichir([_lead("A")])
        assert sdk2.calls == 1


# ─────────────────────────────────────────────────────────────────
# Erreurs (parse / API / budget)
# ─────────────────────────────────────────────────────────────────


class TestEnricherErreurs:
    def test_parse_error_garde_lead_sans_score(self, tmp_path):
        client, _ = _build_client(["pas du JSON"])
        config = ClaudeScoring()
        enricher = EnricheurStage4(
            client=client, config=config, cache=CacheStage4(tmp_path / "l4.sqlite")
        )
        leads_l4 = enricher.enrichir([_lead("A")])
        assert len(leads_l4) == 1
        l4 = leads_l4[0]
        assert l4.score_interet is None
        assert l4.top_lead is False
        assert l4.scoring_erreur is not None
        assert "parse_error" in l4.scoring_erreur

    def test_budget_exhausted_stoppe_les_appels_restants(self, tmp_path):
        # On configure un budget très bas → le 1er appel passe, mais ajouter_cout
        # va dépasser et raise BudgetExceededError.
        client, sdk = _build_client(
            ['{"score_interet": 50, "raison_score": "x"}'] * 5
        )
        # Forcer beaucoup de tokens → dépasse vite
        client.config.budget = BudgetGuard(plafond_eur=0.0000001)

        config = ClaudeScoring(inclure_pitch=False)
        enricher = EnricheurStage4(
            client=client, config=config, cache=CacheStage4(tmp_path / "l4.sqlite")
        )
        leads = [_lead(f"L{i}") for i in range(3)]
        leads_l4 = enricher.enrichir(leads)

        # On garde tous les leads, mais les suivants ont `budget_exhausted`
        assert len(leads_l4) == 3
        assert any("budget" in (lead.scoring_erreur or "") for lead in leads_l4)
        # Pas d'appel API au-delà du déclenchement
        assert sdk.calls <= 2


# ─────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────


class TestStatsL4:
    def test_stats_basiques(self, tmp_path):
        responses = [
            '{"score_interet": 80, "raison_score": "a", "pitch_propose": "p"}',
            '{"score_interet": 40, "raison_score": "b", "pitch_propose": "p"}',
            '{"score_interet": 90, "raison_score": "c", "pitch_propose": "p"}',
        ]
        client, _ = _build_client(responses)
        config = ClaudeScoring(seuil_top_lead=70)
        enricher = EnricheurStage4(
            client=client, config=config, cache=CacheStage4(tmp_path / "l4.sqlite")
        )
        leads_l4 = enricher.enrichir(
            [_lead("A"), _lead("B"), _lead("C")]
        )
        stats = enricher.stats_l4(leads_l4)
        assert stats["total"] == 3
        assert stats["scored"] == 3
        assert stats["top_leads"] == 2  # 80, 90
        assert stats["erreurs"] == 0
        assert stats["score_moyen"] == 70.0

    def test_stats_avec_erreurs(self, tmp_path):
        client, _ = _build_client(
            [
                '{"score_interet": 80, "raison_score": "ok"}',
                "json cassé",
            ]
        )
        enricher = EnricheurStage4(
            client=client,
            config=ClaudeScoring(inclure_pitch=False),
            cache=CacheStage4(tmp_path / "l4.sqlite"),
        )
        leads_l4 = enricher.enrichir([_lead("A"), _lead("B")])
        stats = enricher.stats_l4(leads_l4)
        assert stats["scored"] == 1
        assert stats["erreurs"] == 1


# ─────────────────────────────────────────────────────────────────
# Callback incrémental
# ─────────────────────────────────────────────────────────────────


class TestCallbackIncrementiel:
    def test_callback_appele_toutes_les_20(self, tmp_path):
        responses = ['{"score_interet": 50, "raison_score": "x"}'] * 25
        client, _ = _build_client(responses)
        appels: list[int] = []

        enricher = EnricheurStage4(
            client=client,
            config=ClaudeScoring(inclure_pitch=False),
            cache=CacheStage4(tmp_path / "l4.sqlite"),
            callback_save_incremental=lambda leads: appels.append(len(leads)),
        )
        enricher.enrichir([_lead(f"L{i}") for i in range(25)])
        # Callback à 20
        assert 20 in appels
