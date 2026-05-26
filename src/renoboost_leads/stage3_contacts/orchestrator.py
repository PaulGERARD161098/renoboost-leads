"""Dispatcher L3 : sélectionne la stratégie de contacts selon `cible.type`.

V0 : seule la cible `b2b` est câblée. L'API est en place pour la V1.
"""

from __future__ import annotations

from .strategies.b2b_scraping import StrategieContactsB2B

_STRATEGIES: dict[str, type[StrategieContactsB2B]] = {
    "b2b": StrategieContactsB2B,
}


def strategie_contacts(cible_type: str) -> type[StrategieContactsB2B]:
    """Retourne la classe de stratégie L3 pour ce type de cible.

    Lève NotImplementedError si le type n'est pas supporté en V0.
    """
    strategie = _STRATEGIES.get(cible_type)
    if strategie is None:
        raise NotImplementedError(
            f"Contacts L3 pour cible.type='{cible_type}' indisponible en V0 "
            "(B2B uniquement)."
        )
    return strategie
