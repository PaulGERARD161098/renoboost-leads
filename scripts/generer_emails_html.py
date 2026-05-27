"""Rapport HTML « emails de prospection » depuis un CSV étage 4.

Wrapper CLI : la logique vit dans renoboost_leads.exporter_html (source unique).
Usage : python scripts/generer_emails_html.py <csv_l4> <sortie.html>
"""

from __future__ import annotations

import sys
from pathlib import Path

from renoboost_leads.exporter_html import export_html_emails

if __name__ == "__main__":
    p = export_html_emails(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Rapport emails HTML écrit : {p} ({p.stat().st_size // 1024} Ko)")
