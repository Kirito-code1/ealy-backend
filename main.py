from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # <-- добавляем CORS
from dotenv import load_dotenv
import os
import psycopg
from psycopg.rows import dict_row

# Загружаем переменные окружения
load_dotenv()

app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",                     # твой локальный фронтенд
        "https://eatly-website-frontend.up.railway.app"  # продакшн фронтенд
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Функция подключения к БД
def get_connection():
    return psycopg.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        row_factory=dict_row
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
