"""Outil `alert_human` — envoi email via SMTP existant (Settings).

Réutilise la config SMTP_* déjà présente (Settings.has_smtp). Si SMTP
non configuré, l'outil renvoie un statut "non envoyé" mais ne lève pas :
en local sans SMTP, l'agent est juste informé que l'utilisateur ne sera
pas notifié et continue.

Trois niveaux d'urgence :
- info : préfixe "[Copilote] INFO"
- attention : préfixe "[Copilote] ⚠ ATTENTION"
- urgent : préfixe "[Copilote] 🚨 URGENT"
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ...settings import get_settings

URGENCE_PREFIXES = {
    "info": "[Copilote] INFO",
    "attention": "[Copilote] ⚠ ATTENTION",
    "urgent": "[Copilote] 🚨 URGENT",
}


def alert_human(
    subject: str, body: str, urgency: str = "info", destinataires: list[str] | None = None
) -> dict:
    """Envoie un email d'alerte à l'utilisateur. Idempotent côté Settings."""
    if urgency not in URGENCE_PREFIXES:
        return {"error": f"urgence invalide : '{urgency}'. Valides : {list(URGENCE_PREFIXES)}"}
    if not subject or not body:
        return {"error": "subject et body sont obligatoires"}

    settings = get_settings()
    if not settings.has_smtp():
        return {
            "sent": False,
            "reason": "SMTP non configuré (renseigne SMTP_HOST/USER/PASSWORD/FROM/DESTINATAIRES).",
            "subject_qu_aurait_ete_envoye": f"{URGENCE_PREFIXES[urgency]} — {subject}",
        }

    dests = destinataires or settings.smtp_destinataires_list()
    if not dests:
        return {"sent": False, "reason": "aucun destinataire (SMTP_DESTINATAIRES vide)."}

    msg = EmailMessage()
    msg["Subject"] = f"{URGENCE_PREFIXES[urgency]} — {subject}"
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(dests)
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            if settings.smtp_use_tls:
                s.starttls()
            s.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        return {"sent": False, "reason": f"erreur SMTP : {e!s}"}

    return {
        "sent": True,
        "destinataires": dests,
        "subject": msg["Subject"],
        "urgency": urgency,
    }


SCHEMAS = [
    {
        "name": "alert_human",
        "description": (
            "Envoie un email d'alerte à Paul (RénoBoost) via SMTP. Trois "
            "niveaux : 'info' (récap), 'attention' (validation requise), "
            "'urgent' (incident). Si SMTP n'est pas configuré, renvoie un "
            "statut 'non envoyé' sans erreur — utile en local pour tester."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Objet de l'email."},
                "body": {"type": "string", "description": "Corps texte brut."},
                "urgency": {
                    "type": "string",
                    "enum": list(URGENCE_PREFIXES.keys()),
                    "default": "info",
                },
                "destinataires": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optionnel — surcharge SMTP_DESTINATAIRES.",
                },
            },
            "required": ["subject", "body"],
        },
    }
]

DISPATCH = {"alert_human": alert_human}
