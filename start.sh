#!/bin/bash
set -e

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERRO: DEEPSEEK_API_KEY nao definida."
    exit 1
fi

echo "DEEPSEEK_API_KEY presente (tamanho: ${#DEEPSEEK_API_KEY} chars)"
echo "Primeiros 8: ${DEEPSEEK_API_KEY:0:8}"
echo "Ultimos 4: ${DEEPSEEK_API_KEY: -4}"

export DATA_DIR="${DATA_DIR:-./data}"
mkdir -p "$DATA_DIR"

echo "Iniciando Chainlit..."
exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
