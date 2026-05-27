"""Rapports HTML autoportants depuis les CSV du pipeline (source unique).

Deux rendus :
- `export_html_leads`  : tableau des leads qualifiés (vue CRM, depuis un CSV L3/L3.5/L4)
- `export_html_emails` : une fiche par lead avec email prêt à copier (depuis un CSV L4)

Utilisé par le pipeline (cli, quand `sortie.format` contient "html") et par les
scripts `scripts/generer_*.py` (wrappers CLI). Aucune dépendance externe.
"""

from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path


def _v(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


def _is_true(val: str) -> bool:
    return val in ("VRAI", "True", "true", "1")


def _fmt_eur(raw: str) -> str:
    try:
        return f"{int(raw):,}".replace(",", " ") + " €"
    except (ValueError, TypeError):
        return "—"


def _best_email(row: dict) -> tuple[str, str]:
    """(email, source) — privilégie Dropcontact vérifié, sinon scrap, sinon pattern."""
    if dc := _v(row, "email_dropcontact"):
        return dc, "dropcontact"
    if verifies := _v(row, "emails_verifies"):
        return verifies.split("|")[0], "scrap"
    if candidats := _v(row, "emails_candidats"):
        return candidats.split("|")[0], "pattern"
    return "", ""


# ════════════════════════════════════════════════════════════════
# Vue tableau "leads qualifiés"
# ════════════════════════════════════════════════════════════════


def export_html_leads(csv_path: Path, output_path: Path, sous_titre: str = "") -> Path:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    qual = [r for r in rows if not _is_true(_v(r, "hors_filtre_entreprise"))]

    nb_total = len(rows) or 1
    nb_qual = len(qual)
    nb_enrichi = sum(1 for r in qual if _is_true(_v(r, "enrichi_dropcontact")))
    nb_email_dc = sum(1 for r in qual if _v(r, "email_dropcontact"))
    nb_tel_dc = sum(1 for r in qual if _v(r, "telephone_direct_dropcontact"))
    cout = sum(float(_v(r, "cout_enrichissement_eur") or 0) for r in rows)

    def card(valeur: str, label: str) -> str:
        return (
            f'<div class="card"><div class="num">{html.escape(valeur)}</div>'
            f'<div class="lbl">{html.escape(label)}</div></div>'
        )

    cards = "".join(
        [
            card(str(len(rows)), "leads bruts (L1)"),
            card(f"{nb_qual}", f"qualifiés ({100 * nb_qual // nb_total}%)"),
            card(f"{nb_enrichi}", "traités Dropcontact"),
            card(f"{nb_email_dc}", "emails vérifiés"),
            card(f"{nb_tel_dc}", "tél. directs"),
            card(f"{cout:.2f} €", "coût enrichissement"),
        ]
    )

    qual_tri = sorted(qual, key=lambda r: (not _v(r, "email_dropcontact"), _v(r, "nom")))
    lignes = []
    for r in qual_tri:
        email, src = _best_email(r)
        badge = {
            "dropcontact": '<span class="b b-dc">vérifié</span>',
            "scrap": '<span class="b b-sc">scrapé</span>',
            "pattern": '<span class="b b-pt">pattern</span>',
        }.get(src, "")
        email_cell = (
            f'<a href="mailto:{html.escape(email)}">{html.escape(email)}</a> {badge}'
            if email
            else "—"
        )
        tel = _v(r, "telephone_direct_dropcontact") or _v(r, "telephone") or "—"
        li = _v(r, "linkedin_dirigeant_dropcontact")
        li_cell = f'<a href="{html.escape(li)}" target="_blank">profil</a>' if li else "—"
        dirig = " ".join(x for x in (_v(r, "dirigeant_prenom"), _v(r, "dirigeant_nom")) if x) or "—"
        site = _v(r, "site_web")
        nom_cell = (
            f'<a href="{html.escape(site)}" target="_blank">{html.escape(_v(r, "nom"))}</a>'
            if site
            else html.escape(_v(r, "nom"))
        )
        cls = ' class="hot"' if src == "dropcontact" else ""
        lignes.append(
            f"<tr{cls}>"
            f"<td>{nom_cell}</td>"
            f"<td>{html.escape(_v(r, 'ville'))}</td>"
            f"<td title='{html.escape(_v(r, 'libelle_naf'))}'>"
            f"{html.escape(_v(r, 'code_naf') or '—')}</td>"
            f"<td>{html.escape(_v(r, 'categorie_entreprise') or '—')}</td>"
            f"<td class='num-cell'>{_fmt_eur(_v(r, 'chiffre_affaires'))}</td>"
            f"<td>{html.escape(_v(r, 'libelle_effectif') or '—')}</td>"
            f"<td>{html.escape(dirig)}</td>"
            f"<td>{email_cell}</td>"
            f"<td>{html.escape(tel)}</td>"
            f"<td>{li_cell}</td>"
            "</tr>"
        )

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    sous = html.escape(sous_titre) if sous_titre else f"généré le {now}"
    doc = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RénoBoost — Leads qualifiés</title>
<style>
  :root {{ --vert:#1a7f4b; --bg:#f6f7f9; --bord:#e1e4e8; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    margin:0; background:var(--bg); color:#1b1f23; }}
  header {{ background:#0d2b1e; color:#fff; padding:28px 32px; }}
  header h1 {{ margin:0 0 4px; font-size:22px; }}
  header p {{ margin:0; opacity:.8; font-size:14px; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:24px 32px 60px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:14px; margin:24px 0 8px; }}
  .card {{ background:#fff; border:1px solid var(--bord); border-radius:10px; padding:16px 18px; }}
  .card .num {{ font-size:26px; font-weight:700; color:var(--vert); }}
  .card .lbl {{ font-size:13px; color:#57606a; margin-top:2px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff;
    border:1px solid var(--bord); border-radius:10px; overflow:hidden; font-size:13px; }}
  th,td {{ padding:9px 11px; text-align:left;
    border-bottom:1px solid var(--bord); vertical-align:top; }}
  th {{ background:#eef1f3; font-size:12px; text-transform:uppercase;
    letter-spacing:.3px; color:#57606a; position:sticky; top:0; }}
  tr.hot {{ background:#f0fbf4; }}
  tr:hover {{ background:#eef6ff; }}
  .num-cell {{ white-space:nowrap; text-align:right; }}
  a {{ color:#0969da; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  .b {{ font-size:10px; padding:1px 6px; border-radius:10px; font-weight:600; }}
  .b-dc {{ background:#1a7f4b; color:#fff; }}
  .b-sc {{ background:#0969da; color:#fff; }}
  .b-pt {{ background:#d0d7de; color:#24292f; }}
  .note {{ font-size:13px; color:#57606a; margin:18px 0 4px; }}
  footer {{ text-align:center; font-size:12px; color:#8b949e; padding:24px; }}
</style></head>
<body>
<header><h1>RénoBoost — Leads qualifiés</h1><p>{sous}</p></header>
<div class="wrap">
  <div class="cards">{cards}</div>
  <p class="note">Lignes <b style="color:var(--vert)">vertes</b> = email vérifié Dropcontact.
  CA = dernier exercice publié (vide si non publié).</p>
  <table>
    <thead><tr>
      <th>Entreprise</th><th>Ville</th><th>NAF</th><th>Cat.</th><th>CA</th>
      <th>Effectif</th><th>Dirigeant</th><th>Email</th><th>Téléphone</th><th>LinkedIn</th>
    </tr></thead>
    <tbody>{"".join(lignes)}</tbody>
  </table>
</div>
<footer>RénoBoost Leads · {nb_qual} qualifiés sur {len(rows)} prospects ·
data.gouv.fr + Dropcontact</footer>
</body></html>"""

    output_path.write_text(doc, encoding="utf-8")
    return output_path


# ════════════════════════════════════════════════════════════════
# Vue "emails de prospection" (une fiche par lead)
# ════════════════════════════════════════════════════════════════


def export_html_emails(csv_path: Path, output_path: Path, sous_titre: str = "") -> Path:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    qual = [
        r
        for r in rows
        if not _is_true(_v(r, "hors_filtre_entreprise")) and _v(r, "email_corps")
    ]
    qual.sort(key=lambda r: -(int(_v(r, "score_interet") or 0)))

    nb_scored = len(rows)
    nb_qual = len(qual)
    nb_top = sum(1 for r in qual if _is_true(_v(r, "top_lead")))

    def kpi(valeur: str, label: str) -> str:
        return (
            f'<div class="kpi"><div class="num">{html.escape(valeur)}</div>'
            f'<div class="lbl">{html.escape(label)}</div></div>'
        )

    kpis = "".join(
        [
            kpi(str(nb_scored), "leads scorés"),
            kpi(str(nb_qual), "qualifiés (email prêt)"),
            kpi(f"{nb_top}", "top leads (score ≥ 70)"),
        ]
    )

    fiches = []
    for r in qual:
        score = _v(r, "score_interet") or "—"
        try:
            score_i = int(score)
        except ValueError:
            score_i = 0
        score_cls = "s-hi" if score_i >= 70 else "s-mid" if score_i >= 50 else "s-lo"
        dirig = (
            " ".join(x for x in (_v(r, "dirigeant_prenom"), _v(r, "dirigeant_nom")) if x)
            or "dirigeant non identifié"
        )
        email_addr = _best_email(r)[0]
        meta = " · ".join(
            x
            for x in (
                _v(r, "ville"),
                _v(r, "libelle_naf") or _v(r, "code_naf"),
                (f"CA {_fmt_eur(_v(r, 'chiffre_affaires'))}" if _v(r, "chiffre_affaires") else ""),
                (f"effectif {_v(r, 'libelle_effectif')}" if _v(r, "libelle_effectif") else ""),
            )
            if x
        )
        email_line = (
            f'<a href="mailto:{html.escape(email_addr)}">{html.escape(email_addr)}</a>'
            if email_addr
            else '<span class="noaddr">adresse à enrichir</span>'
        )
        fiches.append(
            f'<article class="fiche"><div class="head">'
            f'<div class="titre"><h3>{html.escape(_v(r, "nom"))}</h3>'
            f'<span class="score {score_cls}">{html.escape(score)}</span></div>'
            f'<div class="meta">{html.escape(meta)}</div>'
            f'<div class="contact">À : {html.escape(dirig)} &nbsp;|&nbsp; {email_line}</div></div>'
            f'<div class="mail">'
            f'<div class="objet"><span class="tag">Objet</span> '
            f'{html.escape(_v(r, "email_objet"))}</div>'
            f'<pre class="corps">{html.escape(_v(r, "email_corps"))}</pre></div></article>'
        )

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    sous = html.escape(sous_titre) if sous_titre else (
        f"{nb_qual} leads qualifiés avec email personnalisé · généré le {now}"
    )
    doc = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RénoBoost — Emails de prospection</title>
<style>
  :root {{ --vert:#1a7f4b; --bg:#f6f7f9; --bord:#e1e4e8; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    margin:0; background:var(--bg); color:#1b1f23; }}
  header {{ background:#0d2b1e; color:#fff; padding:28px 32px; }}
  header h1 {{ margin:0 0 4px; font-size:22px; }}
  header p {{ margin:0; opacity:.8; font-size:14px; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:24px 28px 60px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:22px 0 8px; }}
  .kpi {{ background:#fff; border:1px solid var(--bord); border-radius:10px; padding:16px 18px; }}
  .kpi .num {{ font-size:26px; font-weight:700; color:var(--vert); }}
  .kpi .lbl {{ font-size:13px; color:#57606a; margin-top:2px; }}
  .note {{ font-size:13px; color:#57606a; margin:16px 0; }}
  .fiche {{ background:#fff; border:1px solid var(--bord); border-radius:12px;
    margin:16px 0; overflow:hidden; }}
  .head {{ padding:14px 18px; border-bottom:1px solid var(--bord); background:#fafbfc; }}
  .titre {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
  .titre h3 {{ margin:0; font-size:17px; }}
  .score {{ font-weight:700; font-size:14px; padding:2px 10px; border-radius:20px; color:#fff; }}
  .s-hi {{ background:var(--vert); }} .s-mid {{ background:#b8860b; }}
  .s-lo {{ background:#8b949e; }}
  .meta {{ font-size:13px; color:#57606a; margin-top:4px; }}
  .contact {{ font-size:13px; margin-top:6px; }}
  .noaddr {{ color:#b8860b; }}
  .mail {{ padding:16px 18px; }}
  .objet {{ font-size:14px; margin-bottom:10px; }}
  .tag {{ font-size:10px; text-transform:uppercase; letter-spacing:.4px; background:#eef1f3;
    color:#57606a; padding:2px 7px; border-radius:6px; font-weight:600; margin-right:6px; }}
  .corps {{ white-space:pre-wrap; font-family:inherit; font-size:14px; line-height:1.5;
    margin:0; background:#f8fafc; border:1px solid var(--bord); border-radius:8px; padding:14px; }}
  a {{ color:#0969da; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  footer {{ text-align:center; font-size:12px; color:#8b949e; padding:24px; }}
</style></head>
<body>
<header><h1>RénoBoost — Emails de prospection</h1><p>{sous}</p></header>
<div class="wrap">
  <div class="kpis">{kpis}</div>
  <p class="note">Triés par score. Email généré par Claude à partir du profil entreprise.
  <b>Relire et compléter la signature avant envoi.</b>
  « adresse à enrichir » = pas d'email vérifié.</p>
  {"".join(fiches)}
</div>
<footer>RénoBoost Leads · {nb_qual} emails sur {nb_scored} leads · data.gouv.fr + Claude</footer>
</body></html>"""

    output_path.write_text(doc, encoding="utf-8")
    return output_path
