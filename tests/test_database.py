import pytest

from recipe_poster.storage import database


class FakeCursor:
    """実行されたSQLを記録し、問い合わせの種類に応じた結果を返す"""

    def __init__(self, conn):
        self.conn = conn
        self.result = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        self.conn.executed.append((sql, params))
        if "to_regclass" in sql:
            self.result = [(params[0] in self.conn.tables,)]
        elif sql.startswith("CREATE TABLE post_history"):
            self.conn.tables.add('public."post_history"')
        elif sql.startswith("INSERT INTO post_history (recipe_key, recipe_title, platform, posted_at)"):
            self.rowcount = self.conn.copied
        elif sql.startswith("INSERT"):
            if self.conn.fail:
                raise RuntimeError("DBエラー")
        elif sql.startswith("SELECT recipe_key"):
            self.result = [(key,) for key in self.conn.keys]
        elif sql.startswith("SELECT count(*)"):
            self.result = [(len(self.conn.keys),)]

    def fetchone(self):
        return self.result[0]

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, tables=(), keys=(), copied=0, fail=False):
        self.tables = {f'public."{name}"' for name in tables}
        self.keys = list(keys)
        self.copied = copied
        self.fail = fail
        self.executed = []
        self.committed = self.rolled_back = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def statements(conn) -> list[str]:
    return [sql.split(" (")[0] for sql, _ in conn.executed if not sql.startswith("SELECT to_regclass")]


def test_ensure_schema_creates_table_and_copies_old_records(temp_logger):
    conn = FakeConnection(tables=["Recipe_info"], copied=1)
    database.ensure_schema(conn)
    assert statements(conn) == ["CREATE TABLE post_history", "INSERT INTO post_history"]
    assert conn.committed
    assert "以前の記録から 1件を写しました" in temp_logger.log_file.read_text(encoding="utf-8")


def test_ensure_schema_without_old_table():
    conn = FakeConnection()
    database.ensure_schema(conn)
    assert statements(conn) == ["CREATE TABLE post_history"]


def test_ensure_schema_does_nothing_when_table_exists():
    conn = FakeConnection(tables=["post_history", "Recipe_info"])
    database.ensure_schema(conn)
    assert statements(conn) == []
    assert not conn.committed


def test_posted_keys_and_count():
    conn = FakeConnection(keys=["チャーシューチャーハン", "豚の角煮"])
    assert database.posted_keys(conn, "rakuten") == {"チャーシューチャーハン", "豚の角煮"}
    assert database.count_posts(conn, "rakuten") == 2
    assert conn.executed[0][1] == ("rakuten",)


def test_add_post():
    conn = FakeConnection()
    database.add_post(conn, "豚の角煮", "豚の角煮の甘辛煮込み", "rakuten", "https://recipe.rakuten.co.jp/recipe/1/")
    sql, params = conn.executed[0]
    assert sql.startswith("INSERT INTO post_history (recipe_key, recipe_title, platform, post_url, posted_at)")
    assert "clock_timestamp()" in sql  # now() だと処理の開始時刻になる
    assert params == ("豚の角煮", "豚の角煮の甘辛煮込み", "rakuten", "https://recipe.rakuten.co.jp/recipe/1/")
    assert conn.committed


def test_add_post_rolls_back_and_raises():
    conn = FakeConnection(fail=True)
    with pytest.raises(RuntimeError):
        database.add_post(conn, "豚の角煮", "豚の角煮", "rakuten")
    assert conn.rolled_back and not conn.committed
