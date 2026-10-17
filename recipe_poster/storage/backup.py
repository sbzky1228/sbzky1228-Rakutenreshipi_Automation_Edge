"""
データベースのバックアップ - pg_dump でデータベースの中身を SQL ファイルに保存する

- 保存先は .env の BACKUP_DIR（未指定ならプログラムのフォルダの backup）。OneDrive 配下なら自動でクラウドにも残る
- 前回のバックアップから BACKUP_INTERVAL_DAYS 日以上たっていれば、投稿の処理のあとに自動で取る
- 新しい順に BACKUP_KEEP 個だけ残し、古いものは消す

戻し方（例）:
    psql -U postgres -d RakutenRecipe_information -f backup\\RakutenRecipe_information_20261017_180000.sql
"""
import datetime
import glob
import os
import shutil
import subprocess
from pathlib import Path

from recipe_poster import config
from recipe_poster.logger import get_logger

BACKUP_PREFIX = "RakutenRecipe_information_"
# pg_dump の場所の候補（PATH に無い場合。新しいバージョンを優先）
_PG_DUMP_PATTERN = r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe"


def find_pg_dump() -> str | None:
    """pg_dump の場所を探す（.env の PG_DUMP_PATH → PATH → PostgreSQL の標準のインストール先）"""
    if config.PG_DUMP_PATH:
        return config.PG_DUMP_PATH if Path(config.PG_DUMP_PATH).is_file() else None
    found = shutil.which("pg_dump")
    if found:
        return found
    candidates = sorted(glob.glob(_PG_DUMP_PATTERN),
                        key=lambda p: [int(x) if x.isdigit() else 0 for x in Path(p).parts[-3].split(".")])
    return candidates[-1] if candidates else None


def list_backups(backup_dir: Path) -> list[Path]:
    """バックアップファイルを古い順に返す"""
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob(f"{BACKUP_PREFIX}*.sql"))


def is_due(backup_dir: Path, interval_days: int, now: datetime.datetime | None = None) -> bool:
    """前回のバックアップから interval_days 日以上たっているか（バックアップが無ければTrue）"""
    backups = list_backups(backup_dir)
    if not backups:
        return True
    now = now or datetime.datetime.now()
    last = datetime.datetime.fromtimestamp(backups[-1].stat().st_mtime)
    return now - last >= datetime.timedelta(days=interval_days)


def remove_old_backups(backup_dir: Path, keep: int) -> list[Path]:
    """新しい順に keep 個を残して古いバックアップを消し、消したファイルを返す"""
    old = list_backups(backup_dir)[:-keep] if keep > 0 else []
    for path in old:
        path.unlink()
    return old


def run_backup(backup_dir: Path | None = None) -> Path:
    """バックアップを取り、作ったファイルのパスを返す。失敗したら RuntimeError"""
    backup_dir = Path(backup_dir or config.BACKUP_DIR)
    pg_dump = find_pg_dump()
    if not pg_dump:
        raise RuntimeError("pg_dump が見つかりません（.env の PG_DUMP_PATH に pg_dump.exe の場所を書いてください）")

    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"{BACKUP_PREFIX}{datetime.datetime.now():%Y%m%d_%H%M%S}.sql"
    settings = config.DB_SETTINGS
    command = [pg_dump, "--clean", "--if-exists", "--no-owner", "--encoding=UTF8", "-f", str(path)]
    for option, key in (("-h", "host"), ("-p", "port"), ("-U", "user")):
        if settings[key]:
            command += [option, settings[key]]
    command.append(settings["dbname"])

    env = dict(os.environ, PGPASSWORD=settings["password"]) if settings["password"] else None
    result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=300)
    if result.returncode != 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump が失敗しました: {result.stderr.strip()}")
    return path


def backup_if_due(force: bool = False) -> bool:
    """
    必要ならバックアップを取る（force=True なら日数に関係なく取る）。
    失敗した場合だけ False を返す（取る必要が無かった場合も True）。
    """
    logger = get_logger()
    backup_dir = Path(config.BACKUP_DIR)
    if not force and not is_due(backup_dir, config.BACKUP_INTERVAL_DAYS):
        return True
    try:
        path = run_backup(backup_dir)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        logger.error(f"データベースのバックアップに失敗しました: {e}")
        return False
    logger.info(f"データベースをバックアップしました: {path}")
    for old in remove_old_backups(backup_dir, config.BACKUP_KEEP):
        logger.info(f"古いバックアップを削除しました: {old.name}")
    return True
