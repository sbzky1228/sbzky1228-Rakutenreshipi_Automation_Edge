---
name: rakuten-recipe-post
description: 楽天レシピ自動投稿ツール（Selenium + Edge）を改修・試験・不具合調査する手順と、楽天レシピ投稿画面の自動操作の落とし穴。「楽天レシピに投稿できない」「公開申請ボタンが押せない」「タイトルが下書き_日時になる」「カテゴリが選択されない」「材料・作り方の行が増えない」「投稿したのにDBだけ記録される」「recipe.txt の形式を変えたい」「楽天レシピの画面が変わった」「exeを作り直したい」といったときに使う。
---

# 楽天レシピ自動投稿の改修・試験

画面仕様の詳細は CLAUDE.md の「楽天レシピの画面仕様」にある。ここでは作業の進め方と、つまずきやすい点をまとめる。

## 作業の順番

1. **変更前に現状を把握する**: `python -X utf8 -m pytest` と pyflakes / vulture が通ることを確認
2. **読み込み・変換の変更**はブラウザ不要の部分だけで完結させる（recipe.yaml は `recipe_poster/recipes/model.py`、recipe.txt は `recipes/text.py`、楽天向けの変換は `rakuten/convert.py`。テストは `tests/test_recipe_model.py`・`test_recipe_text.py`・`test_rakuten_convert.py`）。実際の素材は次で一括確認できる:
   ```bash
   python -X utf8 -c "from pathlib import Path; from recipe_poster import config; from recipe_poster.recipes.folders import *; from recipe_poster.rakuten.convert import *; [print(f.name, validate_rakuten_post(to_rakuten_post(load_recipe(f), f))) for f in find_recipe_folders(Path(config.BASE_FOLDER))]"
   ```
3. **画面操作の変更**は `--dry-run` で確かめる（入力まで行い、最後に下書きを削除する。公開申請・投稿履歴の記録・バックアップはしない。投稿履歴の読み取りのためDBには接続する）
   ```bash
   python -X utf8 main.py --dry-run --folder <フォルダ名>
   ```
   失敗時は `logs/screenshot_*.png` とログを見る
4. **本番投稿はユーザーの許可を得てから**、`--folder` で1件に絞って行う。投稿後はマイページの「公開待ち」と保存内容（投稿画面 `/recipe/post/<ID>/` の各欄の value）を読み取りで確認する
5. 試験後、マイページの下書き（`/mypage/<会員番号>/recipe/?recipeStatus=draft`）が0件であることを確認する
6. コードを変えたら exe を作り直し、別フォルダから `--dry-run` で起動確認する（CLAUDE.md の手順）

## 画面が変わったときの調べ方

- まず `--dry-run` のスクリーンショットでどこまで進んだかを見る
- 投稿画面の挙動はサイトのJS `https://recipe.rakuten.co.jp/scripts/webpc/0013_RECIPE_POST.min.js` を curl で取得し、`data-ratid` や `.on("blur"` / `.on("click"` で検索すると早い（推測でセレクタを足すより確実）
- 入力欄の状態は次のように一覧で取れる（どの欄が `error` か、値が何か）:
  ```js
  Array.from(document.querySelectorAll('#recipePost .js_input_count__target'),
    e => [e.dataset.name, e.value, e.classList.contains('error')])
  ```
  `.field_error_text` は非表示（display:none）のままエラー文言だけ入ることがあるので、表示状態に関係なく textContent も見る

## 落とし穴（実際に起きたもの）

| 症状 | 原因 | 対処 |
|---|---|---|
| 投稿したことになっているのに楽天レシピに無い | 各欄は blur 時に下書きへ保存され、公開申請は保存済みの下書きを送るだけ。入力しただけでは保存されない | 入力後に blur し、`window.__recipeSaving` が0になるまで待つ（`rakuten/post.py` の `RecipePoster._type`）。成功判定はマイページの「公開待ち」で行う |
| タイトルが「下書き_日時」に戻る／公開申請ボタンが押せない | 同じタイトルのレシピ・**下書き**が既にある（試験で残った下書きも含む） | 失敗・お試し実行では下書きを削除する（`post()` の finally）。残っていたら下書き一覧から消す |
| カテゴリが選択されない（選択中0件） | 行 `.js_category_check__flg` のクリックで切り替える作り。input を `click()` すると input の切り替え＋行のクリック処理で2回切り替わる | 行要素をクリックする |
| 作り方の行が追加されない | 入力・保存の合間に追加ボタンを押した | 先に必要な行数まで追加してから入力する |
| `jQuery is not defined` | ページの jQuery はモジュール内にありグローバルに無い | 通信の監視は XMLHttpRequest をラップした init スクリプトで行う |
| 起動が遅い（1ページ数十秒） | 広告の読み込み完了を待っている | `pageLoadStrategy = eager` |
| ドライバのバージョン不一致 | 手動で置いた msedgedriver.exe が古い | Selenium Manager に任せる（DRIVER_PATH は自動取得できないときの予備） |

## 守ること

- 誤ったID・パスワードで繰り返しログインしない（アカウントロック）。ID・パスワードは1回だけ送る
- 公開申請ボタンを押した後は下書きを削除しない（投稿済みの可能性がある）
- テスト（pytest・GitHub Actions）に `.env` や実サイト・DBへの接続を持ち込まない
