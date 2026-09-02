#!/usr/bin/env bash
# serve.sh <hf-model-id> — (re)start the TEI embedding service on rtx5090
# serving the given model. The model downloads ON THE SERVER (not your laptop).
#
#   ./serve.sh BAAI/bge-small-en-v1.5
#   ./serve.sh Qwen/Qwen3-Embedding-0.6B
#
# After it's up, re-ingest any lab (the vector dimension may change).
# Needs your sudo password on rtx5090 (ssh -t provides the terminal for it).
set -euo pipefail
MODEL="${1:?usage: ./serve.sh <hf-model-id>   e.g. ./serve.sh BAAI/bge-m3}"

echo "Serving '$MODEL' on rtx5090:8085 (downloads on the server)..."
ssh -t rtx5090 "sudo docker rm -f tei-embed 2>/dev/null; sudo docker run -d --name tei-embed \
  --restart unless-stopped --gpus all -p 127.0.0.1:8085:80 -v /home/ai-server/tei-data:/data \
  ghcr.io/huggingface/text-embeddings-inference:120-1.9 --model-id $MODEL"

echo "Started. Check readiness (with the :8085 tunnel up):  curl -s localhost:8085/info | python3 -m json.tool"
