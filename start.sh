#!/bin/bash
# Startup - Railway
set -e

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERRO: DEEPSEEK_API_KEY nao definida. Configure no Railway."
    exit 1
fi

export CHAINLIT_AUTH_SECRET=*** -n "$DEEPSEEK_API_KEY" | sha256sum | cut -d' ' -f1)
export DATA_DIR="${DATA_DIR:-/data}"

# Garante que o diretorio de dados existe e tem permissao
mkdir -p "$DATA_DIR"
chmod 777 "$DATA_DIR" 2>/dev/null || true

echo "DATA_DIR=$DATA_DIR"
echo "Iniciando Chainlit..."
exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
