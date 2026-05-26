"""Dispatcher L1 : sélectionne la stratégie de découverte selon `cible.type`.

V0 : seule la cible `b2b` est câblée. L'API est en place pour que la V1
ajoute des rails (`b2c-particulier`, ...) sans toucher au pipeline.
"""

from __future__ import annotations

from .strategies.b2b_places import StrategieDecouverteB2B

_STRATEGIES: dict[str, type[StrategieDecouverteB2B]] = {
    "b2b": StrategieDecouverteB2B,
}


def strategie_decouverte(cible_type: str) -> type[StrategieDecouverteB2B]:
    """Retourne la classe de stratégie L1 pour ce type de cible.

    Lève NotImplementedError si le type n'est pas supporté en V0.
    """
    strategie = _STRATEGIES.get(cible_type)
    if strategie is None:
        raise NotImplementedError(
            f"Découverte L1 pour cible.type='{cible_type}' indisponible en V0 "
            "(B2B uniquement)."
        )
    return strategie
