"""Worker RenoBoost — exécute les `runs` Supabase hors-ligne (Railway).

Boucle : poll des runs `demande` → claim atomique → exécution d'un Pipeline →
écriture des leads + progression en continu → finalisation `termine`/`echoue`.

Isolé du package `renoboost_leads` (déployable seul) : ne dépend que de `requests`.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
