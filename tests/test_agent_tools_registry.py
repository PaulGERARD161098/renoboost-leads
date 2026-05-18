"""Test du registry tools (schemas + dispatch cohérents)."""

from __future__ import annotations

from renoboost_leads.agent import tools


def test_all_schemas_contient_pipeline_et_sessions() -> None:
    noms = {s["name"] for s in tools.all_schemas()}
    assert "list_sessions" in noms
    assert "read_session" in noms
    assert "run_pipeline" in noms


def test_all_dispatch_correspond_aux_schemas() -> None:
    schemas = tools.all_schemas()
    dispatch = tools.all_dispatch()
    noms_schemas = {s["name"] for s in schemas}
    noms_dispatch = set(dispatch.keys())
    assert noms_schemas == noms_dispatch


def test_chaque_schema_a_input_valide() -> None:
    for s in tools.all_schemas():
        assert "name" in s
        assert "description" in s
        assert "input_schema" in s
        assert s["input_schema"]["type"] == "object"
