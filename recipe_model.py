"""
レシピデータ（recipe.yaml）モジュール - 投稿先に依存しないレシピの読み込み・検証・書き出し

楽天レシピ・Instagram・TikTok・自分のレシピサイトで共通に使う「レシピの正本」を扱う。
数値（人数・調理時間・費用）は数値のまま持ち、投稿先ごとの表現（「約15分」など）は各投稿処理で変換する。
投稿済みかどうかなどの状態はこのファイルに書かない（DBで管理する）。

形式の説明: docs/recipe-yaml.md
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
import yaml

SCHEMA_VERSION = 1
RECIPE_FILE_NAME = "recipe.yaml"
MEALS = ("朝食", "昼食", "夕食")

# 投稿先ごとに書ける項目と型
PLATFORM_FIELDS = {
    "rakuten": {"title": str, "categories": list},
    "instagram": {"caption": str, "hashtags": list, "images": list},
    "tiktok": {"caption": str, "hashtags": list, "video": str},
}

# エラーメッセージに添える日本語の項目名（recipe.txt の見出し名）
FIELD_LABELS = {
    "title": "タイトル", "description": "紹介文・レシピコメント", "servings": "人数",
    "cook_minutes": "調理時間（分）", "cost_yen": "費用（円）", "story": "きっかけ", "name": "材料名", "text": "手順",
}

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOP_LEVEL_KEYS = (
    "schema_version", "id", "title", "dish_name", "description", "servings", "cook_minutes", "cost_yen",
    "tags", "meal", "ingredients", "steps", "story", "tips", "images", "platforms",
)


class RecipeFormatError(ValueError):
    """recipe.yaml の内容に問題がある（errors に日本語のメッセージを並べる）"""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Ingredient:
    name: str
    amount: str = ""
    group: str = ""   # 「A」など合わせ調味料のまとまり（任意）


@dataclass
class Step:
    text: str
    image: str = ""   # 手順の写真（recipe.yaml のフォルダからの相対パス、任意）


@dataclass
class RecipeData:
    """投稿先に依存しないレシピ"""
    title: str
    description: str                 # レシピの紹介文（楽天レシピの「レシピコメント」）
    servings: int                    # 何人分
    cook_minutes: int                # 調理時間（分）
    ingredients: list[Ingredient]
    steps: list[Step]
    story: str                       # きっかけ
    main_image: str                  # メインの写真（recipe.yaml のフォルダからの相対パス）
    id: str = ""                     # 英小文字・数字・ハイフン（自分のサイトのURLなどに使う、任意）
    dish_name: str = ""              # 料理名（任意）
    cost_yen: int | None = None      # 費用の目安（円、任意）
    tips: str = ""                   # おいしくなるコツ（任意）
    tags: list[str] = field(default_factory=list)
    meal: list[str] = field(default_factory=list)          # 朝食・昼食・夕食
    platforms: dict[str, dict] = field(default_factory=dict)  # 投稿先ごとの上書き・追加


# ------------------------------------------------------------
# 読み込み・検証
# ------------------------------------------------------------
def _label(key: str) -> str:
    return f"{key}（{FIELD_LABELS[key]}）" if key in FIELD_LABELS else key


def _text(data: dict, key: str, errors: list[str], required: bool = False) -> str:
    value = data.get(key)
    if value is None:
        value = ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)  # 「amount: 2」のように数値で書かれた場合
    if not isinstance(value, str):
        errors.append(f"{_label(key)} は文字列で書いてください")
        return ""
    value = value.strip()
    if required and not value:
        errors.append(f"{_label(key)} が書かれていません")
    return value


def _integer(data: dict, key: str, errors: list[str], required: bool = False, minimum: int = 1) -> int | None:
    value = data.get(key)
    if value is None:
        if required:
            errors.append(f"{_label(key)} が書かれていません")
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        errors.append(f"{_label(key)} は{minimum}以上の整数で書いてください（現在: {value!r}）")
        return None
    return value


def _string_list(data: dict, key: str, errors: list[str]) -> list[str]:
    value = data.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        errors.append(f"{key} は文字列のリストで書いてください（例: [和食, 副菜]）")
        return []
    return [v.strip() for v in value]


def _ingredients(data: dict, errors: list[str]) -> list[Ingredient]:
    items = data.get("ingredients")
    if not isinstance(items, list) or not items:
        errors.append("ingredients（材料）が書かれていません")
        return []
    result = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"ingredients の{i}つ目は「name: 材料名」「amount: 分量」の形で書いてください")
            continue
        unknown = set(item) - {"name", "amount", "group"}
        if unknown:
            errors.append(f"ingredients の{i}つ目に不明な項目があります: {', '.join(sorted(unknown))}")
        item_errors: list[str] = []
        name = _text(item, "name", item_errors, required=True)
        amount = _text(item, "amount", item_errors)
        group = _text(item, "group", item_errors)
        errors.extend(f"ingredients の{i}つ目: {e}" for e in item_errors)
        result.append(Ingredient(name, amount, group))
    return result


def _steps(data: dict, errors: list[str]) -> list[Step]:
    items = data.get("steps")
    if not isinstance(items, list) or not items:
        errors.append("steps（作り方）が書かれていません")
        return []
    result = []
    for i, item in enumerate(items, 1):
        if isinstance(item, str):
            item = {"text": item}  # 「- 切る。」のように文だけ書いた場合
        if not isinstance(item, dict):
            errors.append(f"steps の{i}つ目は「text: 手順」の形で書いてください")
            continue
        unknown = set(item) - {"text", "image"}
        if unknown:
            errors.append(f"steps の{i}つ目に不明な項目があります: {', '.join(sorted(unknown))}")
        item_errors: list[str] = []
        text = _text(item, "text", item_errors, required=True)
        image = _text(item, "image", item_errors)
        errors.extend(f"steps の{i}つ目: {e}" for e in item_errors)
        result.append(Step(text, image))
    return result


def _platforms(data: dict, errors: list[str]) -> dict[str, dict]:
    platforms = data.get("platforms") or {}
    if not isinstance(platforms, dict):
        errors.append("platforms は投稿先ごとの項目（rakuten: など）で書いてください")
        return {}
    result = {}
    for name, values in platforms.items():
        if name not in PLATFORM_FIELDS:
            errors.append(f"platforms に不明な投稿先があります: {name}（使えるもの: {', '.join(PLATFORM_FIELDS)}）")
            continue
        values = values or {}
        if not isinstance(values, dict):
            errors.append(f"platforms.{name} は項目（title: など）で書いてください")
            continue
        for key, value in values.items():
            expected = PLATFORM_FIELDS[name].get(key)
            if expected is None:
                errors.append(f"platforms.{name} に不明な項目があります: {key}")
            elif expected is list:
                values[key] = _string_list(values, key, errors)
            elif not isinstance(value, str):
                errors.append(f"platforms.{name}.{key} は文字列で書いてください")
            else:
                values[key] = value.strip()
        result[name] = values
    return result


def parse_recipe_data(data) -> RecipeData:
    """YAMLを読み込んだ辞書を RecipeData にする。問題があればすべてまとめて RecipeFormatError にする"""
    if not isinstance(data, dict):
        raise RecipeFormatError(["recipe.yaml の中身が「項目名: 値」の形になっていません"])

    errors: list[str] = []
    unknown = set(data) - set(_TOP_LEVEL_KEYS)
    if unknown:
        errors.append(f"不明な項目があります（書き間違いの可能性）: {', '.join(sorted(unknown))}")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version は {SCHEMA_VERSION} にしてください（現在: {data.get('schema_version')!r}）")

    recipe_id = _text(data, "id", errors)
    if recipe_id and not _ID_RE.match(recipe_id):
        errors.append(f"id は英小文字・数字・ハイフンで書いてください（例: chashu-chahan）: {recipe_id}")

    images = data.get("images") or {}
    if not isinstance(images, dict):
        errors.append("images は「main: 写真のファイル名」の形で書いてください")
        images = {}
    elif set(images) - {"main"}:
        errors.append(f"images に不明な項目があります: {', '.join(sorted(set(images) - {'main'}))}")

    meal = _string_list(data, "meal", errors)
    for value in meal:
        if value not in MEALS:
            errors.append(f"meal に書けるのは {' / '.join(MEALS)} です: {value}")

    recipe = RecipeData(
        id=recipe_id,
        title=_text(data, "title", errors, required=True),
        dish_name=_text(data, "dish_name", errors),
        description=_text(data, "description", errors, required=True),
        servings=_integer(data, "servings", errors, required=True) or 0,
        cook_minutes=_integer(data, "cook_minutes", errors, required=True) or 0,
        cost_yen=_integer(data, "cost_yen", errors, minimum=0),
        tags=_string_list(data, "tags", errors),
        meal=meal,
        ingredients=_ingredients(data, errors),
        steps=_steps(data, errors),
        story=_text(data, "story", errors, required=True),
        tips=_text(data, "tips", errors),
        main_image=_text(images, "main", errors),
        platforms=_platforms(data, errors),
    )
    if not recipe.main_image:
        errors.append("images.main（メインの写真）が書かれていません")
    if errors:
        raise RecipeFormatError(errors)
    return recipe


def referenced_files(recipe: RecipeData) -> list[str]:
    """recipe.yaml から参照している写真・動画のパス"""
    files = [recipe.main_image, *(step.image for step in recipe.steps if step.image)]
    files += recipe.platforms.get("instagram", {}).get("images", [])
    video = recipe.platforms.get("tiktok", {}).get("video")
    if video:
        files.append(video)
    return files


def load_recipe_yaml(path: Path, check_files: bool = True) -> RecipeData:
    """
    recipe.yaml を読み込んで検証する。
    check_files=True なら、参照している写真・動画が recipe.yaml のフォルダにあるかも確かめる。
    """
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        raise RecipeFormatError([f"YAMLの書き方に誤りがあります: {e}"]) from e
    recipe = parse_recipe_data(data)
    if check_files:
        missing = [f for f in referenced_files(recipe) if not (path.parent / f).is_file()]
        if missing:
            raise RecipeFormatError([f"ファイルが見つかりません: {f}" for f in missing])
    return recipe


# ------------------------------------------------------------
# 書き出し
# ------------------------------------------------------------
def _scalar(value) -> str:
    """1行の値をYAMLとして安全な表記にする（必要なら引用符で囲む）"""
    text = yaml.safe_dump(value, allow_unicode=True, width=10**9)
    return text.removesuffix("\n...\n").rstrip("\n")


def _flow_list(values: list[str]) -> str:
    return yaml.safe_dump(values, allow_unicode=True, default_flow_style=True, width=10**9).rstrip("\n")


def _block_text(key: str, text: str, indent: str = "", content_indent: str | None = None) -> list[str]:
    """複数行の文章は「|」で書き、1行ならそのまま書く"""
    if "\n" not in text:
        return [f"{indent}{key}: {_scalar(text)}"]
    content_indent = indent + "  " if content_indent is None else content_indent
    return [f"{indent}{key}: |"] + [f"{content_indent}{line}".rstrip() for line in text.split("\n")]


def dump_recipe_yaml(recipe: RecipeData) -> str:
    """RecipeData を人が読み書きしやすい形の recipe.yaml の文字列にする（項目の説明コメント付き）"""
    lines = [
        "# レシピデータ（楽天レシピ・Instagram・TikTok・自分のサイトで共通に使う）",
        "# 書き方の説明: docs/recipe-yaml.md",
        f"schema_version: {SCHEMA_VERSION}",
    ]
    if recipe.id:
        lines.append(f"id: {_scalar(recipe.id)}")
    lines.append(f"title: {_scalar(recipe.title)}")
    if recipe.dish_name:
        lines.append(f"dish_name: {_scalar(recipe.dish_name)}")
    lines += _block_text("description", recipe.description)
    lines += ["", "# 人数・調理時間（分）・費用の目安（円）", f"servings: {recipe.servings}",
              f"cook_minutes: {recipe.cook_minutes}"]
    if recipe.cost_yen is not None:
        lines.append(f"cost_yen: {recipe.cost_yen}")
    if recipe.tags:
        lines.append(f"tags: {_flow_list(recipe.tags)}")
    if recipe.meal:
        lines.append(f"meal: {_flow_list(recipe.meal)}")

    lines += ["", "# 材料（group は「A」などの合わせ調味料のまとまり）", "ingredients:"]
    for item in recipe.ingredients:
        lines.append(f"  - name: {_scalar(item.name)}")
        if item.amount:
            lines.append(f"    amount: {_scalar(item.amount)}")
        if item.group:
            lines.append(f"    group: {_scalar(item.group)}")

    lines += ["", "# 作り方（image は手順の写真、任意）", "steps:"]
    for step in recipe.steps:
        # 「- text: |」の本文は text より深く字下げする必要がある
        lines += _block_text("- text", step.text, "  ", content_indent="      ")
        if step.image:
            lines.append(f"    image: {_scalar(step.image)}")

    lines += ["", "# きっかけ"] + _block_text("story", recipe.story)
    if recipe.tips:
        lines += ["", "# おいしくなるコツ"] + _block_text("tips", recipe.tips)

    lines += ["", "# 写真（recipe.yaml と同じフォルダからの相対パス）", "images:",
              f"  main: {_scalar(recipe.main_image)}"]

    if recipe.platforms:
        lines += ["", "# 投稿先ごとの上書き・追加（書かなければ共通の項目を使う）", "platforms:"]
        for name, values in recipe.platforms.items():
            lines.append(f"  {name}:")
            for key, value in values.items():
                if isinstance(value, list):
                    lines.append(f"    {key}: {_flow_list(value)}")
                else:
                    lines += _block_text(key, value, "    ")
    return "\n".join(lines) + "\n"
