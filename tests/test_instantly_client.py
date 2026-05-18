"""Tests du wrapper Instantly (mode dry-run + HTTP mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from renoboost_leads.instantly.client import (
    InstantlyClient,
    InstantlyConfig,
    InstantlyError,
)
from renoboost_leads.settings import Settings

# ─── Mode dry-run (clé absente) ────────────────────────────────────


@pytest.fixture
def cli_dry() -> InstantlyClient:
    cfg = InstantlyConfig(api_key=None, base_url="https://x.test", dry_run=True)
    return InstantlyClient(config=cfg)


def test_dry_run_actif_si_pas_de_cle(cli_dry: InstantlyClient) -> None:
    assert cli_dry.is_dry_run() is True


def test_dry_run_create_campaign_renvoie_id_simule(cli_dry: InstantlyClient) -> None:
    res = cli_dry.create_campaign("test", from_email="a@b.fr")
    assert res["dry_run"] is True
    assert res["id"].startswith("dry-")
    assert res["name"] == "test"
    assert res["status"] == "draft"


def test_dry_run_add_leads(cli_dry: InstantlyClient) -> None:
    res = cli_dry.add_leads("camp1", [{"email": "x@y.fr"}, {"email": "a@b.fr"}])
    assert res["added"] == 2
    assert res["dry_run"] is True


def test_dry_run_add_leads_vide(cli_dry: InstantlyClient) -> None:
    res = cli_dry.add_leads("camp1", [])
    assert res["added"] == 0


def test_dry_run_metrics(cli_dry: InstantlyClient) -> None:
    res = cli_dry.get_campaign_metrics("camp1")
    assert res["sent"] == 0
    assert res["dry_run"] is True


def test_dry_run_pause(cli_dry: InstantlyClient) -> None:
    res = cli_dry.pause_campaign("camp1")
    assert res["status"] == "paused"


def test_dry_run_list_renvoie_vide(cli_dry: InstantlyClient) -> None:
    assert cli_dry.list_campaigns() == []


# ─── Mode réel (HTTP mocké) ────────────────────────────────────────


def _make_real_client(mock_session: MagicMock) -> InstantlyClient:
    cfg = InstantlyConfig(
        api_key="real-key", base_url="https://api.test/v2", dry_run=False
    )
    return InstantlyClient(config=cfg, session=mock_session)


def _make_resp(*, status: int = 200, payload: dict | None = None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.content = b"x" if payload is not None else b""
    r.json.return_value = payload or {}
    return r


def test_create_campaign_construit_url_et_body() -> None:
    session = MagicMock()
    session.request.return_value = _make_resp(
        payload={"id": "real-1", "name": "n"}
    )
    cli = _make_real_client(session)
    res = cli.create_campaign("n", from_email="from@x.fr", sequence_steps=[{"step": 1}])
    call = session.request.call_args
    assert call.args[0] == "POST"
    assert call.args[1] == "https://api.test/v2/campaigns"
    assert call.kwargs["json"] == {
        "name": "n",
        "from_email": "from@x.fr",
        "sequence_steps": [{"step": 1}],
    }
    assert "Authorization" in call.kwargs["headers"]
    assert call.kwargs["headers"]["Authorization"] == "Bearer real-key"
    assert res["id"] == "real-1"


def test_http_erreur_leve() -> None:
    session = MagicMock()
    session.request.return_value = _make_resp(status=403, text="forbidden")
    cli = _make_real_client(session)
    with pytest.raises(InstantlyError) as exc:
        cli.list_campaigns()
    assert "HTTP 403" in str(exc.value)


def test_reseau_erreur_leve() -> None:
    import requests

    session = MagicMock()
    session.request.side_effect = requests.ConnectionError("dns fail")
    cli = _make_real_client(session)
    with pytest.raises(InstantlyError) as exc:
        cli.list_campaigns()
    assert "Réseau" in str(exc.value)


def test_list_campaigns_parse_items() -> None:
    session = MagicMock()
    session.request.return_value = _make_resp(
        payload={"items": [{"id": "1"}, {"id": "2"}]}
    )
    cli = _make_real_client(session)
    items = cli.list_campaigns(limit=10)
    assert len(items) == 2
    assert items[0]["id"] == "1"


def test_list_campaigns_fallback_clef_campaigns() -> None:
    session = MagicMock()
    session.request.return_value = _make_resp(
        payload={"campaigns": [{"id": "x"}]}
    )
    cli = _make_real_client(session)
    items = cli.list_campaigns()
    assert items[0]["id"] == "x"


def test_get_metrics() -> None:
    session = MagicMock()
    session.request.return_value = _make_resp(
        payload={"sent": 42, "opened": 12, "replied": 3}
    )
    cli = _make_real_client(session)
    m = cli.get_campaign_metrics("campX")
    assert m["sent"] == 42
    call = session.request.call_args
    assert "/campaigns/campX/analytics" in call.args[1]


def test_pause_campaign() -> None:
    session = MagicMock()
    session.request.return_value = _make_resp(payload={"status": "paused"})
    cli = _make_real_client(session)
    res = cli.pause_campaign("camp1")
    assert res["status"] == "paused"
    assert session.request.call_args.args[0] == "POST"


# ─── from_settings ─────────────────────────────────────────────────


def test_config_from_settings_dry_run_si_pas_de_cle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = Settings(google_places_api_key=SecretStr("AIza" + "x" * 35))
    monkeypatch.setattr(
        "renoboost_leads.instantly.client.get_settings", lambda: s
    )
    cfg = InstantlyConfig.from_settings()
    assert cfg.api_key is None
    assert cfg.dry_run is True


def test_config_from_settings_avec_cle(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings(
        google_places_api_key=SecretStr("AIza" + "x" * 35),
        instantly_api_key=SecretStr("real-key"),
        instantly_dry_run=False,
    )
    monkeypatch.setattr(
        "renoboost_leads.instantly.client.get_settings", lambda: s
    )
    cfg = InstantlyConfig.from_settings()
    assert cfg.api_key == "real-key"
    assert cfg.dry_run is False


def test_config_dry_run_force_meme_avec_cle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = Settings(
        google_places_api_key=SecretStr("AIza" + "x" * 35),
        instantly_api_key=SecretStr("real"),
        instantly_dry_run=True,
    )
    monkeypatch.setattr(
        "renoboost_leads.instantly.client.get_settings", lambda: s
    )
    cfg = InstantlyConfig.from_settings()
    assert cfg.dry_run is True
