"""Outils exposés à l'agent Claude via tool-use.

Chaque outil = une fonction Python pure (sans état) qui prend un dict
d'arguments JSON et renvoie un dict sérialisable. Le runner (palier 5)
assemble la liste de schémas et dispatche les appels.

Convention :
- Module = catégorie (sessions, pipeline, quality, config, leads, notify)
- Chaque module expose `SCHEMAS: list[dict]` et `DISPATCH: dict[str, Callable]`
"""

from __future__ import annotations

from . import cold_mail, notify, pipeline, quality, report, sessions, workflow
from . import config as cfg_tools
from . import leads as leads_tools


def all_schemas() -> list[dict]:
    """Concat des schémas tool-use à passer à l'API Claude."""
    return [
        *sessions.SCHEMAS,
        *pipeline.SCHEMAS,
        *quality.SCHEMAS,
        *cfg_tools.SCHEMAS,
        *leads_tools.SCHEMAS,
        *notify.SCHEMAS,
        *cold_mail.SCHEMAS,
        *report.SCHEMAS,
        *workflow.SCHEMAS,
    ]


def all_dispatch() -> dict:
    """Concat des dispatchers pour le runner."""
    d: dict = {}
    for mod in (
        sessions,
        pipeline,
        quality,
        cfg_tools,
        leads_tools,
        notify,
        cold_mail,
        report,
        workflow,
    ):
        d.update(mod.DISPATCH)
    return d
