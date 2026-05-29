"""Template de prompt pour le scoring Claude (étage 4).

Le prompt est versionné (`PROMPT_VERSION`). Tout changement de version
invalide automatiquement les entrées de cache (cf. `cache.py`).
"""

from __future__ import annotations

from ..models import LeadStage3

# Bump ce numéro à chaque modification du prompt (structure, instructions, JSON shape).
# Le cache L4 utilise cette valeur comme partie de sa clé de hachage.
PROMPT_VERSION = "v3"


CONTEXTE_CLIENT_DEFAUT = """\
RénoBoost — entreprise de rénovation énergétique B2B (France).
Offre : audit + rénovation thermique de bâtiments tertiaires (bureaux,
hôtels, restaurants, ateliers industriels) avec financement CEE.

Profil idéal (ICP) :
- TPE/PME 10-250 salariés, multi-établissements bienvenus
- Bâtiments anciens (avant 2005), consommation énergétique élevée
- Décideur identifié (dirigeant ou DAF)
- Pas une chaîne nationale (décision centralisée hors zone)

Critères de désintérêt :
- Pure entreprise de service sans patrimoine bâti (cabinet conseil etc.)
- Locaux loués où le bailleur décide des travaux
- Très petites structures (< 5 salariés) sans capex
"""


def _format_emails(emails: list[str], limite: int = 3) -> str:
    """Retourne un résumé compact d'une liste d'emails."""
    if not emails:
        return "aucun"
    affiches = emails[:limite]
    suite = f" (+{len(emails) - limite} autres)" if len(emails) > limite else ""
    return ", ".join(affiches) + suite


def construire_prompt(
    lead: LeadStage3,
    contexte_client: str | None = None,
    inclure_pitch: bool = True,
) -> str:
    """Construit le prompt utilisateur envoyé à Claude pour un lead.

    Le prompt :
    - Fournit le contexte client en tête (`contexte_client` ou défaut).
    - Décrit le lead avec uniquement les champs renseignés (pas de "None").
    - Demande une réponse JSON stricte avec score / raison / (pitch).

    Args:
        lead: lead L3 à scorer
        contexte_client: contexte de l'offre commerciale. None = défaut RénoBoost.
        inclure_pitch: si False, le prompt n'exige pas le champ pitch_propose.

    Returns:
        Chaîne de texte (rôle "user").
    """
    ctx = contexte_client or CONTEXTE_CLIENT_DEFAUT

    # Description du lead : on n'envoie que les champs renseignés
    lignes_lead: list[str] = []
    if lead.nom:
        lignes_lead.append(f"- Nom : {lead.nom}")
    if lead.code_naf or lead.libelle_naf:
        naf = f"{lead.code_naf or ''} {lead.libelle_naf or ''}".strip()
        lignes_lead.append(f"- Activité (NAF) : {naf}")
    if lead.forme_juridique:
        lignes_lead.append(f"- Forme juridique : {lead.forme_juridique}")
    if lead.libelle_effectif or lead.tranche_effectif:
        eff = lead.libelle_effectif or f"tranche INSEE {lead.tranche_effectif}"
        lignes_lead.append(f"- Effectif : {eff}")
    if lead.nb_etablissements:
        lignes_lead.append(f"- Nombre d'établissements : {lead.nb_etablissements}")
    if lead.date_creation:
        lignes_lead.append(f"- Date de création : {lead.date_creation}")
    if lead.ville and lead.code_postal:
        lignes_lead.append(f"- Localisation : {lead.code_postal} {lead.ville}")
    elif lead.ville:
        lignes_lead.append(f"- Localisation : {lead.ville}")
    if lead.dirigeant_nom or lead.dirigeant_prenom:
        dir_nom = " ".join(
            x for x in (lead.dirigeant_prenom, lead.dirigeant_nom) if x
        )
        qualite = f" ({lead.dirigeant_qualite})" if lead.dirigeant_qualite else ""
        lignes_lead.append(f"- Dirigeant principal : {dir_nom}{qualite}")
    if lead.note is not None and lead.nb_avis:
        lignes_lead.append(f"- Note Google : {lead.note}/5 ({lead.nb_avis} avis)")
    if lead.site_web:
        lignes_lead.append(f"- Site web : {lead.site_web}")
    if lead.emails_verifies:
        lignes_lead.append(
            f"- Emails publics (scrapés) : {_format_emails(lead.emails_verifies)}"
        )
    if lead.flag_chaine:
        lignes_lead.append(
            f"- ⚠ Chaîne nationale détectée ({lead.note_chaine or 'décision centralisée probable'})"
        )
    if lead.hors_filtre_entreprise:
        lignes_lead.append(
            f"- ⚠ Hors filtre entreprise : {lead.raison_hors_filtre or 'critères non remplis'}"
        )
    if lead.signaux_ve:
        lignes_lead.append(
            f"- 🔋 Signaux flotte / véhicule électrique détectés : {', '.join(lead.signaux_ve)}"
        )

    desc_lead = "\n".join(lignes_lead) if lignes_lead else "- (aucune donnée enrichie)"

    if inclure_pitch:
        format_json = (
            '{\n'
            '  "score_interet": <entier 0-100>,\n'
            '  "raison_score": "<une seule phrase courte en français>",\n'
            '  "pitch_propose": "<2 à 3 lignes d\'accroche téléphone en français>",\n'
            '  "email_objet": "<objet d\'email court et accrocheur, en français>",\n'
            '  "email_corps": "<email complet prêt à envoyer, en français>"\n'
            '}'
        )
        regles = (
            "1. `score_interet` : 0-100 (0 = aucun intérêt, 100 = lead idéal).\n"
            "2. `raison_score` : UNE phrase, en français, qui justifie le score.\n"
            "3. `pitch_propose` : 2-3 lignes max, ton pro, accroche pour un appel. "
            "Pas de signature ni d'objet.\n"
            "4. `email_objet` : objet d'email court (≤ 70 caractères), spécifique au lead, "
            "sans majuscules criardes ni spam.\n"
            "5. `email_corps` : email B2B complet et personnalisé, prêt à envoyer, structuré : "
            "formule d'appel (utilise le nom du dirigeant si fourni, sinon « Madame, Monsieur »), "
            "2-3 paragraphes courts reliant l'offre au profil du lead (activité, taille, bâti), "
            "un appel à l'action clair (proposer un échange de 15 min), puis une signature "
            "« Cordialement, » suivie du nom de l'entreprise émettrice (issu de l'offre "
            "commerciale ci-dessus). Sauts de ligne encodés en \\n.\n"
            "6. Aucune invention de chiffres (CA, économies, montants CEE) ni de fausse "
            "référence client. Reste factuel et sobre.\n"
            "7. Si des signaux flotte / véhicule électrique sont détectés, traite-les "
            "comme un indicateur d'achat POSITIF uniquement s'ils sont pertinents pour "
            "l'offre commerciale ci-dessus (ex. ombrières, bornes IRVE, transition "
            "énergétique) ; sinon ignore-les. N'invente aucun signal absent."
        )
    else:
        format_json = (
            '{\n'
            '  "score_interet": <entier 0-100>,\n'
            '  "raison_score": "<une seule phrase courte en français>"\n'
            '}'
        )
        regles = (
            "1. `score_interet` : 0-100 (0 = aucun intérêt, 100 = lead idéal).\n"
            "2. `raison_score` : UNE phrase, en français, qui justifie le score.\n"
            "3. Si des signaux flotte / véhicule électrique sont détectés, traite-les "
            "comme un indicateur d'achat POSITIF uniquement s'ils sont pertinents pour "
            "l'offre commerciale ci-dessus ; sinon ignore-les."
        )

    return (
        "Tu es un analyste commercial B2B. Tu dois évaluer un lead par rapport "
        "à une offre commerciale donnée, et répondre EXCLUSIVEMENT en JSON valide "
        "(rien avant, rien après).\n\n"
        f"# Offre commerciale\n{ctx}\n\n"
        f"# Lead à évaluer\n{desc_lead}\n\n"
        f"# Format de sortie attendu (JSON strict)\n{format_json}\n\n"
        f"# Règles\n{regles}\n"
    )
