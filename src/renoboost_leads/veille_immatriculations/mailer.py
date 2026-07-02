"""Envoi du résumé veille par email.

Squelette posé en Phase A ; la connexion SMTP réelle est branchée en Phase C
(quand on aura validé le pipeline manuellement). La fonction `envoyer_resume_veille`
est testable via la classe abstraite `EnvoyeurEmail` (mockable dans les tests).

Configuration via .env :
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=mon-compte@gmail.com
    SMTP_PASSWORD=<mot_de_passe_application>
    SMTP_DESTINATAIRES=paul@renoboost.fr,co@renoboost.fr   # CSV
    SMTP_FROM=veille-renoboost@gmail.com
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from ..common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConfigSMTP:
    host: str
    port: int
    user: str
    password: str
    expediteur: str
    destinataires: list[str]
    use_tls: bool = True


@dataclass
class ResumeVeille:
    date_run: str  # YYYY-MM-DD
    nb_lignes_brutes: int
    nb_ve_flotte: int
    nb_nouveaux: int
    nb_deja_vus: int
    nb_top_leads: int
    cout_l4_eur: float
    chemin_csv: Path
    extraits_top: list[dict[str, str]]  # liste de dicts {nom, siren, score, raison, pitch}


def _construire_message(config: ConfigSMTP, resume: ResumeVeille) -> EmailMessage:
    """Construit l'EmailMessage texte + HTML + pièce jointe CSV."""
    msg = EmailMessage()
    msg["Subject"] = (
        f"[RénoBoost] Veille VE flotte — {resume.date_run} "
        f"({resume.nb_top_leads} top leads)"
    )
    msg["From"] = config.expediteur
    msg["To"] = ", ".join(config.destinataires)

    texte = _construire_corps_texte(resume)
    html = _construire_corps_html(resume)
    msg.set_content(texte)
    msg.add_alternative(html, subtype="html")

    if resume.chemin_csv.exists():
        with resume.chemin_csv.open("rb") as fh:
            msg.add_attachment(
                fh.read(),
                maintype="text",
                subtype="csv",
                filename=resume.chemin_csv.name,
            )

    return msg


def _construire_corps_texte(r: ResumeVeille) -> str:
    lignes = [
        f"Veille immatriculations VE — RénoBoost — {r.date_run}",
        "─" * 60,
        f"Lignes AAA brutes      : {r.nb_lignes_brutes}",
        f"VE flotte entreprise    : {r.nb_ve_flotte}",
        f"  ↳ nouveaux SIREN      : {r.nb_nouveaux}",
        f"  ↳ déjà vus (flag)     : {r.nb_deja_vus}",
        f"Top leads (score ≥ 70) : {r.nb_top_leads}",
        f"Coût scoring L4         : {r.cout_l4_eur:.4f} €",
        f"CSV joint               : {r.chemin_csv.name}",
        "",
    ]
    if r.extraits_top:
        lignes.append("Aperçu top leads du jour :")
        for ex in r.extraits_top[:5]:
            lignes.append(
                f"  • {ex.get('nom', '?')} (SIREN {ex.get('siren', '?')}, "
                f"score {ex.get('score', '?')}) — {ex.get('raison', '')}"
            )
    return "\n".join(lignes)


def _construire_corps_html(r: ResumeVeille) -> str:
    extraits_html = ""
    if r.extraits_top:
        rows = "".join(
            f"<tr><td>{ex.get('nom', '?')}</td>"
            f"<td>{ex.get('siren', '?')}</td>"
            f"<td><b>{ex.get('score', '?')}</b></td>"
            f"<td>{ex.get('raison', '')}</td></tr>"
            for ex in r.extraits_top[:5]
        )
        extraits_html = (
            "<h3>Aperçu top leads</h3>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<tr><th>Nom</th><th>SIREN</th><th>Score</th><th>Raison</th></tr>"
            f"{rows}</table>"
        )
    return (
        "<html><body>"
        f"<h2>Veille VE flotte — {r.date_run}</h2>"
        "<ul>"
        f"<li>Lignes AAA brutes : <b>{r.nb_lignes_brutes}</b></li>"
        f"<li>VE flotte entreprise : <b>{r.nb_ve_flotte}</b> "
        f"(nouveaux : {r.nb_nouveaux} ; déjà vus : {r.nb_deja_vus})</li>"
        f"<li>Top leads (score ≥ 70) : <b>{r.nb_top_leads}</b></li>"
        f"<li>Coût scoring L4 : <b>{r.cout_l4_eur:.4f} €</b></li>"
        f"<li>CSV joint : <code>{r.chemin_csv.name}</code></li>"
        "</ul>"
        f"{extraits_html}"
        "</body></html>"
    )


def envoyer_message(config: ConfigSMTP, msg: EmailMessage) -> None:
    """Envoie un EmailMessage déjà construit via SMTP.

    Brique d'envoi générique partagée par la veille immatriculations et les
    parkings APER (qui construisent chacun leur propre corps de message).

    Raises:
        smtplib.SMTPException si l'envoi échoue.
    """
    with smtplib.SMTP(config.host, config.port, timeout=20) as smtp:
        if config.use_tls:
            smtp.starttls()
        smtp.login(config.user, config.password)
        smtp.send_message(msg)


def envoyer_resume_veille(config: ConfigSMTP, resume: ResumeVeille) -> None:
    """Envoie le résumé via SMTP. Phase A : non câblé au cron, testable seul.

    Raises:
        smtplib.SMTPException si l'envoi échoue.
    """
    msg = _construire_message(config, resume)
    envoyer_message(config, msg)

    logger.info(
        "Email veille envoyé à %d destinataires (%d top leads)",
        len(config.destinataires),
        resume.nb_top_leads,
    )
