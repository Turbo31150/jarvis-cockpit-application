#!/usr/bin/env bash
# Santé du cluster : M4 local, M6 (4 GPU), backends, organes.
echo "🖥  CLUSTER — $(date '+%H:%M:%S')"; echo
echo "── $(hostname | tr '[:lower:]' '[:upper:]') (local) ──"
awk '/MemTotal|MemAvailable/{printf "   %-14s %6.1f Go\n",$1,$2/1048576}' /proc/meminfo
printf "   charge        %s\n" "$(cut -d' ' -f1-3 /proc/loadavg)"
printf "   zram          %s\n" "$(awk '/zram0/{printf "%d%% de %.1f Go", ($4/$3)*100, $3/1048576}' /proc/swaps 2>/dev/null || echo n/a)"
t=$(sensors 2>/dev/null | grep -m1 -oP 'Package id 0:\s+\+\K[0-9.]+'); [ -n "$t" ] && echo "   CPU           ${t} °C"
nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | sed 's/^/   GPU /'
echo
echo "── M6 (tour, 4 GPU · 10.42.0.230) ──"
timeout 3 ssh -o BatchMode=yes -o ConnectTimeout=2 m6 \
  'nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader' 2>/dev/null \
  | sed 's/^/   GPU /' || echo "   ✖ injoignable en SSH"
echo
echo "── organes ──"
for o in "proxy 127.0.0.1:18800" "cockpit-pwa 127.0.0.1:8600" "openclaw 127.0.0.1:18789" \
         "ollama-local 127.0.0.1:11434" "cdp 127.0.0.1:9108" "lms-M6 10.42.0.230:1234" \
         "ollama-M6 10.42.0.230:11434"; do
  set -- $o; h=${2%%:*}; p=${2##*:}
  timeout 1 bash -c "</dev/tcp/$h/$p" 2>/dev/null && echo "   $1 ✅" || echo "   $1 ✖"
done
