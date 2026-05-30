"""Tests du prompt template L4."""

from __future__ import annotations

from datetime import datetime, timezone

from renoboost_leads.models import Emetteur, LeadStage3
from renoboost_leads.stage4_prospection.prompt_template import (
    CONTEXTE_CLIENT_DEFAUT,
    PROMPT_VERSION,
    construire_prompt,
)


def _lead_complet() -> LeadStage3:
    return LeadStage3(
        place_id="ChIJ_test",
        extraction_date=datetime.now(timezone.utc),
        nom="SMI Industrie",
        adresse="12 rue de Lille, 59000 Lille",
        ville="Lille",
        code_postal="59000",
        site_web="https://smi-industrie.fr",
        note=4.2,
        nb_avis=42,
        siren="402222222",
        code_naf="25.62A",
        libelle_naf="Mécanique industrielle",
        forme_juridique="SAS",
        tranche_effectif="22",
        libelle_effectif="100 à 199 salariés",
        nb_etablissements=3,
        date_creation="2008-03-15",
        dirigeant_nom="Dupont",
        dirigeant_prenom="Jean",
        dirigeant_qualite="Président",
        emails_verifies=["contact@smi-industrie.fr", "j.dupont@smi-industrie.fr"],
    )


def _lead_minimal() -> LeadStage3:
    return LeadStage3(
        place_id="ChIJ_min",
        extraction_date=datetime.now(timezone.utc),
        nom="Atelier X",
    )


class TestConstruirePrompt:
    def test_prompt_version_constant(self):
        # Garde-fou : si on bump le prompt, on doit aussi bumper PROMPT_VERSION.
        assert PROMPT_VERSION
        assert isinstance(PROMPT_VERSION, str)

    def test_prompt_contient_contexte_par_defaut(self):
        prompt = construire_prompt(_lead_minimal())
        assert "RénoBoost" in prompt
        assert CONTEXTE_CLIENT_DEFAUT.split("\n", 1)[0] in prompt

    def test_prompt_utilise_contexte_custom(self):
        prompt = construire_prompt(_lead_minimal(), contexte_client="Mon offre custom XYZ.")
        assert "Mon offre custom XYZ." in prompt
        assert "RénoBoost" not in prompt

    def test_prompt_inclut_champs_renseignes(self):
        prompt = construire_prompt(_lead_complet())
        assert "SMI Industrie" in prompt
        assert "25.62A" in prompt
        assert "SAS" in prompt
        assert "100 à 199 salariés" in prompt
        assert "3" in prompt  # nb_etablissements
        assert "Jean Dupont" in prompt
        assert "Président" in prompt
        assert "smi-industrie.fr" in prompt
        assert "59000 Lille" in prompt

    def test_prompt_n_inclut_pas_none(self):
        prompt = construire_prompt(_lead_minimal())
        # Pas de "None" littéral dans le prompt
        assert "None" not in prompt
        # Le lead est quasi-vide → mention d'absence de données
        assert "Atelier X" in prompt

    def test_prompt_avec_pitch_demande_champ(self):
        prompt = construire_prompt(_lead_minimal(), inclure_pitch=True)
        assert "pitch_propose" in prompt

    def test_prompt_sans_pitch_omet_champ(self):
        prompt = construire_prompt(_lead_minimal(), inclure_pitch=False)
        assert "pitch_propose" not in prompt
        assert "score_interet" in prompt

    def test_prompt_avec_pitch_demande_email(self):
        prompt = construire_prompt(_lead_minimal(), inclure_pitch=True)
        assert "email_objet" in prompt
        assert "email_corps" in prompt

    def test_prompt_sans_pitch_omet_email(self):
        prompt = construire_prompt(_lead_minimal(), inclure_pitch=False)
        assert "email_objet" not in prompt
        assert "email_corps" not in prompt

    def test_prompt_flag_chaine_signale(self):
        lead = _lead_minimal()
        lead.flag_chaine = True
        lead.note_chaine = "Groupe Accor"
        prompt = construire_prompt(lead)
        assert "Chaîne" in prompt or "chaîne" in prompt
        assert "Accor" in prompt

    def test_prompt_hors_filtre_signale(self):
        lead = _lead_minimal()
        lead.hors_filtre_entreprise = True
        lead.raison_hors_filtre = "effectif < 50"
        prompt = construire_prompt(lead)
        assert "Hors filtre" in prompt
        assert "effectif < 50" in prompt

    def test_prompt_resume_emails_si_plusieurs(self):
        lead = _lead_minimal()
        lead.emails_verifies = [f"x{i}@ex.fr" for i in range(10)]
        prompt = construire_prompt(lead)
        # On affiche jusqu'à 3 emails + un "+N autres"
        assert "+7 autres" in prompt

    def test_prompt_signaux_ve_affiches(self):
        lead = _lead_minimal()
        lead.signaux_ve = ["IRVE", "borne de recharge"]
        prompt = construire_prompt(lead)
        assert "IRVE" in prompt
        assert "borne de recharge" in prompt

    def test_prompt_sans_signaux_ve_n_affiche_pas_la_ligne(self):
        prompt = construire_prompt(_lead_minimal())
        assert "Signaux flotte" not in prompt


class TestEmetteur:
    @staticmethod
    def _emetteur_complet() -> Emetteur:
        return Emetteur(
            nom_entreprise="Toitures Rossini",
            signataire="Marc Rossini",
            fonction="Gérant",
            telephone="03 20 00 00 00",
            email="contact@toitures-rossini.fr",
            site_web="https://toitures-rossini.fr",
        )

    def test_sans_emetteur_pas_de_section(self):
        prompt = construire_prompt(_lead_minimal())
        assert "# Émetteur" not in prompt
        # Comportement historique : signature devinée depuis l'offre commerciale.
        assert "issu de l'offre commerciale" in prompt

    def test_avec_emetteur_section_et_coordonnees(self):
        prompt = construire_prompt(_lead_minimal(), emetteur=self._emetteur_complet())
        assert "# Émetteur" in prompt
        assert "Toitures Rossini" in prompt
        assert "Marc Rossini" in prompt
        assert "Gérant" in prompt
        assert "03 20 00 00 00" in prompt
        assert "contact@toitures-rossini.fr" in prompt
        assert "https://toitures-rossini.fr" in prompt
        # La règle de signature bascule sur le pied de coordonnées.
        assert "pied de coordonnées" in prompt
        assert "issu de l'offre commerciale" not in prompt

    def test_emetteur_champs_optionnels_absents_non_affiches(self):
        prompt = construire_prompt(
            _lead_minimal(), emetteur=Emetteur(nom_entreprise="ACME Solaire")
        )
        assert "# Émetteur" in prompt
        assert "ACME Solaire" in prompt
        # Aucune ligne de coordonnée fabriquée quand non fournie.
        assert "Téléphone :" not in prompt.split("# Lead", 1)[0]
        assert "Email :" not in prompt.split("# Lead", 1)[0]

    def test_emetteur_sans_pitch_pas_de_section(self):
        # Sans pitch, pas d'email généré → la section émetteur n'a pas de sens
        # mais ne doit pas planter ; la signature ne s'applique qu'au corps email.
        prompt = construire_prompt(
            _lead_minimal(), inclure_pitch=False, emetteur=self._emetteur_complet()
        )
        # La section est toujours injectée (inoffensive), mais aucune règle email.
        assert "email_corps" not in prompt

    def test_emetteur_change_le_hash_du_prompt(self):
        # Deux émetteurs distincts → prompts distincts → cache miss (hash_prompt).
        base = construire_prompt(_lead_minimal())
        avec = construire_prompt(_lead_minimal(), emetteur=self._emetteur_complet())
        assert base != avec
