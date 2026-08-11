#!/bin/bash
set -e

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERRO: DEEPSEEK_API_KEY nao definida. Configure no Railway."
    exit 1
fi

# Usa DATA_DIR se definido, senao ./data (funciona sem volume)
export DATA_DIR="${DATA_DIR:-./data}"
mkdir -p "$DATA_DIR"

echo "DATA_DIR=$DATA_DIR"
echo "Iniciando Chainlit..."
exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
