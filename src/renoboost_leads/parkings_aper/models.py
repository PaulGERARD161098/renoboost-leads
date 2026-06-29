"""Modèles Pydantic + constantes réglementaires pour le module parkings APER.

Le calendrier et les seuils suivent l'article 40 de la loi APER (loi n°2023-175
du 10 mars 2023) et son décret d'application n°2024-1023 du 13 novembre 2024 :

- Parcs de stationnement extérieurs **> 1 500 m²** : obligation de couvrir
  **50 %** de la superficie d'ombrières intégrant une production d'EnR (PV).
- Calendrier d'entrée en vigueur :
    * parkings **> 10 000 m²** : 1er juillet **2026**
    * parkings **1 500 – 10 000 m²** : 1er juillet **2028**
- Sanctions jusqu'à 40 000 €/an pour les plus grands parcs non conformes.

Les seuils sont surchargeables via `AperConfig` au cas où la réglementation
évolue, sans toucher au reste du code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ════════════════════════════════════════════════════════════════
# Constantes réglementaires (loi APER art. 40 + décret 2024-1023)
# ════════════════════════════════════════════════════════════════

SEUIL_APER_M2 = 1500.0  # en-dessous : non soumis à l'obligation
SEUIL_GROS_PARKING_M2 = 10000.0  # au-dessus : échéance anticipée + priorité haute
PART_OMBRABLE = 0.5  # 50 % de la surface doit être ombrée

ECHEANCE_GROS = "2026-07-01"  # > 10 000 m²
ECHEANCE_STANDARD = "2028-07-01"  # 1 500 – 10 000 m²

# Ratio indicatif surface → nombre de places (≈ 25 m²/place voirie comprise).
M2_PAR_PLACE = 25.0


def echeance_pour_surface(surface_m2: float) -> tuple[str | None, str]:
    """Retourne (echeance_iso, priorite) en fonction de la surface du parking.

    Sous le seuil APER (1 500 m²), le parking n'est soumis à AUCUNE obligation
    légale de solarisation : pas d'échéance (`None`), priorité
    « hors_obligation ». Ces parkings relèvent de la cible flotte/RSE
    (autoconsommation, recharge VE), pas du levier réglementaire.
    """
    if surface_m2 >= SEUIL_GROS_PARKING_M2:
        return ECHEANCE_GROS, "haute"
    if surface_m2 < SEUIL_APER_M2:
        return None, "hors_obligation"
    return ECHEANCE_STANDARD, "standard"


# ════════════════════════════════════════════════════════════════
# Modèles de données
# ════════════════════════════════════════════════════════════════


class LigneParking(BaseModel):
    """Une ligne d'inventaire parking, validée et normalisée.

    La source typique est un export géospatial (OSM `amenity=parking` croisé
    avec la BD ORTHO IGN pour la surface) ou un fichier client. Le seul champ
    réellement obligatoire est `surface_m2` ; le reste aide le matching SIREN
    en aval (nom de l'enseigne/exploitant, code postal, commune).
    """

    model_config = ConfigDict(extra="ignore")

    surface_m2: float = Field(gt=0)

    # Identité / matching
    identifiant: str | None = None  # id source (OSM way id, ref cadastre…)
    nom: str | None = None  # enseigne / exploitant si connu ("Carrefour Lens")
    raison_sociale: str | None = None
    siren: str | None = None

    # Localisation
    adresse: str | None = None
    code_postal: str | None = None
    commune: str | None = None
    departement: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    # Source / debug
    source: str | None = None
    ligne_brute: dict[str, str] = Field(default_factory=dict)

    @field_validator("siren")
    @classmethod
    def _normalize_siren(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = "".join(c for c in v if c.isdigit())
        if len(clean) == 9:
            return clean
        if len(clean) == 14:  # SIRET fourni à la place du SIREN
            return clean[:9]
        return None

    @field_validator("code_postal")
    @classmethod
    def _normalize_cp(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().zfill(5)
        return s if len(s) == 5 and s.isdigit() else None

    @property
    def surface_ombrable_m2(self) -> float:
        return round(self.surface_m2 * PART_OMBRABLE, 1)

    @property
    def nb_places_estime(self) -> int:
        return int(self.surface_m2 / M2_PAR_PLACE)

    def echeance(self) -> tuple[str | None, str]:
        return echeance_pour_surface(self.surface_m2)

    def identifiant_stable(self) -> str:
        """Identifiant unique stable pour le dédoublonnage (flag-not-drop)."""
        if self.identifiant:
            return f"id:{self.identifiant}"
        if self.siren:
            return f"siren:{self.siren}"
        # Fallback : nom + CP (suffisant pour un POC, à raffiner avec la géoloc)
        nom = (self.nom or self.raison_sociale or "?").strip().lower()
        return f"nomcp:{nom}|{self.code_postal or '?'}"


class AperConfig(BaseModel):
    """Configuration du parser/filtre parkings (mapping colonnes + seuils)."""

    model_config = ConfigDict(extra="forbid")

    # Lecture CSV
    separateur: str = ";"
    encodage: str = "utf-8-sig"

    # Mapping colonne_fichier → champ_LigneParking
    mapping_colonnes: dict[str, str] = Field(
        default_factory=lambda: {
            "SURFACE_M2": "surface_m2",
            "IDENTIFIANT": "identifiant",
            "NOM": "nom",
            "RAISON_SOCIALE": "raison_sociale",
            "SIREN": "siren",
            "ADRESSE": "adresse",
            "CODE_POSTAL": "code_postal",
            "COMMUNE": "commune",
            "DEPARTEMENT": "departement",
            "LATITUDE": "latitude",
            "LONGITUDE": "longitude",
        }
    )

    # Seuil de surface à partir duquel on garde le parking (défaut = seuil APER).
    surface_min_m2: float = Field(default=SEUIL_APER_M2, gt=0)
    # Plafond de surface (m²) — None = pas de plafond. Sert à cibler une FENÊTRE
    # de taille (ex. petits parkings « flotte » 250-1250 m² ≈ 10-50 places) et à
    # exclure les très grands parcs (hyper, ZC) qui ne sont pas des PME-sièges.
    surface_max_m2: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _verifier_fenetre_surface(self) -> AperConfig:
        if self.surface_max_m2 is not None and self.surface_max_m2 < self.surface_min_m2:
            raise ValueError(
                f"surface_max_m2 ({self.surface_max_m2}) < surface_min_m2 "
                f"({self.surface_min_m2}) : fenêtre de surface vide"
            )
        return self
