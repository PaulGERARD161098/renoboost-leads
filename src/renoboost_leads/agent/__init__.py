"""Agent Copilote — pilotage assisté/autonome de la prospection RénoBoost.

Phase A : fondations + 7 outils de prospection (run, sessions, qualité, config,
priorisation, alerte humain). Sans cold mailing — voir Phase B pour Instantly.

Composants :
- `journal` : journal markdown des décisions/actions de l'agent
- `budget` : garde-fou €/jour API Claude
- `tools/*` : outils exposés au tool-use Claude
- `runner` : boucle Claude tool-use (palier 5)
"""

from __future__ import annotations
