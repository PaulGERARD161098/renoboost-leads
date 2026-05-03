"""Tests pour la methode stats_l2() (bug B4 corrige).

Bug B4 : siren_pct et dirigeant_pct incluaient les chaines dans le denominateur,
ce qui faussait le taux affiche dans les rapports.
Le denominateur correct est n - nb_chaines (les chaines ne sont pas cherchees).
"""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.models import LeadStage2
from renoboost_leads.stage2_entreprises.enricher import EnricheurStage2

_FIXED_DATE = datetime(2026, 5, 1, tzinfo=timezone.utc)
_counter = [0]


def _make_lead(
    *,
    siren: str | None = None,
    dirigeant: str | None = None,
    flag_chaine: bool = False,
) -> LeadStage2:
    """Helper : cree un LeadStage2 minimal pour les tests."""
    _counter[0] += 1
    return LeadStage2(
        place_id=f"test_{_counter[0]}",
        extraction_date=_FIXED_DATE,
        nom="Test Establishment",
        siren=siren,
        dirigeant_nom=dirigeant,
        flag_chaine=flag_chaine,
    )


class TestStatsL2:
    """Verifie que stats_l2 calcule correctement les pourcentages."""

    def test_liste_vide_retourne_total_zero(self):
        """Cas limite : liste vide ne plante pas."""
        result = EnricheurStage2.stats_l2([])
        assert result == {"total": 0}

    def test_aucune_chaine_calcul_classique(self):
        """Sans chaines, le denominateur reste n (comportement standard)."""
        leads = [
            _make_lead(siren="123"),
            _make_lead(siren="456"),
            _make_lead(siren=None),
            _make_lead(siren=None),
        ]
        # 2 SIREN sur 4 leads, aucune chaine
        result = EnricheurStage2.stats_l2(leads)
        assert result["total"] == 4
        assert result["siren_trouve"] == 2
        assert result["siren_pct"] == 50.0  # 2/4
        assert result["chaines"] == 0

    def test_avec_chaines_exclut_du_denominateur_siren(self):
        """BUG B4 : siren_pct doit diviser par (n - nb_chaines), pas n."""
        leads = [
            _make_lead(siren="111"),
            _make_lead(siren="222"),
            _make_lead(siren=None),
            _make_lead(flag_chaine=True),  # chaine 1, pas de SIREN cherche
            _make_lead(flag_chaine=True),  # chaine 2, pas de SIREN cherche
        ]
        # 2 SIREN sur 3 leads non-chaines (5 total - 2 chaines)
        result = EnricheurStage2.stats_l2(leads)
        assert result["total"] == 5
        assert result["siren_trouve"] == 2
        assert result["chaines"] == 2
        # AVANT FIX : 2/5 = 40.0 (FAUX)
        # APRES FIX : 2/3 = 66.7 (correct)
        assert result["siren_pct"] == 66.7

    def test_avec_chaines_exclut_du_denominateur_dirigeant(self):
        """BUG B4 : dirigeant_pct doit aussi exclure les chaines."""
        leads = [
            _make_lead(siren="111", dirigeant="Dupont"),
            _make_lead(siren="222", dirigeant=None),
            _make_lead(siren=None, dirigeant=None),
            _make_lead(flag_chaine=True),
        ]
        # 1 dirigeant sur 3 leads non-chaines
        result = EnricheurStage2.stats_l2(leads)
        assert result["dirigeant_trouve"] == 1
        # AVANT FIX : 1/4 = 25.0
        # APRES FIX : 1/3 = 33.3
        assert result["dirigeant_pct"] == 33.3

    def test_chaines_pct_reste_sur_total(self):
        """chaines_pct doit rester divise par le TOTAL (% de chaines parmi tous)."""
        leads = [
            _make_lead(siren="111"),
            _make_lead(flag_chaine=True),
            _make_lead(flag_chaine=True),
            _make_lead(flag_chaine=True),
        ]
        # 3 chaines sur 4 leads (75%)
        result = EnricheurStage2.stats_l2(leads)
        assert result["chaines"] == 3
        assert result["chaines_pct"] == 75.0  # 3/4

    def test_que_des_chaines_evite_division_par_zero(self):
        """Cas limite : 100% de chaines, pas de division par 0."""
        leads = [
            _make_lead(flag_chaine=True),
            _make_lead(flag_chaine=True),
        ]
        result = EnricheurStage2.stats_l2(leads)
        assert result["total"] == 2
        assert result["chaines"] == 2
        assert result["chaines_pct"] == 100.0
        # Cas limite : pas de division par 0
        assert result["siren_pct"] == 0.0
        assert result["dirigeant_pct"] == 0.0
