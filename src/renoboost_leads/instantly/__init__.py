"""Intégration Instantly — cold mailing Phase B.

Architecture :
- `client` : wrapper HTTP autour de l'API Instantly v2 (création campagne,
  ajout leads, métriques, pause). Mode dry-run si pas de clé ou si
  `INSTANTLY_DRY_RUN=true`.
- `staging` (B3) : workflow N2 — l'agent drafte les emails dans un
  fichier de staging, l'utilisateur valide manuellement avant envoi réel.
- `sequences` (B2) : templates Jinja par secteur (compta, avocats, etc.).
"""

from __future__ import annotations
