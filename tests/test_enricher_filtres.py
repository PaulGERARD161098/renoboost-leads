"""Tests Bloc 3 (intégration) — enricher + mapper avec filtres entreprise."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from renoboost_leads.exporter import export_stage3_csv_separe_hors_filtre
from renoboost_leads.models import FiltresEntreprise, LeadStage1, LeadStage3
from renoboost_leads.stage2_entreprises.enricher import EnricheurStage2
from renoboost_leads.stage2_entreprises.mapper import (
    _extraire_finances,
    _extraire_nb_etablissements,
    candidat_to_l2_fields,
)

# ─────────────────────────────────────────────────────────────────────────────
# Mapper : extraction nb_etablissements
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractionNbEtablissements:
    def test_champ_entier_officiel(self):
        assert _extraire_nb_etablissements({"nombre_etablissements": 5}) == 5

    def test_champ_string_numerique(self):
        assert _extraire_nb_etablissements({"nombre_etablissements": "3"}) == 3

    def test_absence_retourne_none(self):
        assert _extraire_nb_etablissements({}) is None

    def test_fallback_matching_etablissements_list(self):
        d = {"matching_etablissements": [{"siret": "a"}, {"siret": "b"}]}
        assert _extraire_nb_etablissements(d) == 2

    def test_champ_string_non_numerique_ignore(self):
        assert _extraire_nb_etablissements({"nombre_etablissements": "n/a"}) is None

    def test_candidat_to_l2_fields_inclut_nb_etablissements(self):
        candidat = {
            "siren": "123456789",
            "nature_juridique": "5710",
            "nombre_etablissements": 3,
            "siege": {},
        }
        fields = candidat_to_l2_fields(candidat)
        assert fields["nb_etablissements"] == 3


class TestExtractionFinances:
    def test_annee_la_plus_recente_choisie(self):
        finances = {
            "2022": {"ca": 100, "resultat_net": 10},
            "2024": {"ca": 300, "resultat_net": 30},
            "2023": {"ca": 200, "resultat_net": 20},
        }
        ca, res, annee = _extraire_finances({"finances": finances})
        assert (ca, res, annee) == (300, 30, "2024")

    def test_finances_absentes_retourne_none(self):
        assert _extraire_finances({}) == (None, None, None)

    def test_finances_vides_retourne_none(self):
        assert _extraire_finances({"finances": {}}) == (None, None, None)

    def test_floats_convertis_en_int(self):
        ca, res, _ = _extraire_finances({"finances": {"2024": {"ca": 1278355060.0}}})
        assert ca == 1278355060
        assert res is None

    def test_candidat_to_l2_fields_inclut_finances_et_categorie(self):
        candidat = {
            "siren": "123456789",
            "siege": {},
            "categorie_entreprise": "ETI",
            "finances": {"2024": {"ca": 5_000_000, "resultat_net": 250_000}},
        }
        fields = candidat_to_l2_fields(candidat)
        assert fields["chiffre_affaires"] == 5_000_000
        assert fields["resultat_net"] == 250_000
        assert fields["annee_finances"] == "2024"
        assert fields["categorie_entreprise"] == "ETI"


# ─────────────────────────────────────────────────────────────────────────────
# Enricher : application des filtres après enrichissement
# ─────────────────────────────────────────────────────────────────────────────


class _FakeRechercheClient:
    """Stub minimal du client API recherche-entreprises."""

    def __init__(self, candidats_par_query: dict[str, list[dict]] | None = None):
        self.candidats_par_query = candidats_par_query or {}

    def rechercher(self, query: str, code_postal: str | None = None, per_page: int = 10):
        return self.candidats_par_query.get(query, [])


class _RaisingRechercheClient:
    """Stub qui simule une panne API (5xx) après épuisement des retries."""

    def __init__(self):
        self.calls = 0

    def rechercher(self, query: str, code_postal: str | None = None, per_page: int = 10):
        self.calls += 1
        raise RuntimeError("HTTP 503 (panne simulée)")


def _lead_l1(nom: str, cp: str = "59000") -> LeadStage1:
    return LeadStage1(
        place_id=f"ChIJ_{nom}",
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        code_postal=cp,
        ville="Lille",
    )


class _CountingRechercheClient:
    """Stub qui répond par query exacte et compte les appels (test fallback D5)."""

    def __init__(self, par_query: dict[str, list[dict]]):
        self.par_query = par_query
        self.queries: list[str] = []

    def rechercher(self, query: str, code_postal: str | None = None, per_page: int = 10):
        self.queries.append(query)
        return self.par_query.get(query, [])


class TestNettoyageNomRecherche:
    """D5 : nettoyage du nom pour la recherche de repli."""

    def test_coupe_qualificatif_site(self):
        from renoboost_leads.stage2_entreprises.enricher import nettoyer_nom_pour_recherche

        got = nettoyer_nom_pour_recherche("Chaussures Maniet - Siège social")
        assert got == "Chaussures Maniet"

    def test_preserve_trait_union_colle(self):
        from renoboost_leads.stage2_entreprises.enricher import nettoyer_nom_pour_recherche

        # Pas d'espaces autour du tiret → on ne coupe pas
        assert nettoyer_nom_pour_recherche("Saint-Gobain") == "Saint-Gobain"

    def test_retire_parentheses_et_france(self):
        from renoboost_leads.stage2_entreprises.enricher import nettoyer_nom_pour_recherche

        got = nettoyer_nom_pour_recherche("Auchan Logistique (Plateforme) France")
        assert got == "Auchan Logistique"


class TestFallbackRechercheSIREN:
    """D5 : fallback additif quand la requête primaire est vide."""

    def test_fallback_declenche_si_primaire_vide(self):
        candidat = {"siren": "123456789", "siege": {}}
        # La requête primaire (nom + ville) ne renvoie rien ; le nom nettoyé oui.
        client = _CountingRechercheClient({"Daunat Nord": [candidat]})
        enr = EnricheurStage2(client=client)
        enr.enrichir([_lead_l1("Daunat Nord")])  # _lead_l1 ajoute ville="Lille"
        assert client.queries[0] == "Daunat Nord Lille"  # primaire (vide)
        assert client.queries[1] == "Daunat Nord"  # fallback (trouve)

    def test_pas_de_fallback_si_primaire_trouve(self):
        candidat = {"siren": "123456789", "siege": {}}
        client = _CountingRechercheClient({"Daunat Nord Lille": [candidat]})
        enr = EnricheurStage2(client=client)
        enr.enrichir([_lead_l1("Daunat Nord")])
        assert client.queries == ["Daunat Nord Lille"]  # un seul appel


class TestEnricherCacheEchecAPI:
    """D1 : un échec API ne doit jamais être mis en cache."""

    def test_echec_api_non_cache_et_reinterroge(self, tmp_path):
        from renoboost_leads.common.cache import SessionCache

        cache = SessionCache(tmp_path / "cache.sqlite")
        client = _RaisingRechercheClient()
        enr = EnricheurStage2(client=client, cache=cache)

        enr.enrichir([_lead_l1("Bonduelle")])
        assert client.calls == 1
        # L'échec n'a PAS été mémorisé
        assert cache.get_place(place_id="bonduelle|59000", stage="stage2_search") is None
        # Une relance ré-interroge l'API (pas de hit vide obsolète)
        enr.enrichir([_lead_l1("Bonduelle")])
        assert client.calls == 2

    def test_succes_vide_est_cache(self, tmp_path):
        from renoboost_leads.common.cache import SessionCache

        cache = SessionCache(tmp_path / "cache.sqlite")
        client = _FakeRechercheClient({})  # renvoie [] = succès sans résultat
        enr = EnricheurStage2(client=client, cache=cache)

        enr.enrichir([_lead_l1("Inconnu")])
        # Une réponse vide LÉGITIME (200, aucun match) est bien cachée
        assert cache.get_place(place_id="inconnu|59000", stage="stage2_search") is not None


class TestEnricherAvecFiltres:
    def test_lead_qualifie_pas_de_flag(self):
        candidat = {
            "siren": "402222222",
            "nom_complet": "SMI INDUSTRIE SAS",
            "nature_juridique": "5710",  # SAS
            "etat_administratif": "A",
            "tranche_effectif_salarie": "22",  # 100-199
            "activite_principale": "25.62A",
            "nombre_etablissements": 3,
            "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
        }
        client = _FakeRechercheClient({"SMI Industrie Lille": [candidat]})
        filtres = FiltresEntreprise(
            effectif_min=50,
            naf_inclus=["25"],
            forme_juridique_inclus=["SAS"],
        )
        enr = EnricheurStage2(client=client, filtres_entreprise=filtres)
        leads_l2 = enr.enrichir([_lead_l1("SMI Industrie")])

        assert len(leads_l2) == 1
        lead = leads_l2[0]
        assert lead.hors_filtre_entreprise is False
        assert lead.raison_hors_filtre is None
        assert lead.nb_etablissements == 3

    def test_lead_hors_filtre_effectif_flag_avec_raison(self):
        candidat = {
            "siren": "402222222",
            "nom_complet": "PETITE BOITE SARL",
            "nature_juridique": "5499",  # SARL
            "etat_administratif": "A",
            "tranche_effectif_salarie": "11",  # 10-19 → trop petit
            "activite_principale": "25.62A",
            "nombre_etablissements": 1,
            "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
        }
        client = _FakeRechercheClient({"Petite Boite Lille": [candidat]})
        filtres = FiltresEntreprise(effectif_min=50)
        enr = EnricheurStage2(client=client, filtres_entreprise=filtres)
        leads_l2 = enr.enrichir([_lead_l1("Petite Boite")])

        lead = leads_l2[0]
        assert lead.hors_filtre_entreprise is True
        assert lead.raison_hors_filtre is not None
        assert "effectif" in lead.raison_hors_filtre

    def test_aucun_filtre_aucun_flag(self):
        """Backwards compat : filtres_entreprise vide → aucun flag posé."""
        candidat = {
            "siren": "402222222",
            "nom_complet": "RANDOM SARL",
            "nature_juridique": "5499",
            "etat_administratif": "A",
            "tranche_effectif_salarie": "01",
            "activite_principale": "56.10A",
            "nombre_etablissements": 1,
            "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
        }
        client = _FakeRechercheClient({"Random Lille": [candidat]})
        enr = EnricheurStage2(client=client)  # pas de filtres
        leads_l2 = enr.enrichir([_lead_l1("Random")])

        assert leads_l2[0].hors_filtre_entreprise is False

    def test_lead_sans_match_api_flag_si_filtres_actifs(self):
        """Lead pour lequel l'API ne renvoie rien : pas de SIREN, donc les
        filtres qui exigent des données entreprise déclenchent le flag.

        On active `rejeter_effectif_inconnu` car par défaut un effectif inconnu
        n'évince plus (établissements secondaires Sirene sans tranche)."""
        client = _FakeRechercheClient({})  # aucun candidat
        filtres = FiltresEntreprise(effectif_min=50, rejeter_effectif_inconnu=True)
        enr = EnricheurStage2(client=client, filtres_entreprise=filtres)
        leads_l2 = enr.enrichir([_lead_l1("Inconnue")])

        lead = leads_l2[0]
        assert lead.siren is None
        assert lead.hors_filtre_entreprise is True
        assert "inconnu" in (lead.raison_hors_filtre or "")


# ─────────────────────────────────────────────────────────────────────────────
# Export L3 séparé qualifiés / hors-filtre
# ─────────────────────────────────────────────────────────────────────────────


def _lead_l3(nom: str, hors_filtre: bool = False) -> LeadStage3:
    return LeadStage3(
        place_id=f"ChIJ_{nom}",
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        hors_filtre_entreprise=hors_filtre,
        raison_hors_filtre="naf=56.10A pas dans [25]" if hors_filtre else None,
    )


class TestExportSepareL3:
    def test_pas_de_hors_filtre_un_seul_csv(self, tmp_path: Path):
        leads = [_lead_l3("A"), _lead_l3("B")]
        p_main, p_hf = export_stage3_csv_separe_hors_filtre(leads, tmp_path / "etage3_contacts.csv")
        assert p_main.exists()
        assert p_hf is None
        contenu = p_main.read_text(encoding="utf-8-sig")
        assert "A" in contenu and "B" in contenu

    def test_mix_split_en_deux_csv(self, tmp_path: Path):
        leads = [
            _lead_l3("Qualif1"),
            _lead_l3("HorsFiltre1", hors_filtre=True),
            _lead_l3("Qualif2"),
            _lead_l3("HorsFiltre2", hors_filtre=True),
        ]
        p_main, p_hf = export_stage3_csv_separe_hors_filtre(leads, tmp_path / "etage3_contacts.csv")
        assert p_main.exists() and p_hf is not None and p_hf.exists()

        main_content = p_main.read_text(encoding="utf-8-sig")
        hf_content = p_hf.read_text(encoding="utf-8-sig")

        assert "Qualif1" in main_content and "Qualif2" in main_content
        assert "HorsFiltre1" not in main_content and "HorsFiltre2" not in main_content
        assert "HorsFiltre1" in hf_content and "HorsFiltre2" in hf_content
        assert "Qualif1" not in hf_content
        assert p_hf.name == "etage3_contacts_hors_filtre.csv"

    def test_que_des_hors_filtre(self, tmp_path: Path):
        leads = [_lead_l3("HF1", hors_filtre=True), _lead_l3("HF2", hors_filtre=True)]
        p_main, p_hf = export_stage3_csv_separe_hors_filtre(leads, tmp_path / "etage3_contacts.csv")
        # Le main CSV est créé même vide (header seul) pour cohérence
        assert p_main.exists()
        assert p_hf is not None and p_hf.exists()
        main_content = p_main.read_text(encoding="utf-8-sig")
        # Headers présents, mais aucune ligne de données
        assert "HF1" not in main_content and "HF2" not in main_content


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip : lire_stage2_csv préserve les nouvelles colonnes
# ─────────────────────────────────────────────────────────────────────────────


class TestRoundTripCSVStage2:
    @pytest.fixture
    def lead_l2_avec_flags(self):
        from renoboost_leads.models import LeadStage2

        return LeadStage2(
            place_id="ChIJ_x",
            extraction_date=datetime.now(timezone.utc),
            nom="Test",
            code_postal="59000",
            siren="402222222",
            code_naf="56.10A",
            forme_juridique="1000",
            tranche_effectif="01",
            nb_etablissements=2,
            chiffre_affaires=5_000_000,
            resultat_net=250_000,
            annee_finances="2024",
            categorie_entreprise="ETI",
            hors_filtre_entreprise=True,
            raison_hors_filtre="naf=56.10A pas dans [25]",
        )

    def test_export_puis_lecture_preserve_les_nouvelles_colonnes(
        self, tmp_path: Path, lead_l2_avec_flags
    ):
        from renoboost_leads.exporter import export_stage2_csv, lire_stage2_csv

        csv_path = tmp_path / "etage2_entreprises.csv"
        export_stage2_csv([lead_l2_avec_flags], csv_path)
        leads = lire_stage2_csv(csv_path)
        assert len(leads) == 1
        lead = leads[0]
        assert lead.nb_etablissements == 2
        assert lead.chiffre_affaires == 5_000_000
        assert lead.resultat_net == 250_000
        assert lead.annee_finances == "2024"
        assert lead.categorie_entreprise == "ETI"
        assert lead.hors_filtre_entreprise is True
        assert lead.raison_hors_filtre == "naf=56.10A pas dans [25]"
