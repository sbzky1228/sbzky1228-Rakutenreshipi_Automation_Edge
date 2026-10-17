"""
楽天レシピ自動投稿 - メイン

1. 投稿素材フォルダのレシピ（recipe.yaml、無ければ recipe.txt）のうち、
   データベースの投稿履歴で楽天レシピに未投稿のものを読み込み、内容をチェックする
2. 楽天レシピにログインし、1件ずつ入力して公開申請する
3. 投稿できたレシピを投稿履歴に記録する（フォルダは移動しない）
4. 前回のバックアップから一定日数たっていれば、データベースをバックアップする

使い方:
    python main.py                       未投稿のレシピをすべて投稿する
    python main.py --limit 1             1件だけ投稿する
    python main.py --folder 豚の角煮      指定したフォルダだけ投稿する（複数指定可）
    python main.py --dry-run             入力まで行い、公開申請・記録・バックアップはしない（動作確認用）
    python main.py --backup              データベースのバックアップだけを取る
"""
import argparse
import sys
from pathlib import Path

from recipe_poster import config
from recipe_poster.logger import get_logger
from recipe_poster.rakuten.browser import create_driver
from recipe_poster.rakuten.convert import RakutenPost, to_rakuten_post, validate_rakuten_post
from recipe_poster.rakuten.login import login_to_rakuten
from recipe_poster.rakuten.post import RecipePoster
from recipe_poster.recipes.folders import find_recipe_folders, load_recipe
from recipe_poster.recipes.model import RecipeFormatError
from recipe_poster.storage import backup, database
from recipe_poster.storage.database import PLATFORM_RAKUTEN


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="楽天レシピに投稿素材のレシピを自動投稿します")
    parser.add_argument("--limit", type=int, default=None, help="投稿する件数の上限")
    parser.add_argument("--folder", action="append", default=None, metavar="フォルダ名",
                        help="指定したフォルダだけ投稿する（複数指定可）")
    parser.add_argument("--dry-run", action="store_true",
                        help="入力まで行い、公開申請・投稿履歴の記録・バックアップはしない")
    parser.add_argument("--backup", action="store_true", help="データベースのバックアップだけを取る")
    return parser.parse_args(argv)


def load_targets(base_folder: Path, posted_keys: set[str]) -> list[RakutenPost]:
    """
    楽天レシピに未投稿のレシピを読み込み、投稿できる内容のものだけを返す
    （内容に問題のあるものは理由をログに残して除外する）
    """
    logger = get_logger()
    targets = []
    skipped = 0
    for folder in find_recipe_folders(base_folder):
        if folder.name in posted_keys:
            skipped += 1
            continue
        try:
            post = to_rakuten_post(load_recipe(folder), folder)
            errors = validate_rakuten_post(post)
        except RecipeFormatError as e:
            errors = e.errors
        if errors:
            logger.error(f"{folder.name}: 内容に問題があるため投稿しません")
            for error in errors:
                logger.error(f"  - {error}")
            continue
        targets.append(post)
    if skipped:
        logger.info(f"楽天レシピに投稿済み（投稿履歴あり）のため対象外: {skipped}件")
    return targets


def _record(conn, post: RakutenPost, url: str):
    """投稿履歴に記録する。失敗しても投稿は続ける（次回は楽天レシピ上のタイトルで投稿済みと判定される）"""
    logger = get_logger()
    try:
        database.add_post(conn, post.key, post.title, PLATFORM_RAKUTEN, url)
        logger.info(f"{post.key}: 投稿履歴に記録しました（楽天レシピの累計 {database.count_posts(conn, PLATFORM_RAKUTEN)}件）")
    except Exception as e:
        logger.error(f"{post.key}: 投稿履歴に記録できませんでした: {e}")


def post_recipes(targets: list[RakutenPost], poster: RecipePoster, conn, dry_run: bool,
                 limit: int | None = None) -> tuple[int, int]:
    """レシピを順に投稿し、(投稿できた件数, 失敗した件数) を返す。limit 件を試したら終わる"""
    logger = get_logger()
    on_site = poster.posted_recipes()
    succeeded = failed = 0

    for post in targets:
        if post.title in on_site:
            # 投稿履歴に無いが楽天レシピには同じタイトルがある（記録漏れ、または手動で投稿したもの）
            if dry_run:
                logger.warning(f"{post.key}: 「{post.title}」は楽天レシピに投稿済みのため投稿しません")
            else:
                logger.warning(f"{post.key}: 「{post.title}」は楽天レシピに投稿済みのため投稿せず、投稿履歴に記録します")
                _record(conn, post, on_site[post.title])
            continue
        if limit is not None and succeeded + failed >= limit:
            break

        logger.info(f"{post.key}: 投稿を始めます（タイトル: {post.title}）")
        url = poster.post(post, dry_run=dry_run)
        if url is None:
            failed += 1
            continue
        succeeded += 1
        if not dry_run:
            _record(conn, post, url)

    return succeeded, failed


def run_posting(args: argparse.Namespace) -> int:
    """投稿の処理を行い、終了コード（0: 正常、1: 失敗あり）を返す"""
    logger = get_logger()
    conn = driver = None
    try:
        conn = database.connect()
        targets = load_targets(Path(config.BASE_FOLDER), database.posted_keys(conn, PLATFORM_RAKUTEN))
        if args.folder:
            unknown = set(args.folder) - {post.key for post in targets}
            if unknown:
                logger.warning(f"投稿対象に無いフォルダ（投稿済み・内容に問題あり・存在しない）: {', '.join(sorted(unknown))}")
            targets = [post for post in targets if post.key in args.folder]
        if not targets:
            logger.info("投稿するレシピはありません")
            return 0
        logger.info(f"投稿対象: {len(targets)}件（{', '.join(post.key for post in targets)}）")

        driver = create_driver()
        member_id = login_to_rakuten(driver)
        if not member_id:
            return 1
        succeeded, failed = post_recipes(targets, RecipePoster(driver, member_id), conn, args.dry_run, args.limit)
        logger.info(f"終了しました: 成功 {succeeded}件 / 失敗 {failed}件")
        return 1 if failed else 0
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"処理を中断しました: {e.__class__.__name__}: {e}")
        return 1
    finally:
        if driver:
            driver.quit()
        if conn:
            conn.close()


def main(argv: list[str] | None = None) -> int:
    """終了コード（0: 正常、1: 失敗あり）を返す"""
    args = parse_args(argv)
    logger = get_logger()

    missing = config.missing_settings()
    if missing:
        logger.error(f".env に次の項目を設定してください: {', '.join(missing)}")
        return 1

    if args.backup:
        return 0 if backup.backup_if_due(force=True) else 1

    logger.info("楽天レシピ自動投稿を開始します" + ("（お試し実行）" if args.dry_run else ""))
    result = run_posting(args)
    # 定期実行のたびに確認し、前回から BACKUP_INTERVAL_DAYS 日以上たっていればバックアップする
    if not args.dry_run and not backup.backup_if_due():
        result = 1
    return result


if __name__ == "__main__":
    sys.exit(main())
