#!/usr/bin/env bash
# État RÉEL de la vectorisation — source de vérité : board.db, colonne chunks.embedding.
B="$HOME/jarvis/board/board.db"; LOG="$HOME/jarvis/logs/vectorisation.log"
echo "🧬 VECTORISATION — $(date '+%Y-%m-%d %H:%M:%S')"; echo
echo "── BIBLIOTHÈQUE VIVANTE (board.db) ──"
timeout 120 sqlite3 -header -column "$B" "
SELECT COALESCE(NULLIF(embedding_model,''),'(aucun)') AS modele,
       COUNT(*) AS chunks,
       SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) AS sans_vecteur
FROM chunks GROUP BY 1 ORDER BY chunks DESC;" 2>/dev/null | sed 's/^/   /'
echo
CIBLE="nomic-v1.5-prefixe"
tot=$(timeout 60 sqlite3 "$B" "SELECT COUNT(*) FROM chunks;" 2>/dev/null)
ok=$(timeout 60 sqlite3 "$B" "SELECT COUNT(*) FROM chunks WHERE embedding_model='$CIBLE';" 2>/dev/null)
if [ "${tot:-0}" -gt 0 ]; then
  pct=$(( ${ok:-0} * 100 / tot ))
  echo "   Homogénéisation vers « $CIBLE » : ${ok:-0} / $tot  (${pct}%)"
  printf "   ["; for i in $(seq 1 50); do [ $((i*2)) -le $pct ] && printf "█" || printf "·"; done; printf "]\n"
fi
echo
echo "── moteurs d'embeddings ──"
# Débit RÉEL, relu du journal — jamais un chiffre de bench de labo.
DEB=$(grep -oP '\d+\.\d+(?= emb/s)' "$LOG" 2>/dev/null | tail -1)
if curl -s -m 3 http://10.42.0.230:1234/api/v0/models >/dev/null 2>&1; then
  echo "   M6 LM Studio :1234 ✅ nomic-v1.5 768 dims${DEB:+ · débit réel ${DEB} emb/s}"
  GU=$(timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=4 m6 \
      'nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits' 2>/dev/null | paste -sd'/')
  [ -n "$GU" ] && echo "      GPU M6 : ${GU} %  $([ "${GU%%/*}" -lt 10 ] 2>/dev/null && echo '⚠ calcul sur CPU, pas sur GPU')"
else
  echo "   M6 LM Studio :1234 ✖"
fi
curl -s -m 3 http://10.42.0.230:11434/api/tags >/dev/null 2>&1 \
  && echo "   M6 Ollama :11434  ✅" || echo "   M6 Ollama :11434  ✖"
curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
  && echo "   M4 Ollama :11434  ✅ (réservé — M4 en tension mémoire)" || echo "   M4 Ollama :11434  ✖"
echo
VERROU="$HOME/jarvis/logs/.moisson-vecto.lock"
if [ -f "$VERROU" ] && kill -0 "$(cat "$VERROU" 2>/dev/null)" 2>/dev/null; then
  echo "   ▶ MOISSON EN COURS (pid $(cat "$VERROU"))"
else
  echo "   ⏸ moisson à l'arrêt — lancer : ~/jarvis/bin/moisson-vecto"
fi
if [ -f "$LOG" ]; then echo; echo "── journal ──"; tail -8 "$LOG" | sed 's/^/   /'; fi
exit 0
