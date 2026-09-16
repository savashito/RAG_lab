#!/usr/bin/env bash
# serve_reranker.sh [hf-model-id] — (re)start a TEI RERANKER (cross-encoder) on
# rtx5090:8086, en paralelo al embedder de :8085 (contenedor aparte, tei-rerank).
# El modelo se descarga EN EL SERVIDOR. Necesita tu sudo en rtx5090 (ssh -t).
#
#   ./serve_reranker.sh                       # default: BAAI/bge-reranker-v2-m3 (multilingüe, ES)
#   ./serve_reranker.sh BAAI/bge-reranker-base
#
# TEI expone /rerank en este puerto. Tras levantarlo, abre el túnel de 8086 (ya
# incluido en tunnel.sh) y pon RERANK_URL=http://127.0.0.1:8086 en el .env de la app.
set -euo pipefail
MODEL="${1:-BAAI/bge-reranker-v2-m3}"

echo "Serving RERANKER '$MODEL' on rtx5090:8086 (downloads on the server)..."
ssh -t rtx5090 "sudo docker rm -f tei-rerank 2>/dev/null; sudo docker run -d --name tei-rerank \
  --restart unless-stopped --gpus all -p 127.0.0.1:8086:80 -v /home/ai-server/tei-data:/data \
  ghcr.io/huggingface/text-embeddings-inference:120-1.9 --model-id $MODEL"

echo "Started. Readiness (con el túnel :8086 arriba):  curl -s localhost:8086/info | python3 -m json.tool"
echo "Prueba /rerank:  curl -s localhost:8086/rerank -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\":\"estupro\",\"texts\":[\"copula con menor mediante engano\",\"robo de vehiculo\"]}'"
