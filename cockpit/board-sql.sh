#!/usr/bin/env bash
# Panneau BOARD-SQL — lit TOUTES les bases SQL du poste, d'un coup d'œil.
set -uo pipefail
CACHE="$HOME/jarvis/cockpit/.sql-cache.tsv"

bases() {
  # bases VIVANTES uniquement : les backups/archives sont du bruit dans un cockpit
  find "$HOME/jarvis" -maxdepth 3 -name '*.db' -size +1k 2>/dev/null \
    | grep -vE '/(backups?|archive|old|corbeille)/' | sort -u
}

scan() {
  : > "$CACHE"
  while read -r db; do
    nt=$(timeout 5 sqlite3 "$db" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "?")
    [ "$nt" = "0" ] && continue
    sz=$(du -h "$db" 2>/dev/null | cut -f1)
    printf '%s\t%s\t%s\n' "$db" "$sz" "$nt" >> "$CACHE"
  done < <(bases)
}

apercu() {
  clear
  echo "╔══════════════════════════════════════════════════════════════════════╗"
  echo "║   🗄  COCKPIT JARVIS — BOARD & TOUTES LES BASES SQL                   ║"
  echo "╚══════════════════════════════════════════════════════════════════════╝"
  echo "   scan : $(date '+%Y-%m-%d %H:%M:%S')"
  echo
  echo "── BIBLIOTHÈQUE VIVANTE (board.db) ──"
  B="$HOME/jarvis/board/board.db"
  printf "   chunks   : %s\n" "$(timeout 10 sqlite3 "$B" 'SELECT COUNT(*) FROM chunks;' 2>/dev/null || echo '?')"
  printf "   sources  : %s\n" "$(timeout 10 sqlite3 "$B" 'SELECT COUNT(*) FROM sources;' 2>/dev/null || echo '?')"
  printf "   domaines : %s\n" "$(timeout 10 sqlite3 "$B" 'SELECT COUNT(*) FROM domains;' 2>/dev/null || echo '?')"
  printf "   experts  : %s\n" "$(timeout 10 sqlite3 "$B" 'SELECT COUNT(*) FROM experts;' 2>/dev/null || echo '?')"
  V="$HOME/jarvis/data/jarvis_vector_store.db"
  printf "   vecteurs : %s (sur %s fichiers indexés)\n" \
    "$(timeout 10 sqlite3 "$V" 'SELECT COUNT(*) FROM document_vectors;' 2>/dev/null || echo '?')" \
    "$(timeout 10 sqlite3 "$V" 'SELECT COUNT(*) FROM indexed_files;' 2>/dev/null || echo '?')"
  echo
  echo "── TOUTES LES BASES ──"
  [ -s "$CACHE" ] || scan
  sort -t$'\t' -k3,3nr "$CACHE" \
    | awk -F'\t' '{printf "   %-50s %7s %4s tbl\n", substr($1, length(ENVIRON["HOME"])+2), $2, $3}' | head -22
  echo
  echo "   total : $(wc -l < "$CACHE") bases"
  echo
  echo "  [s]=rescan  [t <base>]=tables  [q <base> <SQL>]=requête  [Q]=quitter"
}

while :; do
  apercu
  read -rp "  > " -a rep
  case "${rep[0]:-}" in
    Q) break ;;
    s) scan ;;
    t) d=$(grep -m1 "${rep[1]:-zzz}" "$CACHE" | cut -f1)
       [ -n "$d" ] && { clear; echo "== $d =="; sqlite3 "$d" ".tables" 2>&1 | head -40; read -rp "  [entrée]"; } ;;
    q) d=$(grep -m1 "${rep[1]:-zzz}" "$CACHE" | cut -f1)
       [ -n "$d" ] && { clear; echo "== $d =="; timeout 60 sqlite3 -header -column "$d" "${rep[*]:2}" 2>&1 | head -50; read -rp "  [entrée]"; } ;;
    *) sleep 1 ;;
  esac
done
