"""Tests des helpers de formatage du rapport client (_formatters.py)."""

from __future__ import annotations

from renoboost_leads.agent.tools._formatters import (
    LIBELLES_TRANCHE_EFFECTIF,
    decode_effectif,
    format_dirigeant,
    format_naf,
    nettoyer_nom_espaces,
)

# ── decode_effectif ────────────────────────────────────────────────


def test_decode_effectif_libelle_prioritaire() -> None:
    """Si l'API a fourni un libellé, il prime sur le décodage du code."""
    assert decode_effectif("12", "20 à 49 salariés") == "20 à 49 salariés"


def test_decode_effectif_depuis_code_seul() -> None:
    assert decode_effectif("01") == "1 ou 2 salariés"
    assert decode_effectif("11") == "10 à 19 salariés"
    assert decode_effectif("12") == "20 à 49 salariés"
    assert decode_effectif("53") == "10 000 salariés et plus"


def test_decode_effectif_code_inconnu_renvoie_code_brut() -> None:
    """Sécurité : si l'INSEE ajoute un code, on ne masque pas la donnée."""
    assert decode_effectif("99") == "99"


def test_decode_effectif_vide_renvoie_tiret() -> None:
    assert decode_effectif(None) == "—"
    assert decode_effectif("") == "—"
    assert decode_effectif("   ") == "—"


def test_decode_effectif_libelle_vide_fallback_code() -> None:
    """Libellé vide = absent → on tente le décodage du code."""
    assert decode_effectif("12", "") == "20 à 49 salariés"
    assert decode_effectif("12", "   ") == "20 à 49 salariés"


def test_libelles_tranche_couvre_les_codes_courants() -> None:
    for code in ("00", "01", "02", "03", "11", "12", "21", "22", "31"):
        assert code in LIBELLES_TRANCHE_EFFECTIF


# ── format_naf ─────────────────────────────────────────────────────


def test_format_naf_code_et_libelle() -> None:
    assert (
        format_naf("47.91B", "Vente à distance sur catalogue spécialisé")
        == "47.91B — Vente à distance sur catalogue spécialisé"
    )


def test_format_naf_code_seul() -> None:
    assert format_naf("47.91B", None) == "47.91B"
    assert format_naf("47.91B", "") == "47.91B"


def test_format_naf_libelle_seul() -> None:
    assert format_naf(None, "Activité X") == "Activité X"


def test_format_naf_vide() -> None:
    assert format_naf(None, None) == "—"
    assert format_naf("", "") == "—"


# ── nettoyer_nom_espaces ───────────────────────────────────────────


def test_nettoyer_nom_recolle_lettres_isolees() -> None:
    assert nettoyer_nom_espaces("S H C I") == "SHCI"
    assert nettoyer_nom_espaces("A S D I") == "ASDI"


def test_nettoyer_nom_garde_le_reste() -> None:
    assert nettoyer_nom_espaces("A S D I LOGISTIQUE") == "ASDI LOGISTIQUE"


def test_nettoyer_nom_ignore_token_normal() -> None:
    assert nettoyer_nom_espaces("EDF FRANCE") == "EDF FRANCE"
    assert nettoyer_nom_espaces("CARREFOUR") == "CARREFOUR"
    assert nettoyer_nom_espaces("Société X & Y") == "Société X & Y"


def test_nettoyer_nom_deux_lettres_non_recollees() -> None:
    """2 tokens seuls ne suffisent pas — risque de faux positif."""
    assert nettoyer_nom_espaces("U S") == "U S"


def test_nettoyer_nom_vide() -> None:
    assert nettoyer_nom_espaces(None) == ""
    assert nettoyer_nom_espaces("") == ""


def test_nettoyer_nom_avec_accents() -> None:
    """Lettres accentuées majuscules acceptées dans la séquence."""
    assert nettoyer_nom_espaces("É D F BTP") == "ÉDF BTP"


# ── format_dirigeant ───────────────────────────────────────────────


def test_format_dirigeant_complet() -> None:
    assert (
        format_dirigeant("MARTIN", "Pierre", "Président")
        == "Pierre MARTIN (Président)"
    )


def test_format_dirigeant_prenom_majuscules_titlecase() -> None:
    """Prénom tout-majuscule passe en title-case ("GAMBATESA" -> "Gambatesa")."""
    assert (
        format_dirigeant("MERCALDI", "GAMBATESA") == "Gambatesa MERCALDI"
    )


def test_format_dirigeant_prenom_compose() -> None:
    assert format_dirigeant("DUPONT", "JEAN-PIERRE") == "Jean-Pierre DUPONT"


def test_format_dirigeant_nom_egal_prenom_doublon() -> None:
    """JAZ + JAZ -> juste 'JAZ', pas 'JAZ JAZ'."""
    assert format_dirigeant("JAZ", "JAZ") == "JAZ"
    assert format_dirigeant("JAZ", "JAZ", "Gérant") == "JAZ (Gérant)"


def test_format_dirigeant_nom_seul() -> None:
    assert format_dirigeant("MARTIN") == "MARTIN"
    assert format_dirigeant("MARTIN", None, "Gérant") == "MARTIN (Gérant)"


def test_format_dirigeant_nom_vide() -> None:
    assert format_dirigeant(None) == "—"
    assert format_dirigeant("") == "—"
    assert format_dirigeant("   ") == "—"


def test_format_dirigeant_qualite_capitalisee() -> None:
    """GÉRANT → Gérant (on évite les majuscules criardes dans le rapport)."""
    assert format_dirigeant("MARTIN", "Pierre", "GÉRANT") == "Pierre MARTIN (Gérant)"
