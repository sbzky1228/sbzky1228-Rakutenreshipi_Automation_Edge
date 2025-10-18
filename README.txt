# 📘 Rakuten Recipe 自動投稿プログラム

## 概要
このプログラムは、**楽天レシピ**に対して自動でレシピを投稿するPythonスクリプト群です。  
指定フォルダに保存された画像（.jpg）とテキスト（.txt）を読み込み、Seleniumを使用してレシピ投稿を自動化します。  
投稿が完了すると、データベースへ記録され、投稿済みフォルダへ自動で移動します。

---

## 📂 フォルダ構成

"""
├── main.py                              # メイン実行ファイル
├── Check_Target.py                      # 投稿対象フォルダをチェック
├── Get_Recipe_Info.py                   # テキストファイルからレシピ情報を抽出
├── RakutenRecipe_Login.py               # 楽天レシピへの自動ログイン
├── RakutenRecipe_Post.py                # レシピ投稿処理本体
├── Move_Folder.py                       # 投稿済みフォルダへの移動処理
├── DataBase_connection.py               # PostgreSQLデータベース接続
├── Add_Recipe_Information_To_DataBese.py # 投稿履歴をDBに登録
├── Get_Total_Count_Of_This_Month_From_DataBase.py # 累計投稿数の取得
├── .env                                 # 環境変数定義（個人情報含む）
"""

---

## ⚙️ 使用技術
- **Python 3.10+**
- **Selenium (Edge用)**
- **psycopg (PostgreSQL)**
- **dotenv (環境変数管理)**

---

## 🧩 動作概要

1. **投稿対象フォルダを取得**  
   "Check_Target.py" が ".env" の "base_folder_path" から対象フォルダを読み込み、".jpg" と ".txt" が揃っているものを抽出します。

2. **データベース接続と累計投稿数取得**  
   "DataBase_connection.py" にて PostgreSQL に接続し、"Get_Total_Count_Of_This_Month_From_DataBase.py" で累計投稿件数を取得します。

3. **楽天レシピへログイン**  
   "RakutenRecipe_Login.py" により ".env" に記載の "RAKUTEN_USER_ID" と "RAKUTEN_PASSWORD" を使って自動ログインします。

4. **レシピ投稿処理**  
   各フォルダのテキスト内容を "Get_Recipe_Info.py" で解析し、  
   "RakutenRecipe_Post.py" により楽天レシピ投稿フォームへ自動入力します。

5. **投稿情報のデータベース登録**  
   "Add_Recipe_Information_To_DataBese.py" が投稿情報（年月日・フォルダ名・累計件数）を "Recipe_info" テーブルにINSERTします。

6. **投稿済みフォルダへの移動**  
   "Move_Folder.py" により投稿完了フォルダを ".env" の "dest_folder" へ移動します。

---

## 🧾 .env ファイルの設定例


base_folder_path = "C:\Users\...\投稿素材"
dest_folder = "C:\Users\...\投稿済み"
RAKUTEN_USER_ID = "example@gmail.com"
RAKUTEN_PASSWORD = "password"
DB_NAME = "RakutenRecipe_information"
DB_USER = "postgres"
DB_PASSWORD = "yourpassword"
DB_HOST = "localhost"
DB_PORT = "5432"
DRIVER_PATH = "C:\path\to\msedgedriver.exe"
"""

⚠️ **注意**：  
このファイルには認証情報（ID・パスワード・トークンなど）が含まれるため、  
**絶対にGitHub等に公開しないでください。**

---

## 🧱 データベース仕様（PostgreSQL）

テーブル名："Recipe_info"

| カラム名          | 型      | 内容               |
|------------------|----------|--------------------|
| id               | SERIAL   | 主キー             |
| recipe_name      | TEXT     | フォルダ名（レシピ名） |
| post_day         | INT      | 投稿日（日）       |
| post_month       | INT      | 投稿日（月）       |
| post_year        | INT      | 投稿日（年）       |
| total_post_count | INT      | 累計投稿件数       |

---

## ▶️ 実行方法

1. ".env" ファイルを正しく設定します。  
2. 必要なPythonライブラリをインストールします。
   """bash
   pip install selenium psycopg python-dotenv webdriver-manager
   """
3. PostgreSQLを起動し、"Recipe_info"テーブルを作成しておきます。  
4. Edgeドライバ（msedgedriver.exe）のパスを".env"に設定します。  
5. 以下のコマンドで実行します。
   """bash
   python main.py
   """

---

## 🔄 投稿の流れ
"""
[1] レシピ素材フォルダ → [2] 自動投稿 → [3] DB登録 → [4] 投稿済みフォルダ移動
"""

---

## 📌 注意点
- ".env" のパスやログイン情報は環境ごとに異なります。
- 楽天レシピのUI変更により動作が変わる場合があります。
- 投稿制限（30件/月など）は別途確認が必要です。
- Selenium起動時にEdgeドライバの互換性エラーが出る場合は、"webdriver-manager"を利用して再インストールしてください。

---

## 🧑‍💻 作者メモ
- 将来的に **LINE通知機能** や **月次投稿数の自動報告** 機能を追加予定。
- ".env" ファイルを利用した環境変数管理により、他のPC環境でも再利用可能。
