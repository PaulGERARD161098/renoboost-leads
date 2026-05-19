"""Tests des outils workflow : clone_config + compare_sessions."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from renoboost_leads.agent.tools import sessions as sess
from renoboost_leads.agent.tools import workflow as wf


@pytest.fixture
def fake_config_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sandbox config/ + data/agent/configs/ pour les tests."""
    cfg_root = tmp_path / "config"
    cfg_root.mkdir()
    gen_root = tmp_path / "data" / "agent" / "configs"
    monkeypatch.setattr("renoboost_leads.agent.tools.config.CONFIG_ROOT", cfg_root)
    monkeypatch.setattr(wf, "GENERATED_ROOT", gen_root)
    return cfg_root


@pytest.fixture
def fake_output_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(wf, "OUTPUT_ROOT", root)
    return root


def _ecrire_csv(p: Path, rows: list[dict]) -> None:
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ────────────────────────────────────────────────────────────────────
# clone_config
# ────────────────────────────────────────────────────────────────────

ROSSINI_YAML = """
run:
  client_name: rossini-test-nord
  description: Proto 10 leads
stages:
  enable_stage_1_decouverte: true
secteurs:
  - type: establishment
    query: site industriel
zone:
  type: departement
  codes: ["59"]
  rayon_par_point_km: 10
volume:
  cible: 10
budget:
  max_eur: 1.0
"""


def test_clone_sans_overrides_copie_a_l_identique(fake_config_root: Path) -> None:
    (fake_config_root / "rossini.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config("rossini.yaml", "rossini_copie")
    assert "error" not in res
    parsed = yaml.safe_load(Path(res["path"]).read_text(encoding="utf-8"))
    assert parsed["run"]["client_name"] == "rossini-test-nord"
    assert parsed["zone"]["codes"] == ["59"]
    assert res["changes"] == []


def test_clone_avec_override_zone(fake_config_root: Path) -> None:
    (fake_config_root / "rossini.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "rossini.yaml",
        "rossini_62",
        overrides={
            "client_name": "rossini-pas-de-calais",
            "zone_codes": ["62"],
        },
    )
    assert "error" not in res
    assert res["client_name"] == "rossini-pas-de-calais"
    assert any("zone.codes" in c for c in res["changes"])
    parsed = yaml.safe_load(Path(res["path"]).read_text(encoding="utf-8"))
    assert parsed["zone"]["codes"] == ["62"]
    assert parsed["run"]["client_name"] == "rossini-pas-de-calais"


def test_clone_zone_codes_accepte_csv_string(fake_config_root: Path) -> None:
    (fake_config_root / "rossini.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "rossini.yaml", "multi", overrides={"zone_codes": "59, 62, 80"}
    )
    parsed = yaml.safe_load(Path(res["path"]).read_text(encoding="utf-8"))
    assert parsed["zone"]["codes"] == ["59", "62", "80"]


def test_clone_avec_secteurs_strings(fake_config_root: Path) -> None:
    (fake_config_root / "rossini.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "rossini.yaml",
        "rossini_2sect",
        overrides={"secteurs": ["cabinet comptable", "expert-comptable"]},
    )
    parsed = yaml.safe_load(Path(res["path"]).read_text(encoding="utf-8"))
    assert len(parsed["secteurs"]) == 2
    assert parsed["secteurs"][0]["query"] == "cabinet comptable"
    assert parsed["secteurs"][0]["type"] == "establishment"


def test_clone_secteurs_doit_etre_liste(fake_config_root: Path) -> None:
    (fake_config_root / "rossini.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "rossini.yaml", "bad", overrides={"secteurs": "pas une liste"}
    )
    assert "error" in res


def test_clone_overrides_inconnus_rejetes(fake_config_root: Path) -> None:
    (fake_config_root / "rossini.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "rossini.yaml", "bad", overrides={"truc_qui_existe_pas": 42}
    )
    assert "error" in res
    assert "non autorisés" in res["error"]


def test_clone_source_introuvable(fake_config_root: Path) -> None:
    res = wf.clone_config("nope.yaml", "x")
    assert "error" in res


def test_clone_traversal_rejete(fake_config_root: Path) -> None:
    res = wf.clone_config("../../etc/passwd", "x")
    assert "error" in res


def test_clone_save_as_ajoute_yaml_si_absent(fake_config_root: Path) -> None:
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config("src.yaml", "sans_ext")
    assert res["path"].endswith(".yaml")


def test_clone_save_as_basename_uniquement(fake_config_root: Path) -> None:
    """Empêche path traversal via save_as."""
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config("src.yaml", "../../etc/evil")
    assert "error" not in res
    # Le nom est sanitisé : juste le basename
    assert "etc" not in res["path"]
    assert "evil" in res["path"]


def test_clone_volume_et_budget(fake_config_root: Path) -> None:
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "src.yaml",
        "gros",
        overrides={"volume_cible": 100, "budget_max_eur": 10.5},
    )
    parsed = yaml.safe_load(Path(res["path"]).read_text(encoding="utf-8"))
    assert parsed["volume"]["cible"] == 100
    assert parsed["budget"]["max_eur"] == 10.5


def test_clone_volume_non_int_rejete(fake_config_root: Path) -> None:
    """Coercition int sur volume_cible — payload malformé → message clair."""
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "src.yaml", "bad", overrides={"volume_cible": "pas un nombre"}
    )
    assert "error" in res
    assert "volume_cible" in res["error"]


def test_clone_budget_non_float_rejete(fake_config_root: Path) -> None:
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    res = wf.clone_config(
        "src.yaml", "bad", overrides={"budget_max_eur": "abc"}
    )
    assert "error" in res


def test_clone_save_as_caracteres_dangereux_rejetes(fake_config_root: Path) -> None:
    """Espaces et caractères spéciaux dans save_as → erreur claire.

    Note : les slashes sont silencieusement strippés via Path(save_as).name
    avant la validation regex (cf. test_clone_save_as_basename_uniquement).
    """
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    for nom in ["avec espace", "avec*etoile", "avec?question", ""]:
        res = wf.clone_config("src.yaml", nom)
        assert "error" in res, f"'{nom}' aurait dû échouer"


def test_clone_save_as_collision_suffixe_timestamp(
    fake_config_root: Path,
) -> None:
    """2 appels avec même save_as → 2 fichiers distincts (anti race condition)."""
    (fake_config_root / "src.yaml").write_text(ROSSINI_YAML, encoding="utf-8")
    r1 = wf.clone_config("src.yaml", "test_collision")
    r2 = wf.clone_config("src.yaml", "test_collision")
    assert r1["path"] != r2["path"]
    assert "test_collision" in r2["path"]
    # Le 2e a un suffixe timestamp
    assert Path(r1["path"]).exists()
    assert Path(r2["path"]).exists()


# ────────────────────────────────────────────────────────────────────
# compare_sessions
# ────────────────────────────────────────────────────────────────────


def _session_l3(root: Path, sid: str, n: int, complet: bool) -> None:
    d = root / sid
    d.mkdir()
    rows = [
        {
            "nom": f"E{i}",
            "siren": f"100{i}" if complet else "",
            "dirigeant_nom": f"D{i}" if complet else "",
            "email_principal": f"e{i}@x.fr" if complet else "",
        }
        for i in range(n)
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)


def test_compare_sessions_b_meilleure(fake_output_root: Path) -> None:
    _session_l3(fake_output_root, "s_a", n=10, complet=False)
    _session_l3(fake_output_root, "s_b", n=10, complet=True)
    res = wf.compare_sessions("s_a", "s_b")
    assert "error" not in res
    assert res["delta_b_moins_a"]["l3"]["pct_siren_matche"] == 100.0
    assert "B meilleure" in res["verdict"]


def test_compare_sessions_inclut_l3_5_si_present(fake_output_root: Path) -> None:
    """Quand les 2 sessions ont L3.5, le delta couvre aussi cet étage."""
    _session_l3(fake_output_root, "s_a", n=5, complet=True)
    _session_l3(fake_output_root, "s_b", n=5, complet=True)
    _ecrire_csv(
        fake_output_root / "s_a" / "etage3_5_enrichissement.csv",
        [
            {"nom": "X", "email_dropcontact": "", "telephone_direct_dropcontact": ""}
        ],
    )
    _ecrire_csv(
        fake_output_root / "s_b" / "etage3_5_enrichissement.csv",
        [
            {
                "nom": "X",
                "email_dropcontact": "x@y.fr",
                "telephone_direct_dropcontact": "0102",
            }
        ],
    )
    res = wf.compare_sessions("s_a", "s_b")
    assert "l3_5" in res["metriques_a"]
    assert "l3_5" in res["delta_b_moins_a"]
    assert res["delta_b_moins_a"]["l3_5"]["pct_email_verifie_dropcontact"] == 100.0


def test_compare_sessions_inclut_l4_si_present(fake_output_root: Path) -> None:
    """Quand les 2 sessions ont L4, le delta couvre top_leads et score."""
    _session_l3(fake_output_root, "s_a", n=3, complet=True)
    _session_l3(fake_output_root, "s_b", n=3, complet=True)
    _ecrire_csv(
        fake_output_root / "s_a" / "etage4_prospection.csv",
        [
            {"nom": "X", "score_interet": "40", "top_lead": "FAUX"},
            {"nom": "Y", "score_interet": "50", "top_lead": "FAUX"},
        ],
    )
    _ecrire_csv(
        fake_output_root / "s_b" / "etage4_prospection.csv",
        [
            {"nom": "X", "score_interet": "85", "top_lead": "VRAI"},
            {"nom": "Y", "score_interet": "90", "top_lead": "VRAI"},
        ],
    )
    res = wf.compare_sessions("s_a", "s_b")
    assert "l4" in res["delta_b_moins_a"]
    assert res["delta_b_moins_a"]["l4"]["nb_top_leads"] == 2
    assert res["delta_b_moins_a"]["l4"]["score_moyen"] > 40


def test_compare_sessions_a_meilleure(fake_output_root: Path) -> None:
    _session_l3(fake_output_root, "s_a", n=10, complet=True)
    _session_l3(fake_output_root, "s_b", n=10, complet=False)
    res = wf.compare_sessions("s_a", "s_b")
    assert "A meilleure" in res["verdict"]


def test_compare_sessions_equivalentes(fake_output_root: Path) -> None:
    _session_l3(fake_output_root, "s_a", n=10, complet=True)
    _session_l3(fake_output_root, "s_b", n=10, complet=True)
    res = wf.compare_sessions("s_a", "s_b")
    assert "équivalente" in res["verdict"]


def test_compare_sessions_inconnue(fake_output_root: Path) -> None:
    _session_l3(fake_output_root, "s_a", n=10, complet=True)
    res = wf.compare_sessions("s_a", "nope")
    assert "error" in res


def test_compare_sessions_sans_l3(fake_output_root: Path) -> None:
    _session_l3(fake_output_root, "s_a", n=10, complet=True)
    (fake_output_root / "s_b").mkdir()
    res = wf.compare_sessions("s_a", "s_b")
    assert "error" in res
    assert "étage 3" in res["error"]


# ────────────────────────────────────────────────────────────────────
# Registry
# ────────────────────────────────────────────────────────────────────


def test_outils_enregistres() -> None:
    from renoboost_leads.agent.tools import all_dispatch, all_schemas

    schemas = all_schemas()
    noms = {s["name"] for s in schemas}
    assert "clone_config" in noms
    assert "compare_sessions" in noms
    d = all_dispatch()
    assert "clone_config" in d
    assert "compare_sessions" in d
