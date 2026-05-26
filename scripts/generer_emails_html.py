"""Génère un rapport HTML « emails de prospection » depuis un CSV étage 4.

Une fiche par lead qualifié : profil entreprise + score + email prêt à copier
(objet + corps). Aucune dépendance externe.

Usage : python scripts/generer_emails_html.py <csv_l4> <sortie.html>
"""

from __future__ import annotations

import csv
import html
import sys
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


def _best_email(row: dict) -> str:
    for k in ("email_dropcontact", "emails_verifies", "emails_candidats"):
        v = _v(row, k)
        if v:
            return v.split("|")[0]
    return ""


def generer(csv_path: Path, sortie: Path) -> Path:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    qual = [r for r in rows if not _is_true(_v(r, "hors_filtre_entreprise"))]
    qual = [r for r in qual if _v(r, "email_corps")]
    qual.sort(key=lambda r: -(int(_v(r, "score_interet") or 0)))

    nb_scored = len(rows)
    nb_qual = len(qual)
    nb_top = sum(1 for r in qual if _is_true(_v(r, "top_lead")))

    def card_stat(valeur: str, label: str) -> str:
        return (
            f'<div class="kpi"><div class="num">{html.escape(valeur)}</div>'
            f'<div class="lbl">{html.escape(label)}</div></div>'
        )

    kpis = "".join(
        [
            card_stat(str(nb_scored), "leads scorés"),
            card_stat(str(nb_qual), "qualifiés (email prêt)"),
            card_stat(f"{nb_top}", "top leads (score ≥ 70)"),
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
        dirig = " ".join(
            x for x in (_v(r, "dirigeant_prenom"), _v(r, "dirigeant_nom")) if x
        ) or "dirigeant non identifié"
        email_addr = _best_email(r)
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
        objet = _v(r, "email_objet")
        corps = _v(r, "email_corps")
        email_line = (
            f'<a href="mailto:{html.escape(email_addr)}">{html.escape(email_addr)}</a>'
            if email_addr
            else '<span class="noaddr">adresse à enrichir</span>'
        )
        fiches.append(
            f'<article class="fiche">'
            f'<div class="head">'
            f'<div class="titre"><h3>{html.escape(_v(r, "nom"))}</h3>'
            f'<span class="score {score_cls}">{html.escape(score)}</span></div>'
            f'<div class="meta">{html.escape(meta)}</div>'
            f'<div class="contact">À : {html.escape(dirig)} &nbsp;|&nbsp; {email_line}</div>'
            f'</div>'
            f'<div class="mail">'
            f'<div class="objet"><span class="tag">Objet</span> {html.escape(objet)}</div>'
            f'<pre class="corps">{html.escape(corps)}</pre>'
            f'</div>'
            f'</article>'
        )

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    doc = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RénoBoost — Emails de prospection 59+62</title>
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
  .s-hi {{ background:var(--vert); }} .s-mid {{ background:#b8860b; }} .s-lo {{ background:#8b949e; }}
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
<header>
  <h1>RénoBoost — Emails de prospection Nord + Pas-de-Calais (59/62)</h1>
  <p>{nb_qual} leads qualifiés avec email personnalisé · généré le {now}</p>
</header>
<div class="wrap">
  <div class="kpis">{kpis}</div>
  <p class="note">Triés par score d'intérêt. Chaque email est généré par Claude à partir du profil
  entreprise (activité, taille, CA, dirigeant). <b>Relire et compléter la signature avant envoi.</b>
  Adresse « à enrichir » = pas d'email vérifié (recharger Dropcontact pour les obtenir).</p>
  {"".join(fiches)}
</div>
<footer>RénoBoost Leads · {nb_qual} emails sur {nb_scored} leads analysés · pipeline data.gouv.fr + Claude</footer>
</body></html>"""

    sortie.write_text(doc, encoding="utf-8")
    return sortie


if __name__ == "__main__":
    p = generer(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Rapport emails HTML écrit : {p} ({p.stat().st_size // 1024} Ko)")
