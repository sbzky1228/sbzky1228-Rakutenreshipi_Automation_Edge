from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from selenium.common.exceptions import NoSuchElementException
from Get_Recipe_Info import get_recipe_info

def recipe_post(driver, recipe):
    try:
        # レシピ情報をテキストファイルから読み込む関数
        file_path = recipe["text"]
        image_path = recipe["image"]

        # レシピデータを取得
        recipe_data = get_recipe_info(file_path)

        # 調理時間を楽天レシピの選択肢に変換する関数
        def convert_cooking_time(time_str):
            time_options =  [
            ("5分以内", 5),
            ("約10分", 10),
            ("約15分", 15),
            ("約30分", 30),
            ("約1時間", 60),
            ("1時間以上", 999)  # 999はダミーの上限値
            ]
            match = re.search(r"(\d+)\s*～\s*(\d+)", time_str)
            if match:
                min_time = int(match.group(1))
                max_time = int(match.group(2))
                for t in time_options:
                    if min_time <= t <= max_time:
                        return label
                return time_options[-1][0] if min_time > 60 else time_options[0][0]
            # 単一の数字だけあるパターン（例: 約15分）
            match_single = re.search(r"(\d+)", time_str)
            if match_single:
                val = int(match_single.group(1))
                for label, time in time_options:
                    if val <= time:
                        return label
                return time_options[-1][0]

            return time_options[0][0]

        def convert_cost(cost_str):
            cost_options = [
                ("100円以下", 0, 100),
                ("300円前後", 100, 300),
                ("500円前後", 300, 500),
                ("1,000円前後", 500, 1000),
                ("2,000円前後", 1000, 2000),
                ("3,000円前後", 2000, 3000),
                ("5,000円前後", 3000, 5000),
                ("1,0000円以上", 10000, float("inf"))
            ]

            # 「数値～数値」のパターンを抽出
            match = re.search(r"(\d{3,4})\s*[～\-〜]\s*(\d{3,4})", cost_str)
            if match:
                min_cost = int(match.group(1))
                max_cost = int(match.group(2))
                for label, low, high in cost_options:
                    if low <= min_cost and max_cost <= high:
                        return label
                # 範囲がオーバーしている場合は「1,000円以上」に分類
                return "1,000円以上"
            # 単一の費用（例：800円）しか書かれていない場合にも対応
            match_single = re.search(r"(\d{3,4})", cost_str)
            if match_single:
                val = int(match_single.group(1))
                for label, low, high in cost_options:
                    if low <= val <= high:
                        return label
                return "1,000円以上"
            # パースできなかった場合のデフォルト
            return "500円～1,000円"
        
        def click_category_by_text(driver, category_name):
            try:
                # 指定テキストを含む span 要素を取得してクリック
                target_element = driver.find_element(
                    By.XPATH, f"//span[contains(text(), '{category_name}')]"
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", target_element)
                driver.execute_script("arguments[0].click();", target_element)
                time.sleep(1)  # ページが展開されるのを待つ
            except NoSuchElementException:
                print(f"❌ カテゴリー「{category_name}」が見つかりませんでした。")

        #「レシピ投稿」ボタンをクリック
        post_button = driver.find_element(By.XPATH, "//a[@href='/recipe/post/']")
        post_button.click()
        time.sleep(1)

        # レシピタイトルの入力
        title_field = driver.find_element(By.XPATH, "//input[@type='text']")
        title_field.send_keys(recipe_data["レシピタイトル"])
        title_field.send_keys(Keys.TAB)
        time.sleep(1)

        #写真をアップロード
        picture_input = driver.find_element(By.XPATH, "//input[@type='file']")
        # 2. 非表示なら表示させる（style変更）
        picture_input.send_keys(str(image_path))
        time.sleep(5)

        # # 調理時間の選択
        time_dropdown = Select(driver.find_element(By.NAME, "time"))
        time_dropdown.select_by_visible_text(convert_cooking_time(recipe_data["調理時間"]))

        # 費用の選択（例: 500～1000円なら「500～1000円」を選択）
        # まず費用欄の親要素を取得
        cost_section = driver.find_element(By.ID, "recipe_cost")
        # その中の select 要素（費用のプルダウン）を取得
        cost_dropdown = Select(cost_section.find_element(By.NAME, "time"))
        # 使用例（先ほど作った関数から取得）
        cost_label = convert_cost(recipe_data["費用"])
        cost_dropdown.select_by_visible_text(cost_label)

        # レシピコメントの入力
        comment_field = driver.find_element(By.XPATH, "//*[@data-name='レシピコメント']")
        comment_field.send_keys(recipe_data["レシピコメント"])
        comment_field.send_keys(Keys.TAB)
        time.sleep(1)

        # 材料の入力
        the_number_of_pepole = driver.find_element(By.XPATH, "//*[@data-name='人数']")
        the_number_of_pepole.send_keys("2")
        the_number_of_pepole.send_keys(Keys.TAB)
        time.sleep(1)

        for i, ingredients in enumerate(recipe_data["材料"]):
            if i >= 4:  # 4つ目以降なら追加ボタンを押す
                # JavaScriptでボタンをクリック
                button = driver.find_element(By.CSS_SELECTOR, "[data-ratid='RecipePost_material_add_button']")
                driver.execute_script("arguments[0].click();", button)
                time.sleep(1)
            ingredient_field = driver.find_elements(By.XPATH, "//*[@data-name='材料名']")
            ingredient_field[i].send_keys(ingredients["material"])
            ingredient_field[i].send_keys(Keys.TAB)
            time.sleep(1)
            ingredient_field = driver.find_elements(By.XPATH, "//*[@data-name='分量']")
            ingredient_field[i].send_keys(ingredients["amount"])
            ingredient_field[i].send_keys(Keys.TAB)
            time.sleep(1)

        # 作り方の入力
        for j, step in enumerate(recipe_data["作り方"]):
            if j >= 3:  # 3つ目以降なら追加ボタンを押す
                # JavaScriptでボタンをクリック
                button = driver.find_element(By.CSS_SELECTOR, "[data-ratid='RecipePost_process_add_button']")
                # driver.execute_script("arguments[0].scrollIntoView(true);", button)  # スクロールで表示保証
                time.sleep(1)
                driver.execute_script("arguments[0].click();", button)
                # time.sleep(3)
                # 要素数がj+1になるまで待つ
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.XPATH, "//*[@data-name='作り方コメント']")) > j
                )
            step_field = driver.find_elements(By.XPATH, "//textarea[@data-name='作り方コメント']")
            step_field[j].send_keys(step)
            step_field[j].send_keys(Keys.TAB)
            time.sleep(1)
        
        # きっかけ・コツ・カテゴリの入力
        reason_field = driver.find_element(By.XPATH, "//*[@data-name='きっかけ']")
        reason_field.send_keys(recipe_data["きっかけ"])
        reason_field.send_keys(Keys.TAB)
        time.sleep(1)

        tip_field = driver.find_element(By.XPATH, "//*[@data-name='おいしくなるコツ']")
        tip_field.send_keys(recipe_data["おいしくなるコツ"])
        tip_field.send_keys(Keys.TAB)
        time.sleep(1)

        category_button = driver.find_element(By.XPATH, "//*[@data-ratid='RecipePost_category_edit_button']")
        driver.execute_script("arguments[0].click();", category_button)
        time.sleep(1)

        # 「カテゴリ一覧から設定」をクリック
        category_table = driver.find_element(By.XPATH, "//*[@data-tab-id='list']")
        driver.execute_script("arguments[0].click();", category_table)
        time.sleep(1)

        # 簡単料理カテゴリ
        click_category_by_text(driver, "簡単料理・時短")

        label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='男の簡単料理']/..")
        driver.execute_script("arguments[0].scrollIntoView(true);", label)
        driver.execute_script("arguments[0].click();", label)
        
        click_category_by_text(driver, "節約料理")
        if "100以下" in cost_label:
            label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='100円以下の節約料理']/..")
            driver.execute_script("arguments[0].scrollIntoView(true);", label)
            driver.execute_script("arguments[0].click();", label)
        elif "300円前後" in cost_label:
            label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='300円前後の節約料理']/..")
            driver.execute_script("arguments[0].scrollIntoView(true);", label)
            driver.execute_script("arguments[0].click();", label)
        elif "500円前後" in cost_label:
            label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='500円前後の節約料理']/..")
            driver.execute_script("arguments[0].scrollIntoView(true);", label)
            driver.execute_script("arguments[0].click();", label)

        click_category_by_text(driver, "今日の献立")

        category_text = recipe_data.get("カテゴリ", "")
        if "朝食" in category_text:
            label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='朝食の献立（朝ごはん）']/..")
            driver.execute_script("arguments[0].scrollIntoView(true);", label)
            driver.execute_script("arguments[0].click();", label)
        if "昼食" in category_text:
            label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='昼食の献立（昼ごはん）']/..")
            driver.execute_script("arguments[0].scrollIntoView(true);", label)
            driver.execute_script("arguments[0].click();", label)
        if "夕食" in category_text or "夕飯" in category_text:
            label = driver.find_element(By.XPATH, "//input[@data-check-categoryname='夕食の献立（晩御飯）']/..")
            driver.execute_script("arguments[0].scrollIntoView(true);", label)
            driver.execute_script("arguments[0].click();", label)

        # 保存ボタンのクリック
        try:
            save_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@data-ratid='RecipePost_category_search_save_button']"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
            driver.execute_script("arguments[0].click();", save_button)
            print("✅ 保存ボタンをクリックしました。")
        except Exception as e:
            print(f"❌ 保存ボタンのクリックに失敗しました: {e}")
        
        time.sleep(5)

        # ガイドラインチェックボックスにチェック
        label = driver.find_element(By.XPATH, "//*[@data-ratid='RecipePost_guideline_link']/..")
        driver.execute_script("arguments[0].scrollIntoView(true);", label)
        driver.execute_script("arguments[0].click();", label)

        # driver.get("https://recipe.rakuten.co.jp/mypage")

        # 公開申請ボタンのクリック
        try:
            open_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@data-ratid='RecipePost_publish_botton']"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", open_button)
            driver.execute_script("arguments[0].click();", open_button)
            print("✅ 公開申請しました。")
        except Exception as e:
            print(f"❌ 公開申請できませんでした: {e}")

        time.sleep(5)

        return True

    except Exception as e:
        return False