#!/usr/bin/env bash
# Opens the SSH tunnels the labs need, and keeps them open until you Ctrl-C:
#
#   localhost:5433  ->  srv1312754:5432   Postgres + pgvector  (tlacua-hstgr)
#   localhost:8085  ->  rtx5090:8085      TEI embedding service (GPU)
#
# Local ports (5433/8085) avoid clashing with anything on your laptop.
# Run this in its own terminal:  ./tunnel.sh
set -euo pipefail

echo "Tunnels (Ctrl-C to close both):"
echo "  localhost:5433 -> srv1312754:5432   Postgres/pgvector"
echo "  localhost:8085 -> rtx5090:8085      TEI embeddings (GPU)"

ssh -N -o ServerAliveInterval=20 -L 5433:localhost:5432 tlacua-hstgr &
PG=$!
ssh -N -o ServerAliveInterval=20 -L 8085:localhost:8085 rtx5090 &
TEI=$!
trap 'kill $PG $TEI 2>/dev/null' INT TERM EXIT
wait
