"""Database client and query adapter for Dastak.

Strictly follows AGENTS.md §2.3 Rule 5 (MOCK_MODE must work with zero network).
- When MOCK_MODE=0: Connects to Supabase PostgreSQL using supabase-py.
- When MOCK_MODE=1: Uses an in-memory store mimicking table operations (insert, select, update, delete).
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from Backend.config import MOCK_MODE, SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger("dastak.db")

_supabase_client = None


class InMemoryQueryBuilder:
    """Lightweight query builder for in-memory records to support MOCK_MODE=1."""

    def __init__(self, table_name: str, records: List[Dict[str, Any]]):
        self.table_name = table_name
        self.records = records
        self._filtered: List[Dict[str, Any]] = list(records)

    def select(self, columns: str = "*"):
        # Select all for in-memory records
        return self

    def eq(self, column: str, value: Any):
        self._filtered = [r for r in self._filtered if r.get(column) == value]
        return self

    def order(self, column: str, desc: bool = False):
        self._filtered.sort(key=lambda r: r.get(column) or "", reverse=desc)
        return self

    def limit(self, count: int):
        self._filtered = self._filtered[:count]
        return self

    def execute(self):
        class Response:
            def __init__(self, data):
                self.data = data
        return Response(list(self._filtered))


class InMemoryTable:
    """Table wrapper for in-memory mock store."""

    def __init__(self, name: str, db: "InMemoryDB"):
        self.name = name
        self.db = db

    def select(self, columns: str = "*") -> InMemoryQueryBuilder:
        records = self.db.tables.setdefault(self.name, [])
        builder = InMemoryQueryBuilder(self.name, records)
        return builder.select(columns)

    def insert(self, record: Dict[str, Any] | List[Dict[str, Any]]):
        table_records = self.db.tables.setdefault(self.name, [])
        items = [record] if isinstance(record, dict) else record
        inserted_items = []
        for item in items:
            new_item = dict(item)
            if "id" not in new_item:
                new_item["id"] = len(table_records) + 1
            if "created_at" not in new_item:
                new_item["created_at"] = datetime.now(timezone.utc).isoformat()
            table_records.append(new_item)
            inserted_items.append(new_item)

        class Response:
            def __init__(self, data):
                self.data = data
        return InMemoryInsertBuilder(inserted_items)

    def update(self, updates: Dict[str, Any]):
        return InMemoryUpdateBuilder(self.name, self.db, updates)


class InMemoryInsertBuilder:
    def __init__(self, data: List[Dict[str, Any]]):
        self._data = data

    def execute(self):
        class Response:
            def __init__(self, data):
                self.data = data
        return Response(self._data)


class InMemoryUpdateBuilder:
    def __init__(self, table_name: str, db: "InMemoryDB", updates: Dict[str, Any]):
        self.table_name = table_name
        self.db = db
        self.updates = updates
        self._conditions: List[tuple] = []

    def eq(self, column: str, value: Any):
        self._conditions.append((column, value))
        return self

    def execute(self):
        table_records = self.db.tables.setdefault(self.table_name, [])
        updated = []
        for r in table_records:
            match = all(r.get(c) == v for c, v in self._conditions)
            if match:
                r.update(self.updates)
                updated.append(dict(r))
        class Response:
            def __init__(self, data):
                self.data = data
        return Response(updated)


class InMemoryDB:
    """Mock in-memory database store for full offline execution under MOCK_MODE=1."""

    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {}

    def table(self, name: str) -> InMemoryTable:
        return InMemoryTable(name, self)


_in_memory_db_instance: Optional[InMemoryDB] = None


def get_db():
    """Return the active database client.

    If MOCK_MODE=1 or Supabase credentials are not provided, returns InMemoryDB.
    Otherwise returns the live Supabase Client.
    """
    global _supabase_client, _in_memory_db_instance

    if MOCK_MODE:
        if _in_memory_db_instance is None:
            _in_memory_db_instance = InMemoryDB()
            logger.info("Using InMemoryDB (MOCK_MODE=1 active). Zero network required.")
        return _in_memory_db_instance

    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY missing. Falling back to InMemoryDB.")
        if _in_memory_db_instance is None:
            _in_memory_db_instance = InMemoryDB()
        return _in_memory_db_instance

    from supabase import create_client
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("Supabase client initialized: %s", SUPABASE_URL)
    return _supabase_client
