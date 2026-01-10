import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# Разрешаем React делать запросы
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # для разработки можно *
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", 5432),
        database=os.getenv("PGDATABASE", "EatlyServer"),
        user=os.getenv("PGUSER", "shahzod"),
        password=os.getenv("PGPASSWORD", "2008"),
        cursor_factory=RealDictCursor
    )

# Эндпоинт для получения всех блюд
@app.get("/dishes")
def get_dishes():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, delivery_time FROM dishes ORDER BY id;")
    dishes = cur.fetchall()
    cur.close()
    conn.close()
    return dishes
