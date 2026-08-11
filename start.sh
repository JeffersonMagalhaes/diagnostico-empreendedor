#!/bin/bash
# Startup script para Railway
set -e

echo "=== DEBUG: Environment ==="
echo "HOME=$HOME"
echo "PWD=$PWD"
echo "PORT=$PORT"
echo "CHAINLIT_AUTH_SECRET set: $([ -n "$CHAI...ET" ] && echo SIM || echo NAO)"
echo "DEEPSEEK_API_KEY set: $([ -n "$DEEPS...EY" ] && echo SIM || echo NAO)"
echo "All env vars starting with CHAIN:"
env | grep CHAIN || echo "  (nenhuma)"
echo "All env vars starting with DEEP:"
env | grep DEEP || echo "  (nenhuma)"
echo "=== FIM DEBUG ==="

if [ -z "$CHAINLIT_AUTH_SECRET" ]; then
    echo "ERRO: CHAINLIT_AUTH_SECRET nao definida"
    exit 1
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERRO: DEEPSEEK_API_KEY nao definida"
    exit 1
fi

# Gera .env
echo "DEEPSEEK_API_KEY=$DEEPS...EY" > .env
echo "CHAINLIT_AUTH_SECRET=$CHAIN...ET" >> .env
if [ -n "$DATA_DIR" ]; then
    echo "DATA_DIR=$DATA_DIR" >> .env
fi
echo ".env gerado"

exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
