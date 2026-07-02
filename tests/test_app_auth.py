"""[S3a] Test de fermeture : `_require_auth` est fail-closed.

app.py est un script Streamlit (code exécuté à l'import : set_page_config,
_require_auth(), rendu…), donc non importable tel quel en test. On extrait la
fonction `_require_auth` par AST et on l'exécute en isolation avec un faux
module `st` et un `os.environ` contrôlé — on teste ainsi la source réelle sans
lancer l'application entière.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class _StopError(Exception):
    """Sentinelle levée par le faux st.stop()."""


class _FakeSt:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.session_state: dict = {}

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def stop(self) -> None:
        raise _StopError()

    # Suffisant pour les chemins testés (rien à rendre).
    def markdown(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        pass


def _charger_require_auth(fake_st: _FakeSt, environ: dict, expected):  # noqa: ANN001
    """Compile et exécute uniquement la fonction _require_auth de app.py."""
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_require_auth"
    )
    module = ast.Module(body=[func], type_ignores=[])
    ns: dict = {
        "st": fake_st,
        "os": type("_os", (), {"environ": environ})(),
        "_read_app_password": lambda: expected,
    }
    exec(compile(module, str(APP_PATH), "exec"), ns)  # noqa: S102
    return ns["_require_auth"]


def test_sans_password_et_sans_echappatoire_refuse():
    st = _FakeSt()
    require_auth = _charger_require_auth(st, environ={}, expected=None)
    with pytest.raises(_StopError):
        require_auth()
    assert any("APP_PASSWORD" in e for e in st.errors)


def test_sans_password_avec_echappatoire_dev_ouvre():
    st = _FakeSt()
    require_auth = _charger_require_auth(
        st, environ={"APP_ALLOW_OPEN": "1"}, expected=None
    )
    # Ne doit ni lever ni afficher d'erreur.
    assert require_auth() is None
    assert st.errors == []


def test_avec_password_deja_authentifie_passe():
    st = _FakeSt()
    st.session_state["authenticated"] = True
    require_auth = _charger_require_auth(st, environ={}, expected="secret")
    assert require_auth() is None
    assert st.errors == []
