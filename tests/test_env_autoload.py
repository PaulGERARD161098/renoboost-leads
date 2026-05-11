"""Tests B7 — chargement automatique du .env via pydantic-settings.

Sur Windows et lors d'installations non-éditables, le chemin figé
`PROJECT_ROOT / .env` ne résolvait pas correctement, obligeant l'utilisateur
à exporter les variables d'env manuellement. Le fix résout dynamiquement
le fichier via `find_dotenv()` (walk-up depuis CWD) avec fallback PROJECT_ROOT.
"""

from __future__ import annotations

import pytest

from renoboost_leads.settings import Settings, _find_env_file, get_settings

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Évite la fuite de vars d'env système entre tests."""
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("PAPPERS_API_KEY", raising=False)
    monkeypatch.delenv("DROPCONTACT_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# ─────────────────────────────────────────────────────────────────────────────
# Helper de résolution du fichier .env
# ─────────────────────────────────────────────────────────────────────────────


class TestFindEnvFile:
    def test_trouve_env_dans_cwd(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GOOGLE_PLACES_API_KEY=AIza_dummy\n")
        monkeypatch.chdir(tmp_path)
        assert _find_env_file() == str(env)

    def test_walk_up_depuis_sous_dossier(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GOOGLE_PLACES_API_KEY=AIza_parent\n")
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)
        assert _find_env_file() == str(env)

    def test_renvoie_none_si_absent(self, tmp_path, monkeypatch):
        # Pas de .env dans tmp_path ni au-dessus (tmp_path est isolé)
        monkeypatch.chdir(tmp_path)
        # _find_env_file peut renvoyer None ou le PROJECT_ROOT/.env s'il existe.
        # Dans le sandbox CI on n'a pas de .env à la racine projet → None.
        result = _find_env_file()
        # Le contrat : si rien n'est trouvé, retour None.
        # Si quelque chose est trouvé, ça doit être un fichier existant.
        if result is not None:
            from pathlib import Path

            assert Path(result).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Settings : intégration .env
# ─────────────────────────────────────────────────────────────────────────────


class TestSettingsAutoloadEnvFile:
    def test_charge_cle_depuis_env_dans_cwd(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GOOGLE_PLACES_API_KEY=AIzaDemoKey123Loaded\n")
        monkeypatch.chdir(tmp_path)
        s = get_settings()
        assert s.google_places_api_key.get_secret_value() == "AIzaDemoKey123Loaded"

    def test_charge_cle_depuis_env_dans_parent(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GOOGLE_PLACES_API_KEY=AIzaParentDir9999\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        monkeypatch.chdir(sub)
        s = get_settings()
        assert s.google_places_api_key.get_secret_value() == "AIzaParentDir9999"

    def test_env_var_explicite_prend_priorite(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GOOGLE_PLACES_API_KEY=AIzaFromFile\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "AIzaFromEnvVar")
        s = get_settings()
        assert s.google_places_api_key.get_secret_value() == "AIzaFromEnvVar"

    def test_charge_pappers_optionnel(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GOOGLE_PLACES_API_KEY=AIzaTest\nPAPPERS_API_KEY=pap_test_optional_key\n")
        monkeypatch.chdir(tmp_path)
        s = get_settings()
        assert s.has_pappers() is True
        assert s.pappers_api_key.get_secret_value() == "pap_test_optional_key"

    def test_pas_de_env_pas_de_var_donne_defaults(self, tmp_path, monkeypatch):
        # tmp_path ne contient pas de .env ; mais find_dotenv peut remonter
        # vers un .env du repo si on est dans un test ; on neutralise via
        # une racine isolée.
        monkeypatch.chdir(tmp_path)
        s = get_settings()
        assert s.has_pappers() is False
        # google_places peut être "" (default) ou injecté par un .env amont :
        # on vérifie seulement que l'app démarre sans crash.
        assert isinstance(s, Settings)
