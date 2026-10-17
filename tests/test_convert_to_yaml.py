from tools import convert_to_yaml
from recipe_poster.recipes.model import load_recipe_yaml

RECIPE_TEXT = """■レシピタイトル（25文字以内）
豚の角煮の甘辛煮込み
■調理時間
約1時間30分
■費用
約800〜1000円
■レシピコメント
トロトロの豚肉です。
■材料（3人分）
- 豚バラ肉：300g
- 水 300ml
■作り方
1. 豚肉を切る。
2. 煮込む。
■きっかけ
特別な日に。
■おいしくなるコツ
前日から作り置きする。
■カテゴリ
和食・副菜 / 夕食
"""


def make_folder(tmp_path, name="豚の角煮", text=RECIPE_TEXT):
    folder = tmp_path / name
    folder.mkdir()
    (folder / "IMG_1.jpg").write_bytes(b"jpg")
    (folder / "recipe.txt").write_text(text, encoding="utf-8")
    return folder


def test_convert_folder(tmp_path):
    folder = make_folder(tmp_path)

    assert convert_to_yaml.convert_folder(folder)

    recipe = load_recipe_yaml(folder / "recipe.yaml")
    assert recipe.title == "豚の角煮の甘辛煮込み"
    assert recipe.dish_name == "豚の角煮"
    assert recipe.servings == 3
    assert recipe.cook_minutes == 90
    assert recipe.cost_yen == 900
    assert [(i.name, i.amount) for i in recipe.ingredients] == [("豚バラ肉", "300g"), ("水", "300ml")]
    assert [s.text for s in recipe.steps] == ["豚肉を切る。", "煮込む。"]
    assert recipe.tags == ["和食・副菜"] and recipe.meal == ["夕食"]
    assert recipe.main_image == "IMG_1.jpg"
    assert (folder / "recipe.txt").exists()  # 元のテキストは残す


def test_convert_folder_keeps_existing_yaml(tmp_path):
    folder = make_folder(tmp_path)
    (folder / "recipe.yaml").write_text("手で直した内容", encoding="utf-8")

    assert convert_to_yaml.convert_folder(folder)
    assert (folder / "recipe.yaml").read_text(encoding="utf-8") == "手で直した内容"

    assert convert_to_yaml.convert_folder(folder, overwrite=True)
    assert load_recipe_yaml(folder / "recipe.yaml").title == "豚の角煮の甘辛煮込み"


def test_convert_folder_reports_items_to_fix(tmp_path, temp_logger):
    folder = make_folder(tmp_path, text=RECIPE_TEXT.replace("約1時間30分", "じっくり"))

    assert not convert_to_yaml.convert_folder(folder)

    assert not (folder / "recipe.yaml").exists()
    log = temp_logger.log_file.read_text(encoding="utf-8")
    assert "cook_minutes（調理時間（分）） は1以上の整数で書いてください（現在: 'じっくり'）" in log


def test_main_with_folder_without_text(tmp_path):
    (tmp_path / "空").mkdir()
    assert convert_to_yaml.main([str(tmp_path / "空")]) == 1
