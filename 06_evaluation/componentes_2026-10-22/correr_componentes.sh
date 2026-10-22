#!/bin/bash
# Espera a que terminen las corridas de «descomponer» (launch_descomponer.py) y corre las pruebas por componente.
while ! grep -q "^FIN" /tmp/descomponer.log 2>/dev/null; do sleep 60; done
cd /tmp && ~/apps/RAG_lab/.venv/bin/python /tmp/prueba_hyde.py > /tmp/prueba_hyde.log 2>&1
~/apps/RAG_lab/.venv/bin/python /tmp/prueba_juez.py > /tmp/prueba_juez.log 2>&1
echo FIN >> /tmp/prueba_juez.log
