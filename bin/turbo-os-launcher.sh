#!/usr/bin/env bash
# ==============================================================================
# TURBO OS — LANCEUR UNIFIÉ & VÉRIFICATEUR DES 10 ORGANES VITAUX
# ==============================================================================
# Point d'entrée principal :
#   SYSTEM START → TURBO OS → COCKPIT → BOARD → MODULES → APPLICATIONS
#
# Usage :
#   turbo-os-launcher.sh [--check] [--json] [--start] [--restart] [--help]
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"

show_help() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --check       Vérifie l'état réel des 10 organes vitaux sans lancer l'interface"
    echo "  --json        Affiche le bilan de santé des 10 organes en JSON brut"
    echo "  --start       Vérifie les organes, assure le serveur Cockpit :8600 et lance l'app"
    echo "  --restart     Redémarre le Cockpit et relance l'application"
    echo "  --help, -h    Affiche cette aide"
    echo ""
    echo "Organes vérifiés : Environnement, Services, LM Studio, MCP, STT, TTS, GPU, Mémoire, RAG, Cockpit."
}

MODE="${1:---check}"

case "$MODE" in
    --help|-h)
        show_help
        exit 0
        ;;
    --check)
        exec "$PYTHON" "$REPO_ROOT/cockpit/core/launcher.py" --check
        ;;
    --json)
        exec "$PYTHON" "$REPO_ROOT/cockpit/core/launcher.py" --json
        ;;
    --restart)
        echo "Redémarrage du serveur Cockpit..."
        pkill -f "cockpit/serveur.py" 2>/dev/null || true
        sleep 1
        "$PYTHON" "$REPO_ROOT/cockpit/serveur.py" >/dev/null 2>&1 &
        sleep 1
        MODE="--start"
        ;;
esac

# 1. Vérification des 10 organes
echo "Vérification préalable des 10 organes vitaux..."
"$PYTHON" "$REPO_ROOT/cockpit/core/launcher.py" --check

# 2. Vérification que le Cockpit écoute sur le port 8600
if ! nc -z 127.0.0.1 8600 2>/dev/null && ! curl -s -m 1 http://127.0.0.1:8600/api/status >/dev/null 2>&1; then
    echo "Démarrage du serveur Cockpit sur :8600..."
    nohup "$PYTHON" "$REPO_ROOT/cockpit/serveur.py" > "$HOME/jarvis/logs/cockpit-server.log" 2>&1 &
    sleep 2
fi

# 3. Lancement de l'interface bureau dédiée
LAUNCHER="$HOME/.local/bin/turbo-os"
if [ -x "$LAUNCHER" ]; then
    echo "Lancement de l'interface Turbo OS..."
    exec "$LAUNCHER"
else
    BROWSER="$(command -v google-chrome || command -v chromium || true)"
    if [ -n "$BROWSER" ]; then
        exec "$BROWSER" --app="http://127.0.0.1:8600/orbe.html" --class=TurboOS --name=TurboOS
    else
        echo "Cockpit prêt sur http://127.0.0.1:8600"
    fi
fi
