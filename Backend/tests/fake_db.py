"""A tiny in-memory stand-in for the Supabase query builder.

Tests use it to exercise the SQL-shaped code paths without a network. It
supports exactly what SafeZone calls: insert, upsert, update, delete, select,
eq, in_, not_.is_ and limit. It is a test double, not a second data layer --
production code never imports this module.

Where PostgREST refuses something, this refuses it too. An unfiltered delete
is the one that matters: PostgREST rejects it rather than emptying a table,
so the reset script has to pass a match-everything filter, and a test must
fail if someone drops it.
"""

from collections import defaultdict


class Result:
    def __init__(self, data):
        self.data = data


class _Not:
    """``query.not_.is_(column, "null")``, as the real builder spells it."""

    def __init__(self, query):
        self.query = query

    def is_(self, column, value):
        self.query.not_filters.append((column, value))
        return self.query


class Query:
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self.op = None
        self.payload = {}
        self.filters = []
        self.limit_n = None
        self.conflict = None
        self.in_filter = None
        self.not_filters = []

    @property
    def not_(self):
        return _Not(self)

    def insert(self, row):
        self.op = "insert"
        self.payload = dict(row)
        return self

    def upsert(self, row, on_conflict=None):
        self.op = "upsert"
        self.payload = dict(row)
        self.conflict = on_conflict
        return self

    def update(self, values):
        self.op = "update"
        self.payload = dict(values)
        return self

    def select(self, *_args):
        self.op = "select"
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_filter = (column, list(values))
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def _match(self, row):
        if not all(row.get(column) == value for column, value in self.filters):
            return False
        for column, value in self.not_filters:
            if value == "null" and row.get(column) is None:
                return False
        if self.in_filter is not None:
            column, values = self.in_filter
            return row.get(column) in values
        return True

    def execute(self):
        rows = self.store.tables[self.table]

        if self.op == "insert":
            row = {"id": self.store.next_id(), **self.payload}
            rows.append(row)
            return Result([dict(row)])

        if self.op == "upsert":
            keys = [key.strip() for key in (self.conflict or "id").split(",")]
            for existing in rows:
                if all(existing.get(key) == self.payload.get(key) for key in keys):
                    existing.update(self.payload)
                    return Result([dict(existing)])
            row = {"id": self.store.next_id(), **self.payload}
            rows.append(row)
            return Result([dict(row)])

        if self.op == "delete" and not (
            self.filters or self.in_filter or self.not_filters
        ):
            # PostgREST refuses this rather than truncating the table.
            raise RuntimeError("DELETE requires a filter")

        matched = [row for row in rows if self._match(row)]

        if self.op == "delete":
            kept = [row for row in rows if not self._match(row)]
            rows[:] = kept
            return Result([dict(row) for row in matched])

        if self.op == "update":
            for row in matched:
                row.update(self.payload)
            return Result([dict(row) for row in matched])

        if self.limit_n is not None:
            matched = matched[: self.limit_n]
        return Result([dict(row) for row in matched])


class FakeDB:
    def __init__(self):
        self.tables = defaultdict(list)
        self._id = 0

    def next_id(self):
        self._id += 1
        return self._id

    def table(self, name):
        return Query(self, name)
