#!/usr/bin/env bash
# =============================================================================
# JARVIS COCKPIT — INSTALLATEUR UNIVERSEL & REPRODUCTIBLE À L'INFINI
# Permet de déployer et lancer l'application Cockpit Bureau sur n'importe quel OS Linux
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "🚀 DÉPLOIEMENT REPRODUCTIBLE : JARVIS COCKPIT APPLICATION"
echo "=========================================================="

# 1. Vérification de Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Erreur : python3 n'est pas installé sur ce système."
    echo "Installer avec : sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python détecté : version $PY_VER"

# 2. Création ou détection du venv
if [ ! -d ".venv" ]; then
    echo "📦 Création de l'environnement virtuel local (.venv)..."
    python3 -m venv .venv
fi

PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python3"
PIP_EXEC="$SCRIPT_DIR/.venv/bin/pip"

# 3. Installation des dépendances
echo "📥 Installation / mise à jour des dépendances..."
"$PIP_EXEC" install --upgrade pip >/dev/null 2>&1 || true
"$PIP_EXEC" install -r requirements.txt

# 4. Rendre exécutables les lanceurs
chmod +x portable/JARVIS-COCKPIT.sh bin/* 2>/dev/null || true

# 5. Création des dossiers de travail locaux
mkdir -p jarvis/{logs,data,databases}

echo "=========================================================="
echo "🎉 INSTALLATION TERMINÉE AVEC SUCCÈS !"
echo ""
echo "Modes d'exécution disponibles :"
echo "  1) Application Bureau PyQt6 (15 onglets) :"
echo "     ./portable/JARVIS-COCKPIT.sh"
echo "     ou : $PYTHON_EXEC cockpit/gui_app.py"
echo ""
echo "  2) Serveur Web REST Cockpit (:8600) :"
echo "     $PYTHON_EXEC cockpit/serveur.py"
echo "     ou : ./portable/JARVIS-COCKPIT.sh --web"
echo ""
echo "  3) Terminal TUI Dashboard :"
echo "     $PYTHON_EXEC cockpit/app.py"
echo "=========================================================="
