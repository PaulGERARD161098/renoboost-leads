"""Outil `prioritize_leads` — scoring chaud/tiède/froid d'une session.

Lit `etage4_prospection.csv` si dispo (a score Claude), sinon
`etage3_5_enrichment.csv`, sinon `etage3_contacts.csv`. Tri descendant
sur le score combiné :

- +50 si email vérifié Dropcontact OU email scrapé
- +20 si tel direct OU téléphone standard
- +20 si dirigeant_nom rempli
- + score_interet Claude (0-100) si présent

Renvoie top N + médiane des scores + 3 buckets (chaud >=120, tiède 70-119,
froid < 70).
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

from .sessions import OUTPUT_ROOT, STAGE_FILES


def _lire_csv(p: Path) -> list[dict]:
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _has(row: dict, *keys: str) -> bool:
    return any(row.get(k) and str(row.get(k)).strip() for k in keys)


def _score_lead(row: dict) -> float:
    s = 0.0
    if _has(row, "email_dropcontact", "email_verifie", "email_principal", "emails_verifies"):
        s += 50
    if _has(row, "telephone_direct_dropcontact", "tel_direct", "telephone"):
        s += 20
    if _has(row, "dirigeant_nom", "nom_dirigeant_dropcontact"):
        s += 20
    # score Claude L4
    raw = row.get("score_interet") or row.get("score") or ""
    try:
        s += float(str(raw).replace(",", "."))
    except (ValueError, TypeError):
        pass
    return round(s, 2)


def _bucket(score: float) -> str:
    if score >= 120:
        return "chaud"
    if score >= 70:
        return "tiede"
    return "froid"


def _resoudre_source(dossier: Path) -> Path | None:
    for stage in ("4", "3.5", "3"):
        p = dossier / STAGE_FILES[stage]
        if p.exists():
            return p
    return None


def prioritize_leads(session_id: str, top_n: int = 10) -> dict:
    """Score + tri + top N + distribution chaud/tiède/froid."""
    dossier = OUTPUT_ROOT / session_id
    if not dossier.is_dir():
        return {"error": f"session inconnue : '{session_id}'"}
    source = _resoudre_source(dossier)
    if source is None:
        return {"error": "aucun CSV exploitable (étages 3, 3.5, 4 absents)"}

    rows = _lire_csv(source)
    if not rows:
        return {
            "session_id": session_id,
            "source": source.name,
            "top": [],
            "distribution": {"chaud": 0, "tiede": 0, "froid": 0},
            "score_mediane": 0.0,
        }

    scored = []
    for r in rows:
        s = _score_lead(r)
        scored.append(
            {
                "nom": r.get("nom") or r.get("raison_sociale") or "",
                "siren": r.get("siren", ""),
                "ville": r.get("ville", ""),
                "email": (
                    r.get("email_dropcontact")
                    or r.get("email_verifie")
                    or r.get("email_principal")
                    or ""
                ),
                "telephone": (
                    r.get("telephone_direct_dropcontact")
                    or r.get("tel_direct")
                    or r.get("telephone")
                    or ""
                ),
                "dirigeant": (
                    r.get("nom_dirigeant_dropcontact") or r.get("dirigeant_nom") or ""
                ),
                "score_combine": s,
                "bucket": _bucket(s),
            }
        )

    scored.sort(key=lambda x: x["score_combine"], reverse=True)
    n = max(1, int(top_n))
    distrib = {"chaud": 0, "tiede": 0, "froid": 0}
    for s in scored:
        distrib[s["bucket"]] += 1
    return {
        "session_id": session_id,
        "source": source.name,
        "total": len(scored),
        "score_mediane": round(statistics.median(x["score_combine"] for x in scored), 2),
        "distribution": distrib,
        "top": scored[:n],
    }


SCHEMAS = [
    {
        "name": "prioritize_leads",
        "description": (
            "Score et trie les leads d'une session (utilise L4 si dispo, sinon L3.5, "
            "sinon L3). Renvoie top N + distribution chaud/tiède/froid. Score = "
            "email (+50) + tel (+20) + dirigeant (+20) + score Claude L4."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "top_n": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["session_id"],
        },
    }
]

DISPATCH = {"prioritize_leads": prioritize_leads}
