#!/bin/bash
set -e

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERRO: DEEPSEEK_API_KEY nao definida."
    exit 1
fi

export DATA_DIR="${DATA_DIR:-./data}"
mkdir -p "$DATA_DIR"

exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
