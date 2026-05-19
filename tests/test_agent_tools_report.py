"""Tests de l'outil generate_report (rapport HTML autonome)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import report as rep
from renoboost_leads.agent.tools import sessions as sess


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(rep, "OUTPUT_ROOT", root)
    return root


def _ecrire_csv(p: Path, rows: list[dict]) -> None:
    if not rows:
        p.write_text("nom\n", encoding="utf-8")
        return
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _session_l3(root: Path, sid: str, n: int = 5, complet: bool = True) -> Path:
    d = root / sid
    d.mkdir()
    rows = [
        {
            "nom": f"Entreprise {i}",
            "ville": "Lille",
            "siren": f"100{i:03d}" if complet else "",
            "dirigeant_nom": f"Martin{i}" if complet else "",
            "email_principal": f"contact{i}@ex.fr" if complet else "",
            "telephone": f"03 20 00 00 0{i}",
            "site_web": f"https://ex{i}.fr",
            "tranche_effectif": "11",
        }
        for i in range(n)
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text(
        json.dumps(
            {"campaign": "test-pilote", "debut": "2026-05-18", "fin": "2026-05-18"}
        ),
        encoding="utf-8",
    )
    return d


def test_session_inconnue(fake_root: Path) -> None:
    res = rep.generate_report("nope")
    assert "error" in res


def test_l3_absent(fake_root: Path) -> None:
    (fake_root / "s1").mkdir()
    res = rep.generate_report("s1")
    assert "error" in res
    assert "etage3" in res["error"]


def test_genere_html_complet(fake_root: Path) -> None:
    _session_l3(fake_root, "s1", n=10, complet=True)
    res = rep.generate_report("s1")
    assert "error" not in res
    assert res["leads_inclus"] == 10
    assert res["verdict_go_phase2"] is True
    assert res["bytes_written"] > 1000
    # Fichier écrit
    p = fake_root / "s1" / "rapport.html"
    assert p.exists()
    html = p.read_text(encoding="utf-8")
    # Sections clés présentes
    assert "<!DOCTYPE html>" in html
    assert "RénoBoost" in html
    assert "test-pilote" in html
    assert "Entreprise 0" in html
    assert "Martin0" in html
    assert "contact0@ex.fr" in html
    # GO car tous champs remplis → SIREN/dirigeant/email à 100%
    assert "GO Phase 2" in html


def test_verdict_nogo_si_donnees_vides(fake_root: Path) -> None:
    _session_l3(fake_root, "s2", n=10, complet=False)
    res = rep.generate_report("s2")
    assert res["verdict_go_phase2"] is False
    html = (fake_root / "s2" / "rapport.html").read_text(encoding="utf-8")
    assert "NO-GO Phase 2" in html


def test_max_leads_tronque(fake_root: Path) -> None:
    _session_l3(fake_root, "s3", n=20)
    res = rep.generate_report("s3", max_leads=5)
    assert res["leads_inclus"] == 5
    html = (fake_root / "s3" / "rapport.html").read_text(encoding="utf-8")
    assert "Entreprise 4" in html
    assert "Entreprise 5" not in html


def test_output_path_personnalise(fake_root: Path, tmp_path: Path) -> None:
    _session_l3(fake_root, "s4", n=3)
    cible = tmp_path / "ailleurs" / "monrapport.html"
    res = rep.generate_report("s4", output_path=str(cible))
    assert "error" not in res
    assert cible.exists()
    assert "RénoBoost" in cible.read_text(encoding="utf-8")


def test_inclut_l3_5_si_present(fake_root: Path) -> None:
    d = _session_l3(fake_root, "s5", n=5)
    rows35 = [
        {"nom": f"E{i}", "email_verifie": f"v{i}@x.fr", "tel_direct": "0600000000"}
        for i in range(5)
    ]
    _ecrire_csv(d / "etage3_5_enrichissement.csv", rows35)
    res = rep.generate_report("s5")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "Dropcontact" in html
    assert "L3.5" in html


def test_schema_et_dispatch_exposes() -> None:
    assert any(s["name"] == "generate_report" for s in rep.SCHEMAS)
    assert "generate_report" in rep.DISPATCH
    schema = rep.SCHEMAS[0]
    assert "session_id" in schema["input_schema"]["required"]


def test_outil_enregistre_dans_registry() -> None:
    """generate_report doit apparaître dans le registry global de l'agent."""
    from renoboost_leads.agent.tools import all_dispatch, all_schemas

    schemas = all_schemas()
    assert any(s["name"] == "generate_report" for s in schemas)
    assert "generate_report" in all_dispatch()


def test_fallback_ancien_nom_stats(fake_root: Path) -> None:
    """Compat ascendante : sessions historiques avec stats_run.json."""
    d = fake_root / "old"
    d.mkdir()
    _ecrire_csv(
        d / "etage3_contacts.csv",
        [{"nom": "X", "siren": "1", "dirigeant_nom": "Y", "email_principal": "a@b.fr"}],
    )
    # Ancien nom de fichier
    (d / "stats_run.json").write_text(
        json.dumps({"campaign": "ancien-run", "debut": "2026-04-01"}),
        encoding="utf-8",
    )
    res = rep.generate_report("old")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "ancien-run" in html


def test_inclut_config_snapshot_si_present(fake_root: Path) -> None:
    """Si config_snapshot.yaml présent, ses infos apparaissent dans le HTML."""
    d = _session_l3(fake_root, "s_cfg", n=5)
    (d / "config_snapshot.yaml").write_text(
        """
zone:
  type: departement
  codes: ["59", "62"]
  rayon_par_point_km: 10
secteurs:
  - type: establishment
    query: site industriel
  - type: establishment
    query: plateforme logistique
volume:
  cible: 10
budget:
  max_eur: 1.0
filtres:
  statut_requis: OPERATIONAL
  exiger_site_web: true
""",
        encoding="utf-8",
    )
    res = rep.generate_report("s_cfg")
    assert res["config_inclus"] is True
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "Paramètres de la recherche" in html
    assert "site industriel" in html
    assert "plateforme logistique" in html
    assert "site web requis" in html
    assert "departement" in html
    assert "59" in html


def test_config_path_explicite(fake_root: Path, tmp_path: Path) -> None:
    """Override config_path explicite (priorité sur snapshot)."""
    _session_l3(fake_root, "s_ovr", n=3)
    cfg = tmp_path / "mon_cfg.yaml"
    cfg.write_text(
        "secteurs:\n  - type: x\n    query: comptable\n", encoding="utf-8"
    )
    res = rep.generate_report("s_ovr", config_path=str(cfg))
    assert res["config_inclus"] is True
    html = (fake_root / "s_ovr" / "rapport.html").read_text(encoding="utf-8")
    assert "comptable" in html


def test_config_yaml_corrompu_n_explose_pas(fake_root: Path) -> None:
    d = _session_l3(fake_root, "s_bad", n=3)
    (d / "config_snapshot.yaml").write_text("[: invalide : :", encoding="utf-8")
    res = rep.generate_report("s_bad")
    assert "error" not in res
    assert res["config_inclus"] is False


def test_kpi_run_si_stats_completes(fake_root: Path) -> None:
    d = _session_l3(fake_root, "s_kpi", n=5)
    (d / "run_stats.json").write_text(
        json.dumps(
            {
                "campaign": "test",
                "debut": "2026-05-18T10:00:00",
                "fin": "2026-05-18T10:08:30",
                "duree_totale_secondes": 510,
                "cout_total_eur": 0.4321,
                "leads_finaux": 9,
            }
        ),
        encoding="utf-8",
    )
    res = rep.generate_report("s_kpi")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "0.43" in html  # cout
    assert "8.5 min" in html  # durée arrondie
    assert ">9<" in html  # leads_finaux


def test_chart_svg_inline(fake_root: Path) -> None:
    """Les SVG des distributions sont bien dans le HTML."""
    d = _session_l3(fake_root, "s_chart", n=10)
    res = rep.generate_report("s_chart")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    # Au moins un SVG (effectifs ou NAF)
    assert "<svg" in html
    # SVG inline, pas de référence externe
    assert "<script" not in html
    assert "src=" not in html


def test_bar_chart_vide_renvoie_chaine_vide() -> None:
    assert rep._bar_chart_svg({}) == ""


def test_bar_chart_tronque_labels_longs() -> None:
    svg = rep._bar_chart_svg({"a" * 50: 10})
    assert "…" in svg


def test_xss_autoescape_actif(fake_root: Path) -> None:
    """Les noms d'entreprises malveillants doivent être échappés."""
    d = fake_root / "s_xss"
    d.mkdir()
    rows = [
        {
            "nom": "<script>alert('xss')</script>",
            "ville": "Lille",
            "siren": "100000",
            "dirigeant_nom": "Mr \"OR 1=1\"",
            "email_principal": "<b>not</b>@x.fr",
            "telephone": "",
            "site_web": "",
            "tranche_effectif": "",
        }
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text(
        '{"campaign": "<img src=x onerror=alert(1)>", "debut": "2026-01-01"}',
        encoding="utf-8",
    )
    res = rep.generate_report("s_xss")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    # Les balises malicieuses doivent être échappées
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x onerror" not in html
    assert "&lt;img" in html
    # Les SVG bâtis par nous restent (chart_naf/chart_effectifs sont |safe)
    # — mais ici il n'y a qu'une seule entrée donc pas de chart significatif


def test_l3_absent_liste_fichiers_presents(fake_root: Path) -> None:
    """L'erreur L3 absent doit lister ce qui est présent pour debug."""
    d = fake_root / "s_debug"
    d.mkdir()
    (d / "etage1_decouverte.csv").write_text("nom\n", encoding="utf-8")
    (d / "run_stats.json").write_text("{}", encoding="utf-8")
    res = rep.generate_report("s_debug")
    assert "error" in res
    assert "fichiers_presents" in res
    assert "etage1_decouverte.csv" in res["fichiers_presents"]
    assert "run_stats.json" in res["fichiers_presents"]


def test_effectif_libelle_lisible_dans_rapport(fake_root: Path) -> None:
    """Le rapport affiche un libellé lisible, pas le code INSEE brut."""
    d = fake_root / "s_eff"
    d.mkdir()
    rows = [
        {
            "nom": f"E{i}",
            "siren": f"100{i}",
            "dirigeant_nom": "Martin",
            "email_principal": "x@y.fr",
            "telephone": "01 02 03 04 05",
            "tranche_effectif": "12",  # code INSEE seul (sans libellé)
        }
        for i in range(3)
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    res = rep.generate_report("s_eff")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    # Le code "12" est décodé en libellé humain
    assert "20 à 49 salariés" in html
    # Et le tableau ne montre plus le code seul comme cellule
    assert "<td>12</td>" not in html


def test_effectif_libelle_prioritaire_sur_code(fake_root: Path) -> None:
    """Si le CSV a déjà libelle_effectif (cas normal API), il prime."""
    d = fake_root / "s_eff2"
    d.mkdir()
    rows = [
        {
            "nom": "Test",
            "siren": "100",
            "dirigeant_nom": "M",
            "email_principal": "a@b.fr",
            "telephone": "",
            "tranche_effectif": "11",
            "libelle_effectif": "Une dizaine de personnes",
        }
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    rep.generate_report("s_eff2")
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "Une dizaine de personnes" in html


def test_naf_libelle_dans_distribution(fake_root: Path) -> None:
    """La distribution NAF utilise le libellé, pas le code seul.

    Note : `_bar_chart_svg` tronque les labels à 30 caractères pour
    rester lisible — on vérifie donc un préfixe représentatif.
    """
    d = fake_root / "s_naf"
    d.mkdir()
    rows = [
        {
            "nom": f"E{i}",
            "siren": f"1{i}",
            "dirigeant_nom": "M",
            "email_principal": "a@b.fr",
            "telephone": "",
            "code_naf": "47.91B",
            "libelle_naf": "Vente à distance",
        }
        for i in range(5)
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    rep.generate_report("s_naf")
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "47.91B — Vente à distance" in html


def test_nom_avec_lettres_espacees_recolle(fake_root: Path) -> None:
    """Google Places renvoie 'S H C I' → on affiche 'SHCI' dans le rapport."""
    d = fake_root / "s_nom"
    d.mkdir()
    rows = [
        {
            "nom": "S H C I LOGISTIQUE",
            "siren": "100",
            "dirigeant_nom": "Martin",
            "email_principal": "a@b.fr",
            "telephone": "",
        }
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    rep.generate_report("s_nom")
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "SHCI LOGISTIQUE" in html
    assert "S H C I LOGISTIQUE" not in html


def test_dirigeant_format_propre(fake_root: Path) -> None:
    """Dirigeant 'GAMBATESA MERCALDI' apparaît en 'Gambatesa MERCALDI'."""
    d = fake_root / "s_dir"
    d.mkdir()
    rows = [
        {
            "nom": "E",
            "siren": "1",
            "dirigeant_nom": "MERCALDI",
            "dirigeant_prenom": "GAMBATESA",
            "dirigeant_qualite": "Président",
            "email_principal": "a@b.fr",
            "telephone": "",
        }
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    rep.generate_report("s_dir")
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "Gambatesa MERCALDI (Président)" in html


def test_dirigeant_doublon_nom_prenom(fake_root: Path) -> None:
    """Si nom == prénom (cas 'JAZ (JAZ)'), on n'affiche pas le doublon."""
    d = fake_root / "s_jaz"
    d.mkdir()
    rows = [
        {
            "nom": "E",
            "siren": "1",
            "dirigeant_nom": "JAZ",
            "dirigeant_prenom": "JAZ",
            "email_principal": "a@b.fr",
            "telephone": "",
        }
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    rep.generate_report("s_jaz")
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert ">JAZ<" in html
    assert "JAZ JAZ" not in html


def test_telephone_cellule_nowrap(fake_root: Path) -> None:
    """La colonne Téléphone porte la classe nowrap pour éviter la coupure."""
    _session_l3(fake_root, "s_tel", n=2)
    rep.generate_report("s_tel")
    html = (fake_root / "s_tel" / "rapport.html").read_text(encoding="utf-8")
    # La règle CSS est définie
    assert "td.nowrap" in html
    # Au moins une cellule porte la classe (téléphone)
    assert 'class="nowrap"' in html


def test_lecture_csv_avec_bom(fake_root: Path) -> None:
    """utf-8-sig tolère un BOM (cas CSV Excel France)."""
    d = fake_root / "s_bom"
    d.mkdir()
    # Écrit un CSV avec BOM
    contenu = "﻿nom,siren,dirigeant_nom,email_principal\n"
    contenu += "Test SAS,123456,Martin,m@x.fr\n"
    (d / "etage3_contacts.csv").write_text(contenu, encoding="utf-8")
    (d / "run_stats.json").write_text(
        '{"campaign": "bom-test"}', encoding="utf-8"
    )
    res = rep.generate_report("s_bom")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "Test SAS" in html
    assert "Martin" in html
