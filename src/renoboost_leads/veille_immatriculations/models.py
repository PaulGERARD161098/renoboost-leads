"""Modèles Pydantic pour la veille AAA Data.

Les noms de colonnes et codes énergies suivent les conventions standards AAA Data
(stable depuis ~10 ans). Le mapping concret est paramétrable via `VeilleConfig` :
si un échantillon réel diffère, on ajuste sans toucher au reste du module.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ════════════════════════════════════════════════════════════════
# Constantes AAA Data (conventions standards — à ajuster à réception échantillon)
# ════════════════════════════════════════════════════════════════

# Codes énergie AAA Data identifiant un véhicule électrifié.
#   EL : électrique pur (BEV)
#   HE : hybride rechargeable (PHEV)
#   HH : hybride essence (HEV) — borderline ; à retirer si trop large
#   EH : électrique + hydrogène
#   H2 : hydrogène pur
ENERGIES_ELECTRIQUES = {"EL", "HE", "HH", "EH", "H2"}

# Codes type d'acquéreur AAA Data identifiant une personne morale.
#   M = personne morale (entreprise, association, collectivité)
#   P = personne physique (à exclure)
#   Selon les diffusions, on peut aussi rencontrer "PM" / "PP".
TYPES_ACQUEREUR_MORALE = {"M", "PM"}


# ════════════════════════════════════════════════════════════════
# Modèles de données
# ════════════════════════════════════════════════════════════════


class LigneAAA(BaseModel):
    """Une ligne du fichier AAA Data, validée et normalisée.

    Les champs optionnels (None acceptés) correspondent aux colonnes qui
    peuvent manquer selon les variantes du flux.
    """

    model_config = ConfigDict(extra="ignore")

    # Immatriculation
    date_immatriculation: date
    plaque: str | None = None

    # Véhicule
    marque: str | None = None
    modele: str | None = None
    energie: str  # Code AAA (EL/HE/HH/ES/GO/...). Filtré ailleurs.
    type_vehicule: Literal["VP", "VU", "VUL", "PL", "CTTE", "AUTRE"] | None = None

    # Acquéreur
    type_acquereur: str  # Code AAA (M/P/PM/PP/...)
    siren: str | None = None
    raison_sociale: str | None = None

    # Adresse
    code_postal: str | None = None
    commune: str | None = None
    departement: str | None = None  # Code dept (2 chiffres, "2A"/"2B" pour Corse)

    # Source / debug
    ligne_brute: dict[str, str] = Field(default_factory=dict)

    @field_validator("siren")
    @classmethod
    def _normalize_siren(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = "".join(c for c in v if c.isdigit())
        if not clean:
            return None
        if len(clean) == 9:
            return clean
        if len(clean) == 14:  # SIRET fourni à la place du SIREN
            return clean[:9]
        return None  # SIREN invalide

    @field_validator("code_postal")
    @classmethod
    def _normalize_cp(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().zfill(5)
        return s if len(s) == 5 and s.replace(" ", "").isdigit() else None

    @field_validator("energie", "type_acquereur")
    @classmethod
    def _upper(cls, v: str) -> str:
        return (v or "").strip().upper()


class VeilleConfig(BaseModel):
    """Configuration du parser AAA Data (mapping colonnes + options).

    Cette config permet d'adapter le module à la structure réelle d'AAA Data
    sans toucher au code, dès qu'on aura l'échantillon. Les noms par défaut
    suivent les conventions AAA standards.
    """

    model_config = ConfigDict(extra="forbid")

    # Délimiteur CSV (',' par défaut, ';' fréquent en France)
    separateur: str = ";"
    encodage: str = "utf-8-sig"  # gère le BOM Excel

    # Mapping colonne_fichier → champ_lignAAA
    mapping_colonnes: dict[str, str] = Field(
        default_factory=lambda: {
            "DATE_IMMATRICULATION": "date_immatriculation",
            "PLAQUE": "plaque",
            "MARQUE": "marque",
            "MODELE": "modele",
            "ENERGIE": "energie",
            "TYPE_VEHICULE": "type_vehicule",
            "TYPE_ACQUEREUR": "type_acquereur",
            "SIREN": "siren",
            "RAISON_SOCIALE": "raison_sociale",
            "CODE_POSTAL": "code_postal",
            "COMMUNE": "commune",
            "DEPARTEMENT": "departement",
        }
    )

    # Format de date dans le fichier (formats Python strptime acceptés en cascade)
    formats_date: list[str] = Field(
        default_factory=lambda: ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
    )

    # Codes énergie à conserver (par défaut tous les VE/PHEV/HEV)
    energies_conservees: set[str] = Field(default_factory=lambda: ENERGIES_ELECTRIQUES.copy())

    # Codes type acquéreur considérés comme personne morale
    types_acquereur_morale: set[str] = Field(
        default_factory=lambda: TYPES_ACQUEREUR_MORALE.copy()
    )

    # Exiger un SIREN renseigné pour conserver la ligne
    exiger_siren: bool = True


def parse_date_aaa(valeur: str, formats: list[str]) -> date:
    """Tente de parser une date selon plusieurs formats."""
    valeur = valeur.strip()
    for fmt in formats:
        try:
            return datetime.strptime(valeur, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date AAA non parseable : {valeur!r} (formats essayés : {formats})")
