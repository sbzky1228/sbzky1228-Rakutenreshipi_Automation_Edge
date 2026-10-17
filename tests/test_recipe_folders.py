import pytest
import yaml

from recipe_folders import find_recipe_folders, load_recipe
from recipe_model import RecipeFormatError

RECIPE_TEXT = """■レシピタイトル
txtのタイトル
■調理時間
10分
■レシピコメント
簡単です。
■材料
- 卵: 2個
■作り方
1. 焼く。
■きっかけ
朝ごはんに。
"""

RECIPE_YAML = {
    "schema_version": 1, "title": "yamlのタイトル", "description": "簡単です。", "servings": 2,
    "cook_minutes": 10, "ingredients": [{"name": "卵", "amount": "2個"}], "steps": ["焼く。"],
    "story": "朝ごはんに。", "images": {"main": "main.jpg"},
}


def make_folder(base, name, files):
    folder = base / name
    folder.mkdir(parents=True)
    for file_name, content in files.items():
        (folder / file_name).write_text(content, encoding="utf-8")
    return folder


def test_find_recipe_folders(tmp_path):
    base = tmp_path / "投稿素材"  # tmp_path 直下にはテスト用の logs ができるため分ける
    make_folder(base, "豚の角煮", {})
    make_folder(base, "チョレギサラダ", {})
    (base / "メモ.txt").write_text("x", encoding="utf-8")  # フォルダ以外は無視
    assert [f.name for f in find_recipe_folders(base)] == sorted(["豚の角煮", "チョレギサラダ"])


def test_find_recipe_folders_missing_base(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_recipe_folders(tmp_path / "無い")


def test_yaml_is_preferred_over_text(tmp_path):
    folder = make_folder(tmp_path, "卵焼き", {
        "recipe.txt": RECIPE_TEXT, "IMG_1.JPG": "jpg", "main.jpg": "jpg",
        "recipe.yaml": yaml.safe_dump(RECIPE_YAML, allow_unicode=True),
    })
    assert load_recipe(folder).title == "yamlのタイトル"


def test_invalid_yaml_does_not_fall_back_to_text(tmp_path):
    folder = make_folder(tmp_path, "卵焼き", {
        "recipe.txt": RECIPE_TEXT, "main.jpg": "jpg",
        "recipe.yaml": yaml.safe_dump(dict(RECIPE_YAML, title=""), allow_unicode=True),
    })
    with pytest.raises(RecipeFormatError) as e:
        load_recipe(folder)
    assert "title（タイトル） が書かれていません" in e.value.errors


def test_text_is_used_without_yaml(tmp_path):
    folder = make_folder(tmp_path, "卵焼き", {"recipe.txt": RECIPE_TEXT, "IMG_1.JPG": "jpg"})
    recipe = load_recipe(folder)
    assert recipe.title == "txtのタイトル"
    assert recipe.main_image == "IMG_1.JPG"
    assert recipe.dish_name == "卵焼き"


@pytest.mark.parametrize("files, message", [
    ({"IMG_1.jpg": "jpg"}, "recipe.yaml も .txt もありません"),
    ({"recipe.txt": RECIPE_TEXT}, "写真（.jpg / .jpeg / .png）がありません"),
])
def test_missing_files(tmp_path, files, message):
    folder = make_folder(tmp_path, "卵焼き", files)
    with pytest.raises(RecipeFormatError) as e:
        load_recipe(folder)
    assert e.value.errors == [message]


def test_multiple_text_files_uses_first_and_warns(tmp_path, temp_logger):
    folder = make_folder(tmp_path, "卵焼き", {"a.txt": RECIPE_TEXT, "b.txt": "", "IMG_1.jpg": "jpg"})
    assert load_recipe(folder).title == "txtのタイトル"
    assert "a.txt を使います" in temp_logger.log_file.read_text(encoding="utf-8")
