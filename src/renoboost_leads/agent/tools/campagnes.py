"""Outils campagnes pour l'agent : list / get / create.

Une campagne matérialise l'exécution d'une verticale sur un territoire
(zone + volume + budget). L'agent la crée en conversation une fois l'offre
(verticale) choisie et le périmètre précisé.

Garde-fous (mêmes principes que les outils verticales) :
- chroot strict sous `campagnes/` (id = [a-z0-9-], aucun traversal possible)
- validation Pydantic complète AVANT écriture
- la verticale référencée doit exister et être B2B (V0) — sinon refus
- `create` refuse d'écraser une campagne existante
"""

from __future__ import annotations

import re
from datetime import date

import yaml
from pydantic import ValidationError

from ...campagne.composer import composer_campaign_config
from ...campagne.loader import list_campagnes, load_campagne
from ...campagne.schema import Campagne
from ...settings import PROJECT_ROOT
from ...verticale.loader import VerticaleHorsV0Error, load_verticale

CAMPAGNES_ROOT = PROJECT_ROOT / "campagnes"
VERTICALES_ROOT = PROJECT_ROOT / "verticales"
_ID_RE = re.compile(r"^[a-z0-9-]+$")


def _erreurs_validation(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]


def _apercu_config(campagne: Campagne) -> dict | None:
    """Aperçu du CampaignConfig composé (None si la verticale est inexploitable)."""
    try:
        v = load_verticale(campagne.verticale_slug, base_dir=VERTICALES_ROOT)
        cfg = composer_campaign_config(campagne, v)
    except Exception:  # noqa: BLE001
        return None
    return {
        "client_name": cfg.run.client_name,
        "nb_secteurs": len(cfg.secteurs),
        "zone": f"{cfg.zone.type}:{','.join(cfg.zone.codes)}",
        "seuil_top_lead": cfg.claude_scoring.seuil_top_lead,
        "l3_5_actif": cfg.stages.enable_stage_3_5_enrichment,
        "volume_cible": cfg.volume.cible,
        "budget_max_eur": cfg.budget.max_eur,
    }


def _valider(
    campagne_id: str,
    verticale_slug: str,
    zone: dict,
    volume: dict,
    budget: dict,
    nom: str | None,
) -> tuple[Campagne | None, dict | None]:
    if not isinstance(campagne_id, str) or not _ID_RE.match(campagne_id):
        return None, {"error": f"id invalide : '{campagne_id}' (attendu [a-z0-9-])."}

    # La verticale doit exister et être B2B avant tout.
    try:
        load_verticale(verticale_slug, base_dir=VERTICALES_ROOT)
    except FileNotFoundError:
        return None, {"error": f"verticale introuvable : '{verticale_slug}'."}
    except VerticaleHorsV0Error as e:
        return None, {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return None, {"error": f"verticale invalide : {e}"}

    try:
        modele = Campagne.model_validate(
            {
                "campagne": {
                    "id": campagne_id,
                    "verticale_slug": verticale_slug,
                    "nom": nom,
                    "created": date.today().isoformat(),
                },
                "zone": zone,
                "volume": volume,
                "budget": budget,
            }
        )
    except ValidationError as e:
        return None, {
            "error": "campagne invalide — corrige et réessaie.",
            "details": _erreurs_validation(e),
        }
    return modele, None


def _ecrire(modele: Campagne) -> str:
    d = CAMPAGNES_ROOT / modele.id
    d.mkdir(parents=True, exist_ok=True)
    chemin = d / "campagne.yaml"
    contenu = yaml.safe_dump(modele.model_dump(), allow_unicode=True, sort_keys=False)
    chemin.write_text(contenu, encoding="utf-8")
    try:
        return str(chemin.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(chemin)


def list_campagnes_tool() -> dict:
    """Liste les campagnes existantes (id + verticale + zone + volume + budget)."""
    items = []
    for cid in list_campagnes(base_dir=CAMPAGNES_ROOT):
        try:
            c = load_campagne(cid, base_dir=CAMPAGNES_ROOT)
            items.append(
                {
                    "id": cid,
                    "verticale_slug": c.verticale_slug,
                    "zone": f"{c.zone.type}:{','.join(c.zone.codes)}",
                    "volume_cible": c.volume.cible,
                    "budget_max_eur": c.budget.max_eur,
                }
            )
        except Exception as e:  # noqa: BLE001
            items.append({"id": cid, "erreur": str(e)[:120]})
    return {"campagnes": items, "total": len(items)}


def get_campagne_tool(campagne_id: str) -> dict:
    """Renvoie le contenu d'une campagne + un aperçu de la config composée."""
    try:
        c = load_campagne(campagne_id, base_dir=CAMPAGNES_ROOT)
    except FileNotFoundError:
        return {"error": f"campagne introuvable : {campagne_id}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"campagne invalide : {e}"}
    return {
        "id": campagne_id,
        "campagne": c.model_dump(),
        "config_preview": _apercu_config(c),
    }


def create_campagne_tool(
    id: str,
    verticale_slug: str,
    zone: dict,
    volume: dict,
    budget: dict,
    nom: str | None = None,
) -> dict:
    """Crée une NOUVELLE campagne (refuse d'écraser une existante)."""
    modele, err = _valider(id, verticale_slug, zone, volume, budget, nom)
    if err is not None:
        return err
    assert modele is not None
    if (CAMPAGNES_ROOT / id / "campagne.yaml").exists():
        return {"error": f"la campagne '{id}' existe déjà."}
    chemin = _ecrire(modele)
    return {
        "ok": True,
        "ecrit": True,
        "path": chemin,
        "id": id,
        "verticale_slug": verticale_slug,
        "config_preview": _apercu_config(modele),
        "message": f"Campagne '{id}' créée et validée.",
    }


_ZONE_DESC = (
    "Territoire : {type: 'ville'|'departement'|'region'|'france', "
    "codes: [str] (>=1, ex ['59','80'] pour Nord+Somme), "
    "rayon_par_point_km?, pas_grille_km?}."
)
_VOLUME_DESC = "Volume cible : {cible: int>0 (ex 150), max_par_secteur?: int}."
_BUDGET_DESC = "Budget : {max_eur: float>0 (ex 20.0)}."

SCHEMAS = [
    {
        "name": "list_campagnes",
        "description": "Liste les campagnes existantes (id, verticale, zone, volume, budget).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_campagne",
        "description": (
            "Renvoie le contenu d'une campagne par son id, plus un aperçu du "
            "CampaignConfig qu'elle produit (secteurs, seuil, L3.5, volume, budget)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"campagne_id": {"type": "string"}},
            "required": ["campagne_id"],
        },
    },
    {
        "name": "create_campagne",
        "description": (
            "Crée une campagne = exécution d'une verticale sur un territoire. "
            "Écrit campagnes/<id>/campagne.yaml après validation stricte. La "
            "verticale doit exister et être B2B. Refuse d'écraser une campagne "
            "existante. N'appeler qu'une fois la verticale choisie et le périmètre "
            "(zone, volume, budget) précisé avec l'utilisateur."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Identifiant en minuscules/tirets, ex 'clim-lille-juin'.",
                },
                "verticale_slug": {
                    "type": "string",
                    "description": "Slug de la verticale (offre) à exécuter.",
                },
                "zone": {"type": "object", "description": _ZONE_DESC},
                "volume": {"type": "object", "description": _VOLUME_DESC},
                "budget": {"type": "object", "description": _BUDGET_DESC},
                "nom": {"type": "string", "description": "Libellé lisible (optionnel)."},
            },
            "required": ["id", "verticale_slug", "zone", "volume", "budget"],
        },
    },
]

DISPATCH = {
    "list_campagnes": list_campagnes_tool,
    "get_campagne": get_campagne_tool,
    "create_campagne": create_campagne_tool,
}
