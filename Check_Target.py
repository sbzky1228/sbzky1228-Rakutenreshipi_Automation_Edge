from pathlib import Path
import os

class check_target:
    def __init__(self):
        self.base_folder_str = os.getenv("base_folder_path")
        self.base_folder = Path(self.base_folder_str)
        self.folder_names = []
        self.folder_count = 0
        self.recipes = []

        self._load()

    def _load(self):
        # フォルダのみをリストアップ
        folders = [f for f in self.base_folder.iterdir() if f.is_dir()]
        self.folder_names = [f.name for f in folders]
        self.folder_count = len(self.folder_names)

        if self.folder_count == 0:
            print("⚠️ 対象フォルダが存在しません")
            return

        self.recipes = self._get_recipe_file_paths()

    def _get_recipe_file_paths(self):
        recipe_list = []

        for folder in self.base_folder.iterdir():
            if folder.is_dir():
                jpg_file = next(folder.glob("*.jpg"), None)
                txt_file = next(folder.glob("*.txt"), None)

                if jpg_file and txt_file:
                    recipe_list.append({
                        "image": jpg_file,
                        "text": txt_file
                    })
                else:
                    print(f"⚠️ {folder.name} に .jpg または .txt が見つかりませんでした")

        return recipe_list

    def has_recipes(self):
        return self.folder_count > 0




# from pathlib import Path
# import os

# def check_target():
#     def get_recipe_file_paths(base_folder: Path):
#         recipe_list = []

#         for folder in base_folder.iterdir():
#             if folder.is_dir():
#                 jpg_file = next(folder.glob("*.jpg"), None)
#                 txt_file = next(folder.glob("*.txt"), None)

#                 if jpg_file and txt_file:
#                     recipe_list.append({
#                         "image": jpg_file,
#                         "text": txt_file
#                     })
#                 else:
#                     print(f"⚠️ {folder.name} に .jpg または .txt が見つかりませんでした")

#         return recipe_list
    
#     base_folder_str = os.getenv("base_folder_path")
#     base_folder = Path(base_folder_str)
#     # フォルダのみをリストアップ
#     folders = [f for f in base_folder.iterdir() if f.is_dir()]

#     # フォルダ名だけ取り出す
#     folder_names = [f.name for f in folders]

#     # フォルダの合計数を取得
#     folder_count = len(folder_names)

#     if(folder_count == 0):
#         # 公式LiNEから対象がないことを通知予定
#         return
        
#     recipes = get_recipe_file_paths(base_folder)

#     return recipes
