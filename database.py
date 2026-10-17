"""
データベースモジュール - 投稿先ごとの投稿履歴を PostgreSQL に記録する

テーブル post_history（1レシピ×1投稿先につき1行）:
    id           SERIAL      主キー
    recipe_key   TEXT        レシピの識別名（投稿素材のフォルダ名）
    recipe_title TEXT        投稿したときのタイトル
    platform     TEXT        投稿先（rakuten / instagram / tiktok / website）
    post_url     TEXT        投稿のURL（分からない場合は空）
    posted_at    TIMESTAMPTZ 投稿日時
    UNIQUE (recipe_key, platform)

以前の "Recipe_info" テーブル（楽天レシピのみ・投稿日と累計件数）は、post_history を作るときに
楽天レシピの履歴として1回だけ写す。"Recipe_info" 自体は消さずに残す（今後は使わない）。
"""
import psycopg
from config import DB_SETTINGS
from logger import get_logger

PLATFORM_RAKUTEN = "rakuten"

_CREATE_POST_HISTORY = """
CREATE TABLE post_history (
    id           SERIAL PRIMARY KEY,
    recipe_key   TEXT NOT NULL,
    recipe_title TEXT NOT NULL,
    platform     TEXT NOT NULL,
    post_url     TEXT NOT NULL DEFAULT '',
    posted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (recipe_key, platform)
);
"""

_COPY_RECIPE_INFO = """
INSERT INTO post_history (recipe_key, recipe_title, platform, posted_at)
SELECT DISTINCT ON (recipe_name) recipe_name, recipe_name, %s, make_date(post_year, post_month, post_day)
FROM "Recipe_info"
ORDER BY recipe_name, id
ON CONFLICT (recipe_key, platform) DO NOTHING;
"""


def connect() -> psycopg.Connection:
    """データベースに接続し、投稿履歴のテーブルが無ければ作る"""
    conn = psycopg.connect(**{key: value for key, value in DB_SETTINGS.items() if value})
    ensure_schema(conn)
    return conn


def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL;", (f'public."{name}"',))
    return cur.fetchone()[0]


def ensure_schema(conn):
    """post_history が無ければ作り、以前の "Recipe_info" の記録を写す"""
    with conn.cursor() as cur:
        if _table_exists(cur, "post_history"):
            return
        cur.execute(_CREATE_POST_HISTORY)
        copied = 0
        if _table_exists(cur, "Recipe_info"):
            cur.execute(_COPY_RECIPE_INFO, (PLATFORM_RAKUTEN,))
            copied = cur.rowcount
    conn.commit()
    get_logger().info(f"投稿履歴のテーブル post_history を作りました（以前の記録から {copied}件を写しました）")


def posted_keys(conn, platform: str) -> set[str]:
    """その投稿先に投稿済みのレシピの識別名"""
    with conn.cursor() as cur:
        cur.execute("SELECT recipe_key FROM post_history WHERE platform = %s;", (platform,))
        return {row[0] for row in cur.fetchall()}


def count_posts(conn, platform: str) -> int:
    """その投稿先への累計投稿件数"""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM post_history WHERE platform = %s;", (platform,))
        return cur.fetchone()[0]


def add_post(conn, recipe_key: str, recipe_title: str, platform: str, post_url: str = ""):
    """投稿履歴を1件記録する（投稿日時は現在時刻。now() は処理の開始時刻になるため clock_timestamp() を使う）"""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO post_history (recipe_key, recipe_title, platform, post_url, posted_at)
                VALUES (%s, %s, %s, %s, clock_timestamp());
                """,
                (recipe_key, recipe_title, platform, post_url),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
