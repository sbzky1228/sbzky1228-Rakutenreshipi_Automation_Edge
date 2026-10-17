"""
楽天レシピ向けの変換 - RecipeData（recipe.yaml / recipe.txt の内容）を楽天レシピの投稿画面の入力内容にする

- 調理時間（分）・費用（円）を楽天レシピの選択肢（「約15分」「500円前後」など）に変換する
- 楽天レシピのカテゴリを選ぶ
- 楽天レシピの文字数の上限などをチェックする
"""
from dataclasses import dataclass, field
from pathlib import Path

from recipe_model import RecipeData

# 楽天レシピの入力欄の上限文字数（投稿画面の data-maxlength）
MAX_LENGTHS = {
    "レシピタイトル": 25,
    "レシピコメント": 80,
    "きっかけ": 120,
    "おいしくなるコツ": 120,
    "材料名": 20,
    "分量": 20,
    "作り方": 90,
    "料理名": 25,
}

# 調理時間の選択肢（ラベル, 上限の分数）
COOKING_TIME_OPTIONS = (
    ("5分以内", 5),
    ("約10分", 10),
    ("約15分", 15),
    ("約30分", 30),
    ("約1時間", 60),
)
COOKING_TIME_OVER = "1時間以上"

# 費用目安の選択肢（ラベル, 目安の金額）
COST_OPTIONS = (
    ("100円以下", 100),
    ("300円前後", 300),
    ("500円前後", 500),
    ("1,000円前後", 1000),
    ("2,000円前後", 2000),
    ("3,000円前後", 3000),
    ("5,000円前後", 5000),
    ("10,000円以上", 10000),
)

# 費用目安に応じて選ぶ節約料理カテゴリ
SAVING_CATEGORIES = {
    "100円以下": "100円以下の節約料理",
    "300円前後": "300円前後の節約料理",
    "500円前後": "500円前後の節約料理",
}
# meal（朝食・昼食・夕食）に応じて選ぶ献立カテゴリ
MEAL_CATEGORIES = {
    "朝食": "朝食の献立（朝ごはん）",
    "昼食": "昼食の献立（昼ごはん）",
    "夕食": "夕食の献立（晩御飯）",
}
# 毎回選ぶカテゴリ
DEFAULT_CATEGORY = "男の簡単料理"
# 1レシピに設定できるカテゴリの上限
MAX_CATEGORIES = 5


@dataclass
class RakutenPost:
    """楽天レシピの投稿画面に入力する内容"""
    key: str                    # レシピの識別名（フォルダ名。DBの投稿履歴の recipe_key）
    title: str
    dish_name: str
    image: Path
    cooking_time: str           # 調理時間の選択肢
    cost: str | None            # 費用目安の選択肢（費用が無ければNone）
    comment: str
    servings: str
    ingredients: list[tuple[str, str]]   # (材料名, 分量)
    steps: list[str]
    reason: str
    tip: str
    meal: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)  # recipe.yaml で指定されたカテゴリ（空なら自動で選ぶ）


def cooking_time_label(minutes: int) -> str:
    """調理時間（分）を楽天レシピの選択肢にする"""
    for label, limit in COOKING_TIME_OPTIONS:
        if minutes <= limit:
            return label
    return COOKING_TIME_OVER


def cost_label(yen: int | None) -> str | None:
    """費用（円）を楽天レシピの費用目安にする（最も近い目安、同じ距離なら安い方）"""
    if yen is None:
        return None
    if yen <= COST_OPTIONS[0][1]:
        return COST_OPTIONS[0][0]
    if yen >= COST_OPTIONS[-1][1]:
        return COST_OPTIONS[-1][0]
    return min(COST_OPTIONS, key=lambda option: abs(option[1] - yen))[0]


def to_rakuten_post(recipe: RecipeData, folder: Path) -> RakutenPost:
    """RecipeData を楽天レシピの入力内容にする（platforms.rakuten の指定があれば優先する）"""
    settings = recipe.platforms.get("rakuten", {})
    return RakutenPost(
        key=folder.name,
        title=settings.get("title") or recipe.title,
        dish_name=recipe.dish_name or folder.name,
        image=folder / recipe.main_image,
        cooking_time=cooking_time_label(recipe.cook_minutes),
        cost=cost_label(recipe.cost_yen),
        comment=recipe.description,
        servings=str(recipe.servings),
        # 楽天レシピに材料のグループ欄は無いため、材料名の前に「(A)」のように付ける
        ingredients=[(f"({item.group}){item.name}" if item.group else item.name, item.amount)
                     for item in recipe.ingredients],
        steps=[step.text for step in recipe.steps],
        reason=recipe.story,
        tip=recipe.tips,
        meal=list(recipe.meal),
        categories=list(settings.get("categories", [])),
    )


def choose_categories(available: list[str], post: RakutenPost) -> list[str]:
    """
    設定するカテゴリを選ぶ（最大5件、楽天レシピに存在するものだけ）

    recipe.yaml の platforms.rakuten.categories があればそれを使う。無ければ次の順で選ぶ。
    1. 料理名・タイトルに含まれるカテゴリ名（例: 豚の角煮、お吸い物）。長い名前を優先して最大2件
    2. 男の簡単料理
    3. 費用目安に応じた節約料理
    4. meal（朝食・昼食・夕食）に応じた献立
    """
    existing = set(available)
    chosen: list[str] = []

    def add(name: str):
        if name in existing and name not in chosen and len(chosen) < MAX_CATEGORIES:
            chosen.append(name)

    if post.categories:
        for name in post.categories:
            add(name)
        return chosen

    names_in_dish = sorted(
        (name for name in existing if len(name) >= 2 and (name in post.dish_name or name in post.title)),
        key=lambda name: (-len(name), name),
    )
    for name in names_in_dish[:2]:
        add(name)
    add(DEFAULT_CATEGORY)
    if post.cost in SAVING_CATEGORIES:
        add(SAVING_CATEGORIES[post.cost])
    for meal in post.meal:
        add(MEAL_CATEGORIES[meal])
    return chosen


def validate_rakuten_post(post: RakutenPost) -> list[str]:
    """楽天レシピに投稿できない内容（文字数超過など）を日本語のメッセージで返す。問題が無ければ空リスト"""
    errors = []

    def check_length(name: str, value: str):
        if len(value) > MAX_LENGTHS[name]:
            errors.append(f"{name}が楽天レシピの上限{MAX_LENGTHS[name]}文字を超えています（{len(value)}文字）: {value}")

    check_length("レシピタイトル", post.title)
    check_length("レシピコメント", post.comment)
    check_length("きっかけ", post.reason)
    check_length("おいしくなるコツ", post.tip)
    for name, amount in post.ingredients:
        check_length("材料名", name)
        check_length("分量", amount)
    for step in post.steps:
        check_length("作り方", step)
    if len(post.categories) > MAX_CATEGORIES:
        errors.append(f"楽天レシピのカテゴリは{MAX_CATEGORIES}件までです（{len(post.categories)}件）")

    # Edge WebDriver は絵文字など一部の文字（U+10000以降）を入力できない
    all_text = "".join([post.title, post.comment, post.reason, post.tip, post.dish_name, *post.steps,
                        *(name + amount for name, amount in post.ingredients)])
    unsupported = sorted({ch for ch in all_text if ord(ch) > 0xFFFF})
    if unsupported:
        errors.append(f"楽天レシピに入力できない文字（絵文字など）が含まれています: {' '.join(unsupported)}")
    return errors
