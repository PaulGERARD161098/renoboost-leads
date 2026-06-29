"""Tests Phase C — résolution géoloc parking → SIREN exploitant."""

from __future__ import annotations

from typing import Any

from renoboost_leads.parkings_aper.matching_geo import (
    ligne_a_resoudre,
    resoudre_lignes_sans_enseigne,
    resoudre_siren_geo,
)
from renoboost_leads.parkings_aper.models import LigneParking


class _FakeClient:
    """Client near_point factice : renvoie une liste figée d'entreprises."""

    def __init__(self, candidats: list[dict[str, Any]]):
        self._candidats = candidats
        self.appels: list[dict[str, Any]] = []

    def decouvrir_near_point(self, latitude, longitude, radius_km, **kwargs):
        self.appels.append(
            {"lat": latitude, "long": longitude, "radius": radius_km, **kwargs}
        )
        yield from self._candidats


def _ligne_sans_enseigne() -> LigneParking:
    return LigneParking(surface_m2=12000.0, latitude=50.45, longitude=2.83)


class TestLigneAResoudre:
    def test_sans_identite_avec_coords(self):
        assert ligne_a_resoudre(_ligne_sans_enseigne()) is True

    def test_avec_nom_ignore(self):
        lg = LigneParking(surface_m2=12000.0, nom="Carrefour Lens",
                          latitude=50.45, longitude=2.83)
        assert ligne_a_resoudre(lg) is False

    def test_avec_siren_ignore(self):
        lg = LigneParking(surface_m2=12000.0, siren="552100554",
                          latitude=50.45, longitude=2.83)
        assert ligne_a_resoudre(lg) is False

    def test_sans_coords_ignore(self):
        lg = LigneParking(surface_m2=12000.0)
        assert ligne_a_resoudre(lg) is False


class TestResoudreSiren:
    def test_choisit_le_plus_gros_effectif(self):
        client = _FakeClient([
            {"siren": "111111111", "nom_complet": "Micro Boutique",
             "tranche_effectif_salarie": "03"},
            {"siren": "222222222", "nom_complet": "Hyper Anchor SAS",
             "tranche_effectif_salarie": "42"},
        ])
        siren, nom = resoudre_siren_geo(_ligne_sans_enseigne(), client)
        assert siren == "222222222"
        assert nom == "Hyper Anchor SAS"

    def test_aucun_candidat_renvoie_none(self):
        siren, nom = resoudre_siren_geo(_ligne_sans_enseigne(), _FakeClient([]))
        assert siren is None and nom is None

    def test_resolution_deterministe_independante_de_l_ordre(self):
        # Même jeu de candidats, ordres d'entrée différents → MÊME SIREN choisi.
        # (Avant : `max` suivait l'ordre API non garanti → flip run à run.)
        a = {"siren": "222222222", "nom_complet": "B SAS", "tranche_effectif_salarie": "42"}
        b = {"siren": "111111111", "nom_complet": "A SAS", "tranche_effectif_salarie": "42"}
        s1, _ = resoudre_siren_geo(_ligne_sans_enseigne(), _FakeClient([a, b]))
        s2, _ = resoudre_siren_geo(_ligne_sans_enseigne(), _FakeClient([b, a]))
        assert s1 == s2 == "111111111"  # effectif égal → SIREN croissant départage

    def test_effectif_tous_inconnus_laisse_non_resolu(self):
        # Plusieurs voisins sans effectif renseigné → pur hasard → on n'attribue
        # pas (mieux vaut un SIREN absent qu'un SIREN faux qui corrompt le NAF).
        client = _FakeClient([
            {"siren": "111111111", "nom_complet": "Voisin 1"},
            {"siren": "222222222", "nom_complet": "Voisin 2"},
        ])
        siren, nom = resoudre_siren_geo(_ligne_sans_enseigne(), client)
        assert siren is None and nom is None

    def test_candidat_unique_sans_effectif_reste_retenu(self):
        # Un seul candidat dans le rayon : pas d'ambiguïté → on le garde même
        # sans effectif (le garde-fou ne vise que les choix multiples hasardeux).
        client = _FakeClient([{"siren": "333333333", "nom_complet": "Seul Exploitant"}])
        siren, nom = resoudre_siren_geo(_ligne_sans_enseigne(), client)
        assert siren == "333333333"

    def test_sans_coords_pas_d_appel(self):
        client = _FakeClient([{"siren": "1", "nom_complet": "X"}])
        siren, nom = resoudre_siren_geo(LigneParking(surface_m2=12000.0), client)
        assert (siren, nom) == (None, None)
        assert client.appels == []  # aucun appel réseau sans coordonnées


class TestResoudreLignes:
    def test_enrichit_en_place_et_compte(self):
        client = _FakeClient([
            {"siren": "552100554", "nom_complet": "Foncière Parc SA",
             "tranche_effectif_salarie": "32"},
        ])
        lignes = [_ligne_sans_enseigne(), LigneParking(surface_m2=9000.0, nom="Déjà connu")]
        stats = resoudre_lignes_sans_enseigne(lignes, client)
        assert stats["tente"] == 1 and stats["resolu"] == 1
        assert stats["erreurs"] == 0 and stats["interrompu"] == 0
        assert lignes[0].siren == "552100554"
        assert lignes[0].raison_sociale == "Foncière Parc SA"
        # La ligne avec nom n'a pas été touchée
        assert lignes[1].raison_sociale is None

    def test_non_resolu_laisse_la_ligne_intacte(self):
        lignes = [_ligne_sans_enseigne()]
        stats = resoudre_lignes_sans_enseigne(lignes, _FakeClient([]))
        assert stats["tente"] == 1 and stats["resolu"] == 0
        assert lignes[0].siren is None


class _ClientErreur:
    """Client near_point qui lève — simule un rate-limit API (HTTP 429)."""

    def __init__(self, exc: Exception, echouer_apres: int = 0):
        self.exc = exc
        self.echouer_apres = echouer_apres  # nb d'appels OK avant de lever
        self.appels = 0

    def decouvrir_near_point(self, latitude, longitude, radius_km, **kwargs):
        self.appels += 1
        if self.appels > self.echouer_apres:
            raise self.exc
        return iter([{"siren": "552100554", "nom_complet": "OK SA",
                      "tranche_effectif_salarie": "32"}])


class TestResilience:
    """Phase C ne doit jamais crasher le run sur une erreur API transitoire."""

    def _lignes(self, n: int) -> list[LigneParking]:
        return [
            LigneParking(surface_m2=800.0, latitude=50.4 + i / 1000, longitude=2.8)
            for i in range(n)
        ]

    def test_erreur_api_ne_crashe_pas(self):
        client = _ClientErreur(RuntimeError("HTTP 429 rate-limited"))
        # 3 parkings, toutes les résolutions échouent → pas d'exception levée.
        stats = resoudre_lignes_sans_enseigne(self._lignes(3), client)
        assert stats["resolu"] == 0
        assert stats["erreurs"] == 3
        assert stats["interrompu"] == 0  # 3 < seuil par défaut (8)

    def test_interruption_apres_echecs_consecutifs(self):
        client = _ClientErreur(RuntimeError("HTTP 429 rate-limited"))
        stats = resoudre_lignes_sans_enseigne(
            self._lignes(20), client, max_echecs_consecutifs=3
        )
        # On s'arrête au 3e échec consécutif, on ne tente pas les 20.
        assert stats["interrompu"] == 1
        assert stats["tente"] == 3
        assert stats["erreurs"] == 3

    def test_echecs_non_consecutifs_ne_stoppent_pas(self):
        # 1 OK puis 1 KO en alternance ne doit pas déclencher l'interruption.
        client = _ClientErreur(RuntimeError("429"), echouer_apres=1)
        stats = resoudre_lignes_sans_enseigne(
            self._lignes(2), client, max_echecs_consecutifs=2
        )
        assert stats["resolu"] == 1  # le 1er passe
        assert stats["erreurs"] == 1  # le 2e échoue
        assert stats["interrompu"] == 0
