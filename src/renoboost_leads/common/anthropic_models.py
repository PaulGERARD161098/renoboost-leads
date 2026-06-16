"""Résolution des identifiants de modèles Anthropic.

Les libellés internes (config, pricing, Literal de validation) restent courts et
stables (« claude-haiku-4-5 ») ; on les traduit vers l'identifiant d'API **exact**
au moment de l'appel réseau. Sans ça, un alias non daté peut être rejeté par
l'API Anthropic (400 BadRequest) — cas observé en prod sur le scoring L4, où
chaque appel échouait silencieusement (leads sans score).

Source des identifiants : famille Claude 4.x (cf. doc Anthropic). Les modèles
déjà valides tels quels (ex. sonnet) ne sont pas listés → passthrough.
"""

from __future__ import annotations

# Libellé interne → identifiant d'API Anthropic exact (daté).
_API_MODEL_IDS: dict[str, str] = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}


def resolve_model_id(modele: str) -> str:
    """Traduit un libellé interne en identifiant d'API Anthropic valide.

    Passthrough pour les modèles déjà exacts (ex. « claude-sonnet-4-6 »).
    """
    return _API_MODEL_IDS.get(modele, modele)


__all__ = ["resolve_model_id"]
