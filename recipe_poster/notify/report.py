"""
実行結果のまとめ - 投稿できたレシピ・失敗したレシピ・エラーを集め、通知用の文章にする
"""
import datetime
from dataclasses import dataclass, field

MAX_ERROR_LINES = 5  # 通知に載せるエラーの件数（残りは件数だけ書く）


@dataclass
class RunReport:
    posted: list[tuple[str, str]] = field(default_factory=list)    # 公開申請した (タイトル, URL)
    recorded: list[tuple[str, str]] = field(default_factory=list)  # 楽天レシピに既にあり、履歴に記録だけした (タイトル, URL)
    failed: list[str] = field(default_factory=list)                # 投稿に失敗したタイトル

    def to_message(self, errors: list[str], log_name: str = "") -> str:
        """通知の文章を作る。errors はこの実行でログに出たエラー"""
        lines = [f"楽天レシピ自動投稿（{datetime.datetime.now():%Y/%m/%d %H:%M}）"]
        if self.posted:
            lines.append(f"\n✅ 公開申請しました: {len(self.posted)}件")
            for title, url in self.posted:
                lines += [f"・{title}", url]
        if self.recorded:
            lines.append(f"\n📝 楽天レシピに投稿済みのため履歴に記録だけしました: {len(self.recorded)}件")
            lines += [f"・{title}" for title, _ in self.recorded]
        if self.failed:
            lines.append(f"\n❌ 投稿に失敗しました: {len(self.failed)}件")
            lines += [f"・{title}" for title in self.failed]
        if errors:
            lines.append(f"\n⚠ エラー: {len(errors)}件")
            lines += [f"・{error}" for error in errors[:MAX_ERROR_LINES]]
            if len(errors) > MAX_ERROR_LINES:
                lines.append(f"…ほか{len(errors) - MAX_ERROR_LINES}件")
        if log_name and (self.failed or errors):
            lines.append(f"\nログ: {log_name}")
        return "\n".join(lines)

    def has_news(self, errors: list[str]) -> bool:
        """知らせることがあるか（投稿対象が無く、エラーも無い日は通知しない）"""
        return bool(self.posted or self.recorded or self.failed or errors)
