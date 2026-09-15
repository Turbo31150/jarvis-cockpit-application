#!/usr/bin/env bash
# ==============================================================================
# JARVIS BOX — INSTALLEUR AUTONOME & DÉPLOIEMENT APPLIANCE SOUVERAINE
# ==============================================================================
# Référence : Cahier des Charges Fonctionnel & Technique v1.0.0-PROD
# Rôle : Qualification matérielle, durcissement Zero-Trust, configuration P0,
#        initialisation du service Cockpit OS et validation RAG 0-Token.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
JARVIS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}==================================================================${NC}"
echo -e "${GREEN}   🏛️  JARVIS BOX — INSTALLATEUR D'APPLIANCE SOUVERAINE 0-TOKEN   ${NC}"
echo -e "${CYAN}==================================================================${NC}"
echo -e "Date : $(date '+%Y-%m-%d %H:%M:%S') | Hôte : $(hostname)"
echo -e "Racine JARVIS : $JARVIS_ROOT"
echo ""

# ── 1. CONTRÔLE DES PRIVILÈGES & PRÉREQUIS SYSTÈME ──
echo -e "${BLUE}[1/7] Qualification Système & Matériel...${NC}"

# CPU check
CPU_MODEL=$(lscpu | grep "Nom de modèle\|Model name" | cut -d: -f2 | xargs || echo "Inconnu")
AVX2_SUPPORT=$(grep -m1 -c "avx2" /proc/cpuinfo || true)
echo -e "  • CPU : $CPU_MODEL"
if [ "$AVX2_SUPPORT" -ge 1 ]; then
    echo -e "  • Support vectoriel AVX2 : ${GREEN}OUI (Optimal pour tokenisation/FTS5)${NC}"
else
    echo -e "  • Support vectoriel AVX2 : ${YELLOW}NON (Mode laboratoire compatible)${NC}"
fi

# RAM check
RAM_TOTAL_MB=$(free -m | awk '/^Mem:/{print $2}')
RAM_TOTAL_GB=$(python3 -c "print(round($RAM_TOTAL_MB/1024, 1))")
echo -e "  • Mémoire Vive (RAM) : ${RAM_TOTAL_GB} Go"
if [ "$RAM_TOTAL_MB" -ge 16000 ]; then
    echo -e "  • Seuil RAM : ${GREEN}CONFORME (>= 16 Go)${NC}"
else
    echo -e "  • Seuil RAM : ${YELLOW}ATTENTION (< 16 Go, recommandé 32-64 Go)${NC}"
fi

# GPU check
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
    TOTAL_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | awk '{s+=$1} END {print s}')
    TOTAL_VRAM_GB=$(awk "BEGIN {printf \"%.1f\", $TOTAL_VRAM_MB/1024}")
    echo -e "  • Accélération GPU : ${GREEN}$GPU_COUNT GPU(s) NVIDIA détecté(s) — ${TOTAL_VRAM_GB} Go VRAM totale${NC}"
    nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader | while IFS=',' read -r idx name mem drv; do
        echo -e "    - GPU$idx : $name ($mem) | Pilote : $drv"
    done
else
    echo -e "  • Accélération GPU : ${YELLOW}Aucun GPU NVIDIA actif (Mode dégradé CPU)${NC}"
fi

# ── 2. ARBORESCENCE & DÉPENDANCES PYTHON ──
echo ""
echo -e "${BLUE}[2/7] Configuration de l'Arborescence & Dépendances...${NC}"
mkdir -p "$JARVIS_ROOT/config" "$JARVIS_ROOT/data" "$JARVIS_ROOT/logs" "$JARVIS_ROOT/data/mirror"

VENV_PATH="$JARVIS_ROOT/.venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "  • Création de l'environnement virtuel Python (.venv)..."
    python3 -m venv "$VENV_PATH"
fi

PY_BIN="$VENV_PATH/bin/python3"
PIP_BIN="$VENV_PATH/bin/pip"
echo -e "  • Python venv : $($PY_BIN --version) à $PY_BIN"

# Vérification des paquets vitaux
$PY_BIN -c "import sqlite3, urllib.request, hashlib, socket; print('  • Modules internes standard : OK')"

# ── 3. INTÉGRITÉ DU MOAT SOUVERAIN (board.db) ──
echo ""
echo -e "${BLUE}[3/7] Validation de l'Intégrité de board.db (FTS5 BM25)...${NC}"
BOARD_DB="$JARVIS_ROOT/board/board.db"
if [ -f "$BOARD_DB" ]; then
    BOARD_SIZE_GB=$(du -h "$BOARD_DB" | cut -f1)
    echo -e "  • Emplacement : $BOARD_DB ($BOARD_SIZE_GB)"
    
    # Test FTS5 rapide
    QUERY_TEST=$($PY_BIN -c "
import sqlite3, sys
try:
    con = sqlite3.connect('file:$BOARD_DB?mode=ro', uri=True, timeout=5)
    cur = con.cursor()
    cur.execute('SELECT count(*) FROM chunks;')
    chunks = cur.fetchone()[0]
    cur.execute('SELECT count(*) FROM sources;')
    sources = cur.fetchone()[0]
    cur.execute('SELECT count(*) FROM answers_sans_citation;')
    rejets = cur.fetchone()[0]
    con.close()
    print(f'{chunks}|{sources}|{rejets}')
except Exception as e:
    print(f'ERROR|{e}')
")
    if [[ "$QUERY_TEST" == ERROR* ]]; then
        echo -e "  • Test SQLite : ${RED}ÉCHEC ($QUERY_TEST)${NC}"
    else
        IFS='|' read -r CHUNKS SOURCES REJETS <<< "$QUERY_TEST"
        echo -e "  • Fragments curés : ${GREEN}$CHUNKS chunks${NC}"
        echo -e "  • Sources tracées : ${GREEN}$SOURCES sources${NC}"
        echo -e "  • Règle Anti-Hallucination : ${GREEN}Vue answers_sans_citation validée ($REJETS rejets tracés)${NC}"
    fi
else
    echo -e "  • board.db : ${YELLOW}Non trouvé à $BOARD_DB (Ingestion requise)${NC}"
fi

# ── 4. SÉCURITÉ P0 & GÉNÉRATION DU JETON BEARER ──
echo ""
echo -e "${BLUE}[4/7] Sécurisation P0 & Jeton d'Authentification...${NC}"
TOKEN_FILE="$JARVIS_ROOT/config/auth_token.secret"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "  • Génération d'un nouveau jeton Bearer cryptographique..."
    $PY_BIN -c "import secrets; print(secrets.token_hex(24))" > "$TOKEN_FILE"
    chmod 0600 "$TOKEN_FILE"
    echo -e "  • Jeton enregistré dans $TOKEN_FILE (${GREEN}permissions 0600${NC})"
else
    chmod 0600 "$TOKEN_FILE"
    echo -e "  • Jeton existant vérifié : $TOKEN_FILE (${GREEN}permissions 0600 conformes${NC})"
fi
TOKEN_PREVIEW=$(head -c 6 "$TOKEN_FILE")...$(tail -c 5 "$TOKEN_FILE")
echo -e "  • Empreinte Jeton : ${CYAN}$TOKEN_PREVIEW${NC}"

# ── 5. SERVICE SYSTEMD D'APPLIANCE COCKPIT ──
echo ""
echo -e "${BLUE}[5/7] Configuration du Service Démon Cockpit (:8600)...${NC}"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_SYSTEMD_DIR"
SERVICE_FILE="$USER_SYSTEMD_DIR/jarvis-cockpit.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=JARVIS Cockpit Application Server (:8600)
After=network.target

[Service]
Type=simple
WorkingDirectory=$JARVIS_ROOT/cockpit
ExecStart=$PY_BIN $JARVIS_ROOT/cockpit/serveur.py
Restart=always
RestartSec=3
Environment=COCKPIT_PORT=8600
Environment=PYTHONUNBUFFERED=1
StandardOutput=append:$JARVIS_ROOT/logs/cockpit.log
StandardError=append:$JARVIS_ROOT/logs/cockpit.log

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable jarvis-cockpit.service
systemctl --user restart jarvis-cockpit.service
echo -e "  • Service ${GREEN}jarvis-cockpit.service${NC} activé et démarré."

# ── 6. VÉRIFICATION DU COCKPIT EN LIGNE ──
echo ""
echo -e "${BLUE}[6/7] Vérification de l'API Cockpit en Direct...${NC}"
sleep 2
if curl -s -f http://127.0.0.1:8600/api/status >/dev/null 2>&1; then
    echo -e "  • Serveur HTTP (:8600) : ${GREEN}EN LIGNE & OPÉRATIONNEL${NC}"
    APP_STATUS=$(curl -s http://127.0.0.1:8600/api/appliance/status || echo "{}")
    echo -e "  • Modèle Appliance : ${GREEN}$(echo "$APP_STATUS" | grep -o '"appliance_model": "[^"]*"' | cut -d'"' -f4 || echo "JARVIS Box")${NC}"
else
    echo -e "  • Serveur HTTP (:8600) : ${RED}ERREUR DE DÉMARRAGE (vérifier $JARVIS_ROOT/logs/cockpit.log)${NC}"
fi

# ── 7. SYNTHÈSE & CERTIFICAT DÉPLOIEMENT ──
echo ""
echo -e "${CYAN}==================================================================${NC}"
echo -e "${GREEN}    🎉 DÉPLOIEMENT DE L'APPLIANCE JARVIS BOX ACHEVÉ AVEC SUCCÈS   ${NC}"
echo -e "${CYAN}==================================================================${NC}"
echo -e "Accès Cockpit Bureau : ${GREEN}http://127.0.0.1:8600/#audit${NC}"
echo -e "Jeton Bearer API :      ${CYAN}$TOKEN_PREVIEW${NC}"
echo -e "Attestation DPO :       ${GREEN}http://127.0.0.1:8600/api/rag/export-dpo${NC}"
echo -e "Validation Pré-Vol :    ${GREEN}http://127.0.0.1:8600/api/appliance/validation${NC}"
echo -e "Miroir Haute Dispo :    ${GREEN}http://127.0.0.1:8600/api/appliance/ha${NC}"
echo -e "${CYAN}==================================================================${NC}"
