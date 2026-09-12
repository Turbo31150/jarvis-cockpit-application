#!/usr/bin/env bash
# ==============================================================================
# JARVIS OS COCKPIT — POSTE DE COMMANDE UNIFIÉ (PC & MOBILE S9)
# ==============================================================================
set -e

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

if [ -z "$DISPLAY" ]; then
    if [ -e "/tmp/.X11-unix/X1" ]; then
        export DISPLAY=":1"
    elif [ -e "/tmp/.X11-unix/X0" ]; then
        export DISPLAY=":0"
    else
        export DISPLAY=":1"
    fi
fi

if [ -z "$XAUTHORITY" ]; then
    if [ -f "$XDG_RUNTIME_DIR/gdm/Xauthority" ]; then
        export XAUTHORITY="$XDG_RUNTIME_DIR/gdm/Xauthority"
    elif [ -f "/run/user/1000/gdm/Xauthority" ]; then
        export XAUTHORITY="/run/user/1000/gdm/Xauthority"
    elif [ -f "$HOME/.Xauthority" ]; then
        export XAUTHORITY="$HOME/.Xauthority"
    fi
fi

# 1. Vérification et démarrage du serveur de bord Port 8600 si inactif
if ! curl -s -m 1 http://127.0.0.1:8600/api/status >/dev/null 2>&1; then
    systemctl --user start jarvis-cockpit.service 2>/dev/null || {
        nohup /home/turbo/jarvis/.venv/bin/python /home/turbo/jarvis/cockpit/serveur.py > /home/turbo/jarvis/logs/cockpit_serveur.log 2>&1 &
    }
    for i in {1..15}; do
        if curl -s -m 1 http://127.0.0.1:8600/api/status >/dev/null 2>&1; then
            break
        fi
        sleep 0.2
    done
fi

# 2. Mode natif PyQt6 si demandé explicitement (--native ou --qt)
for arg in "$@"; do
    if [ "$arg" = "--qt" ] || [ "$arg" = "--native" ]; then
        export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
        if [ -x "$HOME/jarvis/.venv/bin/python" ]; then
            exec "$HOME/jarvis/.venv/bin/python" "/home/turbo/jarvis/cockpit/gui_app.py" "$@"
        else
            exec python3 "/home/turbo/jarvis/cockpit/gui_app.py" "$@"
        fi
    fi
done

# 3. Lancement par défaut : Application Cyber-Deck identique au Galaxy S9 en Standalone App
CHROME_BIN=""
if command -v google-chrome >/dev/null 2>&1; then
    CHROME_BIN="google-chrome"
elif command -v google-chrome-stable >/dev/null 2>&1; then
    CHROME_BIN="google-chrome-stable"
elif command -v chromium-browser >/dev/null 2>&1; then
    CHROME_BIN="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
    CHROME_BIN="chromium"
fi

if [ -n "$CHROME_BIN" ]; then
    exec "$CHROME_BIN" \
        --app="http://127.0.0.1:8600" \
        --class="jarvis-cockpit-os" \
        --name="JARVIS OS" \
        --window-size=1680,1050 \
        --user-data-dir="$HOME/.config/jarvis-cockpit-chrome" \
        --renderer-process-limit=2 \
        --js-flags="--max-old-space-size=256" \
        --disable-features=Translate,OptimizationHints,MediaRouter,CalculateNativeWinOcclusion,InterestFeedContentSuggestions \
        --enable-features=OverlayScrollbar \
        --disable-background-timer-throttling=false \
        --disable-renderer-backgrounding=false \
        --enable-gpu-rasterization \
        --ignore-gpu-blocklist \
        --enable-zero-copy \
        --no-first-run \
        --no-default-browser-check \
        "$@"
else
    # Repli PyQt6 si aucun navigateur disponible
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
    if [ -x "$HOME/jarvis/.venv/bin/python" ]; then
        exec "$HOME/jarvis/.venv/bin/python" "/home/turbo/jarvis/cockpit/gui_app.py" "$@"
    else
        exec python3 "/home/turbo/jarvis/cockpit/gui_app.py" "$@"
    fi
fi
