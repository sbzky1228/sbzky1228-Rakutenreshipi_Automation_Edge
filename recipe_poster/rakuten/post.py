"""
レシピ投稿モジュール - 楽天レシピの投稿画面に入力して公開申請する

投稿画面: https://recipe.rakuten.co.jp/recipe/post/
入力欄は data-name 属性（レシピタイトル、材料名、作り方コメント など）で探す。

投稿画面を開くと下書き（レシピID）が作られ、各欄は入力欄から離れた時（blur）に下書きへ保存される。
公開申請ボタンは保存済みの下書きを公開申請するだけなので、入力ごとに保存の完了を待つ。
公開申請のあと、マイページの「公開中」「公開待ち」に載ったことを確認できたら成功とする。
入力する内容は rakuten.convert.RakutenPost（recipe.yaml / recipe.txt から変換したもの）。
"""
import datetime
import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from recipe_poster.config import RECIPE_MYPAGE_URL, RECIPE_POST_URL, RECIPE_TOP_URL
from recipe_poster.logger import get_logger
from recipe_poster.rakuten.convert import MAX_LENGTHS, RakutenPost, choose_categories

# 投稿済みとみなすマイページのタブ（公開中・公開待ち）
POSTED_STATUSES = ("publish", "pending")
# 一覧を読むページ数の上限（1ページ目から順に、新しいレシピが出なくなるまで読む）
MAX_LIST_PAGES = 20


def _field(name: str) -> tuple[str, str]:
    return By.CSS_SELECTOR, f"[data-name='{name}']"


class RecipePoster:
    """楽天レシピへの投稿を行うクラス"""

    def __init__(self, driver: WebDriver, member_id: str):
        self.driver = driver
        self.member_id = member_id
        self.logger = get_logger()

    # ------------------------------------------------------------
    # 画面操作の共通処理
    # ------------------------------------------------------------
    def _wait(self, locator, timeout: float = 20) -> WebElement:
        return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located(locator))

    def _js_click(self, element: WebElement):
        # 画面下部の「自動で下書きに保存」の帯などに隠れてもクリックできるよう JavaScript で押す
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", element)

    def _wait_saved(self, timeout: float = 30):
        """下書きへの保存（画面の通信）が終わるまで待つ"""
        # window.__recipeSaving は rakuten.browser.TRACK_SAVING_SCRIPT が数える実行中の保存通信の数
        time.sleep(0.3)  # 入力欄から離れてから保存の通信が始まるまでの間を空ける
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("return (window.__recipeSaving || 0) === 0;"),
            "下書きへの保存が終わりませんでした")

    def _type(self, element: WebElement, text: str):
        """入力欄を空にしてから入力し、欄から離れて下書きに保存させる"""
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.DELETE)
        element.send_keys(text)
        self.driver.execute_script("arguments[0].blur();", element)
        self._wait_saved()
        # 保存を断られると入力欄が元に戻る（例: 同じタイトルのレシピ・下書きがあると「下書き_日時」に戻る）
        if (element.get_attribute("value") or "").strip() != text.strip():
            message = self.driver.execute_script(
                "const box = arguments[0].closest('.field_group');"
                "return box ? Array.from(box.querySelectorAll('.field_error_text'),"
                " e => e.textContent.trim()).filter(Boolean).join(' ') : '';", element)
            raise RuntimeError(f"「{element.get_attribute('data-name')}」の入力が保存されませんでした: {message}")

    def _fill_rows(self, field_names: tuple[str, ...], add_button: str, values: list[tuple[str, ...]]):
        """材料・作り方のように行の数が変わる欄を、必要な行数まで追加してから順に埋める"""
        def row_count(driver: WebDriver) -> int:
            return len(driver.find_elements(*_field(field_names[0])))

        while row_count(self.driver) < len(values):
            before = row_count(self.driver)
            self._js_click(self.driver.find_element(By.CSS_SELECTOR, f"[data-ratid='{add_button}']"))
            WebDriverWait(self.driver, 10).until(
                lambda d: row_count(d) > before, f"{field_names[0]}の行を追加できませんでした（{before}行）")

        for i, row_values in enumerate(values):
            for name, value in zip(field_names, row_values):
                self._type(self.driver.find_elements(*_field(name))[i], value)

    def save_screenshot(self, label: str):
        """失敗時の画面をログフォルダに保存する"""
        path = self.logger.log_dir / f"screenshot_{label}_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"
        try:
            self.driver.save_screenshot(str(path))
            self.logger.info(f"画面を保存しました: {path}")
        except Exception as e:
            self.logger.warning(f"画面を保存できませんでした: {e}")

    # ------------------------------------------------------------
    # 投稿済みレシピの確認
    # ------------------------------------------------------------
    def posted_recipes(self) -> dict[str, str]:
        """マイページの「公開中」「公開待ち」にあるレシピを {タイトル: レシピのURL} で返す"""
        recipes: dict[str, str] = {}
        for status in POSTED_STATUSES:
            for page in range(1, MAX_LIST_PAGES + 1):
                self.driver.get(f"{RECIPE_MYPAGE_URL}{self.member_id}/recipe/?recipeStatus={status}&page={page}")
                self._wait((By.CSS_SELECTOR, "a[href='/logout/']"))
                # 一覧の各レシピは /recipe/post/<レシピID>/ へのリンク。公開ページは /recipe/<レシピID>/
                page_recipes = self.driver.execute_script(
                    "return Array.from(document.querySelectorAll(\"a[href^='/recipe/post/']\"))"
                    ".filter(a => a.querySelector('dt.recipe_name'))"
                    ".map(a => [a.querySelector('dt.recipe_name').textContent.trim(),"
                    " a.getAttribute('href').split('/').filter(Boolean).pop()]);")
                new = {title: f"{RECIPE_TOP_URL}/recipe/{recipe_id}/" for title, recipe_id in page_recipes
                       if title not in recipes}
                if not new:
                    break
                recipes.update(new)
        return recipes

    # ------------------------------------------------------------
    # 投稿画面への入力
    # ------------------------------------------------------------
    def _fill_form(self, post: RakutenPost):
        driver = self.driver
        driver.get(RECIPE_POST_URL)
        self._wait(_field("レシピタイトル"))

        self._type(driver.find_element(*_field("レシピタイトル")), post.title)

        # 料理写真（アップロードされてプレビューが表示されるまで待つ）
        driver.find_element(By.CSS_SELECTOR, "#food_image input[type='file']").send_keys(str(post.image.resolve()))
        WebDriverWait(driver, 60).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#food_image_path").get_attribute("src"),
            "料理写真をアップロードできませんでした")
        self._wait_saved()

        Select(driver.find_element(By.CSS_SELECTOR, "#recipe_indication select")).select_by_visible_text(
            post.cooking_time)
        self._wait_saved()
        if post.cost:  # 費用目安は任意項目
            Select(driver.find_element(By.CSS_SELECTOR, "#recipe_cost select")).select_by_visible_text(post.cost)
            self._wait_saved()

        self._type(driver.find_element(*_field("レシピコメント")), post.comment)
        self._type(driver.find_element(*_field("人数")), post.servings)
        self._fill_rows(("材料名", "分量"), "RecipePost_material_add_button", post.ingredients)
        self._fill_rows(("作り方コメント",), "RecipePost_process_add_button", [(step,) for step in post.steps])
        self._type(driver.find_element(*_field("きっかけ")), post.reason)
        if post.tip:
            self._type(driver.find_element(*_field("おいしくなるコツ")), post.tip)

        self._select_categories(post)

        # 「もっと詳しく書く」を開いて料理名を入力する
        if len(post.dish_name) <= MAX_LENGTHS["料理名"]:
            dish_input = driver.find_element(*_field("料理名"))
            if not dish_input.is_displayed():
                self._js_click(driver.find_element(By.CSS_SELECTOR, "[data-ratid='RecipePost_show_more_area']"))
                WebDriverWait(driver, 10).until(lambda d: dish_input.is_displayed())
            self._type(dish_input, post.dish_name)

        # ガイドラインに同意（未チェックのときだけ押す）
        driver.execute_script(
            "const box = document.querySelector(\"input[name='guideline']\"); if (!box.checked) box.click();")
        self._wait_saved()

    def _select_categories(self, post: RakutenPost):
        """カテゴリ追加の画面で「カテゴリ一覧から設定」を開き、カテゴリを選んで保存する"""
        driver = self.driver
        self._js_click(driver.find_element(By.CSS_SELECTOR, "[data-ratid='RecipePost_category_edit_button']"))
        list_tab = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-tab-id='list']")))
        self._js_click(list_tab)

        available = driver.execute_script(
            "return Array.from(document.querySelectorAll('input.js_category_check'),"
            " e => e.dataset.checkCategoryname);")
        categories = choose_categories(available, post)
        unknown = [name for name in post.categories if name not in available]
        if unknown:
            self.logger.warning(f"{post.key}: 楽天レシピに無いカテゴリは設定しません: {' / '.join(unknown)}")
        # 楽天レシピは行（.js_category_check__flg）のクリックでチェックを切り替える。
        # チェックボックス自体を押すと、行のクリック処理と合わせて2回切り替わり外れてしまう
        for name in categories:
            driver.execute_script(
                "const box = Array.from(document.querySelectorAll('.tab_content_list input.js_category_check'))"
                ".find(e => e.dataset.checkCategoryname === arguments[0]);"
                "if (box && !box.checked) box.closest('.js_category_check__flg').click();", name)
        selected = driver.execute_script(
            "return Array.from(document.querySelectorAll('.js_category__item'), e => e.dataset.selectCategoryname);")
        self.logger.info(f"カテゴリ: {' / '.join(selected)}")
        if not selected:
            raise RuntimeError("カテゴリを選択できませんでした")

        self._js_click(driver.find_element(By.CSS_SELECTOR, "[data-ratid='RecipePost_category_search_save_button']"))
        WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-tab-id='list']")))
        self._wait_saved()

    def _visible_errors(self) -> list[str]:
        """投稿画面に表示されている入力エラーの文言"""
        return [e.text.strip() for e in self.driver.find_elements(By.CSS_SELECTOR, ".field_error_text")
                if e.is_displayed() and e.text.strip()]

    # ------------------------------------------------------------
    # 投稿
    # ------------------------------------------------------------
    def post(self, post: RakutenPost, dry_run: bool = False) -> str | None:
        """
        レシピを入力して公開申請する。投稿を確認できればレシピのURLを返し、失敗したらNone。
        dry_run=True の場合は入力だけ行い、公開申請はしない（成功なら空文字を返す）。

        公開申請の前に終わった場合（お試し実行・失敗）は、入力中にできた下書きを削除する。
        同じタイトルの下書きが残ると、次回の投稿でタイトルが使えなくなるため。
        """
        publish_clicked = False
        try:
            self._fill_form(post)

            publish_button = self.driver.find_element(By.CSS_SELECTOR, "[data-ratid='RecipePost_publish_botton']")
            try:
                WebDriverWait(self.driver, 20).until(lambda d: publish_button.is_enabled())
            except TimeoutException:
                errors = self._visible_errors()
                self.logger.error(f"{post.key}: 入力内容に不足があり公開申請ボタンが押せません: {errors or '（エラー表示なし）'}")
                self.save_screenshot(post.key)
                return None

            if dry_run:
                self.logger.info(f"{post.key}: 入力が完了しました（お試し実行のため公開申請はしません）")
                self.save_screenshot(f"dryrun_{post.key}")
                return ""

            self._js_click(publish_button)
            publish_clicked = True
            self.logger.info(f"{post.key}: 公開申請ボタンを押しました")
            return self._wait_until_posted(post)

        except Exception as e:
            self.logger.error(f"{post.key}: 投稿中にエラーが発生しました: {e.__class__.__name__}: {e}")
            self.save_screenshot(post.key)
            return None
        finally:
            if not publish_clicked:
                self._delete_draft()

    def _delete_draft(self):
        """表示中の投稿画面の下書きを削除する"""
        try:
            draft_id = self.driver.execute_script(
                "const form = document.querySelector('#recipePost'); return form ? form.dataset.recipeid : '';")
            if not self.driver.current_url.startswith(RECIPE_POST_URL) or draft_id in ("", "0", None):
                return  # 投稿画面ではない、またはまだ何も保存されておらず下書きは作られていない
            self._js_click(self.driver.find_element(By.ID, "recipeDelete"))
            self._js_click(WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.ID, "recipeDeleteAction"))))
            WebDriverWait(self.driver, 30).until(lambda d: not d.current_url.startswith(RECIPE_POST_URL))
            self.logger.info(f"入力中にできた下書き（レシピID {draft_id}）を削除しました")
        except Exception as e:
            self.logger.warning(f"下書きを削除できませんでした（マイページの「下書き」から削除してください）: {e.__class__.__name__}")

    def _wait_until_posted(self, post: RakutenPost, timeout: float = 60) -> str | None:
        """公開申請のあと投稿画面から移動するのを待ち、マイページに載ったかを確かめてレシピのURLを返す"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.driver.current_url.startswith(RECIPE_POST_URL):
                break
            error_modal = self.driver.find_elements(By.CSS_SELECTOR, "[data-modal-id='input_error'] #modalMainText")
            if error_modal and error_modal[0].is_displayed():
                self.logger.error(f"{post.key}: 公開申請でエラーが表示されました: {error_modal[0].text} {self._visible_errors()}")
                self.save_screenshot(post.key)
                return None
            time.sleep(1)
        else:
            self.logger.error(f"{post.key}: 公開申請のあと画面が切り替わりませんでした")
            self.save_screenshot(post.key)
            return None

        url = self.posted_recipes().get(post.title)
        if url:
            self.logger.info(f"{post.key}: 投稿できました（マイページで「{post.title}」を確認）: {url}")
            return url
        self.logger.error(f"{post.key}: マイページの公開中・公開待ちに「{post.title}」が見つかりません")
        return None
