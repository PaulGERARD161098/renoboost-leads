"""Outils verticales pour l'agent : list / get / create / refine.

Discovery conversationnelle (cf prompts/discovery.md) : l'agent dialogue avec
l'utilisateur pour préciser une offre, puis matérialise une verticale.

Garde-fous (l'agent écrit réellement, mais sous contrôle) :
- chroot strict sous `verticales/` (slug = [a-z0-9-], aucun traversal possible)
- validation Pydantic complète AVANT écriture (rien d'invalide n'est écrit)
- garde V0 : `cible.type` doit être `b2b` (le B2C arrive en V1)
- `create` refuse d'écraser une verticale existante ; `refine` exige qu'elle existe
"""

from __future__ import annotations

import re

import yaml
from pydantic import ValidationError

from ...settings import PROJECT_ROOT
from ...verticale.loader import list_verticales, load_verticale
from ...verticale.schema import Verticale

VERTICALES_ROOT = PROJECT_ROOT / "verticales"
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def _erreurs_validation(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]


def _valider(slug: str, verticale: dict) -> tuple[Verticale | None, dict | None]:
    """Valide slug + contenu. Retourne (modèle, None) ou (None, erreur)."""
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        return None, {"error": f"slug invalide : '{slug}' (attendu [a-z0-9-])."}
    if not isinstance(verticale, dict):
        return None, {"error": "`verticale` doit être un objet (dict)."}

    try:
        modele = Verticale.model_validate(verticale)
    except ValidationError as e:
        return None, {
            "error": "verticale invalide — corrige et réessaie.",
            "details": _erreurs_validation(e),
        }

    if modele.slug != slug:
        return None, {
            "error": f"incohérence slug : argument '{slug}' ≠ verticale.slug='{modele.slug}'."
        }
    if modele.cible.type != "b2b":
        return None, {
            "error": (
                f"cible.type='{modele.cible.type}' non supporté en V0 (B2B uniquement ; "
                "le B2C arrive en V1)."
            )
        }
    return modele, None


def _ecrire(slug: str, modele: Verticale) -> str:
    d = VERTICALES_ROOT / slug
    d.mkdir(parents=True, exist_ok=True)
    chemin = d / "verticale.yaml"
    contenu = yaml.safe_dump(
        modele.model_dump(), allow_unicode=True, sort_keys=False
    )
    chemin.write_text(contenu, encoding="utf-8")
    return str(chemin.relative_to(PROJECT_ROOT))


def list_verticales_tool() -> dict:
    """Liste les verticales existantes (slug + nom + cible)."""
    items = []
    for slug in list_verticales(base_dir=VERTICALES_ROOT):
        try:
            v = load_verticale(slug, base_dir=VERTICALES_ROOT)
            items.append({"slug": slug, "nom": v.verticale.nom, "cible": v.cible.type})
        except Exception as e:  # noqa: BLE001
            items.append({"slug": slug, "erreur": str(e)[:120]})
    return {"verticales": items, "total": len(items)}


def get_verticale_tool(slug: str) -> dict:
    """Renvoie le contenu validé d'une verticale (pour la modifier ensuite)."""
    try:
        v = load_verticale(slug, base_dir=VERTICALES_ROOT)
    except FileNotFoundError:
        return {"error": f"verticale introuvable : {slug}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"verticale invalide : {e}"}
    return {"slug": slug, "verticale": v.model_dump()}


def create_verticale_tool(slug: str, verticale: dict) -> dict:
    """Crée une NOUVELLE verticale (refuse d'écraser une existante)."""
    modele, err = _valider(slug, verticale)
    if err is not None:
        return err
    if (VERTICALES_ROOT / slug / "verticale.yaml").exists():
        return {
            "error": (
                f"la verticale '{slug}' existe déjà — utilise refine_verticale "
                "pour la modifier."
            )
        }
    chemin = _ecrire(slug, modele)
    return {
        "ok": True,
        "ecrit": True,
        "path": chemin,
        "slug": slug,
        "nom": modele.verticale.nom,
        "message": f"Verticale '{slug}' créée et validée.",
    }


def refine_verticale_tool(slug: str, verticale: dict) -> dict:
    """Met à jour une verticale EXISTANTE (refuse d'en créer une nouvelle)."""
    if not (VERTICALES_ROOT / slug / "verticale.yaml").exists():
        return {
            "error": f"la verticale '{slug}' n'existe pas — utilise create_verticale pour la créer."
        }
    modele, err = _valider(slug, verticale)
    if err is not None:
        return err
    chemin = _ecrire(slug, modele)
    return {
        "ok": True,
        "ecrit": True,
        "path": chemin,
        "slug": slug,
        "nom": modele.verticale.nom,
        "message": f"Verticale '{slug}' mise à jour et validée.",
    }


_VERTICALE_DESC = (
    "Objet verticale complet (10 sections) : `verticale` (slug, nom, description), "
    "`cible` (type='b2b', detail), `offre` (produit, argument_principal, "
    "ticket_moyen_eur), `cibles` (secteurs_places[{type,query}], filtres_entreprise), "
    "`signaux` (liste, >=1), `qualification` (seuil_score_top, criteres_top[], "
    "criteres_exclusion[]), `enrichissements`, `ton_mail`, `sequence` (j0[,j3,j7]), "
    "`budget_typique`. Voir le prompt discovery pour le détail des champs."
)

SCHEMAS = [
    {
        "name": "list_verticales",
        "description": "Liste les verticales existantes (slug, nom, type de cible).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_verticale",
        "description": (
            "Renvoie le contenu validé d'une verticale par son slug. À utiliser avant "
            "refine_verticale pour repartir du contenu actuel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
        },
    },
    {
        "name": "create_verticale",
        "description": (
            "Crée une NOUVELLE verticale et l'écrit dans verticales/<slug>/verticale.yaml. "
            "Valide strictement le contenu avant d'écrire ; en cas d'erreur, renvoie le "
            "détail pour correction (corrige et rappelle l'outil). Refuse d'écraser une "
            "verticale existante. B2B uniquement en V0. N'appeler qu'une fois l'offre bien "
            "précisée avec l'utilisateur."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Identifiant en minuscules/tirets, ex 'clim-pro-b2b'.",
                },
                "verticale": {"type": "object", "description": _VERTICALE_DESC},
            },
            "required": ["slug", "verticale"],
        },
    },
    {
        "name": "refine_verticale",
        "description": (
            "Met à jour une verticale EXISTANTE (réécrit le fichier). Mêmes validations "
            "que create_verticale. Refuse si la verticale n'existe pas. Récupère d'abord "
            "le contenu actuel via get_verticale, applique la demande, puis renvoie "
            "l'objet complet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "verticale": {"type": "object", "description": _VERTICALE_DESC},
            },
            "required": ["slug", "verticale"],
        },
    },
]

DISPATCH = {
    "list_verticales": list_verticales_tool,
    "get_verticale": get_verticale_tool,
    "create_verticale": create_verticale_tool,
    "refine_verticale": refine_verticale_tool,
}
