import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pathlib import Path


class Status(Enum):
    processing = "processing"
    queued = "queued"
    processed = "processed"
    failed = "failed"


class CrawlStorage:
    """SQLite-backed storage for crawl state and extracted content."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    status_code INTEGER,
                    fetched_timestamp TEXT,
                    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'processed', 'failed'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS data (
                    id INTEGER PRIMARY KEY,
                    metadata_id INTEGER NOT NULL UNIQUE REFERENCES metadata(id),
                    content TEXT
                )
                """
            )

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    # ---- sync methods (called from ThreadPoolExecutor) ----

    def get_stalled_records_sync(self) -> list:
        conn = self._get_connection()
        c = conn.cursor()
        with conn:
            c.execute(
                """
                SELECT url, status FROM metadata
                WHERE status = ? OR status = ?
                """,
                (Status.processing.value, Status.queued.value),
            )
            return c.fetchall()

    def get_finished_records_sync(self) -> list:
        conn = self._get_connection()
        c = conn.cursor()
        with conn:
            c.execute(
                """
                SELECT url, status FROM metadata
                WHERE status = ? OR status = ?
                """,
                (Status.failed.value, Status.processed.value),
            )
            return c.fetchall()

    def is_completed_sync(self, url: str) -> bool:
        conn = self._get_connection()
        c = conn.cursor()
        with conn:
            c.execute("SELECT status FROM metadata WHERE url = ?", (url,))
            result = c.fetchone()
        if result is None:
            return False
        return result["status"] in (Status.processed.value, Status.failed.value)

    def write_metadata_sync(
        self, url: str, status_code: int | None, timestamp: str, status: Status
    ) -> int:
        conn = self._get_connection()
        c = conn.cursor()
        with conn:
            c.execute(
                """
                INSERT INTO metadata (url, status_code, fetched_timestamp, status)
                VALUES (:url, :status_code, :fetched_timestamp, :status)
                ON CONFLICT(url)
                DO UPDATE SET
                    fetched_timestamp = excluded.fetched_timestamp,
                    status = excluded.status,
                    status_code = excluded.status_code
                RETURNING id;
                """,
                {
                    "url": url,
                    "status_code": status_code,
                    "fetched_timestamp": timestamp,
                    "status": status.value,
                },
            )
            result = c.fetchone()
            return result[0] if result else None

    def write_data_sync(self, metadata_id: int, content: str) -> None:
        conn = self._get_connection()
        c = conn.cursor()
        with conn:
            c.execute(
                """
                INSERT INTO data (metadata_id, content) VALUES (:metadata_id, :content)
                ON CONFLICT(metadata_id)
                DO UPDATE SET
                    content = excluded.content
                """,
                {"metadata_id": metadata_id, "content": content},
            )

    def get_all_results_sync(self) -> list[dict]:
        conn = self._get_connection()
        c = conn.cursor()
        with conn:
            c.execute(
                """
                SELECT m.url, m.status_code, m.fetched_timestamp, m.status, d.content
                FROM metadata m
                LEFT JOIN data d ON d.metadata_id = m.id
                """
            )
            rows = c.fetchall()
        return [
            {
                "url": row["url"],
                "status_code": row["status_code"],
                "content": row["content"],
                "fetched_at": row["fetched_timestamp"],
                "status": row["status"],
            }
            for row in rows
        ]

    # ---- async wrappers ----

    async def get_stalled_records(self, executor: ThreadPoolExecutor) -> list:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self.get_stalled_records_sync)

    async def get_finished_records(self, executor: ThreadPoolExecutor) -> list:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self.get_finished_records_sync)

    async def is_completed(self, executor: ThreadPoolExecutor, url: str) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self.is_completed_sync, url)

    async def write_metadata(
        self,
        executor: ThreadPoolExecutor,
        url: str,
        status_code: int | None,
        timestamp: str,
        status: Status,
    ) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            executor, self.write_metadata_sync, url, status_code, timestamp, status
        )

    async def write_data(
        self, executor: ThreadPoolExecutor, metadata_id: int, content: str
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            executor, self.write_data_sync, metadata_id, content
        )

    async def get_all_results(self, executor: ThreadPoolExecutor) -> list[dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self.get_all_results_sync)
