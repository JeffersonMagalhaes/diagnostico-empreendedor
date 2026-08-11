"""
Chainlit app — Diagnóstico Empreendedor.

Entrypoint do chat. Gerencia autenticação, criação/retomada de sessões,
e o loop de conversa com o motor de diagnóstico.
"""

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Carrega .env ANTES de qualquer outro import
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Auto-gera CHAINLIT_AUTH_SECRET se nao definido (Railway)
import hashlib
if not os.environ.get("CHAINLIT_AUTH_SECRET"):
    secret = hashlib.sha256(os.urandom(64)).hexdigest()
    os.environ["CHAINLIT_AUTH_SECRET"] = secret

# Debug: verificar DEEPSEEK_API_KEY
_dsk = os.environ.get("DEEPSEEK_API_KEY", "")
print(f"DEEPSEEK_API_KEY: presente={'SIM' if _dsk else 'NAO'}, tamanho={len(_dsk)}, prefixo={_dsk[:8] if _dsk else 'N/A'}", flush=True)

import chainlit as cl

from auth.users import authenticate_user, register_user, create_first_user_if_needed
from agent.data_layer import SQLiteDataLayer
from agent.engine import run_turn, generate_report
from agent.security import check_rate_limit, validate_message
from agent.state import (
    create_session,
    get_session_by_thread,
    link_thread,
    set_session_title,
    get_session_title,
    load_state,
)

# Data layer: persiste threads no SQLite (sessions.db)
@cl.data_layer
def get_dl():
    return SQLiteDataLayer()


# Garante que existe pelo menos um usuário (MVP)
create_first_user_if_needed()


@cl.password_auth_callback
def auth_callback(email: str, password: str) -> cl.User | None:
    """Autenticação por email/senha. Registra automaticamente novos usuários."""
    user = authenticate_user(email, password)
    if user is not None:
        return cl.User(
            identifier=user["id"],
            metadata={"email": user["email"], "name": user["name"]},
        )

    # Email não existe — registra automaticamente
    if len(password) < 6:
        return None  # Senha muito curta

    ok, msg = register_user(email, password, name=email.split("@")[0])
    if not ok:
        return None

    # Autentica o usuário recém-criado
    user = authenticate_user(email, password)
    if user is None:
        return None

    return cl.User(
        identifier=user["id"],
        metadata={"email": user["email"], "name": user["name"]},
    )


async def _setup_session(thread_id: str | None = None):
    """Configura a sessão: nova ou retomada. Retorna True se for retomada."""
    user = cl.user_session.get("user")
    if user is None:
        await cl.Message(content="Erro: usuário não autenticado.").send()
        return None

    user_id = user.identifier

    if thread_id:
        existing = get_session_by_thread(thread_id)
        if existing:
            # Verifica se o thread pertence ao usuário logado
            from agent.security import verify_session_owner
            if not verify_session_owner(existing, user_id):
                await cl.Message(
                    content="Sessão não encontrada ou acesso negado."
                ).send()
                return None
            cl.user_session.set("session_id", existing)
            cl.user_session.set("user_id", user_id)
            title = get_session_title(existing)
            await cl.Message(
                content=f"**Retomando:** {title}\n\n"
                "Você pode continuar de onde parou. "
                "Digite **/encerrar** a qualquer momento para receber seu relatório parcial."
            ).send()
            return True

    # Nova sessão
    session_id = str(uuid.uuid4())
    create_session(session_id, user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("user_id", user_id)

    if thread_id:
        link_thread(session_id, thread_id)

    await cl.Message(
        content=(
            "Olá! Sou um facilitador de diagnóstico para empreendedores.\n\n"
            "Esta conversa serve para entender a fundo sua ideia de negócio. "
            "Não existe resposta certa ou errada — quanto mais concreto você for, melhor.\n\n"
            "**Me conta: o que você quer construir e para quem?**\n\n"
            "💡 *A qualquer momento, digite* **/encerrar** *para receber seu relatório parcial.*"
        )
    ).send()
    return False


@cl.on_chat_start
async def on_chat_start():
    """Inicializa uma nova sessão de diagnóstico."""
    thread_id = cl.context.session.thread_id
    await _setup_session(thread_id)


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Retoma uma sessão existente."""
    thread_id = thread.get("id") if isinstance(thread, dict) else cl.context.session.thread_id
    await _setup_session(thread_id)


@cl.on_message
async def on_message(msg: cl.Message):
    """Processa cada mensagem do usuário."""
    session_id = cl.user_session.get("session_id")
    user_id = cl.user_session.get("user_id")

    if session_id is None or user_id is None:
        await cl.Message(
            content="Sessão não encontrada. Recarregue a página para iniciar uma nova."
        ).send()
        return

    content = msg.content.strip()

    # Comandos especiais
    if content.lower() in ("/encerrar", "/relatorio", "/report"):
        # Rate limit também para relatórios (cada um chama a API)
        allowed, error = check_rate_limit(user_id)
        if not allowed:
            await cl.Message(content=error).send()
            return
        await _handle_encerrar(session_id, user_id)
        return

    # Valida input
    valid, error = validate_message(content)
    if not valid:
        await cl.Message(content=error).send()
        return

    # Rate limiting
    allowed, error = check_rate_limit(user_id)
    if not allowed:
        await cl.Message(content=error).send()
        return

    # Na primeira mensagem, usa como título da sessão
    state = load_state(session_id)
    if state and not state.get("processo", {}).get("confirmacoes"):
        title = content[:80]
        set_session_title(session_id, title)

    # Envia mensagem placeholder
    msg_obj = cl.Message(content="")
    await msg_obj.send()

    # Processa com o motor de diagnóstico
    try:
        response = run_turn(session_id, user_id, content)
        msg_obj.content = response
        await msg_obj.update()
    except Exception:
        msg_obj.content = "Erro interno. Tente novamente."
        await msg_obj.update()


async def _handle_encerrar(session_id: str, user_id: str):
    """Gera e envia o relatório parcial de diagnóstico."""
    msg = cl.Message(content="Analisando a conversa e gerando seu relatório...")
    await msg.send()

    try:
        relatorio = generate_report(session_id, user_id)
        msg.content = relatorio
        await msg.update()
    except Exception:
        msg.content = "Erro interno ao gerar relatório. Tente novamente."
        await msg.update()


@cl.set_starters
async def set_starters():
    """Sugestões iniciais para o chat (aparecem como botões)."""
    return [
        cl.Starter(
            label="Tenho uma ideia de produto",
            message="Tenho uma ideia de produto digital e quero estruturá-la melhor.",
        ),
        cl.Starter(
            label="Quero validar uma dor de mercado",
            message="Identifiquei um problema que quero resolver com tecnologia, mas não sei por onde começar.",
        ),
        cl.Starter(
            label="Já tenho um MVP e quero refinar",
            message="Já tenho uma versão inicial do meu produto e quero entender melhor meus usuários.",
        ),
    ]
