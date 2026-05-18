"""Tests du journal markdown de l'agent."""

from __future__ import annotations

from pathlib import Path

from renoboost_leads.agent.journal import Journal, JournalEntry


def test_journal_append_cree_fichier(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "journal.md")
    j.append(JournalEntry(cycle_id="abc", instruction="lance pilote", decision="run_pipeline()"))
    contenu = (tmp_path / "journal.md").read_text(encoding="utf-8")
    assert "cycle_id=abc" in contenu
    assert "lance pilote" in contenu
    assert "run_pipeline()" in contenu


def test_journal_append_plusieurs_entries(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "journal.md")
    j.append(JournalEntry(cycle_id="a", instruction="i1", decision="d1"))
    j.append(JournalEntry(cycle_id="b", instruction="i2", decision="d2"))
    blocs = j.read_recent(n=10)
    assert len(blocs) == 2
    assert "cycle_id=a" in blocs[0]
    assert "cycle_id=b" in blocs[1]


def test_journal_read_recent_limite(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "journal.md")
    for i in range(5):
        j.append(JournalEntry(cycle_id=f"c{i}", instruction=f"i{i}", decision=f"d{i}"))
    recents = j.read_recent(n=2)
    assert len(recents) == 2
    assert "cycle_id=c3" in recents[0]
    assert "cycle_id=c4" in recents[1]


def test_journal_context_vide(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "vide.md")
    # fichier créé par __init__ mais vide
    j.path.write_text("", encoding="utf-8")
    ctx = j.context_pour_agent()
    assert "vide" in ctx.lower()


def test_journal_entry_to_markdown_complet() -> None:
    e = JournalEntry(
        cycle_id="x1",
        instruction="lance pilote 59",
        decision="run_pipeline(config=pilote_phase1.yaml, stages=1,2,3)",
        resultat="session=20260518-0900, 28 leads L3",
        suite="diagnose_quality",
    )
    md = e.to_markdown()
    assert md.startswith("## ")
    assert "**Instruction**" in md
    assert "**Décision**" in md
    assert "**Résultat**" in md
    assert "**Suite**" in md


def test_journal_entry_to_markdown_minimal() -> None:
    e = JournalEntry(cycle_id="x", instruction="i", decision="d")
    md = e.to_markdown()
    assert "**Résultat**" not in md
    assert "**Suite**" not in md
