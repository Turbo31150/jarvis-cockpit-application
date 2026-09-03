#!/usr/bin/env bash
# Panneau VECTORISATION — affiche le dernier état connu tout de suite,
# puis recalcule en fond (les COUNT sur 313k lignes prennent ~40 s).
CK="$HOME/jarvis/cockpit"; SNAP="$CK/.vecto-snapshot.txt"
while :; do
  [ -s "$SNAP" ] && { clear; cat "$SNAP"; } || { clear; echo "🧬 VECTORISATION — premier calcul en cours..."; }
  echo; echo "   (rafraîchi toutes les 60 s · Ctrl-C pour rendre la main)"
  bash "$CK/vecto-calcul.sh" > "$SNAP.tmp" 2>/dev/null && mv "$SNAP.tmp" "$SNAP"
  sleep 60
done
