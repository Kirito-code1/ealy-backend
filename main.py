from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import psycopg
from psycopg.rows import dict_row

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "ealy-backend-production.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    # Получаем DATABASE_URL или собираем из отдельных переменных
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Используем полный URL (Railway даёт его автоматически)
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
    return {
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
        "POSTGRES_PORT": os.getenv("POSTGRES_PORT"),
        "DATABASE_URL": os.getenv("DATABASE_URL")[:30] + "..." if os.getenv("DATABASE_URL") else None
    }


@app.get("/dishes")
def get_dishes():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM dishes;")
                return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))