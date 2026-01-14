from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import psycopg
from psycopg.rows import dict_row  # чтобы получать JSON-словарь

# Загружаем переменные окружения
load_dotenv()

app = FastAPI()

# Функция подключения к БД
def get_connection():
    return psycopg.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        row_factory=dict_row  # возвращает словари вместо кортежей
    )

# Тестовый эндпоинт
@app.get("/ping")
def ping():
    return {"message": "pong"}

# Чтение данных из таблицы dishes
@app.get("/dishes")
def get_dishes():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM dishes;")
                rows = cur.fetchall()
                return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
