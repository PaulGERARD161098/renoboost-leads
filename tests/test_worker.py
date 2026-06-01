"""Tests du worker M3 — boucle de runs + DemoPipeline, sans réseau."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from worker.config import ConfigError, WorkerConfig
from worker.pipeline import DemoPipeline, RunContext, build_pipeline
from worker.worker import Worker


class FakeDB:
    """Faux SupabaseRest en mémoire : reproduit le contrat utilisé par Worker."""

    def __init__(self, runs: list[dict[str, Any]], verticales: dict[str, dict[str, Any]]):
        self.runs = {r["id"]: dict(r) for r in runs}
        self.verticales = verticales
        self.leads: list[dict[str, Any]] = []
        self.progress_calls: list[tuple[str, int, dict[str, int]]] = []

    def fetch_pending_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        pend = [dict(r) for r in self.runs.values() if r["status"] == "demande"]
        return pend[:limit]

    def claim_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.runs.get(run_id)
        if run is None or run["status"] != "demande":
            return None
        run["status"] = "en_cours"
        return dict(run)

    def get_verticale(self, verticale_id: str | None) -> dict[str, Any] | None:
        return self.verticales.get(verticale_id) if verticale_id else None

    def update_run_progress(
        self, run_id: str, *, etape: str, progress: int, counts: dict[str, int]
    ) -> None:
        self.progress_calls.append((etape, progress, counts))
        self.runs[run_id].update(etape_courante=etape, progress=progress, counts=counts)

    def insert_leads(self, rows: list[dict[str, Any]]) -> None:
        self.leads.extend(rows)

    def finalize_run(
        self, run_id, *, status, counts, cout_eur, erreur=None
    ) -> None:
        self.runs[run_id].update(
            status=status,
            counts=counts,
            cout_eur=round(cout_eur, 2),
            erreur=erreur,
            progress=100 if status == "termine" else 0,
            etape_courante="Terminé" if status == "termine" else "Échec",
        )


def _config() -> WorkerConfig:
    return WorkerConfig(supabase_url="https://x.supabase.co", service_role_key="k", mode="demo")


def _make_run(verticale_id: str | None = None, volume: int = 8) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "verticale_id": verticale_id,
        "zone": {"departement": "59", "effectif_min": 50},
        "volume_cible": volume,
        "status": "demande",
    }


# --- config ------------------------------------------------------------------


def test_config_missing_keys_raises():
    with pytest.raises(ConfigError):
        WorkerConfig.from_env({})


def test_config_rejects_bad_mode():
    with pytest.raises(ConfigError):
        WorkerConfig.from_env(
            {"SUPABASE_URL": "u", "SUPABASE_SERVICE_ROLE_KEY": "k", "WORKER_MODE": "wat"}
        )


def test_config_rest_url():
    cfg = WorkerConfig(supabase_url="https://x.supabase.co/", service_role_key="k")
    assert cfg.rest_url == "https://x.supabase.co/rest/v1"


# --- DemoPipeline ------------------------------------------------------------


def test_demo_pipeline_generates_expected_leads():
    vert = {"config": {"offre": "ombrières photovoltaïques", "secteurs_naf": ["49.41A"],
                       "signaux": ["grande toiture"]}}
    ctx = RunContext(run=_make_run(volume=10), verticale=vert)
    emitted: list[tuple[str, int, dict[str, int]]] = []
    result = DemoPipeline(seed=42).run(ctx, lambda e, p, c: emitted.append((e, p, c)))

    assert len(result.leads) == 10
    assert result.counts["leads"] == 10
    assert result.cout_eur == pytest.approx(0.40)
    # Progression bornée et croissante jusqu'à <=95.
    assert emitted[0][1] == 10
    assert all(0 <= p <= 95 for _, p, _ in emitted)
    # Chaque lead a les champs requis par le schéma.
    lead = result.leads[0]
    for key in ("entreprise", "siren", "naf", "ville", "code_postal", "score",
                "mail_sujet", "mail_corps", "statut"):
        assert lead[key] not in (None, "")
    assert lead["statut"] == "a_valider"
    assert lead["verticale_id"] is None or isinstance(lead["verticale_id"], str)


def test_demo_pipeline_caps_at_50():
    ctx = RunContext(run=_make_run(volume=999), verticale=None, max_leads=500)
    result = DemoPipeline(seed=1).run(ctx, lambda *a: None)
    assert len(result.leads) == 50


def test_build_pipeline_real_not_implemented():
    with pytest.raises(NotImplementedError):
        build_pipeline("real")


def test_build_pipeline_unknown():
    with pytest.raises(ValueError):
        build_pipeline("???")


# --- Worker ------------------------------------------------------------------


def test_worker_processes_run_end_to_end():
    vid = str(uuid.uuid4())
    run = _make_run(verticale_id=vid, volume=6)
    db = FakeDB(runs=[run], verticales={vid: {"config": {"offre": "IRVE"}}})
    worker = Worker(_config(), db=db, pipeline=DemoPipeline(seed=7))

    traites = worker.poll_once()

    assert traites == 1
    assert db.runs[run["id"]]["status"] == "termine"
    assert db.runs[run["id"]]["progress"] == 100
    assert len(db.leads) == 6
    assert db.runs[run["id"]]["cout_eur"] == pytest.approx(0.24)
    assert len(db.progress_calls) >= 1


def test_worker_marks_failure_on_pipeline_error():
    run = _make_run(volume=3)

    class Boom:
        def run(self, ctx, emit):
            raise RuntimeError("kaboom")

    db = FakeDB(runs=[run], verticales={})
    worker = Worker(_config(), db=db, pipeline=Boom())

    worker.poll_once()

    assert db.runs[run["id"]]["status"] == "echoue"
    assert "kaboom" in db.runs[run["id"]]["erreur"]
    assert db.leads == []


def test_worker_skips_already_claimed_run():
    run = _make_run(volume=2)
    run["status"] = "en_cours"  # déjà pris
    db = FakeDB(runs=[run], verticales={})
    worker = Worker(_config(), db=db, pipeline=DemoPipeline(seed=1))

    assert worker.poll_once() == 0
    assert db.leads == []
