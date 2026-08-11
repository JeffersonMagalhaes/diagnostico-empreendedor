"""
Data layer mínimo para Chainlit que persiste threads no SQLite existente.

Implementa apenas os métodos necessários para listar e carregar threads,
usando as tabelas que já temos em sessions.db.
"""

import json
import os as _os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Data directory configurável
DATA_DIR = Path(_os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "sessions.db"

from chainlit.data.base import BaseDataLayer
from chainlit.element import ElementDict
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    FeedbackDict,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User
from chainlit.logger import logger


DB_PATH = Path(__file__).parent.parent / "data" / "sessions.db"


class SQLiteDataLayer(BaseDataLayer):
    """Data layer que persiste threads no sessions.db existente."""

    def __init__(self):
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chainlit_users (
                id TEXT PRIMARY KEY,
                "identifier" TEXT UNIQUE NOT NULL,
                "createdAt" TEXT NOT NULL,
                "metadata" TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chainlit_threads (
                id TEXT PRIMARY KEY,
                "userId" TEXT NOT NULL,
                "userIdentifier" TEXT,
                "createdAt" TEXT NOT NULL,
                "name" TEXT,
                "tags" TEXT DEFAULT '[]',
                "metadata" TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chainlit_steps (
                id TEXT PRIMARY KEY,
                "threadId" TEXT NOT NULL,
                "name" TEXT NOT NULL DEFAULT '',
                "type" TEXT NOT NULL DEFAULT 'undefined',
                "input" TEXT DEFAULT '',
                "output" TEXT DEFAULT '',
                "metadata" TEXT DEFAULT '{}',
                "tags" TEXT DEFAULT '[]',
                "start" TEXT,
                "end" TEXT,
                "createdAt" TEXT,
                "generation" TEXT,
                "showInput" TEXT,
                "language" TEXT,
                "isError" INTEGER DEFAULT 0,
                "waitForAnswer" INTEGER DEFAULT 0,
                "parentId" TEXT,
                FOREIGN KEY ("threadId") REFERENCES chainlit_threads(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.close()

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        conn = self._get_conn()
        row = conn.execute(
            'SELECT * FROM chainlit_users WHERE "identifier" = ?', (identifier,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return PersistedUser(
            id=row["id"],
            identifier=row["identifier"],
            createdAt=row["createdAt"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        conn = self._get_conn()
        now = datetime.utcnow().isoformat() + "Z"
        metadata = user.metadata if user.metadata else {}

        try:
            conn.execute(
                'INSERT INTO chainlit_users (id, "identifier", "createdAt", "metadata") VALUES (?, ?, ?, ?)',
                (user.identifier, user.identifier, now, json.dumps(metadata)),
            )
            conn.commit()
            conn.close()
            return PersistedUser(
                id=user.identifier,
                identifier=user.identifier,
                createdAt=now,
                metadata=metadata,
            )
        except sqlite3.IntegrityError:
            # Usuário já existe, retorna o existente
            conn.close()
            return await self.get_user(user.identifier)

    async def update_thread(self, thread_id: str, name: Optional[str] = None,
                            user_id: Optional[str] = None,
                            metadata: Optional[Dict] = None,
                            tags: Optional[List[str]] = None) -> None:
        conn = self._get_conn()
        now = datetime.utcnow().isoformat() + "Z"

        existing = conn.execute(
            "SELECT id, name FROM chainlit_threads WHERE id = ?", (thread_id,)
        ).fetchone()

        if existing:
            # Só atualiza campos que foram explicitamente passados (não None)
            if name is not None:
                conn.execute(
                    'UPDATE chainlit_threads SET "name" = ? WHERE id = ?',
                    (name, thread_id),
                )
            if metadata is not None:
                conn.execute(
                    'UPDATE chainlit_threads SET "metadata" = ? WHERE id = ?',
                    (json.dumps(metadata), thread_id),
                )
            if tags is not None:
                conn.execute(
                    'UPDATE chainlit_threads SET "tags" = ? WHERE id = ?',
                    (json.dumps(tags), thread_id),
                )
            if user_id is not None:
                conn.execute(
                    'UPDATE chainlit_threads SET "userId" = ?, "userIdentifier" = ? WHERE id = ?',
                    (user_id, user_id, thread_id),
                )
        else:
            conn.execute(
                """INSERT INTO chainlit_threads (id, "userId", "userIdentifier", "createdAt", "name", "metadata", "tags")
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    user_id or "anonymous",
                    user_id or "anonymous",
                    now,
                    name,
                    json.dumps(metadata or {}),
                    json.dumps(tags or []),
                ),
            )
        conn.commit()
        conn.close()

    async def list_threads(self, pagination: Pagination, filter: ThreadFilter) -> PaginatedResponse:
        conn = self._get_conn()
        user_id = filter.userId if filter else None
        # Pagination usa cursor, não offset. Para simplicidade, usamos limit sem offset.
        limit = pagination.first

        if user_id:
            rows = conn.execute(
                """SELECT id, "userId", "userIdentifier", "createdAt", "name", "metadata", "tags"
                   FROM chainlit_threads WHERE "userIdentifier" = ?
                   ORDER BY "createdAt" DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
            total = conn.execute(
                'SELECT COUNT(*) as c FROM chainlit_threads WHERE "userIdentifier" = ?',
                (user_id,),
            ).fetchone()["c"]
        else:
            rows = conn.execute(
                """SELECT id, "userId", "userIdentifier", "createdAt", "name", "metadata", "tags"
                   FROM chainlit_threads ORDER BY "createdAt" DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) as c FROM chainlit_threads"
            ).fetchone()["c"]

        conn.close()

        data = []
        for r in rows:
            data.append(ThreadDict(
                id=r["id"],
                createdAt=r["createdAt"],
                name=r["name"],
                userId=r["userId"],
                userIdentifier=r["userIdentifier"],
                metadata=json.loads(r["metadata"] or "{}"),
                tags=json.loads(r["tags"] or "[]"),
                steps=[],
                elements=[],
            ))

        return PaginatedResponse(
            pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None),
            data=data,
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM chainlit_threads WHERE id = ?", (thread_id,)
        ).fetchone()

        if not row:
            conn.close()
            return None

        # Carrega steps do thread
        step_rows = conn.execute(
            'SELECT * FROM chainlit_steps WHERE "threadId" = ? ORDER BY "createdAt" ASC',
            (thread_id,),
        ).fetchall()
        conn.close()

        steps = []
        for s in step_rows:
            steps.append({
                "id": s["id"],
                "name": s["name"],
                "type": s["type"],
                "threadId": s["threadId"],
                "input": s["input"] or "",
                "output": s["output"] or "",
                "metadata": json.loads(s["metadata"] or "{}"),
                "tags": json.loads(s["tags"] or "[]"),
                "start": s["start"],
                "end": s["end"],
                "createdAt": s["createdAt"],
                "generation": json.loads(s["generation"]) if s["generation"] else None,
                "showInput": s["showInput"],
                "language": s["language"],
                "isError": bool(s["isError"]),
                "waitForAnswer": bool(s["waitForAnswer"]),
                "parentId": s["parentId"],
            })

        return ThreadDict(
            id=row["id"],
            createdAt=row["createdAt"],
            name=row["name"],
            userId=row["userId"],
            userIdentifier=row["userIdentifier"],
            metadata=json.loads(row["metadata"] or "{}"),
            tags=json.loads(row["tags"] or "[]"),
            steps=steps,
            elements=[],
        )

    async def delete_thread(self, thread_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM chainlit_steps WHERE \"threadId\" = ?", (thread_id,))
        conn.execute("DELETE FROM chainlit_threads WHERE id = ?", (thread_id,))
        conn.commit()
        conn.close()

    async def create_step(self, step_dict: StepDict) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO chainlit_steps (id, "threadId", "name", "type", "input", "output",
                   "metadata", "tags", "start", "end", "createdAt", "generation",
                   "showInput", "language", "isError", "waitForAnswer", "parentId")
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    step_dict.get("id", ""),
                    step_dict.get("threadId", ""),
                    step_dict.get("name", ""),
                    step_dict.get("type", "undefined"),
                    step_dict.get("input", ""),
                    step_dict.get("output", ""),
                    json.dumps(step_dict.get("metadata", {})),
                    json.dumps(step_dict.get("tags", [])),
                    step_dict.get("start"),
                    step_dict.get("end"),
                    step_dict.get("createdAt"),
                    json.dumps(step_dict.get("generation")) if step_dict.get("generation") else None,
                    str(step_dict.get("showInput")) if step_dict.get("showInput") is not None else None,
                    step_dict.get("language"),
                    1 if step_dict.get("isError") else 0,
                    1 if step_dict.get("waitForAnswer") else 0,
                    step_dict.get("parentId"),
                ),
            )
        except sqlite3.IntegrityError:
            # Step already exists, update it
            pass
        conn.commit()
        conn.close()

    async def update_step(self, step_dict: StepDict) -> None:
        conn = self._get_conn()
        conn.execute(
            """UPDATE chainlit_steps SET "output" = ?, "end" = ?, "isError" = ?,
               "showInput" = ?, "input" = ?, "metadata" = ?, "tags" = ? WHERE id = ?""",
            (
                step_dict.get("output", ""),
                step_dict.get("end"),
                1 if step_dict.get("isError") else 0,
                str(step_dict.get("showInput")) if step_dict.get("showInput") is not None else None,
                step_dict.get("input", ""),
                json.dumps(step_dict.get("metadata", {})),
                json.dumps(step_dict.get("tags", [])),
                step_dict.get("id", ""),
            ),
        )
        conn.commit()
        conn.close()

    async def delete_step(self, step_id: str) -> None:
        pass

    async def create_element(self, element: "ElementDict") -> None:
        pass

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None) -> None:
        pass

    async def delete_feedback(self, feedback_id: str) -> None:
        pass

    async def upsert_feedback(self, feedback: Feedback) -> str:
        return ""

    async def get_thread_author(self, thread_id: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            'SELECT "userIdentifier" FROM chainlit_threads WHERE id = ?', (thread_id,)
        ).fetchone()
        conn.close()
        return row["userIdentifier"] if row else ""

    async def build_debug_url(self) -> str:
        return ""

    async def get_favorite_steps(self, user_id: str) -> List["StepDict"]:
        return []

    async def set_step_favorite(self, step_id: str, favorite: bool) -> None:
        pass

    async def close(self) -> None:
        pass
