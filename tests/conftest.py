import sys
from pathlib import Path

import pytest

# プロジェクト直下の main・recipe_poster・tools を import できるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recipe_poster import logger  # noqa: E402


@pytest.fixture(autouse=True)
def temp_logger(tmp_path, monkeypatch):
    """テスト中のログはプロジェクトの logs ではなく一時フォルダに書く"""
    test_logger = logger.Logger(tmp_path / "logs")
    monkeypatch.setattr(logger, "_shared_logger", test_logger)
    return test_logger
