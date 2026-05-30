"""Étage 0 — Découverte SIRENE-first.

Alternative à l'étage 1 Places-first pour les profils où la cible est
définie par des critères entreprise (CA, effectif, NAF, zone) plutôt que
par la visibilité Google Maps. Découvre via recherche-entreprises.api.gouv.fr
puis produit directement des LeadStage2 (données identité + financier).
"""

from .extractor import ExtracteurStage0
from .geocoder import (
    AdresseIntrouvableError,
    BANGeocoder,
    GeocoderConfig,
    ResultatGeocodage,
)
from .mapper import entreprise_to_lead_stage2
from .places_enricher import EnrichisseurPlaces, villes_correspondent

__all__ = [
    "AdresseIntrouvableError",
    "BANGeocoder",
    "EnrichisseurPlaces",
    "ExtracteurStage0",
    "GeocoderConfig",
    "ResultatGeocodage",
    "entreprise_to_lead_stage2",
    "villes_correspondent",
]
