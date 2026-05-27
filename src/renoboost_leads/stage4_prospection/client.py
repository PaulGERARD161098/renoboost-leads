"""Wrapper du SDK Anthropic pour le scoring L4.

Responsabilités :
- Appel `messages.create` avec retry + budget guard
- Parsing JSON strict de la réponse
- Calcul du coût en € à partir des `usage` retournés

Conçu pour être facilement mockable dans les tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..common.budget_guard import BudgetExceededError, BudgetGuard
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = get_logger(__name__)


# Pricing par modèle ($ par MTok input/output, mai 2026).
# Convertis en EUR avec un taux indicatif 0.93 EUR/USD.
_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}
_USD_TO_EUR = 0.93


def cout_eur(modele: str, tokens_in: int, tokens_out: int) -> float:
    """Calcule le coût en euros d'un appel à partir des tokens consommés."""
    prix_in, prix_out = _PRICING_USD_PER_MTOK.get(modele, (3.00, 15.00))
    usd = (tokens_in / 1_000_000) * prix_in + (tokens_out / 1_000_000) * prix_out
    return usd * _USD_TO_EUR


@dataclass
class ClaudeReponse:
    """Réponse normalisée pour un lead."""

    score_interet: int
    raison_score: str
    pitch_propose: str | None
    tokens_in: int
    tokens_out: int
    cout_eur: float
    modele: str
    email_objet: str | None = None
    email_corps: str | None = None


@dataclass
class ClaudeClientConfig:
    api_key: str
    modele: str = "claude-haiku-4-5"
    max_tokens_sortie: int = 400
    rate_limiter: RateLimiter | None = None
    budget: BudgetGuard | None = None
    # Si fourni, c'est le client Anthropic injecté (utile pour les tests).
    sdk_client: Anthropic | None = None


class ClaudeParseError(ValueError):
    """Lève quand la réponse Claude n'est pas un JSON exploitable."""


def _extraire_json(texte: str) -> dict[str, Any]:
    """Parse strictement le JSON renvoyé par Claude.

    Tolère un préfixe ```json et un suffixe ``` au cas où le modèle aurait
    ajouté un fenced code block malgré l'instruction.
    """
    cleaned = texte.strip()
    if cleaned.startswith("```"):
        # ```json\n...\n```
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ClaudeParseError(f"JSON invalide : {e}") from e


class ClaudeClient:
    """Façade SDK Anthropic — retourne un `ClaudeReponse` typé."""

    def __init__(self, config: ClaudeClientConfig):
        self.config = config
        self._client = config.sdk_client or self._build_sdk_client()

    def _build_sdk_client(self) -> Anthropic:
        # Import paresseux : si l'utilisateur n'utilise pas L4, anthropic
        # peut ne pas être importable à l'init de la lib (lazy guard).
        from anthropic import Anthropic

        return Anthropic(api_key=self.config.api_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _call_api(self, prompt: str) -> Any:
        if self.config.rate_limiter:
            self.config.rate_limiter.acquire()
        return self._client.messages.create(
            model=self.config.modele,
            max_tokens=self.config.max_tokens_sortie,
            messages=[{"role": "user", "content": prompt}],
        )

    def scorer(self, prompt: str) -> ClaudeReponse:
        """Envoie le prompt et retourne la réponse parsée.

        Peut lever :
        - `ClaudeParseError` si la réponse n'est pas du JSON exploitable
        - `BudgetExceededError` si le run dépasse son plafond
        - Toute exception SDK Anthropic non gérée par le retry
        """
        message = self._call_api(prompt)

        # Extraction texte (le SDK renvoie une liste de content blocks).
        if not message.content:
            raise ClaudeParseError("Réponse Claude vide.")
        bloc = message.content[0]
        texte = getattr(bloc, "text", None)
        if texte is None:
            raise ClaudeParseError(f"Réponse Claude sans bloc texte : {type(bloc).__name__}")

        data = _extraire_json(texte)

        # Validation des champs
        if "score_interet" not in data or "raison_score" not in data:
            raise ClaudeParseError(
                f"Champs obligatoires manquants. Reçu : {sorted(data.keys())}"
            )

        try:
            score = int(data["score_interet"])
        except (TypeError, ValueError) as e:
            raise ClaudeParseError(f"score_interet non entier : {data['score_interet']!r}") from e
        score = max(0, min(100, score))

        raison = str(data["raison_score"]).strip()
        pitch_brut = data.get("pitch_propose")
        pitch = str(pitch_brut).strip() if pitch_brut else None
        objet_brut = data.get("email_objet")
        email_objet = str(objet_brut).strip() if objet_brut else None
        corps_brut = data.get("email_corps")
        email_corps = str(corps_brut).strip() if corps_brut else None

        tokens_in = int(getattr(message.usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(message.usage, "output_tokens", 0) or 0)
        cout = cout_eur(self.config.modele, tokens_in, tokens_out)

        if self.config.budget:
            try:
                self.config.budget.ajouter_cout(cout, contexte=f"L4 {self.config.modele}")
            except BudgetExceededError:
                raise

        return ClaudeReponse(
            score_interet=score,
            raison_score=raison,
            pitch_propose=pitch,
            email_objet=email_objet,
            email_corps=email_corps,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cout_eur=cout,
            modele=self.config.modele,
        )
