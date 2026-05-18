"""Métriques agent — compteur d'appels par outil + temps cumulé.

Persistance JSON sous `data/agent/metrics.json`. Pas de période glissante,
agrégat depuis le début (l'utilisateur peut purger manuellement). Sert à
voir quels outils l'agent appelle le plus, où il passe son temps, et où
investir des améliorations (ex : si `run_pipeline` représente 80% du
temps, c'est normal — c'est lui qui fait le vrai travail).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..settings import PROJECT_ROOT

METRICS_DEFAULT_PATH = PROJECT_ROOT / "data" / "agent" / "metrics.json"


@dataclass
class ToolMetric:
    name: str
    count: int = 0
    duration_total_s: float = 0.0
    erreurs: int = 0


@dataclass
class AgentMetrics:
    cycles_total: int = 0
    outils_total: int = 0
    cout_total_eur: float = 0.0
    par_outil: dict[str, ToolMetric] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "cycles_total": self.cycles_total,
            "outils_total": self.outils_total,
            "cout_total_eur": round(self.cout_total_eur, 6),
            "par_outil": {n: asdict(m) for n, m in self.par_outil.items()},
        }


class MetricsStore:
    """Lecture/écriture JSON de l'agrégat de métriques."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or METRICS_DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AgentMetrics:
        if not self.path.exists():
            return AgentMetrics()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AgentMetrics()
        m = AgentMetrics(
            cycles_total=int(raw.get("cycles_total", 0)),
            outils_total=int(raw.get("outils_total", 0)),
            cout_total_eur=float(raw.get("cout_total_eur", 0.0)),
        )
        for name, data in (raw.get("par_outil") or {}).items():
            m.par_outil[name] = ToolMetric(
                name=name,
                count=int(data.get("count", 0)),
                duration_total_s=float(data.get("duration_total_s", 0.0)),
                erreurs=int(data.get("erreurs", 0)),
            )
        return m

    def save(self, metrics: AgentMetrics) -> None:
        self.path.write_text(
            json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def record_cycle(
        self,
        *,
        cout_eur: float,
        outils: list[dict],
    ) -> AgentMetrics:
        """Enregistre 1 cycle (cumule cycles_total, cout, par-outil)."""
        m = self.load()
        m.cycles_total += 1
        m.cout_total_eur = round(m.cout_total_eur + cout_eur, 6)
        for o in outils:
            name = o.get("name") or "?"
            duration = float(o.get("duration_s") or 0.0)
            erreur = bool(o.get("erreur") or False)
            tm = m.par_outil.setdefault(name, ToolMetric(name=name))
            tm.count += 1
            tm.duration_total_s = round(tm.duration_total_s + duration, 4)
            if erreur:
                tm.erreurs += 1
            m.outils_total += 1
        self.save(m)
        return m
