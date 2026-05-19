"""Interface Streamlit — RénoBoost Leads.

Quatre onglets :
1. 📊 Veille du jour    — résumé du dernier run veille + top leads
2. 📥 Nouveau run       — upload CSV (AAA Data ou autre) + lancement
3. 📁 Sessions          — historique L1-L4 + déclenchement L4 sur ancienne session
4. 📈 Stats             — agrégation cross-runs

Lancement :
    pip install -e ".[ui]"
    streamlit run app.py
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


def _bridge_streamlit_secrets_to_env() -> None:
    """Sur Streamlit Cloud, expose `st.secrets` à `os.environ` pour Settings.

    Settings (pydantic-settings) lit depuis l'environnement / .env. Sur Cloud,
    on n'a ni l'un ni l'autre — uniquement `st.secrets`. Ce bridge copie chaque
    clé secret vers `os.environ` *avant* la première instanciation de Settings.

    No-op en local (pas de secrets file → `st.secrets` lève KeyError) — le
    .env standard prend le relais.
    """
    try:
        secrets_dict = dict(st.secrets)  # type: ignore[arg-type]
    except (FileNotFoundError, st.runtime.secrets.StreamlitSecretNotFoundError):
        return
    except Exception:  # noqa: BLE001 — pas de secrets, on ignore proprement
        return
    for key, value in secrets_dict.items():
        # Ne jamais écraser une variable déjà définie dans l'env (priorité au shell)
        if value is None or key in os.environ:
            continue
        os.environ[key] = str(value)


_bridge_streamlit_secrets_to_env()


# noqa: E402 — les imports ci-dessous viennent APRÈS le bridge des secrets
# Streamlit (volontaire), pour que Settings voie les variables au bon moment.
from renoboost_leads.exporter import (  # noqa: E402
    export_csv_crm,
    lire_stage4_csv,
)
from renoboost_leads.models import ClaudeScoring  # noqa: E402
from renoboost_leads.settings import PROJECT_ROOT, get_settings  # noqa: E402
from renoboost_leads.stage4_prospection.prompt_template import (  # noqa: E402
    CONTEXTE_CLIENT_DEFAUT,
)
from renoboost_leads.veille_immatriculations.exporter_veille import (  # noqa: E402
    COLONNES_VEILLE,
)
from renoboost_leads.veille_immatriculations.parser_generique import (  # noqa: E402
    detecter_format_csv,
)
from renoboost_leads.veille_immatriculations.pipeline_veille import (  # noqa: E402
    VeilleRunConfig,
    executer_cycle_veille,
)

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _read_anthropic_key() -> str | None:
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            val = st.secrets["ANTHROPIC_API_KEY"]
            if val:
                return str(val)
    except Exception:  # noqa: BLE001, S110 — st.secrets non dispo en local
        return os.environ.get("ANTHROPIC_API_KEY") or None
    try:
        s = get_settings()
        if s.has_anthropic():
            return s.anthropic_api_key.get_secret_value()
    except Exception:  # noqa: BLE001, S110 — .env absent / mal formé
        return os.environ.get("ANTHROPIC_API_KEY") or None
    return os.environ.get("ANTHROPIC_API_KEY") or None


def _sessions_classiques() -> list[Path]:
    base = PROJECT_ROOT / "data" / "output"
    if not base.exists():
        return []
    return sorted(
        (d for d in base.iterdir() if d.is_dir()), key=lambda d: d.name, reverse=True
    )


def _runs_veille() -> list[Path]:
    base = PROJECT_ROOT / "data" / "veille"
    if not base.exists():
        return []
    return sorted(
        (d for d in base.iterdir() if d.is_dir() and (d / "veille_leads.csv").exists()),
        key=lambda d: d.name,
        reverse=True,
    )


def _charger_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


# ═══════════════════════════════════════════════════════════════════
# Page setup
# ═══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="RénoBoost Leads",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Sidebar : statut système ──
with st.sidebar:
    st.title("RénoBoost Leads")
    st.caption("Plateforme de prospection B2B")

    settings = get_settings()
    st.subheader("État du système")

    cle_anthropic = _read_anthropic_key()
    st.write("🔑 **Anthropic** :", "✓ active" if cle_anthropic else "✗ absente")
    st.write("📍 **Google Places** :", "✓ active" if settings.has_google_places() else "✗ absente")
    st.write(
        "💎 **Dropcontact** :",
        "✓ active" if settings.has_dropcontact() else "✗ absente",
    )
    st.write("📧 **SMTP veille** :", "✓ configuré" if settings.has_smtp() else "✗ absent")

    st.divider()
    py = f"{os.sys.version_info.major}.{os.sys.version_info.minor}"
    st.caption(f"Version : 0.10.0  •  Python {py}")
    st.caption(f"Projet : `{PROJECT_ROOT.name}`")


# ═══════════════════════════════════════════════════════════════════
# Onglets
# ═══════════════════════════════════════════════════════════════════

tab_recherche, tab_veille, tab_nouveau, tab_sessions, tab_stats, tab_copilote = st.tabs(
    [
        "🔎 Nouvelle recherche",
        "📊 Veille du jour",
        "📥 Nouveau run",
        "📁 Sessions",
        "📈 Stats",
        "🤖 Copilote",
    ]
)


# ───────────────────────────────────────────────────────────────────
# ONGLET 0 : Nouvelle recherche prospect (form non-technique)
# ───────────────────────────────────────────────────────────────────

with tab_recherche:
    st.header("🔎 Nouvelle recherche de prospects")
    st.caption(
        "Configure et lance une recherche en quelques clics — pas besoin "
        "de toucher au YAML. Génère la config + lance L1+L2+L3, puis va "
        "dans l'onglet **📁 Sessions** pour télécharger le rapport HTML."
    )

    from renoboost_leads.agent.tools.workflow import clone_config

    # Liste des configs disponibles comme template (utilise les client_*.yaml)
    templates = sorted(
        (PROJECT_ROOT / "config").glob("client_*.yaml"),
        key=lambda p: p.name,
    )
    if not templates:
        templates = sorted((PROJECT_ROOT / "config").glob("*.yaml"))
    template_names = [t.name for t in templates]

    if not template_names:
        st.error("Aucun template de config trouvé dans `config/`. "
                 "Ajoute au moins un YAML avant de lancer une recherche.")
    else:
        col_a, col_b = st.columns([2, 1])
        with col_a:
            base = st.selectbox(
                "Modèle de départ",
                template_names,
                help="Copie ce config et applique tes paramètres par-dessus. "
                "`client_rossini.yaml` = sites industriels Nord (preset).",
            )
        with col_b:
            stages_choisis = st.selectbox(
                "Étages à lancer",
                ["1,2,3", "1,2", "1,2,3,3.5"],
                help="L1=Google Places, L2=Sirene, L3=scraping contacts, "
                "L3.5=Dropcontact (clé requise).",
            )

        st.subheader("Paramètres")
        col1, col2 = st.columns(2)
        with col1:
            nom_campagne = st.text_input(
                "Nom de la campagne",
                value="recherche-2026-05",
                help="Identifie ton run (apparaît dans le rapport).",
            )
            volume = st.slider(
                "Volume cible (leads)", 5, 100, 10, step=5,
                help="Nombre de prospects souhaités. ~0.03 € par lead L1.",
            )
            budget = st.number_input(
                "Plafond budget €", 0.5, 50.0, 5.0, 0.5,
                help="Coupe le run si dépassé.",
            )
        with col2:
            depts = st.text_input(
                "Départements (ex: `59, 62, 80`)",
                value="59",
                help="Codes INSEE séparés par virgules. Ou code postal pour "
                "zone fine.",
            )
            secteurs_str = st.text_area(
                "Secteurs cibles (un par ligne)",
                value="site industriel\nplateforme logistique",
                height=120,
                help="Requêtes Google Places brutes — comme tu les "
                "taperais dans Maps.",
            )

        # Bouton de lancement
        api_ok = bool(_read_anthropic_key()) and settings.has_google_places()
        if not settings.has_google_places():
            st.warning("⚠ GOOGLE_PLACES_API_KEY absente — impossible de lancer "
                       "L1. Configure-la dans les secrets.")

        if st.button(
            "🚀 Générer et lancer la recherche",
            type="primary",
            disabled=not api_ok,
            use_container_width=True,
        ):
            secteurs = [s.strip() for s in secteurs_str.splitlines() if s.strip()]
            if not secteurs:
                st.error("Indique au moins un secteur.")
                st.stop()

            save_name = nom_campagne.replace(" ", "_").replace("/", "_")

            with st.spinner("Création de la config…"):
                cfg_res = clone_config(
                    source_path=base,
                    save_as=save_name,
                    overrides={
                        "client_name": nom_campagne,
                        "zone_codes": depts,
                        "secteurs": secteurs,
                        "volume_cible": volume,
                        "budget_max_eur": budget,
                    },
                )

            if "error" in cfg_res:
                st.error(f"Erreur config : {cfg_res['error']}")
                st.stop()

            st.success(f"✓ Config créée : `{cfg_res['path']}`")
            with st.expander("Voir le YAML généré"):
                contenu = (PROJECT_ROOT / cfg_res["path"]).read_text(
                    encoding="utf-8"
                )
                st.code(contenu, language="yaml")

            # ─── Exécution streamée du pipeline ──────────────────────
            # subprocess.Popen + lecture ligne par ligne pour donner
            # un feedback live à l'utilisateur (au lieu d'un spinner
            # figé pendant 3-8 min). Garde aussi le WebSocket Streamlit
            # actif, ce qui aide sur Streamlit Cloud (timeout reverse-
            # proxy ~5 min en cas d'inactivité).
            import os as _os
            import subprocess as _sp
            import sys as _sys
            import time as _time

            cfg_full = PROJECT_ROOT / cfg_res["path"]
            cmd = [
                _sys.executable,
                "-m",
                "renoboost_leads.cli",
                "run",
                "--config",
                str(cfg_full),
                "--stages",
                stages_choisis,
            ]

            st.markdown("### 🔄 Recherche en cours")
            status_box = st.empty()
            metric_cols = st.columns(3)
            duree_box = metric_cols[0].empty()
            stage_box = metric_cols[1].empty()
            lignes_box = metric_cols[2].empty()
            log_container = st.empty()

            logs_buffer: list[str] = []
            current_stage = "Initialisation"
            TIMEOUT_S = 1800  # 30 min — marge confortable
            start = _time.time()

            env = _os.environ.copy()
            # Force l'unbuffering Python sinon les logs CLI n'arrivent
            # qu'à la fin (buffering 4kB par défaut sur pipe).
            env["PYTHONUNBUFFERED"] = "1"

            try:
                # S603 ignoré : cmd ne contient que sys.executable + literals
                # + chemins issus de clone_config (déjà chroot/sanitized).
                proc = _sp.Popen(  # noqa: S603
                    cmd,
                    stdout=_sp.PIPE,
                    stderr=_sp.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(PROJECT_ROOT),
                    encoding="utf-8",
                    env=env,
                )
            except OSError as e:
                st.error(f"Impossible de lancer le subprocess : {e}")
                st.stop()

            rc: int | None = None
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    logs_buffer.append(line)

                    # Détection grossière de l'étage courant dans les logs
                    low = line.lower()
                    if "étage 1" in low or "etage1" in low or "stage 1" in low:
                        current_stage = "L1 — Google Places"
                    elif "étage 2" in low or "etage2" in low or "stage 2" in low:
                        current_stage = "L2 — Sirene"
                    elif "étage 3.5" in low or "etage3_5" in low:
                        current_stage = "L3.5 — Dropcontact"
                    elif "étage 3" in low or "etage3" in low or "stage 3" in low:
                        current_stage = "L3 — Scraping"
                    elif "étage 4" in low or "etage4" in low:
                        current_stage = "L4 — Prospection"

                    elapsed = int(_time.time() - start)
                    mn, sec = divmod(elapsed, 60)
                    status_box.info(
                        f"⏱ **{mn}min {sec:02d}s** · {current_stage}"
                    )
                    duree_box.metric("Durée", f"{mn}:{sec:02d}")
                    stage_box.metric(
                        "Étage", current_stage.split(" — ")[0]
                    )
                    lignes_box.metric("Logs", len(logs_buffer))
                    log_container.code(
                        "\n".join(logs_buffer[-30:]), language="text"
                    )

                    if _time.time() - start > TIMEOUT_S:
                        proc.kill()
                        st.error(
                            f"⏱ Timeout après {TIMEOUT_S}s — process tué."
                        )
                        break
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except _sp.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                rc = proc.returncode

            total = int(_time.time() - start)
            mn, sec = divmod(total, 60)
            status_box.empty()

            if rc == 0:
                st.success(
                    f"✓ Recherche terminée en **{mn}min {sec:02d}s**. "
                    "Onglet **📁 Sessions** pour télécharger le rapport HTML."
                )
                st.balloons()
            else:
                st.error(
                    f"Échec du pipeline (code retour {rc}) après "
                    f"{mn}min {sec:02d}s."
                )

            with st.expander(
                f"Logs complets ({len(logs_buffer)} lignes)"
            ):
                st.code(
                    "\n".join(logs_buffer[-200:]) or "(aucun log)",
                    language="text",
                )


# ───────────────────────────────────────────────────────────────────
# ONGLET 1 : Veille du jour
# ───────────────────────────────────────────────────────────────────

with tab_veille:
    st.header("📊 Veille du jour")
    runs = _runs_veille()
    if not runs:
        st.info(
            "Aucun run de veille pour l'instant. Va dans l'onglet **📥 Nouveau run** "
            "pour uploader un fichier CSV (AAA Data ou autre source)."
        )
    else:
        labels = [r.name for r in runs]
        choix = st.selectbox(
            "Choisir un run", labels, index=0, key="veille_select"
        )
        run_dir = runs[labels.index(choix)]

        df = _charger_csv(run_dir / "veille_leads.csv")
        nb_total = len(df)
        nb_top = (df["top_lead"] == "VRAI").sum() if "top_lead" in df.columns else 0
        scores = (
            pd.to_numeric(df["score_interet"], errors="coerce").dropna()
            if "score_interet" in df.columns
            else pd.Series([], dtype=float)
        )
        score_moyen = scores.mean() if not scores.empty else 0
        nb_deja_vus = (df["deja_eu_ve"] == "VRAI").sum() if "deja_eu_ve" in df.columns else 0
        nb_nouveaux = nb_total - nb_deja_vus

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total leads", nb_total)
        c2.metric("⭐ Top leads", nb_top)
        c3.metric("Score moyen", f"{score_moyen:.0f}" if score_moyen else "—")
        c4.metric("Nouveaux SIREN", f"{nb_nouveaux}/{nb_total}")

        # Filtres rapides
        st.subheader("Filtres")
        f1, f2, f3 = st.columns(3)
        only_top = f1.checkbox("⭐ Top leads seulement", value=False)
        only_nouveaux = f2.checkbox("🆕 Nouveaux SIREN seulement", value=False)
        score_min = f3.slider("Score minimum", 0, 100, 0, step=5)

        df_filtre = df.copy()
        if only_top and "top_lead" in df_filtre.columns:
            df_filtre = df_filtre[df_filtre["top_lead"] == "VRAI"]
        if only_nouveaux and "deja_eu_ve" in df_filtre.columns:
            df_filtre = df_filtre[df_filtre["deja_eu_ve"] != "VRAI"]
        if score_min > 0 and "score_interet" in df_filtre.columns:
            df_filtre = df_filtre[
                pd.to_numeric(df_filtre["score_interet"], errors="coerce").fillna(0) >= score_min
            ]

        st.write(f"**{len(df_filtre)} leads après filtrage**")

        cols_visibles = [c for c in COLONNES_VEILLE[:14] if c in df_filtre.columns]
        st.dataframe(df_filtre[cols_visibles], use_container_width=True, height=400)

        # Détail expandable d'un top lead
        if not df_filtre.empty:
            st.subheader("🎯 Aperçu top leads (raisons + pitchs)")
            top_df = df_filtre[df_filtre.get("top_lead", "FAUX") == "VRAI"].head(5)
            for _, row in top_df.iterrows():
                with st.expander(
                    f"**{row.get('nom', '?')}** "
                    f"— score {row.get('score_interet', '?')} "
                    f"— SIREN {row.get('siren', '?')}"
                ):
                    st.markdown(f"**Pourquoi :** {row.get('raison_score', '—')}")
                    st.markdown("**Pitch proposé :**")
                    st.code(row.get("pitch_propose", "—"), language=None)
                    if row.get("marque_ve") or row.get("modele_ve"):
                        st.caption(
                            f"🚗 {row.get('marque_ve', '')} {row.get('modele_ve', '')} "
                            f"({row.get('energie_ve', '')}) "
                            f"immat le {row.get('date_immatriculation_ve', '?')}"
                        )

        # Téléchargements
        st.download_button(
            "📤 Télécharger CSV filtré",
            df_filtre.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"veille_filtre_{run_dir.name}.csv",
            mime="text/csv",
        )


# ───────────────────────────────────────────────────────────────────
# ONGLET 2 : Nouveau run veille (upload CSV)
# ───────────────────────────────────────────────────────────────────

with tab_nouveau:
    st.header("📥 Nouveau run de veille")
    st.caption(
        "Upload un fichier CSV (AAA Data, ou autre source). L'app détecte "
        "automatiquement le séparateur, l'encodage et propose un mapping des colonnes."
    )

    uploaded = st.file_uploader(
        "Fichier CSV à analyser",
        type=["csv", "txt"],
        help=(
            "Format type AAA Data : DATE_IMMATRICULATION;MARQUE;MODELE;"
            "ENERGIE;TYPE_ACQUEREUR;SIREN…"
        ),
    )

    if uploaded is not None:
        # Sauvegarde temporaire pour pouvoir détecter
        with tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, dir=tempfile.gettempdir()
        ) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = Path(tmp.name)

        try:
            detection = detecter_format_csv(tmp_path)
        except Exception as e:  # noqa: BLE001
            st.error(f"Erreur de détection : {e}")
            st.stop()

        st.success(
            f"✓ Détecté : encodage **{detection.encodage_detecte}**, "
            f"séparateur **`{detection.separateur_detecte}`**, "
            f"**{len(detection.colonnes_brutes)}** colonnes."
        )

        # Preview
        df_preview = pd.read_csv(
            tmp_path,
            sep=detection.separateur_detecte,
            encoding=detection.encodage_detecte,
            nrows=5,
        )
        st.subheader("Aperçu (5 premières lignes)")
        st.dataframe(df_preview, use_container_width=True)

        # Mapping interactif
        st.subheader("Mapping des colonnes")
        if detection.utilisable:
            st.success(f"✓ Mapping automatique : {detection.mapping_propose}")
        else:
            st.warning(
                f"⚠ Champs obligatoires manquants : {', '.join(detection.champs_manquants)}. "
                "Ajuste manuellement ci-dessous."
            )

        champs_internes = [
            "(ignorer)",
            "date_immatriculation",
            "plaque",
            "marque",
            "modele",
            "energie",
            "type_vehicule",
            "type_acquereur",
            "siren",
            "raison_sociale",
            "code_postal",
            "commune",
            "departement",
        ]
        mapping_final: dict[str, str] = {}
        cols_per_row = 3
        for i in range(0, len(detection.colonnes_brutes), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for j, col_fichier in enumerate(detection.colonnes_brutes[i : i + cols_per_row]):
                with row_cols[j]:
                    default_val = detection.mapping_propose.get(col_fichier, "(ignorer)")
                    sel = st.selectbox(
                        col_fichier,
                        options=champs_internes,
                        index=champs_internes.index(default_val)
                        if default_val in champs_internes
                        else 0,
                        key=f"mapping_{col_fichier}",
                    )
                    if sel != "(ignorer)":
                        mapping_final[col_fichier] = sel

        # Paramètres veille
        st.subheader("Paramètres scoring L4")
        c1, c2, c3 = st.columns(3)
        modele = c1.selectbox("Modèle Claude", ["claude-haiku-4-5", "claude-sonnet-4-6"])
        seuil = c2.slider("Seuil top_lead", 0, 100, 70, step=5)
        budget = c3.number_input("Plafond budget €", 0.10, 100.0, 5.0, 0.5)

        c4, c5 = st.columns(2)
        inclure_pitch = c4.checkbox("Inclure pitch", value=True)
        dry_run = c5.checkbox(
            "Mode dry-run (pas d'appel Anthropic)", value=not bool(cle_anthropic)
        )

        contexte_default = st.checkbox(
            "Utiliser le contexte RénoBoost par défaut", value=True
        )
        contexte_client: str | None = None
        if not contexte_default:
            contexte_client = st.text_area(
                "Contexte commercial",
                value=CONTEXTE_CLIENT_DEFAUT,
                height=200,
            )

        if st.button("🚀 Lancer la veille", type="primary", use_container_width=True):
            from renoboost_leads.veille_immatriculations.models import VeilleConfig

            if not dry_run and not cle_anthropic:
                st.error("ANTHROPIC_API_KEY manquante. Active dry-run ou configure la clé.")
                st.stop()

            # Préparer dossier sortie
            date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
            output_dir = PROJECT_ROOT / "data" / "veille" / f"{date_str}_ui_upload"
            output_dir.mkdir(parents=True, exist_ok=True)

            veille_cfg = VeilleConfig(
                separateur=detection.separateur_detecte,
                encodage=detection.encodage_detecte,
                mapping_colonnes=mapping_final,
            )
            run_cfg = VeilleRunConfig(
                source_veille="ui_upload",
                veille_config=veille_cfg,
                claude_scoring=ClaudeScoring(
                    modele=modele,
                    seuil_top_lead=seuil,
                    inclure_pitch=inclure_pitch,
                    contexte_client=contexte_client,
                ),
                budget_eur=float(budget),
                anthropic_api_key=cle_anthropic if not dry_run else None,
                dry_run_l4=dry_run,
                # Pas d'envoi mail depuis l'UI (peut être ajouté en config)
                smtp_config=None,
            )

            with st.spinner("Veille en cours…"):
                resultat = executer_cycle_veille(tmp_path, output_dir, run_cfg)

            st.success(
                f"✓ {resultat.nb_top_leads} top leads / {resultat.nb_ve_flotte} VE flotte "
                f"({resultat.nb_nouveaux} nouveaux, {resultat.nb_deja_vus} déjà vus)"
            )
            st.balloons()
            st.info(
                f"Va dans l'onglet **📊 Veille du jour** pour explorer les résultats. "
                f"Dossier : `{output_dir.name}`"
            )


# ───────────────────────────────────────────────────────────────────
# ONGLET 3 : Sessions classiques L1-L4
# ───────────────────────────────────────────────────────────────────

with tab_sessions:
    st.header("📁 Sessions L1-L4")
    sessions = _sessions_classiques()
    if not sessions:
        st.info(
            "Aucune session classique. "
            "Lance `python -m renoboost_leads.cli run --stages 1,2,3`."
        )
    else:
        labels = [s.name for s in sessions]
        choix = st.selectbox("Session", labels, key="sess_select")
        session_dir = sessions[labels.index(choix)]

        csv_l4 = session_dir / "etage4_prospection.csv"
        csv_l35 = session_dir / "etage3_5_enrichissement.csv"
        csv_l3 = session_dir / "etage3_contacts.csv"

        # ── Rapport HTML (livrable client, dispo dès L3) ──
        if csv_l3.exists():
            from renoboost_leads.agent.tools.report import generate_report

            colr1, colr2 = st.columns([1, 3])
            with colr1:
                max_leads = st.number_input(
                    "Max leads dans le rapport",
                    min_value=1, max_value=200, value=50, step=10,
                    key=f"rep_max_{session_dir.name}",
                )
            with colr2:
                if st.button(
                    "📄 Générer le rapport HTML",
                    key=f"rep_btn_{session_dir.name}",
                    help="Livrable client autonome (CSS inline). "
                    "Ctrl+P dans le navigateur pour exporter en PDF.",
                ):
                    res = generate_report(session_dir.name, max_leads=int(max_leads))
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        st.success(
                            f"✓ Rapport généré ({res['bytes_written'] // 1024} KB, "
                            f"{res['leads_inclus']} leads, "
                            f"verdict pilote : "
                            f"{'GO' if res['verdict_go_phase2'] else 'NO-GO'})"
                        )
                rapport_path = session_dir / "rapport.html"
                if rapport_path.exists():
                    st.download_button(
                        "⬇ Télécharger le rapport HTML",
                        rapport_path.read_bytes(),
                        file_name=f"rapport_{session_dir.name}.html",
                        mime="text/html",
                        key=f"rep_dl_{session_dir.name}",
                    )

        if csv_l4.exists():
            st.success("CSV L4 trouvé")
            leads_l4 = lire_stage4_csv(csv_l4)
            df = pd.DataFrame([lead.model_dump() for lead in leads_l4])
            cols_prio = [
                "nom", "ville", "score_interet", "top_lead",
                "raison_score", "pitch_propose", "siren",
            ]
            cols_show = [c for c in cols_prio if c in df.columns] + [
                c for c in df.columns if c not in cols_prio
            ]
            st.dataframe(df[cols_show], use_container_width=True, height=500)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.download_button(
                    "📤 CSV L4 complet",
                    csv_l4.read_bytes(),
                    file_name=csv_l4.name,
                    mime="text/csv",
                )
            with col_b:
                # Export CRM-friendly (toutes les leads)
                export_path = session_dir / "leads_exportables.csv"
                export_csv_crm(leads_l4, export_path)
                st.download_button(
                    "📦 CSV exportable (CRM)",
                    export_path.read_bytes(),
                    file_name=export_path.name,
                    mime="text/csv",
                    help="Colonnes utiles pour démarchage : nom, dirigeant, "
                    "email vérifié, téléphone direct, LinkedIn, score, pitch.",
                )
            with col_c:
                # Export top leads uniquement
                top_leads = [lead for lead in leads_l4 if lead.top_lead]
                if top_leads:
                    top_path = session_dir / "leads_exportables_top.csv"
                    export_csv_crm(top_leads, top_path)
                    st.download_button(
                        f"⭐ Top leads ({len(top_leads)})",
                        top_path.read_bytes(),
                        file_name=top_path.name,
                        mime="text/csv",
                    )
                else:
                    st.caption("Aucun top lead (score ≥ seuil) dans cette session.")

        elif csv_l3.exists():
            from renoboost_leads.agent.tools.enrich import (
                enrich_l3_5_on_session,
                score_l4_on_session,
            )

            st.info("CSV L3 trouvé. L4 non encore exécuté pour cette session.")

            # ── L3.5 : enrichissement Dropcontact (optionnel, avant L4) ──
            col_l35a, col_l35b = st.columns([1, 1])
            with col_l35a:
                if csv_l35.exists():
                    st.success("💎 L3.5 déjà exécuté pour cette session.")
                else:
                    has_dc = settings.has_dropcontact()
                    dry = st.checkbox(
                        "Mode dry-run (simulation)",
                        value=not has_dc,
                        key=f"l35_dry_{session_dir.name}",
                        help="Si la clé Dropcontact n'est pas configurée, "
                        "le dry-run permet de tester sans coût.",
                    )
                    if st.button(
                        "💎 Enrichir L3.5 (Dropcontact)",
                        key=f"l35_btn_{session_dir.name}",
                        disabled=not (has_dc or dry),
                        help="Email vérifié + tél direct + LinkedIn. "
                        "Coût ~0.10€/lead éligible.",
                    ):
                        with st.spinner("Enrichissement Dropcontact…"):
                            res = enrich_l3_5_on_session(
                                session_dir.name, dry_run=dry
                            )
                        if not res.get("ok"):
                            st.error(
                                res.get("error")
                                or f"Échec L3.5 (code {res.get('returncode')})"
                            )
                            if res.get("stderr_tail"):
                                st.code(res["stderr_tail"], language=None)
                        else:
                            s = res.get("stats", {})
                            st.success(
                                f"✓ L3.5 terminé — {s.get('total', '?')} leads, "
                                f"{s.get('pct_email_dropcontact', 0)}% email, "
                                f"{s.get('pct_tel_direct', 0)}% tél direct."
                            )
                            st.rerun()

            # ── L4 : scoring Claude ──
            with col_l35b:
                dry_l4 = st.checkbox(
                    "Mode dry-run (simulation)",
                    value=not cle_anthropic,
                    key=f"l4_dry_{session_dir.name}",
                )
                if st.button(
                    "🚀 Lancer L4 sur cette session",
                    key=f"l4_btn_{session_dir.name}",
                    disabled=not (cle_anthropic or dry_l4),
                ):
                    with st.spinner("Scoring L4…"):
                        res = score_l4_on_session(session_dir.name, dry_run=dry_l4)
                    if not res.get("ok"):
                        st.error(
                            res.get("error")
                            or f"Échec L4 (code {res.get('returncode')})"
                        )
                        if res.get("stderr_tail"):
                            st.code(res["stderr_tail"], language=None)
                    else:
                        s = res.get("stats", {})
                        st.success(
                            f"✓ L4 terminé — {s.get('top_leads', 0)} top leads, "
                            f"score moyen {s.get('score_moyen', 0)}."
                        )
                        st.rerun()
        else:
            st.warning("Aucun CSV L3 ou L4 dans cette session.")


# ───────────────────────────────────────────────────────────────────
# ONGLET 4 : Stats agrégées cross-runs
# ───────────────────────────────────────────────────────────────────

with tab_stats:
    st.header("📈 Stats globales")
    runs_v = _runs_veille()
    sessions_c = _sessions_classiques()

    c1, c2, c3 = st.columns(3)
    c1.metric("Runs veille", len(runs_v))
    c2.metric("Sessions L1-L4", len(sessions_c))

    # Agrégation veille
    if runs_v:
        all_dfs = []
        for r in runs_v:
            try:
                df = _charger_csv(r / "veille_leads.csv")
                df["_run"] = r.name
                all_dfs.append(df)
            except Exception as e:  # noqa: BLE001
                st.warning(f"Impossible de lire {r.name} : {e}")
        if all_dfs:
            df_total = pd.concat(all_dfs, ignore_index=True)
            c3.metric("Total leads veille (cumul)", len(df_total))

            st.subheader("Distribution des scores (tous runs veille)")
            if "score_interet" in df_total.columns:
                scores = pd.to_numeric(df_total["score_interet"], errors="coerce").dropna()
                if not scores.empty:
                    bins = pd.cut(
                        scores, bins=[0, 30, 50, 70, 85, 100], include_lowest=True
                    ).value_counts().sort_index()
                    chart_df = pd.DataFrame({"score": bins.index.astype(str), "count": bins.values})
                    st.bar_chart(chart_df.set_index("score"))

            st.subheader("Volumes par run")
            counts_per_run = df_total.groupby("_run").size().reset_index(name="leads")
            st.dataframe(counts_per_run, use_container_width=True)

            if "marque_ve" in df_total.columns:
                st.subheader("Top 10 marques observées")
                top_marques = df_total["marque_ve"].value_counts().head(10)
                st.bar_chart(top_marques)
    else:
        st.info("Pas encore de run veille — les statistiques s'afficheront ici.")


# ───────────────────────────────────────────────────────────────────
# ONGLET 5 : Copilote (agent IA Phase A)
# ───────────────────────────────────────────────────────────────────

with tab_copilote:
    st.header("🤖 Copilote RénoBoost")
    st.caption(
        "Agent IA qui pilote la prospection : lance des runs, diagnostique "
        "la qualité, priorise les leads, alerte par email. Phase A — "
        "lecture seule sur les configs, pas de cold mailing (Phase B)."
    )

    from renoboost_leads.agent.budget import BudgetGuard
    from renoboost_leads.agent.config import load_agent_config
    from renoboost_leads.agent.journal import Journal

    agent_cfg = load_agent_config()
    guard = BudgetGuard(
        cap_eur_par_jour=agent_cfg.budget_eur_par_jour,
        path=agent_cfg.budget_path_abs(),
    )
    journal_agent = Journal(path=agent_cfg.journal_path_abs())

    c1, c2, c3 = st.columns(3)
    c1.metric("Budget cap", f"{guard.cap:.2f} €/jour")
    c2.metric("Consommé aujourd'hui", f"{guard.cumul_eur:.4f} €")
    c3.metric("Reste", f"{guard.reste_eur:.4f} €")

    api_key_dispo = _read_anthropic_key() is not None
    if not api_key_dispo:
        st.warning(
            "ANTHROPIC_API_KEY absente : configure-la dans `.env` (local) ou "
            "Streamlit secrets (cloud) pour activer l'agent."
        )

    instruction = st.text_area(
        "Instruction",
        placeholder=(
            "Ex : 'liste les sessions récentes', 'diagnostique la dernière "
            "session pilote', 'priorise les leads de la session 20260518-...'"
        ),
        height=80,
        key="copilote_instruction",
    )

    if st.button("🚀 Lancer un cycle", disabled=not api_key_dispo or not instruction.strip()):
        from renoboost_leads.agent.runner import run_cycle

        with st.spinner("L'agent travaille…"):
            try:
                if "ANTHROPIC_API_KEY" not in os.environ and api_key_dispo:
                    os.environ["ANTHROPIC_API_KEY"] = _read_anthropic_key() or ""
                result = run_cycle(instruction.strip())
            except Exception as e:  # noqa: BLE001
                st.error(f"{type(e).__name__} : {e}")
                result = None

        if result is not None:
            st.success("Cycle terminé.")
            if result.outils_appeles:
                noms = " → ".join(o["name"] for o in result.outils_appeles)
                st.caption(f"Outils : {noms}")
            st.markdown("**Réponse de l'agent**")
            st.markdown(result.texte_final or "_(rien)_")
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("Tours", result.tours)
            cc2.metric("Coût", f"{result.cout_eur:.4f} €")
            cc3.metric("Tokens in", result.tokens_input)
            cc4.metric("Tokens out", result.tokens_output)
            if result.erreur:
                st.warning(result.erreur)

    st.divider()
    with st.expander("📓 Journal récent (10 dernières entrées)"):
        entries = journal_agent.read_recent(n=10)
        if not entries:
            st.info("Journal vide — l'agent n'a pas encore tourné.")
        else:
            for e in reversed(entries):
                st.markdown(e)
                st.divider()

    st.divider()
    st.subheader("📨 Staging cold mail — validation manuelle")
    st.caption(
        "L'agent drafte les emails ici. Tu valides un par un, puis tu cliques "
        "**Envoyer les validés** pour les pousser dans Instantly. "
        "Tant que rien n'est validé, rien ne part."
    )

    from renoboost_leads.agent.tools.cold_mail import send_validated
    from renoboost_leads.instantly.client import InstantlyClient
    from renoboost_leads.instantly.staging import StagingStore

    cm_store = StagingStore()
    stagings_resume = cm_store.list()
    if not stagings_resume:
        st.info(
            "Aucun staging — demande à l'agent : "
            "`stage_cold_emails(session_id, secteur)`."
        )
    else:
        labels = [
            (
                f"{s['staging_id']}  • {s.get('secteur')}  "
                f"({s['etats']['en_attente']} att / "
                f"{s['etats']['valide']} val / "
                f"{s['etats']['envoye']} env)"
            )
            for s in stagings_resume
        ]
        choix_idx = st.selectbox(
            "Choisir un staging",
            range(len(labels)),
            format_func=lambda i: labels[i],
            key="cm_select",
        )
        sid = stagings_resume[choix_idx]["staging_id"]
        staging = cm_store.load(sid)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(staging.items))
        for col, etat in zip(
            (c2, c3, c4), ("en_attente", "valide", "envoye"), strict=True
        ):
            col.metric(
                etat,
                sum(1 for i in staging.items if i.etat == etat),
            )

        cli = InstantlyClient()
        if cli.is_dry_run():
            st.warning(
                "Instantly en **DRY-RUN** — la clé n'est pas configurée ou "
                "INSTANTLY_DRY_RUN=true. Les envois seront simulés."
            )

        if st.button(
            "📤 Envoyer les items validés vers Instantly",
            disabled=not any(i.etat == "valide" for i in staging.items),
        ):
            res = send_validated(sid)
            if "error" in res:
                st.error(res["error"])
            elif "warning" in res:
                st.warning(res["warning"])
            else:
                st.success(
                    f"{res['envoyes']} envoyé(s) — campagne {res['campaign_id']}"
                    + (" (dry-run)" if res.get("dry_run") else "")
                )
                st.rerun()

        st.divider()
        for item in staging.items:
            badge = {
                "en_attente": "🟡 en attente",
                "valide": "🟢 validé",
                "refuse": "🔴 refusé",
                "envoye": "🔵 envoyé",
            }.get(item.etat, item.etat)
            with st.expander(
                f"{badge} — {item.email_dest} ({item.nom_dest})",
                expanded=item.etat == "en_attente",
            ):
                st.markdown(f"**Sujet** : {item.sujet}")
                st.text(item.corps)
                if item.etat == "en_attente":
                    cc1, cc2 = st.columns(2)
                    if cc1.button("✅ Valider", key=f"v_{item.lead_id}"):
                        cm_store.set_etat(sid, item.lead_id, "valide")
                        st.rerun()
                    if cc2.button("❌ Refuser", key=f"r_{item.lead_id}"):
                        cm_store.set_etat(sid, item.lead_id, "refuse")
                        st.rerun()
                elif item.campagne_instantly_id:
                    st.caption(
                        f"Campagne Instantly : `{item.campagne_instantly_id}`"
                    )


st.caption(
    "📚 Doc : [README](./README.md) • [VEILLE.md](./VEILLE.md) • "
    "[OPERATIONS.md](./OPERATIONS.md) • [RGPD_COMPLIANCE.md](./RGPD_COMPLIANCE.md)"
)
