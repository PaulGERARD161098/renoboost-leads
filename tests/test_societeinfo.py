"""Tests client + enricher Societeinfo (dry-run + parsing + ciblage)."""

from __future__ import annotations

from renoboost_leads.models import LeadStage2
from renoboost_leads.societeinfo_enrichment.client import (
    ResultatSocieteinfo,
    SocieteinfoClient,
    SocieteinfoClientDryRun,
)
from renoboost_leads.societeinfo_enrichment.enricher import EnricheurSocieteinfo


def _lead(nom="Acme", siren=None, match_incertain=False, hors_filtre=False, **kw):
    from datetime import datetime, timezone

    return LeadStage2(
        place_id=f"p_{nom}",
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        siren=siren,
        match_incertain=match_incertain,
        hors_filtre_entreprise=hors_filtre,
        **kw,
    )


class TestClientDryRun:
    def test_renvoie_donnees_simulees(self):
        client = SocieteinfoClientDryRun()
        res = client.enrichir(nom="Rossini Energy", code_postal="75001")
        assert res.trouve is True
        assert res.naf == "42.99Z"
        assert res.email and res.email.startswith("contact@")

    def test_lead_vide_non_trouve(self):
        res = SocieteinfoClientDryRun().enrichir()
        assert res.trouve is False

    def test_health_check_ok(self):
        ok, _ = SocieteinfoClientDryRun().health_check()
        assert ok is True


class TestParseResultat:
    def test_mappe_bloc_result(self):
        data = {
            "result": {
                "siren": "552100554",
                "naf": "35.11Z",
                "naf_label": "Production d'électricité",
                "effectif": 1000,
                "turnover": "60000000",
                "manager": "Jean Dupont",
                "emails": ["a@edf.fr", "b@edf.fr"],
                "phone": "+33147654321",
                "website": "edf.fr",
            }
        }
        res = SocieteinfoClient._parse_resultat(data)
        assert res.trouve is True
        assert res.siren == "552100554"
        assert res.libelle_naf == "Production d'électricité"
        assert res.effectif == "1000"
        assert res.chiffre_affaires == 60000000
        assert res.email == "a@edf.fr"
        assert res.emails == ["a@edf.fr", "b@edf.fr"]

    def test_liste_results(self):
        res = SocieteinfoClient._parse_resultat({"results": [{"siren": "123456789"}]})
        assert res.siren == "123456789"

    def test_reponse_vide(self):
        res = SocieteinfoClient._parse_resultat({})
        assert res.trouve is False


class TestEnricheur:
    def test_only_incertain_cible_siren_manquant(self):
        leads = [
            _lead(nom="AvecSiren", siren="402111111"),  # ignoré (a un SIREN sûr)
            _lead(nom="SansSiren", siren=None),  # ciblé
            _lead(nom="Incertain", siren="402111111", match_incertain=True),  # ciblé
        ]
        enr = EnricheurSocieteinfo(SocieteinfoClientDryRun(), only_incertain=True)
        out = enr.enrichir(leads)
        assert enr.nb_enrichis == 2
        avec = next(o for o in out if o.nom == "AvecSiren")
        assert avec.enrichi_societeinfo is False

    def test_mode_all_enrichit_tout(self):
        leads = [_lead(nom="A", siren="402111111"), _lead(nom="B", siren="402111112")]
        enr = EnricheurSocieteinfo(SocieteinfoClientDryRun(), only_incertain=False)
        enr.enrichir(leads)
        assert enr.nb_enrichis == 2

    def test_hors_filtre_jamais_enrichi(self):
        leads = [_lead(nom="HF", siren=None, hors_filtre=True)]
        enr = EnricheurSocieteinfo(SocieteinfoClientDryRun(), only_incertain=True)
        enr.enrichir(leads)
        assert enr.nb_enrichis == 0

    def test_comble_siren_manquant(self):
        leads = [_lead(nom="SansSiren", siren=None)]
        out = EnricheurSocieteinfo(SocieteinfoClientDryRun()).enrichir(leads)
        # Le dry-run renvoie "000000000" → comble le SIREN vide du lead
        assert out[0].siren == "000000000"
        assert out[0].societeinfo_siren == "000000000"

    def test_flag_not_drop_preserve_tout(self):
        leads = [_lead(nom=f"L{i}", siren="402111111") for i in range(5)]
        out = EnricheurSocieteinfo(SocieteinfoClientDryRun()).enrichir(leads)
        assert len(out) == 5

    def test_erreur_client_capturee(self):
        class _Boom(SocieteinfoClientDryRun):
            def enrichir(self, **kw):  # noqa: ARG002
                raise RuntimeError("API down")

        leads = [_lead(nom="X", siren=None)]
        out = EnricheurSocieteinfo(_Boom()).enrichir(leads)
        assert out[0].enrichi_societeinfo is True
        assert out[0].societeinfo_erreur == "API down"

    def test_resultat_dataclass_defaut(self):
        r = ResultatSocieteinfo()
        assert r.trouve is False
        assert r.siren is None
