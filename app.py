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
from renoboost_leads.common.budget_guard import BudgetGuard  # noqa: E402
from renoboost_leads.common.rate_limiter import RateLimiter  # noqa: E402
from renoboost_leads.exporter import (  # noqa: E402
    export_csv_crm,
    export_stage4_csv,
    lire_stage3_csv,
    lire_stage4_csv,
)
from renoboost_leads.models import ClaudeScoring  # noqa: E402
from renoboost_leads.settings import PROJECT_ROOT, get_settings  # noqa: E402
from renoboost_leads.stage4_prospection.cache import CacheStage4  # noqa: E402
from renoboost_leads.stage4_prospection.client import (  # noqa: E402
    ClaudeClient,
    ClaudeClientConfig,
)
from renoboost_leads.stage4_prospection.enricher import EnricheurStage4  # noqa: E402
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
    st.write("📧 **SMTP veille** :", "✓ configuré" if settings.has_smtp() else "✗ absent")

    st.divider()
    py = f"{os.sys.version_info.major}.{os.sys.version_info.minor}"
    st.caption(f"Version : 0.5.0  •  Python {py}")
    st.caption(f"Projet : `{PROJECT_ROOT.name}`")


# ═══════════════════════════════════════════════════════════════════
# Onglets
# ═══════════════════════════════════════════════════════════════════

tab_veille, tab_nouveau, tab_sessions, tab_stats = st.tabs(
    ["📊 Veille du jour", "📥 Nouveau run", "📁 Sessions", "📈 Stats"]
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
        csv_l3 = session_dir / "etage3_contacts.csv"

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
            st.info("CSV L3 trouvé. L4 non encore exécuté pour cette session.")
            if cle_anthropic and st.button("🚀 Lancer L4 sur cette session"):
                with st.spinner("Scoring L4…"):
                    leads_l3 = lire_stage3_csv(csv_l3)
                    client = ClaudeClient(
                        ClaudeClientConfig(
                            api_key=cle_anthropic,
                            modele="claude-haiku-4-5",
                            rate_limiter=RateLimiter(60),
                            budget=BudgetGuard(plafond_eur=5.0),
                        )
                    )
                    cache = CacheStage4(session_dir / "cache_l4.sqlite")
                    enricher = EnricheurStage4(
                        client=client, config=ClaudeScoring(), cache=cache
                    )
                    leads_l4 = enricher.enrichir(leads_l3)
                    export_stage4_csv(leads_l4, csv_l4)
                st.success(f"✓ L4 terminé. Coût {enricher.cout_total_eur:.4f} €")
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


st.caption(
    "📚 Doc : [README](./README.md) • [VEILLE.md](./VEILLE.md) • "
    "[OPERATIONS.md](./OPERATIONS.md) • [RGPD_COMPLIANCE.md](./RGPD_COMPLIANCE.md)"
)
