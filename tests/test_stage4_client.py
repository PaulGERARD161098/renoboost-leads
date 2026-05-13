"""Tests du wrapper Claude (parsing JSON + coût + retry)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from renoboost_leads.common.budget_guard import BudgetExceededError, BudgetGuard
from renoboost_leads.stage4_prospection.client import (
    ClaudeClient,
    ClaudeClientConfig,
    ClaudeParseError,
    _extraire_json,
    cout_eur,
)

# ─────────────────────────────────────────────────────────────────
# _extraire_json
# ─────────────────────────────────────────────────────────────────


class TestExtraireJson:
    def test_json_pur(self):
        assert _extraire_json('{"a": 1}') == {"a": 1}

    def test_json_avec_espaces(self):
        assert _extraire_json("   {\"a\": 1}   ") == {"a": 1}

    def test_json_dans_fenced_codeblock(self):
        texte = '```json\n{"score": 75, "raison": "ok"}\n```'
        assert _extraire_json(texte) == {"score": 75, "raison": "ok"}

    def test_json_dans_codeblock_sans_lang(self):
        texte = '```\n{"score": 50}\n```'
        assert _extraire_json(texte) == {"score": 50}

    def test_invalide_leve(self):
        with pytest.raises(ClaudeParseError):
            _extraire_json("pas du json")


# ─────────────────────────────────────────────────────────────────
# cout_eur
# ─────────────────────────────────────────────────────────────────


class TestCoutEur:
    def test_haiku_facturation_basique(self):
        c = cout_eur("claude-haiku-4-5", tokens_in=500, tokens_out=200)
        # 500 * 0.80 / 1M + 200 * 4.00 / 1M = 0.0004 + 0.0008 = $0.0012 ≈ €0.001116
        assert 0.0008 < c < 0.0015

    def test_sonnet_plus_cher_que_haiku(self):
        c_haiku = cout_eur("claude-haiku-4-5", 500, 200)
        c_sonnet = cout_eur("claude-sonnet-4-6", 500, 200)
        assert c_sonnet > 3 * c_haiku  # Sonnet ~3.75× Haiku

    def test_modele_inconnu_fallback_sonnet(self):
        # Le pricing inconnu ne fait pas crasher l'app
        c = cout_eur("claude-mystere", 100, 100)
        assert c > 0


# ─────────────────────────────────────────────────────────────────
# ClaudeClient (mock SDK)
# ─────────────────────────────────────────────────────────────────


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeContentBlock:
    text: str


@dataclass
class _FakeMessage:
    content: list
    usage: _FakeUsage


class _FakeMessagesAPI:
    def __init__(self, response_text: str, tokens_in: int = 100, tokens_out: int = 50):
        self.response_text = response_text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage(
            content=[_FakeContentBlock(text=self.response_text)],
            usage=_FakeUsage(self.tokens_in, self.tokens_out),
        )


class _FakeSDK:
    def __init__(self, messages_api):
        self.messages = messages_api


class TestClaudeClientScorer:
    def _build(self, response_text: str, **kwargs):
        api = _FakeMessagesAPI(response_text, **kwargs)
        sdk = _FakeSDK(api)
        client = ClaudeClient(
            ClaudeClientConfig(
                api_key="sk-fake", modele="claude-haiku-4-5", sdk_client=sdk
            )
        )
        return client, api

    def test_reponse_valide_avec_pitch(self):
        client, _ = self._build(
            '{"score_interet": 78, "raison_score": "PME mécanique, ICP type", '
            '"pitch_propose": "Bonjour, ..."}'
        )
        rep = client.scorer("prompt")
        assert rep.score_interet == 78
        assert rep.raison_score == "PME mécanique, ICP type"
        assert rep.pitch_propose == "Bonjour, ..."
        assert rep.cout_eur > 0
        assert rep.modele == "claude-haiku-4-5"

    def test_reponse_sans_pitch(self):
        client, _ = self._build('{"score_interet": 50, "raison_score": "moyen"}')
        rep = client.scorer("prompt")
        assert rep.pitch_propose is None

    def test_score_borne_a_100(self):
        client, _ = self._build('{"score_interet": 250, "raison_score": "wow"}')
        rep = client.scorer("prompt")
        assert rep.score_interet == 100

    def test_score_borne_a_0(self):
        client, _ = self._build('{"score_interet": -5, "raison_score": "nope"}')
        rep = client.scorer("prompt")
        assert rep.score_interet == 0

    def test_json_invalide_leve(self):
        client, _ = self._build("pas du JSON")
        with pytest.raises(ClaudeParseError):
            client.scorer("prompt")

    def test_champs_obligatoires_manquants_leve(self):
        client, _ = self._build('{"score_interet": 50}')
        with pytest.raises(ClaudeParseError):
            client.scorer("prompt")

    def test_score_non_entier_leve(self):
        client, _ = self._build('{"score_interet": "abc", "raison_score": "x"}')
        with pytest.raises(ClaudeParseError):
            client.scorer("prompt")

    def test_budget_guard_applique(self):
        client, _ = self._build(
            '{"score_interet": 50, "raison_score": "x"}',
            tokens_in=500_000,
            tokens_out=200_000,
        )
        # On plafonne à 1 centime → 700k tokens vont dépasser largement
        client.config.budget = BudgetGuard(plafond_eur=0.01)
        with pytest.raises(BudgetExceededError):
            client.scorer("prompt")

    def test_budget_guard_compte_cout(self):
        client, _ = self._build(
            '{"score_interet": 50, "raison_score": "x"}',
            tokens_in=1000,
            tokens_out=500,
        )
        budget = BudgetGuard(plafond_eur=1.0)
        client.config.budget = budget
        client.scorer("prompt")
        assert budget.cout_actuel_eur > 0
        assert budget.nb_appels == 1

    def test_reponse_fenced_codeblock_parse_ok(self):
        client, _ = self._build(
            '```json\n{"score_interet": 80, "raison_score": "ok"}\n```'
        )
        rep = client.scorer("prompt")
        assert rep.score_interet == 80
