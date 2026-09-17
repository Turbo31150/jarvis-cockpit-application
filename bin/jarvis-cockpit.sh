#!/usr/bin/env bash
# ==============================================================================
# jarvis-cockpit.sh — LANCEUR DU COCKPIT UNIFIÉ JARVIS
# Redirige vers bin/jarvis-cockpit-app de manière transparente.
# ==============================================================================
set -e

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "Usage: $(basename "$0") [--restart] [--native]"
    echo "Lance le cockpit unifié JARVIS (web app ou GUI natif PyQt6)."
    exit 0
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -x "$DIR/jarvis-cockpit-app" ]; then
    exec "$DIR/jarvis-cockpit-app" "$@"
elif [ -x "$HOME/jarvis/bin/jarvis-cockpit-app" ]; then
    exec "$HOME/jarvis/bin/jarvis-cockpit-app" "$@"
else
    echo "Lanceur jarvis-cockpit-app introuvable dans $DIR ou ~/jarvis/bin." >&2
    exit 1
fi
