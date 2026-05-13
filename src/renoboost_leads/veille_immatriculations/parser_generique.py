"""Parser CSV générique — auto-détection séparateur, encodage, mapping.

Utile quand le fichier source n'est pas garanti AAA Data : un client peut nous
envoyer un CSV maison, un export Excel re-converti, un dump d'une autre source.
On essaye de deviner la structure et de proposer un mapping intelligent.

Le mapping final reste géré par `VeilleConfig` — ce module produit juste un
"squelette de config" prêt à être ajusté par l'utilisateur (CLI ou UI).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from ..common.logger import get_logger
from .models import LigneAAA, VeilleConfig
from .parser_aaa import lire_csv_aaa

logger = get_logger(__name__)


# Heuristiques pour deviner à quel champ interne correspond une colonne fichier.
# Mappe vers `champ_interne` (cf. LigneAAA) — match insensible à la casse,
# accents et caractères de séparation.
_PATTERNS_CHAMPS = {
    "date_immatriculation": [
        "date_immatriculation",
        "date_immat",
        "dateimmat",
        "date",
        "datemep",
        "date_mise_circulation",
    ],
    "plaque": ["plaque", "immatriculation_plaque", "numero_plaque", "plaque_immat"],
    "marque": ["marque", "brand", "make"],
    "modele": ["modele", "model", "version", "modele_commercial"],
    "energie": ["energie", "energy", "carburant", "fuel", "motorisation", "type_energie"],
    "type_vehicule": ["type_vehicule", "categorie", "carrosserie", "genre", "type_vh"],
    "type_acquereur": [
        "type_acquereur",
        "acquereur",
        "type_proprietaire",
        "categorie_acquereur",
        "tiers",
    ],
    "siren": ["siren", "siren_acquereur", "n_siren", "siren_num", "code_siren"],
    "raison_sociale": [
        "raison_sociale",
        "nom_acquereur",
        "denomination",
        "denomination_sociale",
        "rs",
        "nom",
    ],
    "code_postal": ["code_postal", "cp", "postal_code", "zip", "cp_acquereur"],
    "commune": ["commune", "ville", "city", "localite", "ville_acquereur"],
    "departement": [
        "departement", "dept", "code_dept", "code_departement", "departement_acquereur",
    ],
}


@dataclass
class DetectionFichier:
    """Résultat de l'analyse heuristique d'un CSV inconnu."""

    chemin: Path
    encodage_detecte: str
    separateur_detecte: str
    colonnes_brutes: list[str]
    mapping_propose: dict[str, str]  # colonne_fichier → champ_interne
    colonnes_non_mappees: list[str]
    champs_manquants: list[str]  # champs obligatoires non trouvés

    @property
    def utilisable(self) -> bool:
        """True si tous les champs obligatoires ont un mapping."""
        return not self.champs_manquants

    def vers_veille_config(self, separateur: str | None = None) -> VeilleConfig:
        """Construit une VeilleConfig prête à passer au parser AAA standard."""
        return VeilleConfig(
            separateur=separateur or self.separateur_detecte,
            encodage=self.encodage_detecte,
            mapping_colonnes=self.mapping_propose,
        )


def _detecter_encodage(chemin: Path) -> str:
    """Essaie utf-8-sig, utf-8, latin-1, cp1252 dans cet ordre."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with chemin.open("r", encoding=enc) as fh:
                fh.read(4096)  # lire un échantillon
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # fallback ultime


def _detecter_separateur(chemin: Path, encodage: str) -> str:
    """Utilise csv.Sniffer sur les premières lignes."""
    with chemin.open("r", encoding=encodage) as fh:
        echantillon = fh.read(4096)
    try:
        dialect = csv.Sniffer().sniff(echantillon, delimiters=";,|\t")
        return dialect.delimiter
    except csv.Error:
        # Fallback : compte les occurrences les plus fréquentes
        candidats = {sep: echantillon.count(sep) for sep in (";", ",", "|", "\t")}
        return max(candidats.items(), key=lambda kv: kv[1])[0]


def _normaliser_pour_match(s: str) -> str:
    """`Date Immatriculation` → `date_immatriculation`."""
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return (
        ascii_only.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .strip("_")
    )


def _proposer_mapping(colonnes: list[str]) -> tuple[dict[str, str], list[str], list[str]]:
    """Heuristique : associe chaque colonne fichier à un champ interne si possible."""
    mapping: dict[str, str] = {}
    non_mappees: list[str] = []

    for col in colonnes:
        col_norm = _normaliser_pour_match(col)
        match: str | None = None
        for champ, motifs in _PATTERNS_CHAMPS.items():
            if col_norm in motifs:
                match = champ
                break
            if any(m in col_norm for m in motifs):
                match = champ
                break
        if match and match not in mapping.values():
            mapping[col] = match
        else:
            non_mappees.append(col)

    obligatoires = {"date_immatriculation", "energie", "type_acquereur"}
    presents = set(mapping.values())
    manquants = sorted(obligatoires - presents)

    return mapping, non_mappees, manquants


def detecter_format_csv(chemin: Path) -> DetectionFichier:
    """Analyse un CSV inconnu et propose une VeilleConfig.

    Args:
        chemin: chemin du fichier à analyser.

    Returns:
        DetectionFichier avec encodage, séparateur, mapping proposé,
        colonnes non mappées, champs obligatoires manquants.
    """
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    encodage = _detecter_encodage(chemin)
    separateur = _detecter_separateur(chemin, encodage)

    with chemin.open("r", encoding=encodage, newline="") as fh:
        reader = csv.reader(fh, delimiter=separateur)
        try:
            entete = next(reader)
        except StopIteration as e:
            raise ValueError(f"Fichier vide : {chemin}") from e

    mapping, non_mappees, manquants = _proposer_mapping(entete)

    detection = DetectionFichier(
        chemin=chemin,
        encodage_detecte=encodage,
        separateur_detecte=separateur,
        colonnes_brutes=entete,
        mapping_propose=mapping,
        colonnes_non_mappees=non_mappees,
        champs_manquants=manquants,
    )
    logger.info(
        "Détection CSV %s : encodage=%s, séparateur=%r, %d/%d colonnes mappées, "
        "%d champs obligatoires manquants",
        chemin.name,
        encodage,
        separateur,
        len(mapping),
        len(entete),
        len(manquants),
    )
    return detection


def lire_csv_avec_detection(chemin: Path) -> tuple[list[LigneAAA], DetectionFichier]:
    """Lit un CSV inconnu : auto-détecte + parse.

    Si la détection ne trouve pas tous les champs obligatoires, lève une erreur
    avec les colonnes détectées pour aider au debug. L'appelant peut alors
    passer un VeilleConfig manuel à `parser_aaa.lire_csv_aaa()`.
    """
    detection = detecter_format_csv(chemin)
    if not detection.utilisable:
        raise ValueError(
            f"Impossible de mapper automatiquement les champs obligatoires "
            f"({', '.join(detection.champs_manquants)}). "
            f"Colonnes détectées : {detection.colonnes_brutes}. "
            f"Mapping partiel proposé : {detection.mapping_propose}. "
            f"→ Compléter manuellement via VeilleConfig.mapping_colonnes."
        )
    config = detection.vers_veille_config()
    result = lire_csv_aaa(chemin, config)
    return result.lignes, detection
