#!/usr/bin/env bash
# =============================================================================
# JARVIS COCKPIT — LANCEUR PORTABLE
#
# Se lance depuis N'IMPORTE QUEL emplacement : cle USB, disque externe, VHDX.
# Il ne suppose aucun chemin : il deduit sa racine de sa propre position.
#
#   ./JARVIS-COCKPIT.sh            application de bureau (15 onglets)
#   ./JARVIS-COCKPIT.sh --web      serveur seul, puis navigateur sur :8600
#   ./JARVIS-COCKPIT.sh --verifier controle les prerequis sans rien lancer
# =============================================================================
set -euo pipefail

# Racine reelle du paquet, quel que soit le point de montage.
# readlink -f resout les liens : un raccourci vers ce script marche aussi.
RACINE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
if [ ! -d "$RACINE/cockpit" ] && [ -d "$RACINE/../cockpit" ]; then
    RACINE="$(cd "$RACINE/.." && pwd)"
fi

# Détection intelligente et relocalisable de Python
if [ -x "$RACINE/.venv/bin/python3" ]; then
    PYTHON_BIN="$RACINE/.venv/bin/python3"
elif [ -x "$RACINE/../.venv/bin/python3" ]; then
    PYTHON_BIN="$RACINE/../.venv/bin/python3"
elif [ -x "/home/turbo/jarvis/.venv/bin/python3" ]; then
    PYTHON_BIN="/home/turbo/jarvis/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

# Dit a l'application ou vivre. Sans cela elle chercherait ~/jarvis sur la
# machine hote — qui n'existe pas forcement, et qui n'est pas la nôtre.
export JARVIS_COCKPIT_ROOT="$RACINE/jarvis"
export PYTHONPATH="$RACINE/cockpit:${PYTHONPATH:-}"
mkdir -p "$JARVIS_COCKPIT_ROOT"/{logs,data,databases}

verifier() {
    local manque=0
    echo "Racine      : $RACINE"
    echo "Donnees     : $JARVIS_COCKPIT_ROOT"
    printf "python3     : "
    if command -v "$PYTHON_BIN" >/dev/null 2>&1; then "$PYTHON_BIN" --version; else echo "ABSENT"; manque=1; fi
    printf "PyQt6       : "
    if "$PYTHON_BIN" -c "import PyQt6" 2>/dev/null; then
        "$PYTHON_BIN" -c "from PyQt6.QtCore import QT_VERSION_STR; print('present, Qt', QT_VERSION_STR)"
    else
        # PyQt6 n'est PAS embarque : il pese ~100 Mo et depend de la
        # bibliotheque graphique de la machine hote. On le dit franchement
        # plutot que d'echouer au lancement avec une trace Python.
        echo "ABSENT — installer :  sudo apt install python3-pyqt6"
        manque=1
    fi
    printf "ecriture    : "
    if touch "$JARVIS_COCKPIT_ROOT/.t" 2>/dev/null; then
        rm -f "$JARVIS_COCKPIT_ROOT/.t"; echo "OK"
    else
        echo "LECTURE SEULE — l'application demarre mais ne gardera rien"
    fi
    echo "fichiers py : $(find "$RACINE/cockpit" -name '*.py' | wc -l)"
    return $manque
}

case "${1:-}" in
    --verifier|-v) verifier; exit $? ;;
    --web|-w)
        verifier >/dev/null || true
        cd "$RACINE/cockpit"
        "$PYTHON_BIN" serveur.py &
        sleep 2
        xdg-open "http://127.0.0.1:${COCKPIT_PORT:-8600}" >/dev/null 2>&1 || true
        wait
        ;;
    *)
        if ! "$PYTHON_BIN" -c "import PyQt6" 2>/dev/null; then
            echo "PyQt6 absent sur cette machine." >&2
            echo "  interface graphique :  sudo apt install python3-pyqt6" >&2
            echo "  sans installer      :  $0 --web   (navigateur, meme cockpit)" >&2
            exit 1
        fi
        cd "$RACINE/cockpit"
        exec "$PYTHON_BIN" gui_app.py "$@"
        ;;
esac
