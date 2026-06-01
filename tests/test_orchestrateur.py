"""Tests de l'orchestrateur partagé CLI/worker — dry-run hermétique (zéro réseau)."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.models import (
    Budget,
    CampaignConfig,
    RunInfo,
    RunStats,
    SecteurCible,
    StagesFlags,
    Volume,
    Zone,
)
from renoboost_leads.orchestrateur import OrchestrationResult, executer_pipeline
from renoboost_leads.settings import get_settings


def _cfg(volume: int = 6) -> CampaignConfig:
    return CampaignConfig(
        run=RunInfo(client_name="test-orch", description="dry", campaign_date="2026-01-01"),
        stages=StagesFlags(enable_stage_1_decouverte=True),
        secteurs=[SecteurCible(type="establishment", query="x")],
        zone=Zone(type="departement", codes=["59"]),
        volume=Volume(cible=volume),
        budget=Budget(max_eur=10),
    )


def _stats() -> RunStats:
    return RunStats(session_id="s", campaign="test-orch", debut=datetime.now(timezone.utc))


def test_executer_pipeline_stage1_dry_rend_les_leads(tmp_path):
    """Étage 1 dry : leads factices déterministes + CSV écrit comme le ferait la CLI."""
    emitted: list[tuple] = []
    result = executer_pipeline(
        _cfg(volume=6),
        get_settings(),
        [1],
        tmp_path,
        _stats(),
        dry_run=True,
        emit=lambda e, p, c: emitted.append((e, p, c)),
    )

    assert isinstance(result, OrchestrationResult)
    assert result.leads_l1 is not None
    assert len(result.leads_l1) == 6  # min(10, volume.cible)
    assert result.nb_leads_finaux == 6
    assert result.leads_finaux is result.leads_l1
    # Le CSV de l'étage 1 a bien été produit (parité avec la CLI).
    assert (tmp_path / "etage1_decouverte.csv").exists()
    # Sources RGPD tracées.
    assert any("Google Places" in s for s in result.sources_rgpd)


def test_executer_pipeline_emet_progression_bornee(tmp_path):
    emitted: list[tuple] = []
    executer_pipeline(
        _cfg(volume=4),
        get_settings(),
        [1],
        tmp_path,
        _stats(),
        dry_run=True,
        emit=lambda e, p, c: emitted.append((e, p, c)),
    )
    assert emitted, "au moins une émission attendue"
    assert all(0 <= p <= 100 for _, p, _ in emitted)
    etape, progress, counts = emitted[-1]
    assert progress == 20
    assert counts["decouverte"] == 4


def test_executer_pipeline_sans_stage_rend_vide(tmp_path):
    result = executer_pipeline(
        _cfg(), get_settings(), [], tmp_path, _stats(), dry_run=True
    )
    assert result.nb_leads_finaux == 0
    assert result.leads_finaux == []
    assert result.sources_rgpd == []


def test_executer_pipeline_emit_optionnel(tmp_path):
    """Sans callback emit, l'orchestrateur fonctionne (chemin CLI)."""
    result = executer_pipeline(
        _cfg(volume=3), get_settings(), [1], tmp_path, _stats(), dry_run=True
    )
    assert result.leads_l1 is not None and len(result.leads_l1) == 3
