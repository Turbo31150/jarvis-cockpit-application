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
echo "── Moteurs d'embeddings GPU locaux ──"
if curl -s -m 1 http://127.0.0.1:11436/api/tags | grep -q "nomic-embed-text"; then
  echo "   GTX 1660S (:11436) ✅ nomic-embed-text 768 dims (GPU 0 permanent, résident)"
else
  echo "   GTX 1660S (:11436) ✖ hors-ligne"
fi
ACT_DB="$HOME/jarvis/data/jarvis_action_memory.db"
if [ -f "$ACT_DB" ]; then
  N_ACT=$(sqlite3 "$ACT_DB" "SELECT COUNT(*) FROM action_memory;" 2>/dev/null || echo "0")
  N_VEC=$(sqlite3 "$ACT_DB" "SELECT COUNT(*) FROM action_memory WHERE vectorized=1;" 2>/dev/null || echo "0")
  echo "   Mémoire Action GPU : $N_VEC / $N_ACT actions vectorisées (768D instantané)"
fi

echo
echo "── Moteurs distants / cluster ──"
if curl -s -m 0.5 http://10.42.0.230:1234/api/v0/models >/dev/null 2>&1; then
  echo "   M6 LM Studio :1234 ✅ nomic-v1.5 768 dims"
else
  echo "   M6 LM Studio :1234 ✖ (hors-ligne / cluster local prioritaire)"
fi
echo
VERROU="$HOME/jarvis/logs/.moisson-vecto.lock"
if [ -f "$VERROU" ] && kill -0 "$(cat "$VERROU" 2>/dev/null)" 2>/dev/null; then
  echo "   ▶ MOISSON EN COURS (pid $(cat "$VERROU"))"
else
  echo "   ⏸ moisson à l'arrêt — lancer : ~/jarvis/bin/moisson-vecto"
fi
if [ -f "$LOG" ]; then echo; echo "── journal ──"; tail -8 "$LOG" | sed 's/^/   /'; fi
exit 0
