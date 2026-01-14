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
        "https://eatly-website-frontend.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Добавляем SSL для Railway
        if "sslmode" not in database_url:
            if "?" in database_url:
                database_url += "&sslmode=require"
            else:
                database_url += "?sslmode=require"

        # ДЛЯ ОТЛАДКИ: меняем БД на EatlyServer если нужно
        if "/railway" in database_url:
            database_url = database_url.replace("/railway", "/EatlyServer")
            print(f"Changed DB to EatlyServer in URL")

        print(f"DB URL used: {database_url[:70]}...")
        return psycopg.connect(database_url, row_factory=dict_row)
    else:
        return psycopg.connect(
            dbname=os.getenv("POSTGRES_DB", "EatlyServer"),
            user=os.getenv("POSTGRES_USER", "shahzod"),
            password=os.getenv("POSTGRES_PASSWORD", "2008"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            row_factory=dict_row
        )


# ========== ЭНДПОИНТЫ ==========

@app.get("/")
def root():
    return {"message": "Eatly API is running"}


@app.get("/ping")
def ping():
    return {"message": "pong"}


@app.get("/env")
def check_env():
    db_url = os.getenv("DATABASE_URL")
    return {
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
        "POSTGRES_PORT": os.getenv("POSTGRES_PORT"),
        "DATABASE_URL": db_url[:50] + "..." if db_url and len(db_url) > 50 else db_url,
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "Not set")
    }


@app.get("/db-info")
def db_info():
    """ПОЛНАЯ ИНФОРМАЦИЯ О ПОДКЛЮЧЕНИИ К БД"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Инфо о подключении
                cur.execute("""
                    SELECT 
                        current_database() as db_name,
                        current_user as db_user,
                        inet_server_addr() as host,
                        inet_server_port() as port
                """)
                info = cur.fetchone()

                # 2. Список всех таблиц
                cur.execute("""
                            SELECT table_name
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                            ORDER BY table_name
                            """)
                tables_result = cur.fetchall()
                tables = [row["table_name"] for row in tables_result]

                # 3. Если есть dishes - количество записей
                dishes_count = 0
                if "dishes" in tables:
                    cur.execute("SELECT COUNT(*) as cnt FROM dishes")
                    dishes_count = cur.fetchone()["cnt"]

                return {
                    "connection": info,
                    "tables": tables,
                    "tables_count": len(tables),
                    "dishes_count": dishes_count,
                    "has_dishes_table": "dishes" in tables
                }
    except Exception as e:
        return {"error": str(e)}


@app.get("/test-db")
def test_db():
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


@app.post("/create-dishes-table")
def create_dishes_table():
    """Создать таблицу dishes если её нет"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Создаём таблицу
                cur.execute("""
                            CREATE TABLE IF NOT EXISTS dishes
                            (
                                id
                                SERIAL
                                PRIMARY
                                KEY,
                                name
                                VARCHAR
                            (
                                255
                            ) NOT NULL,
                                description TEXT,
                                price DECIMAL
                            (
                                10,
                                2
                            ) NOT NULL,
                                category VARCHAR
                            (
                                100
                            ),
                                image_url VARCHAR
                            (
                                500
                            ),
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """)

                # Добавляем тестовые данные если таблица пустая
                cur.execute("SELECT COUNT(*) as cnt FROM dishes")
                count = cur.fetchone()["cnt"]

                if count == 0:
                    cur.execute("""
                                INSERT INTO dishes (name, description, price, category)
                                VALUES ('Плов', 'Узбекский плов с бараниной', 120.00, 'Основные блюда'),
                                       ('Салат Цезарь', 'С курицей и соусом', 85.50, 'Салаты'),
                                       ('Пицца Маргарита', 'Классическая пицца', 150.00, 'Пицца')
                                """)

                conn.commit()

                cur.execute("SELECT COUNT(*) as new_count FROM dishes")
                new_count = cur.fetchone()["new_count"]

                return {
                    "success": True,
                    "message": "Table dishes created/updated",
                    "initial_count": count,
                    "current_count": new_count
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))