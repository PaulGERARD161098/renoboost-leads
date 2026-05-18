"""Tests des outils alert_human et email_report (SMTP mocké)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from renoboost_leads.agent.tools import notify
from renoboost_leads.agent.tools import report as rep
from renoboost_leads.agent.tools import sessions as sess
from renoboost_leads.settings import Settings


def _settings_smtp_ok() -> Settings:
    return Settings(
        google_places_api_key=SecretStr("AIza" + "x" * 35),
        smtp_host="smtp.test.fr",
        smtp_port=587,
        smtp_user="bot@x.fr",
        smtp_password=SecretStr("pw"),
        smtp_from="bot@x.fr",
        smtp_destinataires="paul@renoboost.fr",
    )


def _settings_smtp_off() -> Settings:
    return Settings(google_places_api_key=SecretStr("AIza" + "x" * 35))


def test_urgence_invalide() -> None:
    res = notify.alert_human("s", "b", urgency="zzz")
    assert "error" in res


def test_subject_vide() -> None:
    res = notify.alert_human("", "body")
    assert "error" in res


def test_smtp_non_configure_renvoie_non_envoye() -> None:
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings", return_value=_settings_smtp_off()
    ):
        res = notify.alert_human("ping", "corps")
    assert res["sent"] is False
    assert "SMTP" in res["reason"]
    assert "ping" in res["subject_qu_aurait_ete_envoye"]


def test_smtp_envoi_ok() -> None:
    smtp_mock = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = smtp_mock
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings", return_value=_settings_smtp_ok()
    ), patch("renoboost_leads.agent.tools.notify.smtplib.SMTP", return_value=cm):
        res = notify.alert_human("sujet", "corps", urgency="attention")
    assert res["sent"] is True
    assert res["urgency"] == "attention"
    assert "ATTENTION" in res["subject"]
    smtp_mock.starttls.assert_called_once()
    smtp_mock.login.assert_called_once()
    smtp_mock.send_message.assert_called_once()


def test_smtp_erreur_renvoie_sent_false() -> None:
    import smtplib

    cm = MagicMock()
    cm.__enter__.side_effect = smtplib.SMTPException("nope")
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings", return_value=_settings_smtp_ok()
    ), patch("renoboost_leads.agent.tools.notify.smtplib.SMTP", return_value=cm):
        res = notify.alert_human("s", "b")
    assert res["sent"] is False
    assert "SMTP" in res["reason"]


def test_destinataires_surcharge() -> None:
    smtp_mock = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = smtp_mock
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings", return_value=_settings_smtp_ok()
    ), patch("renoboost_leads.agent.tools.notify.smtplib.SMTP", return_value=cm):
        res = notify.alert_human("s", "b", destinataires=["x@y.fr", "z@a.fr"])
    assert res["destinataires"] == ["x@y.fr", "z@a.fr"]


# ────────────────────────────────────────────────────────────────────
# email_report
# ────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_output_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(rep, "OUTPUT_ROOT", root)
    return root


def _session_l3(root: Path, sid: str, n: int = 5) -> Path:
    d = root / sid
    d.mkdir()
    rows = [
        {
            "nom": f"E{i}",
            "siren": f"100{i}",
            "dirigeant_nom": f"D{i}",
            "email_principal": f"e{i}@x.fr",
        }
        for i in range(n)
    ]
    with (d / "etage3_contacts.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (d / "run_stats.json").write_text(
        json.dumps({"campaign": "t", "debut": "2026-05-18"}), encoding="utf-8"
    )
    return d


def test_email_report_destinataires_vide() -> None:
    res = notify.email_report("s1", [])
    assert "error" in res


def test_email_report_email_invalide() -> None:
    res = notify.email_report("s1", ["pas-un-email"])
    assert "error" in res
    assert "invalides" in res["error"]


def test_email_report_session_inconnue(fake_output_root: Path) -> None:
    res = notify.email_report("nope", ["x@y.fr"])
    assert "error" in res


def test_email_report_smtp_off_renvoie_non_envoye(
    fake_output_root: Path,
) -> None:
    _session_l3(fake_output_root, "s1")
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings",
        return_value=_settings_smtp_off(),
    ):
        res = notify.email_report("s1", ["client@x.fr"])
    assert res["sent"] is False
    assert "SMTP" in res["reason"]
    assert res["destinataires_qu_auraient_recu"] == ["client@x.fr"]


def test_email_report_envoi_ok_avec_piece_jointe(
    fake_output_root: Path,
) -> None:
    _session_l3(fake_output_root, "s1")
    smtp_mock = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = smtp_mock
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings",
        return_value=_settings_smtp_ok(),
    ), patch(
        "renoboost_leads.agent.tools.notify.smtplib.SMTP", return_value=cm
    ):
        res = notify.email_report(
            "s1", ["client@x.fr"], subject="Mon rapport"
        )
    assert res["sent"] is True
    assert res["attachment_bytes"] > 100
    assert res["subject"] == "Mon rapport"
    # Vérifie qu'un message avec pièce jointe a été envoyé
    smtp_mock.send_message.assert_called_once()
    msg = smtp_mock.send_message.call_args[0][0]
    # EmailMessage : la pièce jointe est dans msg.iter_attachments()
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename().startswith("rapport_s1")


def test_email_report_regenere_si_demande(fake_output_root: Path) -> None:
    """Si regenerer=True, le rapport est généré même s'il existe déjà."""
    d = _session_l3(fake_output_root, "s1")
    rapport = d / "rapport.html"
    rapport.write_text("<html>vieux contenu</html>", encoding="utf-8")
    smtp_mock = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = smtp_mock
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings",
        return_value=_settings_smtp_ok(),
    ), patch(
        "renoboost_leads.agent.tools.notify.smtplib.SMTP", return_value=cm
    ):
        res = notify.email_report("s1", ["c@x.fr"], regenerer=True)
    assert res["sent"] is True
    # Le rapport a été regénéré (taille > vieux contenu)
    assert "vieux contenu" not in rapport.read_text(encoding="utf-8")
    assert res["attachment_bytes"] > 500


def test_email_report_genere_si_absent(fake_output_root: Path) -> None:
    """Si rapport.html absent, generate_report est appelé automatiquement."""
    d = _session_l3(fake_output_root, "s1")
    assert not (d / "rapport.html").exists()
    smtp_mock = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = smtp_mock
    with patch(
        "renoboost_leads.agent.tools.notify.get_settings",
        return_value=_settings_smtp_ok(),
    ), patch(
        "renoboost_leads.agent.tools.notify.smtplib.SMTP", return_value=cm
    ):
        res = notify.email_report("s1", ["c@x.fr"])
    assert res["sent"] is True
    assert (d / "rapport.html").exists()


def test_email_report_dans_registry() -> None:
    from renoboost_leads.agent.tools import all_dispatch, all_schemas

    noms = {s["name"] for s in all_schemas()}
    assert "email_report" in noms
    assert "email_report" in all_dispatch()
