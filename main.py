from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import psycopg
from psycopg.rows import dict_row

# Загружаем локальные переменные окружения (для локальной разработки)
load_dotenv()

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # локальный фронтенд
        "https://eatly-website-frontend.up.railway.app"  # продакшн фронтенд
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_connection():
    """
    Подключение к PostgreSQL.
    Использует DATABASE_URL на Railway или локальные переменные для разработки.
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Добавляем SSL для Railway
        if "sslmode" not in database_url:
            if "?" in database_url:
                database_url += "&sslmode=require"
            else:
                database_url += "?sslmode=require"

        return psycopg.connect(database_url, row_factory=dict_row)
    else:
        # Локальная разработка
        return psycopg.connect(
            dbname=os.getenv("POSTGRES_DB", "EatlyServer"),
            user=os.getenv("POSTGRES_USER", "shahzod"),
            password=os.getenv("POSTGRES_PASSWORD", "2008"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            row_factory=dict_row
        )

@app.get("/")
def root():
    return {"message": "Eatly API", "status": "running"}

@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.get("/env")
def check_env():
    """Проверка переменных окружения"""
    db_url = os.getenv("DATABASE_URL")
    return {
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
        "POSTGRES_PORT": os.getenv("POSTGRES_PORT"),
        "DATABASE_URL": db_url[:60] + "..." if db_url and len(db_url) > 60 else db_url,
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "not set")
    }

@app.get("/db-info")
def db_info():
    """Информация о подключенной базе данных"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Информация о подключении
                cur.execute("SELECT current_database() as db_name, current_user as db_user;")
                info = cur.fetchone()

                # Список таблиц
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = [row["table_name"] for row in cur.fetchall()]

                return {
                    "connection": info,
                    "tables": tables,
                    "total_tables": len(tables)
                }
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-connection")
def test_connection():
    """Простая проверка подключения к БД"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 as test_value;")
                result = cur.fetchone()
                return {
                    "status": "success",
                    "database_connected": True,
                    "test_value": result["test_value"]
                }
    except Exception as e:
        return {
            "status": "error",
            "database_connected": False,
            "error": str(e)
        }

@app.get("/dishes")
def get_dishes():
    """Получить все блюда из базы (только существующие)"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM dishes ORDER BY id;")
                dishes = cur.fetchall()
                return {
                    "success": True,
                    "count": len(dishes),
                    "dishes": dishes
                }
    except Exception as e:
        # Если таблицы нет, возвращаем пустой массив
        if "does not exist" in str(e) or "dishes" in str(e).lower():
            return {
                "success": True,
                "count": 0,
                "dishes": [],
                "message": "Table 'dishes' does not exist. Add dishes to your database manually."
            }
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    """Проверка здоровья API"""
    return {
        "status": "healthy",
        "service": "Eatly Backend API",
        "endpoints": {
            "root": "/",
            "ping": "/ping",
            "env": "/env",
            "db_info": "/db-info",
            "test": "/test-connection",
            "get_dishes": "/dishes"
        }
    }
