"""Tests de l'outil alert_human (SMTP mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from renoboost_leads.agent.tools import notify
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
