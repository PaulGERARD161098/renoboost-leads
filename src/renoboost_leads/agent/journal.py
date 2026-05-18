"""Journal markdown de l'agent — décisions, appels d'outils, alertes.

Un seul fichier `data/agent/journal.md` append-only, lu en début de chaque
cycle agent pour donner du contexte historique au LLM. Format :

    ## 2026-05-18T09:12:34+00:00 — cycle_id=ab12cd
    **Instruction** : lance un pilote sur le 62, secteur BTP, 50 leads
    **Décision** : run_pipeline(config=config/pilote_62.yaml, stages=1,2,3)
    **Résultat** : session=20260518-091234-pilote62, 47 leads L3 dont 38 SIREN matché
    **Suite** : diagnose_quality → si > 70% matché, lancer 3.5+4 dry-run

Pas de base, pas de vecteur — un humain doit pouvoir le lire en 30 secondes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..settings import PROJECT_ROOT

JOURNAL_DEFAULT_PATH = PROJECT_ROOT / "data" / "agent" / "journal.md"


@dataclass
class JournalEntry:
    """Une entrée du journal."""

    cycle_id: str
    instruction: str
    decision: str
    resultat: str = ""
    suite: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_markdown(self) -> str:
        parts = [f"## {self.timestamp} — cycle_id={self.cycle_id}"]
        parts.append(f"**Instruction** : {self.instruction.strip()}")
        parts.append(f"**Décision** : {self.decision.strip()}")
        if self.resultat:
            parts.append(f"**Résultat** : {self.resultat.strip()}")
        if self.suite:
            parts.append(f"**Suite** : {self.suite.strip()}")
        return "\n".join(parts) + "\n"


class Journal:
    """Wrapper append-only autour du fichier markdown."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or JOURNAL_DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: JournalEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            if self.path.stat().st_size > 0:
                f.write("\n")
            f.write(entry.to_markdown())

    def read_recent(self, n: int = 10) -> list[str]:
        """Renvoie les `n` dernières entrées (blocs markdown) pour contexte."""
        if not self.path.exists():
            return []
        contenu = self.path.read_text(encoding="utf-8")
        blocs = [b for b in contenu.split("\n## ") if b.strip()]
        if not blocs:
            return []
        # Le 1er bloc commence par "## " (ou est déjà préfixé) ; uniformise.
        normalises = []
        for i, b in enumerate(blocs):
            if i == 0 and b.startswith("## "):
                normalises.append(b)
            else:
                normalises.append("## " + b)
        return normalises[-n:]

    def context_pour_agent(self, n: int = 5) -> str:
        """Concatène les n dernières entrées en bloc markdown injectable au prompt."""
        entries = self.read_recent(n)
        if not entries:
            return "_(journal vide — premier cycle de l'agent)_"
        return "\n\n".join(entries)
