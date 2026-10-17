"""ブラウザ管理モジュール - Selenium で Microsoft Edge を起動する"""
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.edge.service import Service
from config import DRIVER_PATH
from logger import get_logger

# パスキー（publicKey）の navigator.credentials.get を、ユーザーがキャンセルした時と同じ
# NotAllowedError で失敗させる。楽天のログインでパスキーのダイアログが出て止まるのを防ぐ
CANCEL_PASSKEY_SCRIPT = """
(() => {
  if (!navigator.credentials || !navigator.credentials.get) return;
  const originalGet = navigator.credentials.get.bind(navigator.credentials);
  navigator.credentials.get = (options) => {
    if (options && options.publicKey) {
      return Promise.reject(new DOMException('Passkey was cancelled by automation.', 'NotAllowedError'));
    }
    return originalGet(options);
  };
})();
"""

# 楽天レシピの投稿画面は入力欄ごとに下書きを保存する通信（/recipe/post/save/...）を行う。
# 保存の完了を待てるよう、実行中の通信の数を window.__recipeSaving に数えておく
TRACK_SAVING_SCRIPT = """
(() => {
  window.__recipeSaving = 0;
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__isRecipeSave = String(url).includes('/recipe/post/');
    return open.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    if (this.__isRecipeSave) {
      window.__recipeSaving++;
      this.addEventListener('loadend', () => { window.__recipeSaving--; }, { once: true });
    }
    return send.apply(this, args);
  };
})();
"""


def create_driver() -> webdriver.Edge:
    """
    Edge を起動する。

    Selenium Manager がインストール済みの Edge に合う msedgedriver を自動で用意する。
    自動取得に失敗した場合（オフライン等）だけ、.env の DRIVER_PATH のドライバで起動する。
    """
    options = webdriver.EdgeOptions()
    options.add_argument("--window-size=1280,1000")
    # 広告などの読み込み完了を待たず、画面の組み立てが終わった時点で操作を始める
    options.set_capability("pageLoadStrategy", "eager")
    try:
        driver = webdriver.Edge(options=options)
    except WebDriverException as e:
        if not (DRIVER_PATH and Path(DRIVER_PATH).exists()):
            raise
        get_logger().warning(f"Edgeドライバを自動で用意できなかったため、DRIVER_PATH のドライバを使います: {e.msg}")
        driver = webdriver.Edge(service=Service(DRIVER_PATH), options=options)

    for script in (CANCEL_PASSKEY_SCRIPT, TRACK_SAVING_SCRIPT):
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
    driver.set_page_load_timeout(60)
    return driver
