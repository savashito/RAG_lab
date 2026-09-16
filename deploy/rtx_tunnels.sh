#!/usr/bin/env bash
# rtx_tunnels.sh — corre EN el rtx5090. Publica los servicios GPU hacia el host de
# la app (tlacua-hstgr) con túneles REVERSE (-R) autossh, uno por servicio para
# aislar fallas. Reemplaza al viejo `rtxtun` (forwards -L) que corría en hstgr.
#
#   servicio            rtx5090 (local)      →   tlacua-hstgr (remoto)
#   embedder TEI        localhost:8085           127.0.0.1:8085
#   reranker TEI        localhost:8086           127.0.0.1:8086
#   llama.cpp           localhost:<detectado>    127.0.0.1:1237
#
# El puerto de llama-server cambia en cada relanzamiento, así que se autodetecta.
# El lado REMOTO (lo que la app consume) queda FIJO: 8085 / 8086 / 1237.
#
# ⚠️ CUTOVER: antes de correr esto, MATA el rtxtun en hstgr, o el bind de 8085
#    (que rtxtun ya tiene tomado allá) hará fallar el -R 8085. En hstgr:
#       tmux kill-session -t rtxtun
#
# Uso:   ./rtx_tunnels.sh            # arranca los 3 (si ya hay, no duplica)
#        ./rtx_tunnels.sh stop       # los baja
set -euo pipefail

REMOTE="${REMOTE:-tlacua-hstgr}"     # alias SSH del host de la app (en ~/.ssh/config de la RTX)
AUTOSSH="${AUTOSSH:-/usr/lib/autossh/autossh}"
export AUTOSSH_GATETIME=0            # que autossh reintente aunque la 1a conexión caiga rápido
SSH_OPTS=(-M 0 -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3)

detect_llama_port() {
  local p port
  p=$(pgrep -f 'llama-server' | head -1 || true)
  [[ -n "$p" ]] && port=$(tr '\0' '\n' < "/proc/$p/cmdline" 2>/dev/null | grep -A1 '^--port$' | tail -1)
  [[ "${port:-}" =~ ^[0-9]+$ ]] && echo "$port" || echo 1237
}

start_one() {  # <etiqueta> <remote_port> <local_port>
  local tag=$1 rport=$2 lport=$3
  if pgrep -f "autossh.*-R ${rport}:localhost" >/dev/null 2>&1; then
    echo "· $tag ya corriendo (-R ${rport}) — omito"
    return
  fi
  echo "· $tag: rtx:${lport} → ${REMOTE}:${rport}"
  "$AUTOSSH" "${SSH_OPTS[@]}" -R "${rport}:localhost:${lport}" "$REMOTE" &
}

if [[ "${1:-}" == "stop" ]]; then
  pkill -f "autossh.*-R (8085|8086|1237):localhost" && echo "túneles detenidos" || echo "no había túneles"
  exit 0
fi

LLAMA_PORT=$(detect_llama_port)
echo "Publicando servicios GPU → ${REMOTE} (llama detectado en :${LLAMA_PORT})"
start_one "embedder" 8085 8085
start_one "reranker" 8086 8086
start_one "llama"    1237 "$LLAMA_PORT"
echo "Listo. Verifica en ${REMOTE}:  curl -s localhost:8085/info >/dev/null && echo embed-ok"
