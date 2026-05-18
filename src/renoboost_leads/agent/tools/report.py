"""Outil `generate_report` — rapport HTML autonome d'une session.

Produit un fichier HTML unique (CSS inline, aucune ressource externe)
résumant une session de prospection : campagne, KPI qualité, tableau des
leads, verdict diagnostic pilote, sources.

Le client (ou Paul) peut l'ouvrir dans un navigateur et faire
**Ctrl+P → Enregistrer en PDF** pour un livrable papier.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Template

from ...settings import PROJECT_ROOT
from .quality import _metriques_l3, _metriques_l3_5, _verdict_pilote_phase1
from .sessions import OUTPUT_ROOT, STAGE_FILES

# Colonnes affichées dans le tableau leads (ordre = lisibilité commerciale).
COLONNES_LEADS = [
    ("nom", "Raison sociale"),
    ("ville", "Ville"),
    ("siren", "SIREN"),
    ("dirigeant_nom", "Dirigeant"),
    ("email_principal", "Email"),
    ("telephone", "Téléphone"),
    ("site_web", "Site"),
    ("tranche_effectif", "Effectif"),
]


_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Rapport RénoBoost — {{ campaign }}</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1a1a1a;
    margin: 0;
    padding: 32px;
    background: #fafafa;
    line-height: 1.5;
  }
  .container { max-width: 1100px; margin: 0 auto; background: white;
    padding: 40px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
  h1 { margin: 0 0 4px 0; font-size: 28px; color: #0f4c81; }
  h2 { margin-top: 36px; margin-bottom: 12px; font-size: 18px;
    border-bottom: 2px solid #0f4c81; padding-bottom: 4px; color: #0f4c81; }
  .meta { color: #666; font-size: 14px; margin-bottom: 24px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 16px; margin: 16px 0 24px 0; }
  .kpi { background: #f0f7ff; padding: 16px; border-radius: 6px;
    border-left: 3px solid #0f4c81; }
  .kpi .label { font-size: 12px; color: #555; text-transform: uppercase;
    letter-spacing: 0.5px; }
  .kpi .value { font-size: 26px; font-weight: 600; color: #0f4c81;
    margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px;
    margin: 8px 0; }
  th { background: #0f4c81; color: white; text-align: left; padding: 8px;
    font-weight: 500; }
  td { padding: 8px; border-bottom: 1px solid #eee; }
  tr:nth-child(even) td { background: #fafafa; }
  .verdict { padding: 16px; border-radius: 6px; margin: 16px 0;
    font-weight: 500; }
  .verdict.go { background: #e6f6e6; border-left: 4px solid #2c8a2c;
    color: #1a5a1a; }
  .verdict.nogo { background: #fde6e6; border-left: 4px solid #c82c2c;
    color: #6a1a1a; }
  .criteres { list-style: none; padding: 0; margin: 12px 0; }
  .criteres li { padding: 6px 0; border-bottom: 1px solid #eee;
    font-size: 14px; }
  .criteres .ok { color: #2c8a2c; }
  .criteres .ko { color: #c82c2c; }
  .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #ddd;
    font-size: 12px; color: #999; text-align: center; }
  .empty { color: #999; font-style: italic; padding: 12px;
    background: #fafafa; border-radius: 4px; }
  @media print {
    body { background: white; padding: 0; }
    .container { box-shadow: none; padding: 16px; }
  }
</style>
</head>
<body>
<div class="container">

  <h1>Rapport de prospection</h1>
  <div class="meta">
    <strong>Campagne :</strong> {{ campaign }}<br>
    <strong>Session :</strong> {{ session_id }}<br>
    <strong>Période :</strong> {{ debut }} → {{ fin }}<br>
    <strong>Étages traités :</strong> {{ stages|join(', ') }}
  </div>

  <h2>Indicateurs qualité</h2>
  <div class="kpi-grid">
    <div class="kpi">
      <div class="label">Leads identifiés</div>
      <div class="value">{{ metriques.row_count }}</div>
    </div>
    <div class="kpi">
      <div class="label">SIREN matchés</div>
      <div class="value">{{ metriques.pct_siren_matche }}%</div>
    </div>
    <div class="kpi">
      <div class="label">Dirigeant identifié</div>
      <div class="value">{{ metriques.pct_dirigeant_identifie }}%</div>
    </div>
    <div class="kpi">
      <div class="label">Email scrapé</div>
      <div class="value">{{ metriques.pct_email_scrape }}%</div>
    </div>
  </div>

  <h2>Verdict pilote Phase 1</h2>
  {% if verdict.go_phase2 %}
    <div class="verdict go">✓ GO Phase 2 — tous les critères pilote sont
      atteints.</div>
  {% else %}
    <div class="verdict nogo">✗ NO-GO Phase 2 — au moins un critère pilote
      n'est pas atteint.</div>
  {% endif %}
  <ul class="criteres">
    {% for c in verdict.criteres %}
    <li>
      <span class="{{ 'ok' if c.ok else 'ko' }}">
        {{ '✓' if c.ok else '✗' }}
      </span>
      <strong>{{ c.critere }}</strong> — mesuré : {{ c.valeur }}%
    </li>
    {% endfor %}
  </ul>

  <h2>Top {{ leads|length }} leads</h2>
  {% if leads %}
  <table>
    <thead>
      <tr>
        {% for _, label in colonnes %}<th>{{ label }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for lead in leads %}
      <tr>
        {% for key, _ in colonnes %}
        <td>{{ lead.get(key, '') }}</td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="empty">Aucun lead disponible pour cette session.</div>
  {% endif %}

  {% if effectifs %}
  <h2>Distribution effectifs</h2>
  <table>
    <thead><tr><th>Tranche</th><th>Nombre</th></tr></thead>
    <tbody>
      {% for tranche, n in effectifs.items() %}
      <tr><td>{{ tranche }}</td><td>{{ n }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if metriques_l3_5 %}
  <h2>Enrichissement Dropcontact (L3.5)</h2>
  <div class="kpi-grid">
    <div class="kpi">
      <div class="label">Lignes L3.5</div>
      <div class="value">{{ metriques_l3_5.row_count_3_5 }}</div>
    </div>
    <div class="kpi">
      <div class="label">Email vérifié</div>
      <div class="value">
        {{ metriques_l3_5.pct_email_verifie_dropcontact }}%
      </div>
    </div>
    <div class="kpi">
      <div class="label">Tél. direct</div>
      <div class="value">{{ metriques_l3_5.pct_tel_direct }}%</div>
    </div>
  </div>
  {% endif %}

  <h2>Sources</h2>
  <ul>
    <li><strong>L1 — Découverte</strong> : Google Places API</li>
    <li><strong>L2 — Entreprises</strong> : data.gouv.fr (Sirene)</li>
    <li><strong>L3 — Contacts</strong> : scraping site web + détection
      patterns email</li>
    {% if metriques_l3_5 %}
    <li><strong>L3.5 — Enrichissement</strong> : Dropcontact (email
      vérifié + téléphone direct)</li>
    {% endif %}
  </ul>

  <div class="footer">
    Rapport généré le {{ generated_at }} par RénoBoost Leads {{ version }}.
    Pour exporter en PDF, utilisez Ctrl+P puis « Enregistrer en PDF ».
  </div>

</div>
</body>
</html>
"""
)


def _lire_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _lire_stats(dossier: Path) -> dict[str, Any]:
    stats_path = dossier / "run_stats.json"
    if not stats_path.exists():
        return {}
    try:
        return json.loads(stats_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _detecter_stages(dossier: Path) -> list[str]:
    return [k for k, fname in STAGE_FILES.items() if (dossier / fname).exists()]


def _get_version() -> str:
    try:
        from ... import __version__
        return __version__
    except Exception:  # noqa: BLE001
        return "?"


def generate_report(
    session_id: str,
    max_leads: int = 50,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Génère un rapport HTML pour une session et le renvoie.

    Args:
        session_id: identifiant de session (ex. `20260518-091234-pilote59`).
        max_leads: nombre max de leads dans le tableau (défaut 50).
        output_path: chemin de sortie. Si `None`, écrit dans
            `data/output/<session_id>/rapport.html`.

    Returns:
        Dict avec `path` (str), `bytes_written` (int), `html_preview` (str
        — 500 premiers caractères), ou `error`.
    """
    dossier = OUTPUT_ROOT / session_id
    if not dossier.is_dir():
        return {"error": f"session inconnue : '{session_id}'"}

    fichier_l3 = dossier / STAGE_FILES["3"]
    if not fichier_l3.exists():
        return {
            "error": (
                "etage3_contacts.csv absent — lance au moins L1+L2+L3 "
                "avant de générer un rapport."
            )
        }

    rows_l3 = _lire_csv(fichier_l3)
    metriques = _metriques_l3(rows_l3)
    verdict = _verdict_pilote_phase1(metriques)
    stats = _lire_stats(dossier)
    stages = _detecter_stages(dossier)

    metriques_l3_5 = None
    fichier_l3_5 = dossier / STAGE_FILES["3.5"]
    if fichier_l3_5.exists():
        metriques_l3_5 = _metriques_l3_5(_lire_csv(fichier_l3_5))

    n = max(0, min(int(max_leads), len(rows_l3)))
    leads = rows_l3[:n]

    html = _TEMPLATE.render(
        session_id=session_id,
        campaign=stats.get("campaign") or "(non renseignée)",
        debut=stats.get("debut") or "?",
        fin=stats.get("fin") or "?",
        stages=stages or ["—"],
        metriques=metriques,
        verdict=verdict,
        leads=leads,
        colonnes=COLONNES_LEADS,
        effectifs=metriques.get("distribution_effectif"),
        metriques_l3_5=metriques_l3_5,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        version=_get_version(),
    )

    if output_path is None:
        cible = dossier / "rapport.html"
    else:
        cible = Path(output_path)
        if not cible.is_absolute():
            cible = PROJECT_ROOT / cible
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(html, encoding="utf-8")

    try:
        path_str = str(cible.relative_to(PROJECT_ROOT))
    except ValueError:
        path_str = str(cible)

    return {
        "session_id": session_id,
        "path": path_str,
        "bytes_written": len(html.encode("utf-8")),
        "leads_inclus": n,
        "verdict_go_phase2": verdict["go_phase2"],
    }


SCHEMAS = [
    {
        "name": "generate_report",
        "description": (
            "Génère un rapport HTML autonome (CSS inline) résumant une "
            "session de prospection : campagne, KPI qualité (SIREN, "
            "dirigeant, email), verdict pilote Phase 1, tableau des "
            "leads, sources. Livrable client. Écrit le fichier dans "
            "`data/output/<session_id>/rapport.html` par défaut."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Identifiant de la session à exporter.",
                },
                "max_leads": {
                    "type": "integer",
                    "description": (
                        "Nombre max de leads dans le tableau (défaut 50, "
                        "max 200)."
                    ),
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Chemin de sortie alternatif (relatif au projet ou "
                        "absolu). Si omis, écrit dans le dossier de la "
                        "session."
                    ),
                },
            },
            "required": ["session_id"],
        },
    }
]

DISPATCH = {"generate_report": generate_report}
