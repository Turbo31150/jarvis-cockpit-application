#!/usr/bin/env bash
# Inventorie TOUS les outils lançables du Bureau (racine + sous-dossiers).
# Sortie TSV : CATEGORIE \t NOM \t CHEMIN \t COMMANDE
set -uo pipefail
BUREAU="$HOME/Bureau"

nom_de() {  # extrait Name= d'un .desktop, sinon le basename
  local f="$1" n
  n=$(grep -m1 '^Name=' "$f" 2>/dev/null | cut -d= -f2-)
  [ -n "$n" ] || n=$(basename "$f" | sed 's/\.desktop$//;s/\.sh$//')
  printf '%s' "$n"
}
exec_de() {
  local f="$1" e
  e=$(grep -m1 '^Exec=' "$f" 2>/dev/null | cut -d= -f2- | sed 's/ %[fFuUdDnNickvm]//g')
  printf '%s' "$e"
}

while IFS= read -r -d '' f; do
  case "$f" in *"/.backup-lanceurs"*|*"/_RACCOURCIS_INACTIFS/"*) continue;; esac
  rel="${f#$BUREAU/}"
  case "$rel" in */*) cat="${rel%%/*}";; *) cat="BUREAU";; esac
  case "$f" in
    *.desktop) printf '%s\t%s\t%s\t%s\n' "$cat" "$(nom_de "$f")" "$f" "$(exec_de "$f")";;
    *.sh)      printf '%s\t%s\t%s\t%s\n' "$cat" "$(basename "$f" .sh)" "$f" "bash '$f'";;
  esac
done < <(find "$BUREAU" -maxdepth 2 \( -name '*.desktop' -o -name '*.sh' \) -not -name '*.bak-*' -print0 2>/dev/null) | sort -t$'\t' -k1,1 -k2,2
