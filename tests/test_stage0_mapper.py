"""Tests du mapper SIRENE → LeadStage2 (étage 0)."""

from __future__ import annotations

from typing import Any

from renoboost_leads.stage0_sirene_first.mapper import (
    _derniere_annee_finances,
    _premier_dirigeant_physique,
    entreprise_to_lead_stage2,
)


def _entreprise_complete() -> dict[str, Any]:
    """Échantillon réaliste calqué sur la réponse réelle de l'API."""
    return {
        "siren": "402222222",
        "nom_complet": "BONDUELLE FRESH SAS",
        "nom_raison_sociale": "BONDUELLE FRESH",
        "nature_juridique": "5710",
        "activite_principale": "10.39A",
        "tranche_effectif_salarie": "12",
        "categorie_entreprise": "PME",
        "etat_administratif": "A",
        "date_creation": "1947-01-01",
        "nombre_etablissements": 3,
        "siege": {
            "siret": "40222222200015",
            "adresse": "296 RUE CHARLES SAINT-VENANT 59650 VILLENEUVE-D'ASCQ",
            "geo_adresse": "296 Rue Charles Saint-Venant 59650 Villeneuve-d'Ascq",
            "code_postal": "59650",
            "commune": "59009",
            "libelle_commune": "Villeneuve-d'Ascq",
            "departement": "59",
            "latitude": 50.6195,
            "longitude": 3.1352,
            "activite_principale": "10.39A",
        },
        "finances": {
            "2023": {"ca": 2_500_000, "resultat_net": 180_000},
            "2022": {"ca": 2_100_000, "resultat_net": 150_000},
        },
        "dirigeants": [
            {
                "type_dirigeant": "personne morale",
                "denomination": "HOLDING SAS",
                "qualite": "Président",
            },
            {
                "type_dirigeant": "personne physique",
                "nom": "Dupont",
                "prenom": "Marie",
                "qualite": "Gérante",
            },
        ],
    }


class TestMappingComplet:
    def test_lead_avec_tous_les_champs(self):
        lead = entreprise_to_lead_stage2(_entreprise_complete())
        assert lead is not None
        assert lead.siren == "402222222"
        assert lead.place_id == "sirene:402222222"
        assert lead.nom == "BONDUELLE FRESH SAS"
        assert lead.siret == "40222222200015"
        assert lead.code_naf == "10.39A"
        assert lead.tranche_effectif == "12"
        assert lead.categorie_entreprise == "PME"
        assert lead.statut_actif is True
        assert lead.statut_business == "OPERATIONAL"
        assert lead.code_postal == "59650"
        assert lead.ville == "Villeneuve-d'Ascq"
        assert lead.pays == "France"
        assert lead.latitude == 50.6195
        assert lead.longitude == 3.1352
        assert lead.nb_etablissements == 3
        assert lead.date_creation == "1947-01-01"
        assert lead.forme_juridique == "5710"
        # Dernière année finances (2023, pas 2022)
        assert lead.chiffre_affaires == 2_500_000
        assert lead.resultat_net == 180_000
        assert lead.annee_finances == "2023"
        # Premier dirigeant personne physique (pas la holding)
        assert lead.dirigeant_nom == "Dupont"
        assert lead.dirigeant_prenom == "Marie"
        assert lead.dirigeant_qualite == "Gérante"
        # Métadonnées de matching SIRENE-first
        assert lead.score_matching == 100.0
        assert lead.match_incertain is False
        assert lead.hors_filtre_entreprise is False

    def test_secteur_et_requete_passes(self):
        lead = entreprise_to_lead_stage2(
            _entreprise_complete(),
            secteur_recherche="pme_transport",
            requete_origine="dpt=59,62",
        )
        assert lead is not None
        assert lead.secteur_recherche == "pme_transport"
        assert lead.requete_origine == "dpt=59,62"


class TestMappingMinimal:
    def test_siren_manquant_renvoie_none(self):
        e = _entreprise_complete()
        del e["siren"]
        assert entreprise_to_lead_stage2(e) is None

    def test_nom_manquant_renvoie_none(self):
        e = _entreprise_complete()
        del e["nom_complet"]
        del e["nom_raison_sociale"]
        assert entreprise_to_lead_stage2(e) is None

    def test_fallback_nom_raison_sociale(self):
        e = _entreprise_complete()
        del e["nom_complet"]
        lead = entreprise_to_lead_stage2(e)
        assert lead is not None
        assert lead.nom == "BONDUELLE FRESH"

    def test_pas_de_finances(self):
        e = _entreprise_complete()
        e["finances"] = {}
        lead = entreprise_to_lead_stage2(e)
        assert lead is not None
        assert lead.chiffre_affaires is None
        assert lead.resultat_net is None
        assert lead.annee_finances is None

    def test_pas_de_dirigeants(self):
        e = _entreprise_complete()
        e["dirigeants"] = []
        lead = entreprise_to_lead_stage2(e)
        assert lead is not None
        assert lead.dirigeant_nom is None
        assert lead.dirigeant_prenom is None

    def test_etat_cesse_marque_statut_closed(self):
        e = _entreprise_complete()
        e["etat_administratif"] = "C"
        lead = entreprise_to_lead_stage2(e)
        assert lead is not None
        assert lead.statut_business == "CLOSED"
        assert lead.statut_actif is False

    def test_coordonnees_invalides_none(self):
        e = _entreprise_complete()
        e["siege"]["latitude"] = "pas_un_nombre"
        e["siege"]["longitude"] = None
        lead = entreprise_to_lead_stage2(e)
        assert lead is not None
        assert lead.latitude is None
        assert lead.longitude is None


class TestHelpers:
    def test_derniere_annee_finances_prend_la_plus_recente(self):
        annee, fin = _derniere_annee_finances(
            {"2020": {"ca": 100}, "2023": {"ca": 999}, "2021": {"ca": 200}}
        )
        assert annee == "2023"
        assert fin["ca"] == 999

    def test_derniere_annee_finances_vide(self):
        assert _derniere_annee_finances({}) == (None, {})
        assert _derniere_annee_finances(None) == (None, {})  # type: ignore[arg-type]

    def test_premier_dirigeant_physique_ignore_personne_morale(self):
        dirigeants = [
            {"type_dirigeant": "personne morale", "denomination": "HOLDING"},
            {"type_dirigeant": "personne physique", "nom": "Martin", "prenom": "Paul"},
        ]
        d = _premier_dirigeant_physique(dirigeants)
        assert d is not None
        assert d["nom"] == "Martin"

    def test_premier_dirigeant_physique_detecte_par_nom_prenom(self):
        # type_dirigeant absent → on prend si nom+prenom présents
        dirigeants = [
            {"qualite": "Président"},  # ni nom ni prenom
            {"nom": "Durand", "prenom": "Sophie"},
        ]
        d = _premier_dirigeant_physique(dirigeants)
        assert d is not None
        assert d["nom"] == "Durand"

    def test_premier_dirigeant_physique_aucun(self):
        assert _premier_dirigeant_physique([]) is None
        assert _premier_dirigeant_physique([{"qualite": "Président"}]) is None
