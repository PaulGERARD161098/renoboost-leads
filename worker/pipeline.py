"""Pipelines d'exécution d'un run.

`Pipeline` est le contrat : transformer un `RunContext` en `RunResult` (des leads
prêts à insérer), en signalant la progression via un callback `emit`.

Deux implémentations :
- `DemoPipeline` : génère des leads plausibles sans API externe. Permet de tester
  toute la boucle (UI → run → leads) immédiatement, et donne du grain à moudre
  à la validation commerciale.
- `build_pipeline("real")` : point d'extension pour brancher les étages réels
  (`renoboost_leads.stage0..4`). Non implémenté tant que les clés API ne sont pas
  fournies — lève une erreur explicite.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

# Callback de progression : (etape, progress 0-100, counts).
EmitFn = Callable[[str, int, dict[str, int]], None]


@dataclass
class RunContext:
    run: dict[str, Any]
    verticale: dict[str, Any] | None
    max_leads: int = 500

    @property
    def zone(self) -> dict[str, Any]:
        z = self.run.get("zone")
        return z if isinstance(z, dict) else {}

    @property
    def config(self) -> dict[str, Any]:
        if not self.verticale:
            return {}
        c = self.verticale.get("config")
        return c if isinstance(c, dict) else {}

    @property
    def departement(self) -> str:
        return str(self.zone.get("departement") or "75")

    @property
    def volume_cible(self) -> int:
        v = self.run.get("volume_cible")
        return int(v) if v else 25


@dataclass
class RunResult:
    leads: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    cout_eur: float = 0.0


class Pipeline(Protocol):
    def run(self, ctx: RunContext, emit: EmitFn) -> RunResult: ...


# --- Données de démo ---------------------------------------------------------

_PREFIXES = [
    "Ateliers", "Groupe", "Établissements", "Société", "Comptoir", "Manufacture",
    "Transports", "Distribution", "Entreprise", "Compagnie",
]
_NOMS = [
    "Lefebvre", "Moreau", "Durand", "Bernard", "Petit", "Rousseau", "Girard",
    "Lambert", "Fontaine", "Mercier", "Blanchard", "Dumont", "Carpentier", "Vasseur",
]
_FORMES = ["SARL", "SAS", "SA", "EURL", "SASU"]
_VILLES_PAR_DEPT: dict[str, list[str]] = {
    "59": ["Lille", "Roubaix", "Tourcoing", "Dunkerque", "Villeneuve-d'Ascq"],
    "62": ["Arras", "Lens", "Calais", "Boulogne-sur-Mer", "Béthune"],
    "75": ["Paris"],
    "13": ["Marseille", "Aix-en-Provence", "Arles", "Aubagne"],
    "69": ["Lyon", "Villeurbanne", "Vénissieux"],
}


def _ville_pour(dept: str, rng: random.Random) -> str:
    villes = _VILLES_PAR_DEPT.get(dept)
    if villes:
        return rng.choice(villes)  # noqa: S311 (données de démo, pas de la crypto)
    return f"Ville-{dept}"


def _siren(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(9))  # noqa: S311


class DemoPipeline:
    """Génère des leads crédibles, sans appel réseau externe."""

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed

    def run(self, ctx: RunContext, emit: EmitFn) -> RunResult:
        # Graine déterministe par run → idempotence des relances de démo.
        rng = random.Random(  # noqa: S311 (démo : pas d'usage cryptographique)
            self._seed if self._seed is not None else hash(ctx.run.get("id"))
        )

        n = max(1, min(ctx.volume_cible, ctx.max_leads, 50))
        dept = ctx.departement
        cfg = ctx.config
        naf_pool: list[str] = [str(s) for s in cfg.get("secteurs_naf", [])] or ["46.90Z"]
        offre = str(cfg.get("offre") or "notre solution")
        signaux: list[str] = [str(s) for s in cfg.get("signaux", [])]

        emit("Découverte (SIRENE)", 10, {"decouverte": n})

        leads: list[dict[str, Any]] = []
        qualifies = 0
        for i in range(n):
            forme = rng.choice(_FORMES)  # noqa: S311
            nom = f"{rng.choice(_PREFIXES)} {rng.choice(_NOMS)} {forme}"  # noqa: S311
            ville = _ville_pour(dept, rng)
            cp = f"{dept}{rng.randint(0, 999):03d}"[:5]
            naf = rng.choice(naf_pool)  # noqa: S311
            effectif = rng.choice(["10 à 19", "20 à 49", "50 à 99", "100 à 199"])  # noqa: S311
            hors_filtre = rng.random() < 0.12  # noqa: S311
            score = rng.randint(35, 54) if hors_filtre else rng.randint(58, 96)  # noqa: S311
            if not hors_filtre:
                qualifies += 1

            slug = _slugify(nom)
            signal = rng.choice(signaux) if signaux else None  # noqa: S311

            leads.append(
                {
                    "run_id": ctx.run.get("id"),
                    "verticale_id": ctx.run.get("verticale_id"),
                    "entreprise": nom,
                    "siren": _siren(rng),
                    "naf": naf,
                    "libelle_naf": _libelle_naf(naf),
                    "effectif": effectif,
                    "ville": ville,
                    "code_postal": cp,
                    "score": score,
                    "contact_nom": None,
                    "contact_email": f"contact@{slug}.fr",
                    "site_web": f"https://www.{slug}.fr",
                    "hors_filtre": hors_filtre,
                    "raison_hors_filtre": (
                        "Effectif/secteur hors cible (démo)" if hors_filtre else None
                    ),
                    "mail_sujet": f"{offre} pour {nom.split(' ', 1)[-1]}",
                    "mail_corps": _corps_mail(nom, offre, ville, signal),
                    "statut": "a_valider",
                }
            )

            if (i + 1) % max(1, n // 4) == 0:
                pct = 10 + int(80 * (i + 1) / n)
                emit(
                    "Enrichissement & scoring",
                    min(pct, 90),
                    {"decouverte": n, "qualifies": qualifies, "leads": i + 1},
                )

        counts = {"decouverte": n, "qualifies": qualifies, "leads": len(leads)}
        emit("Rédaction des e-mails", 95, counts)

        # Coût simulé : ordre de grandeur réaliste (~4 c€/lead enrichi).
        cout = round(len(leads) * 0.04, 2)
        return RunResult(leads=leads, counts=counts, cout_eur=cout)


def _slugify(nom: str) -> str:
    out = []
    for ch in nom.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -'":
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "entreprise"


_NAF_LIBELLES = {
    "46.90Z": "Commerce de gros non spécialisé",
    "49.41A": "Transports routiers de fret interurbains",
    "47.30Z": "Commerce de détail de carburants",
    "25.11Z": "Fabrication de structures métalliques",
    "52.10B": "Entreposage et stockage non frigorifique",
}


def _libelle_naf(naf: str) -> str:
    return _NAF_LIBELLES.get(naf, "Activité non précisée")


def _corps_mail(nom: str, offre: str, ville: str, signal: str | None) -> str:
    accroche = f" J'ai noté votre {signal}." if signal else ""
    return (
        f"Bonjour,\n\n"
        f"Je me permets de vous contacter au sujet de {nom} à {ville}.{accroche}\n"
        f"Nous proposons {offre} aux entreprises de votre profil, avec un retour "
        f"sur investissement chiffré dès la première année.\n\n"
        f"Seriez-vous disponible 15 minutes cette semaine pour en échanger ?\n\n"
        f"Bien cordialement,\nL'équipe RénoBoost"
    )


def build_pipeline(mode: str, *, seed: int | None = None) -> Pipeline:
    if mode == "demo":
        return DemoPipeline(seed=seed)
    if mode == "real":
        raise NotImplementedError(
            "Pipeline réel non branché : il nécessite les clés API "
            "(GOOGLE_PLACES, PAPPERS/SOCIETEINFO, ANTHROPIC) et l'adaptateur vers "
            "renoboost_leads.stage0..4. Utilise WORKER_MODE=demo en attendant."
        )
    raise ValueError(f"Mode de pipeline inconnu : {mode!r}")
