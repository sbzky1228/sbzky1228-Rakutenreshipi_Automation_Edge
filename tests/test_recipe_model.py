from pathlib import Path

import pytest
import yaml

from recipe_poster.recipes.model import (
    Ingredient, RecipeData, RecipeFormatError, Step, dump_recipe_yaml, load_recipe_yaml, parse_recipe_data,
)

EXAMPLES = sorted((Path(__file__).resolve().parent.parent / "examples").glob("*/recipe.yaml"))

MINIMUM = {
    "schema_version": 1,
    "title": "卵焼き",
    "description": "簡単です。",
    "servings": 2,
    "cook_minutes": 10,
    "ingredients": [{"name": "卵", "amount": "2個"}],
    "steps": [{"text": "焼く。"}],
    "story": "朝ごはんに。",
    "images": {"main": "main.jpg"},
}


def errors_of(data) -> list[str]:
    with pytest.raises(RecipeFormatError) as e:
        parse_recipe_data(data)
    return e.value.errors


def test_examples_exist():
    assert len(EXAMPLES) >= 4


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.parent.name)
def test_examples_are_valid_and_round_trip(path):
    # 写真は examples に置いていないため、ファイルの有無は確かめない
    recipe = load_recipe_yaml(path, check_files=False)
    assert parse_recipe_data(yaml.safe_load(dump_recipe_yaml(recipe))) == recipe


def test_minimum_recipe():
    recipe = parse_recipe_data(MINIMUM)
    assert recipe.title == "卵焼き"
    assert recipe.cost_yen is None
    assert recipe.ingredients == [Ingredient("卵", "2個")]
    assert recipe.main_image == "main.jpg"


def test_shorthand_and_numbers_are_accepted():
    data = dict(MINIMUM, steps=["切る。", {"text": "焼く。", "image": "step2.jpg"}],
                ingredients=[{"name": "卵", "amount": 2}])
    recipe = parse_recipe_data(data)
    assert recipe.steps == [Step("切る。"), Step("焼く。", "step2.jpg")]
    assert recipe.ingredients == [Ingredient("卵", "2")]


def test_all_errors_are_reported_together():
    errors = errors_of({"schema_version": 1, "titel": "卵焼き", "servings": "2人"})
    assert "不明な項目があります（書き間違いの可能性）: titel" in errors
    assert "title（タイトル） が書かれていません" in errors
    assert "servings（人数） は1以上の整数で書いてください（現在: '2人'）" in errors
    assert "ingredients（材料）が書かれていません" in errors
    assert "steps（作り方）が書かれていません" in errors
    assert "images.main（メインの写真）が書かれていません" in errors


@pytest.mark.parametrize("change, message", [
    ({"schema_version": 2}, "schema_version は 1 にしてください"),
    ({"id": "Chashu Chahan"}, "id は英小文字・数字・ハイフンで書いてください"),
    ({"meal": ["おやつ"]}, "meal に書けるのは 朝食 / 昼食 / 夕食 です"),
    ({"tags": "和食"}, "tags は文字列のリストで書いてください"),
    ({"cost_yen": -1}, "cost_yen（費用（円）） は0以上の整数で書いてください"),
    ({"ingredients": [{"amount": "2個"}]}, "ingredients の1つ目: name（材料名） が書かれていません"),
    ({"ingredients": [{"name": "卵", "amonut": "2個"}]}, "ingredients の1つ目に不明な項目があります: amonut"),
    ({"platforms": {"twitter": {}}}, "platforms に不明な投稿先があります: twitter"),
    ({"platforms": {"instagram": {"tags": ["a"]}}}, "platforms.instagram に不明な項目があります: tags"),
    ({"platforms": {"tiktok": {"video": ["a.mp4"]}}}, "platforms.tiktok.video は文字列で書いてください"),
])
def test_invalid_values(change, message):
    assert any(e.startswith(message) for e in errors_of(dict(MINIMUM, **change)))


def test_not_a_mapping():
    assert errors_of(["卵焼き"]) == ["recipe.yaml の中身が「項目名: 値」の形になっていません"]


def test_load_checks_referenced_files(tmp_path):
    data = dict(MINIMUM, steps=[{"text": "焼く。", "image": "step1.jpg"}],
                platforms={"tiktok": {"video": "tiktok.mp4"}})
    path = tmp_path / "recipe.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    (tmp_path / "main.jpg").write_bytes(b"jpg")

    with pytest.raises(RecipeFormatError) as e:
        load_recipe_yaml(path)
    assert e.value.errors == ["ファイルが見つかりません: step1.jpg", "ファイルが見つかりません: tiktok.mp4"]
    assert load_recipe_yaml(path, check_files=False).title == "卵焼き"


def test_load_reports_yaml_syntax_error(tmp_path):
    path = tmp_path / "recipe.yaml"
    path.write_text("title: [卵焼き\n", encoding="utf-8")
    with pytest.raises(RecipeFormatError, match="YAMLの書き方に誤りがあります"):
        load_recipe_yaml(path)


def test_dump_round_trip_with_tricky_text():
    recipe = RecipeData(
        title="yes", description="1行目\n2行目: コロン", servings=2, cook_minutes=15,
        ingredients=[Ingredient("卵", "2個"), Ingredient("醤油", "大さじ1", "A")],
        steps=[Step("切る。\n- 細かく"), Step("焼く: 強火", "step2.jpg")],
        story="#ハッシュタグではない", main_image="main.jpg", id="a-b", cost_yen=0,
        tags=["和食", "a, b"], meal=["朝食"],
        platforms={"instagram": {"caption": "1行目\n2行目", "hashtags": ["料理"]}},
    )
    text = dump_recipe_yaml(recipe)
    assert "title: 'yes'" in text  # 真偽値と解釈されないよう引用符で囲む
    assert parse_recipe_data(yaml.safe_load(text)) == recipe
