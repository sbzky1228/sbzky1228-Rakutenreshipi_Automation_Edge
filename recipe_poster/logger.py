"""
ロギングモジュール - コンソールとログファイル（config.LOG_DIR）の両方へタイムスタンプ付きで出力する
"""
import datetime
import sys
from pathlib import Path
from recipe_poster.config import LOG_DIR

# コンソールがcp932の場合に「✓」等で UnicodeEncodeError となり処理が止まらないよう、
# 表示できない文字は置き換えて出力する
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(errors='replace')


class Logger:
    """ログ出力を管理するクラス"""

    def __init__(self, log_dir: Path = LOG_DIR):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = log_dir
        # ログファイル名（例: rakuten_recipe_20261012_143022.log）
        now = datetime.datetime.now()
        self.log_file = log_dir / f"rakuten_recipe_{now.strftime('%Y%m%d_%H%M%S')}.log"

    def log(self, message: str, level: str = 'INFO'):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def info(self, message: str):
        self.log(message, 'INFO')

    def warning(self, message: str):
        self.log(message, 'WARNING')

    def error(self, message: str):
        self.log(message, 'ERROR')


_shared_logger = None


def get_logger() -> Logger:
    """プログラム全体で共有するLoggerを取得する（初回呼び出し時に1つだけ作成し、同じログファイルに出力する）"""
    global _shared_logger
    if _shared_logger is None:
        _shared_logger = Logger()
    return _shared_logger
