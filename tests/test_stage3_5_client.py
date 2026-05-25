"""Tests du wrapper Dropcontact (POST + polling + retry + budget)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from renoboost_leads.common.budget_guard import BudgetExceededError, BudgetGuard
from renoboost_leads.stage3_5_enrichment.client import (
    DropcontactClient,
    DropcontactClientConfig,
    DropcontactError,
    DropcontactTimeoutError,
    lead_payload_dropcontact,
)


@dataclass
class _FakeResponse:
    status_code: int
    body: dict | None = None
    text: str = ""

    def json(self):
        if self.body is None:
            raise ValueError("non-json")
        return self.body


def _post_factory(response: _FakeResponse):
    captured = {}

    def _fn(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return response

    return _fn, captured


def _get_factory(responses: list[_FakeResponse]):
    iterator = iter(responses)

    def _fn(url, *, headers, timeout):
        return next(iterator)

    return _fn


class TestPayload:
    def test_omet_les_champs_vides(self):
        p = lead_payload_dropcontact(
            first_name="Paul", last_name=None, company="Acme",
            website="acme.fr", siren="123",
        )
        assert p == {
            "first_name": "Paul",
            "company": "Acme",
            "website": "acme.fr",
            "siren": "123",
        }
        assert "last_name" not in p

    def test_email_optionnel(self):
        p = lead_payload_dropcontact(
            first_name="P", last_name="D", company="A", website="a.fr",
            siren="1", email="p@a.fr",
        )
        assert p["email"] == "p@a.fr"


class TestDropcontactClient:
    def test_post_puis_polling_succes_premier_get(self):
        post_resp = _FakeResponse(200, body={"request_id": "req-1"})
        get_resp = _FakeResponse(200, body={"success": True, "data": [{"email": []}]})

        post_fn, captured = _post_factory(post_resp)
        get_fn = _get_factory([get_resp])

        cfg = DropcontactClientConfig(
            api_key="key123",
            poll_initial_delay_s=0.0,
            poll_interval_s=0.0,
            poll_timeout_s=10.0,
            http_post=post_fn,
            http_get=get_fn,
            sleep_fn=lambda s: None,
        )
        client = DropcontactClient(cfg)
        rep = client.enrichir_batch([{"first_name": "Paul", "company": "Acme"}])

        assert rep.request_id == "req-1"
        assert len(rep.data) == 1
        assert rep.cout_eur == pytest.approx(0.50)
        assert captured["headers"]["X-Access-Token"] == "key123"
        assert captured["json"]["language"] == "fr"
        assert captured["json"]["siren"] is True

    def test_polling_attend_avant_succes(self):
        post_resp = _FakeResponse(200, body={"request_id": "r"})
        get_responses = [
            _FakeResponse(200, body={"success": False, "reason": "processing"}),
            _FakeResponse(200, body={"success": False, "reason": "processing"}),
            _FakeResponse(200, body={"success": True, "data": [{}]}),
        ]
        post_fn, _ = _post_factory(post_resp)
        get_fn = _get_factory(get_responses)
        sleeps: list[float] = []

        cfg = DropcontactClientConfig(
            api_key="k",
            poll_initial_delay_s=2.0,
            poll_interval_s=3.0,
            poll_timeout_s=60.0,
            http_post=post_fn,
            http_get=get_fn,
            sleep_fn=sleeps.append,
        )
        client = DropcontactClient(cfg)
        rep = client.enrichir_batch([{"first_name": "P"}])
        assert rep.data == [{}]
        # 1 sleep initial + 2 sleeps d'intervalle entre les 3 polls
        assert sleeps == [2.0, 3.0, 3.0]

    def test_timeout_si_jamais_pret(self):
        post_resp = _FakeResponse(200, body={"request_id": "r"})
        # 10 réponses "pas prêt" — assez pour dépasser le timeout
        get_responses = [
            _FakeResponse(200, body={"success": False, "reason": "wait"})
            for _ in range(10)
        ]
        post_fn, _ = _post_factory(post_resp)
        get_fn = _get_factory(get_responses)

        cfg = DropcontactClientConfig(
            api_key="k",
            poll_initial_delay_s=1.0,
            poll_interval_s=1.0,
            poll_timeout_s=3.0,
            http_post=post_fn,
            http_get=get_fn,
            sleep_fn=lambda s: None,
        )
        client = DropcontactClient(cfg)
        with pytest.raises(DropcontactTimeoutError):
            client.enrichir_batch([{"first_name": "P"}])

    def test_post_400_leve_dropcontact_error(self):
        post_resp = _FakeResponse(400, text="bad request")
        post_fn, _ = _post_factory(post_resp)
        cfg = DropcontactClientConfig(
            api_key="k",
            http_post=post_fn,
            http_get=lambda *a, **k: _FakeResponse(200, body={}),
            sleep_fn=lambda s: None,
        )
        client = DropcontactClient(cfg)
        with pytest.raises(DropcontactError):
            client.enrichir_batch([{"first_name": "P"}])

    def test_403_allowlist_leve_host_blocked(self):
        from renoboost_leads.stage3_5_enrichment.client import DropcontactHostBlockedError

        post_resp = _FakeResponse(403, text="Host not in allowlist")
        post_fn, _ = _post_factory(post_resp)
        cfg = DropcontactClientConfig(
            api_key="k",
            http_post=post_fn,
            http_get=lambda *a, **k: _FakeResponse(200, body={}),
            sleep_fn=lambda s: None,
        )
        client = DropcontactClient(cfg)
        with pytest.raises(DropcontactHostBlockedError):
            client.enrichir_batch([{"first_name": "P"}])

    def test_403_autre_reste_dropcontact_error(self):
        from renoboost_leads.stage3_5_enrichment.client import DropcontactHostBlockedError

        post_resp = _FakeResponse(403, text="Forbidden: bad token")
        post_fn, _ = _post_factory(post_resp)
        cfg = DropcontactClientConfig(
            api_key="k",
            http_post=post_fn,
            http_get=lambda *a, **k: _FakeResponse(200, body={}),
            sleep_fn=lambda s: None,
        )
        client = DropcontactClient(cfg)
        with pytest.raises(DropcontactError) as exc:
            client.enrichir_batch([{"first_name": "P"}])
        assert not isinstance(exc.value, DropcontactHostBlockedError)

    def test_budget_exceeded_avant_appel(self):
        budget = BudgetGuard(plafond_eur=0.10)
        cfg = DropcontactClientConfig(
            api_key="k",
            cout_par_lead_eur=0.50,
            budget=budget,
            http_post=lambda *a, **k: _FakeResponse(200, body={"request_id": "r"}),
            http_get=lambda *a, **k: _FakeResponse(200, body={"success": True, "data": [{}]}),
            sleep_fn=lambda s: None,
        )
        client = DropcontactClient(cfg)
        with pytest.raises(BudgetExceededError):
            client.enrichir_batch([{"first_name": "P"}])

    def test_lots_vides_court_circuit(self):
        cfg = DropcontactClientConfig(api_key="k", sleep_fn=lambda s: None)
        client = DropcontactClient(cfg)
        rep = client.enrichir_batch([])
        assert rep.data == []
        assert rep.cout_eur == 0.0
