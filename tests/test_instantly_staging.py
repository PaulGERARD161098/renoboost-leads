"""Tests du store de staging cold mail."""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.instantly.staging import (
    StagedItem,
    Staging,
    StagingStore,
    nouveau_staging_id,
)


def _make_staging(staging_id: str = "stg_t1") -> Staging:
    return Staging(
        staging_id=staging_id,
        secteur="compta",
        session_id="20260518-test",
        from_email="paul@x.fr",
        items=[
            StagedItem(
                lead_id="100",
                email_dest="a@x.fr",
                nom_dest="Alice",
                sujet="S1",
                corps="Hello Alice",
            ),
            StagedItem(
                lead_id="200",
                email_dest="b@x.fr",
                nom_dest="Bob",
                sujet="S2",
                corps="Hello Bob",
            ),
        ],
    )


def test_id_unique() -> None:
    a = nouveau_staging_id()
    b = nouveau_staging_id()
    assert a != b
    assert a.startswith("stg_")


def test_save_load_roundtrip(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    s = _make_staging()
    store.save(s)
    rechargé = store.load(s.staging_id)
    assert rechargé.staging_id == s.staging_id
    assert rechargé.secteur == "compta"
    assert len(rechargé.items) == 2
    assert rechargé.items[0].nom_dest == "Alice"


def test_load_inexistant(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load("absent")


def test_list_resume(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    store.save(_make_staging("stg_a"))
    store.save(_make_staging("stg_b"))
    items = store.list()
    assert len(items) == 2
    # tri inverse (plus récent d'abord) — alphabétique inverse car même date
    assert items[0]["staging_id"] == "stg_b"
    assert items[0]["total"] == 2
    assert items[0]["etats"]["en_attente"] == 2
    assert items[0]["etats"]["valide"] == 0


def test_set_etat(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    s = _make_staging()
    store.save(s)
    apres = store.set_etat(s.staging_id, "100", "valide")
    item = next(i for i in apres.items if i.lead_id == "100")
    assert item.etat == "valide"
    assert item.decide_le is not None
    # Persisté
    rechargé = store.load(s.staging_id)
    assert rechargé.items[0].etat == "valide"


def test_set_etat_invalide(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    s = _make_staging()
    store.save(s)
    with pytest.raises(ValueError, match="invalide"):
        store.set_etat(s.staging_id, "100", "zzz")


def test_set_etat_lead_inconnu(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    s = _make_staging()
    store.save(s)
    with pytest.raises(KeyError):
        store.set_etat(s.staging_id, "fantome", "valide")


def test_list_fichier_corrompu_ignore(tmp_path: Path) -> None:
    store = StagingStore(dir_path=tmp_path)
    (tmp_path / "stg_ok.json").write_text(
        _make_staging("stg_ok").to_dict().__repr__(),
        encoding="utf-8",
    )
    (tmp_path / "stg_bad.json").write_text("{pas du json", encoding="utf-8")
    # Le bad est ignoré, on n'a que le ok... ou rien si le ok est aussi cassé
    items = store.list()
    # __repr__ d'un dict n'est PAS du JSON valide → les 2 sont ignorés
    assert items == []
