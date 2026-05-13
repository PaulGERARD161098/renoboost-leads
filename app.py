"""Interface Streamlit — visualisation des leads + lancement L4 (scoring Claude).

Lancement :
    pip install -e ".[ui]"
    streamlit run app.py

L'app sert deux usages :
1. **Visualiser** un CSV L3 ou L4 existant produit par la CLI.
2. **Lancer L4** (scoring Claude) sur un CSV L3 chargé, depuis l'UI.

La clé Anthropic est lue dans cet ordre :
1. `st.secrets["ANTHROPIC_API_KEY"]` (déploiement Streamlit Cloud)
2. Variable d'env / fichier `.env` (via `Settings`)
3. Saisie utilisateur dans la sidebar (non persistée)
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from renoboost_leads.common.budget_guard import BudgetGuard
from renoboost_leads.common.rate_limiter import RateLimiter
from renoboost_leads.exporter import (
    COLONNES_STAGE4,
    export_stage4_csv,
    lire_stage3_csv,
    lire_stage4_csv,
)
from renoboost_leads.models import ClaudeScoring
from renoboost_leads.settings import PROJECT_ROOT, get_settings
from renoboost_leads.stage4_prospection.cache import CacheStage4
from renoboost_leads.stage4_prospection.client import ClaudeClient, ClaudeClientConfig
from renoboost_leads.stage4_prospection.enricher import EnricheurStage4
from renoboost_leads.stage4_prospection.prompt_template import CONTEXTE_CLIENT_DEFAUT

# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────


def _read_anthropic_key() -> str | None:
    """Résout la clé Anthropic depuis st.secrets puis .env."""
    # 1. st.secrets (Streamlit Cloud / .streamlit/secrets.toml)
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            val = st.secrets["ANTHROPIC_API_KEY"]
            if val:
                return str(val)
    except Exception:  # noqa: BLE001, S110 — secrets non disponible en local
        return os.environ.get("ANTHROPIC_API_KEY") or None  # fallback immédiat

    # 2. Settings (.env via pydantic-settings)
    try:
        settings = get_settings()
        if settings.has_anthropic():
            return settings.anthropic_api_key.get_secret_value()
    except Exception:  # noqa: BLE001, S110 — .env absent / mal formé
        return os.environ.get("ANTHROPIC_API_KEY") or None

    # 3. Variable d'env directe (fallback)
    return os.environ.get("ANTHROPIC_API_KEY") or None


def _sessions_disponibles() -> list[Path]:
    """Liste les dossiers de session dans data/output/."""
    base = PROJECT_ROOT / "data" / "output"
    if not base.exists():
        return []
    return sorted(
        (d for d in base.iterdir() if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )


def _format_dataframe_l4(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    cols_prio = [
        "nom",
        "ville",
        "code_postal",
        "score_interet",
        "top_lead",
        "raison_score",
        "pitch_propose",
        "scoring_modele",
        "scoring_erreur",
        "site_web",
        "dirigeant_prenom",
        "dirigeant_nom",
        "siren",
    ]
    autres = [c for c in df.columns if c not in cols_prio]
    return df[[c for c in cols_prio if c in df.columns] + autres]


# ───────────────────────────────────────────────────────────────
# UI
# ───────────────────────────────────────────────────────────────


st.set_page_config(page_title="RénoBoost Leads", layout="wide")
st.title("RénoBoost Leads — Visualisation + Scoring L4")

st.caption(
    "Charge un CSV L3 ou L4 produit par la CLI. "
    "Si tu veux lancer L4 (scoring Claude), coche **Activer L4** ci-dessous."
)

# ─── Sidebar ───
with st.sidebar:
    st.header("Sessions disponibles")
    sessions = _sessions_disponibles()
    if not sessions:
        st.warning("Aucune session dans data/output/. Lance d'abord la CLI.")
        session_choisi: Path | None = None
    else:
        labels = [s.name for s in sessions]
        choix = st.selectbox("Session", labels, index=0)
        session_choisi = sessions[labels.index(choix)]

    st.divider()
    st.header("Clé Anthropic (L4)")
    cle_detectee = _read_anthropic_key()
    if cle_detectee:
        st.success("Clé détectée (st.secrets ou .env).")
    else:
        st.info("Aucune clé détectée. Saisis-la ici pour activer L4 :")
        saisie = st.text_input(
            "ANTHROPIC_API_KEY",
            type="password",
            help="Non persistée — uniquement utilisée pour cette session.",
        )
        if saisie:
            cle_detectee = saisie

# ─── Body ───
if session_choisi is None:
    st.stop()

csv_l4 = session_choisi / "etage4_prospection.csv"
csv_l3 = session_choisi / "etage3_contacts.csv"

if csv_l4.exists():
    st.success(f"CSV L4 trouvé : `{csv_l4.name}`")
    leads_l4 = lire_stage4_csv(csv_l4)
    df = _format_dataframe_l4([lead.model_dump() for lead in leads_l4])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total leads", len(leads_l4))
    col2.metric("Top leads", sum(1 for x in leads_l4 if x.top_lead))
    scores = [x.score_interet for x in leads_l4 if x.score_interet is not None]
    col3.metric("Score moyen", f"{sum(scores) / len(scores):.0f}" if scores else "—")
    col4.metric("Erreurs scoring", sum(1 for x in leads_l4 if x.scoring_erreur))

    st.dataframe(df, use_container_width=True, height=600)
    st.download_button(
        "Télécharger CSV L4",
        csv_l4.read_bytes(),
        file_name=csv_l4.name,
        mime="text/csv",
    )

elif csv_l3.exists():
    st.info(f"CSV L3 trouvé : `{csv_l3.name}`. L4 non encore exécuté.")
    leads_l3 = lire_stage3_csv(csv_l3)
    st.write(f"**{len(leads_l3)} leads L3 prêts à scorer.**")

    activer_l4 = st.checkbox("Activer L4 (scoring Claude)", value=False)

    if activer_l4:
        if cle_detectee is None:
            st.error(
                "ANTHROPIC_API_KEY manquante. Saisis-la dans la sidebar ou "
                "ajoute-la à `.env` / `st.secrets`."
            )
        else:
            with st.expander("⚙ Paramètres scoring", expanded=True):
                modele = st.selectbox(
                    "Modèle",
                    ["claude-haiku-4-5", "claude-sonnet-4-6"],
                    index=0,
                    help="Haiku ~0.005 €/lead, Sonnet ~0.02 €/lead",
                )
                seuil = st.slider(
                    "Seuil top_lead", min_value=0, max_value=100, value=70, step=5
                )
                inclure_pitch = st.checkbox("Inclure pitch personnalisé", value=True)
                contexte_default = st.checkbox(
                    "Utiliser le contexte RénoBoost par défaut", value=True
                )
                if contexte_default:
                    contexte_client = None
                    with st.expander("Voir le contexte par défaut"):
                        st.code(CONTEXTE_CLIENT_DEFAUT)
                else:
                    contexte_client = st.text_area(
                        "Contexte commercial",
                        value=CONTEXTE_CLIENT_DEFAUT,
                        height=200,
                    )

                budget_eur = st.number_input(
                    "Plafond budget € pour ce run L4",
                    min_value=0.10,
                    max_value=100.0,
                    value=5.0,
                    step=0.5,
                )

            cout_estime = len(leads_l3) * (
                0.005 if modele == "claude-haiku-4-5" else 0.02
            )
            st.caption(
                f"💰 Coût indicatif : ~{cout_estime:.2f} € pour {len(leads_l3)} leads "
                f"(plafond : {budget_eur:.2f} €)."
            )

            if st.button("🚀 Lancer le scoring L4", type="primary"):
                config = ClaudeScoring(
                    modele=modele,
                    seuil_top_lead=seuil,
                    inclure_pitch=inclure_pitch,
                    contexte_client=contexte_client,
                )
                client = ClaudeClient(
                    ClaudeClientConfig(
                        api_key=cle_detectee,
                        modele=modele,
                        max_tokens_sortie=config.max_tokens_sortie,
                        rate_limiter=RateLimiter(60),
                        budget=BudgetGuard(plafond_eur=float(budget_eur)),
                    )
                )
                cache = CacheStage4(session_choisi / "cache_l4.sqlite")

                progress = st.progress(0, text="Scoring en cours...")
                status = st.empty()

                # On enrichit en streaming en pilotant manuellement (au lieu d'enrichir())
                # pour pouvoir mettre à jour la barre de progression.
                enricher = EnricheurStage4(client=client, config=config, cache=cache)
                leads_l4: list = []
                for i, lead in enumerate(leads_l3, start=1):
                    try:
                        leads_l4.append(enricher._enrichir_un_lead(lead))
                    except Exception as e:  # noqa: BLE001
                        status.error(f"Erreur sur {lead.nom} : {e}")
                        break
                    progress.progress(
                        i / len(leads_l3),
                        text=f"{i}/{len(leads_l3)} — coût {enricher.cout_total_eur:.4f} €",
                    )

                progress.empty()
                if leads_l4:
                    csv_path = session_choisi / "etage4_prospection.csv"
                    export_stage4_csv(leads_l4, csv_path)
                    st.success(
                        f"✓ L4 terminé. {len(leads_l4)} leads → `{csv_path.name}` "
                        f"(coût {enricher.cout_total_eur:.4f} €, "
                        f"{enricher.cache_hits} cache hits)."
                    )
                    st.balloons()
                    st.rerun()

    st.divider()
    st.subheader("Aperçu L3 (avant scoring)")
    rows = [lead.model_dump() for lead in leads_l3]
    df_l3 = pd.DataFrame(rows)
    st.dataframe(df_l3, use_container_width=True, height=400)

else:
    st.warning(
        f"Aucun CSV L3 ni L4 dans `{session_choisi.name}/`. "
        "Lance d'abord la CLI : `python -m renoboost_leads.cli run --stages 1,2,3 ...`"
    )

st.caption(f"Colonnes L4 attendues : `{', '.join(COLONNES_STAGE4[-6:])}`")
