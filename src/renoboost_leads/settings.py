"""Configuration globale — chargée depuis .env via pydantic-settings.

Validation stricte au démarrage : si une variable obligatoire manque
ou est invalide, l'app refuse de démarrer avec un message clair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import find_dotenv
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemin racine du projet (= dossier qui contient `pyproject.toml`)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_env_file() -> str | None:
    """Localise un fichier .env de façon dynamique (B7).

    Stratégie :
    1. `find_dotenv(usecwd=True)` remonte depuis le répertoire courant — couvre
       le cas standard où le user lance la CLI depuis la racine projet ou un
       sous-dossier, y compris en venv Windows et en install non-éditable.
    2. Fallback : `PROJECT_ROOT / .env` si présent (compat historique).
    3. None si rien — Settings s'initialisera depuis les variables d'env seules.
    """
    found = find_dotenv(usecwd=True)
    if found:
        return found
    fallback = PROJECT_ROOT / ".env"
    if fallback.exists():
        return str(fallback)
    return None


class Settings(BaseSettings):
    """Variables d'environnement validées par Pydantic."""

    model_config = SettingsConfigDict(
        # env_file résolu dynamiquement à chaque instanciation via __init__ ci-dessous.
        # Le fallback statique sert uniquement aux instances construites sans
        # passer par get_settings() (cas marginal — tests directs, scripts ad-hoc).
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

    # ─── Phase B : Instantly (cold mailing — optionnel) ───
    instantly_api_key: SecretStr | None = Field(default=None)
    instantly_base_url: str = Field(default="https://api.instantly.ai/api/v2")
    # Mode dry-run global : si True, le client Instantly n'envoie aucune
    # requête réelle et renvoie des payloads simulés. Pratique tant que
    # l'abonnement n'est pas actif et pour les tests d'intégration locaux.
    instantly_dry_run: bool = Field(default=True)

    # ─── Plafonds de sécurité ───
    max_budget_eur_per_run: float = Field(default=30.0, gt=0, le=1000)
    max_leads_per_run: int = Field(default=500, gt=0, le=10_000)
    max_requests_per_minute: int = Field(default=60, gt=0, le=600)

    # ─── Logging ───
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "text"] = Field(default="json")

    # ─── Storage Supabase (persistance des sessions, optionnel) ───
    storage_backend: Literal["local", "supabase"] = Field(
        default="local",
        description=(
            "Backend de persistance des sessions. 'local' (défaut) = "
            "data/output/ uniquement. 'supabase' = upload auto vers le "
            "bucket configuré + lecture depuis ce bucket."
        ),
    )
    supabase_url: str | None = Field(
        default=None,
        description="URL projet Supabase, ex https://xxx.supabase.co",
    )
    supabase_service_role_key: SecretStr | None = Field(
        default=None,
        description=(
            "Clé service_role (pas anon) — permet l'upload/download "
            "côté serveur en bypassant RLS. NE JAMAIS exposer côté client."
        ),
    )
    supabase_bucket: str = Field(
        default="sessions",
        description="Nom du bucket Supabase Storage qui héberge les sessions.",
    )

    # ─── Auth interface Streamlit (optionnel) ───
    app_password: SecretStr | None = Field(
        default=None,
        description=(
            "Mot de passe partagé pour accéder à l'app Streamlit déployée. "
            "Si vide, l'app est ouverte (mode dev local)."
        ),
    )

    # ─── Veille — SMTP (notification email post-run) ───
    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = Field(default=None)
    smtp_password: SecretStr | None = Field(default=None)
    smtp_from: str | None = Field(default=None)
    smtp_destinataires: str = Field(default="")  # CSV séparé par virgules
    smtp_use_tls: bool = Field(default=True)

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

    def has_instantly(self) -> bool:
        return self.instantly_api_key is not None and bool(
            self.instantly_api_key.get_secret_value()
        )

    def has_smtp(self) -> bool:
        """SMTP utilisable (host + user + password + from + au moins 1 dest)."""
        return all(
            [
                self.smtp_host,
                self.smtp_user,
                self.smtp_password and self.smtp_password.get_secret_value(),
                self.smtp_from,
                self.smtp_destinataires.strip(),
            ]
        )

    def smtp_destinataires_list(self) -> list[str]:
        """Renvoie la liste de destinataires nettoyée."""
        return [d.strip() for d in self.smtp_destinataires.split(",") if d.strip()]

    def has_google_places(self) -> bool:
        return bool(self.google_places_api_key.get_secret_value())

    def has_supabase_storage(self) -> bool:
        """Supabase Storage utilisable (URL + service role + backend activé)."""
        return (
            self.storage_backend == "supabase"
            and bool(self.supabase_url)
            and self.supabase_service_role_key is not None
            and bool(self.supabase_service_role_key.get_secret_value())
        )

    def has_app_password(self) -> bool:
        return self.app_password is not None and bool(self.app_password.get_secret_value())


# Instance unique
def get_settings() -> Settings:
    """Renvoie une instance de Settings (lazy).

    Résout dynamiquement le fichier .env via `_find_env_file()` pour rester
    robuste quand le CWD ≠ racine projet (cas Windows / installs non-éditables).
    """
    env_file = _find_env_file()
    if env_file:
        return Settings(_env_file=env_file)
    return Settings()
