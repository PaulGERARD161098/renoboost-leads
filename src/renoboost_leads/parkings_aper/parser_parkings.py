"""Parser CSV inventaire parkings → list[LigneParking].

Tolérant : ignore les lignes invalides individuelles (avec log) plutôt que de
casser tout le fichier. Le mapping de colonnes est paramétrable via `AperConfig`
pour s'adapter à un export OSM/IGN ou à un fichier client.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..common.logger import get_logger
from .models import AperConfig, LigneParking

logger = get_logger(__name__)


class ParseParkingsError(Exception):
    """Erreur fatale de parsing (fichier illisible, entête manquante…)."""


@dataclass
class ParseResultParkings:
    lignes: list[LigneParking] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    nb_lignes_brutes: int = 0

    @property
    def nb_lignes_valides(self) -> int:
        return len(self.lignes)


def _to_float(valeur: str) -> float:
    """Parse un nombre tolérant aux virgules décimales et espaces."""
    nettoye = valeur.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(nettoye)


def _row_en_ligne(row: dict[str, str], config: AperConfig) -> LigneParking | None:
    mapped: dict[str, object] = {"ligne_brute": dict(row)}

    for col_fichier, champ in config.mapping_colonnes.items():
        if col_fichier not in row:
            continue
        valeur = (row[col_fichier] or "").strip()
        if not valeur:
            continue
        if champ in ("surface_m2", "latitude", "longitude"):
            mapped[champ] = _to_float(valeur)
        else:
            mapped[champ] = valeur

    if "surface_m2" not in mapped:
        raise ValueError("surface_m2 manquante ou non numérique")

    return LigneParking(**mapped)


def lire_csv_parkings(
    chemin: Path, config: AperConfig | None = None
) -> ParseResultParkings:
    """Lit un CSV inventaire parkings et retourne les lignes validées."""
    config = config or AperConfig()

    if not chemin.exists():
        raise ParseParkingsError(f"Fichier introuvable : {chemin}")

    result = ParseResultParkings()

    try:
        with chemin.open("r", encoding=config.encodage, newline="") as fh:
            reader = csv.DictReader(fh, delimiter=config.separateur)
            if reader.fieldnames is None:
                raise ParseParkingsError(f"Entête CSV manquante : {chemin}")

            cols_attendues = set(config.mapping_colonnes.keys())
            cols_presentes = set(reader.fieldnames)
            if not (cols_attendues & cols_presentes):
                raise ParseParkingsError(
                    f"Aucune colonne attendue trouvée. "
                    f"Attendues : {sorted(cols_attendues)} ; "
                    f"présentes : {sorted(cols_presentes)}"
                )

            for num_ligne, row in enumerate(reader, start=2):
                result.nb_lignes_brutes += 1
                try:
                    ligne = _row_en_ligne(row, config)
                    if ligne is not None:
                        result.lignes.append(ligne)
                except Exception as e:  # noqa: BLE001
                    msg = f"L{num_ligne}: {e}"
                    result.erreurs.append(msg)
                    logger.debug("Ligne parking ignorée — %s", msg)

    except UnicodeDecodeError as e:
        raise ParseParkingsError(
            f"Encodage incorrect ({config.encodage}) : {e}. "
            f"Essaye encodage='latin-1' ou 'cp1252' dans AperConfig."
        ) from e

    logger.info(
        "Parkings APER : %s — %d/%d lignes valides (%d erreurs)",
        chemin.name,
        result.nb_lignes_valides,
        result.nb_lignes_brutes,
        len(result.erreurs),
    )
    return result
