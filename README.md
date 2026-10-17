# 楽天レシピ自動投稿

投稿素材フォルダに置いたレシピ（料理写真＋recipe.yaml）を、Microsoft Edge を自動操作して楽天レシピに投稿するツールです。
投稿できたレシピは PostgreSQL の投稿履歴に記録します。投稿してもフォルダは移動せず、投稿済みかどうかは投稿履歴で判定します。
データベースは定期的に自動でバックアップします。

[![テスト](../../actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)

## できること

- 投稿素材フォルダのレシピのうち、楽天レシピに未投稿のものを順に投稿（公開申請）する
- 投稿前に内容をチェックし、未入力・文字数オーバーなどがあれば理由をログに出して投稿しない
- 調理時間（分）・費用（円）を楽天レシピの選択肢に変換する（例: 20分→「約30分」、600円→「500円前後」）
- カテゴリを自動で選ぶ（最大5件。recipe.yaml で指定することもできる）
  1. 料理名・タイトルに含まれる楽天レシピのカテゴリ（例: 豚の角煮、お吸い物）
  2. 男の簡単料理
  3. 費用目安に応じた節約料理（100円以下／300円前後／500円前後）
  4. `meal`（朝食・昼食・夕食）に応じた献立カテゴリ
- 投稿後にマイページの「公開待ち」に載ったことを確認してから、投稿URLとともに投稿履歴に記録する
- 同じタイトルのレシピが既に公開中・公開待ちにある場合は投稿しない（二重投稿の防止。投稿履歴に無ければ記録する）
- 失敗したときは画面を `logs` に保存し、入力途中の下書きは削除する（次回やり直せるように）
- 前回から7日以上たっていれば、投稿の処理のあとにデータベースをバックアップする

## 必要なもの

- Windows ＋ Microsoft Edge
- PostgreSQL（投稿履歴の記録用。バックアップには付属の pg_dump を使う）
- Python 3.12（exe で使う場合は不要）

Edge のドライバ（msedgedriver）は Selenium が Edge のバージョンに合わせて自動で用意します。

## セットアップ

1. `.env.example` を `.env` にコピーして値を設定する（exe で使う場合は exe と同じフォルダに置く）

   | 項目 | 内容 |
   |---|---|
   | `base_folder_path` | 投稿素材のフォルダ（すべてのレシピをここに置く） |
   | `RAKUTEN_USER_ID` / `RAKUTEN_PASSWORD` | 楽天会員のユーザーID・パスワード |
   | `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL の接続情報 |
   | `BACKUP_DIR`（任意） | バックアップの保存先（未指定ならプログラムのフォルダの `backup`） |
   | `BACKUP_INTERVAL_DAYS`（任意） | 何日ごとにバックアップするか（未指定なら7） |
   | `BACKUP_KEEP`（任意） | バックアップを何個残すか（未指定なら10） |
   | `PG_DUMP_PATH`（任意） | pg_dump.exe の場所（未指定なら `C:\Program Files\PostgreSQL\<版>\bin` などから自動で探す） |
   | `DRIVER_PATH`（任意） | ドライバを自動で用意できない環境（オフライン等）で使う msedgedriver.exe |
   | `LOG_DIR`（任意） | ログの保存先（未指定ならプログラムのフォルダの `logs`） |

2. PostgreSQL にデータベースを作る（テーブル `post_history` は初回の実行時に自動で作られる）

3. Python で動かす場合はパッケージを入れる

   ```bash
   pip install -r requirements.txt
   ```

## 投稿素材の置き方

```
投稿素材\
├── チャーシューチャーハン\      ← フォルダ名＝レシピの識別名（投稿履歴の recipe_key）。変えないこと
│   ├── main.jpg                ← 料理写真（recipe.yaml の images.main で指定）
│   └── recipe.yaml             ← レシピの内容
└── 豚の角煮\
    ├── ...
```

レシピの内容は次の優先順で読みます。

1. **recipe.yaml があれば recipe.yaml だけを使う。** 書き方は [docs/recipe-yaml.md](docs/recipe-yaml.md)、例は [examples/](examples/)。
   内容に誤りがある場合は、recipe.txt には切り替えずエラー内容をログに出して投稿しない（古い内容が投稿されないように）
2. **recipe.yaml が無ければ .txt（■見出し形式）と写真（.jpg / .jpeg / .png）を使う**（recipe.yaml への移行期間用）

既存の recipe.txt から recipe.yaml を作るには:

```bash
python -X utf8 convert_to_yaml.py                      # 投稿素材のすべて（recipe.yaml が既にあるものは作らない）
python -X utf8 convert_to_yaml.py 投稿素材/豚の角煮      # 指定したフォルダだけ
```

楽天レシピの文字数の上限: タイトル25・レシピコメント80・きっかけ120・コツ120・材料名20・分量20・作り方（1手順）90文字。
絵文字（😋 など）は楽天レシピには入力できないため、楽天レシピに出る項目では使わないでください。

<details>
<summary>recipe.txt（■見出し形式）の書き方</summary>

```
■レシピタイトル（25文字以内）
チャーシューチャーハン

■調理時間
15分                      ← 範囲（15〜20分）は長い方で判定

■費用
約600円                   ← 範囲（800〜1000円）は平均で判定

■レシピコメント（80文字以内）
余ったチャーシューを使った簡単チャーハン。

■材料（2人分）           ← 「2人分」の数字が人数になる（無ければ2）
- ご飯: 400g             ← 「名前: 分量」「名前 … 分量」「名前 分量」のどれでも可
- 卵: 2個

■作り方
1. チャーシューとネギを1cm角に切る。

■きっかけ（120文字以内）
...

■おいしくなるコツ（120文字以内）  ← 任意
...

■カテゴリ                 ← 任意。「朝食」「昼食」「夕食」などがあれば献立カテゴリを選ぶ
ご飯・丼もの
```

</details>

## 使い方

```bash
python main.py                         # 楽天レシピに未投稿のレシピをすべて投稿
python main.py --limit 1               # 1件だけ投稿
python main.py --folder 豚の角煮        # 指定したフォルダだけ投稿（複数指定可）
python main.py --dry-run               # 入力まで行い、公開申請・投稿履歴の記録・バックアップはしない（動作確認用）
python main.py --backup                # データベースのバックアップだけを取る
```

exe の場合も同じ引数が使えます（例: `RakutenRecipe_Auto_Post.exe --dry-run`）。
終了コードは、すべて成功（または対象なし）なら 0、投稿・バックアップに失敗があれば 1 です（タスクスケジューラの「前回の実行結果」で確認できます）。

ログは `logs\rakuten_recipe_日付_時刻.log` に出力されます。失敗したときの画面も `logs` に保存されます（不要になったら消してかまいません）。

### 投稿をやり直したいとき

投稿履歴にあるレシピは投稿されません。楽天レシピ側で削除したレシピを投稿し直す場合は、投稿履歴の行を削除します。

```sql
DELETE FROM post_history WHERE recipe_key = '豚の角煮' AND platform = 'rakuten';
```

### タスクスケジューラで定期実行する

「操作」の「プログラム/スクリプト」に `RakutenRecipe_Auto_Post.exe` のフルパスを指定します。
`.env`・`logs`・`backup` は exe と同じフォルダが使われるため、「開始（オプション）」の指定は不要です。
Edge の画面を操作するため、「ユーザーがログオンしているときのみ実行する」を選んでください。
定期実行していれば、データベースのバックアップも `BACKUP_INTERVAL_DAYS` 日ごとに自動で取られます。

## データベース

テーブル `post_history`（1レシピ×1投稿先につき1行）:

| 列 | 内容 |
|---|---|
| `recipe_key` | レシピの識別名（投稿素材のフォルダ名） |
| `recipe_title` | 投稿したときのタイトル |
| `platform` | 投稿先（今は `rakuten`。将来 `instagram` / `tiktok` / `website`） |
| `post_url` | 投稿のURL |
| `posted_at` | 投稿日時 |

以前の `"Recipe_info"` テーブルの記録は、`post_history` を作ったときに写してあります（`"Recipe_info"` は残っていますが使っていません）。

### バックアップから戻す

`backup` フォルダの SQL ファイルを psql で流し込みます（今のデータベースの中身はバックアップの内容に置き換わります）。

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d RakutenRecipe_information -f backup\RakutenRecipe_information_20261017_170729.sql
```

## 注意

- 新規投稿は楽天レシピの審査（3〜4日）のあとに公開されます。投稿直後はマイページの「公開待ち」に入ります
- 楽天レシピは 2025/9/16 でレシピ投稿への楽天ポイント進呈を終了しています
- 楽天レシピは同じタイトルのレシピ・下書きを作れません。投稿し直す場合はタイトルを変えてください
- 楽天レシピの画面が変わると動かなくなることがあります。`--dry-run` で入力まで確認できます
- 誤ったID・パスワードで何度もログインするとアカウントがロックされるおそれがあるため、ID・パスワードは1回しか送信しません

## 開発

```bash
pip install -r requirements-dev.txt
python -X utf8 -m pytest                                  # 自動テスト（ブラウザ・DBには接続しない）
python -m pyflakes *.py tests/*.py                        # 未使用の import・変数など
python -m vulture *.py tests/*.py --min-confidence 60     # 使っていないコード
```

GitHub に push すると GitHub Actions（`.github/workflows/tests.yml`）で上記のチェックとテストが自動で実行されます。

exe の作成:

```powershell
python -m PyInstaller --noconfirm --clean --workpath "$env:TEMP\RakutenRecipe_build" RakutenRecipe_Auto_Post.spec
Copy-Item dist\RakutenRecipe_Auto_Post.exe . -Force
```

### ファイル構成

| ファイル | 役割 |
|---|---|
| `main.py` | 全体の流れ（未投稿のレシピの読み込み → ログイン → 投稿 → 投稿履歴に記録 → バックアップ） |
| `config.py` | `.env` の読み込み・設定値 |
| `recipe_folders.py` | 投稿素材フォルダの検出、レシピの読み込み（recipe.yaml 優先、無ければ recipe.txt） |
| `recipe_model.py` | recipe.yaml の読み込み・検証・書き出し（投稿先に依存しないレシピデータ） |
| `recipe_text.py` | recipe.txt の読み込み（recipe.yaml と同じ形に変換。移行期間用） |
| `rakuten_recipe.py` | 楽天レシピ向けの変換（調理時間・費用の選択肢、カテゴリ選択、文字数チェック） |
| `browser.py` | Edge の起動 |
| `rakuten_login.py` | 楽天レシピへのログイン |
| `recipe_post.py` | 投稿画面への入力・公開申請・投稿の確認 |
| `database.py` | 投稿履歴（post_history）の記録・読み込み |
| `backup.py` | データベースのバックアップ（pg_dump） |
| `convert_to_yaml.py` | recipe.txt → recipe.yaml の変換 |
| `logger.py` | ログ出力 |
| `docs/recipe-yaml.md` | recipe.yaml の書き方 |
| `examples/` | recipe.yaml の例（楽天レシピに投稿済みのレシピ） |
| `tests/` | 自動テスト |
