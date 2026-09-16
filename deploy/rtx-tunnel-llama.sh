#!/usr/bin/env bash
# rtx-tunnel-llama.sh — wrapper para el unit tunnel-llama.service. Autodetecta el
# puerto de llama-server (cambia en cada relanzamiento) y abre el reverse tunnel con
# el lado remoto FIJO en 1237 (lo que la app espera). `exec` para que systemd
# supervise directamente al autossh.
set -euo pipefail
REMOTE="${REMOTE:-tlacua-hstgr}"
AUTOSSH="${AUTOSSH:-/usr/lib/autossh/autossh}"
export AUTOSSH_GATETIME=0

p=$(pgrep -f 'llama-server' | head -1 || true)
[[ -n "$p" ]] && PORT=$(tr '\0' '\n' < "/proc/$p/cmdline" 2>/dev/null | grep -A1 '^--port$' | tail -1)
[[ "${PORT:-}" =~ ^[0-9]+$ ]] || PORT=1237

echo "llama-server detectado en :${PORT} → ${REMOTE}:1237"
exec "$AUTOSSH" -M 0 -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -R "1237:localhost:${PORT}" "$REMOTE"
