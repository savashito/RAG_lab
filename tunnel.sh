#!/usr/bin/env bash
# Opens the SSH tunnels the labs need, and keeps them open until you Ctrl-C:
#
#   localhost:5433  ->  srv1312754:5432   Postgres + pgvector  (tlacua-hstgr)
#   localhost:8085  ->  rtx5090:8085      TEI embedding service (GPU)
#
# Local ports (5433/8085) avoid clashing with anything on your laptop.
# Run this in its own terminal:  ./tunnel.sh
set -euo pipefail

# El puerto del llama-server cambia en cada relanzamiento, así que se autodetecta
# leyendo el --port del proceso en el server. Si la detección falla, usa el último
# conocido (fallback) para no tumbar el resto de túneles.
LLAMA_PORT=$(ssh -o ConnectTimeout=8 rtx5090 'p=$(pgrep -f llama-server | head -1); tr "\0" "\n" < /proc/$p/cmdline | grep -A1 "^--port$" | tail -1' 2>/dev/null || true)
[[ "$LLAMA_PORT" =~ ^[0-9]+$ ]] || LLAMA_PORT=58387

echo "Tunnels (Ctrl-C to close both):"
echo "  localhost:5433 -> srv1312754:5432   Postgres/pgvector"
echo "  localhost:8085 -> rtx5090:8085      TEI embeddings (GPU)"
echo "  localhost:41499 -> rtx5090:$LLAMA_PORT      llama.cpp server (GPU, puerto autodetectado)"

ssh -N -o ServerAliveInterval=20 -L 5433:localhost:5432 tlacua-hstgr &
PG=$!
ssh -N -o ServerAliveInterval=20 -L 8085:localhost:8085 rtx5090 &
TEI=$!
ssh -N -o ServerAliveInterval=20 -L 41499:localhost:$LLAMA_PORT rtx5090 &
LLAMA=$!
trap 'kill $PG $TEI $LLAMA 2>/dev/null' INT TERM EXIT
wait
