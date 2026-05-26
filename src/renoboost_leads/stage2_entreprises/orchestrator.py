"""Dispatcher L2 : sélectionne la stratégie d'enrichissement selon `cible.type`.

V0 : seule la cible `b2b` est câblée. L'API est en place pour la V1.
"""

from __future__ import annotations

from .strategies.b2b_sirene import StrategieEntreprisesB2B

_STRATEGIES: dict[str, type[StrategieEntreprisesB2B]] = {
    "b2b": StrategieEntreprisesB2B,
}


def strategie_entreprises(cible_type: str) -> type[StrategieEntreprisesB2B]:
    """Retourne la classe de stratégie L2 pour ce type de cible.

    Lève NotImplementedError si le type n'est pas supporté en V0.
    """
    strategie = _STRATEGIES.get(cible_type)
    if strategie is None:
        raise NotImplementedError(
            f"Enrichissement L2 pour cible.type='{cible_type}' indisponible en V0 "
            "(B2B uniquement)."
        )
    return strategie
