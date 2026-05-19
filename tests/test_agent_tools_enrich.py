"""Tests des outils agent ciblés `enrich_l3_5_on_session` / `score_l4_on_session`.

On mocke `subprocess.run` pour éviter l'exécution réelle du CLI (qui
demanderait des secrets API). On vérifie le contrat : pré-checks, command
construite, extraction des stats depuis le CSV produit.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from renoboost_leads.agent.tools import enrich as enr
from renoboost_leads.agent.tools import sessions as sess


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(enr, "OUTPUT_ROOT", root)
    return root


def _ecrire_csv(p: Path, rows: list[dict]) -> None:
    if not rows:
        p.write_text("nom\n", encoding="utf-8")
        return
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _session_l3_complete(root: Path, sid: str) -> Path:
    """Session avec L1+L3 + config snapshot, prête pour L3.5 ou L4."""
    d = root / sid
    d.mkdir()
    _ecrire_csv(
        d / "etage1_decouverte.csv",
        [{"nom": f"E{i}", "place_id": f"p{i}"} for i in range(3)],
    )
    _ecrire_csv(
        d / "etage3_contacts.csv",
        [
            {
                "nom": f"E{i}",
                "siren": f"100{i}",
                "dirigeant_nom": "Martin",
                "email_principal": "a@b.fr",
            }
            for i in range(3)
        ],
    )
    (d / "config_snapshot.yaml").write_text("run:\n  client_name: test\n", encoding="utf-8")
    return d


# ── Pré-checks ─────────────────────────────────────────────────────


def test_session_inconnue_l3_5(fake_root: Path) -> None:
    res = enr.enrich_l3_5_on_session("nope")
    assert "error" in res
    assert "inconnue" in res["error"]


def test_session_inconnue_l4(fake_root: Path) -> None:
    res = enr.score_l4_on_session("nope")
    assert "error" in res


def test_l3_absent_l3_5(fake_root: Path) -> None:
    d = fake_root / "s_no_l3"
    d.mkdir()
    (d / "config_snapshot.yaml").write_text("run:\n  client_name: t\n", encoding="utf-8")
    res = enr.enrich_l3_5_on_session("s_no_l3")
    assert "error" in res
    assert "L3" in res["error"] or "etage3_contacts" in res["error"]


def test_l3_absent_l4(fake_root: Path) -> None:
    d = fake_root / "s_no_l3"
    d.mkdir()
    (d / "config_snapshot.yaml").write_text("run:\n  client_name: t\n", encoding="utf-8")
    res = enr.score_l4_on_session("s_no_l3")
    assert "error" in res


def test_config_snapshot_absent(fake_root: Path) -> None:
    d = fake_root / "s_no_cfg"
    d.mkdir()
    _ecrire_csv(
        d / "etage3_contacts.csv", [{"nom": "X", "siren": "1"}]
    )
    _ecrire_csv(d / "etage1_decouverte.csv", [{"nom": "X"}])
    res = enr.enrich_l3_5_on_session("s_no_cfg")
    assert "error" in res
    assert "config_snapshot" in res["error"]


def test_etage1_absent_bloque(fake_root: Path) -> None:
    d = fake_root / "s_no_l1"
    d.mkdir()
    _ecrire_csv(d / "etage3_contacts.csv", [{"nom": "X"}])
    (d / "config_snapshot.yaml").write_text("run:\n  client_name: t\n", encoding="utf-8")
    res = enr.enrich_l3_5_on_session("s_no_l1")
    assert "error" in res
    assert "etage1" in res["error"]


# ── Commande subprocess construite correctement ────────────────────


def test_command_l3_5_contient_les_bons_args(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_l3_complete(fake_root, "s_ok")
    captured: dict[str, Any] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        # Simule run réussi sans CSV produit
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = enr.enrich_l3_5_on_session("s_ok", dry_run=True)
    assert res["ok"] is True
    cmd = captured["cmd"]
    assert cmd[0] == sys.executable
    assert "run" in cmd
    assert "--stages" in cmd
    idx = cmd.index("--stages")
    assert cmd[idx + 1] == "3.5"
    assert "--from-csv" in cmd
    assert "--dry-run" in cmd


def test_command_l4_stages_4(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_l3_complete(fake_root, "s_ok2")
    captured: dict[str, Any] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    enr.score_l4_on_session("s_ok2", dry_run=False)
    cmd = captured["cmd"]
    idx = cmd.index("--stages")
    assert cmd[idx + 1] == "4"
    assert "--dry-run" not in cmd


# ── Extraction de stats post-CSV ───────────────────────────────────


def test_stats_l3_5_extraites_du_csv(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _session_l3_complete(fake_root, "s_stats")

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        # Écrit un CSV L3.5 mock
        _ecrire_csv(
            d / "etage3_5_enrichissement.csv",
            [
                {
                    "nom": "A",
                    "email_dropcontact": "a@x.fr",
                    "qualification_email_dropcontact": "correct",
                    "telephone_direct_dropcontact": "0102",
                    "linkedin_dirigeant_dropcontact": "",
                    "enrichi_dropcontact": "VRAI",
                },
                {
                    "nom": "B",
                    "email_dropcontact": "b@x.fr",
                    "qualification_email_dropcontact": "wrong",
                    "telephone_direct_dropcontact": "",
                    "linkedin_dirigeant_dropcontact": "linkedin.com/in/b",
                    "enrichi_dropcontact": "VRAI",
                },
                {
                    "nom": "C",
                    "email_dropcontact": "",
                    "qualification_email_dropcontact": "",
                    "telephone_direct_dropcontact": "",
                    "linkedin_dirigeant_dropcontact": "",
                    "enrichi_dropcontact": "FAUX",
                },
            ],
        )
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = enr.enrich_l3_5_on_session("s_stats", dry_run=True)
    assert res["ok"] is True
    s = res["stats"]
    assert s["total"] == 3
    assert s["enrichis"] == 2
    assert s["pct_email_dropcontact"] == round(100 * 2 / 3, 1)
    assert s["pct_email_correct"] == round(100 * 1 / 3, 1)
    assert s["pct_tel_direct"] == round(100 * 1 / 3, 1)
    assert s["pct_linkedin"] == round(100 * 1 / 3, 1)


def test_stats_l4_extraites_du_csv(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _session_l3_complete(fake_root, "s_l4")

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        _ecrire_csv(
            d / "etage4_prospection.csv",
            [
                {"nom": "A", "score_interet": "80", "top_lead": "VRAI", "pitch_propose": "X"},
                {"nom": "B", "score_interet": "65", "top_lead": "FAUX", "pitch_propose": "Y"},
                {"nom": "C", "score_interet": "30", "top_lead": "FAUX", "pitch_propose": ""},
                {"nom": "D", "score_interet": "90", "top_lead": "VRAI", "pitch_propose": "Z"},
            ],
        )
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = enr.score_l4_on_session("s_l4", dry_run=True)
    s = res["stats"]
    assert s["total"] == 4
    assert s["top_leads"] == 2
    assert s["pct_top_leads"] == 50.0
    # moyenne (80+65+30+90)/4 = 66.25
    assert s["score_moyen"] == 66.2 or s["score_moyen"] == 66.3
    assert s["pct_avec_pitch"] == 75.0


# ── Timeout / erreurs subprocess ───────────────────────────────────


def test_timeout_renvoie_erreur(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_l3_complete(fake_root, "s_timeout")

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = enr.enrich_l3_5_on_session("s_timeout", timeout_s=60)
    assert "error" in res
    assert "timeout" in res["error"].lower()
    assert "command" in res


def test_returncode_non_zero_marque_ko(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_l3_complete(fake_root, "s_fail")

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, returncode=2, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = enr.score_l4_on_session("s_fail")
    assert res["ok"] is False
    assert res["returncode"] == 2
    assert "boom" in res["stderr_tail"]


# ── Registry ───────────────────────────────────────────────────────


def test_outils_enregistres_dans_registry() -> None:
    from renoboost_leads.agent.tools import all_dispatch, all_schemas

    noms = {s["name"] for s in all_schemas()}
    assert "enrich_l3_5_on_session" in noms
    assert "score_l4_on_session" in noms
    dispatch = all_dispatch()
    assert "enrich_l3_5_on_session" in dispatch
    assert "score_l4_on_session" in dispatch
