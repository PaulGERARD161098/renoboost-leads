"""Parser CSV AAA Data → list[LigneAAA].

Tolérant : ignore les lignes invalides individuelles (avec log) plutôt que
de casser tout le fichier. Les erreurs sont remontées dans `ParseResult`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..common.logger import get_logger
from .models import LigneAAA, VeilleConfig, parse_date_aaa

logger = get_logger(__name__)


class ParseAAAError(Exception):
    """Erreur fatale de parsing (fichier illisible, entête manquante…)."""


# Alias rétrocompatibilité — `ParseErrorAAA` reste utilisable.
ParseErrorAAA = ParseAAAError


@dataclass
class ParseResult:
    lignes: list[LigneAAA] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    nb_lignes_brutes: int = 0

    @property
    def nb_lignes_valides(self) -> int:
        return len(self.lignes)


def lire_csv_aaa(chemin: Path, config: VeilleConfig | None = None) -> ParseResult:
    """Lit un CSV AAA Data et retourne les lignes validées.

    Args:
        chemin: chemin du fichier CSV
        config: VeilleConfig (mapping colonnes, encodage, séparateur).
                Si None, valeurs par défaut (conventions standards AAA).

    Returns:
        ParseResult avec lignes valides + erreurs ligne-à-ligne.

    Raises:
        ParseErrorAAA: si le fichier est introuvable ou si l'entête CSV
                       ne contient aucune des colonnes attendues.
    """
    config = config or VeilleConfig()

    if not chemin.exists():
        raise ParseAAAError(f"Fichier introuvable : {chemin}")

    result = ParseResult()

    try:
        with chemin.open("r", encoding=config.encodage, newline="") as fh:
            reader = csv.DictReader(fh, delimiter=config.separateur)
            if reader.fieldnames is None:
                raise ParseAAAError(f"Entête CSV manquante : {chemin}")

            # Vérification : au moins une colonne du mapping doit exister dans l'entête
            cols_attendues = set(config.mapping_colonnes.keys())
            cols_presentes = set(reader.fieldnames)
            intersection = cols_attendues & cols_presentes
            if not intersection:
                raise ParseAAAError(
                    f"Aucune colonne attendue trouvée dans l'entête. "
                    f"Attendues : {sorted(cols_attendues)} ; "
                    f"présentes : {sorted(cols_presentes)}"
                )
            logger.info(
                "Veille AAA : %d colonnes mappées sur %d présentes dans le fichier",
                len(intersection),
                len(cols_presentes),
            )

            for num_ligne, row in enumerate(reader, start=2):
                result.nb_lignes_brutes += 1
                try:
                    ligne = _ligne_row_en_lignaaa(row, config)
                    if ligne is not None:
                        result.lignes.append(ligne)
                except Exception as e:  # noqa: BLE001
                    msg = f"L{num_ligne}: {e}"
                    result.erreurs.append(msg)
                    logger.debug("Ligne AAA ignorée — %s", msg)

    except UnicodeDecodeError as e:
        raise ParseAAAError(
            f"Encodage incorrect ({config.encodage}) : {e}. "
            f"Essaye `encodage='latin-1'` ou `'cp1252'` dans la VeilleConfig."
        ) from e

    logger.info(
        "Veille AAA : %s — %d/%d lignes valides (%d erreurs)",
        chemin.name,
        result.nb_lignes_valides,
        result.nb_lignes_brutes,
        len(result.erreurs),
    )
    return result


def _ligne_row_en_lignaaa(row: dict[str, str], config: VeilleConfig) -> LigneAAA | None:
    """Convertit un dict CSV → LigneAAA en appliquant le mapping de colonnes."""
    mapped: dict[str, object] = {"ligne_brute": dict(row)}

    for col_fichier, champ_interne in config.mapping_colonnes.items():
        if col_fichier not in row:
            continue
        valeur = (row[col_fichier] or "").strip()
        if not valeur:
            continue

        if champ_interne == "date_immatriculation":
            mapped[champ_interne] = parse_date_aaa(valeur, config.formats_date)
        else:
            mapped[champ_interne] = valeur

    # Champs obligatoires
    if "date_immatriculation" not in mapped:
        raise ValueError("date_immatriculation manquante")
    if "energie" not in mapped:
        raise ValueError("energie manquante")
    if "type_acquereur" not in mapped:
        raise ValueError("type_acquereur manquant")

    return LigneAAA(**mapped)
