#!/bin/bash
# SessionStart hook — prépare un environnement Python exécutable pour la session.
# Crée un venv isolé et installe le package en éditable (deps + dev + storage),
# puis expose le venv à toute la session via CLAUDE_ENV_FILE pour que
# `python`, `pytest`, `ruff` et la CLI `renoboost-leads` fonctionnent directement.
set -euo pipefail

# Ne tourne qu'en environnement distant (Claude Code on the web).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# venv isolé (évite le conflit PyJWT du Python système debian).
if [ ! -d .venv ]; then
  python -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev,storage]"

# Expose le venv au reste de la session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=${CLAUDE_PROJECT_DIR:-$PWD}/.venv"
    echo "export PATH=${CLAUDE_PROJECT_DIR:-$PWD}/.venv/bin:\$PATH"
  } >> "$CLAUDE_ENV_FILE"
fi

echo "✅ renoboost-leads : venv prêt, package installé (deps+dev+storage)."
