#!/usr/bin/env bash
# Toutes les sessions tmux vivantes — bascule d'un panneau à l'autre.
while :; do
  clear
  echo "╔══════════════════════════════════════════════════════════════════════╗"
  echo "║   🪟  COCKPIT JARVIS — TOUTES LES SESSIONS TMUX                       ║"
  echo "╚══════════════════════════════════════════════════════════════════════╝"; echo
  mapfile -t S < <(tmux ls -F '#{session_name}' 2>/dev/null)
  for i in "${!S[@]}"; do
    s="${S[$i]}"
    nw=$(tmux list-windows -t "=$s" 2>/dev/null | wc -l)
    printf "  %2d  %-18s %2d fenêtres\n" "$((i+1))" "$s" "$nw"
    tmux list-windows -t "=$s" -F '        #{window_index} #{window_name} (#{pane_current_command})' 2>/dev/null
    echo
  done
  echo "  [numéro]=basculer   t=tout ouvrir (hubs manquants)   r=rafraîchir   q=quitter"
  read -rp "  > " rep
  case "$rep" in
    q|Q) break ;;
    r|R) continue ;;
    t|T) bash "$HOME/jarvis/cockpit/tmux-tout-ouvrir.sh"; read -rp "  [entrée]" ;;
    ''|*[!0-9]*) continue ;;
    *) idx=$((rep-1)); [ "$idx" -ge 0 ] && [ "$idx" -lt "${#S[@]}" ] && tmux switch-client -t "=${S[$idx]}" ;;
  esac
done
