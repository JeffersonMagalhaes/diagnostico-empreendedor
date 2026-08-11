"""
Segurança: rate limiting, sanitização de input, e validação de sessão.
"""

import time
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

# Data directory — usa DATA_DIR do ambiente ou ./data local
import os as _os
DATA_DIR = Path(_os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "sessions.db"

# --- Rate Limiting ---

MAX_MESSAGES_PER_MINUTE = 10
MAX_MESSAGE_LENGTH = 2000


def check_rate_limit(user_id: str) -> tuple[bool, str]:
    """
    Verifica se o usuário excedeu o limite de mensagens.
    Retorna (permitido, mensagem_de_erro).
    """
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            window_start REAL NOT NULL
        )
    """)
    conn.commit()

    now = time.time()
    row = conn.execute(
        "SELECT count, window_start FROM rate_limits WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO rate_limits (user_id, count, window_start) VALUES (?, 1, ?)",
            (user_id, now),
        )
        conn.commit()
        conn.close()
        return True, ""

    count = row["count"]
    window_start = row["window_start"]

    if now - window_start > 60:
        # Nova janela
        conn.execute(
            "UPDATE rate_limits SET count = 1, window_start = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()
        conn.close()
        return True, ""

    if count >= MAX_MESSAGES_PER_MINUTE:
        wait = int(60 - (now - window_start))
        conn.close()
        return False, f"Muitas mensagens. Aguarde {wait}s."

    conn.execute(
        "UPDATE rate_limits SET count = count + 1 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()
    return True, ""


# --- Session Isolation ---

def verify_session_owner(session_id: str, user_id: str) -> bool:
    """Verifica se a sessão pertence ao usuário."""
    conn = _get_db()
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return False
    return row["user_id"] == user_id


# --- Input Sanitization ---

# Padrões de possível prompt injection
INJECTION_PATTERNS = [
    r"\[SYSTEM\]",
    r"\[INST\]",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"ignore (all |)previous instructions",
    r"you are now",
    r"new system prompt",
]


def sanitize_message(content: str) -> str:
    """
    Sanitiza a mensagem do usuário contra prompt injection.
    Trunca em MAX_MESSAGE_LENGTH e remove marcadores suspeitos.
    """
    # Trunca
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[:MAX_MESSAGE_LENGTH] + "..."

    # Remove marcadores de injection
    for pattern in INJECTION_PATTERNS:
        content = re.sub(pattern, "[removido]", content, flags=re.IGNORECASE)

    return content


def validate_message(content: str) -> tuple[bool, str]:
    """
    Valida a mensagem: tamanho mínimo e máximo, sem conteúdo vazio.
    Retorna (válido, erro).
    """
    stripped = content.strip()
    if not stripped:
        return False, "Mensagem vazia."
    if len(stripped) > MAX_MESSAGE_LENGTH:
        return False, f"Mensagem muito longa (máx {MAX_MESSAGE_LENGTH} caracteres)."
    return True, ""


# --- Helpers ---

def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn
