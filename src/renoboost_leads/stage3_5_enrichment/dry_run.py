"""Client Dropcontact factice — pour tests et `--dry-run`.

Renvoie des données plausibles (email construit, civilité par défaut)
sans appel HTTP réel. Permet de valider le flux pipeline bout-en-bout
sans clé API ni dépense.
"""

from __future__ import annotations

from typing import Any

from .client import DropcontactReponse


class DropcontactClientDryRun:
    """Mime `DropcontactClient.enrichir_batch` sans appel réseau."""

    def __init__(self, cout_par_lead_eur: float = 0.50):
        self.cout_par_lead_eur = cout_par_lead_eur

    def enrichir_batch(self, lots: list[dict[str, Any]]) -> DropcontactReponse:
        data: list[dict[str, Any]] = []
        for lot in lots:
            first = lot.get("first_name", "")
            last = lot.get("last_name", "")
            company = lot.get("company") or ""
            website = lot.get("website") or ""
            domaine = website.replace("https://", "").replace("http://", "").split("/")[0]
            email = None
            if first and last and domaine:
                email = f"{first.lower()}.{last.lower()}@{domaine}"
            data.append(
                {
                    "first_name": first,
                    "last_name": last,
                    "civility": "M" if first else None,
                    "company": company,
                    "website": website,
                    "siren": lot.get("siren"),
                    "email": [{"email": email, "qualification": "correct"}] if email else [],
                    "phone": "+33100000000" if email else None,
                    "linkedin": (
                        f"https://www.linkedin.com/in/{first.lower()}-{last.lower()}/"
                        if first and last
                        else None
                    ),
                    "company_linkedin": (
                        f"https://www.linkedin.com/company/{domaine.split('.')[0]}/"
                        if domaine
                        else None
                    ),
                }
            )
        return DropcontactReponse(
            request_id="dry-run-fake-id",
            data=data,
            cout_eur=0.0,  # gratuit en dry-run
        )
