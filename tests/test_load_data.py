import pytest

from etl import load_data as L


class FakeCursor:
    def __init__(self, fail_on_table=None):
        self.executed = []
        self.copies = []
        self.fail_on_table = fail_on_table
        self.closed = False

    def execute(self, sql):
        self.executed.append(sql)

    def copy_expert(self, sql, file_obj):
        self.copies.append(sql)
        if self.fail_on_table and self.fail_on_table in sql:
            raise RuntimeError("COPY lỗi giả lập")
        file_obj.read()

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _tables(tmp_path):
    one = tmp_path / "one.csv"
    two = tmp_path / "two.csv"
    one.write_text("order_id\n1\n", encoding="utf-8")
    two.write_text("order_id\n2\n", encoding="utf-8")
    return {"Dim_One": one, "Fact_Two": two}


def _run(monkeypatch, tables, cursor, conn):
    monkeypatch.setattr(L, "WAREHOUSE_TABLES", tables)
    monkeypatch.setattr(L, "ensure_dirs", lambda: None)
    monkeypatch.setattr(
        L,
        "get_db_config",
        lambda: {"user": "u", "host": "h", "port": 5432, "dbname": "d"},
    )
    monkeypatch.setattr(L.psycopg2, "connect", lambda **kwargs: conn)
    L.load_data_warehouse()
    return cursor, conn


def test_success_commits_once_after_all_copies(monkeypatch, tmp_path):
    cursor = FakeCursor()
    conn = FakeConnection(cursor)
    _run(monkeypatch, _tables(tmp_path), cursor, conn)

    assert len(cursor.copies) == 2
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert conn.closed is True
    assert len(cursor.executed) == 1
    assert "TRUNCATE TABLE Dim_One, Fact_Two" in cursor.executed[0]


def test_failure_rolls_back_everything_and_raises(monkeypatch, tmp_path):
    cursor = FakeCursor(fail_on_table="Fact_Two")
    conn = FakeConnection(cursor)
    tables = _tables(tmp_path)

    with pytest.raises(RuntimeError, match="COPY lỗi giả lập"):
        _run(monkeypatch, tables, cursor, conn)

    assert conn.commits == 0
    assert conn.rollbacks == 1
    assert conn.closed is True
    assert len(cursor.copies) == 2  # bảng 1 đã COPY, bảng 2 lỗi
