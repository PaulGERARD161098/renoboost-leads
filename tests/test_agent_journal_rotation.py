"""Tests rotation + troncature du journal."""

from __future__ import annotations

from pathlib import Path

from renoboost_leads.agent.journal import Journal, JournalEntry


def test_rotation_si_taille_depassee(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md", rotate_bytes=200)
    # On écrit ~5 entrées au-dessus du seuil
    for i in range(10):
        j.append(
            JournalEntry(
                cycle_id=f"c{i}",
                instruction="x" * 30,
                decision="y" * 30,
                resultat="z" * 30,
            )
        )
    # Le fichier actif doit être plus petit que le total écrit
    assert j.path.exists()
    archives = list(tmp_path.glob("j-archive-*.md"))
    assert len(archives) >= 1


def test_pas_de_rotation_si_sous_seuil(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md", rotate_bytes=10_000)
    for i in range(3):
        j.append(JournalEntry(cycle_id=f"c{i}", instruction="i", decision="d"))
    archives = list(tmp_path.glob("j-archive-*.md"))
    assert archives == []
    assert j.path.stat().st_size > 0


def test_archive_meme_mois_appendée(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md", rotate_bytes=100)
    for i in range(5):
        j.append(
            JournalEntry(cycle_id=f"a{i}", instruction="x" * 50, decision="y" * 50)
        )
    # On retombe au-dessus du seuil → 2e rotation devrait apender à l'archive
    archives_avant = list(tmp_path.glob("j-archive-*.md"))
    taille_avant = archives_avant[0].stat().st_size if archives_avant else 0
    for i in range(5):
        j.append(
            JournalEntry(cycle_id=f"b{i}", instruction="x" * 50, decision="y" * 50)
        )
    archives_apres = list(tmp_path.glob("j-archive-*.md"))
    assert len(archives_apres) == 1  # Toujours 1 fichier ce mois
    assert archives_apres[0].stat().st_size > taille_avant


def test_context_tronque_si_trop_gros(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md", context_max_bytes=300)
    for i in range(10):
        j.append(
            JournalEntry(
                cycle_id=f"c{i}", instruction="i" * 50, decision="d" * 50
            )
        )
    ctx = j.context_pour_agent(n=10)
    # La taille ne dépasse pas trop le plafond (on garde au moins la dernière)
    assert len(ctx.encode("utf-8")) <= 600  # marge pour le séparateur
    # La dernière entrée est présente
    assert "c9" in ctx
    # La plus vieille a été tronquée
    assert "c0" not in ctx


def test_context_garde_toujours_la_derniere(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md", context_max_bytes=10)
    j.append(
        JournalEntry(cycle_id="seule", instruction="i" * 200, decision="d" * 200)
    )
    ctx = j.context_pour_agent()
    # Même si l'entrée dépasse le plafond, on la garde
    assert "seule" in ctx


def test_context_pas_de_troncature_si_sous_plafond(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md", context_max_bytes=10_000)
    for i in range(3):
        j.append(JournalEntry(cycle_id=f"c{i}", instruction="i", decision="d"))
    ctx = j.context_pour_agent(n=10)
    for i in range(3):
        assert f"c{i}" in ctx
