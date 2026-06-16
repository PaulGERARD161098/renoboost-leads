"""Invariants des identifiants de modèles Anthropic.

Garde-fou anti-régression : le scoring L4 a échoué en prod (400 BadRequest) parce
que le libellé interne « claude-haiku-4-5 » était envoyé tel quel à l'API, qui
attend l'identifiant daté. On verrouille la résolution + la cohérence avec les
modèles réellement configurés dans le code.
"""

from __future__ import annotations

from renoboost_leads.common.anthropic_models import resolve_model_id
from renoboost_leads.stage4_prospection.client import (
    _PRICING_USD_PER_MTOK,
    ClaudeClientConfig,
)


def test_haiku_resolu_vers_id_date():
    # L'alias non daté doit être traduit vers l'identifiant d'API exact.
    assert resolve_model_id("claude-haiku-4-5") == "claude-haiku-4-5-20251001"


def test_sonnet_passthrough():
    # Modèle déjà exact : inchangé.
    assert resolve_model_id("claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_modele_inconnu_passthrough():
    assert resolve_model_id("modele-x") == "modele-x"


def test_modele_par_defaut_l4_est_resoluble_et_tarife():
    # Le modèle L4 par défaut doit avoir un identifiant d'API résolu (≠ vide) et
    # une entrée de pricing — sinon coût mal estimé / appel rejeté en silence.
    defaut = ClaudeClientConfig(api_key="x").modele
    assert resolve_model_id(defaut)
    assert defaut in _PRICING_USD_PER_MTOK
