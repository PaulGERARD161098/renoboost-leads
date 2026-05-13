"""Étage 4 — Scoring d'intérêt + pitch proposé via Claude."""

from .client import ClaudeClient, ClaudeClientConfig, ClaudeReponse
from .enricher import EnricheurStage4
from .prompt_template import (
    CONTEXTE_CLIENT_DEFAUT,
    PROMPT_VERSION,
    construire_prompt,
)

__all__ = [
    "ClaudeClient",
    "ClaudeClientConfig",
    "ClaudeReponse",
    "EnricheurStage4",
    "CONTEXTE_CLIENT_DEFAUT",
    "PROMPT_VERSION",
    "construire_prompt",
]
