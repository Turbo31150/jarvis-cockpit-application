#!/usr/bin/env bash
# Menu de lancement des 100 outils du Bureau — panneau APPS du cockpit.
set -uo pipefail
INV="$HOME/jarvis/cockpit/apps-inventaire.sh"
PAGE=0

lancer() {
  local chemin="$1" cmd="$2" nom="$3"
  echo "▶ $nom"
  case "$chemin" in
    *.desktop) setsid gio launch "$chemin" >/dev/null 2>&1 & ;;
    *)         setsid bash -c "$cmd" >/dev/null 2>&1 & ;;
  esac
  echo "  lancé (pid $!)"
}

while :; do
  clear
  echo "╔══════════════════════════════════════════════════════════════════════╗"
  echo "║   🚀 COCKPIT JARVIS — APPLICATIONS DU BUREAU                         ║"
  echo "╚══════════════════════════════════════════════════════════════════════╝"
  mapfile -t L < <("$INV")
  echo "   ${#L[@]} outils inventoriés"; echo
  # pagination : sinon les 101 outils débordent de l'écran
  LIG=$(( $(tput lines 2>/dev/null || echo 40) - 10 ))
  [ "$LIG" -lt 10 ] && LIG=10
  deb=$(( PAGE * LIG )); fin=$(( deb + LIG ))
  [ "$fin" -gt "${#L[@]}" ] && fin=${#L[@]}
  cat_prec=""
  for (( i=deb; i<fin; i++ )); do
    IFS=$'\t' read -r cat nom chemin cmd <<< "${L[$i]}"
    [ "$cat" != "$cat_prec" ] && { echo "── $cat ──"; cat_prec="$cat"; }
    printf "  %3d  %s\n" "$((i+1))" "$nom"
  done
  npages=$(( (${#L[@]} + LIG - 1) / LIG ))
  echo
  echo "  page $((PAGE+1))/$npages — [numéro]=lancer  n=suivante  p=précédente  /=chercher  q=quitter"
  read -rp "  > " rep
  case "$rep" in
    q|Q) break ;;
    n|N) PAGE=$(( PAGE + 1 )); [ "$PAGE" -ge "$npages" ] && PAGE=0; continue ;;
    p|P) PAGE=$(( PAGE - 1 )); [ "$PAGE" -lt 0 ] && PAGE=$(( npages - 1 )); continue ;;
    /*) motif="${rep#/}"; clear; echo "── résultats pour « $motif » ──"
        for i in "${!L[@]}"; do
          IFS=$'\t' read -r c n ch cm <<< "${L[$i]}"
          case "${n,,}" in *"${motif,,}"*) printf "  %3d  %-40s [%s]\n" "$((i+1))" "$n" "$c";; esac
        done; read -rp "  [entrée]"; continue ;;
    r|R) continue ;;
    ''|*[!0-9]*) continue ;;
    *)
      idx=$((rep-1))
      [ "$idx" -ge 0 ] && [ "$idx" -lt "${#L[@]}" ] || continue
      IFS=$'\t' read -r cat nom chemin cmd <<< "${L[$idx]}"
      lancer "$chemin" "$cmd" "$nom"; sleep 1.5 ;;
  esac
done
