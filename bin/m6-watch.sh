#!/usr/bin/env bash
# =============================================================================
# m6-watch.sh — SUPERVISION DU NŒUD GPU M6 (10.42.0.230)
# =============================================================================
set -u

M6_HOST="${M6_HOST:-10.42.0.230}"
INTERVAL="${1:-3}"

echo "🖥  [JARVIS] Surveillance du nœud M6 ($M6_HOST) (rafraîchissement ${INTERVAL}s)..."

while true; do
    clear 2>/dev/null || true
    echo "====================================================================="
    echo "🖥  CLUSTER M6 GPU MONITOR — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "   Cible : $M6_HOST (Câble direct 10 GbE / LAN)"
    echo "====================================================================="
    echo
    if ping -c 1 -W 1 "$M6_HOST" >/dev/null 2>&1; then
        echo -e "  Connectivité réseau : \033[32m✓ JOIGNABLE (Ping OK)\033[0m"
        echo
        echo "--- État GPU Distant (M6) ---"
        if ssh -o BatchMode=yes -o ConnectTimeout=2 "$M6_HOST" "nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader" 2>/dev/null; then
            :
        else
            echo "  (Accès SSH direct non authentifié ou session fermée)"
        fi
        echo
        echo "--- Services Distants ---"
        for svc in "LMStudio:1234" "Ollama:11434" "Cockpit:8600"; do
            nom="${svc%%:*}"; port="${svc##*:}"
            if timeout 1 bash -c "</dev/tcp/$M6_HOST/$port" 2>/dev/null; then
                printf "  %-12s [Port %5s] : \033[32mEN LIGNE\033[0m\n" "$nom" "$port"
            else
                printf "  %-12s [Port %5s] : \033[33mNON RÉPONDANT\033[0m\n" "$nom" "$port"
            fi
        done
    else
        echo -e "  Connectivité réseau : \033[31m✖ INJOIGNABLE ($M6_HOST)\033[0m"
        echo "  Vérifiez le câble direct ou le bail DHCP/IP statique."
    fi

    if [ "${1:-}" = "--once" ] || [ "${2:-}" = "--once" ]; then
        break
    fi
    sleep "$INTERVAL"
done
