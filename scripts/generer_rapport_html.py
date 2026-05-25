"""Génère un rapport HTML autoportant à partir d'un CSV étage 3.5.

Usage : python scripts/generer_rapport_html.py <csv_l35> <sortie.html>
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


def _best_email(row: dict) -> tuple[str, str]:
    """(email, source) — privilégie Dropcontact vérifié, sinon pattern."""
    dc = _v(row, "email_dropcontact")
    if dc:
        return dc, "dropcontact"
    verifies = _v(row, "emails_verifies")
    if verifies:
        return verifies.split("|")[0], "scrap"
    candidats = _v(row, "emails_candidats")
    if candidats:
        return candidats.split("|")[0], "pattern"
    return "", ""


def generer(csv_path: Path, sortie: Path) -> Path:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    qual = [r for r in rows if not _is_true(_v(r, "hors_filtre_entreprise"))]

    nb_total = len(rows)
    nb_qual = len(qual)
    nb_enrichi = sum(1 for r in qual if _is_true(_v(r, "enrichi_dropcontact")))
    nb_email_dc = sum(1 for r in qual if _v(r, "email_dropcontact"))
    nb_tel_dc = sum(1 for r in qual if _v(r, "telephone_direct_dropcontact"))
    nb_li = sum(1 for r in qual if _v(r, "linkedin_dirigeant_dropcontact"))
    cout = sum(float(_v(r, "cout_enrichissement_eur") or 0) for r in rows)

    def card(valeur: str, label: str) -> str:
        return (
            f'<div class="card"><div class="num">{html.escape(valeur)}</div>'
            f'<div class="lbl">{html.escape(label)}</div></div>'
        )

    cards = "".join(
        [
            card(str(nb_total), "leads bruts (L1)"),
            card(f"{nb_qual}", f"qualifiés ({100*nb_qual//nb_total}%)"),
            card(f"{nb_enrichi}", "traités Dropcontact"),
            card(f"{nb_email_dc}", "emails vérifiés"),
            card(f"{nb_tel_dc}", "tél. directs"),
            card(f"{cout:.2f} €", "coût enrichissement"),
        ]
    )

    # Lignes du tableau — qualifiés triés : enrichis d'abord
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
        dirig = " ".join(
            x for x in (_v(r, "dirigeant_prenom"), _v(r, "dirigeant_nom")) if x
        ) or "—"
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
            f"<td title='{html.escape(_v(r, 'libelle_naf'))}'>{html.escape(_v(r, 'code_naf') or '—')}</td>"
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
    doc = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RénoBoost — Leads qualifiés 59+62</title>
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
  .card {{ background:#fff; border:1px solid var(--bord); border-radius:10px;
    padding:16px 18px; }}
  .card .num {{ font-size:26px; font-weight:700; color:var(--vert); }}
  .card .lbl {{ font-size:13px; color:#57606a; margin-top:2px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff;
    border:1px solid var(--bord); border-radius:10px; overflow:hidden; font-size:13px; }}
  th,td {{ padding:9px 11px; text-align:left; border-bottom:1px solid var(--bord);
    vertical-align:top; }}
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
<header>
  <h1>RénoBoost — Leads qualifiés Nord + Pas-de-Calais (59/62)</h1>
  <p>Zone-test calibration · industrie / logistique / sièges sociaux · PME-ETI · généré le {now}</p>
</header>
<div class="wrap">
  <div class="cards">{cards}</div>
  <p class="note">Filtres : NAF industriel/logistique strict · catégorie PME/ETI · effectif ≥ 20.
  Lignes <b style="color:var(--vert)">vertes</b> = email vérifié Dropcontact. CA = dernier exercice publié (vide si non publié).</p>
  <table>
    <thead><tr>
      <th>Entreprise</th><th>Ville</th><th>NAF</th><th>Cat.</th><th>CA</th>
      <th>Effectif</th><th>Dirigeant</th><th>Email</th><th>Téléphone</th><th>LinkedIn</th>
    </tr></thead>
    <tbody>
      {"".join(lignes)}
    </tbody>
  </table>
</div>
<footer>RénoBoost Leads · {nb_qual} leads qualifiés sur {nb_total} prospects analysés · pipeline data.gouv.fr + Dropcontact</footer>
</body></html>"""

    sortie.write_text(doc, encoding="utf-8")
    return sortie


if __name__ == "__main__":
    csv_in = Path(sys.argv[1])
    out = Path(sys.argv[2])
    p = generer(csv_in, out)
    print(f"Rapport HTML écrit : {p} ({p.stat().st_size // 1024} Ko)")
