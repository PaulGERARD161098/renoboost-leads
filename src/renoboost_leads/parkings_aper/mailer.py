"""Phase D — notification email matinale post-run parkings APER.

Réutilise la brique d'envoi SMTP de la veille immatriculations
(`ConfigSMTP` + `envoyer_message`) et n'ajoute ici que la mise en forme propre
aux parkings APER : surfaces, échéances réglementaires et priorités.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

from ..common.logger import get_logger
from ..veille_immatriculations.mailer import ConfigSMTP, envoyer_message

logger = get_logger(__name__)


@dataclass
class ResumeAper:
    """Données du récapitulatif d'un run parkings APER pour l'email."""

    date_run: str  # YYYY-MM-DD
    nb_lignes_brutes: int
    nb_parkings_aper: int
    nb_nouveaux: int
    nb_deja_vus: int
    nb_top_leads: int
    cout_l4_eur: float
    chemin_csv: Path
    # liste de dicts {nom, siren, score, surface, echeance, priorite, raison}
    extraits_top: list[dict[str, str]] = field(default_factory=list)


def _construire_message(config: ConfigSMTP, r: ResumeAper) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = (
        f"[RénoBoost] Parkings loi APER — {r.date_run} "
        f"({r.nb_top_leads} top leads)"
    )
    msg["From"] = config.expediteur
    msg["To"] = ", ".join(config.destinataires)

    msg.set_content(_corps_texte(r))
    msg.add_alternative(_corps_html(r), subtype="html")

    if r.chemin_csv.exists():
        with r.chemin_csv.open("rb") as fh:
            msg.add_attachment(
                fh.read(), maintype="text", subtype="csv", filename=r.chemin_csv.name
            )
    return msg


def _corps_texte(r: ResumeAper) -> str:
    lignes = [
        f"Parkings soumis à la loi APER — RénoBoost — {r.date_run}",
        "─" * 60,
        f"Lignes inventaire brutes : {r.nb_lignes_brutes}",
        f"Parkings soumis (> seuil) : {r.nb_parkings_aper}",
        f"  ↳ nouveaux              : {r.nb_nouveaux}",
        f"  ↳ déjà vus (flag)       : {r.nb_deja_vus}",
        f"Top leads                 : {r.nb_top_leads}",
        f"Coût scoring L4           : {r.cout_l4_eur:.4f} €",
        f"CSV joint                 : {r.chemin_csv.name}",
        "",
    ]
    if r.extraits_top:
        lignes.append("Aperçu top leads du jour :")
        for ex in r.extraits_top[:5]:
            lignes.append(
                f"  • {ex.get('nom', '?')} (SIREN {ex.get('siren', '?')}, "
                f"score {ex.get('score', '?')}) — {ex.get('surface', '?')} m², "
                f"échéance {ex.get('echeance', '?')} ({ex.get('priorite', '?')})"
            )
    return "\n".join(lignes)


def _corps_html(r: ResumeAper) -> str:
    extraits_html = ""
    if r.extraits_top:
        rows = "".join(
            f"<tr><td>{ex.get('nom', '?')}</td>"
            f"<td>{ex.get('siren', '?')}</td>"
            f"<td><b>{ex.get('score', '?')}</b></td>"
            f"<td>{ex.get('surface', '?')} m²</td>"
            f"<td>{ex.get('echeance', '?')}</td>"
            f"<td>{ex.get('priorite', '?')}</td></tr>"
            for ex in r.extraits_top[:5]
        )
        extraits_html = (
            "<h3>Aperçu top leads</h3>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<tr><th>Nom</th><th>SIREN</th><th>Score</th><th>Surface</th>"
            "<th>Échéance</th><th>Priorité</th></tr>"
            f"{rows}</table>"
        )
    return (
        "<html><body>"
        f"<h2>Parkings loi APER — {r.date_run}</h2>"
        "<ul>"
        f"<li>Lignes inventaire brutes : <b>{r.nb_lignes_brutes}</b></li>"
        f"<li>Parkings soumis (&gt; seuil) : <b>{r.nb_parkings_aper}</b> "
        f"(nouveaux : {r.nb_nouveaux} ; déjà vus : {r.nb_deja_vus})</li>"
        f"<li>Top leads : <b>{r.nb_top_leads}</b></li>"
        f"<li>Coût scoring L4 : <b>{r.cout_l4_eur:.4f} €</b></li>"
        f"<li>CSV joint : <code>{r.chemin_csv.name}</code></li>"
        "</ul>"
        f"{extraits_html}"
        "</body></html>"
    )


def envoyer_resume_aper(config: ConfigSMTP, resume: ResumeAper) -> None:
    """Construit et envoie l'email récapitulatif d'un run parkings APER."""
    msg = _construire_message(config, resume)
    envoyer_message(config, msg)
    logger.info(
        "Email APER envoyé à %d destinataire(s) (%d top leads)",
        len(config.destinataires),
        resume.nb_top_leads,
    )


__all__ = ["ResumeAper", "envoyer_resume_aper"]
