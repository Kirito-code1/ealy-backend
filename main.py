from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import psycopg
from psycopg.rows import dict_row

load_dotenv()

app = FastAPI()

# 🔴 ОШИБКА: В allow_origins должен быть URL фронтенда, а не бэкенда!
# 🟢 ИСПРАВЛЕНО:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Локальный фронтенд
        "https://eatly-website-frontend.up.railway.app"  # Продакшен фронтенд
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # 🔴 ПРОБЛЕМА: Нет SSL параметра для Railway
        # 🟢 ИСПРАВЛЕНО: Добавляем sslmode=require
        if "sslmode" not in database_url:
            if "?" in database_url:
                database_url += "&sslmode=require"
            else:
                database_url += "?sslmode=require"

        # Для отладки (увидишь в логах Railway)
        print(f"Connecting to DB with URL: {database_url[:50]}...")

        return psycopg.connect(database_url, row_factory=dict_row)
    else:
        # Для локальной разработки
        return psycopg.connect(
            dbname=os.getenv("POSTGRES_DB", "EatlyServer"),
            user=os.getenv("POSTGRES_USER", "shahzod"),
            password=os.getenv("POSTGRES_PASSWORD", "2008"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            row_factory=dict_row
        )


@app.get("/ping")
def ping():
    return {"message": "pong"}


@app.get("/env")
def check_env():
    """Проверка переменных окружения (без пароля)"""
    db_url = os.getenv("DATABASE_URL")
    return {
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
        "POSTGRES_PORT": os.getenv("POSTGRES_PORT"),
        "DATABASE_URL": db_url[:30] + "..." if db_url and len(db_url) > 30 else db_url,
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "Not set")
    }


@app.get("/test-db")
def test_db():
    """Тест подключения к БД"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user;")
                result = cur.fetchone()
                return {
                    "status": "connected",
                    "database": result["current_database"],
                    "user": result["current_user"]
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dishes")
def get_dishes():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM dishes;")
                dishes = cur.fetchall()
                return {
                    "count": len(dishes),
                    "dishes": dishes
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))