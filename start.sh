#!/bin/bash
# Startup - Railway
set -e

# Deriva CHAINLIT_AUTH_SECRET do DEEPSEEK_API_KEY (hash deterministico)
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERRO: DEEPSEEK_API_KEY nao definida. Configure no Railway."
    exit 1
fi

export CHAINLIT_AUTH_SECRET=*** "$DEEPSEEK_API_KEY" | sha256sum | cut -d' ' -f1)
export DATA_DIR="${DATA_DIR:-/data}"

echo "Iniciando Chainlit..."
exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
