"""
設定ファイル - .env の読み込みと定数の管理

- 楽天ログイン情報
- 投稿素材フォルダ
- データベース接続情報・バックアップ
- ログの保存先
- 楽天レシピのURL
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# プログラムのフォルダ（.env・logsの基準）
# - .exe実行時: RakutenRecipe_Auto_Post.exe と同じフォルダ
# - python main.py 実行時: プロジェクト直下（このファイルは recipe_poster フォルダの中にある）
# タスクスケジューラ等で作業フォルダが変わっても同じ場所を使うよう固定する
APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, 'frozen', False)
    else Path(__file__).resolve().parent.parent
)

# プログラムのフォルダの .env を優先し、無ければ作業フォルダの .env を読む
_dotenv_file = APP_DIR / '.env'
load_dotenv(_dotenv_file if _dotenv_file.exists() else Path.cwd() / '.env')


def _env(name: str) -> str:
    return os.getenv(name, '').strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value.isdigit() else default


def _env_path(name: str, default: Path) -> Path:
    """フォルダの設定（相対パスはプログラムのフォルダ基準。未指定なら default）"""
    value = _env(name)
    return (APP_DIR / value).resolve() if value else default


# ============================================================
# 楽天ログイン情報
# ============================================================
RAKUTEN_USER_ID = _env('RAKUTEN_USER_ID')
RAKUTEN_PASSWORD = _env('RAKUTEN_PASSWORD')

# ============================================================
# フォルダ
# ============================================================
# 投稿素材（レシピごとのフォルダ）を置くフォルダ。投稿してもフォルダは移動しない
BASE_FOLDER = _env('base_folder_path')

# ============================================================
# データベース（PostgreSQL）
# ============================================================
DB_SETTINGS = {
    'dbname': _env('DB_NAME'),
    'user': _env('DB_USER'),
    'password': _env('DB_PASSWORD'),
    'host': _env('DB_HOST'),
    'port': _env('DB_PORT'),
}

# データベースのバックアップ（pg_dump）
BACKUP_DIR = _env_path('BACKUP_DIR', APP_DIR / 'backup')         # 保存先
BACKUP_INTERVAL_DAYS = _env_int('BACKUP_INTERVAL_DAYS', 7)        # 何日ごとに取るか
BACKUP_KEEP = _env_int('BACKUP_KEEP', 10)                         # 残す個数
PG_DUMP_PATH = _env('PG_DUMP_PATH')  # pg_dump.exe の場所（未指定なら自動で探す）

# ============================================================
# Edge WebDriver
# 通常は Selenium が Edge のバージョンに合うドライバを自動で用意する。
# オフライン等で自動取得できない場合だけ、DRIVER_PATH の msedgedriver.exe を使う
# ============================================================
DRIVER_PATH = _env('DRIVER_PATH')

# ============================================================
# ログの保存先（相対パスはプログラムのフォルダ基準。未指定ならプログラムのフォルダの logs）
# ============================================================
LOG_DIR = _env_path('LOG_DIR', APP_DIR / 'logs')

# ============================================================
# 楽天レシピ
# ============================================================
RECIPE_TOP_URL = "https://recipe.rakuten.co.jp"
RECIPE_LOGIN_URL = f"{RECIPE_TOP_URL}/login/"
RECIPE_MYPAGE_URL = f"{RECIPE_TOP_URL}/mypage/"
RECIPE_POST_URL = f"{RECIPE_TOP_URL}/recipe/post/"


def missing_settings() -> list[str]:
    """未設定の必須項目（.envの項目名）を返す"""
    required = {
        'RAKUTEN_USER_ID': RAKUTEN_USER_ID,
        'RAKUTEN_PASSWORD': RAKUTEN_PASSWORD,
        'base_folder_path': BASE_FOLDER,
        'DB_NAME': DB_SETTINGS['dbname'],
        'DB_USER': DB_SETTINGS['user'],
        'DB_HOST': DB_SETTINGS['host'],
    }
    return [name for name, value in required.items() if not value]
