"""Outils `alert_human` et `email_report` — envoi email via SMTP existant.

Réutilise la config SMTP_* déjà présente (Settings.has_smtp). Si SMTP
non configuré, les outils renvoient un statut "non envoyé" mais ne
lèvent pas : en local sans SMTP, l'agent est juste informé que
l'utilisateur ne sera pas notifié et continue.

`alert_human` : message texte simple, 3 niveaux d'urgence.
`email_report` : envoie le rapport HTML d'une session en pièce jointe au
                 client (ou à Paul). Génère le rapport si absent.
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


def _connect_and_send(msg: EmailMessage, settings) -> tuple[bool, str | None]:  # type: ignore[no-untyped-def]
    """Connexion SMTP + envoi. Renvoie (succès, raison_si_echec)."""
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            if settings.smtp_use_tls:
                s.starttls()
            s.login(
                settings.smtp_user, settings.smtp_password.get_secret_value()
            )
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        return False, f"erreur SMTP : {e!s}"
    return True, None


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

    ok, raison = _connect_and_send(msg, settings)
    if not ok:
        return {"sent": False, "reason": raison}

    return {
        "sent": True,
        "destinataires": dests,
        "subject": msg["Subject"],
        "urgency": urgency,
    }


def email_report(
    session_id: str,
    destinataires: list[str],
    subject: str | None = None,
    message: str | None = None,
    regenerer: bool = False,
) -> dict:
    """Envoie le rapport HTML d'une session par email (en pièce jointe).

    Args:
        session_id: identifiant de session.
        destinataires: liste d'emails (au moins 1).
        subject: objet personnalisé (défaut : « Rapport prospection — <session> »).
        message: corps texte personnalisé (défaut : message standard).
        regenerer: force la régénération du rapport même si rapport.html existe.

    Returns:
        Dict avec `sent`, `destinataires`, `attachment_bytes`, `subject`,
        ou `error`.
    """
    if not destinataires:
        return {"error": "destinataires vide — fournis au moins 1 email."}
    bad = [d for d in destinataires if "@" not in d]
    if bad:
        return {"error": f"emails invalides : {bad}"}

    # Import paresseux pour éviter les boucles d'import si report importe notify
    from ...settings import PROJECT_ROOT
    from .report import generate_report
    from .sessions import OUTPUT_ROOT

    rapport_path = OUTPUT_ROOT / session_id / "rapport.html"
    if regenerer or not rapport_path.exists():
        gen_res = generate_report(session_id)
        if "error" in gen_res:
            return {"error": f"impossible de générer le rapport : {gen_res['error']}"}
        # Recalcule le chemin (generate_report peut écrire ailleurs si override)
        candidat = PROJECT_ROOT / gen_res["path"]
        if candidat.exists():
            rapport_path = candidat

    if not rapport_path.exists():
        return {"error": f"rapport introuvable : {rapport_path}"}

    settings = get_settings()
    if not settings.has_smtp():
        return {
            "sent": False,
            "reason": (
                "SMTP non configuré (renseigne SMTP_HOST/USER/PASSWORD/FROM)."
            ),
            "rapport_path": str(
                rapport_path.relative_to(PROJECT_ROOT)
                if PROJECT_ROOT in rapport_path.parents
                else rapport_path
            ),
            "destinataires_qu_auraient_recu": destinataires,
        }

    subject_final = subject or f"Rapport prospection RénoBoost — {session_id}"
    body_final = message or (
        "Bonjour,\n\n"
        "Vous trouverez en pièce jointe le rapport de prospection pour "
        f"la session {session_id}.\n\n"
        "Le rapport est au format HTML autonome — ouvrez-le dans votre "
        "navigateur, et utilisez Ctrl+P → Enregistrer en PDF si besoin.\n\n"
        "Cordialement,\nRénoBoost Leads"
    )

    msg = EmailMessage()
    msg["Subject"] = subject_final
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(destinataires)
    msg.set_content(body_final)

    html_bytes = rapport_path.read_bytes()
    msg.add_attachment(
        html_bytes,
        maintype="text",
        subtype="html",
        filename=f"rapport_{session_id}.html",
    )

    ok, raison = _connect_and_send(msg, settings)
    if not ok:
        return {"sent": False, "reason": raison}

    return {
        "sent": True,
        "destinataires": destinataires,
        "subject": subject_final,
        "attachment_bytes": len(html_bytes),
        "rapport_path": str(
            rapport_path.relative_to(PROJECT_ROOT)
            if PROJECT_ROOT in rapport_path.parents
            else rapport_path
        ),
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
    },
    {
        "name": "email_report",
        "description": (
            "Envoie le rapport HTML d'une session en pièce jointe par "
            "email. Si le rapport n'existe pas encore, le génère "
            "automatiquement via generate_report. Utilise la config SMTP "
            "standard (Settings). Use case : « envoie le rapport de la "
            "session XYZ à client@example.com »."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Identifiant de la session.",
                },
                "destinataires": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste d'emails (au moins 1).",
                },
                "subject": {
                    "type": "string",
                    "description": "Objet personnalisé (optionnel).",
                },
                "message": {
                    "type": "string",
                    "description": "Corps texte personnalisé (optionnel).",
                },
                "regenerer": {
                    "type": "boolean",
                    "description": (
                        "Force la régénération du rapport HTML même s'il "
                        "existe déjà. Défaut false."
                    ),
                    "default": False,
                },
            },
            "required": ["session_id", "destinataires"],
        },
    },
]

DISPATCH = {"alert_human": alert_human, "email_report": email_report}
