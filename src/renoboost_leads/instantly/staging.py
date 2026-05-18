"""Workflow staging N2 — drafte les emails, attend validation humaine.

Quand l'agent décide d'envoyer une campagne cold mail, il NE pousse PAS
directement dans Instantly. Il :
1. Génère les emails rendus (step 1 de la séquence pour chaque lead)
2. Les écrit dans `data/cold_mail/staging/<staging_id>.json`
3. Alerte l'utilisateur par email (subject + lien validation)

L'utilisateur ouvre Streamlit (ou la CLI) → revoit les emails preview
par preview → clique "Valider" ou "Refuser" pour chacun. À la validation,
les emails approuvés sont effectivement poussés dans Instantly (création
campagne + add_leads + send).

Format staging JSON :
{
  "staging_id": "stg_abcdef",
  "cree_le": "2026-05-18T...",
  "secteur": "compta",
  "session_id": "20260518-...",
  "from_email": "paul@renoboost.fr",
  "items": [
    {
      "lead_id": "siren_123",
      "email_dest": "x@y.fr",
      "nom_dest": "Marie Dupont",
      "sujet": "...",
      "corps": "...",
      "etat": "en_attente",  // en_attente / valide / refuse / envoye
      "decide_le": null,
      "campagne_instantly_id": null
    }
  ]
}
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..settings import PROJECT_ROOT

STAGING_DIR_DEFAULT = PROJECT_ROOT / "data" / "cold_mail" / "staging"

ETATS_VALIDES = {"en_attente", "valide", "refuse", "envoye"}


@dataclass
class StagedItem:
    lead_id: str
    email_dest: str
    nom_dest: str
    sujet: str
    corps: str
    etat: str = "en_attente"
    decide_le: str | None = None
    campagne_instantly_id: str | None = None


@dataclass
class Staging:
    staging_id: str
    secteur: str
    session_id: str
    from_email: str
    items: list[StagedItem] = field(default_factory=list)
    cree_le: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "staging_id": self.staging_id,
            "cree_le": self.cree_le,
            "secteur": self.secteur,
            "session_id": self.session_id,
            "from_email": self.from_email,
            "items": [asdict(i) for i in self.items],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Staging:
        items = [StagedItem(**i) for i in raw.get("items", [])]
        return cls(
            staging_id=raw["staging_id"],
            cree_le=raw.get("cree_le") or datetime.now(timezone.utc).isoformat(),
            secteur=raw.get("secteur", ""),
            session_id=raw.get("session_id", ""),
            from_email=raw.get("from_email", ""),
            items=items,
        )


class StagingStore:
    """Persistance JSON des stagings."""

    def __init__(self, dir_path: Path | None = None) -> None:
        self.dir = dir_path or STAGING_DIR_DEFAULT
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, staging_id: str) -> Path:
        return self.dir / f"{staging_id}.json"

    def save(self, staging: Staging) -> Path:
        p = self._path(staging.staging_id)
        p.write_text(
            json.dumps(staging.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return p

    def load(self, staging_id: str) -> Staging:
        p = self._path(staging_id)
        if not p.exists():
            raise FileNotFoundError(f"staging absent : {staging_id}")
        raw = json.loads(p.read_text(encoding="utf-8"))
        return Staging.from_dict(raw)

    def list(self) -> list[dict]:
        """Liste résumée — id, secteur, session, créé_le, compteurs etats."""
        out = []
        if not self.dir.exists():
            return out
        for p in sorted(self.dir.glob("*.json"), reverse=True):
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            items = raw.get("items", [])
            etats: dict[str, int] = {e: 0 for e in ETATS_VALIDES}
            for it in items:
                e = it.get("etat", "?")
                etats[e] = etats.get(e, 0) + 1
            out.append(
                {
                    "staging_id": raw["staging_id"],
                    "secteur": raw.get("secteur"),
                    "session_id": raw.get("session_id"),
                    "cree_le": raw.get("cree_le"),
                    "total": len(items),
                    "etats": etats,
                }
            )
        return out

    def set_etat(self, staging_id: str, lead_id: str, etat: str) -> Staging:
        """Met à jour l'état d'un item et persiste."""
        if etat not in ETATS_VALIDES:
            raise ValueError(f"état invalide : '{etat}' (valides : {ETATS_VALIDES})")
        s = self.load(staging_id)
        item = next((i for i in s.items if i.lead_id == lead_id), None)
        if item is None:
            raise KeyError(f"lead {lead_id} absent du staging {staging_id}")
        item.etat = etat
        item.decide_le = datetime.now(timezone.utc).isoformat()
        self.save(s)
        return s


def nouveau_staging_id() -> str:
    return f"stg_{uuid.uuid4().hex[:8]}"
