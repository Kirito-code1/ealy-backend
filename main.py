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
    """Подключение к PostgreSQL"""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Добавляем SSL для Railway
        if "sslmode" not in database_url:
            if "?" in database_url:
                database_url += "&sslmode=require"
            else:
                database_url += "?sslmode=require"

        print(f"Connecting to: {database_url[:60]}...")
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

                # Проверяем таблицу dishes
                has_dishes = "dishes" in tables
                dishes_count = 0
                dishes_columns = []

                if has_dishes:
                    cur.execute("SELECT COUNT(*) as cnt FROM dishes;")
                    dishes_count = cur.fetchone()["cnt"]

                    # Получаем информацию о колонках
                    cur.execute("""
                                SELECT column_name, data_type
                                FROM information_schema.columns
                                WHERE table_name = 'dishes'
                                ORDER BY ordinal_position;
                                """)
                    dishes_columns = cur.fetchall()

                return {
                    "connection": info,
                    "tables": tables,
                    "total_tables": len(tables),
                    "has_dishes_table": has_dishes,
                    "dishes_count": dishes_count,
                    "dishes_columns": dishes_columns
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


@app.post("/setup-dishes")
def setup_dishes():
    """Создать таблицу dishes с нужными колонками"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, есть ли уже таблица
                cur.execute("""
                            SELECT EXISTS (SELECT
                                           FROM information_schema.tables
                                           WHERE table_schema = 'public'
                                             AND table_name = 'dishes');
                            """)
                exists = cur.fetchone()["exists"]

                if not exists:
                    # Создаём таблицу с ВСЕМИ нужными колонками
                    cur.execute("""
                                CREATE TABLE dishes
                                (
                                    id            SERIAL PRIMARY KEY,
                                    name          VARCHAR(255)   NOT NULL,
                                    description   TEXT,
                                    price         DECIMAL(10, 2) NOT NULL,
                                    category      VARCHAR(100),
                                    delivery_time INTEGER,
                                    rating        DECIMAL(3, 1),
                                    image_url     VARCHAR(500),
                                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                                """)
                    conn.commit()
                    return {
                        "status": "created",
                        "message": "Table 'dishes' created with all columns",
                        "columns": ["id", "name", "description", "price", "category", "delivery_time", "rating",
                                    "image_url", "created_at"]
                    }
                else:
                    # Таблица уже есть, добавляем недостающие колонки
                    added_columns = []

                    # Проверяем и добавляем delivery_time
                    cur.execute("""
                                SELECT column_name
                                FROM information_schema.columns
                                WHERE table_name = 'dishes'
                                  AND column_name = 'delivery_time'
                                """)
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE dishes ADD COLUMN delivery_time INTEGER;")
                        added_columns.append("delivery_time")

                    # Проверяем и добавляем rating
                    cur.execute("""
                                SELECT column_name
                                FROM information_schema.columns
                                WHERE table_name = 'dishes'
                                  AND column_name = 'rating'
                                """)
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE dishes ADD COLUMN rating DECIMAL(3,1);")
                        added_columns.append("rating")

                    conn.commit()

                    if added_columns:
                        return {
                            "status": "updated",
                            "message": f"Added missing columns: {', '.join(added_columns)}",
                            "added_columns": added_columns
                        }
                    else:
                        return {
                            "status": "already_complete",
                            "message": "Table 'dishes' already has all required columns"
                        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add-sample-dishes")
def add_sample_dishes():
    """Добавить 10 примеров блюд"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Сначала убедимся, что таблица и колонки есть
                cur.execute("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name = 'dishes'
                            """)
                columns = [row["column_name"] for row in cur.fetchall()]

                if not columns:
                    raise HTTPException(status_code=400,
                                        detail="Table 'dishes' does not exist. Call /setup-dishes first.")

                # Очищаем старые данные (опционально)
                cur.execute("TRUNCATE dishes RESTART IDENTITY;")

                # Добавляем 10 популярных блюд
                dishes = [
                    ("Chicken Hell", "Grilled chicken with vegetables", 12.99, "Healthy", 24, 4.8),
                    ("Salmon Heaven", "Baked salmon with quinoa", 15.99, "Healthy", 28, 4.7),
                    ("Avocado Toast", "Whole grain toast with avocado", 8.99, "Healthy", 15, 4.5),
                    ("Cheese Burger", "Classic cheeseburger with fries", 8.99, "Fast Food", 18, 4.6),
                    ("Margarita Pizza", "Classic tomato and cheese", 11.99, "Pizza", 25, 4.7),
                    ("Chicken Teriyaki", "Teriyaki chicken with rice", 11.99, "Asian", 22, 4.7),
                    ("Chocolate Cake", "Rich chocolate cake", 6.99, "Dessert", 15, 4.8),
                    ("Burrito", "Chicken burrito", 10.99, "Mexican", 22, 4.7),
                    ("Pancakes", "3 pancakes with syrup", 7.99, "Breakfast", 15, 4.7),
                    ("Spaghetti Carbonara", "Pasta with bacon and eggs", 12.99, "Italian", 22, 4.7)
                ]

                for dish in dishes:
                    name, description, price, category, delivery_time, rating = dish
                    cur.execute("""
                                INSERT INTO dishes (name, description, price, category, delivery_time, rating)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """, (name, description, price, category, delivery_time, rating))

                conn.commit()

                # Проверяем результат
                cur.execute("SELECT COUNT(*) as count FROM dishes;")
                count = cur.fetchone()["count"]

                return {
                    "success": True,
                    "message": f"Added {count} sample dishes",
                    "dishes_count": count
                }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dishes")
def get_dishes():
    """Получить все блюда"""
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
        # Если таблицы нет
        if "does not exist" in str(e) or "dishes" in str(e).lower():
            return {
                "success": True,
                "count": 0,
                "dishes": [],
                "message": "Table 'dishes' does not exist. Call POST /setup-dishes to create it."
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
            "setup_dishes": "POST /setup-dishes",
            "add_sample_dishes": "POST /add-sample-dishes",
            "get_dishes": "/dishes"
        }
    }