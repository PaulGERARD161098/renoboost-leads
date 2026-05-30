"""Tests de l'étage de complétion (3.7) : détection trous, backfill, livrables."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.completion import (
    COLONNES_COMPLETION,
    EtageCompletion,
    SocieteinfoProvider,
    construire_provider_societeinfo,
    export_completion_csv,
    generer_annexe_completion,
)
from renoboost_leads.completion.models import LeadComplete
from renoboost_leads.models import LeadStage2, LeadStage4
from renoboost_leads.societeinfo_enrichment.client import SocieteinfoClientDryRun


def _lead(nom="Acme", siren=None, match_incertain=False, hors_filtre=False, **kw):
    return LeadStage2(
        place_id=f"p_{nom}",
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        siren=siren,
        match_incertain=match_incertain,
        hors_filtre_entreprise=hors_filtre,
        **kw,
    )


def _provider_dry() -> SocieteinfoProvider:
    return SocieteinfoProvider(SocieteinfoClientDryRun())


class TestDetectionTrous:
    def test_lead_nu_a_des_trous(self):
        manques = EtageCompletion.trous(_lead(siren=None))
        for champ in ("siren", "dirigeant_nom", "libelle_naf", "chiffre_affaires", "emails"):
            assert champ in manques

    def test_siren_incertain_compte_comme_trou(self):
        manques = EtageCompletion.trous(_lead(siren="402111111", match_incertain=True))
        assert "siren" in manques

    def test_lead_complet_sans_trou(self):
        lead = LeadComplete(
            place_id="p1",
            extraction_date=datetime.now(timezone.utc),
            nom="Plein",
            siren="402111111",
            dirigeant_nom="Dupont",
            libelle_naf="Construction",
            tranche_effectif="50 à 99 salariés",
            chiffre_affaires=1_000_000,
            telephone="+33100000000",
            emails_verifies=["a@plein.fr"],
        )
        assert EtageCompletion.trous(lead) == []


class TestBackfill:
    def test_comble_les_trous_et_trace_provenance(self):
        out = EtageCompletion(_provider_dry()).enrichir([_lead(nom="SansRien", siren=None)])
        lead = out[0]
        assert lead.complete is True
        assert lead.completion_provider == "societeinfo"
        # Le dry-run remplit SIREN, dirigeant, NAF, effectif, CA, emails, tel, site.
        for champ in ("siren", "dirigeant_nom", "libelle_naf", "chiffre_affaires", "emails"):
            assert champ in lead.completion_champs_remplis
        assert lead.siren == "000000000"
        assert lead.repeche is True

    def test_fill_if_empty_ne_reecrit_pas(self):
        lead = _lead(nom="DejaSiren", siren="402111111", match_incertain=True)
        out = EtageCompletion(_provider_dry()).enrichir([lead])
        # SIREN déjà présent → non réécrit, absent des champs comblés.
        assert out[0].siren == "402111111"
        assert "siren" not in out[0].completion_champs_remplis

    def test_only_gaps_ignore_lead_complet(self):
        lead = LeadComplete(
            place_id="p1",
            extraction_date=datetime.now(timezone.utc),
            nom="Plein",
            siren="402111111",
            dirigeant_nom="Dupont",
            libelle_naf="Construction",
            tranche_effectif="50 à 99 salariés",
            chiffre_affaires=1_000_000,
            telephone="+33100000000",
            emails_verifies=["a@plein.fr"],
        )
        etage = EtageCompletion(_provider_dry(), only_gaps=True)
        out = etage.enrichir([lead])
        assert etage.nb_appeles == 0
        assert out[0].complete is False

    def test_mode_tout_appelle_meme_sans_trou(self):
        lead = LeadComplete(
            place_id="p1",
            extraction_date=datetime.now(timezone.utc),
            nom="Plein",
            siren="402111111",
            dirigeant_nom="Dupont",
            libelle_naf="Construction",
            tranche_effectif="50 à 99 salariés",
            chiffre_affaires=1_000_000,
            telephone="+33100000000",
            emails_verifies=["a@plein.fr"],
        )
        etage = EtageCompletion(_provider_dry(), only_gaps=False)
        etage.enrichir([lead])
        assert etage.nb_appeles == 1

    def test_hors_filtre_jamais_appele(self):
        etage = EtageCompletion(_provider_dry())
        etage.enrichir([_lead(nom="HF", siren=None, hors_filtre=True)])
        assert etage.nb_appeles == 0

    def test_flag_not_drop(self):
        leads = [_lead(nom=f"L{i}", siren=None) for i in range(4)]
        out = EtageCompletion(_provider_dry()).enrichir(leads)
        assert len(out) == 4

    def test_erreur_provider_capturee(self):
        class _Boom(SocieteinfoClientDryRun):
            def enrichir(self, **kw):  # noqa: ARG002
                raise RuntimeError("provider down")

        out = EtageCompletion(SocieteinfoProvider(_Boom())).enrichir([_lead(siren=None)])
        assert out[0].complete is True
        assert out[0].completion_erreur == "provider down"
        assert out[0].completion_champs_remplis == []


class TestChainage:
    def test_lead_complete_passe_a_l4_en_conservant_les_champs_de_base(self):
        out = EtageCompletion(_provider_dry()).enrichir([_lead(siren=None)])
        lc = out[0]
        l4 = LeadStage4(**lc.model_dump())
        # Les champs repêchés (base) survivent à L4...
        assert l4.siren == lc.siren
        assert l4.dirigeant_nom == lc.dirigeant_nom
        # ...mais les métadonnées de complétion sont ignorées (extra="ignore").
        assert not hasattr(l4, "completion_provider")


class TestLivrables:
    def test_csv_contient_colonnes_completion(self, tmp_path):
        out = EtageCompletion(_provider_dry()).enrichir([_lead(siren=None)])
        path = export_completion_csv(out, tmp_path / "etage3_7_completion.csv")
        contenu = path.read_text(encoding="utf-8-sig")
        for col in ("completion_provider", "completion_champs_remplis", "cout_completion_eur"):
            assert col in contenu
        assert "completion_champs_remplis" in COLONNES_COMPLETION

    def test_annexe_markdown_liste_les_repeches(self, tmp_path):
        out = EtageCompletion(_provider_dry()).enrichir(
            [_lead(nom="ZoléParking", siren=None)]
        )
        path = generer_annexe_completion(out, tmp_path / "completion.md")
        md = path.read_text(encoding="utf-8")
        assert "Annexe complétion" in md
        assert "Leads repêchés" in md
        assert "ZoléParking" in md

    def test_annexe_sans_repeche(self, tmp_path):
        lead = LeadComplete(
            place_id="p1",
            extraction_date=datetime.now(timezone.utc),
            nom="Plein",
            siren="402111111",
            dirigeant_nom="Dupont",
            libelle_naf="Construction",
            tranche_effectif="50 à 99 salariés",
            chiffre_affaires=1_000_000,
            telephone="+33100000000",
            emails_verifies=["a@plein.fr"],
        )
        out = EtageCompletion(_provider_dry()).enrichir([lead])
        path = generer_annexe_completion(out, tmp_path / "completion.md")
        assert "Aucun champ comblé" in path.read_text(encoding="utf-8")


class TestProviderFactory:
    def test_dry_run_si_pas_de_cle(self):
        prov = construire_provider_societeinfo(api_key=None)
        assert isinstance(prov.client, SocieteinfoClientDryRun)
        assert prov.nom == "societeinfo"

    def test_dry_run_force(self):
        prov = construire_provider_societeinfo(api_key="secret", dry_run=True)
        assert isinstance(prov.client, SocieteinfoClientDryRun)
