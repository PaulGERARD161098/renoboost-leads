"""Tests de l'orchestrateur L3.5 — filtre intelligent + cache + batch."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from renoboost_leads.models import EnrichissementL35, LeadStage3
from renoboost_leads.stage3_5_enrichment.cache import CacheStage35
from renoboost_leads.stage3_5_enrichment.client import DropcontactReponse
from renoboost_leads.stage3_5_enrichment.dry_run import DropcontactClientDryRun
from renoboost_leads.stage3_5_enrichment.enricher import (
    EnricheurStage35,
    _eligible,
    _extraire_email_dropcontact,
)


def _lead(
    place_id: str = "p1",
    nom: str = "Acme",
    siren: str | None = "123456789",
    site_web: str | None = "https://acme.fr",
    dirigeant_prenom: str | None = "Paul",
    dirigeant_nom: str | None = "Durand",
    hors_filtre: bool = False,
) -> LeadStage3:
    return LeadStage3(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        siren=siren,
        site_web=site_web,
        dirigeant_prenom=dirigeant_prenom,
        dirigeant_nom=dirigeant_nom,
        hors_filtre_entreprise=hors_filtre,
    )


class _FakeClient:
    """Client mockable qui renvoie un payload contrôlé par lot."""

    def __init__(self, items_par_lot: list[dict[str, Any]] | None = None,
                 cout: float = 0.50, exception: Exception | None = None):
        self.items_par_lot = items_par_lot
        self.cout = cout
        self.exception = exception
        self.appels = []

    def enrichir_batch(self, lots: list[dict[str, Any]]) -> DropcontactReponse:
        self.appels.append(lots)
        if self.exception:
            raise self.exception
        # Par défaut renvoie un item par lead avec l'email construit
        if self.items_par_lot is None:
            data = []
            for lot in lots:
                first = lot.get("first_name", "")
                last = lot.get("last_name", "")
                data.append(
                    {
                        "first_name": first,
                        "last_name": last,
                        "civility": "M",
                        "email": [
                            {"email": f"{first.lower()}.{last.lower()}@x.fr",
                             "qualification": "correct"}
                        ],
                        "phone": "+33100000000",
                        "linkedin": f"https://linkedin.com/in/{first.lower()}-{last.lower()}/",
                    }
                )
        else:
            data = self.items_par_lot[: len(lots)]
        return DropcontactReponse(
            request_id="fake",
            data=data,
            cout_eur=self.cout * len(lots),
        )


# ─── _eligible ────────────────────────────────────────────────────


class TestEligible:
    def test_lead_complet_eligible(self):
        assert _eligible(_lead()) is True

    def test_hors_filtre_rejete(self):
        assert _eligible(_lead(hors_filtre=True)) is False

    def test_sans_siren_rejete(self):
        assert _eligible(_lead(siren=None)) is False

    def test_sans_dirigeant_ni_site_rejete(self):
        assert _eligible(_lead(dirigeant_nom=None, dirigeant_prenom=None,
                               site_web=None)) is False

    def test_avec_site_seul_eligible(self):
        assert _eligible(_lead(dirigeant_nom=None, dirigeant_prenom=None)) is True

    def test_avec_dirigeant_seul_eligible(self):
        assert _eligible(_lead(site_web=None)) is True

    def test_exiger_domaine_rejette_sans_site(self):
        # Correctif hit-rate : sans domaine, Dropcontact ne trouve rien → on
        # n'envoie pas quand exiger_domaine est actif, même avec un dirigeant.
        lead = _lead(site_web=None)
        assert _eligible(lead, exiger_domaine=False) is True
        assert _eligible(lead, exiger_domaine=True) is False

    def test_exiger_domaine_accepte_avec_site(self):
        assert _eligible(_lead(), exiger_domaine=True) is True


# ─── _extraire_email_dropcontact ──────────────────────────────────


class TestExtraireEmail:
    def test_priorite_correct(self):
        item = {
            "email": [
                {"email": "risky@x.fr", "qualification": "risky"},
                {"email": "ok@x.fr", "qualification": "correct"},
            ]
        }
        assert _extraire_email_dropcontact(item) == ("ok@x.fr", "correct")

    def test_premier_si_aucun_correct(self):
        item = {"email": [{"email": "r@x.fr", "qualification": "risky"}]}
        assert _extraire_email_dropcontact(item) == ("r@x.fr", "risky")

    def test_vide(self):
        assert _extraire_email_dropcontact({"email": []}) == (None, None)
        assert _extraire_email_dropcontact({}) == (None, None)


# ─── EnricheurStage35 ────────────────────────────────────────────


class TestEnricheurStage35:
    def _config(self, batch_size: int = 50) -> EnrichissementL35:
        return EnrichissementL35(batch_size=batch_size)

    def test_filtre_les_hors_filtre(self):
        leads = [_lead("p1"), _lead("p2", hors_filtre=True)]
        client = _FakeClient()
        enr = EnricheurStage35(client=client, config=self._config())
        out = enr.enrichir(leads)

        assert len(out) == 2
        assert out[0].enrichi_dropcontact is True
        assert out[1].enrichi_dropcontact is False
        # Un seul lead envoyé à l'API
        assert len(client.appels) == 1
        assert len(client.appels[0]) == 1
        assert enr.nb_filtres_out == 1
        assert enr.nb_envoyes == 1

    def test_decoupe_en_batchs(self):
        leads = [_lead(f"p{i}") for i in range(7)]
        client = _FakeClient()
        enr = EnricheurStage35(client=client, config=self._config(batch_size=3))
        out = enr.enrichir(leads)

        assert len(out) == 7
        # 7 leads / batch=3 → 3 appels (3, 3, 1)
        assert [len(a) for a in client.appels] == [3, 3, 1]
        assert enr.nb_envoyes == 7
        assert all(lead.enrichi_dropcontact for lead in out)

    def test_hydrate_email_phone_linkedin(self, tmp_path):
        leads = [_lead("p1", dirigeant_prenom="Paul", dirigeant_nom="Durand")]
        client = _FakeClient()
        enr = EnricheurStage35(client=client, config=self._config())
        out = enr.enrichir(leads)

        assert out[0].email_dropcontact == "paul.durand@x.fr"
        assert out[0].qualification_email_dropcontact == "correct"
        assert out[0].telephone_direct_dropcontact == "+33100000000"
        assert "paul-durand" in out[0].linkedin_dirigeant_dropcontact
        assert out[0].civilite_dirigeant_dropcontact == "M"
        assert out[0].cout_enrichissement_eur > 0

    def test_cache_hit_court_circuite_api(self, tmp_path):
        cache = CacheStage35(tmp_path / "cache.sqlite")
        # Pre-warm cache
        from renoboost_leads.stage3_5_enrichment.cache import calcul_cache_key
        key = calcul_cache_key("dropcontact", "fr", True)
        cache.store("p1", key, {
            "email": [{"email": "cached@x.fr", "qualification": "correct"}],
            "phone": None,
        })

        leads = [_lead("p1"), _lead("p2")]
        client = _FakeClient()
        enr = EnricheurStage35(client=client, config=self._config(), cache=cache)
        out = enr.enrichir(leads)

        assert out[0].email_dropcontact == "cached@x.fr"
        # Seul p2 a été envoyé à l'API (p1 venait du cache)
        assert client.appels == [
            [{"first_name": "Paul", "last_name": "Durand", "company": "Acme",
              "website": "https://acme.fr", "siren": "123456789"}]
        ]
        assert enr.cache_hits == 1
        assert enr.cache_misses == 1

    def test_erreur_api_marque_lead(self):
        from renoboost_leads.stage3_5_enrichment.client import DropcontactError
        leads = [_lead("p1"), _lead("p2")]
        client = _FakeClient(exception=DropcontactError("boom"))
        enr = EnricheurStage35(client=client, config=self._config())
        out = enr.enrichir(leads)

        assert all(not lead.enrichi_dropcontact for lead in out)
        assert all("api_error" in (lead.enrichissement_erreur or "") for lead in out)
        assert enr.nb_erreurs == 2

    def test_dry_run_client_fonctionne(self):
        leads = [_lead("p1")]
        client = DropcontactClientDryRun()
        enr = EnricheurStage35(client=client, config=self._config())
        out = enr.enrichir(leads)

        assert out[0].enrichi_dropcontact is True
        assert out[0].email_dropcontact is not None

    def test_callback_save_appele_par_batch(self, tmp_path):
        leads = [_lead(f"p{i}") for i in range(5)]
        client = _FakeClient()
        captured = []
        enr = EnricheurStage35(
            client=client,
            config=self._config(batch_size=2),
            callback_save_incremental=captured.append,
        )
        enr.enrichir(leads)
        # 5 leads / batch=2 → 3 appels au callback (après chaque batch)
        assert len(captured) == 3
        # Le dernier callback contient tous les leads
        assert len(captured[-1]) == 5

    def test_stats(self):
        leads = [_lead(f"p{i}") for i in range(3)]
        client = _FakeClient()
        enr = EnricheurStage35(client=client, config=self._config())
        out = enr.enrichir(leads)
        stats = enr.stats_l35(out)
        assert stats["total"] == 3
        assert stats["envoyes_api"] == 3
        assert stats["enrichis"] == 3
        assert stats["avec_email_pct"] == 100.0
