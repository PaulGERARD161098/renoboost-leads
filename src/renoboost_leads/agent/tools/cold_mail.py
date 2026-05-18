"""Outils agent Phase B — cold mailing via Instantly avec staging N2.

Quatre outils :
- `stage_cold_emails(session_id, secteur, top_n, from_email, variables)` :
  drafte les emails pour les leads top N d'une session, les écrit dans
  staging, alerte l'utilisateur. PAS d'envoi tant que pas de validation.
- `list_stagings()` : liste les stagings en cours avec compteurs etats.
- `send_validated(staging_id)` : pousse vers Instantly UNIQUEMENT les
  items en état 'valide' (créé la campagne + add_leads). En dry-run
  (clé absente ou flag), simule l'envoi.
- `read_campaign_metrics(campaign_id)` : passe-plat vers Instantly.
- `pause_campaign(campaign_id)` : passe-plat vers Instantly.

L'agent ne peut PAS valider les emails lui-même — c'est la garantie N2.
Il propose, l'humain valide via Streamlit ou `cold-mail validate`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ...instantly.client import InstantlyClient, InstantlyError
from ...instantly.sequences import load_sequence
from ...instantly.staging import (
    StagedItem,
    Staging,
    StagingStore,
    nouveau_staging_id,
)
from .leads import prioritize_leads
from .notify import alert_human


def stage_cold_emails(
    session_id: str,
    secteur: str,
    top_n: int = 10,
    from_email: str = "paul@renoboost.fr",
    variables_globales: dict | None = None,
) -> dict:
    """Drafte les emails step 1 pour les top N leads et écrit en staging."""
    try:
        sequence = load_sequence(secteur)
    except (FileNotFoundError, ValueError) as e:
        return {"error": f"séquence '{secteur}' indisponible : {e}"}

    priorisation = prioritize_leads(session_id, top_n=top_n)
    if "error" in priorisation:
        return priorisation
    leads_top = priorisation.get("top", [])
    leads_avec_email = [
        lead for lead in leads_top if lead.get("email")
    ]
    if not leads_avec_email:
        return {
            "session_id": session_id,
            "warning": "aucun lead avec email parmi le top N — rien à stager",
            "top_total": len(leads_top),
        }

    gl = variables_globales or {}
    items = []
    for lead in leads_avec_email:
        variables = {
            "civilite": "",
            "prenom": _premiere_partie(lead.get("dirigeant") or "") or "",
            "nom_dirigeant": lead.get("dirigeant") or "",
            "nom_entreprise": lead.get("nom") or "",
            **gl,
        }
        rendu = sequence.render_step(1, variables)
        items.append(
            StagedItem(
                lead_id=lead.get("siren") or lead.get("email") or "?",
                email_dest=lead["email"],
                nom_dest=lead.get("dirigeant") or lead.get("nom") or "",
                sujet=rendu.sujet,
                corps=rendu.corps,
            )
        )

    staging = Staging(
        staging_id=nouveau_staging_id(),
        secteur=secteur,
        session_id=session_id,
        from_email=from_email,
        items=items,
    )
    StagingStore().save(staging)

    # Alerte l'utilisateur (best-effort, ne plante pas si SMTP off)
    notify_res = alert_human(
        subject=f"Cold mail prêt à valider — {len(items)} email(s) {secteur}",
        body=(
            f"L'agent a draftté {len(items)} emails cold mail pour la "
            f"session {session_id} (secteur : {secteur}).\n\n"
            f"Staging ID : {staging.staging_id}\n\n"
            f"Valide ou refuse les emails via :\n"
            f"- CLI : renoboost-leads cold-mail validate "
            f"--staging-id {staging.staging_id}\n"
            f"- Streamlit : onglet Copilote → section Staging\n\n"
            f"Tant qu'aucun item n'est validé, rien ne part dans Instantly."
        ),
        urgency="attention",
    )

    return {
        "staging_id": staging.staging_id,
        "secteur": secteur,
        "session_id": session_id,
        "from_email": from_email,
        "items_count": len(items),
        "items_sans_email_ignores": len(leads_top) - len(leads_avec_email),
        "alert_sent": notify_res.get("sent"),
        "alert_reason": notify_res.get("reason"),
        "next_action": (
            "Demande à l'utilisateur de valider via la CLI ou Streamlit. "
            "Rien n'est envoyé tant qu'aucun item n'est en état 'valide'."
        ),
    }


def list_stagings() -> dict:
    """Renvoie la liste résumée des stagings."""
    items = StagingStore().list()
    return {"count": len(items), "stagings": items}


def send_validated(staging_id: str) -> dict:
    """Pousse les items 'valide' vers Instantly (crée campagne + add_leads).

    Les items déjà 'envoye' sont ignorés (idempotent). Les items 'en_attente'
    ou 'refuse' ne sont jamais envoyés.
    """
    store = StagingStore()
    try:
        staging = store.load(staging_id)
    except FileNotFoundError as e:
        return {"error": str(e)}

    a_envoyer = [i for i in staging.items if i.etat == "valide"]
    if not a_envoyer:
        return {
            "staging_id": staging_id,
            "warning": "aucun item en état 'valide' — rien à envoyer",
            "compteurs": _compteurs(staging),
        }

    client = InstantlyClient()
    try:
        campagne = client.create_campaign(
            name=f"renoboost-{staging.secteur}-{staging.staging_id}",
            from_email=staging.from_email,
        )
        campaign_id = campagne["id"]
        leads_payload = [
            {
                "email": i.email_dest,
                "first_name": i.nom_dest.split(" ", 1)[0] if i.nom_dest else "",
                "last_name": (
                    i.nom_dest.split(" ", 1)[1] if " " in i.nom_dest else ""
                ),
                "personalization_subject": i.sujet,
                "personalization_body": i.corps,
            }
            for i in a_envoyer
        ]
        ajout = client.add_leads(campaign_id, leads_payload)
    except InstantlyError as e:
        return {"error": f"Instantly : {e!s}"}

    # Marque les items comme envoyés
    horodatage = datetime.now(timezone.utc).isoformat()
    for item in a_envoyer:
        item.etat = "envoye"
        item.decide_le = horodatage
        item.campagne_instantly_id = campaign_id
    store.save(staging)

    return {
        "staging_id": staging_id,
        "campaign_id": campaign_id,
        "envoyes": len(a_envoyer),
        "dry_run": bool(client.is_dry_run()),
        "ajout_payload": ajout,
        "compteurs": _compteurs(staging),
    }


def read_campaign_metrics(campaign_id: str) -> dict:
    """Récupère les métriques (envoyés/ouverts/répondus/bounce) d'une campagne."""
    client = InstantlyClient()
    try:
        return client.get_campaign_metrics(campaign_id)
    except InstantlyError as e:
        return {"error": f"Instantly : {e!s}"}


def pause_campaign(campaign_id: str) -> dict:
    """Met une campagne en pause (interrompt les envois futurs)."""
    client = InstantlyClient()
    try:
        return client.pause_campaign(campaign_id)
    except InstantlyError as e:
        return {"error": f"Instantly : {e!s}"}


# ─── Helpers ──────────────────────────────────────────────────────


def _premiere_partie(s: str) -> str:
    return s.split(" ", 1)[0] if s else ""


def _compteurs(staging: Staging) -> dict:
    d: dict = {}
    for i in staging.items:
        d[i.etat] = d.get(i.etat, 0) + 1
    return d


# ─── Schémas tool-use ─────────────────────────────────────────────


SCHEMAS = [
    {
        "name": "stage_cold_emails",
        "description": (
            "Drafte les emails cold mail (step 1) pour les top N leads "
            "d'une session, les écrit dans staging et alerte l'utilisateur. "
            "Aucun envoi tant que pas de validation humaine (workflow N2). "
            "Secteur ∈ compta, avocats, immo, com, be."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "secteur": {
                    "type": "string",
                    "enum": ["compta", "avocats", "immo", "com", "be"],
                },
                "top_n": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
                "from_email": {
                    "type": "string",
                    "description": "Email d'expédition (doit être configuré dans Instantly).",
                    "default": "paul@renoboost.fr",
                },
                "variables_globales": {
                    "type": "object",
                    "description": (
                        "Variables injectées dans le template "
                        "(ex {telephone_paul: '06...', lien_calendly: '...'})."
                    ),
                },
            },
            "required": ["session_id", "secteur"],
        },
    },
    {
        "name": "list_stagings",
        "description": (
            "Liste les stagings cold mail en cours (compteurs par état : "
            "en_attente, valide, refuse, envoye)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_validated",
        "description": (
            "Crée une campagne Instantly et y pousse UNIQUEMENT les items "
            "marqués 'valide' par l'utilisateur. Les autres sont ignorés. "
            "Idempotent : les 'envoye' ne sont pas renvoyés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"staging_id": {"type": "string"}},
            "required": ["staging_id"],
        },
    },
    {
        "name": "read_campaign_metrics",
        "description": (
            "Métriques d'une campagne Instantly (envoyés, ouverts, clics, "
            "répondus, bounce)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "string"}},
            "required": ["campaign_id"],
        },
    },
    {
        "name": "pause_campaign",
        "description": "Met une campagne Instantly en pause (envois futurs interrompus).",
        "input_schema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "string"}},
            "required": ["campaign_id"],
        },
    },
]

DISPATCH = {
    "stage_cold_emails": stage_cold_emails,
    "list_stagings": list_stagings,
    "send_validated": send_validated,
    "read_campaign_metrics": read_campaign_metrics,
    "pause_campaign": pause_campaign,
}
