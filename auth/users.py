"""
Autenticação de usuários com SQLite.

Gerencia registro, login e sessões de usuários.
Usa bcrypt para hash de senhas (fallback: hashlib se bcrypt não disponível).
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

# Data directory configurável
DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "users.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _hash_password(password: str) -> str:
    """Hash de senha com salt usando hashlib (stdlib, sem dependência extra)."""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + key.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifica senha contra hash armazenado."""
    salt_hex, key_hex = stored_hash.split(":")
    salt = bytes.fromhex(salt_hex)
    key = bytes.fromhex(key_hex)
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return secrets.compare_digest(key, new_key)


def register_user(email: str, password: str, name: str = "") -> tuple[bool, str]:
    """
    Registra um novo usuário.
    Retorna (sucesso, mensagem).
    """
    if len(password) < 6:
        return False, "Senha deve ter pelo menos 6 caracteres."

    conn = _get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return False, "Não foi possível completar o registro. Verifique os dados informados."

    now = datetime.utcnow().isoformat()
    password_hash = _hash_password(password)
    conn.execute(
        "INSERT INTO users (email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
        (email, password_hash, name, now),
    )
    conn.commit()
    conn.close()
    return True, "Registro realizado com sucesso."


def authenticate_user(email: str, password: str) -> dict | None:
    """
    Autentica um usuário.
    Retorna dict com dados do usuário ou None se falhar.
    """
    conn = _get_db()
    row = conn.execute(
        "SELECT id, email, name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    if not _verify_password(password, row["password_hash"]):
        return None

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["name"] or row["email"],
    }


def get_user(user_id: str) -> dict | None:
    """Busca usuário por ID."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, email, name FROM users WHERE id = ?", (int(user_id),)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": str(row["id"]), "email": row["email"], "name": row["name"] or row["email"]}


def create_first_user_if_needed() -> None:
    """Cria usuário admin inicial APENAS se variável de ambiente CREATE_DEFAULT_USER=true."""
    if os.getenv("CREATE_DEFAULT_USER", "").lower() != "true":
        return
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    conn.close()
    if count == 0:
        register_user("admin@teste.com", "admin123", "Admin")
