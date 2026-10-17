from pathlib import Path

import pytest
import yaml

import backup
import config
import database
import main
from rakuten_recipe import RakutenPost

RECIPE_YAML = {
    "schema_version": 1, "title": "{title}", "description": "簡単です。", "servings": 2, "cook_minutes": 10,
    "ingredients": [{"name": "卵", "amount": "2個"}], "steps": ["焼く。"], "story": "朝ごはんに。",
    "images": {"main": "main.jpg"},
}


def make_recipe_folder(base: Path, name: str, title: str | None = None) -> Path:
    folder = base / name
    folder.mkdir(parents=True)
    (folder / "main.jpg").write_bytes(b"jpg")
    data = dict(RECIPE_YAML, title=name if title is None else title)
    (folder / "recipe.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return folder


def make_post(key, title=None) -> RakutenPost:
    return RakutenPost(key=key, title=title or key, dish_name=key, image=Path(key) / "main.jpg",
                       cooking_time="約10分", cost=None, comment="簡単です。", servings="2",
                       ingredients=[("卵", "2個")], steps=["焼く。"], reason="朝ごはんに。", tip="")


class FakePoster:
    def __init__(self, on_site=None, fail=()):
        self.on_site = dict(on_site or {})
        self.fail = set(fail)
        self.calls = []

    def posted_recipes(self):
        return dict(self.on_site)

    def post(self, post, dry_run=False):
        self.calls.append((post.key, dry_run))
        if post.key in self.fail:
            return None
        return "" if dry_run else f"https://recipe.rakuten.co.jp/recipe/{len(self.calls)}/"


@pytest.fixture
def recorded(monkeypatch):
    """投稿履歴の記録をリストにためる"""
    calls = []
    monkeypatch.setattr(database, "add_post", lambda conn, key, title, platform, url="": calls.append((key, url)))
    monkeypatch.setattr(database, "count_posts", lambda conn, platform: len(calls))
    return calls


@pytest.fixture
def run_env(monkeypatch, tmp_path):
    """main() を、DB・ブラウザ・バックアップをフェイクにして動かす"""
    monkeypatch.setattr(config, "missing_settings", lambda: [])
    monkeypatch.setattr(config, "BASE_FOLDER", str(tmp_path / "投稿素材"))  # tmp_path 直下にはテスト用の logs ができる

    class FakeConnection:
        closed = False

        def close(self):
            FakeConnection.closed = True

    class FakeDriver:
        quit_called = False

        def quit(self):
            FakeDriver.quit_called = True

    env = type("Env", (), {})()
    env.posted = set()
    env.poster = FakePoster()
    env.backups = []
    env.conn_class, env.driver_class = FakeConnection, FakeDriver
    monkeypatch.setattr(database, "connect", FakeConnection)
    monkeypatch.setattr(database, "posted_keys", lambda conn, platform: set(env.posted))
    monkeypatch.setattr(main, "create_driver", FakeDriver)
    monkeypatch.setattr(main, "login_to_rakuten", lambda driver: "123")
    monkeypatch.setattr(main, "RecipePoster", lambda driver, member_id: env.poster)
    monkeypatch.setattr(backup, "backup_if_due", lambda force=False: env.backups.append(force) or True)
    return env


def test_load_targets_skips_posted_and_invalid(tmp_path, temp_logger):
    make_recipe_folder(tmp_path / "投稿素材", "卵焼き")
    make_recipe_folder(tmp_path / "投稿素材", "投稿済み")
    make_recipe_folder(tmp_path / "投稿素材", "タイトルなし", title="")
    make_recipe_folder(tmp_path / "投稿素材", "長すぎ", title="あ" * 30)

    targets = main.load_targets(tmp_path / "投稿素材", {"投稿済み"})

    assert [post.key for post in targets] == ["卵焼き"]
    log = temp_logger.log_file.read_text(encoding="utf-8")
    assert "楽天レシピに投稿済み（投稿履歴あり）のため対象外: 1件" in log
    assert "タイトルなし: 内容に問題があるため投稿しません" in log
    assert "レシピタイトルが楽天レシピの上限25文字を超えています" in log
    assert log.count("内容に問題があるため投稿しません") == 2


def test_post_recipes_records_success_only(recorded):
    poster = FakePoster(fail={"失敗"})
    targets = [make_post("卵焼き"), make_post("失敗"), make_post("サラダ")]

    assert main.post_recipes(targets, poster, conn=object(), dry_run=False) == (2, 1)
    assert recorded == [("卵焼き", "https://recipe.rakuten.co.jp/recipe/1/"),
                        ("サラダ", "https://recipe.rakuten.co.jp/recipe/3/")]


def test_post_recipes_records_title_already_on_site(recorded):
    url = "https://recipe.rakuten.co.jp/recipe/99/"
    poster = FakePoster(on_site={"卵焼き": url})
    assert main.post_recipes([make_post("卵焼き"), make_post("サラダ")], poster, conn=object(), dry_run=False) == (1, 0)
    assert [key for key, _ in poster.calls] == ["サラダ"]
    assert recorded[0] == ("卵焼き", url)  # 投稿せず、楽天レシピ上のURLで履歴に記録する


def test_post_recipes_limit_counts_attempts(recorded):
    poster = FakePoster(on_site={"投稿済み": "url"})
    targets = [make_post("投稿済み"), make_post("卵焼き"), make_post("サラダ")]
    assert main.post_recipes(targets, poster, conn=object(), dry_run=False, limit=1) == (1, 0)
    assert [key for key, _ in poster.calls] == ["卵焼き"]


def test_post_recipes_dry_run_does_not_record(recorded):
    poster = FakePoster(on_site={"サラダ": "url"})
    assert main.post_recipes([make_post("卵焼き"), make_post("サラダ")], poster, conn=None, dry_run=True) == (1, 0)
    assert poster.calls == [("卵焼き", True)]
    assert recorded == []


def test_post_recipes_continues_when_record_fails(monkeypatch, temp_logger):
    def broken(*args):
        raise RuntimeError("DBに接続できません")
    monkeypatch.setattr(database, "add_post", broken)

    poster = FakePoster()
    assert main.post_recipes([make_post("卵焼き"), make_post("サラダ")], poster, conn=object(), dry_run=False) == (2, 0)
    assert "卵焼き: 投稿履歴に記録できませんでした" in temp_logger.log_file.read_text(encoding="utf-8")


def test_main_requires_settings(monkeypatch):
    monkeypatch.setattr(config, "missing_settings", lambda: ["RAKUTEN_USER_ID"])
    assert main.main([]) == 1


def test_main_without_targets_does_not_open_browser_but_backs_up(run_env, tmp_path, monkeypatch):
    make_recipe_folder(tmp_path / "投稿素材", "卵焼き")
    run_env.posted = {"卵焼き"}

    def must_not_be_called():
        raise AssertionError("ブラウザを起動してはいけない")
    monkeypatch.setattr(main, "create_driver", must_not_be_called)

    assert main.main([]) == 0
    assert run_env.backups == [False]
    assert run_env.conn_class.closed


def test_main_posts_and_cleans_up(run_env, tmp_path, recorded):
    make_recipe_folder(tmp_path / "投稿素材", "卵焼き")
    make_recipe_folder(tmp_path / "投稿素材", "サラダ")
    run_env.posted = {"サラダ"}

    assert main.main([]) == 0
    assert run_env.poster.calls == [("卵焼き", False)]
    assert recorded == [("卵焼き", "https://recipe.rakuten.co.jp/recipe/1/")]
    assert run_env.driver_class.quit_called and run_env.conn_class.closed


def test_main_dry_run_with_folder_option(run_env, tmp_path):
    make_recipe_folder(tmp_path / "投稿素材", "卵焼き")
    make_recipe_folder(tmp_path / "投稿素材", "サラダ")

    assert main.main(["--dry-run", "--folder", "サラダ"]) == 0
    assert run_env.poster.calls == [("サラダ", True)]
    assert run_env.backups == []  # お試し実行ではバックアップしない


def test_main_returns_1_when_post_fails(run_env, tmp_path):
    make_recipe_folder(tmp_path / "投稿素材", "卵焼き")
    run_env.poster = FakePoster(fail={"卵焼き"})
    assert main.main([]) == 1


def test_main_returns_1_when_login_fails(run_env, tmp_path, monkeypatch):
    make_recipe_folder(tmp_path / "投稿素材", "卵焼き")
    monkeypatch.setattr(main, "login_to_rakuten", lambda driver: None)
    assert main.main([]) == 1


def test_main_returns_1_when_backup_fails(run_env, tmp_path, monkeypatch):
    (tmp_path / "投稿素材").mkdir()
    monkeypatch.setattr(backup, "backup_if_due", lambda force=False: False)
    assert main.main([]) == 1


def test_main_backup_option(run_env):  # 投稿素材フォルダが無くてもバックアップだけは取れる
    assert main.main(["--backup"]) == 0
    assert run_env.backups == [True]
