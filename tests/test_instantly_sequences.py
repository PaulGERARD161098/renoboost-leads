"""Tests du loader de séquences cold mail."""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.instantly import sequences as seq

TEMPLATE_3_STEPS = """---
secteur: test
nom_lisible: "Cabinet de test"
sujet_step_1: "Hello {{prenom}}"
delai_step_2_jours: 4
sujet_step_2: "Re : {{prenom}}"
delai_step_3_jours: 7
sujet_step_3: "Last call"
---

# Step 1 — Premier contact

Bonjour {{civilite}} {{nom_dirigeant}},
Votre cabinet {{nom_entreprise}} gagnerait à...

Paul

---

# Step 2 — Relance

Bonjour,
Relance.

---

# Step 3 — Last

Dernier message.
"""


def _ecrire(tmp_path: Path, nom: str, contenu: str) -> Path:
    d = tmp_path / "templates"
    d.mkdir()
    p = d / f"{nom}.md"
    p.write_text(contenu, encoding="utf-8")
    return d


def test_load_sequence_complete(tmp_path: Path) -> None:
    d = _ecrire(tmp_path, "test", TEMPLATE_3_STEPS)
    s = seq.load_sequence("test", dir_path=d)
    assert s.secteur == "test"
    assert s.nom_lisible == "Cabinet de test"
    assert len(s.steps) == 3
    assert s.steps[0].numero == 1
    assert s.steps[0].sujet == "Hello {{prenom}}"
    assert s.steps[0].delai_jours == 0
    assert s.steps[1].delai_jours == 4
    assert s.steps[2].delai_jours == 7


def test_render_substitution_variables(tmp_path: Path) -> None:
    d = _ecrire(tmp_path, "test", TEMPLATE_3_STEPS)
    s = seq.load_sequence("test", dir_path=d)
    rendu = s.render_step(
        1,
        {
            "prenom": "Marie",
            "civilite": "Mme",
            "nom_dirigeant": "Dupont",
            "nom_entreprise": "ABC SARL",
        },
    )
    assert rendu.sujet == "Hello Marie"
    assert "Mme Dupont" in rendu.corps
    assert "ABC SARL" in rendu.corps


def test_render_variables_manquantes_stripees(tmp_path: Path) -> None:
    d = _ecrire(tmp_path, "test", TEMPLATE_3_STEPS)
    s = seq.load_sequence("test", dir_path=d)
    rendu = s.render_step(1, {"prenom": "Marie"})
    # Les autres variables sont supprimées (pas spammées au destinataire)
    assert "{{civilite}}" not in rendu.corps
    assert "{{nom_dirigeant}}" not in rendu.corps
    assert "Marie" not in rendu.corps  # parce que prenom n'est pas dans le corps


def test_step_inexistant_leve(tmp_path: Path) -> None:
    d = _ecrire(tmp_path, "test", TEMPLATE_3_STEPS)
    s = seq.load_sequence("test", dir_path=d)
    with pytest.raises(ValueError):
        s.render_step(99, {})


def test_load_fichier_absent(tmp_path: Path) -> None:
    d = tmp_path / "templates"
    d.mkdir()
    with pytest.raises(FileNotFoundError):
        seq.load_sequence("inexistant", dir_path=d)


def test_load_sans_front_matter(tmp_path: Path) -> None:
    d = _ecrire(tmp_path, "x", "# Step 1\nCorps")
    with pytest.raises(ValueError, match="front-matter"):
        seq.load_sequence("x", dir_path=d)


def test_list_secteurs(tmp_path: Path) -> None:
    d = _ecrire(tmp_path, "compta", TEMPLATE_3_STEPS)
    (d / "avocats.md").write_text(TEMPLATE_3_STEPS, encoding="utf-8")
    assert seq.list_secteurs(dir_path=d) == ["avocats", "compta"]


def test_list_secteurs_dossier_absent(tmp_path: Path) -> None:
    assert seq.list_secteurs(dir_path=tmp_path / "rien") == []


# ─── Validation des templates livrés ───────────────────────────────


@pytest.mark.parametrize("secteur", ["compta", "avocats", "immo", "com", "be"])
def test_templates_livres_parsent(secteur: str) -> None:
    """Tous les 5 templates par défaut doivent parser proprement."""
    s = seq.load_sequence(secteur)
    assert s.secteur == secteur
    assert len(s.steps) == 3
    assert all(st.sujet for st in s.steps)
    assert all(st.corps for st in s.steps)
    # Le step 1 a delai_jours=0 forcé
    assert s.steps[0].delai_jours == 0
    # Steps suivants ont un délai > 0
    assert s.steps[1].delai_jours > 0
    assert s.steps[2].delai_jours > s.steps[1].delai_jours
