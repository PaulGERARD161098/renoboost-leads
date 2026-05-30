"""Livrables de l'étage de complétion : CSV enrichi + fiche annexe markdown.

Deux sorties par run :
1. `etage3_7_completion.csv` — toutes les colonnes du pipeline + colonnes
   `completion_*` (provenance, coût). Exploitable en CRM / cold-mail.
2. `completion.md` — fiche annexe lisible listant, pour chaque lead repêché, ce
   que la complétion a comblé + une accroche prête à l'emploi.
"""

from __future__ import annotations

from pathlib import Path

from ..exporter import COLONNES_STAGE3_5, _ecrire_csv
from .models import LeadComplete

COLONNES_COMPLETION_EXTRA = [
    "complete",
    "completion_provider",
    "completion_champs_remplis",
    "completion_linkedin",
    "completion_erreur",
    "cout_completion_eur",
]
COLONNES_COMPLETION = COLONNES_STAGE3_5 + COLONNES_COMPLETION_EXTRA


def export_completion_csv(leads: list[LeadComplete], output_path: Path) -> Path:
    """Écrit le CSV de l'étage de complétion (pipeline + colonnes completion_*)."""
    rows = [lead.model_dump() for lead in leads]
    return _ecrire_csv(rows, COLONNES_COMPLETION, output_path)


def _accroche(lead: LeadComplete) -> str:
    """Petite accroche cold-mail dérivée des données repêchées/connues."""
    qui = lead.dirigeant_nom or "la direction"
    quoi = lead.libelle_naf or lead.type_principal or "votre activité"
    return f"Contact privilégié {qui} — secteur « {quoi} »."


def generer_annexe_completion(leads: list[LeadComplete], output_path: Path) -> Path:
    """Génère la fiche annexe markdown `completion.md`."""
    repeches = [lead for lead in leads if lead.repeche]
    erreurs = [lead for lead in leads if lead.completion_erreur]
    cout = sum(lead.cout_completion_eur for lead in leads)

    lignes: list[str] = []
    lignes.append("# Annexe complétion — repêchage & enrichissement")
    lignes.append("")
    lignes.append(
        f"- Leads traités : **{len(leads)}** — repêchés : **{len(repeches)}** — "
        f"erreurs provider : **{len(erreurs)}**"
    )
    lignes.append(f"- Coût complétion : **{cout:.2f} €**")
    if leads:
        providers = sorted({lead.completion_provider for lead in leads if lead.completion_provider})
        if providers:
            lignes.append(f"- Provider(s) : {', '.join(providers)}")
    lignes.append("")

    if not repeches:
        lignes.append("_Aucun champ comblé par la complétion sur ce run._")
        lignes.append("")
        return _ecrire_md(lignes, output_path)

    lignes.append("## Leads repêchés")
    lignes.append("")
    lignes.append("| Enseigne | SIREN | Champs comblés | Dirigeant | Email | Accroche |")
    lignes.append("|---|---|---|---|---|---|")
    for lead in repeches:
        email = lead.emails_verifies[0] if lead.emails_verifies else ""
        champs = ", ".join(lead.completion_champs_remplis)
        nom = (lead.nom or "").replace("|", "/")
        dirigeant = (lead.dirigeant_nom or "").replace("|", "/")
        lignes.append(
            f"| {nom} | {lead.siren or ''} | {champs} | {dirigeant} | {email} | "
            f"{_accroche(lead).replace('|', '/')} |"
        )
    lignes.append("")

    if erreurs:
        lignes.append("## Erreurs provider")
        lignes.append("")
        for lead in erreurs:
            lignes.append(f"- **{lead.nom}** : {lead.completion_erreur}")
        lignes.append("")

    return _ecrire_md(lignes, output_path)


def _ecrire_md(lignes: list[str], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lignes), encoding="utf-8")
    return output_path
