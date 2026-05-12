"""Tests B5 — filtre géographique strict post-Places.

Garantit que les leads renvoyés par Places dont le code postal n'est pas
dans `zone.codes` du YAML sont rejetés avant d'entrer dans le pipeline.

Métropole uniquement (Corse 2A/2B incluse, DOM non gérés).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from renoboost_leads.models import LeadStage1, Zone
from renoboost_leads.stage1_decouverte.extractor import lead_dans_zone


def _lead(cp: str | None) -> LeadStage1:
    return LeadStage1(
        place_id="ChIJtest",
        extraction_date=datetime.now(timezone.utc),
        nom="Test",
        code_postal=cp,
    )


def _zone(codes: list[str]) -> Zone:
    return Zone(type="departement", codes=codes, rayon_par_point_km=10, pas_grille_km=15)


class TestLeadDansZoneDepartementStandard:
    def test_cp_dans_dept_cible_accepte(self):
        ok, _ = lead_dans_zone(_lead("59800"), _zone(["59"]))
        assert ok is True

    def test_cp_hors_dept_cible_rejete(self):
        # CP 60000 = Oise, zone visée 59 Nord
        ok, raison = lead_dans_zone(_lead("60000"), _zone(["59"]))
        assert ok is False
        assert "hors_zone" in raison or "60" in raison

    def test_cp_dans_un_des_codes_accepte(self):
        # zone multi-départements : 13 doit passer
        ok, _ = lead_dans_zone(_lead("13001"), _zone(["59", "13"]))
        assert ok is True

    def test_cp_paris_75(self):
        ok, _ = lead_dans_zone(_lead("75008"), _zone(["75"]))
        assert ok is True

    def test_cp_none_rejete(self):
        # Pas d'adresse → on ne peut pas vérifier → on rejette (safe)
        ok, _ = lead_dans_zone(_lead(None), _zone(["59"]))
        assert ok is False


class TestLeadDansZoneCorse:
    def test_cp_20000_dans_2a_accepte(self):
        # Ajaccio
        ok, _ = lead_dans_zone(_lead("20000"), _zone(["2A"]))
        assert ok is True

    def test_cp_20100_dans_2a_accepte(self):
        # Sartène
        ok, _ = lead_dans_zone(_lead("20100"), _zone(["2A"]))
        assert ok is True

    def test_cp_20200_pas_dans_2a(self):
        # Bastia = 2B, pas 2A
        ok, raison = lead_dans_zone(_lead("20200"), _zone(["2A"]))
        assert ok is False
        assert "hors_zone" in raison

    def test_cp_20200_dans_2b_accepte(self):
        ok, _ = lead_dans_zone(_lead("20200"), _zone(["2B"]))
        assert ok is True

    def test_cp_20600_dans_2b_accepte(self):
        # Bastia haut
        ok, _ = lead_dans_zone(_lead("20600"), _zone(["2B"]))
        assert ok is True


class TestLeadDansZoneCasLimites:
    def test_cp_invalide_4_chiffres_rejete(self):
        ok, _ = lead_dans_zone(_lead("5980"), _zone(["59"]))
        assert ok is False

    def test_cp_invalide_alpha_rejete(self):
        ok, _ = lead_dans_zone(_lead("ABCDE"), _zone(["59"]))
        assert ok is False

    @pytest.mark.parametrize(
        "cp_dept_attendu",
        [
            ("01000", "01"),  # Bourg-en-Bresse
            ("06000", "06"),  # Nice
            ("69001", "69"),  # Lyon
            ("13008", "13"),  # Marseille
            ("34000", "34"),  # Montpellier
            ("95000", "95"),  # Cergy
        ],
    )
    def test_correspondances_metropole(self, cp_dept_attendu):
        cp, dept = cp_dept_attendu
        ok, _ = lead_dans_zone(_lead(cp), _zone([dept]))
        assert ok is True, f"CP {cp} devrait être dans dpt {dept}"
