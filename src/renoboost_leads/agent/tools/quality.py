"""Outil `diagnose_quality` — calcule la qualité d'une session pilote.

Métriques retournées (sur la base d'`etage3_contacts.csv` qui est l'étage
le plus riche post-scraping, avant Dropcontact) :
- % SIREN matché (siren non vide)
- % dirigeant identifié (dirigeant_nom non vide)
- % email scrapé (email_principal non vide)
- % site web identifié
- distribution effectif (PME 10-49 = cible Phase 1)
- distribution NAF (top 5)
- 5 anomalies (lignes sans rien)

Sur L3.5 (si présent) on ajoute :
- % email vérifié Dropcontact
- % tel direct

Critères de validation pilote Phase 1 (du handoff utilisateur) :
- matching SIREN > 80%
- dirigeant identifié sur majorité
- au moins 1 email scrapé ~50%
- effectif/NAF cohérents PME 10-49 tertiaire
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .sessions import OUTPUT_ROOT, STAGE_FILES


def _lire_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def _has(row: dict, key: str) -> bool:
    v = row.get(key)
    return bool(v and str(v).strip())


def _metriques_l3(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"row_count": 0}
    siren_ok = sum(1 for r in rows if _has(r, "siren"))
    dirigeant_ok = sum(1 for r in rows if _has(r, "dirigeant_nom"))
    # email peut être stocké sous diverses clés selon l'évolution du schéma
    email_ok = sum(
        1
        for r in rows
        if _has(r, "email_principal") or _has(r, "email") or _has(r, "emails")
    )
    site_ok = sum(1 for r in rows if _has(r, "site_web") or _has(r, "website"))
    effectifs = Counter(
        (r.get("tranche_effectif") or r.get("effectif") or "n/a").strip()
        for r in rows
    )
    nafs = Counter(
        (r.get("naf") or r.get("code_naf") or "n/a").strip()
        for r in rows
    )
    return {
        "row_count": n,
        "pct_siren_matche": _pct(siren_ok, n),
        "pct_dirigeant_identifie": _pct(dirigeant_ok, n),
        "pct_email_scrape": _pct(email_ok, n),
        "pct_site_web": _pct(site_ok, n),
        "distribution_effectif": dict(effectifs.most_common(8)),
        "distribution_naf_top5": dict(nafs.most_common(5)),
    }


def _metriques_l3_5(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"row_count_3_5": 0}
    email_verif = sum(1 for r in rows if _has(r, "email_verifie"))
    tel_direct = sum(1 for r in rows if _has(r, "tel_direct"))
    return {
        "row_count_3_5": n,
        "pct_email_verifie_dropcontact": _pct(email_verif, n),
        "pct_tel_direct": _pct(tel_direct, n),
    }


def _verdict_pilote_phase1(m3: dict) -> dict:
    """Applique les seuils Phase 1 du handoff."""
    criteres = []
    siren = m3.get("pct_siren_matche", 0.0)
    criteres.append(
        {
            "critere": "matching SIREN > 80%",
            "valeur": siren,
            "ok": siren > 80,
        }
    )
    dirigeant = m3.get("pct_dirigeant_identifie", 0.0)
    criteres.append(
        {
            "critere": "dirigeant identifié sur majorité (> 50%)",
            "valeur": dirigeant,
            "ok": dirigeant > 50,
        }
    )
    email = m3.get("pct_email_scrape", 0.0)
    criteres.append(
        {
            "critere": "email scrapé ~50% (> 40%)",
            "valeur": email,
            "ok": email > 40,
        }
    )
    go = all(c["ok"] for c in criteres)
    return {"go_phase2": go, "criteres": criteres}


def diagnose_quality(session_id: str) -> dict:
    """Retourne métriques + verdict pilote pour une session."""
    dossier = OUTPUT_ROOT / session_id
    if not dossier.is_dir():
        return {"error": f"session inconnue : '{session_id}'"}

    fichier_l3 = dossier / STAGE_FILES["3"]
    if not fichier_l3.exists():
        return {
            "session_id": session_id,
            "error": "etage3_contacts.csv absent — lance au moins les étages 1,2,3 d'abord.",
        }
    rows_l3 = _lire_csv(fichier_l3)
    m3 = _metriques_l3(rows_l3)

    result: dict = {
        "session_id": session_id,
        "metriques_l3": m3,
        "verdict_pilote_phase1": _verdict_pilote_phase1(m3),
    }

    fichier_l3_5 = dossier / STAGE_FILES["3.5"]
    if fichier_l3_5.exists():
        result["metriques_l3_5"] = _metriques_l3_5(_lire_csv(fichier_l3_5))

    # 5 anomalies = lignes sans SIREN ni email ni dirigeant
    anomalies = [
        {k: r.get(k, "") for k in ("nom", "ville", "siren")}
        for r in rows_l3
        if not (
            _has(r, "siren")
            or _has(r, "email_principal")
            or _has(r, "dirigeant_nom")
        )
    ][:5]
    result["anomalies_echantillon"] = anomalies
    return result


SCHEMAS = [
    {
        "name": "diagnose_quality",
        "description": (
            "Calcule la qualité d'une session de prospection : % SIREN matché, "
            "dirigeant identifié, email scrapé, distribution effectif/NAF, "
            "anomalies. Applique les seuils Phase 1 pilote (SIREN>80%, "
            "dirigeant>50%, email>40%) et renvoie un verdict go/no-go."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Identifiant de session à diagnostiquer.",
                }
            },
            "required": ["session_id"],
        },
    }
]

DISPATCH = {"diagnose_quality": diagnose_quality}
