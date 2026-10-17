# CLAUDE.md

楽天レシピ自動投稿ツール（Python + Selenium + Microsoft Edge）。`.env` の `base_folder_path`（投稿素材）配下のレシピフォルダ（写真＋recipe.yaml、無ければ recipe.txt）のうち、PostgreSQL の投稿履歴 `post_history` に楽天レシピの記録が無いものを公開申請し、投稿URLとともに記録する。**フォルダは移動しない**（すべて投稿素材に置いたまま）。前回から一定日数たっていれば pg_dump でDBをバックアップする。仕様・セットアップは README.md を参照。recipe.txt は兄弟ツール `../Get_RecipeInfo_from_ChatGPT` が作る（■見出し形式。recipe.yaml を作るようにする改修は別セッションで行う）。

## 処理の流れとモジュール

`main.py` → `database.posted_keys`（投稿済みのフォルダ名）→ `recipe_folders.load_recipe`（recipe.yaml 優先。yaml があれば txt は読まない。yaml に誤りがあればエラーで止め、txt に切り替えない）→ `rakuten_recipe.to_rakuten_post`（RecipeData → 楽天の入力内容 RakutenPost）→ `validate_rakuten_post` → `recipe_post.RecipePoster.post`（URLを返す）→ `database.add_post` → `backup.backup_if_due`

- recipe.txt は `recipe_text.parse_recipe_text` で recipe.yaml と同じ形の辞書にし、`recipe_model.parse_recipe_data` の同じ検証を通す（txt 専用の投稿処理は持たない）
- 楽天レシピ固有のこと（選択肢・カテゴリ・文字数上限）は `rakuten_recipe.py` に閉じ込める。Instagram 等を足すときも同様に投稿先ごとのモジュールを作る

## 実行・ビルド・テスト

- 実行: `python -X utf8 main.py [--dry-run] [--limit N] [--folder 名前] [--backup]`（コンソールがcp932のため `-X utf8`）
- テスト: `python -X utf8 -m pytest`（ブラウザ・DBに触れない。Selenium部分はテスト対象外、`main` はフェイクの poster で確認）
- 静的チェック: `python -m pyflakes *.py tests/*.py`、`python -m vulture *.py tests/*.py --min-confidence 60`（どちらも指摘ゼロを保つ）
- GitHub Actions: `.github/workflows/tests.yml`（ubuntu、Python 3.12、`.env` 不要）。テストに秘密情報や実サイトへの接続を持ち込まない
- exe: `python -m PyInstaller --noconfirm --clean --workpath "$env:TEMP\RakutenRecipe_build" RakutenRecipe_Auto_Post.spec` → `dist\RakutenRecipe_Auto_Post.exe` をプロジェクト直下へコピー（`.env` と同じフォルダで使う運用）。`dist`・`build` は消してよい
  - OneDrive配下なので `--workpath` を外に出す（WinError 5 対策）。**コードを変えたら exe を作り直す**
  - Selenium Manager（ドライバ自動取得）は PyInstaller の hook-selenium で同梱される。exe を別フォルダから `--dry-run` で起動して確認する
- `config.APP_DIR`（exe時はexeのフォルダ）の `.env` を優先して読む。`logs`・`backup` もここ

## データベース

- `post_history`（recipe_key=フォルダ名, recipe_title, platform, post_url, posted_at、UNIQUE(recipe_key, platform)）。`database.connect()` が無ければ作り、旧 `"Recipe_info"` の記録を1回だけ写す（`"Recipe_info"` は残してあるが使わない）
- 投稿日時は `clock_timestamp()`（`now()` はトランザクション開始＝処理開始の時刻になる）
- 楽天レシピ上に同じタイトルがあるのに履歴に無い場合は、投稿せずにそのURLで履歴に記録する（記録漏れの自己修復）
- バックアップ: `backup.py`。pg_dump（`PG_DUMP_PATH` → PATH → `C:\Program Files\PostgreSQL\<版>\bin`）で `--clean --if-exists` のプレーンSQL。最新ファイルの更新日時から `BACKUP_INTERVAL_DAYS` 日たったら取り、`BACKUP_KEEP` 個残す。`--dry-run` では取らない。パスワードは環境変数 PGPASSWORD で渡す
- 復元の確認は一時DB（createdb → psql -f → dropdb）で行った。本番DBに psql -f を流さない

## recipe.yaml（投稿先に依存しないレシピデータ）

- 楽天レシピ・Instagram・TikTok・自分のサイトで共通に使う正本。形式は `docs/recipe-yaml.md`、読み込み・検証・書き出しは `recipe_model.py`（`load_recipe_yaml` / `dump_recipe_yaml`）、変換は `convert_to_yaml.py`
- 数値は数値で持ち（`cook_minutes`・`cost_yen`）、投稿先ごとの表現は各投稿処理で変換する。投稿状態は書かない（DBで管理）
- 項目を増やすときは `recipe_model` の `_TOP_LEVEL_KEYS` / `PLATFORM_FIELDS`、`dump_recipe_yaml`、docs、`examples/` をそろえて更新し、`schema_version` を上げるか検討する
- `examples/` は楽天レシピに投稿済みの4件（手動3件は公開ページの内容から作成）。写真は置いていない（テストは `check_files=False`）
- 2026-10-17 時点: recipe.yaml があるのは投稿素材のチャーシューチャーハン・ピーマンのお吸い物和え。他の3件（エッグベネディクト・チョレギサラダ・豚の角煮）は recipe.txt のまま

## 動作確認の注意（重要）

- `main.py` / exe（`--dry-run` なし）は**実際に楽天レシピへ公開申請し、DBに記録し、バックアップを取る**。実行前にユーザーの許可を取る
- 画面の確認は `--dry-run`（入力まで行い、最後に下書きを削除）で行う
- 楽天レシピは**同じタイトルのレシピ・下書きを作れない**（「そのタイトルは既に使われています」→ タイトルが「下書き_日時」に戻される）。試験で下書きが残ったら必ず削除する（マイページ `?recipeStatus=draft`）
- 2026-10-17 時点: 公開中4件（手動3件＋チャーシューチャーハン）、公開待ち1件（ピーマンのお吸い物和え、10/17 に試験投稿）。post_history はこの2件（URL付き）。手動投稿の3件は投稿素材に無いため履歴にも無い
- 旧方式の `投稿済み` フォルダ・msedgedriver.exe・`.env` の `dest_folder` / `DRIVER_PATH` は 2026-10-17 にユーザーの了承を得て削除済み（ドライバは Selenium Manager が用意する）
- 誤パスワードのテストはしない（アカウントロック）

## 楽天レシピの画面仕様（調査済み）

- ログイン: `https://recipe.rakuten.co.jp/login/` → `login.account.rakuten.com`（ユーザーID `#user_id`→「次へ」`#cta001`、パスワード `#password_current`→`#cta011`）→ `/mypage/<会員番号>/`。毎回新しいプロファイルで起動するがパスキーは出ない（念のため `browser.CANCEL_PASSKEY_SCRIPT` で無効化）
- 投稿画面 `/recipe/post/`: 最初の保存で下書き（`#recipePost[data-recipeid]`）が作られ、**各欄は blur 時に AJAX（`/recipe/post/save/...`）で下書きに保存**される。公開申請（`/recipe/post/publish/`）は recipeId だけを送るため、blur と保存完了待ちが必須
  - ページの jQuery はグローバルに無い。保存中の通信は `browser.TRACK_SAVING_SCRIPT` が `window.__recipeSaving` に数える
  - 入力欄は `[data-name='レシピタイトル' / 'レシピコメント' / '人数' / '材料名' / '分量' / '作り方コメント' / 'きっかけ' / 'おいしくなるコツ' / '料理名']`。上限は `data-maxlength`（maxlength属性ではないので超えても入力できてしまう → `rakuten_recipe.validate_rakuten_post` で事前チェック）
  - 写真 `#food_image input[type=file]` → `#food_image_path` に src が入れば完了。調理時間 `#recipe_indication select`、費用 `#recipe_cost select`（どちらも name="time"）
  - 材料4行・作り方3行が初期表示。追加ボタン `[data-ratid='RecipePost_material_add_button' / 'RecipePost_process_add_button']`。**入力の合間に追加すると増えないことがあったため、先に必要な行数まで追加してから入力する**
  - カテゴリ: `[data-ratid='RecipePost_category_edit_button']` → `[data-tab-id='list']`（カテゴリ一覧、約1570件、`input.js_category_check[data-check-categoryname]`）。**チェックは行 `.js_category_check__flg` のクリックで切り替わる。input を直接押すと2回切り替わって外れる**。選択中は `.js_category__item`、最大5件。保存 `[data-ratid='RecipePost_category_search_save_button']`
  - 料理名は「もっと詳しく書く」`[data-ratid='RecipePost_show_more_area']` の中（閉じていると入力できない）
  - ガイドライン `input[name='guideline']`、公開申請 `[data-ratid='RecipePost_publish_botton']`（全項目がそろうと enabled）。成功すると `/mypage/<会員番号>/recipe...` へ移動
  - 下書き削除 `#recipeDelete` → `#recipeDeleteAction`
  - サイトのJS: `/scripts/webpc/0013_RECIPE_POST.min.js`（挙動が変わったらこれを読む）
- マイページ一覧 `/mypage/<会員番号>/recipe/?recipeStatus=all|publish|pending|draft|passback`、タイトルは `dt.recipe_name`

## コーディング規約

- コメント・ログ・ユーザー向けメッセージは日本語
- 失敗理由や分岐結果は `logger.get_logger()` でログファイルに残す（`[DEBUG]` の細かい出力は `print` のみ）
- 楽天レシピ側で起きる失敗は「投稿しない／下書きを消す」側に倒す（二重投稿・タイトル重複を作らない）。公開申請ボタンを押した後は下書きを消さない
- 不要になった変数・関数・設定は残さない（vulture で確認）
- コミットメッセージは日本語で簡潔に（1行目＋箇条書き数行）
