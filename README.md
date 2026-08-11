# Diagnóstico Empreendedor

Chat de diagnóstico para empreendedores em estágio inicial. Um facilitador com IA conduz uma conversa para entender a ideia de negócio a fundo e gera um relatório estruturado com VPC, JTBD, jornada do consumidor e dados para Lean Canvas.

**Stack:** Chainlit (UI) + DeepSeek (LLM) + SQLite (auth/persistência)

---

## Funcionalidades

- Chat livre com facilitador cético (sem bajulação, sem superlativos vazios)
- Relatório estruturado ao digitar `/encerrar`
- Autenticação por email/senha
- Histórico de conversas persistido (retomar de onde parou)
- Rate limiting e sanitização de input

## Rodar localmente

```bash
# 1. Clone
git clone https://github.com/JeffersonMagalhaes/diagnostico-empreendedor.git
cd diagnostico-empreendedor

# 2. Venv + dependências
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configurar .env
cp .env.example .env
# Preencha DEEPSEEK_API_KEY e gere CHAINLIT_AUTH_SECRET:
chainlit create-secret >> .env

# 4. Para dev local, crie um usuário inicial:
echo "CREATE_DEFAULT_USER=true" >> .env
# Login: admin@teste.com / admin123

# 5. Rodar
chainlit run app.py
```

Acesse http://localhost:8000

## Deploy (Railway)

1. Conecte o repo no Railway
2. Adicione um **Volume** em `/data` (para persistir SQLite)
3. Configure as variáveis de ambiente:

| Variável | Descrição |
|---|---|
| `DEEPSEEK_API_KEY` | Chave da API DeepSeek |
| `CHAINLIT_AUTH_SECRET` | Segredo JWT (gere com `chainlit create-secret`) |
| `DATA_DIR` | `/data` |
| `PORT` | `8000` |

**⚠️ Não defina `CREATE_DEFAULT_USER` em produção.** Registre o primeiro usuário pelo formulário de login do Chainlit.

## Arquitetura

```
chat-app/
├── app.py              # Entrypoint Chainlit (auth, sessão, comandos)
├── chainlit.md          # Tela de boas-vindas
├── agent/
│   ├── prompts.py       # System prompt do facilitador
│   ├── engine.py        # Motor de conversa (DeepSeek API)
│   ├── state.py         # Estado da sessão (SQLite)
│   ├── report.py        # Geração de relatório
│   ├── data_layer.py    # Persistência de threads Chainlit
│   └── security.py      # Rate limiting e sanitização
├── auth/
│   └── users.py         # Autenticação SQLite
└── .chainlit/
    └── config.toml      # Configuração Chainlit
```

## Licença

MIT
