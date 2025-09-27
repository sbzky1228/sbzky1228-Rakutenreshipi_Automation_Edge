import psycopg

#データベースから累計件数を取得(データベースへの記録がない場合は0を返すように設定)
def get_total_count(conn):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT total_post_count
                FROM "Recipe_info"
                ORDER BY id DESC
                LIMIT 1;
                """
            )
            result = cur.fetchone() # 結果を1行取得(データベース内の最終行の結果上記で取得)

            if result:
                return result[0]  # 累計件数を返す
            else:
                return 0          # データがなければ0を返す

    except Exception as e:
        print("エラーが発生しました:", e)
        return 0
