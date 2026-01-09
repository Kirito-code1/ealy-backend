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
        host="127.0.0.1",
        port=5432,
        database="EatlyServer",  # твоя база
        user="shahzod",          # твой пользователь
        password="2008",         # твой пароль
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
