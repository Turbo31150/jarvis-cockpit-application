#!/usr/bin/env bash
# ==============================================================================
# JARVIS WEB COCKPIT — LAUNCHER PORT 8600
# ==============================================================================

if ! ss -tulpn | grep -q ":8600 "; then
    systemctl --user start jarvis-cockpit.service 2>/dev/null || {
        nohup /home/turbo/jarvis/.venv/bin/python /home/turbo/jarvis/cockpit/serveur.py > /home/turbo/jarvis/logs/cockpit_serveur.log 2>&1 &
    }
    sleep 1
fi

if command -v google-chrome >/dev/null 2>&1; then
    google-chrome --app="http://127.0.0.1:8600" &
elif command -v google-chrome-stable >/dev/null 2>&1; then
    google-chrome-stable --app="http://127.0.0.1:8600" &
else
    xdg-open "http://127.0.0.1:8600" &
fi
