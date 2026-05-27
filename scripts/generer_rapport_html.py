"""Rapport HTML « leads qualifiés » (vue tableau) depuis un CSV L3/L3.5/L4.

Wrapper CLI : la logique vit dans renoboost_leads.exporter_html (source unique).
Usage : python scripts/generer_rapport_html.py <csv> <sortie.html>
"""

from __future__ import annotations

import sys
from pathlib import Path

from renoboost_leads.exporter_html import export_html_leads

if __name__ == "__main__":
    p = export_html_leads(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Rapport HTML écrit : {p} ({p.stat().st_size // 1024} Ko)")
