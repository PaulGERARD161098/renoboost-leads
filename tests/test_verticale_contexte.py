"""Tests du contexte_client construit depuis une verticale (offre + signature)."""

from __future__ import annotations

from renoboost_leads.verticale.contexte import contexte_client_depuis_verticale
from renoboost_leads.verticale.loader import load_verticale


class TestContexteRossini:
    def test_signature_client_et_offre(self):
        v = load_verticale("rossini")
        ctx = contexte_client_depuis_verticale(v)
        # Le client (émetteur) apparaît → signature au bon nom, pas RénoBoost.
        assert "Rossini Energy" in ctx
        assert "RénoBoost" not in ctx
        # L'offre réelle est câblée (ombrières + bornes).
        assert "mbrières" in ctx and "IRVE" in ctx
        # Mots-clés com' imposés.
        assert "Pilotage de la consommation" in ctx
        assert "avantages fiscaux" in ctx.lower()

    def test_pas_de_doublon_client(self):
        v = load_verticale("rossini")
        ctx = contexte_client_depuis_verticale(v)
        assert "Rossini Energy — Rossini Energy" not in ctx

    def test_inclut_icp_et_exclusions(self):
        v = load_verticale("rossini")
        ctx = contexte_client_depuis_verticale(v)
        assert "Profil idéal" in ctx


class TestEmetteurVerticales:
    def test_4_verticales_energie_signent_rossini(self):
        for slug in (
            "rossini",
            "solaire-pme-toitures",
            "ombrieres-parkings-grandes-surfaces",
            "irve-flottes-b2b",
        ):
            v = load_verticale(slug)
            assert v.emetteur is not None
            assert v.emetteur.nom_entreprise == "Rossini Energy"

    def test_clim_pro_sans_emetteur(self):
        assert load_verticale("clim-pro-b2b").emetteur is None
