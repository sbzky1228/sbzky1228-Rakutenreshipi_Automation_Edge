import pytest

from recipe_model import Ingredient, RecipeFormatError, Step
from recipe_text import load_recipe_text, parse_minutes, parse_recipe_text, parse_yen, split_category

# ChatGPTで作る標準の形式（■見出し、材料は「名前: 分量」）
SQUARE_FORMAT = """■レシピタイトル（25文字以内）
チャーシューチャーハン

■調理時間
15分

■費用
約600円

■レシピコメント（80文字以内）
余ったチャーシューを使った簡単チャーハン。

■材料（2人分）
- ご飯: 400g
- チャーシュー: 150g
- 塩: 少々

■作り方
1. チャーシューを1cm角に切る。
2. 全ての材料をフライパンで炒める。
3. 材料費を抑えたい時は卵を減らす。

■きっかけ（120文字以内）
余っていたチャーシューを使いました。

■おいしくなるコツ（120文字以内）
冷ご飯を使うとパラっと仕上がります。

■カテゴリ
ご飯・丼もの / 夕飯
"""

# 古い形式（**・見出し：**、材料は「名前 … 分量」）
BOLD_FORMAT = """**・レシピタイトル（25文字以内）：**
簡単カフェ風♪エッグベネディクト

**・調理時間：**
約１５〜２０分

**・費用：**
約800〜1000円

**・レシピコメント（80文字以内）：**
カフェ風の贅沢朝ごはん！

**・材料（3人分）：**

* イングリッシュマフィン … 2個
* オランデーズソース（市販または自作） … 適量

**・作り方：**

1. 鍋に湯を沸かす。
2. 卵を割り入れる。

**・きっかけ（120文字以内）：**
カフェで食べた味を再現しました。

**・カテゴリ：**
朝食 / 洋食
"""


def test_parse_square_format():
    data = parse_recipe_text(SQUARE_FORMAT)
    assert data["title"] == "チャーシューチャーハン"
    assert data["cook_minutes"] == 15
    assert data["cost_yen"] == 600
    assert data["servings"] == 2
    assert data["ingredients"] == [{"name": "ご飯", "amount": "400g"}, {"name": "チャーシュー", "amount": "150g"},
                                   {"name": "塩", "amount": "少々"}]
    assert data["tags"] == ["ご飯・丼もの"] and data["meal"] == ["夕食"]


def test_step_containing_section_word_is_not_a_header():
    # 「材料」「費用」を含む作り方の行で見出しが切り替わらない
    data = parse_recipe_text(SQUARE_FORMAT)
    assert [s["text"] for s in data["steps"]] == [
        "チャーシューを1cm角に切る。",
        "全ての材料をフライパンで炒める。",
        "材料費を抑えたい時は卵を減らす。",
    ]
    assert len(data["ingredients"]) == 3


def test_parse_bold_format():
    data = parse_recipe_text(BOLD_FORMAT)
    assert data["title"] == "簡単カフェ風♪エッグベネディクト"
    assert data["servings"] == 3
    assert data["cook_minutes"] == 20       # 範囲は長い方
    assert data["cost_yen"] == 900          # 範囲は平均
    assert data["ingredients"][1] == {"name": "オランデーズソース（市販または自作）", "amount": "適量"}
    assert data["meal"] == ["朝食"] and data["tags"] == ["洋食"]
    assert "tips" not in data               # 書かれていない項目は入れない


def test_header_with_inline_value_and_multiline_text():
    data = parse_recipe_text("■調理時間：10分\n■費用: 300円\n■レシピコメント\n1行目\n2行目\n")
    assert data["cook_minutes"] == 10
    assert data["cost_yen"] == 300
    assert data["description"] == "1行目\n2行目"


def test_unreadable_cooking_time_is_kept_as_text():
    assert parse_recipe_text("■調理時間\nじっくり\n")["cook_minutes"] == "じっくり"


@pytest.mark.parametrize("line, expected", [
    ("- 赤玉ねぎ 1/4個", {"name": "赤玉ねぎ", "amount": "1/4個"}),
    ("- 胡麻 1 tablespoon", {"name": "胡麻", "amount": "1 tablespoon"}),
    ("- わかめ（乾燥） 大さじ1", {"name": "わかめ（乾燥）", "amount": "大さじ1"}),
    ("- 豚バラ肉：300g", {"name": "豚バラ肉", "amount": "300g"}),
    ("- 塩少々", {"name": "塩少々", "amount": ""}),
])
def test_ingredient_separators(line, expected):
    assert parse_recipe_text(f"■材料\n{line}\n")["ingredients"] == [expected]


@pytest.mark.parametrize("step", ["1. 切る。", "1) 切る。", "① 切る。", "・切る。", "１．切る。"])
def test_step_numbers_are_removed(step):
    assert parse_recipe_text(f"■作り方\n{step}\n")["steps"] == [{"text": "切る。"}]


@pytest.mark.parametrize("text, expected", [
    ("5分", 5), ("約15〜20分", 20), ("１５分", 15), ("1時間", 60), ("1時間30分", 90),
    ("1時間半", 90), ("約120分", 120), ("すぐ", None),
])
def test_parse_minutes(text, expected):
    assert parse_minutes(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("約600円", 600), ("約800〜1000円", 900), ("1,500円", 1500), ("不明", None),
])
def test_parse_yen(text, expected):
    assert parse_yen(text) == expected


@pytest.mark.parametrize("category, tags, meal", [
    ("朝食 / 洋食 / カフェ風", ["洋食", "カフェ風"], ["朝食"]),
    ("ご飯・丼もの", ["ご飯・丼もの"], []),
    ("夕飯、和食", ["和食"], ["夕食"]),
    ("", [], []),
])
def test_split_category(category, tags, meal):
    assert split_category(category) == (tags, meal)


def test_load_recipe_text(tmp_path):
    path = tmp_path / "recipe.txt"
    path.write_text(SQUARE_FORMAT, encoding="utf-8-sig")  # BOM付きも読める
    recipe = load_recipe_text(path, "IMG_1.jpg", "チャーシューチャーハン")
    assert recipe.dish_name == "チャーシューチャーハン"
    assert recipe.main_image == "IMG_1.jpg"
    assert recipe.ingredients[0] == Ingredient("ご飯", "400g")
    assert recipe.steps[0] == Step("チャーシューを1cm角に切る。")
    assert recipe.story == "余っていたチャーシューを使いました。"


def test_load_recipe_text_reports_problems(tmp_path):
    path = tmp_path / "recipe.txt"
    path.write_text("■レシピタイトル\n卵焼き\n■調理時間\nじっくり\n", encoding="utf-8")
    with pytest.raises(RecipeFormatError) as e:
        load_recipe_text(path, "IMG_1.jpg", "卵焼き")
    assert "cook_minutes（調理時間（分）） は1以上の整数で書いてください（現在: 'じっくり'）" in e.value.errors
    assert "ingredients（材料）が書かれていません" in e.value.errors
