#!/usr/bin/env bash
# =============================================================================
# swarm-watch.sh — SUPERVISION DES SERVICES DOCKER SWARM & CONTENEURS
# =============================================================================
set -u

INTERVAL="${1:-3}"

echo "🐳 [JARVIS] Surveillance Docker Swarm & Conteneurs (rafraîchissement ${INTERVAL}s)..."

while true; do
    clear 2>/dev/null || true
    echo "====================================================================="
    echo "🐳 SWARM & CONTAINER SUPERVISOR — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "====================================================================="
    echo
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        echo "--- Nœuds & Stacks Swarm ---"
        docker node ls 2>/dev/null || echo "Mode Swarm inactif (Docker standalone)"
        echo
        echo "--- Conteneurs Actifs ---"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null
    else
        echo "Docker démon non disponible sur cette machine locale."
        echo "Sonde des services locaux (Ports Swarm standards) :"
        for svc in "Postgres:5432" "Redis:6379" "n8n:5678" "Portainer:9000" "Ollama:11434" "CDP:9222" "Cockpit:8600"; do
            nom="${svc%%:*}"; port="${svc##*:}"
            if timeout 1 bash -c "</dev/tcp/127.0.0.1/$port" 2>/dev/null; then
                printf "  %-12s [Port %5s] : \033[32mEN LIGNE\033[0m\n" "$nom" "$port"
            else
                printf "  %-12s [Port %5s] : \033[31mHORS LIGNE\033[0m\n" "$nom" "$port"
            fi
        done
    fi

    if [ "${1:-}" = "--once" ] || [ "${2:-}" = "--once" ]; then
        break
    fi
    sleep "$INTERVAL"
done
