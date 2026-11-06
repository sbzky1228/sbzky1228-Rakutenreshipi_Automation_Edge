"""
LINE通知 - LINE Messaging API のプッシュメッセージで、自分のLINEにテキストを送る

（LINE Notify は 2025年3月末で終了したため、LINE公式アカウントの Messaging API を使う）
設定は .env の LINE_CHANNEL_ACCESS_TOKEN と LINE_USER_ID。どちらも未設定なら送らない。
"""
import json
import urllib.error
import urllib.request
import uuid

from recipe_poster import config
from recipe_poster.logger import get_logger

PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_TEXT_LENGTH = 5000  # テキストメッセージ1件の上限文字数
TIMEOUT_SECONDS = 15


def is_enabled() -> bool:
    """LINE通知の設定があるか（片方だけのときは設定漏れとしてログに残す）"""
    token, user_id = config.LINE_CHANNEL_ACCESS_TOKEN, config.LINE_USER_ID
    if token and user_id:
        return True
    if token or user_id:
        missing = 'LINE_USER_ID' if token else 'LINE_CHANNEL_ACCESS_TOKEN'
        get_logger().warning(f"LINE通知: .env の {missing} が未設定のため通知しません")
    return False


def _shorten(text: str) -> str:
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    suffix = "\n…（長いため省略。続きはログを見てください）"
    return text[:MAX_TEXT_LENGTH - len(suffix)] + suffix


def send_line_message(text: str) -> bool:
    """LINEにテキストを送り、送れたら True を返す（失敗は理由をログに残して False）"""
    logger = get_logger()
    body = json.dumps({
        "to": config.LINE_USER_ID,
        "messages": [{"type": "text", "text": _shorten(text)}],
    }).encode("utf-8")
    request = urllib.request.Request(PUSH_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
        "X-Line-Retry-Key": str(uuid.uuid4()),  # 再送しても二重に届かないようにするキー
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
            pass
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        hint = {
            400: "（LINE_USER_ID が正しいか確認してください）",
            401: "（LINE_CHANNEL_ACCESS_TOKEN が正しいか確認してください）",
            429: "（送信できる月の上限に達した可能性があります）",
        }.get(e.code, "")
        logger.error(f"LINE通知を送れませんでした: HTTP {e.code} {detail}{hint}")
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.error(f"LINE通知を送れませんでした: {e.__class__.__name__}: {e}")
        return False
    logger.info("LINEに通知しました")
    return True
