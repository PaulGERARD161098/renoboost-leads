"""Outil `generate_report` — rapport HTML autonome d'une session.

Produit un fichier HTML unique (CSS inline, aucune ressource externe)
résumant une session de prospection : campagne, snapshot config,
KPI qualité, tableau des leads, verdict diagnostic pilote, distributions,
sources, métriques de run (coût/durée/étages).

Le client (ou Paul) peut l'ouvrir dans un navigateur et faire
**Ctrl+P → Enregistrer en PDF** pour un livrable papier.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, select_autoescape

from ...settings import PROJECT_ROOT
from ._formatters import (
    decode_effectif,
    format_dirigeant,
    nettoyer_nom_espaces,
)
from .quality import _metriques_l3, _metriques_l3_5, _verdict_pilote_phase1
from .sessions import OUTPUT_ROOT, STAGE_FILES

# Jinja2 avec autoescape HTML actif : tout `{{ var }}` est échappé par
# défaut (protection XSS sur les noms d'entreprises, dirigeants etc.
# venant de Google Places / scraping). Les SVG construits par nous
# (chart_*) sont marqués `|safe` explicitement dans le template.
_ENV = Environment(autoescape=select_autoescape(["html"]))

# Les clés référencent les champs **enrichis** (cf. `_preparer_leads`) :
# `nom_affiche`, `dirigeant_affiche`, `effectif_affiche` sont produits
# à l'affichage et n'existent pas dans le CSV stocké.
COLONNES_LEADS = [
    ("nom_affiche", "Raison sociale", False),
    ("ville", "Ville", False),
    ("siren", "SIREN", True),
    ("dirigeant_affiche", "Dirigeant", False),
    ("email_principal", "Email", True),
    ("telephone", "Téléphone", True),
    ("site_web", "Site", True),
    ("effectif_affiche", "Effectif", False),
]


def _preparer_leads(rows: list[dict]) -> list[dict]:
    """Enrichit chaque ligne avec les champs d'affichage formatés.

    On ne touche pas au CSV : on calcule à la volée `nom_affiche`,
    `dirigeant_affiche`, `effectif_affiche` à partir des champs bruts.
    """
    enrichis = []
    for r in rows:
        e = dict(r)
        e["nom_affiche"] = nettoyer_nom_espaces(r.get("nom"))
        e["dirigeant_affiche"] = format_dirigeant(
            r.get("dirigeant_nom"),
            r.get("dirigeant_prenom"),
            r.get("dirigeant_qualite"),
        )
        e["effectif_affiche"] = decode_effectif(
            r.get("tranche_effectif"),
            r.get("libelle_effectif"),
        )
        enrichis.append(e)
    return enrichis


def _bar_chart_svg(
    data: dict[str, int], width: int = 600, bar_height: int = 24
) -> str:
    """Génère un bar chart SVG horizontal inline (zéro JS, zéro asset).

    `data` = {label: count}. Affiche les barres triées par count desc.
    """
    if not data:
        return ""
    items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)
    max_val = max(v for _, v in items) or 1
    label_w = 180
    bar_max_w = width - label_w - 50
    gap = 6
    h = (bar_height + gap) * len(items) + 10
    rows = []
    for i, (lbl, val) in enumerate(items):
        y = i * (bar_height + gap) + 5
        bw = int(bar_max_w * val / max_val)
        rows.append(
            f'<text x="0" y="{y + bar_height * 0.7:.0f}" '
            f'font-size="13" fill="#333">{_clip(lbl, 30)}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bw}" '
            f'height="{bar_height}" fill="#0f4c81" rx="2"/>'
            f'<text x="{label_w + bw + 6}" y="{y + bar_height * 0.7:.0f}" '
            f'font-size="13" fill="#555">{val}</text>'
        )
    return (
        f'<svg width="{width}" height="{h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="max-width:100%;height:auto;">{"".join(rows)}</svg>'
    )


def _clip(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


_TEMPLATE = _ENV.from_string(
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
  h3 { margin-top: 20px; margin-bottom: 6px; font-size: 14px;
    color: #555; text-transform: uppercase; letter-spacing: 0.5px; }
  .meta { color: #666; font-size: 14px; margin-bottom: 24px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 16px; margin: 16px 0 24px 0; }
  .kpi { background: #f0f7ff; padding: 16px; border-radius: 6px;
    border-left: 3px solid #0f4c81; }
  .kpi .label { font-size: 12px; color: #555; text-transform: uppercase;
    letter-spacing: 0.5px; }
  .kpi .value { font-size: 26px; font-weight: 600; color: #0f4c81;
    margin-top: 4px; }
  .kpi-grid-3 { display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 16px; margin: 16px 0; }
  table { width: 100%; border-collapse: collapse; font-size: 13px;
    margin: 8px 0; }
  th { background: #0f4c81; color: white; text-align: left; padding: 8px;
    font-weight: 500; }
  td { padding: 8px; border-bottom: 1px solid #eee; }
  td.nowrap { white-space: nowrap; }
  tr:nth-child(even) td { background: #fafafa; }
  .verdict { padding: 16px; border-radius: 6px; margin: 16px 0;
    font-weight: 500; }
  .verdict.go { background: #e6f6e6; border-left: 4px solid #2c8a2c;
    color: #1a5a1a; }
  .verdict.nogo { background: #fde6e6; border-left: 4px solid #c82c2c;
    color: #6a1a1a; }
  .verdict.indetermine { background: #fff6e0; border-left: 4px solid #d18b1a;
    color: #6a4a10; }
  .criteres { list-style: none; padding: 0; margin: 12px 0; }
  .criteres li { padding: 6px 0; border-bottom: 1px solid #eee;
    font-size: 14px; }
  .criteres .ok { color: #2c8a2c; font-weight: 600; }
  .criteres .ko { color: #c82c2c; font-weight: 600; }
  .config-card { background: #fafafa; border-left: 3px solid #0f4c81;
    padding: 12px 16px; margin: 8px 0; border-radius: 4px; }
  .config-card dl { margin: 0; display: grid;
    grid-template-columns: 160px 1fr; gap: 4px 12px; font-size: 13px; }
  .config-card dt { color: #555; font-weight: 500; }
  .config-card dd { margin: 0; color: #1a1a1a; }
  .badges { display: flex; gap: 6px; flex-wrap: wrap; }
  .badge { display: inline-block; padding: 2px 8px; background: #0f4c81;
    color: white; border-radius: 10px; font-size: 12px; }
  .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #ddd;
    font-size: 12px; color: #999; text-align: center; }
  .empty { color: #999; font-style: italic; padding: 12px;
    background: #fafafa; border-radius: 4px; }
  .chart-wrap { margin: 12px 0; padding: 12px;
    background: #fafafa; border-radius: 4px; }
  @media print {
    body { background: white; padding: 0; }
    .container { box-shadow: none; padding: 16px; }
    h2 { page-break-after: avoid; }
    table { page-break-inside: auto; }
    tr { page-break-inside: avoid; }
  }
</style>
</head>
<body>
<div class="container">

  <h1>Rapport de prospection</h1>
  <div class="meta">
    <strong>Campagne :</strong> {{ campaign }}<br>
    <strong>Session :</strong> {{ session_id }}<br>
    <strong>Période :</strong> {{ debut }} → {{ fin }}
    {% if duree_min is not none %} ({{ duree_min }} min){% endif %}<br>
    <strong>Étages traités :</strong>
    <span class="badges">
      {% for s in stages %}<span class="badge">L{{ s }}</span>{% endfor %}
    </span>
  </div>

  {% if config_snapshot %}
  <h2>Paramètres de la recherche</h2>
  <div class="config-card">
    <dl>
      {% if config_snapshot.zone %}
      <dt>Zone géographique</dt>
      <dd>{{ config_snapshot.zone }}</dd>
      {% endif %}
      {% if config_snapshot.secteurs %}
      <dt>Secteurs ciblés</dt>
      <dd>
        <span class="badges">
          {% for s in config_snapshot.secteurs %}
          <span class="badge">{{ s }}</span>
          {% endfor %}
        </span>
      </dd>
      {% endif %}
      {% if config_snapshot.volume_cible %}
      <dt>Volume cible</dt>
      <dd>{{ config_snapshot.volume_cible }} leads</dd>
      {% endif %}
      {% if config_snapshot.filtres %}
      <dt>Filtres appliqués</dt>
      <dd>{{ config_snapshot.filtres }}</dd>
      {% endif %}
      {% if config_snapshot.budget_max %}
      <dt>Plafond budget</dt>
      <dd>{{ config_snapshot.budget_max }} €</dd>
      {% endif %}
    </dl>
  </div>
  {% endif %}

  <h2>Indicateurs qualité</h2>
  <div class="kpi-grid">
    <div class="kpi">
      <div class="label">Leads identifiés</div>
      <div class="value">{{ metriques.row_count }}</div>
    </div>
    <div class="kpi">
      <div class="label">SIREN matchés</div>
      <div class="value">{% if metriques.pct_siren_matche is not none %}{{ metriques.pct_siren_matche }}%{% else %}N/A{% endif %}</div>
    </div>
    <div class="kpi">
      <div class="label">Dirigeant identifié</div>
      <div class="value">{% if metriques.pct_dirigeant_identifie is not none %}{{ metriques.pct_dirigeant_identifie }}%{% else %}N/A{% endif %}</div>
    </div>
    <div class="kpi">
      <div class="label">Email scrapé</div>
      <div class="value">{% if metriques.pct_email_scrape is not none %}{{ metriques.pct_email_scrape }}%{% else %}N/A{% endif %}</div>
    </div>
  </div>

  {% if run_stats_extra %}
  <h3>Exécution du pipeline</h3>
  <div class="kpi-grid-3">
    {% if run_stats_extra.cout_total_eur is not none %}
    <div class="kpi">
      <div class="label">Coût total</div>
      <div class="value">{{ "%.2f"|format(run_stats_extra.cout_total_eur) }} €</div>
    </div>
    {% endif %}
    {% if run_stats_extra.duree_min is not none %}
    <div class="kpi">
      <div class="label">Durée</div>
      <div class="value">{{ run_stats_extra.duree_min }} min</div>
    </div>
    {% endif %}
    {% if run_stats_extra.leads_finaux is not none %}
    <div class="kpi">
      <div class="label">Leads finaux</div>
      <div class="value">{{ run_stats_extra.leads_finaux }}</div>
    </div>
    {% endif %}
  </div>
  {% endif %}

  <h2>Verdict pilote Phase 1</h2>
  {% if verdict.indetermine %}
    <div class="verdict indetermine">⚠ INDÉTERMINÉ — {{ verdict.raison_indetermine }}
      Les critères pilote ne peuvent pas être évalués sans données.</div>
  {% elif verdict.go_phase2 %}
    <div class="verdict go">✓ GO Phase 2 — tous les critères pilote sont
      atteints.</div>
  {% else %}
    <div class="verdict nogo">✗ NO-GO Phase 2 — au moins un critère pilote
      n'est pas atteint.</div>
  {% endif %}
  {% if verdict.criteres %}
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
  {% endif %}

  <h2>Top {{ leads|length }} leads</h2>
  {% if leads %}
  <table>
    <thead>
      <tr>
        {% for _, label, _ in colonnes %}<th>{{ label }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for lead in leads %}
      <tr>
        {% for key, _, nowrap in colonnes %}
        <td{% if nowrap %} class="nowrap"{% endif %}>{{ lead.get(key, '') }}</td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="empty">Aucun lead disponible pour cette session.</div>
  {% endif %}

  {% if chart_naf %}
  <h2>Distribution sectorielle (NAF top 5)</h2>
  <div class="chart-wrap">{{ chart_naf|safe }}</div>
  {% endif %}

  {% if chart_effectifs %}
  <h2>Distribution des effectifs</h2>
  <div class="chart-wrap">{{ chart_effectifs|safe }}</div>
  {% endif %}

  {% if metriques_l3_5 %}
  <h2>Enrichissement Dropcontact (L3.5)</h2>
  <div class="kpi-grid-3">
    <div class="kpi">
      <div class="label">Lignes L3.5</div>
      <div class="value">{{ metriques_l3_5.row_count_3_5 }}</div>
    </div>
    <div class="kpi">
      <div class="label">Email vérifié</div>
      <div class="value">
        {% if metriques_l3_5.pct_email_verifie_dropcontact is not none %}{{ metriques_l3_5.pct_email_verifie_dropcontact }}%{% else %}N/A{% endif %}
      </div>
    </div>
    <div class="kpi">
      <div class="label">Tél. direct</div>
      <div class="value">{% if metriques_l3_5.pct_tel_direct is not none %}{{ metriques_l3_5.pct_tel_direct }}%{% else %}N/A{% endif %}</div>
    </div>
  </div>
  {% endif %}

  <h2>Sources & méthodologie</h2>
  <ul>
    <li><strong>L1 — Découverte</strong> : Google Places API (recherche
      par secteur et zone géographique)</li>
    <li><strong>L2 — Entreprises</strong> : data.gouv.fr — base Sirene
      (SIREN, NAF, effectif, dirigeant)</li>
    <li><strong>L3 — Contacts</strong> : scraping site web officiel +
      détection patterns email (mentions légales, contact)</li>
    {% if metriques_l3_5 %}
    <li><strong>L3.5 — Enrichissement</strong> : Dropcontact (email
      vérifié + téléphone direct du dirigeant)</li>
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
    # utf-8-sig pour tolérer un BOM en tête (cas des CSV exportés par
    # Excel France ou ré-importés via un autre outil).
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _lire_stats(dossier: Path) -> dict[str, Any]:
    """Lit run_stats.json (avec fallback sur l'ancien nom stats_run.json)."""
    for name in ("run_stats.json", "stats_run.json"):
        p = dossier / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
    return {}


def _detecter_stages(dossier: Path) -> list[str]:
    return [
        k for k, fname in STAGE_FILES.items()
        if (dossier / fname).exists() and not k.endswith("hors_filtre")
    ]


def _get_version() -> str:
    try:
        from ... import __version__
        return __version__
    except Exception:  # noqa: BLE001
        return "?"


def _load_config_snapshot(dossier: Path, override: str | None = None) -> dict | None:
    """Cherche le config YAML utilisé pour la session.

    Ordre :
    1. `override` (chemin explicite fourni par l'agent)
    2. `<session>/config_snapshot.yaml` (copié automatiquement par cli run)
    """
    candidat: Path | None = None
    if override:
        p = Path(override)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            candidat = p
    if candidat is None:
        snap = dossier / "config_snapshot.yaml"
        if snap.exists():
            candidat = snap
    if candidat is None:
        return None
    try:
        raw = yaml.safe_load(candidat.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    return _resumer_config(raw)


def _resumer_config(raw: dict) -> dict:
    """Extrait les champs lisibles d'un config CampaignConfig pour l'affichage."""
    out: dict = {}
    zone = raw.get("zone") or {}
    if zone:
        codes = zone.get("codes") or []
        type_zone = zone.get("type", "")
        rayon = zone.get("rayon_par_point_km")
        bits = []
        if type_zone:
            bits.append(type_zone)
        if codes:
            bits.append(", ".join(str(c) for c in codes))
        if rayon:
            bits.append(f"rayon {rayon} km")
        out["zone"] = " — ".join(bits) if bits else None
    secteurs = raw.get("secteurs") or []
    if secteurs:
        out["secteurs"] = [s.get("query", "?") for s in secteurs]
    volume = raw.get("volume") or {}
    if volume.get("cible"):
        out["volume_cible"] = volume["cible"]
    budget = raw.get("budget") or {}
    if budget.get("max_eur") is not None:
        out["budget_max"] = budget["max_eur"]
    filtres = raw.get("filtres") or {}
    if filtres:
        bits = []
        if filtres.get("exiger_site_web"):
            bits.append("site web requis")
        if filtres.get("exiger_telephone"):
            bits.append("téléphone requis")
        if filtres.get("statut_requis"):
            bits.append(f"statut {filtres['statut_requis']}")
        if filtres.get("note_min"):
            bits.append(f"note ≥ {filtres['note_min']}")
        if filtres.get("dedup_chaines"):
            bits.append("dédup chaînes")
        out["filtres"] = ", ".join(bits) if bits else None
    return out


def _extract_run_stats(stats: dict) -> dict:
    """Garde uniquement les champs utiles à l'affichage."""
    if not stats:
        return {}
    duree_s = stats.get("duree_totale_secondes")
    duree_min = round(duree_s / 60, 1) if duree_s is not None else None
    return {
        "cout_total_eur": stats.get("cout_total_eur"),
        "duree_min": duree_min,
        "leads_finaux": stats.get("leads_finaux"),
    }


def generate_report(
    session_id: str,
    max_leads: int = 50,
    output_path: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Génère un rapport HTML pour une session et le renvoie.

    Args:
        session_id: identifiant de session.
        max_leads: nombre max de leads dans le tableau (défaut 50).
        output_path: chemin de sortie. Si `None`, écrit dans
            `data/output/<session_id>/rapport.html`.
        config_path: chemin du config YAML utilisé (optionnel). Si omis,
            cherche `<session>/config_snapshot.yaml`.

    Returns:
        Dict avec `path`, `bytes_written`, `leads_inclus`,
        `verdict_go_phase2`, `config_inclus`, ou `error`.
    """
    dossier = OUTPUT_ROOT / session_id
    if not dossier.is_dir():
        return {"error": f"session inconnue : '{session_id}'"}

    fichier_l3 = dossier / STAGE_FILES["3"]
    if not fichier_l3.exists():
        presents = sorted(
            p.name for p in dossier.iterdir() if p.is_file()
        )
        return {
            "error": (
                "etage3_contacts.csv absent — lance au moins L1+L2+L3 "
                "avant de générer un rapport."
            ),
            "fichiers_presents": presents,
        }

    rows_l3 = _lire_csv(fichier_l3)
    metriques = _metriques_l3(rows_l3)
    verdict = _verdict_pilote_phase1(metriques)
    stats = _lire_stats(dossier)
    stages = _detecter_stages(dossier)
    config_snapshot = _load_config_snapshot(dossier, config_path)
    run_stats_extra = _extract_run_stats(stats)

    metriques_l3_5 = None
    fichier_l3_5 = dossier / STAGE_FILES["3.5"]
    if fichier_l3_5.exists():
        metriques_l3_5 = _metriques_l3_5(_lire_csv(fichier_l3_5))

    n = max(0, min(int(max_leads), len(rows_l3)))
    leads = _preparer_leads(rows_l3[:n])

    chart_naf = _bar_chart_svg(metriques.get("distribution_naf_top5") or {})
    chart_effectifs = _bar_chart_svg(metriques.get("distribution_effectif") or {})

    duree_min = run_stats_extra.get("duree_min")

    html = _TEMPLATE.render(
        session_id=session_id,
        campaign=stats.get("campaign") or "(non renseignée)",
        debut=stats.get("debut") or "?",
        fin=stats.get("fin") or "?",
        duree_min=duree_min,
        stages=stages or ["—"],
        metriques=metriques,
        verdict=verdict,
        leads=leads,
        colonnes=COLONNES_LEADS,
        metriques_l3_5=metriques_l3_5,
        config_snapshot=config_snapshot,
        run_stats_extra=run_stats_extra,
        chart_naf=chart_naf,
        chart_effectifs=chart_effectifs,
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
        "config_inclus": config_snapshot is not None,
    }


SCHEMAS = [
    {
        "name": "generate_report",
        "description": (
            "Génère un rapport HTML autonome (CSS inline, graphiques SVG "
            "inline) résumant une session de prospection : snapshot config, "
            "KPI qualité (SIREN, dirigeant, email), verdict pilote Phase 1, "
            "tableau des leads, distributions sectorielle et effectifs, "
            "métriques de run (coût, durée), sources. Livrable client. "
            "Écrit dans `data/output/<session_id>/rapport.html` par défaut. "
            "Si la session a été lancée via `cli run`, le config est inclus "
            "automatiquement (via le snapshot copié). Sinon, passe "
            "`config_path` explicitement."
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
                "config_path": {
                    "type": "string",
                    "description": (
                        "Chemin du config YAML utilisé pour cette session. "
                        "Si omis, cherche `config_snapshot.yaml` dans le "
                        "dossier de la session."
                    ),
                },
            },
            "required": ["session_id"],
        },
    }
]

DISPATCH = {"generate_report": generate_report}
