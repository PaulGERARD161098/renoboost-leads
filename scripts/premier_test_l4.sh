#!/usr/bin/env bash
# Premier test L4 réel — à lancer APRÈS avoir collé ANTHROPIC_API_KEY dans .env
#
# Usage :
#   bash scripts/premier_test_l4.sh
#
# Effectue :
#   1. check-connections (vérifie que la clé est lue)
#   2. tests d'intégration (~0.01 €)
#   3. run L4 sur 5 leads variés (~0.025 €)
#   4. affichage de la sortie pour inspection visuelle
#
# Coût total attendu : < 0.05 €.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "═══════════════════════════════════════════════════════════"
echo "1/4 — Vérification de la clé"
echo "═══════════════════════════════════════════════════════════"
python -m renoboost_leads.cli check-connections | grep -A0 -B0 "Anthropic" || true
echo

# Si la clé n'est pas chargée, on arrête net
if ! python -c "from renoboost_leads.settings import get_settings; \
import sys; sys.exit(0 if get_settings().has_anthropic() else 1)" 2>/dev/null; then
    echo "✗ ANTHROPIC_API_KEY non détectée dans .env"
    echo "  → ouvre le fichier .env, colle ta clé sur la ligne ANTHROPIC_API_KEY="
    exit 2
fi

echo "═══════════════════════════════════════════════════════════"
echo "2/4 — Tests d'intégration (1 appel Haiku + pipeline 3 leads)"
echo "═══════════════════════════════════════════════════════════"
ANTHROPIC_API_KEY="$(grep '^ANTHROPIC_API_KEY=' .env | cut -d= -f2-)" \
    pytest tests/test_stage4_integration.py -v -m integration
echo

echo "═══════════════════════════════════════════════════════════"
echo "3/4 — Premier vrai run L4 (5 leads variés)"
echo "═══════════════════════════════════════════════════════════"
python -m renoboost_leads.cli run \
    --config config/premier_test_l4.yaml \
    --stages 4 \
    --from-csv data/output/2026-05-13_KEYR_premier-test/etage3_contacts.csv
echo

echo "═══════════════════════════════════════════════════════════"
echo "4/4 — Inspection des scores"
echo "═══════════════════════════════════════════════════════════"
python <<'PY'
from pathlib import Path
from renoboost_leads.exporter import lire_stage4_csv

csv_path = Path("data/output/2026-05-13_KEYR_premier-test/etage4_prospection.csv")
leads = lire_stage4_csv(csv_path)

print(f"\n{'Lead':<28s} {'Score':>5s}  {'Top':<5s}  Raison")
print("─" * 90)
for lead in leads:
    top = "TOP" if lead.top_lead else "—"
    raison = (lead.raison_score or "")[:55]
    print(f"{(lead.nom or '?'):<28s} {lead.score_interet:>5d}  {top:<5s}  {raison}")

print(f"\n{'Pitches générés' :>15s}")
print("─" * 90)
for lead in leads:
    if lead.pitch_propose:
        print(f"• {lead.nom}")
        print(f"  {lead.pitch_propose[:200]}")
        print()
PY

echo
echo "═══════════════════════════════════════════════════════════"
echo "✓ Premier test L4 terminé."
echo "  CSV : data/output/2026-05-13_KEYR_premier-test/etage4_prospection.csv"
echo "  Logs : data/output/2026-05-13_KEYR_premier-test/session.log"
echo "  Coût : voir data/output/2026-05-13_KEYR_premier-test/stats_run.json"
echo "═══════════════════════════════════════════════════════════"
