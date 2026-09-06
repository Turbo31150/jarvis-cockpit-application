#!/usr/bin/env bash
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
    elif [ -f "$HOME/.Xauthority" ]; then
        export XAUTHORITY="$HOME/.Xauthority"
    fi
fi

export QT_QPA_PLATFORM="xcb"
exec /home/turbo/jarvis/bin/jarvis-cockpit-app "$@"
