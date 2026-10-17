import datetime
import os
import subprocess

import pytest

import backup
import config

DB = {"dbname": "RakutenRecipe_information", "user": "postgres", "password": "secret", "host": "localhost", "port": "5432"}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """バックアップの設定を一時フォルダ・偽の pg_dump に差し替える"""
    pg_dump = tmp_path / "pg_dump.exe"
    pg_dump.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "PG_DUMP_PATH", str(pg_dump))
    monkeypatch.setattr(config, "DB_SETTINGS", dict(DB))
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backup")
    monkeypatch.setattr(config, "BACKUP_INTERVAL_DAYS", 7)
    monkeypatch.setattr(config, "BACKUP_KEEP", 2)
    return tmp_path


def make_backup(folder, name, days_ago=0):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{backup.BACKUP_PREFIX}{name}.sql"
    path.write_text("-- dump", encoding="utf-8")
    when = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).timestamp()
    os.utime(path, (when, when))
    return path


def fake_run(calls, returncode=0, stderr=""):
    def run(command, **kwargs):
        calls.append((command, kwargs))
        if returncode == 0:
            open(command[command.index("-f") + 1], "w").close()
        return subprocess.CompletedProcess(command, returncode, "", stderr)
    return run


def test_is_due(tmp_path):
    assert backup.is_due(tmp_path / "無い", 7)
    make_backup(tmp_path, "old", days_ago=3)
    assert not backup.is_due(tmp_path, 7)
    assert backup.is_due(tmp_path, 3)


def test_remove_old_backups(tmp_path):
    paths = [make_backup(tmp_path, f"2026101{i}_000000") for i in range(4)]
    assert backup.remove_old_backups(tmp_path, 2) == paths[:2]
    assert backup.list_backups(tmp_path) == paths[2:]


def test_run_backup_command(settings, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls))

    path = backup.run_backup()

    command, kwargs = calls[0]
    assert command[0] == config.PG_DUMP_PATH
    assert command[-1] == "RakutenRecipe_information"
    assert ["-h", "localhost"] == command[command.index("-h"):command.index("-h") + 2]
    assert ["-U", "postgres"] == command[command.index("-U"):command.index("-U") + 2]
    assert kwargs["env"]["PGPASSWORD"] == "secret"  # パスワードは引数ではなく環境変数で渡す
    assert path.parent == settings / "backup" and path.exists()


def test_run_backup_failure_removes_file(settings, monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run([], returncode=1, stderr="接続できません"))
    with pytest.raises(RuntimeError, match="pg_dump が失敗しました: 接続できません"):
        backup.run_backup()
    assert backup.list_backups(settings / "backup") == []


def test_run_backup_without_pg_dump(settings, monkeypatch):
    monkeypatch.setattr(config, "PG_DUMP_PATH", str(settings / "無い.exe"))
    with pytest.raises(RuntimeError, match="pg_dump が見つかりません"):
        backup.run_backup()


def test_backup_if_due_skips_recent_backup(settings, monkeypatch):
    make_backup(settings / "backup", "recent", days_ago=1)
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls))
    assert backup.backup_if_due()
    assert calls == []


def test_backup_if_due_runs_and_keeps_newest(settings, monkeypatch, temp_logger):
    for i in range(2):
        make_backup(settings / "backup", f"2026100{i}_000000", days_ago=10)
    monkeypatch.setattr(subprocess, "run", fake_run([]))

    assert backup.backup_if_due()

    names = [p.name for p in backup.list_backups(settings / "backup")]
    assert len(names) == 2 and names[0].endswith("20261001_000000.sql")  # 一番古いものが消える
    assert "データベースをバックアップしました" in temp_logger.log_file.read_text(encoding="utf-8")


def test_backup_if_due_reports_failure(settings, monkeypatch, temp_logger):
    monkeypatch.setattr(subprocess, "run", fake_run([], returncode=1, stderr="error"))
    assert not backup.backup_if_due(force=True)
    assert "バックアップに失敗しました" in temp_logger.log_file.read_text(encoding="utf-8")
