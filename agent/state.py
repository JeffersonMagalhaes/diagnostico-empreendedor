"""
Gerenciamento de estado da sessão de diagnóstico.

Cada sessão mantém um dicionário com as estruturas sendo preenchidas,
gaps pendentes, confirmações do cliente, e sinais de loop.
"""

import json
import os as _os
import sqlite3
from datetime import datetime
from pathlib import Path

# Data directory configurável
DATA_DIR = Path(_os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "sessions.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            thread_id TEXT,
            title TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'active'
        )
    """)
    # Migração: adiciona colunas thread_id e title se não existirem
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN thread_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
    except sqlite3.OperationalError:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    conn.commit()
    return conn


def create_session(session_id: str, user_id: str) -> dict:
    """Cria uma nova sessão de diagnóstico."""
    now = datetime.utcnow().isoformat()
    initial_state = {
        "vpc": {
            "dores": [],
            "tarefas": [],
            "ganhos": [],
            "produtos_servicos": [],
            "aliviadores_dor": [],
            "geradores_ganho": [],
        },
        "jtbd": [],
        "jornada": {"etapas": []},
        "lean_futuro": {
            "segmentos_cliente": [],
            "canais_aquisicao": [],
            "fontes_receita": [],
            "metricas_chave": [],
            "diferencial_vantagem": [],
            "riscos_barreiras": [],
        },
        "publico": {
            "segmento_entrada": None,
            "segmentos_futuros": [],
        },
        "processo": {
            "gaps_pendentes": [],
            "confirmacoes": [],
            "tecnicas_tentadas": [],
            "sinal_loop": None,
        },
    }
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (id, user_id, created_at, updated_at, state) VALUES (?, ?, ?, ?, ?)",
        (session_id, user_id, now, now, json.dumps(initial_state, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    return initial_state


def load_state(session_id: str) -> dict | None:
    """Carrega o estado de uma sessão."""
    conn = _get_db()
    row = conn.execute(
        "SELECT state FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row["state"])


def save_state(session_id: str, state: dict) -> None:
    """Salva o estado atualizado da sessão."""
    now = datetime.utcnow().isoformat()
    conn = _get_db()
    conn.execute(
        "UPDATE sessions SET state = ?, updated_at = ? WHERE id = ?",
        (json.dumps(state, ensure_ascii=False), now, session_id),
    )
    conn.commit()
    conn.close()


def save_message(session_id: str, role: str, content: str) -> None:
    """Registra uma mensagem no histórico da sessão."""
    now = datetime.utcnow().isoformat()
    conn = _get_db()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now),
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 40) -> list[dict]:
    """Recupera o histórico recente da sessão."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def get_user_sessions(user_id: str) -> list[dict]:
    """Lista sessões ativas de um usuário."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, thread_id, title, created_at, updated_at, status FROM sessions WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def link_thread(session_id: str, thread_id: str) -> None:
    """Associa um thread do Chainlit à sessão."""
    conn = _get_db()
    conn.execute(
        "UPDATE sessions SET thread_id = ? WHERE id = ?",
        (thread_id, session_id),
    )
    conn.commit()
    conn.close()


def get_session_by_thread(thread_id: str) -> str | None:
    """Retorna o session_id associado a um thread do Chainlit."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id FROM sessions WHERE thread_id = ? AND status = 'active'",
        (thread_id,),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def set_session_title(session_id: str, title: str) -> None:
    """Define um título descritivo para a sessão."""
    conn = _get_db()
    conn.execute(
        "UPDATE sessions SET title = ? WHERE id = ?",
        (title[:100], session_id),
    )
    conn.commit()
    conn.close()


def get_session_title(session_id: str) -> str:
    """Retorna o título da sessão ou um fallback."""
    conn = _get_db()
    row = conn.execute(
        "SELECT title, created_at FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if row and row["title"]:
        return row["title"]
    return f"Diagnóstico — {row['created_at'][:10]}" if row else "Diagnóstico"
