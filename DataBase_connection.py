import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

def database_connection():
    # 接続情報（自分の環境に合わせて変更）
    conn = psycopg.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )
    return conn