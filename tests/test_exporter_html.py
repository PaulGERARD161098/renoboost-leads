"""Tests D4 — rendus HTML depuis un CSV (export_html_emails / export_html_leads)."""

from __future__ import annotations

import csv
from pathlib import Path

from renoboost_leads.exporter_html import export_html_emails, export_html_leads

_COLS = [
    "nom",
    "ville",
    "code_naf",
    "libelle_naf",
    "categorie_entreprise",
    "chiffre_affaires",
    "libelle_effectif",
    "dirigeant_prenom",
    "dirigeant_nom",
    "site_web",
    "telephone",
    "emails_candidats",
    "email_dropcontact",
    "telephone_direct_dropcontact",
    "linkedin_dirigeant_dropcontact",
    "enrichi_dropcontact",
    "cout_enrichissement_eur",
    "score_interet",
    "top_lead",
    "email_objet",
    "email_corps",
    "hors_filtre_entreprise",
]


def _ecrire_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def test_export_html_emails_ne_garde_que_qualifies_avec_email(tmp_path):
    rows = [
        {"nom": "Alpha", "score_interet": "82", "top_lead": "VRAI",
         "email_objet": "Sujet A", "email_corps": "Bonjour,\n\nCorps A\n\nCordialement",
         "hors_filtre_entreprise": "", "dirigeant_prenom": "Jean", "dirigeant_nom": "Dupont",
         "emails_candidats": "j.dupont@alpha.fr"},
        {"nom": "Beta", "score_interet": "50", "email_objet": "Sujet B",
         "email_corps": "Corps B", "hors_filtre_entreprise": "VRAI"},  # hors-filtre → exclu
        {"nom": "Gamma", "score_interet": "40", "email_objet": "",
         "email_corps": "", "hors_filtre_entreprise": ""},  # pas d'email → exclu
    ]
    csv_path = _ecrire_csv(tmp_path / "l4.csv", rows)
    out = export_html_emails(csv_path, tmp_path / "emails.html")
    doc = out.read_text(encoding="utf-8")
    assert out.exists()
    assert "Alpha" in doc and "Corps A" in doc and "Sujet A" in doc
    assert "Beta" not in doc  # hors-filtre exclu
    assert "Gamma" not in doc  # sans email_corps exclu
    assert "j.dupont@alpha.fr" in doc


def test_export_html_leads_tableau_qualifies(tmp_path):
    rows = [
        {"nom": "Alpha", "ville": "Lille", "code_naf": "25.62A", "chiffre_affaires": "5000000",
         "categorie_entreprise": "PME", "hors_filtre_entreprise": ""},
        {"nom": "Beta", "hors_filtre_entreprise": "VRAI"},  # exclu du tableau
    ]
    csv_path = _ecrire_csv(tmp_path / "l3.csv", rows)
    out = export_html_leads(csv_path, tmp_path / "leads.html")
    doc = out.read_text(encoding="utf-8")
    assert "Alpha" in doc and "Lille" in doc
    assert "5 000 000 €" in doc  # CA formaté
    assert "<table" in doc


def test_export_html_emails_csv_vide(tmp_path):
    csv_path = _ecrire_csv(tmp_path / "vide.csv", [])
    out = export_html_emails(csv_path, tmp_path / "e.html")
    assert out.exists()
    assert "0" in out.read_text(encoding="utf-8")
