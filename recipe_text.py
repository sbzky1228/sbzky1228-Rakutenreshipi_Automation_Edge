"""
recipe.txt（■見出し形式）の読み込み - recipe.yaml への移行期間用

recipe.txt を recipe.yaml と同じ形のデータに変換し、recipe_model の検証を通して RecipeData にする。
recipe.yaml があるフォルダでは使われない（recipe_folders.load_recipe を参照）。

テキストは見出し（■レシピタイトル、**・材料（2人分）：** など）ごとに内容を書く形式。
見出しは行頭の記号のあとに項目名で始まる行だけを見出しとみなすため、
作り方の本文に「材料」などの語が含まれていても見出しと誤認しない。
"""
import re
import unicodedata
from pathlib import Path

from recipe_model import SCHEMA_VERSION, RecipeData, parse_recipe_data

SECTION_KEYS = (
    "レシピタイトル", "調理時間", "費用", "レシピコメント", "材料",
    "作り方", "きっかけ", "おいしくなるコツ", "カテゴリ",
)

# 見出し行: 行頭の記号 → 項目名 → （補足） → 「：」のあとに値が続く場合もある
_HEADER_RE = re.compile(
    r"^[\s*#■□●◆◇・【\[]*"
    r"(?P<key>" + "|".join(SECTION_KEYS) + r")"
    r"\s*(?:[（(](?P<note>[^）)]*)[）)])?"
    r"[\s*】\]]*"
    r"(?:[:：][\s*]*(?P<value>.*?))?[\s*]*$"
)
# 材料・作り方の行頭の箇条書き記号
_BULLET_RE = re.compile(r"^[\s*\-−‐・•●]+")
# 作り方の行頭の番号（1. 1) 1、 ① など）
_STEP_NUMBER_RE = re.compile(r"^(?:\d+\s*[.．、)）:：]|[①-⑳])\s*")
# 材料名と分量の区切り（優先順）
_INGREDIENT_SEPARATORS = ("…", "...", "：", ":")
# 区切り記号が無い場合の分量の始まり（数字・大さじ・少々 など）
_AMOUNT_START_RE = re.compile(
    r"^(?P<name>.+?)[\s　]+(?P<amount>(?:\d|[０-９]|大さじ|小さじ|少々|適量|適宜|お好み|ひとつまみ|約|半).*)$"
)
# カテゴリ欄の区切り（「朝食 / 洋食」「朝食、洋食」）。「ご飯・丼もの」のような「・」は1つの語として残す
_CATEGORY_SEPARATOR_RE = re.compile(r"[/／、,，\s]+")
# カテゴリ欄の語を meal（朝食・昼食・夕食）に読み替える
MEAL_WORDS = (
    ("朝食", ("朝食", "朝ごはん", "朝ご飯", "モーニング")),
    ("昼食", ("昼食", "昼ごはん", "昼ご飯", "ランチ")),
    ("夕食", ("夕食", "夕飯", "晩ごはん", "晩ご飯", "晩御飯")),
)
# 材料の見出しに人数が無い場合の人数
DEFAULT_SERVINGS = 2


def _normalize(text: str) -> str:
    """全角数字・記号を半角にそろえる（「１５〜２０分」→「15〜20分」）"""
    return unicodedata.normalize("NFKC", text)


def _split_ingredient(line: str) -> tuple[str, str]:
    """「卵 … 2個」「卵: 2個」「卵 2個」を (材料名, 分量) に分ける"""
    for separator in _INGREDIENT_SEPARATORS:
        if separator in line:
            name, amount = line.split(separator, 1)
            return name.strip(), amount.strip()
    match = _AMOUNT_START_RE.match(line)
    if match:
        return match.group("name").strip(), match.group("amount").strip()
    return line.strip(), ""


def _minutes_in(text: str) -> list[float]:
    """文字列に含まれる時間を分に換算して返す（「1時間30分」→ [90]、「15〜20分」→ [15, 20]）"""
    text = _normalize(text)
    hour_matches = re.findall(r"(\d+(?:\.\d+)?)\s*時間(半)?(?:\s*(\d+)\s*分)?", text)
    if hour_matches:
        return [float(hours) * 60 + (30 if half else 0) + int(minutes or 0)
                for hours, half, minutes in hour_matches]
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]


def parse_minutes(text: str) -> int | None:
    """調理時間を分の数値にする。範囲（15〜20分）は長い方。読み取れなければNone"""
    minutes = _minutes_in(text)
    return round(max(minutes)) if minutes else None


def parse_yen(text: str) -> int | None:
    """費用を円の数値にする。範囲（800〜1000円）は平均。読み取れなければNone"""
    amounts = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", _normalize(text).replace(",", ""))]
    return round(sum(amounts) / len(amounts)) if amounts else None


def split_category(category: str) -> tuple[list[str], list[str]]:
    """カテゴリ欄を (tags, meal) に分ける。「朝食」「夕飯」などは meal（朝食・昼食・夕食）にまとめる"""
    tags, meal = [], []
    for word in (w for w in _CATEGORY_SEPARATOR_RE.split(category) if w):
        matched = [name for name, words in MEAL_WORDS if any(w in word for w in words)]
        if matched:
            meal += [m for m in matched if m not in meal]
        elif word not in tags:
            tags.append(word)
    return tags, meal


def parse_recipe_text(text: str) -> dict:
    """
    recipe.txt の文章を recipe.yaml と同じ形の辞書にする（images・dish_name は含まない）。
    数値にできない調理時間は元の文字のまま入れ、検証で知らせる。
    """
    texts: dict[str, list[str]] = {}
    ingredients: list[dict] = []
    steps: list[dict] = []
    servings = DEFAULT_SERVINGS
    current_key = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header = _HEADER_RE.match(line)
        if header:
            current_key = header.group("key")
            if current_key == "材料" and header.group("note"):
                found = re.search(r"(\d+)\s*人", _normalize(header.group("note")))
                if found:
                    servings = int(found.group(1))
            line = header.group("value") or ""
            if not line:
                continue

        if current_key == "材料":
            name, amount = _split_ingredient(_BULLET_RE.sub("", line))
            if name:
                ingredients.append({"name": name, "amount": amount})
        elif current_key == "作り方":
            step = _STEP_NUMBER_RE.sub("", _BULLET_RE.sub("", line)).strip()
            if step:
                steps.append({"text": step})
        elif current_key:
            texts.setdefault(current_key, []).append(line)

    joined = {key: "\n".join(lines) for key, lines in texts.items()}
    cooking_time = joined.get("調理時間", "")
    tags, meal = split_category(joined.get("カテゴリ", ""))
    data = {
        "schema_version": SCHEMA_VERSION,
        "title": joined.get("レシピタイトル", ""),
        "description": joined.get("レシピコメント", ""),
        "servings": servings,
        "cook_minutes": parse_minutes(cooking_time) or (cooking_time or None),
        "cost_yen": parse_yen(joined.get("費用", "")),
        "tags": tags,
        "meal": meal,
        "ingredients": ingredients,
        "steps": steps,
        "story": joined.get("きっかけ", ""),
        "tips": joined.get("おいしくなるコツ", ""),
    }
    return {key: value for key, value in data.items() if value not in ("", None, [])}


def load_recipe_text(text_path: Path, main_image: str, dish_name: str) -> RecipeData:
    """recipe.txt（UTF-8、BOM付きも可）を読み込んで検証し、RecipeData にする"""
    data = parse_recipe_text(Path(text_path).read_text(encoding="utf-8-sig"))
    data.update(dish_name=dish_name, images={"main": main_image})
    return parse_recipe_data(data)
