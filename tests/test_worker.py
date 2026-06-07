"""Tests du worker M3 — boucle de runs + DemoPipeline, sans réseau."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from worker.config import ConfigError, WorkerConfig
from worker.pipeline import DemoPipeline, RealPipeline, RunContext, build_pipeline
from worker.worker import Worker


class FakeDB:
    """Faux SupabaseRest en mémoire : reproduit le contrat utilisé par Worker."""

    def __init__(self, runs: list[dict[str, Any]], verticales: dict[str, dict[str, Any]]):
        self.runs = {r["id"]: dict(r) for r in runs}
        self.verticales = verticales
        self.leads: list[dict[str, Any]] = []
        self.progress_calls: list[tuple[str, int, dict[str, int]]] = []
        self.heartbeats: list[dict[str, Any]] = []
        self.requeue_calls: list[float] = []
        self.requeue_return = 0

    def requeue_stale_runs(self, older_than_s: float) -> int:
        self.requeue_calls.append(older_than_s)
        return self.requeue_return

    def heartbeat(
        self,
        *,
        mode: str,
        version: str | None = None,
        pending: int | None = None,
        last_error: str | None = None,
        keys: dict[str, bool] | None = None,
    ) -> None:
        self.heartbeats.append(
            {
                "mode": mode,
                "version": version,
                "pending": pending,
                "last_error": last_error,
                "keys": keys,
            }
        )

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
        self, run_id, *, status, counts, cout_eur, cout_detail=None, erreur=None
    ) -> None:
        self.runs[run_id].update(
            status=status,
            counts=counts,
            cout_eur=round(cout_eur, 2),
            cout_detail=cout_detail or {},
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


def test_demo_pipeline_ventile_cout_par_api():
    """Le coût démo est ventilé par poste et la somme reste = cout_eur."""
    ctx = RunContext(run=_make_run(volume=10), verticale=None)
    result = DemoPipeline(seed=42).run(ctx, lambda *a: None)
    assert set(result.cout_detail) == {"places", "pappers", "dropcontact", "claude"}
    assert all(v >= 0 for v in result.cout_detail.values())
    assert sum(result.cout_detail.values()) == pytest.approx(result.cout_eur)
    # Google Places domine le poste de coût (cohérent avec les ratios réels).
    assert result.cout_detail["places"] == max(result.cout_detail.values())


# --- Ventilation des coûts (cout_detail_depuis_stats) ------------------------


def test_cout_detail_depuis_stats_regroupe_par_api():
    from renoboost_leads.models import StageStats
    from worker.pipeline import cout_detail_depuis_stats

    def _s(nom: str, cout: float) -> StageStats:
        return StageStats(
            nom_etage=nom,
            duree_secondes=0.0,
            nb_appels_api=0,
            nb_succes=0,
            nb_echecs=0,
            cout_eur_estime=cout,
            leads_collectes=0,
        )

    etages = [
        _s("stage0_sirene_decouverte", 0.0),  # gratuit, ignoré
        _s("stage1_decouverte", 5.0),  # places
        _s("stage2_entreprises", 2.0),  # pappers
        _s("stage3_contacts", 0.0),  # gratuit, ignoré
        _s("stage3_5_enrichment", 3.0),  # dropcontact
        _s("completion", 0.5),  # claude
        _s("stage4_prospection", 1.5),  # claude
    ]
    detail = cout_detail_depuis_stats(etages)
    assert detail == {
        "places": 5.0,
        "pappers": 2.0,
        "dropcontact": 3.0,
        "claude": 2.0,
    }


def test_cout_detail_depuis_stats_vide():
    from worker.pipeline import cout_detail_depuis_stats

    assert cout_detail_depuis_stats([]) == {
        "places": 0.0,
        "pappers": 0.0,
        "dropcontact": 0.0,
        "claude": 0.0,
    }


def test_build_pipeline_real_returns_realpipeline():
    assert isinstance(build_pipeline("real"), RealPipeline)


def test_build_pipeline_unknown():
    with pytest.raises(ValueError):
        build_pipeline("???")


# --- RealPipeline (moteur mocké, zéro réseau) --------------------------------


class _FakeSettings:
    """Réglages factices : clés présentes par défaut, sans Dropcontact."""

    def __init__(self, google=True, anthropic=True, dropcontact=False):
        self._google, self._anthropic, self._dropcontact = google, anthropic, dropcontact

    def has_google_places(self):
        return self._google

    def has_anthropic(self):
        return self._anthropic

    def has_dropcontact(self):
        return self._dropcontact


def _lead4(**over):
    """Fabrique un LeadStage4 minimal pour tester le mapping."""
    from renoboost_leads.models import LeadStage4

    base = dict(
        place_id="p1",
        extraction_date=datetime.now(timezone.utc),
        nom="Acme SAS",
        ville="Lille",
        code_postal="59000",
        siren="123456789",
        code_naf="49.41A",
        libelle_naf="Transports routiers",
        libelle_effectif="20 à 49 salariés",
        dirigeant_prenom="Marie",
        dirigeant_nom="Durand",
        emails_verifies=["contact@acme.fr"],
        telephone="0102030405",
        site_web="https://acme.fr",
        score_interet=82,
        email_objet="Une idée pour Acme",
        email_corps="Bonjour Marie, ...",
        hors_filtre_entreprise=False,
    )
    base.update(over)
    return LeadStage4(**base)


def _real_ctx(vid="vid-1"):
    run = {
        "id": "run-abc",
        "verticale_id": vid,
        "zone": {"departement": "59", "effectif_min": 20},
        "volume_cible": 5,
        "budget_eur": 12.0,
    }
    return RunContext(
        run=run,
        verticale={"slug": "irve-flottes-b2b"},
        max_leads=500,
        max_budget_eur=50.0,
    )


def test_real_pipeline_maps_leads_and_emits(monkeypatch):
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    monkeypatch.delenv("WORKER_SCORE_HORS_FILTRE", raising=False)

    captured: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        captured["cfg"] = cfg
        captured["stages"] = stages
        stats.cout_total_eur = 1.23
        emit = kwargs.get("emit")
        if emit:
            emit("Rédaction des e-mails", 95, {"decouverte": 2, "qualifies": 2, "leads": 1})
        res = OrchestrationResult()
        res.leads_l1 = [_lead4(place_id="a"), _lead4(place_id="b")]
        res.leads_l2 = res.leads_l1
        res.leads_l4 = [_lead4()]
        res.nb_leads_finaux = 1
        return res

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)

    emitted: list[tuple] = []
    result = RealPipeline().run(_real_ctx(), lambda e, p, c: emitted.append((e, p, c)))

    # Mapping LeadStage4 → dict leads
    assert len(result.leads) == 1
    lead = result.leads[0]
    assert lead["entreprise"] == "Acme SAS"
    assert lead["siren"] == "123456789"
    assert lead["naf"] == "49.41A"
    assert lead["effectif"] == "20 à 49 salariés"
    assert lead["score"] == 82
    assert lead["contact_nom"] == "Marie Durand"
    assert lead["contact_email"] == "contact@acme.fr"
    assert lead["contact_tel"] == "0102030405"
    assert lead["mail_sujet"] == "Une idée pour Acme"
    assert lead["statut"] == "a_valider"
    assert lead["run_id"] == "run-abc"
    assert lead["verticale_id"] == "vid-1"

    # Coût + counts + progression
    assert result.cout_eur == pytest.approx(1.23)
    assert result.counts == {"decouverte": 2, "qualifies": 2, "leads": 1}
    assert emitted and emitted[-1][1] == 95

    # Ciblage : la verticale fichier a écrasé le placeholder + override effectif.
    assert len(captured["cfg"].secteurs) >= 1
    assert captured["cfg"].filtres_entreprise.effectif_min == 20
    assert captured["cfg"].volume.cible == 5
    assert captured["cfg"].budget.max_eur == 12.0
    assert 4 in captured["stages"]  # L4 toujours exécuté en real
    assert 3.5 not in captured["stages"]  # pas de clé Dropcontact

    # Mail L4 : signature au nom du client + offre câblée depuis la verticale.
    cfg = captured["cfg"]
    assert cfg.emetteur is not None
    assert cfg.emetteur.nom_entreprise == "Rossini Energy"
    assert cfg.claude_scoring.contexte_client
    assert "RénoBoost" not in cfg.claude_scoring.contexte_client
    # Économie par défaut : Claude ne score/rédige pas les leads hors-filtre.
    assert cfg.claude_scoring.scorer_hors_filtre is False


def _capture_stages(monkeypatch, slug: str) -> list[float]:
    """Lance RealPipeline pour `slug` et renvoie les stages demandés à l'orchestrateur."""
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    captured: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        captured["stages"] = stages
        return OrchestrationResult()

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)
    ctx = RunContext(
        run={"id": "r", "verticale_id": "v", "zone": {}, "volume_cible": 5},
        verticale={"slug": slug},
    )
    RealPipeline().run(ctx, lambda *a: None)
    return captured["stages"]  # type: ignore[return-value]


def test_real_pipeline_rossini_sirene_first(monkeypatch):
    """Verticale rossini (decouverte_sirene_first=true) → découverte SIRENE (stage 0)
    + Places en enrichissement (stage 1), pas de Places-first large."""
    stages = _capture_stages(monkeypatch, "rossini")
    assert 0 in stages  # découverte par NAF natif (gratuit)
    assert 1 in stages  # Places en simple enrichissement par nom


def test_real_pipeline_verticale_fichier_sans_flag_reste_places_first(monkeypatch):
    """Verticale fichier sans le flag → Places-first historique (pas de stage 0)."""
    stages = _capture_stages(monkeypatch, "irve-flottes-b2b")
    assert 0 not in stages
    assert 1 in stages


def test_real_pipeline_base_only_contexte_depuis_config(monkeypatch):
    """Verticale CRM base-only : contexte_client construit depuis le config (pas RénoBoost)."""
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    captured: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        captured["cfg"] = cfg
        return OrchestrationResult()

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)
    ctx = RunContext(
        run={"id": "r", "verticale_id": "v", "zone": {}, "volume_cible": 5},
        verticale={
            "slug": "cible-crm-x",
            "nom": "Cible CRM X",
            "config": {"secteurs_naf": ["43"], "offre": "Pose de bornes IRVE"},
        },
    )
    RealPipeline().run(ctx, lambda *a: None)
    ctx_client = captured["cfg"].claude_scoring.contexte_client
    assert ctx_client and "Pose de bornes IRVE" in ctx_client
    assert "RénoBoost" not in ctx_client


def test_real_pipeline_override_effectif_tranche(monkeypatch):
    """Zone CRM {effectif_min, effectif_max} → override la tranche (plafond PME)."""
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    captured: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        captured["cfg"] = cfg
        return OrchestrationResult()

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)
    ctx = RunContext(
        run={
            "id": "r",
            "verticale_id": "v",
            "zone": {"departement": "59", "effectif_min": 10, "effectif_max": 250},
            "volume_cible": 5,
        },
        verticale={"slug": "irve-flottes-b2b"},
    )
    RealPipeline().run(ctx, lambda *a: None)
    filtres = captured["cfg"].filtres_entreprise
    assert filtres.effectif_min == 10
    assert filtres.effectif_max == 250


def test_real_pipeline_score_hors_filtre_via_env(monkeypatch):
    """WORKER_SCORE_HORS_FILTRE=true → Claude score aussi les hors-filtre."""
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    monkeypatch.setenv("WORKER_SCORE_HORS_FILTRE", "true")
    captured: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        captured["cfg"] = cfg
        return OrchestrationResult()

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)
    ctx = RunContext(
        run={"id": "r", "verticale_id": "v", "zone": {}, "volume_cible": 5},
        verticale={"slug": "cible-crm-x", "nom": "Cible CRM X", "config": {"secteurs_naf": ["43"]}},
    )
    RealPipeline().run(ctx, lambda *a: None)
    assert captured["cfg"].claude_scoring.scorer_hors_filtre is True


def test_real_pipeline_email_dropcontact_prioritaire(monkeypatch):
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        res = OrchestrationResult()
        res.leads_l4 = [
            _lead4(
                email_dropcontact="dc@acme.fr",
                telephone_direct_dropcontact="0600000000",
                linkedin_dirigeant_dropcontact="https://www.linkedin.com/in/marie-durand",
                linkedin_entreprise_dropcontact="https://www.linkedin.com/company/acme",
            )
        ]
        return res

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)

    result = RealPipeline().run(_real_ctx(), lambda *a: None)
    assert result.leads[0]["contact_email"] == "dc@acme.fr"
    assert result.leads[0]["contact_tel"] == "0600000000"
    assert (
        result.leads[0]["contact_linkedin"]
        == "https://www.linkedin.com/in/marie-durand"
    )
    assert (
        result.leads[0]["entreprise_linkedin"]
        == "https://www.linkedin.com/company/acme"
    )


def test_real_pipeline_missing_key_raises(monkeypatch):
    import renoboost_leads.settings as settings_mod

    monkeypatch.setattr(
        settings_mod, "get_settings", lambda: _FakeSettings(google=False)
    )
    with pytest.raises(RuntimeError, match="GOOGLE_PLACES_API_KEY"):
        RealPipeline().run(_real_ctx(), lambda *a: None)


def test_real_pipeline_sans_verticale_raises(monkeypatch):
    import renoboost_leads.settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    ctx = RunContext(run={"id": "r", "zone": {}}, verticale=None)
    with pytest.raises(RuntimeError, match="verticale"):
        RealPipeline().run(ctx, lambda *a: None)


def test_real_pipeline_zone_point_gps(monkeypatch):
    """Mode point GPS (#38) : lat/lon dans la zone → Zone(type='point')."""
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())

    seen: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        seen["zone"] = cfg.zone
        return OrchestrationResult()

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)

    ctx = RunContext(
        run={
            "id": "r",
            "verticale_id": "v",
            "zone": {"latitude": 50.63, "longitude": 3.06, "rayon_par_point_km": 8},
            "volume_cible": 3,
        },
        verticale={"slug": "irve-flottes-b2b"},
    )
    RealPipeline().run(ctx, lambda *a: None)
    assert seen["zone"].type == "point"
    assert seen["zone"].latitude == pytest.approx(50.63)
    assert seen["zone"].rayon_par_point_km == pytest.approx(8.0)


def test_real_pipeline_verticale_base_only_sirene_first(monkeypatch):
    """Verticale CRM sans fichier repo : ciblage depuis config base + SIRENE-first."""
    import renoboost_leads.orchestrateur as orch
    import renoboost_leads.settings as settings_mod
    from renoboost_leads.orchestrateur import OrchestrationResult

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())

    captured: dict[str, object] = {}

    def fake_executer(cfg, settings, stages, output_dir, stats, **kwargs):
        captured["cfg"] = cfg
        captured["stages"] = stages
        return OrchestrationResult()

    monkeypatch.setattr(orch, "executer_pipeline", fake_executer)

    ctx = RunContext(
        run={
            "id": "r-db",
            "verticale_id": "v-db",
            "zone": {"departement": "59", "effectif_min": 15},
            "volume_cible": 8,
        },
        verticale={
            "slug": "ma-cible-crm-sans-fichier",
            "nom": "Cible CRM ad hoc",
            "config": {"secteurs_naf": ["41", "43.21A"], "effectif_min": 30},
        },
    )
    RealPipeline().run(ctx, lambda *a: None)

    cfg = captured["cfg"]
    # Découverte SIRENE-first (stage 0 présent, ciblage NAF depuis la base)
    assert 0 in captured["stages"]
    assert cfg.filtres_entreprise.naf_inclus == ["41", "43.21A"]
    # L'override effectif de la zone CRM prime sur le config verticale
    assert cfg.filtres_entreprise.effectif_min == 15
    assert cfg.run.description == "Cible CRM ad hoc"


def test_real_pipeline_base_only_sans_naf_raises(monkeypatch):
    """Verticale base-only sans NAF : refus explicite (sinon ciblage trop large)."""
    import renoboost_leads.settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _FakeSettings())
    ctx = RunContext(
        run={"id": "r", "verticale_id": "v", "zone": {}, "volume_cible": 3},
        verticale={"slug": "cible-vide", "config": {"secteurs_naf": []}},
    )
    with pytest.raises(RuntimeError, match="NAF"):
        RealPipeline().run(ctx, lambda *a: None)


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
    # L'échec remonte aussi au heartbeat (visible dans l'UI sans logs Railway).
    assert any("kaboom" in (h["last_error"] or "") for h in db.heartbeats)


def test_worker_heartbeat_each_poll_reports_mode_and_pending():
    run = _make_run(volume=4)
    db = FakeDB(runs=[run], verticales={})
    config = WorkerConfig(
        supabase_url="https://x.supabase.co", service_role_key="k", mode="demo", version="abc1234"
    )
    worker = Worker(config, db=db, pipeline=DemoPipeline(seed=1))

    worker.poll_once()

    # Premier heartbeat du tour : mode + version + nombre de runs en file.
    first = db.heartbeats[0]
    assert first["mode"] == "demo"
    assert first["version"] == "abc1234"
    assert first["pending"] == 1
    # Présence des clés rapportée (booléens, jamais les valeurs).
    assert set(first["keys"]) == {"google_places", "anthropic", "pappers", "dropcontact"}
    assert all(isinstance(v, bool) for v in first["keys"].values())


def test_worker_poll_reaps_stale_runs():
    db = FakeDB(runs=[], verticales={})
    db.requeue_return = 2
    config = WorkerConfig(
        supabase_url="https://x.supabase.co",
        service_role_key="k",
        mode="demo",
        stale_run_timeout_s=600,
    )
    worker = Worker(config, db=db, pipeline=DemoPipeline(seed=1))

    worker.poll_once()

    # Le reaper est invoqué à chaque poll, avec le seuil configuré.
    assert db.requeue_calls == [600]


def test_heartbeat_tick_writes_heartbeat():
    db = FakeDB(runs=[], verticales={})
    worker = Worker(_config(), db=db, pipeline=DemoPipeline(seed=1))

    worker.heartbeat_tick()

    assert len(db.heartbeats) == 1
    assert db.heartbeats[0]["mode"] == "demo"


def test_config_reads_version_from_railway_sha():
    cfg = WorkerConfig.from_env(
        {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "k",
            "RAILWAY_GIT_COMMIT_SHA": "0123456789abcdef",
        }
    )
    assert cfg.version == "0123456"  # tronqué à 7 caractères


def test_worker_test_run_forces_demo_pipeline():
    """Un run marqué is_test passe en mode démo, même si le pipeline configuré planterait."""
    vid = str(uuid.uuid4())
    run = _make_run(verticale_id=vid, volume=4)
    run["is_test"] = True
    db = FakeDB(runs=[run], verticales={vid: {"config": {"offre": "IRVE"}}})

    class Boom:
        def run(self, ctx, emit):
            raise RuntimeError("le pipeline réel ne doit pas tourner pour un run test")

    worker = Worker(_config(), db=db, pipeline=Boom(), demo_pipeline=DemoPipeline(seed=3))

    assert worker.poll_once() == 1
    assert db.runs[run["id"]]["status"] == "termine"
    assert len(db.leads) == 4


def test_worker_non_test_run_uses_configured_pipeline():
    """Sans is_test, c'est bien le pipeline configuré (ici réel mocké) qui tourne."""
    run = _make_run(volume=3)

    class Sentinel:
        def __init__(self):
            self.called = False

        def run(self, ctx, emit):
            self.called = True
            from worker.pipeline import RunResult

            return RunResult(leads=[], counts={}, cout_eur=0.0)

    sentinel = Sentinel()
    db = FakeDB(runs=[run], verticales={})
    worker = Worker(_config(), db=db, pipeline=sentinel, demo_pipeline=DemoPipeline(seed=1))

    worker.poll_once()
    assert sentinel.called is True


def test_worker_skips_already_claimed_run():
    run = _make_run(volume=2)
    run["status"] = "en_cours"  # déjà pris
    db = FakeDB(runs=[run], verticales={})
    worker = Worker(_config(), db=db, pipeline=DemoPipeline(seed=1))

    assert worker.poll_once() == 0
    assert db.leads == []
