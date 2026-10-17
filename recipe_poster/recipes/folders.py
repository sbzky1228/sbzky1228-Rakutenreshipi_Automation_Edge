"""
レシピフォルダの管理 - 投稿素材フォルダからレシピを探して読み込む

投稿素材フォルダの中に、レシピごとのフォルダ（フォルダ名＝レシピの識別名）を置く。
投稿してもフォルダは移動しない。投稿済みかどうかはデータベースの投稿履歴で判定する。

レシピの内容は次の優先順で読む。
1. recipe.yaml があれば recipe.yaml だけを使う（内容に誤りがあればエラー。recipe.txt には切り替えない）
2. recipe.yaml が無ければ .txt（■見出し形式）と写真（.jpg / .jpeg / .png）を使う（移行期間用）
"""
from pathlib import Path

from recipe_poster.logger import get_logger
from recipe_poster.recipes.model import RECIPE_FILE_NAME, RecipeData, RecipeFormatError, load_recipe_yaml
from recipe_poster.recipes.text import load_recipe_text

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def find_recipe_folders(base_folder: Path) -> list[Path]:
    """投稿素材フォルダの中のレシピフォルダを名前順で返す"""
    base_folder = Path(base_folder)
    if not base_folder.is_dir():
        raise FileNotFoundError(f"投稿素材のフォルダがありません: {base_folder}")
    return sorted(f for f in base_folder.iterdir() if f.is_dir())


def _first_file(folder: Path, suffixes: tuple[str, ...]) -> Path | None:
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in suffixes)
    if len(files) > 1:
        get_logger().warning(f"{folder.name}: {'/'.join(suffixes)} が複数あるため {files[0].name} を使います")
    return files[0] if files else None


def find_text_and_image(folder: Path) -> tuple[Path, Path]:
    """recipe.txt 形式のフォルダから (.txt, 写真) を探す。どちらかが無ければ RecipeFormatError"""
    text = _first_file(folder, (".txt",))
    image = _first_file(folder, IMAGE_SUFFIXES)
    if not text:
        raise RecipeFormatError([f"{RECIPE_FILE_NAME} も .txt もありません"])
    if not image:
        raise RecipeFormatError(["写真（.jpg / .jpeg / .png）がありません"])
    return text, image


def load_recipe(folder: Path) -> RecipeData:
    """
    レシピフォルダからレシピを読み込む（recipe.yaml を優先、無ければ recipe.txt）。
    読めない・内容に誤りがある場合は RecipeFormatError（理由は errors に入る）。
    """
    folder = Path(folder)
    yaml_path = folder / RECIPE_FILE_NAME
    if yaml_path.exists():
        return load_recipe_yaml(yaml_path)

    text, image = find_text_and_image(folder)
    try:
        return load_recipe_text(text, image.name, folder.name)
    except (OSError, UnicodeDecodeError) as e:
        raise RecipeFormatError([f"{text.name} を読み込めません（UTF-8で保存してください）: {e}"]) from e
