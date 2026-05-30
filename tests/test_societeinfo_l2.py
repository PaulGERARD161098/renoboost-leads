"""Tests porte d — Societeinfo comme provider L2 alternatif."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.models import LeadStage1
from renoboost_leads.societeinfo_enrichment.client import (
    ResultatSocieteinfo,
    SocieteinfoClientDryRun,
)
from renoboost_leads.stage2_entreprises.enricher import EnricheurStage2
from renoboost_leads.stage2_entreprises.mapper import candidat_to_l2_fields
from renoboost_leads.stage2_entreprises.societeinfo_l2_client import (
    SocieteinfoL2Client,
    societeinfo_resultat_to_candidat,
)


class TestMapperCandidat:
    def test_forme_candidat_compatible_datagouv(self):
        res = ResultatSocieteinfo(
            siren="552100554",
            naf="35.11Z",
            libelle_naf="Production d'électricité",
            effectif="1000 et plus",
            chiffre_affaires=60_000_000,
            dirigeant="Jean Dupont",
            trouve=True,
        )
        cand = societeinfo_resultat_to_candidat(res, nom="EDF", code_postal="75008")
        # Format attendu par le matcher
        assert cand["nom_complet"] == "EDF"
        assert cand["siege"]["code_postal"] == "75008"
        assert cand["etat_administratif"] == "A"
        # Extraction L2 standard
        l2 = candidat_to_l2_fields(cand)
        assert l2["siren"] == "552100554"
        assert l2["code_naf"] == "35.11Z"
        assert l2["dirigeant_nom"] == "Jean Dupont"
        assert l2["chiffre_affaires"] == 60_000_000


class TestClientL2:
    def test_rechercher_dry_run_renvoie_candidat(self):
        client = SocieteinfoL2Client(SocieteinfoClientDryRun())
        cands = client.rechercher("Rossini Energy", code_postal="75001")
        assert len(cands) == 1
        assert cands[0]["siren"]  # dry-run renvoie "000000000"
        assert cands[0]["_source_l2"] == "societeinfo"

    def test_rechercher_vide_si_non_trouve(self):
        client = SocieteinfoL2Client(SocieteinfoClientDryRun())
        assert client.rechercher("") == []  # query vide → SI ne trouve rien

    def test_health_check(self):
        ok, _ = SocieteinfoL2Client(SocieteinfoClientDryRun()).health_check()
        assert ok is True


class TestIntegrationEnricheur:
    def test_enricheur_l2_avec_provider_societeinfo(self):
        lead = LeadStage1(
            place_id="p1",
            extraction_date=datetime.now(timezone.utc),
            nom="Garage Bttn",
            code_postal="59000",
            ville="Lille",
        )
        enr = EnricheurStage2(client=SocieteinfoL2Client(SocieteinfoClientDryRun()))
        out = enr.enrichir([lead])
        assert len(out) == 1
        # Le provider Societeinfo (dry-run) a fourni un SIREN → match abouti.
        assert out[0].siren == "000000000"
