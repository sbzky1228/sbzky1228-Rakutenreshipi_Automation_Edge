from pathlib import Path

import pytest

from recipe_poster.rakuten.convert import (
    RakutenPost, choose_categories, cooking_time_label, cost_label, to_rakuten_post, validate_rakuten_post,
)
from recipe_poster.recipes.model import Ingredient, RecipeData, Step


def make_recipe(**changes) -> RecipeData:
    values = dict(
        title="チャーシューチャーハン", description="簡単です。", servings=2, cook_minutes=15,
        ingredients=[Ingredient("ご飯", "400g"), Ingredient("醤油", "大さじ1", "A")],
        steps=[Step("切る。"), Step("炒める。", "step2.jpg")], story="余っていたので。", main_image="main.jpg",
        dish_name="チャーシューチャーハン", cost_yen=600, tips="冷ご飯で。", meal=["夕食"],
    )
    values.update(changes)
    return RecipeData(**values)


def make_post(**changes) -> RakutenPost:
    values = dict(
        key="卵焼き", title="卵焼き", dish_name="卵焼き", image=Path("main.jpg"), cooking_time="約10分",
        cost="300円前後", comment="簡単です。", servings="2", ingredients=[("卵", "2個")], steps=["焼く。"],
        reason="朝ごはんに。", tip="",
    )
    values.update(changes)
    return RakutenPost(**values)


@pytest.mark.parametrize("minutes, expected", [
    (5, "5分以内"), (10, "約10分"), (15, "約15分"), (20, "約30分"), (30, "約30分"),
    (45, "約1時間"), (60, "約1時間"), (90, "1時間以上"),
])
def test_cooking_time_label(minutes, expected):
    assert cooking_time_label(minutes) == expected


@pytest.mark.parametrize("yen, expected", [
    (50, "100円以下"), (100, "100円以下"), (300, "300円前後"), (600, "500円前後"), (900, "1,000円前後"),
    (1500, "1,000円前後"),  # 同じ距離なら安い方
    (4000, "3,000円前後"), (12000, "10,000円以上"), (None, None),
])
def test_cost_label(yen, expected):
    assert cost_label(yen) == expected


def test_to_rakuten_post():
    post = to_rakuten_post(make_recipe(), Path("投稿素材/チャーシューチャーハン"))
    assert post.key == "チャーシューチャーハン"
    assert post.image == Path("投稿素材/チャーシューチャーハン/main.jpg")
    assert post.cooking_time == "約15分" and post.cost == "500円前後"
    assert post.servings == "2"
    assert post.ingredients == [("ご飯", "400g"), ("(A)醤油", "大さじ1")]  # グループは材料名の前に付ける
    assert post.steps == ["切る。", "炒める。"]
    assert post.reason == "余っていたので。" and post.tip == "冷ご飯で。"
    assert post.meal == ["夕食"] and post.categories == []


def test_to_rakuten_post_uses_platform_settings():
    recipe = make_recipe(dish_name="", platforms={"rakuten": {"title": "楽天用のタイトル", "categories": ["男の簡単料理"]}})
    post = to_rakuten_post(recipe, Path("チャーハン"))
    assert post.title == "楽天用のタイトル"
    assert post.dish_name == "チャーハン"  # 料理名が無ければフォルダ名
    assert post.categories == ["男の簡単料理"]


AVAILABLE = ["男の簡単料理", "100円以下の節約料理", "300円前後の節約料理", "500円前後の節約料理",
             "朝食の献立（朝ごはん）", "昼食の献立（昼ごはん）", "夕食の献立（晩御飯）",
             "豚の角煮", "お吸い物", "ピーマン", "チョレギサラダ", "角"]


def test_choose_categories_from_dish_name_and_cost():
    post = make_post(title="ピーマンのお吸い物和え", dish_name="ピーマンのお吸い物和え", cost="300円前後")
    assert choose_categories(AVAILABLE, post) == ["お吸い物", "ピーマン", "男の簡単料理", "300円前後の節約料理"]


def test_choose_categories_meal_and_limit():
    post = make_post(title="豚の角煮", dish_name="豚の角煮", cost="100円以下", meal=["朝食", "昼食", "夕食"])
    # 1文字のカテゴリ名（角）は料理名との照合に使わない。上限は5件
    assert choose_categories(AVAILABLE, post) == [
        "豚の角煮", "男の簡単料理", "100円以下の節約料理", "朝食の献立（朝ごはん）", "昼食の献立（昼ごはん）"]


def test_choose_categories_uses_specified_categories():
    post = make_post(categories=["ピーマン", "存在しないカテゴリ"])
    assert choose_categories(AVAILABLE, post) == ["ピーマン"]


def test_validate_ok():
    assert validate_rakuten_post(make_post()) == []


def test_validate_reports_too_long_and_unsupported_text():
    post = make_post(title="あ" * 26, ingredients=[("い" * 21, "1個")], comment="おいしい😋",
                     categories=["a", "b", "c", "d", "e", "f"])
    errors = validate_rakuten_post(post)
    assert any(e.startswith("レシピタイトルが楽天レシピの上限25文字を超えています（26文字）") for e in errors)
    assert any(e.startswith("材料名が楽天レシピの上限20文字を超えています") for e in errors)
    assert any("入力できない文字" in e and "😋" in e for e in errors)
    assert "楽天レシピのカテゴリは5件までです（6件）" in errors
