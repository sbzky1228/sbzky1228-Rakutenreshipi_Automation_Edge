import psycopg

# データベースにレシピ情報を追加(年、月、日、フォルダ名(レシピ名)、累計件数)
def add_recipe_info(conn, year, month, day, folder_name, total_count):
    try:
        with conn.cursor() as cur:
            # SQL実行
            cur.execute(
                """
                INSERT INTO "Recipe_info" (recipe_name, post_day, post_month, post_year, total_post_count)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (folder_name, day, month, year, total_count)
            )
        conn.commit()  # 明示的にコミットが必要

    except Exception as e:
        print("エラーが発生しました:", e)
        conn.rollback()
