"""Tests du connecteur IRVE (comptage par rayon, sans réseau)."""

from __future__ import annotations

from renoboost_leads.potentiel.irve import Borne, ClientIRVE, _parse_rows

# Lille ~ (50.6292, 3.0573). On place des bornes à diverses distances.
_CENTRE = (50.6292, 3.0573)


def _borne(dlat: float, dlon: float, kw: float | None = 22.0) -> Borne:
    return Borne(lat=_CENTRE[0] + dlat, lon=_CENTRE[1] + dlon, puissance_kw=kw)


class TestComptage:
    def test_paliers_distincts(self):
        bornes = [
            _borne(0.0005, 0.0005),    # ~70 m → sur site
            _borne(0.005, 0.0),        # ~550 m → voisinage
            _borne(0.05, 0.0),         # ~5,5 km → rayon 10
            _borne(0.2, 0.0),          # ~22 km → hors zone
        ]
        c = ClientIRVE(bornes=bornes).compter(*_CENTRE)
        assert c.sur_site == 1
        assert c.voisinage_1km == 2  # sur-site + 550 m
        assert c.rayon_10km == 3     # + 5,5 km
        assert c.types  # au moins un type listé

    def test_zone_vide(self):
        c = ClientIRVE(bornes=[_borne(0.5, 0.5)]).compter(*_CENTRE)
        assert (c.sur_site, c.voisinage_1km, c.rayon_10km) == (0, 0, 0)

    def test_type_label_puissances(self):
        assert Borne(0, 0, 150).type_label().startswith("rapide")
        assert "AC" in Borne(0, 0, 22).type_label()


class TestParsing:
    def test_parse_colonnes_consolidees(self):
        csv_txt = (
            "consolidated_latitude,consolidated_longitude,puissance_nominale,nom_operateur\n"
            "50.6292,3.0573,22,Izivia\n"
        )
        bornes = _parse_rows(csv_txt)
        assert len(bornes) == 1
        assert bornes[0].puissance_kw == 22.0
        assert bornes[0].operateur == "Izivia"

    def test_parse_coordonneesxy_et_watts(self):
        csv_txt = 'coordonneesXY,puissance_nominale\n"[3.0573, 50.6292]",22000\n'
        bornes = _parse_rows(csv_txt)
        assert len(bornes) == 1
        assert round(bornes[0].lat, 3) == 50.629
        assert bornes[0].puissance_kw == 22.0  # 22000 W → 22 kW

    def test_ligne_sans_coord_ignoree(self):
        assert _parse_rows("puissance_nominale\n22\n") == []
