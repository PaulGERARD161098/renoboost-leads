"""Modèle de sortie de l'étage de complétion (3.7).

`LeadComplete` étend `LeadStage35` : il se branche après l'étage 3.5 et avant le
scoring L4. Les valeurs repêchées comblent les **champs de base existants**
(`siren`, `dirigeant_nom`, `libelle_naf`, `tranche_effectif`, `chiffre_affaires`,
`emails_verifies`, `telephone`…) qui traversent naturellement L4 et le CSV final.

Les champs `completion_*` ci-dessous portent uniquement les **métadonnées** de
l'étage (provenance, coût, erreur). Ils vivent dans le CSV `etage3_7_completion.csv`
et dans l'annexe `completion.md` ; L4 les ignore (extra="ignore"), ce qui est voulu.
"""

from __future__ import annotations

from ..models import LeadStage35


class LeadComplete(LeadStage35):
    """LeadStage35 + métadonnées de l'étage de complétion."""

    # True si le lead a été envoyé à un provider (succès, vide ou erreur).
    complete: bool = False
    # Nom du provider sollicité (ex. "societeinfo").
    completion_provider: str | None = None
    # Liste des champs de base effectivement comblés par la complétion
    # (ex. ["siren", "dirigeant_nom", "emails"]). Sérialisé "a|b|c" en CSV.
    completion_champs_remplis: list[str] = []
    # LinkedIn entreprise renvoyé par le provider (pas de champ de base dédié).
    completion_linkedin: str | None = None
    # Raison textuelle si l'appel provider a échoué.
    completion_erreur: str | None = None
    # Coût imputé à la complétion de ce lead.
    cout_completion_eur: float = 0.0

    @property
    def repeche(self) -> bool:
        """True si la complétion a effectivement comblé au moins un champ."""
        return bool(self.completion_champs_remplis)
