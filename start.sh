#!/bin/bash
# Startup script para Railway
set -e

if [ -z "$CHAINLIT_AUTH_SECRET" ]; then
    echo "ERRO: CHAINLIT_AUTH_SECRET nao definida"
    exit 1
fi

# Gera .env a partir das variaveis de ambiente
echo "DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY" > .env
echo "CHAINLIT_AUTH_SECRET=$CHAINLIT_AUTH_SECRET" >> .env
if [ -n "$DATA_DIR" ]; then
    echo "DATA_DIR=$DATA_DIR" >> .env
fi
echo ".env gerado"

exec chainlit run app.py --port "${PORT:-8000}" --host 0.0.0.0
