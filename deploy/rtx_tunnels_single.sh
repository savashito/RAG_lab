#!/usr/bin/env bash
# rtx_tunnels_single.sh — corre EN el rtx5090. UN solo autossh con los 3 reverse
# tunnels (embedder + reranker + llama) hacia tlacua-hstgr. Más simple que 3
# servicios; el precio es que comparten una conexión.
#
#   servicio       rtx5090 (local)     →  tlacua-hstgr (remoto, lo que usa la app)
#   embedder TEI   localhost:8085         127.0.0.1:8085
#   reranker TEI   localhost:8086         127.0.0.1:8086
#   llama.cpp      localhost:<auto>       127.0.0.1:1237
#
# NOTA: NO usamos ExitOnForwardFailure. En una conexión compartida, ese flag haría
# que si UN bind remoto falla (p. ej. 8086 ocupado) se cayera TODO. Sin él, autossh
# levanta los puertos que pueda y solo avisa de los que fallen (éxito parcial). El
# costo: si un puerto no bindeó, queda silenciosamente sin forward (revísalo abajo).
#
# ⚠️ ANTES de correrlo, libera los puertos en hstgr o los binds fallan:
#   · mata el rtxtun (tiene 8085):     tmux kill-session -t rtxtun   # en hstgr
#   · mata el reverse suelto de llama (tiene 1237):  ver comando al pie / abajo
#
# Uso:  REMOTE=tlacua-hstgr ./rtx_tunnels_single.sh        # arranca
#       ./rtx_tunnels_single.sh stop                        # lo baja
set -euo pipefail

REMOTE="${REMOTE:-tlacua-hstgr}"
AUTOSSH="${AUTOSSH:-/usr/lib/autossh/autossh}"
export AUTOSSH_GATETIME=0            # reintenta aunque la 1a conexión caiga rápido
MATCH="autossh.*-R 8085:localhost:8085"   # marca única de ESTE túnel combinado

if [[ "${1:-}" == "stop" ]]; then
  pkill -f "$MATCH" && echo "túnel combinado detenido" || echo "no había túnel combinado"
  exit 0
fi

# Puerto local de llama-server (cambia en cada relanzamiento); el remoto queda fijo en 1237.
p=$(pgrep -f 'llama-server' | head -1 || true)
[[ -n "$p" ]] && LLAMA=$(tr '\0' '\n' < "/proc/$p/cmdline" 2>/dev/null | grep -A1 '^--port$' | tail -1)
[[ "${LLAMA:-}" =~ ^[0-9]+$ ]] || LLAMA=1237

if pgrep -f "$MATCH" >/dev/null 2>&1; then
  echo "Ya hay un túnel combinado corriendo. Bájalo con: $0 stop"; exit 1
fi

echo "Publicando a ${REMOTE}:  8085→8085 · 8086→8086 · 1237→${LLAMA} (llama)"
exec "$AUTOSSH" -M 0 -N -T \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -R 8085:localhost:8085 \
  -R 8086:localhost:8086 \
  -R "1237:localhost:${LLAMA}" \
  "$REMOTE"
