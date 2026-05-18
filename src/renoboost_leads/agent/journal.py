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

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..settings import PROJECT_ROOT

JOURNAL_DEFAULT_PATH = PROJECT_ROOT / "data" / "agent" / "journal.md"

# Au-delà de ce seuil (octets), `append` archive le fichier complet sous
# `journal-archive-YYYYMM.md` et redémarre vide. Évite que le journal
# gonfle indéfiniment et coûte des tokens à chaque cycle.
DEFAULT_ROTATE_BYTES = 200_000  # ~200 KB

# Plafond bytes du contexte injecté au LLM. Si la concat des N entrées
# récentes dépasse, on tronque par le début (on garde le plus récent).
DEFAULT_CONTEXT_MAX_BYTES = 10_000  # ~10 KB ~ 2.5k tokens


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
    """Wrapper append-only autour du fichier markdown.

    Rotation : si le fichier dépasse `rotate_bytes`, il est archivé sous
    `<basename>-archive-YYYYMM.md` (dans le même dossier) avant d'être
    redémarré vide. Les archives ne sont jamais relues — elles servent
    d'historique pour humain ou compliance.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        rotate_bytes: int = DEFAULT_ROTATE_BYTES,
        context_max_bytes: int = DEFAULT_CONTEXT_MAX_BYTES,
    ) -> None:
        self.path = path or JOURNAL_DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rotate_bytes = int(rotate_bytes)
        self.context_max_bytes = int(context_max_bytes)

    def _rotate_si_besoin(self) -> Path | None:
        """Si fichier > seuil, déplace vers archive et renvoie le chemin."""
        if not self.path.exists():
            return None
        if self.path.stat().st_size <= self.rotate_bytes:
            return None
        suffixe = datetime.now(timezone.utc).strftime("%Y%m")
        archive = self.path.with_name(f"{self.path.stem}-archive-{suffixe}.md")
        # Si une archive existe déjà ce mois-ci, on append à la fin
        if archive.exists():
            with archive.open("ab") as fa, self.path.open("rb") as fc:
                fa.write(b"\n")
                shutil.copyfileobj(fc, fa)
            self.path.unlink()
        else:
            shutil.move(str(self.path), str(archive))
        return archive

    def append(self, entry: JournalEntry) -> None:
        self._rotate_si_besoin()
        # Le fichier peut ne plus exister après rotation — recréer dans 'a'.
        with self.path.open("a", encoding="utf-8") as f:
            try:
                taille = self.path.stat().st_size
            except FileNotFoundError:
                taille = 0
            if taille > 0:
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
        """Concatène les n dernières entrées, tronquées à `context_max_bytes`.

        Si la concat dépasse le plafond, on enlève les plus vieilles entrées
        jusqu'à passer sous — on garde toujours la plus récente, quitte à
        retourner une seule entrée.
        """
        entries = self.read_recent(n)
        if not entries:
            return "_(journal vide — premier cycle de l'agent)_"
        # On garde toujours la dernière, puis on rajoute en remontant tant
        # qu'on reste sous le plafond.
        retenues = [entries[-1]]
        taille = len(retenues[0].encode("utf-8"))
        for e in reversed(entries[:-1]):
            t = len(e.encode("utf-8")) + 2  # séparateur \n\n
            if taille + t > self.context_max_bytes:
                break
            retenues.insert(0, e)
            taille += t
        return "\n\n".join(retenues)
