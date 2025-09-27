from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

def login_to_rakuten():
    user_id = os.getenv('RAKUTEN_USER_ID')
    pass_word = os.getenv('RAKUTEN_PASSWORD')
    # Edge の WebDriver を自動取得
    # 手動でダウンロードしたEdge WebDriverのパスを指定（例: ./drivers/msedgedriver.exe）
    # driver_path = os.getenv('DRIVER_PATH')  # 必要に応じてパスを調整
    # # WebDriverサービスを起動してEdgeドライバを起動
    # service = Service(executable_path=driver_path)
    # driver = webdriver.Edge(service=service)

    driver = None
    driver_path = os.getenv('DRIVER_PATH')  # .env に設定したパス

    try:
        if driver_path and os.path.exists(driver_path):
            print(f"✅ まず既存のドライバを使用します: {driver_path}")
            service = Service(driver_path)
            driver = webdriver.Edge(service=service)
        else:
            raise FileNotFoundError("指定された msedgedriver.exe が存在しません")

    except (SessionNotCreatedException, WebDriverException, FileNotFoundError) as e:
        print(f"⚠️ 既存のドライバでは起動できませんでした: {e}")
        print("➡️ webdriver-manager で最新版をインストールして再試行します")

        service = Service(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service)

    # 楽天レシピのログインページを開く
    driver.get("https://recipe.rakuten.co.jp/login/")

    # 2秒待機（ページ読み込みを待つ）
    time.sleep(2)

    # ユーザーID（メールアドレス）を入力
    email_input = driver.find_element(By.ID, "user_id")
    email_input.send_keys(user_id)  # 🔹 ここに自分のメールアドレスを入力

    # ログインボタンをクリック
    login_button = driver.find_element(By.ID, "cta001")
    login_button.click()

    # パスワードを入力
    # 最大10秒間、パスワード入力欄が表示されるのを待つ
    password_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "password_current"))
    )
    password_input.send_keys(pass_word)  # 🔹 ここに自分のパスワードを入力

    # 次へボタンをクリック
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "cta011"))  # 🔹 「次へ」ボタンの正しいIDを確認！
    )
    login_button.click()

    # 5秒待機（ログイン処理が完了するまで待つ）
    time.sleep(5)

    return driver