"""Export CSV des leads (étages 1, 2, 3) + sauvegardes horodatées."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from .common.logger import get_logger
from .models import LeadStage1, LeadStage2, LeadStage3, LeadStage4, LeadStage35, RunStats

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════
# Schémas de colonnes
# ════════════════════════════════════════════════════════════════

COLONNES_STAGE1 = [
    "place_id",
    "nom",
    "adresse",
    "ville",
    "code_postal",
    "pays",
    "telephone",
    "site_web",
    "note",
    "nb_avis",
    "type_principal",
    "types",
    "statut_business",
    "niveau_prix",
    "latitude",
    "longitude",
    "google_maps_url",
    "secteur_recherche",
    "requete_origine",
    "extraction_date",
]

COLONNES_STAGE2 = COLONNES_STAGE1 + [
    "siren",
    "siret",
    "code_naf",
    "libelle_naf",
    "forme_juridique",
    "statut_actif",
    "tranche_effectif",
    "libelle_effectif",
    "dirigeant_nom",
    "dirigeant_prenom",
    "dirigeant_qualite",
    "adresse_normalisee",
    "date_creation",
    "nb_etablissements",
    "score_matching",
    "match_incertain",
    "flag_chaine",
    "note_chaine",
    "hors_filtre_entreprise",
    "raison_hors_filtre",
]

COLONNES_STAGE3 = COLONNES_STAGE2 + [
    "emails_verifies",
    "emails_candidats",
    "domaine_extrait",
    "page_source_emails",
    "nb_emails_verifies",
    "nb_emails_candidats",
    "source_globale",
    "contient_dirigeant_pattern",
]

COLONNES_STAGE3_5 = COLONNES_STAGE3 + [
    "email_dropcontact",
    "qualification_email_dropcontact",
    "telephone_direct_dropcontact",
    "linkedin_dirigeant_dropcontact",
    "linkedin_entreprise_dropcontact",
    "civilite_dirigeant_dropcontact",
    "prenom_dirigeant_dropcontact",
    "nom_dirigeant_dropcontact",
    "enrichi_dropcontact",
    "enrichissement_erreur",
    "cout_enrichissement_eur",
]

COLONNES_STAGE4 = COLONNES_STAGE3_5 + [
    "score_interet",
    "raison_score",
    "pitch_propose",
    "top_lead",
    "scoring_modele",
    "scoring_erreur",
]

# Vue "exportable" pour CRM / démarchage : colonnes utiles sans bruit interne.
COLONNES_EXPORT_CRM = [
    "nom",
    "siren",
    "code_naf",
    "libelle_naf",
    "tranche_effectif",
    "ville",
    "code_postal",
    "site_web",
    "telephone",
    "telephone_direct_dropcontact",
    "civilite_dirigeant_dropcontact",
    "prenom_dirigeant_dropcontact",
    "nom_dirigeant_dropcontact",
    "email_dropcontact",
    "qualification_email_dropcontact",
    "linkedin_dirigeant_dropcontact",
    "linkedin_entreprise_dropcontact",
    "emails_verifies",
    "emails_candidats",
    "score_interet",
    "raison_score",
    "pitch_propose",
    "top_lead",
    "google_maps_url",
]


# ════════════════════════════════════════════════════════════════
# Helpers de sérialisation
# ════════════════════════════════════════════════════════════════


def _serialize_value(val):
    """Sérialise un champ pour le CSV (listes → 'a|b|c', date → ISO)."""
    if val is None:
        return ""
    if isinstance(val, list):
        return "|".join(str(x) for x in val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bool):
        return "VRAI" if val else "FAUX"
    return val


# ════════════════════════════════════════════════════════════════
# Exports CSV
# ════════════════════════════════════════════════════════════════


def _ecrire_csv(rows: list[dict], colonnes: list[str], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=colonnes, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            sanitized = {k: _serialize_value(row.get(k)) for k in colonnes}
            writer.writerow(sanitized)
    return output_path


def export_stage1_csv(leads: list[LeadStage1], output_path: Path) -> Path:
    """CSV étage 1."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_STAGE1, output_path)
    logger.info("CSV étage 1 écrit : %s (%d leads)", p, len(leads))
    return p


def export_stage2_csv(leads: list[LeadStage2], output_path: Path) -> Path:
    """CSV étage 2 (= étage 1 + colonnes Pappers/data.gouv.fr)."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_STAGE2, output_path)
    logger.info("CSV étage 2 écrit : %s (%d leads)", p, len(leads))
    return p


def export_stage3_csv(leads: list[LeadStage3], output_path: Path) -> Path:
    """CSV étage 3 (= étage 1 + 2 + colonnes contacts)."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_STAGE3, output_path)
    logger.info("CSV étage 3 écrit : %s (%d leads)", p, len(leads))
    return p


def export_stage3_5_csv(leads: list[LeadStage35], output_path: Path) -> Path:
    """CSV étage 3.5 (= étage 1+2+3 + enrichissement Dropcontact)."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_STAGE3_5, output_path)
    logger.info("CSV étage 3.5 écrit : %s (%d leads)", p, len(leads))
    return p


def export_csv_crm(leads: list, output_path: Path) -> Path:
    """Export 'exportable' : colonnes utiles pour démarchage / import CRM.

    Accepte n'importe quelle famille de leads (L3 / L3.5 / L4). Les colonnes
    manquantes deviennent des cases vides.
    """
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_EXPORT_CRM, output_path)
    logger.info("CSV exportable CRM écrit : %s (%d leads)", p, len(leads))
    return p


def export_stage4_csv(leads: list[LeadStage4], output_path: Path) -> Path:
    """CSV étage 4 (= étage 1+2+3 + scoring/pitch Claude)."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_STAGE4, output_path)
    logger.info("CSV étage 4 écrit : %s (%d leads)", p, len(leads))
    return p


def export_stage3_csv_separe_hors_filtre(
    leads: list[LeadStage3], output_path: Path
) -> tuple[Path, Path | None]:
    """Export L3 séparant qualifiés et hors-filtre (B3 "pas de mélange").

    Si aucun lead n'est flagué `hors_filtre_entreprise`, n'écrit qu'un seul
    CSV (= comportement historique). Sinon écrit aussi
    `<output_path.stem>_hors_filtre<suffix>` avec les leads flagués.

    Returns:
        (chemin_qualifies, chemin_hors_filtre_ou_None)
    """
    qualifies = [lead for lead in leads if not lead.hors_filtre_entreprise]
    hors_filtre = [lead for lead in leads if lead.hors_filtre_entreprise]

    p_main = _ecrire_csv([lead.model_dump() for lead in qualifies], COLONNES_STAGE3, output_path)
    logger.info("CSV étage 3 (qualifiés) écrit : %s (%d leads)", p_main, len(qualifies))

    if not hors_filtre:
        return p_main, None

    hf_path = output_path.with_name(f"{output_path.stem}_hors_filtre{output_path.suffix}")
    p_hf = _ecrire_csv([lead.model_dump() for lead in hors_filtre], COLONNES_STAGE3, hf_path)
    logger.info(
        "CSV étage 3 (hors filtre entreprise) écrit : %s (%d leads)", p_hf, len(hors_filtre)
    )
    return p_main, p_hf


# ════════════════════════════════════════════════════════════════
# Backup horodaté
# ════════════════════════════════════════════════════════════════


def backup_csv(csv_path: Path) -> Path | None:
    """Copie le CSV dans <output>/backups/ avec un timestamp."""
    if not csv_path.exists():
        return None
    backup_dir = csv_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"{csv_path.stem}_{timestamp}{csv_path.suffix}"
    target = backup_dir / backup_name
    try:
        shutil.copy2(csv_path, target)
        logger.debug("Backup créé : %s", target)
        return target
    except Exception as e:  # noqa: BLE001
        logger.warning("Échec backup %s : %s", csv_path, e)
        return None


# ════════════════════════════════════════════════════════════════
# Stats run
# ════════════════════════════════════════════════════════════════


def export_run_stats(stats: RunStats, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(stats.model_dump(mode="json"), fh, ensure_ascii=False, indent=2, default=str)
    return output_path


# ════════════════════════════════════════════════════════════════
# Registre RGPD
# ════════════════════════════════════════════════════════════════


def generer_registre_rgpd(
    output_path: Path,
    client_name: str,
    nb_leads: int,
    sources: list[str],
    etages_executes: list[int],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    contenu = f"""# Registre des traitements — Run RénoBoost Leads

**Date** : {datetime.now().isoformat()}
**Client / Campagne** : {client_name}
**Étages exécutés** : {", ".join(f"L{i}" for i in etages_executes)}
**Nombre de leads finaux** : {nb_leads}

## Sources des données
{chr(10).join(f"- {s}" for s in sources)}

## Finalité du traitement
Prospection commerciale B2B (article 6.1.f RGPD — intérêt légitime).

## Catégories de personnes concernées
- Personnes morales (entreprises, établissements)
- Le cas échéant, contacts professionnels génériques (`contact@`, `direction@`)
- Le cas échéant, dirigeants identifiés via le registre du commerce (donnée publique)

## Catégories de données traitées
- Identification entreprise (raison sociale, adresse, téléphone, site web)
- Métadonnées Google Places (note, nb avis, catégories)
- Données légales (SIREN, NAF, dirigeants) — étage 2
- Emails professionnels — étage 3 (mentions légales publiques + patterns)

## Durée de conservation
3 ans à compter du dernier contact (recommandation CNIL — prospection B2B).

## Mesures de sécurité
- Données stockées en local, pas de transmission vers des tiers non autorisés
- Clés API en variables d'environnement (jamais en clair dans le code)
- Restriction par adresses IP des accès aux APIs Google
- User-Agent identifiable lors du scraping de mentions légales (transparence)
- robots.txt respecté

## Droits des personnes
Toute personne dont les données figurent dans ce fichier peut exercer ses droits
(accès, rectification, effacement, opposition) en contactant le responsable de traitement.
"""
    output_path.write_text(contenu, encoding="utf-8")
    return output_path


# ════════════════════════════════════════════════════════════════
# Lecture CSV (pour reprendre L2/L3 sur un CSV L1 existant)
# ════════════════════════════════════════════════════════════════


def lire_stage1_csv(csv_path: Path) -> list[LeadStage1]:
    """Re-charge un CSV L1 vers des LeadStage1."""
    if not csv_path.exists():
        parent = csv_path.parent
        if not parent.exists():
            raise FileNotFoundError(f"Dossier de session introuvable : {parent}")
        autres = sorted(f.name for f in parent.iterdir() if f.is_file())
        if not autres:
            raise FileNotFoundError(f"CSV étage 1 introuvable (dossier vide) : {csv_path}")
        raise FileNotFoundError(
            f"CSV étage 1 introuvable : {csv_path}\n"
            f"Fichiers presents dans le dossier : {', '.join(autres)}"
        )

    leads: list[LeadStage1] = []
    with csv_path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Reconvertir les types
            data = dict(row)
            # types: liste séparée par |
            types_str = data.get("types") or ""
            data["types"] = [t for t in types_str.split("|") if t] if types_str else []
            # numériques
            for col in ("note", "latitude", "longitude"):
                v = data.get(col)
                data[col] = float(v) if v not in (None, "", "None") else None
            for col in ("nb_avis", "niveau_prix"):
                v = data.get(col)
                data[col] = int(v) if v not in (None, "", "None") else None
            # date
            ed = data.get("extraction_date")
            if ed:
                try:
                    data["extraction_date"] = datetime.fromisoformat(ed)
                except ValueError:
                    data["extraction_date"] = datetime.now()
            else:
                data["extraction_date"] = datetime.now()
            # vide → None pour str
            for col in (
                "adresse",
                "ville",
                "code_postal",
                "pays",
                "telephone",
                "site_web",
                "type_principal",
                "statut_business",
                "google_maps_url",
                "secteur_recherche",
                "requete_origine",
            ):
                if data.get(col) == "":
                    data[col] = None
            try:
                leads.append(LeadStage1.model_validate(data))
            except Exception as e:  # noqa: BLE001
                logger.warning("Ligne CSV invalide ignorée : %s", e)
    logger.info("CSV étage 1 lu : %d leads depuis %s", len(leads), csv_path)
    return leads


def lire_stage2_csv(csv_path: Path) -> list[LeadStage2]:
    """Re-charge un CSV L2 vers des LeadStage2."""
    leads_l1 = lire_stage1_csv(csv_path)  # L2 contient toutes les colonnes L1

    # On relit pour récupérer aussi les colonnes L2
    with csv_path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    leads_l2: list[LeadStage2] = []
    for l1, row in zip(leads_l1, rows, strict=False):
        score = row.get("score_matching")
        match_incertain_raw = row.get("match_incertain") or ""
        flag_chaine_raw = row.get("flag_chaine") or ""
        statut_actif_raw = row.get("statut_actif") or ""
        nb_etabs_raw = row.get("nb_etablissements") or ""
        hors_filtre_raw = row.get("hors_filtre_entreprise") or ""

        leads_l2.append(
            LeadStage2(
                **l1.model_dump(),
                siren=row.get("siren") or None,
                siret=row.get("siret") or None,
                code_naf=row.get("code_naf") or None,
                libelle_naf=row.get("libelle_naf") or None,
                forme_juridique=row.get("forme_juridique") or None,
                statut_actif=(statut_actif_raw == "VRAI") if statut_actif_raw else None,
                tranche_effectif=row.get("tranche_effectif") or None,
                libelle_effectif=row.get("libelle_effectif") or None,
                dirigeant_nom=row.get("dirigeant_nom") or None,
                dirigeant_prenom=row.get("dirigeant_prenom") or None,
                dirigeant_qualite=row.get("dirigeant_qualite") or None,
                adresse_normalisee=row.get("adresse_normalisee") or None,
                date_creation=row.get("date_creation") or None,
                nb_etablissements=(int(nb_etabs_raw) if nb_etabs_raw not in ("", "None") else None),
                score_matching=float(score) if score not in (None, "", "None") else None,
                match_incertain=(match_incertain_raw == "VRAI"),
                flag_chaine=(flag_chaine_raw == "VRAI"),
                note_chaine=row.get("note_chaine") or None,
                hors_filtre_entreprise=(hors_filtre_raw == "VRAI"),
                raison_hors_filtre=row.get("raison_hors_filtre") or None,
            )
        )
    return leads_l2


def lire_stage3_csv(csv_path: Path) -> list[LeadStage3]:
    """Re-charge un CSV L3 vers des LeadStage3 (utile pour relancer L4)."""
    leads_l2 = lire_stage2_csv(csv_path)

    with csv_path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    leads_l3: list[LeadStage3] = []
    for l2, row in zip(leads_l2, rows, strict=False):
        emails_v_raw = row.get("emails_verifies") or ""
        emails_c_raw = row.get("emails_candidats") or ""
        emails_v = [e for e in emails_v_raw.split("|") if e]
        emails_c = [e for e in emails_c_raw.split("|") if e]
        nb_v_raw = row.get("nb_emails_verifies") or "0"
        nb_c_raw = row.get("nb_emails_candidats") or "0"
        dirig_raw = row.get("contient_dirigeant_pattern") or ""
        source = row.get("source_globale") or "aucun_email"
        if source not in (
            "scraping_uniquement",
            "patterns_uniquement",
            "scraping_et_patterns",
            "aucun_email",
            "chaine_non_traitee",
        ):
            source = "aucun_email"

        leads_l3.append(
            LeadStage3(
                **l2.model_dump(),
                emails_verifies=emails_v,
                emails_candidats=emails_c,
                domaine_extrait=row.get("domaine_extrait") or None,
                page_source_emails=row.get("page_source_emails") or None,
                nb_emails_verifies=int(nb_v_raw) if nb_v_raw not in ("", "None") else 0,
                nb_emails_candidats=int(nb_c_raw) if nb_c_raw not in ("", "None") else 0,
                source_globale=source,
                contient_dirigeant_pattern=(dirig_raw == "VRAI"),
            )
        )
    return leads_l3


def lire_stage3_5_csv(csv_path: Path) -> list[LeadStage35]:
    """Re-charge un CSV L3.5 vers des LeadStage35.

    Tolère un CSV L3 standard (colonnes Dropcontact absentes → champs None).
    """
    leads_l3 = lire_stage3_csv(csv_path)

    with csv_path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    leads_l35: list[LeadStage35] = []
    for l3, row in zip(leads_l3, rows, strict=False):
        enrichi_raw = row.get("enrichi_dropcontact") or ""
        cout_raw = row.get("cout_enrichissement_eur") or "0"
        try:
            cout = float(cout_raw) if cout_raw not in ("", "None") else 0.0
        except ValueError:
            cout = 0.0
        leads_l35.append(
            LeadStage35(
                **l3.model_dump(),
                email_dropcontact=row.get("email_dropcontact") or None,
                qualification_email_dropcontact=(
                    row.get("qualification_email_dropcontact") or None
                ),
                telephone_direct_dropcontact=row.get("telephone_direct_dropcontact") or None,
                linkedin_dirigeant_dropcontact=row.get("linkedin_dirigeant_dropcontact") or None,
                linkedin_entreprise_dropcontact=row.get("linkedin_entreprise_dropcontact") or None,
                civilite_dirigeant_dropcontact=row.get("civilite_dirigeant_dropcontact") or None,
                prenom_dirigeant_dropcontact=row.get("prenom_dirigeant_dropcontact") or None,
                nom_dirigeant_dropcontact=row.get("nom_dirigeant_dropcontact") or None,
                enrichi_dropcontact=(enrichi_raw == "VRAI"),
                enrichissement_erreur=row.get("enrichissement_erreur") or None,
                cout_enrichissement_eur=cout,
            )
        )
    return leads_l35


def lire_stage4_csv(csv_path: Path) -> list[LeadStage4]:
    """Re-charge un CSV L4 vers des LeadStage4 (inclut colonnes L3.5)."""
    leads_l35 = lire_stage3_5_csv(csv_path)

    with csv_path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    leads_l4: list[LeadStage4] = []
    for l35, row in zip(leads_l35, rows, strict=False):
        score_raw = row.get("score_interet") or ""
        top_raw = row.get("top_lead") or ""
        leads_l4.append(
            LeadStage4(
                **l35.model_dump(),
                score_interet=(
                    int(score_raw) if score_raw not in ("", "None") else None
                ),
                raison_score=row.get("raison_score") or None,
                pitch_propose=row.get("pitch_propose") or None,
                top_lead=(top_raw == "VRAI"),
                scoring_modele=row.get("scoring_modele") or None,
                scoring_erreur=row.get("scoring_erreur") or None,
            )
        )
    return leads_l4
