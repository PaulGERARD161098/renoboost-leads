"""Étage 0 — Découverte SIRENE-first.

Alternative à l'étage 1 Places-first pour les profils où la cible est
définie par des critères entreprise (CA, effectif, NAF, zone) plutôt que
par la visibilité Google Maps. Découvre via recherche-entreprises.api.gouv.fr
puis produit directement des LeadStage2 (données identité + financier).
"""

from .extractor import ExtracteurStage0
from .mapper import entreprise_to_lead_stage2

__all__ = ["ExtracteurStage0", "entreprise_to_lead_stage2"]
