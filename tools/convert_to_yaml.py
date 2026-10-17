"""
recipe.txt → recipe.yaml 変換

レシピフォルダの recipe.txt（■見出し形式）を読み取り、同じフォルダに recipe.yaml を作る。
元の recipe.txt はそのまま残す（recipe.yaml ができると、投稿では recipe.yaml が使われる）。

使い方（プロジェクト直下で実行）:
    python tools/convert_to_yaml.py                  投稿素材フォルダのすべてのレシピを変換
    python tools/convert_to_yaml.py <フォルダ> ...    指定したレシピフォルダだけ変換
    python tools/convert_to_yaml.py --overwrite      既にある recipe.yaml も作り直す
"""
import argparse
import sys
from pathlib import Path

# tools フォルダから直接起動しても、プロジェクト直下の recipe_poster を import できるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recipe_poster import config
from recipe_poster.logger import get_logger
from recipe_poster.recipes.folders import find_recipe_folders, find_text_and_image
from recipe_poster.recipes.model import RECIPE_FILE_NAME, RecipeFormatError, dump_recipe_yaml
from recipe_poster.recipes.text import load_recipe_text


def convert_folder(folder: Path, overwrite: bool = False) -> bool:
    """1つのレシピフォルダを変換する。作成できた（または既にある）ならTrue"""
    logger = get_logger()
    folder = Path(folder)
    yaml_path = folder / RECIPE_FILE_NAME
    if yaml_path.exists() and not overwrite:
        logger.info(f"{folder.name}: {RECIPE_FILE_NAME} は既にあるため作りません（作り直す場合は --overwrite）")
        return True
    try:
        text, image = find_text_and_image(folder)
        recipe = load_recipe_text(text, image.name, folder.name)
    except (RecipeFormatError, OSError, UnicodeDecodeError) as e:
        logger.error(f"{folder.name}: {RECIPE_FILE_NAME} を作れません。次の点を直してください")
        for error in getattr(e, "errors", [str(e)]):
            logger.error(f"  - {error}")
        return False
    yaml_path.write_text(dump_recipe_yaml(recipe), encoding="utf-8")
    logger.info(f"{folder.name}: {RECIPE_FILE_NAME} を作りました")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="recipe.txt から recipe.yaml を作ります")
    parser.add_argument("folders", nargs="*", type=Path, help="レシピフォルダ（省略時は投稿素材のすべて）")
    parser.add_argument("--overwrite", action="store_true", help="既にある recipe.yaml も作り直す")
    args = parser.parse_args(argv)

    try:
        folders = args.folders or find_recipe_folders(Path(config.BASE_FOLDER))
    except FileNotFoundError as e:
        get_logger().error(f"{e}（.env の base_folder_path を確認してください）")
        return 1
    results = [convert_folder(folder, args.overwrite) for folder in folders]
    get_logger().info(f"終了しました: 成功 {results.count(True)}件 / 要確認 {results.count(False)}件")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
