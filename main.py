from datetime import date                                               # 今日の日付を取得するために使用
from Check_Target import check_target                                   # 投稿対象のレシピ名(フォルダ名)を取得
from Get_Total_Count_Of_This_Month_From_DataBase import get_total_count # データベースから今月の累計投稿件数を取得
from Add_Recipe_Information_To_DataBese import add_recipe_info          # 投稿したレシピをデータベースに記録する
from RakutenRecipe_Login import login_to_rakuten                        # 楽天レシピにログイン    
from RakutenRecipe_Post import recipe_post                              # レシピを投稿
# from line_notify import send_line_notify                              # 後述のLINE通知関数
from dotenv import load_dotenv                                          # .envファイルを読み込むために使用   
from DataBase_connection import database_connection                     # データベース接続
from Move_Folder import move_folder                                     # 投稿済みフォルダを移動

def main():
    # .envファイルのパスを指定して読み込む(パスワードやIDを環境変数として使用するため)
    load_dotenv('.env')
    # 今日の日付を取得
    today = date.today()
    # 年、月、日を取得
    year = today.year
    month = today.month
    day = today.day
    # データベース接続
    conn = database_connection()
    # 1.データベースから投稿累計数を取得
    total_count = get_total_count(conn) 
    # 2. ベースフォルダから対象数およびレシピ名(フォルダ名)を取得
    recipes = check_target()
    # 3. 楽天レシピにログイン（Seleniumドライバ起動含む）
    driver = login_to_rakuten()
    # 4. 対象フォルダに格納されている投稿素材をチェックし投稿
    for folder_name, recipe in zip(recipes.folder_names, recipes.recipes):     # 取得したフォルダ内に格納されているリストの数だけ繰り返す
        post = recipe_post(driver, recipe)
        # 投稿完了後データベースに記録しフォルダを移動
        if post:
            total_count += 1    #累計投稿数をインクリメント
            add_recipe_info(conn, year, month, day, folder_name, total_count)
            # 投稿対象をフォルダから移動(※後で追加※)
            move_folder(folder_name)

    driver.quit()   #楽天レシピを閉じる
    conn.close()    #DBとの接続を解除

        # 6b. LINE通知で完了報告(※後で追加※)
        # post_countを使用して件数を表示
        # message = f"{recipe_name} の投稿が完了しました。"
        # send_line_notify(message)
    
    # else:
        # 今月の投稿数が30件以上であることをLINEで通知(※後で追加※)

    
if __name__ == "__main__":
    main()