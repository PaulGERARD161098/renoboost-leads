"""Pipelines d'exécution d'un run.

`Pipeline` est le contrat : transformer un `RunContext` en `RunResult` (des leads
prêts à insérer), en signalant la progression via un callback `emit`.

Deux implémentations :
- `DemoPipeline` : génère des leads plausibles sans API externe. Permet de tester
  toute la boucle (UI → run → leads) immédiatement, et donne du grain à moudre
  à la validation commerciale.
- `RealPipeline` : exécute le vrai moteur L1→L4 (`renoboost_leads`) via
  l'orchestrateur partagé avec la CLI, applique le ciblage de la verticale fichier
  (source de vérité), et mappe chaque `LeadStage4` vers le contrat `leads`.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

# Callback de progression : (etape, progress 0-100, counts).
EmitFn = Callable[[str, int, dict[str, int]], None]


@dataclass
class RunContext:
    run: dict[str, Any]
    verticale: dict[str, Any] | None
    max_leads: int = 500
    max_budget_eur: float = 50.0

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

    @property
    def budget_eur(self) -> float:
        """Budget du run (€). Fallback sur le plafond worker si absent/invalide."""
        v = self.run.get("budget_eur")
        try:
            b = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            b = 0.0
        return b if b > 0 else self.max_budget_eur


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
                    "adresse": f"{ville} {cp}".strip(),
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
                    "score_raison": (
                        "Hors cible : effectif/secteur hors critères (démo)"
                        if hors_filtre
                        else (
                            f"Bon potentiel : {effectif} salariés, {_libelle_naf(naf)}"
                            + (f" · signal détecté : {signal}" if signal else "")
                        )
                    ),
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


# --- Pipeline réel -----------------------------------------------------------


class RealPipeline:
    """Exécute le vrai moteur L1→L4 et renvoie des leads réels (contrat Supabase).

    Construit une `CampaignConfig` programmatique depuis le `RunContext`, applique
    le ciblage de la verticale (fichier `verticales/<slug>/verticale.yaml` — source
    de vérité), exécute l'orchestrateur partagé avec la CLI, puis mappe chaque
    `LeadStage4` vers le schéma `leads`. Le moteur lit ses clés via `get_settings()`
    (GOOGLE_PLACES, ANTHROPIC, opt. DROPCONTACT/PAPPERS/SOCIETEINFO).
    """

    def run(self, ctx: RunContext, emit: EmitFn) -> RunResult:
        import tempfile
        from pathlib import Path

        from renoboost_leads.models import RunStats
        from renoboost_leads.orchestrateur import executer_pipeline
        from renoboost_leads.settings import get_settings

        settings = get_settings()
        self._verifier_cles(settings)

        cfg, sirene_first = self._construire_config(ctx, settings)

        # Découverte : verticale fichier → Places-first (ciblage riche) ; verticale
        # base-only (créée dans le CRM, sans fichier) → SIRENE-first par NAF (stage 0),
        # qui n'a pas besoin de requêtes Google Places. L3.5 seulement si clé dispo.
        if sirene_first:
            stages = [0, 1, 2, 3, 3.5, 4] if settings.has_dropcontact() else [0, 1, 2, 3, 4]
        else:
            stages = [1, 2, 3, 3.5, 4] if settings.has_dropcontact() else [1, 2, 3, 4]

        stats = RunStats(
            session_id=str(ctx.run.get("id")),
            campaign=cfg.run.client_name,
            debut=datetime.now(timezone.utc),
            emetteur_email=cfg.emetteur.email if cfg.emetteur else None,
        )

        output_dir = Path(tempfile.mkdtemp(prefix="renoboost-run-"))
        result = executer_pipeline(
            cfg,
            settings,
            stages,
            output_dir,
            stats,
            l2_provider="datagouv",
            dry_run=False,
            emit=emit,
        )

        leads = [self._mapper_lead(lead, ctx) for lead in result.leads_finaux]
        self._enrichir_satellite(leads, emit)

        base = result.leads_l2 if result.leads_l2 is not None else result.leads_l1
        decouverte = len(base) if base is not None else 0
        qualifies = sum(
            1 for lead in (base or []) if not getattr(lead, "hors_filtre_entreprise", False)
        )
        counts = {"decouverte": decouverte, "qualifies": qualifies, "leads": len(leads)}
        return RunResult(leads=leads, counts=counts, cout_eur=round(stats.cout_total_eur, 2))

    @staticmethod
    def _verifier_cles(settings: Any) -> None:
        """Échoue clairement (avant tout traitement) si une clé L1/L4 manque."""
        manquantes = []
        if not settings.has_google_places():
            manquantes.append("GOOGLE_PLACES_API_KEY (étage 1 — découverte)")
        if not settings.has_anthropic():
            manquantes.append("ANTHROPIC_API_KEY (étage 4 — scoring)")
        if manquantes:
            raise RuntimeError(
                "WORKER_MODE=real : clé(s) API requise(s) absente(s) : "
                + ", ".join(manquantes)
                + ". Définis-les dans l'environnement Railway, ou repasse en WORKER_MODE=demo."
            )

    def _construire_config(self, ctx: RunContext, settings: Any) -> tuple[Any, bool]:
        """Construit la CampaignConfig et indique le mode de découverte.

        Returns:
            (cfg, sirene_first) — `sirene_first=True` quand le ciblage vient de la
            base (verticale CRM sans fichier repo) → découverte par NAF (stage 0).
        """
        from datetime import date

        from renoboost_leads.models import (
            Budget,
            CampaignConfig,
            RunInfo,
            SecteurCible,
            StagesFlags,
            Volume,
        )
        from renoboost_leads.verticale.contexte import contexte_client_depuis_verticale

        if not ctx.verticale or not ctx.verticale.get("slug"):
            raise RuntimeError(
                "Run sans verticale exploitable : impossible de cibler. "
                "Associe une verticale (slug) au run avant de le lancer."
            )
        slug = str(ctx.verticale["slug"])
        verticale_fichier = self._charger_verticale_fichier(slug)
        description = (
            verticale_fichier.verticale.nom
            if verticale_fichier is not None
            else (ctx.verticale.get("nom") or slug)
        )

        volume_cible = max(1, min(ctx.volume_cible, ctx.max_leads))
        budget_eur = min(ctx.budget_eur, ctx.max_budget_eur)

        cfg = CampaignConfig(
            run=RunInfo(
                client_name=slug[:80],
                description=description,
                campaign_date=date.today().isoformat(),
            ),
            stages=StagesFlags(
                enable_stage_1_decouverte=True,
                enable_stage_2_entreprises=True,
                enable_stage_3_contacts=True,
                enable_stage_3_5_enrichment=settings.has_dropcontact(),
                enable_stage_4_prospection=True,
            ),
            # Placeholder requis (secteurs min 1) — écrasé par la verticale fichier ;
            # inutilisé en SIRENE-first (stage 1 sauté).
            secteurs=[SecteurCible(type="establishment", query=slug)],
            zone=self._construire_zone(ctx),
            volume=Volume(cible=volume_cible),
            budget=Budget(max_eur=budget_eur),
        )
        import os

        # Économie (défaut) : Claude NE score/rédige PAS les leads hors-filtre
        # (souvent ~60% de la découverte) — tu ne les contactes pas. Ils restent
        # insérés au CRM (flagués hors-filtre), simplement sans score ni mail, ce
        # qui réduit d'autant le coût L4. Mettre WORKER_SCORE_HORS_FILTRE=true pour
        # les faire scorer quand même (ancien comportement).
        cfg.claude_scoring.scorer_hors_filtre = (
            os.environ.get("WORKER_SCORE_HORS_FILTRE", "false").strip().lower()
            in ("1", "true", "yes", "on")
        )

        # Gros volume : scraping L3 parallélisé (attente réseau dominante). Pilotable
        # via WORKER_SCRAPE_WORKERS ; défaut 8, borné par la validation du modèle.
        try:
            workers = int(os.environ.get("WORKER_SCRAPE_WORKERS", "8"))
        except ValueError:
            workers = 8
        cfg.scraping_l3.parallelisme = max(1, min(workers, 32))

        if verticale_fichier is not None:
            # Ciblage = verticale fichier (source de vérité, ciblage riche Places).
            cfg.secteurs = verticale_fichier.cibles.secteurs_places
            cfg.filtres_entreprise = verticale_fichier.cibles.filtres_entreprise
            cfg.claude_scoring.seuil_top_lead = verticale_fichier.qualification.seuil_score_top
            # Mail L4 : offre + signature au nom du client (sinon défaut RénoBoost).
            cfg.claude_scoring.contexte_client = contexte_client_depuis_verticale(
                verticale_fichier
            )
            if verticale_fichier.emetteur is not None:
                cfg.emetteur = verticale_fichier.emetteur
            # Découverte : opt-in par verticale. Quand la liste NAF est fiable,
            # SIRENE-first (étage 0) pré-filtre à la source gratuite et évite de
            # payer Places sur des leads jetés ensuite (cf. taux_hors_filtre).
            # Les `secteurs_places` deviennent alors un simple enrichissement par nom.
            sirene_first = verticale_fichier.cibles.decouverte_sirene_first
        else:
            # Ciblage = config CRM (base) → découverte SIRENE-first par NAF.
            cfg.filtres_entreprise = self._filtres_depuis_config_crm(ctx.verticale, slug)
            cfg.claude_scoring.contexte_client = self._contexte_depuis_config_crm(ctx.verticale)
            sirene_first = True

        # Override per-run : tranche d'effectif (min ET max) depuis la zone du CRM,
        # sans toucher au ciblage NAF porté par la verticale. Le plafond évite de
        # remonter des grands groupes hors cœur de cible PME.
        effectif_min = ctx.zone.get("effectif_min")
        if effectif_min is not None:
            cfg.filtres_entreprise.effectif_min = int(effectif_min)
        effectif_max = ctx.zone.get("effectif_max")
        if effectif_max is not None:
            cfg.filtres_entreprise.effectif_max = int(effectif_max)

        return cfg, sirene_first

    @staticmethod
    def _charger_verticale_fichier(slug: str) -> Any | None:
        """Charge la verticale fichier si elle existe, sinon None (verticale base-only).

        Un fichier présent mais corrompu lève une erreur actionnable (vs absent,
        qui bascule proprement sur le ciblage base).
        """
        from renoboost_leads.verticale import load_verticale
        from renoboost_leads.verticale.loader import VERTICALES_DIR

        if not (VERTICALES_DIR / slug / "verticale.yaml").exists():
            return None
        try:
            return load_verticale(slug)
        except Exception as exc:  # noqa: BLE001 — message actionnable
            raise RuntimeError(f"Verticale '{slug}' présente mais illisible : {exc}") from exc

    @staticmethod
    def _filtres_depuis_config_crm(verticale_row: dict[str, Any], slug: str) -> Any:
        """Construit les FiltresEntreprise depuis le `config` d'une verticale CRM.

        Le CRM stocke {offre, secteurs_naf, effectif_min, signaux}. Le ciblage NAF
        est requis pour la découverte SIRENE-first (sinon on draguerait toute la
        zone) : on refuse explicitement une verticale base-only sans NAF.
        """
        from renoboost_leads.models import FiltresEntreprise

        config = verticale_row.get("config") or {}
        naf = [str(x) for x in (config.get("secteurs_naf") or []) if str(x).strip()]
        if not naf:
            raise RuntimeError(
                f"Verticale '{slug}' sans fichier repo ni ciblage NAF en base "
                "(config.secteurs_naf vide) : impossible de cibler. Renseigne des "
                "codes NAF (secteurs) dans la fiche Cible du CRM, ou ajoute un "
                "fichier verticale au repo."
            )
        effectif_min = config.get("effectif_min")
        return FiltresEntreprise(
            naf_inclus=naf,
            effectif_min=int(effectif_min) if effectif_min is not None else None,
        )

    @staticmethod
    def _contexte_depuis_config_crm(verticale_row: dict[str, Any]) -> str | None:
        """Bloc « # Offre commerciale » d'une verticale CRM (base-only).

        Évite le contexte par défaut (RénoBoost) pour les mails L4 : on reconstruit
        une offre minimale depuis {nom, offre, signaux}. None si rien d'exploitable.
        """
        config = verticale_row.get("config") or {}
        nom = verticale_row.get("nom") or "Notre société"
        offre = config.get("offre")
        signaux = [str(s) for s in (config.get("signaux") or []) if str(s).strip()]
        if not offre and not signaux:
            return None
        lignes = [f"{nom}."]
        if offre:
            lignes.append(f"Offre : {offre}.")
        if signaux:
            lignes.append("Signaux d'intérêt :")
            lignes.extend(f"- {s}" for s in signaux[:6])
        return "\n".join(lignes)

    @staticmethod
    def _construire_zone(ctx: RunContext) -> Any:
        """Zone moteur depuis la zone du run : point GPS (#38) si fourni, sinon département."""
        from renoboost_leads.models import Zone

        z = ctx.zone
        lat, lon = z.get("latitude"), z.get("longitude")
        adresse = z.get("adresse")
        a_coords = lat is not None and lon is not None
        a_adresse = bool(adresse and str(adresse).strip())
        if a_coords or a_adresse:
            return Zone(
                type="point",
                latitude=float(lat) if a_coords else None,
                longitude=float(lon) if a_coords else None,
                adresse=str(adresse) if a_adresse else None,
                rayon_par_point_km=float(z.get("rayon_par_point_km") or 10.0),
            )
        return Zone(type="departement", codes=[ctx.departement])

    @staticmethod
    def _enrichir_satellite(leads: list[dict[str, Any]], emit: EmitFn) -> None:
        """Analyse 'potentiel solaire' (IGN + vision) si WORKER_SATELLITE est activé."""
        import os

        from .satellite import analyser_potentiel, satellite_active, satellite_max

        if not satellite_active():
            return
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return
        # Priorité aux meilleurs scores, dans la limite du plafond.
        candidats = [
            lead
            for lead in leads
            if lead.get("latitude") is not None and lead.get("longitude") is not None
        ]
        candidats.sort(key=lambda x: x.get("score") or 0, reverse=True)
        candidats = candidats[: satellite_max()]
        for i, lead in enumerate(candidats):
            res = analyser_potentiel(
                float(lead["latitude"]),
                float(lead["longitude"]),
                api_key,
                signaux_ve=bool(lead.get("signaux_ve")),
                exploitant=lead.get("entreprise"),
            )
            if res is not None:
                lead["vision_satellite"] = res
            if (i + 1) % 5 == 0:
                emit("Analyse satellite", 97, {"satellite": i + 1})

    @staticmethod
    def _mapper_lead(lead: Any, ctx: RunContext) -> dict[str, Any]:
        """Mappe un LeadStage4 vers une ligne du contrat `leads`."""
        prenom = getattr(lead, "dirigeant_prenom", None)
        nom_dir = getattr(lead, "dirigeant_nom", None)
        contact_nom = " ".join(p for p in (prenom, nom_dir) if p) or None

        emails_verifies = getattr(lead, "emails_verifies", None) or []
        contact_email = getattr(lead, "email_dropcontact", None) or (
            emails_verifies[0] if emails_verifies else None
        )
        contact_tel = getattr(lead, "telephone_direct_dropcontact", None) or getattr(
            lead, "telephone", None
        )

        return {
            "run_id": ctx.run.get("id"),
            "verticale_id": ctx.run.get("verticale_id"),
            "entreprise": getattr(lead, "nom", None),
            "siren": getattr(lead, "siren", None),
            "naf": getattr(lead, "code_naf", None),
            "libelle_naf": getattr(lead, "libelle_naf", None),
            "effectif": getattr(lead, "libelle_effectif", None),
            "ville": getattr(lead, "ville", None),
            "code_postal": getattr(lead, "code_postal", None),
            "adresse": getattr(lead, "adresse", None),
            "latitude": getattr(lead, "latitude", None),
            "longitude": getattr(lead, "longitude", None),
            "score": getattr(lead, "score_interet", None),
            "contact_nom": contact_nom,
            "contact_email": contact_email,
            "contact_tel": contact_tel,
            "contact_linkedin": getattr(lead, "linkedin_dirigeant_dropcontact", None),
            "entreprise_linkedin": getattr(lead, "linkedin_entreprise_dropcontact", None),
            "site_web": getattr(lead, "site_web", None),
            "hors_filtre": getattr(lead, "hors_filtre_entreprise", False),
            "raison_hors_filtre": getattr(lead, "raison_hors_filtre", None),
            "mail_sujet": getattr(lead, "email_objet", None),
            "mail_corps": getattr(lead, "email_corps", None),
            "score_raison": getattr(lead, "raison_score", None),
            "statut": "a_valider",
        }


def build_pipeline(mode: str, *, seed: int | None = None) -> Pipeline:
    if mode == "demo":
        return DemoPipeline(seed=seed)
    if mode == "real":
        return RealPipeline()
    raise ValueError(f"Mode de pipeline inconnu : {mode!r}")
