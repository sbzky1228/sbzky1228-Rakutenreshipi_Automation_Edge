import shutil
from pathlib import Path
import os

def move_folder(folder_name: str):
    base_folder_str = os.getenv("base_folder_path")
    base_folder = Path(base_folder_str)
    
    # フォルダの移動先パス
    dest_folder_str = os.getenv("dest_folder")
    dest_folder = Path(dest_folder_str)
    
    # 移動元のフォルダ（対象フォルダ）
    src_folder = base_folder / folder_name

    # 移動先のパス
    dest_folder = dest_folder

    # 移動先の親フォルダがなければ作成
    dest_folder.mkdir(parents=True, exist_ok=True)

    # フォルダを移動
    shutil.move(str(src_folder), str(dest_folder))