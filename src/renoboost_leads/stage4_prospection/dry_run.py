"""Client L4 factice — n'appelle pas l'API, retourne des réponses plausibles.

Utilisé par `--dry-run --stages 4` pour valider le flow complet (CLI, cache,
exporter, UI) sans dépenser de tokens et sans clé Anthropic.

Les scores sont déterministes : un même prompt produit toujours la même réponse
(via hash sha256), ce qui permet de tester l'invalidation du cache.
"""

from __future__ import annotations

import hashlib
import re

from .client import ClaudeReponse


def _extraire_nom_lead(prompt: str) -> str:
    """Tente d'extraire le nom du lead depuis le prompt construit.

    Format attendu : "- Nom : <nom>" dans la section `# Lead à évaluer`.
    """
    m = re.search(r"-\s*Nom\s*:\s*([^\n]+)", prompt)
    if m:
        return m.group(1).strip()
    return "ce lead"


class ClaudeClientDryRun:
    """Mock de `ClaudeClient` qui ne fait aucun appel réseau.

    Expose la même signature publique que `ClaudeClient` (méthode
    `scorer(prompt) -> ClaudeReponse`) pour être interchangeable dans l'enricher.
    """

    def __init__(self, modele: str = "claude-haiku-4-5", inclure_pitch: bool = True):
        self.modele = modele
        self.inclure_pitch = inclure_pitch
        # Compteur d'appels (utile pour les logs / asserts)
        self.calls = 0

    def scorer(self, prompt: str) -> ClaudeReponse:
        self.calls += 1
        nom = _extraire_nom_lead(prompt)
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        score = 30 + (int(h[:8], 16) % 66)  # 30..95, stable

        if score >= 80:
            raison = f"[DRY-RUN] {nom} : profil B2B prometteur."
        elif score >= 60:
            raison = f"[DRY-RUN] {nom} : profil intermédiaire, à qualifier."
        else:
            raison = f"[DRY-RUN] {nom} : hors ICP probable."

        pitch = None
        if self.inclure_pitch:
            pitch = (
                f"[DRY-RUN] Bonjour, j'ai repéré {nom}. "
                "Auriez-vous 15 min pour parler audit énergétique ?"
            )

        return ClaudeReponse(
            score_interet=score,
            raison_score=raison,
            pitch_propose=pitch,
            tokens_in=0,
            tokens_out=0,
            cout_eur=0.0,
            modele=self.modele,
        )


__all__ = ["ClaudeClientDryRun"]
