#!/usr/bin/env bash
# Ouvre les hubs tmux connus qui ne tournent pas encore.
declare -A HUBS=(
  ["jarvis-cluster"]="$HOME/Bureau/OUVRIR_JARVIS_TMUX_HUB.sh"
  ["jarvis"]="$HOME/jarvis/scripts/cockpit-tmux.sh"
)
for s in "${!HUBS[@]}"; do
  script="${HUBS[$s]}"
  if tmux has-session -t "=$s" 2>/dev/null; then
    echo "   ✅ $s — déjà ouvert"
  elif [ -x "$script" ] || [ -f "$script" ]; then
    echo "   ▶ $s — ouverture via $(basename "$script")"
    ( setsid bash "$script" </dev/null >/dev/null 2>&1 & )
    sleep 2
    tmux has-session -t "=$s" 2>/dev/null && echo "      ✅ ouvert" || echo "      ✖ échec"
  else
    echo "   ✖ $s — script introuvable ($script)"
  fi
done
echo
echo "   Sessions vivantes : $(tmux ls -F '#{session_name}' 2>/dev/null | tr '\n' ' ')"
