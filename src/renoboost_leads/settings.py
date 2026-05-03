"""Configuration globale — chargée depuis .env via pydantic-settings.

Validation stricte au démarrage : si une variable obligatoire manque
ou est invalide, l'app refuse de démarrer avec un message clair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemin racine du projet (= dossier qui contient `pyproject.toml`)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Variables d'environnement validées par Pydantic."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Étage 1 : Google Places ───
    google_places_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Clé API Google Places (New). Obligatoire pour Étage 1.",
    )

    # ─── Étage 2 : Pappers (optionnel pour L1) ───
    pappers_api_key: SecretStr | None = Field(default=None)
    pappers_plan: Literal["starter", "pro", "business"] = Field(default="starter")

    # ─── Étage 3 : Dropcontact (optionnel pour L1) ───
    dropcontact_api_key: SecretStr | None = Field(default=None)

    # ─── Étage 4 : Anthropic Claude (optionnel pour L1) ───
    anthropic_api_key: SecretStr | None = Field(default=None)
    claude_model: str = Field(default="claude-sonnet-4-6")

    # ─── Plafonds de sécurité ───
    max_budget_eur_per_run: float = Field(default=30.0, gt=0, le=1000)
    max_leads_per_run: int = Field(default=500, gt=0, le=10_000)
    max_requests_per_minute: int = Field(default=60, gt=0, le=600)

    # ─── Logging ───
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "text"] = Field(default="json")

    @field_validator("google_places_api_key")
    @classmethod
    def _validate_google_key_format(cls, v: SecretStr) -> SecretStr:
        """Format Google : commence par AIza et fait ~39 caractères."""
        secret = v.get_secret_value()
        if secret and not secret.startswith("AIza"):
            raise ValueError("GOOGLE_PLACES_API_KEY format inattendu (doit commencer par 'AIza').")
        return v

    # ─── Helpers ───
    def has_pappers(self) -> bool:
        return self.pappers_api_key is not None and bool(self.pappers_api_key.get_secret_value())

    def has_dropcontact(self) -> bool:
        return self.dropcontact_api_key is not None and bool(
            self.dropcontact_api_key.get_secret_value()
        )

    def has_anthropic(self) -> bool:
        return self.anthropic_api_key is not None and bool(
            self.anthropic_api_key.get_secret_value()
        )

    def has_google_places(self) -> bool:
        return bool(self.google_places_api_key.get_secret_value())


# Instance unique
def get_settings() -> Settings:
    """Renvoie une instance de Settings (lazy)."""
    return Settings()
