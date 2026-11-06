import io
import json
import urllib.error

from recipe_poster import config
from recipe_poster.notify import line
from recipe_poster.notify.report import RunReport


def use_line_settings(monkeypatch):
    """.env の内容に関係なく、テスト用の設定にする"""
    monkeypatch.setattr(config, "LINE_CHANNEL_ACCESS_TOKEN", "secret-token")
    monkeypatch.setattr(config, "LINE_USER_ID", "U123")


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_line_message_posts_push_request(monkeypatch):
    use_line_settings(monkeypatch)
    sent = []
    monkeypatch.setattr(line.urllib.request, "urlopen",
                        lambda request, timeout: sent.append(request) or FakeResponse())

    assert line.send_line_message("こんにちは") is True
    request = sent[0]
    assert request.full_url == "https://api.line.me/v2/bot/message/push"
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert request.get_header("X-line-retry-key")
    assert json.loads(request.data) == {"to": "U123", "messages": [{"type": "text", "text": "こんにちは"}]}


def test_send_line_message_shortens_long_text(monkeypatch):
    use_line_settings(monkeypatch)
    sent = []
    monkeypatch.setattr(line.urllib.request, "urlopen",
                        lambda request, timeout: sent.append(request) or FakeResponse())
    line.send_line_message("あ" * 6000)
    text = json.loads(sent[0].data)["messages"][0]["text"]
    assert len(text) == line.MAX_TEXT_LENGTH
    assert text.endswith("続きはログを見てください）")


def test_send_line_message_logs_http_error_without_token(monkeypatch, temp_logger):
    use_line_settings(monkeypatch)
    def unauthorized(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b'{"message":"Authentication failed"}'))
    monkeypatch.setattr(line.urllib.request, "urlopen", unauthorized)

    assert line.send_line_message("テスト") is False
    log = temp_logger.log_file.read_text(encoding="utf-8")
    assert "HTTP 401" in log and "LINE_CHANNEL_ACCESS_TOKEN が正しいか" in log
    assert "secret-token" not in log


def test_send_line_message_network_error(monkeypatch):
    use_line_settings(monkeypatch)
    def offline(request, timeout):
        raise urllib.error.URLError("接続できません")
    monkeypatch.setattr(line.urllib.request, "urlopen", offline)
    assert line.send_line_message("テスト") is False


def test_is_enabled(monkeypatch, temp_logger):
    monkeypatch.setattr(config, "LINE_CHANNEL_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "LINE_USER_ID", "")
    assert line.is_enabled() is False

    monkeypatch.setattr(config, "LINE_CHANNEL_ACCESS_TOKEN", "token")
    assert line.is_enabled() is False
    assert "LINE_USER_ID が未設定" in temp_logger.log_file.read_text(encoding="utf-8")

    monkeypatch.setattr(config, "LINE_USER_ID", "U123")
    assert line.is_enabled() is True


def test_report_message_limits_error_lines():
    report = RunReport(posted=[("卵焼き", "https://example/1")])
    errors = [f"エラー{i}" for i in range(8)]
    message = report.to_message(errors, "rakuten_recipe_1.log")
    assert "⚠ エラー: 8件" in message
    assert "・エラー4" in message and "・エラー5" not in message
    assert "…ほか3件" in message
    assert message.endswith("ログ: rakuten_recipe_1.log")


def test_report_has_news():
    assert RunReport().has_news([]) is False
    assert RunReport().has_news(["エラー"]) is True
    assert RunReport(failed=["卵焼き"]).has_news([]) is True
