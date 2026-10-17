"""
楽天ログインモジュール - 楽天レシピのログイン画面から楽天会員IDでログインする

楽天レシピの「ログイン」→ 楽天の認証画面（login.account.rakuten.com）でID・パスワードを入力し、
楽天レシピのマイページに戻ったらログイン成功とする。
"""
import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from recipe_poster.config import RAKUTEN_USER_ID, RAKUTEN_PASSWORD, RECIPE_LOGIN_URL, RECIPE_MYPAGE_URL
from recipe_poster.logger import get_logger

RAKUTEN_LOGIN_HOST = "login.account.rakuten.com"

_USER_ID_INPUT = (By.CSS_SELECTOR, "input#user_id, input[name='username']")
_PASSWORD_INPUT = (By.CSS_SELECTOR, "input#password_current, input[type='password']")
# 「次へ」は button 要素とは限らない（div#cta001 など）ため、IDと文言の両方で探す
_NEXT_BUTTON = (By.XPATH, "//*[@id='cta001' or @id='cta011' or normalize-space(text())='次へ']")
_USE_PASSWORD_BUTTON = (By.XPATH, "//*[normalize-space(text())='パスワードを使用する']")
# ログイン済みのときだけ表示されるヘッダーの「ログアウト」
_LOGOUT_LINK = (By.CSS_SELECTOR, "a[href='/logout/']")


def _visible(driver: WebDriver, locator) -> list:
    return [e for e in driver.find_elements(*locator) if e.is_displayed()]


def _click_next(driver: WebDriver) -> bool:
    buttons = _visible(driver, _NEXT_BUTTON)
    if buttons:
        buttons[0].click()
        return True
    return False


def _wait_until_gone(driver: WebDriver, locator, timeout: float = 20):
    """画面が切り替わるまで待ち、同じ入力を二重に送らないようにする"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and _visible(driver, locator):
        time.sleep(0.5)


def _complete_login_form(driver: WebDriver, timeout: float = 90) -> bool:
    """
    楽天の認証画面で、画面の状態に応じてID・パスワードを入力し、認証画面から離れたら成功とする。
    誤った情報で何度も送信するとアカウントがロックされるおそれがあるため、ID・パスワードは1回しか送らない。
    """
    logger = get_logger()
    user_id_sent = False
    password_sent = False
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if RAKUTEN_LOGIN_HOST not in driver.current_url:
            return True
        try:
            password_inputs = _visible(driver, _PASSWORD_INPUT)
            user_id_inputs = _visible(driver, _USER_ID_INPUT)
            if password_inputs:
                if password_sent:
                    logger.error("パスワードを送信しましたがログインできませんでした。"
                                 ".env の RAKUTEN_PASSWORD を確認してください（アカウントロック防止のため再送信しません）")
                    return False
                password_inputs[0].send_keys(RAKUTEN_PASSWORD)
                if not _click_next(driver):
                    password_inputs[0].submit()
                password_sent = True
                logger.info("パスワードを入力しました")
                _wait_until_gone(driver, _PASSWORD_INPUT)
            elif _visible(driver, _USE_PASSWORD_BUTTON):
                logger.info("パスキー認証をやめて、パスワードでのログインに切り替えます")
                _visible(driver, _USE_PASSWORD_BUTTON)[0].click()
                _wait_until_gone(driver, _USE_PASSWORD_BUTTON, timeout=10)
            elif user_id_inputs:
                if user_id_sent:
                    logger.error("ユーザーIDを送信しましたが次の画面に進めませんでした。"
                                 ".env の RAKUTEN_USER_ID を確認してください（アカウントロック防止のため再送信しません）")
                    return False
                user_id_inputs[0].clear()
                user_id_inputs[0].send_keys(RAKUTEN_USER_ID)
                if not _click_next(driver):
                    user_id_inputs[0].submit()
                user_id_sent = True
                logger.info("ユーザーIDを入力しました")
                _wait_until_gone(driver, _USER_ID_INPUT)
        except Exception as e:
            # 画面の切り替わり中に要素が消えた場合などは、次のループで判定し直す
            print(f"[DEBUG] ログイン画面の操作中に画面が切り替わりました: {e.__class__.__name__}")
        time.sleep(0.5)

    logger.error(f"ログイン画面での認証が完了しませんでした。現在のURL: {driver.current_url}")
    return False


def login_to_rakuten(driver: WebDriver) -> str | None:
    """
    楽天レシピにログインし、マイページの会員番号（/mypage/<番号>/ の番号）を返す。失敗時は None。
    """
    logger = get_logger()
    if not RAKUTEN_USER_ID or not RAKUTEN_PASSWORD:
        logger.error(".env に RAKUTEN_USER_ID / RAKUTEN_PASSWORD が設定されていません")
        return None

    try:
        driver.get(RECIPE_LOGIN_URL)
        if RAKUTEN_LOGIN_HOST in driver.current_url and not _complete_login_form(driver):
            return None

        # マイページを開き、ログアウトのリンクと会員番号でログインできたことを確かめる
        driver.get(RECIPE_MYPAGE_URL)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            member = re.search(r"/mypage/(\d+)/", driver.current_url)
            if member and driver.find_elements(*_LOGOUT_LINK):
                logger.info("楽天レシピへのログインに成功しました")
                return member.group(1)
            time.sleep(0.5)
        logger.error(f"楽天レシピにログインできませんでした。現在のURL: {driver.current_url}")
        return None
    except Exception as e:
        logger.error(f"ログイン処理でエラーが発生しました: {e}")
        return None
