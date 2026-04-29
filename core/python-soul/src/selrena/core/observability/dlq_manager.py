"""
dlq_manager.py — 异步死信队列 (Dead Letter Queue)
═══════════════════════════════════════════════════
所属层级：可观测性 (Observability)
核心作用：捕获事件处理器未处理的异常，持久化到本地 SQLite，
         供后续审计、排查或重放 (Replay)

v4.5 Phase 2: Trace & DLQ — 韧性兜底

设计原则：
1. 基于 aiosqlite 异步操作，不阻塞主事件循环
2. 仅做写入和查询，不做自动重放（重放由人工/脚本触发）
3. 通过 trace_id 关联全链路追踪
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from selrena.core.observability.logger import get_logger

logger = get_logger("dlq_manager")

# 默认 DLQ 数据库路径
_DEFAULT_DB_PATH = Path("data") / "dlq" / "dead_letters.db"


class DeadLetterQueue:
    """
    异步死信队列管理器（单例）。

    当 EventBus 的事件处理器抛出未捕获异常时，
    将 { trace_id, event_type, event_payload, exception_stack, timestamp }
    异步写入本地 SQLite 持久化存储。
    """

    _instance: DeadLetterQueue | None = None

    def __new__(cls) -> DeadLetterQueue:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _init(self, db_path: Path | None = None) -> None:
        """惰性初始化，在首次 enqueue 时自动调用。"""
        self._db_path = db_path or _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None
        self._initialized = True

    async def _ensure_connection(self) -> aiosqlite.Connection:
        """确保数据库连接就绪并创建表。"""
        if not self._initialized:
            self._init()
        if self._conn is None:
            self._conn = await aiosqlite.connect(str(self._db_path))
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS dead_letters (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id    TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    exception   TEXT NOT NULL,
                    stack_trace TEXT,
                    created_at  TEXT NOT NULL,
                    replayed    INTEGER DEFAULT 0
                )
            """)
            await self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dl_trace ON dead_letters(trace_id)"
            )
            await self._conn.commit()
            logger.info("DLQ 数据库已就绪", db_path=str(self._db_path))
        return self._conn

    async def enqueue(
        self,
        trace_id: str,
        event_type: str,
        payload: Any,
        exception: Exception,
    ) -> None:
        """
        将失败事件写入死信队列。

        Parameters
        ----------
        trace_id : str
            全链路追踪 ID
        event_type : str
            事件类型名称（通常为类名）
        payload : Any
            事件的序列化载荷（会尝试 JSON 序列化）
        exception : Exception
            捕获到的异常实例
        """
        conn = await self._ensure_connection()

        try:
            payload_json = json.dumps(payload, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            payload_json = str(payload)

        stack = traceback.format_exception(type(exception), exception, exception.__traceback__)
        stack_text = "".join(stack)

        await conn.execute(
            """
            INSERT INTO dead_letters (trace_id, event_type, payload, exception, stack_trace, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                event_type,
                payload_json,
                str(exception),
                stack_text,
                datetime.now().isoformat(),
            ),
        )
        await conn.commit()
        logger.warning(
            "事件已写入死信队列",
            trace_id=trace_id,
            event_type=event_type,
            error=str(exception),
        )

    async def query_by_trace(self, trace_id: str) -> list[dict]:
        """按 trace_id 查询死信记录。"""
        conn = await self._ensure_connection()
        cursor = await conn.execute(
            "SELECT id, trace_id, event_type, payload, exception, stack_trace, created_at, replayed "
            "FROM dead_letters WHERE trace_id = ? ORDER BY created_at DESC",
            (trace_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "trace_id": r[1], "event_type": r[2],
                "payload": r[3], "exception": r[4], "stack_trace": r[5],
                "created_at": r[6], "replayed": bool(r[7]),
            }
            for r in rows
        ]

    async def query_recent(self, limit: int = 50) -> list[dict]:
        """查询最近的死信记录。"""
        conn = await self._ensure_connection()
        cursor = await conn.execute(
            "SELECT id, trace_id, event_type, payload, exception, stack_trace, created_at, replayed "
            "FROM dead_letters WHERE replayed = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "trace_id": r[1], "event_type": r[2],
                "payload": r[3], "exception": r[4], "stack_trace": r[5],
                "created_at": r[6], "replayed": bool(r[7]),
            }
            for r in rows
        ]

    async def mark_replayed(self, record_id: int) -> None:
        """标记某条死信为已重放。"""
        conn = await self._ensure_connection()
        await conn.execute(
            "UPDATE dead_letters SET replayed = 1 WHERE id = ?",
            (record_id,),
        )
        await conn.commit()

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("DLQ 数据库连接已关闭")
