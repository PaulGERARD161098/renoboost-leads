"""Construit le bloc « # Offre commerciale » (contexte_client) depuis une verticale.

Sans ce câblage, le scoring L4 retombe sur le contexte par défaut (RénoBoost
rénovation thermique) : le mail décrit alors la mauvaise offre et ne signe pas au
nom du client. On compose ici un contexte fidèle à la verticale : offre, cible,
argument clé, critères de qualification, et le **ton du mail** (registre, accroche,
appel à l'action, longueur) — utilisé par la CLI et le worker.
"""

from __future__ import annotations

from .schema import Verticale


def contexte_client_depuis_verticale(verticale: Verticale) -> str:
    """Texte « # Offre commerciale » décrivant l'offre portée par la verticale."""
    v = verticale
    client = v.emetteur.nom_entreprise if v.emetteur else v.verticale.nom
    # Évite « Client — Client … » quand le nom de verticale reprend déjà le client.
    if client.lower() in v.verticale.nom.lower():
        entete = v.verticale.nom
    else:
        entete = f"{client} — {v.verticale.nom}"
    lignes: list[str] = [
        f"{entete}.",
        f"Offre : {v.offre.produit}.",
        f"Argument clé : {v.offre.argument_principal}",
        f"Cible : {v.cible.detail}",
    ]
    if v.qualification.criteres_top:
        lignes.append("Profil idéal (ICP) :")
        lignes.extend(f"- {c}" for c in v.qualification.criteres_top)
    if v.qualification.criteres_exclusion:
        lignes.append("À écarter :")
        lignes.extend(f"- {c}" for c in v.qualification.criteres_exclusion)

    # Ton du mail propre à la verticale : le mail L4 doit respecter ce style.
    t = v.ton_mail
    lignes.append("Ton et style du mail (à respecter) :")
    lignes.append(f"- Registre : {t.registre}")
    lignes.append(f"- Longueur cible : ~{t.longueur_mots} mots")
    lignes.append(f"- Accroche : {t.attaque}")
    lignes.append(f"- Appel à l'action : {t.cta}")
    if t.signaux_a_personnaliser:
        lignes.append(
            "- Personnaliser avec ces signaux s'ils sont présents : "
            + ", ".join(t.signaux_a_personnaliser)
        )
    return "\n".join(lignes)


__all__ = ["contexte_client_depuis_verticale"]
