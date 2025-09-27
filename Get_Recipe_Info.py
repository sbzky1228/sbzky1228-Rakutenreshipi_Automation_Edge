import os
import re

def get_recipe_info(file_path):
    recipe_data = {
        "レシピタイトル": "",
        "調理時間": "",
        "費用": "",
        "レシピコメント": "",
        "材料": [],
        "作り方": [],
        "きっかけ": "",
        "おいしくなるコツ": "",
        "カテゴリ": ""
    }

    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    current_key = None

    for line in lines:
        line = line.strip()

        if not line:
            continue  # 空行はスキップ

        # キーワードが含まれていれば current_key をセット
        if "レシピタイトル" in line:
            current_key = "レシピタイトル"
            continue
        elif "調理時間" in line:
            current_key = "調理時間"
            continue
        elif "費用" in line:
            current_key = "費用"
            continue
        elif "レシピコメント" in line:
            current_key = "レシピコメント"
            continue
        elif "材料" in line:
            current_key = "材料"
            continue
        elif "作り方" in line:
            current_key = "作り方"
            continue
        elif "きっかけ" in line:
            current_key = "きっかけ"
            continue
        elif "おいしくなるコツ" in line:
            current_key = "おいしくなるコツ"
            continue
        elif "カテゴリ" in line:
            current_key = "カテゴリ"
            continue

        # 値の格納
        if current_key == "材料":
        # 例: "- 卵 … 2個" → "卵 … 2個"
            cleaned_line = re.sub(r"^[\*\-−ー・\s]*", "", line)  # 行頭の記号や空白を削除
            if "…" in cleaned_line:
                material, amount = map(str.strip, cleaned_line.split("…", 1))
                recipe_data["材料"].append({"material": material, "amount": amount})
        elif current_key == "作り方":
            cleaned_line = re.sub(r"^[-−ー・\s]*", "", line)
            # 数字とピリオドを削除
            cleaned_line = re.sub(r"^\d+\.\s*", "", line)
            if cleaned_line:
                recipe_data["作り方"].append(cleaned_line)
        else:
            if recipe_data[current_key]:
                recipe_data[current_key] += "\n" + line
            else:
                recipe_data[current_key] = line

    return recipe_data

    #フォルダをループして各ファイル名を取得する(他のところで使えそう)
    # def load_all_recipes_from_folder(folder_path):
    #     recipe_list = []
    #     for filename in os.listdir(folder_path):
    #         if filename.endswith(".txt"):
    #             file_path = os.path.join(folder_path, filename)
    #             recipe = load_recipe_from_file(file_path)
    #             recipe_list.append(recipe)
    #     return recipe_list