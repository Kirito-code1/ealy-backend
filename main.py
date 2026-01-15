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
    allow_origins=["*"],
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


@app.post("/add-100-dishes")
def add_100_dishes():
    """Добавить 100 разнообразных блюд"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Очищаем старые данные
                cur.execute("TRUNCATE dishes RESTART IDENTITY;")

                # 100 блюд: (name, description, price, category, delivery_time, rating)
                dishes_100 = [
                    # Healthy (20 блюд)
                    ("Chicken Hell", "Grilled chicken with vegetables", 12.99, "Healthy", 24, 4.8),
                    ("Salmon Heaven", "Baked salmon with quinoa", 15.99, "Healthy", 28, 4.7),
                    ("Avocado Toast", "Whole grain toast with avocado", 8.99, "Healthy", 15, 4.5),
                    ("Quinoa Bowl", "Quinoa with roasted vegetables", 10.99, "Healthy", 20, 4.6),
                    ("Greek Salad", "Fresh Greek salad with feta", 9.99, "Healthy", 18, 4.4),
                    ("Protein Power", "Chicken breast with sweet potato", 13.49, "Healthy", 25, 4.7),
                    ("Green Smoothie", "Spinach and fruit smoothie", 6.99, "Healthy", 10, 4.3),
                    ("Tuna Poke", "Fresh tuna poke bowl", 14.99, "Healthy", 22, 4.8),
                    ("Veggie Wrap", "Vegetable wrap with hummus", 8.49, "Healthy", 16, 4.4),
                    ("Berry Bowl", "Mixed berries with yogurt", 7.99, "Healthy", 12, 4.5),
                    ("Kale Salad", "Kale salad with almonds", 8.99, "Healthy", 17, 4.3),
                    ("Egg White Omelette", "Egg white omelette with veggies", 9.49, "Healthy", 14, 4.6),
                    ("Brown Rice Bowl", "Brown rice with vegetables", 8.99, "Healthy", 19, 4.4),
                    ("Turkey Sandwich", "Turkey sandwich on whole wheat", 10.49, "Healthy", 16, 4.5),
                    ("Lentil Soup", "Hearty lentil soup", 7.99, "Healthy", 22, 4.6),
                    ("Zucchini Noodles", "Zucchini noodles with pesto", 11.99, "Healthy", 18, 4.7),
                    ("Sweet Potato Fries", "Baked sweet potato fries", 5.99, "Healthy", 15, 4.5),
                    ("Chia Pudding", "Chia seed pudding", 6.49, "Healthy", 12, 4.4),
                    ("Fruit Plate", "Seasonal fruit plate", 8.99, "Healthy", 10, 4.6),
                    ("Hummus Plate", "Hummus with pita bread", 7.49, "Healthy", 14, 4.5),

                    # Fast Food (20 блюд)
                    ("Cheese Burger", "Classic cheeseburger with fries", 8.99, "Fast Food", 18, 4.6),
                    ("Crispy Chicken", "Crispy chicken burger", 9.49, "Fast Food", 20, 4.7),
                    ("BBQ Bacon Burger", "Burger with bacon and BBQ", 10.99, "Fast Food", 22, 4.8),
                    ("French Fries", "Golden crispy fries", 3.99, "Fast Food", 12, 4.5),
                    ("Onion Rings", "Crispy onion rings", 4.49, "Fast Food", 14, 4.4),
                    ("Chicken Nuggets", "10 pieces with sauce", 6.99, "Fast Food", 16, 4.5),
                    ("Hot Dog", "Classic hot dog", 5.99, "Fast Food", 15, 4.3),
                    ("Double Burger", "Double meat burger", 12.49, "Fast Food", 25, 4.8),
                    ("Chicken Wings", "Spicy chicken wings", 11.99, "Fast Food", 24, 4.7),
                    ("Mozzarella Sticks", "Fried mozzarella sticks", 5.49, "Fast Food", 16, 4.4),
                    ("Fish & Chips", "Fried fish with chips", 13.99, "Fast Food", 28, 4.6),
                    ("Chili Cheese Fries", "Fries with chili and cheese", 8.99, "Fast Food", 19, 4.5),
                    ("Bacon Cheeseburger", "Burger with extra bacon", 11.49, "Fast Food", 23, 4.7),
                    ("Fried Chicken", "Crispy fried chicken", 10.99, "Fast Food", 26, 4.6),
                    ("Corn Dog", "Fried corn dog", 4.99, "Fast Food", 13, 4.2),
                    ("Tater Tots", "Crispy tater tots", 4.49, "Fast Food", 14, 4.3),
                    ("Loaded Nachos", "Nachos with all toppings", 9.99, "Fast Food", 21, 4.7),
                    ("Philly Cheesesteak", "Philly cheesesteak sandwich", 12.99, "Fast Food", 24, 4.8),
                    ("Breakfast Burrito", "Morning burrito", 7.99, "Fast Food", 17, 4.5),
                    ("Buffalo Wrap", "Buffalo chicken wrap", 9.49, "Fast Food", 19, 4.6),

                    # Pizza (15 блюд)
                    ("Margarita Pizza", "Classic tomato and cheese", 11.99, "Pizza", 25, 4.7),
                    ("Pepperoni Pizza", "Pepperoni and cheese", 13.99, "Pizza", 26, 4.8),
                    ("BBQ Chicken Pizza", "Chicken with BBQ sauce", 14.99, "Pizza", 28, 4.7),
                    ("Veggie Pizza", "Vegetarian pizza", 12.49, "Pizza", 24, 4.6),
                    ("Hawaiian Pizza", "Ham and pineapple", 13.49, "Pizza", 27, 4.5),
                    ("Meat Lovers", "Pizza with 4 meats", 16.99, "Pizza", 30, 4.8),
                    ("Four Cheese", "4 cheese blend", 12.99, "Pizza", 25, 4.7),
                    ("Mushroom Pizza", "Pizza with mushrooms", 11.49, "Pizza", 23, 4.5),
                    ("Seafood Pizza", "Pizza with shrimp", 15.99, "Pizza", 29, 4.7),
                    ("Buffalo Pizza", "Pizza with buffalo sauce", 13.99, "Pizza", 26, 4.6),
                    ("White Pizza", "Pizza without tomato sauce", 12.99, "Pizza", 25, 4.5),
                    ("Sausage Pizza", "Pizza with Italian sausage", 13.49, "Pizza", 27, 4.7),
                    ("Spinach Pizza", "Pizza with spinach", 11.99, "Pizza", 24, 4.6),
                    ("Bacon Pizza", "Pizza with bacon", 14.49, "Pizza", 28, 4.8),
                    ("Truffle Pizza", "Pizza with truffle oil", 17.99, "Pizza", 32, 4.9),

                    # Asian (15 блюд)
                    ("Chicken Teriyaki", "Teriyaki chicken with rice", 11.99, "Asian", 22, 4.7),
                    ("Sushi Roll", "California roll (8 pcs)", 9.99, "Asian", 20, 4.6),
                    ("Pad Thai", "Thai noodles with shrimp", 12.99, "Asian", 25, 4.8),
                    ("Ramen", "Japanese ramen soup", 10.99, "Asian", 24, 4.7),
                    ("Spring Rolls", "Vegetable spring rolls (4 pcs)", 6.99, "Asian", 18, 4.5),
                    ("Kung Pao Chicken", "Spicy chicken with peanuts", 13.49, "Asian", 26, 4.7),
                    ("Fried Rice", "Chicken fried rice", 9.49, "Asian", 20, 4.6),
                    ("Dumplings", "Steamed dumplings (6 pcs)", 7.99, "Asian", 19, 4.5),
                    ("Beef Curry", "Beef curry with rice", 12.49, "Asian", 23, 4.6),
                    ("Sashimi", "Fresh salmon sashimi", 14.99, "Asian", 21, 4.8),
                    ("Orange Chicken", "Sweet orange chicken", 11.99, "Asian", 24, 4.6),
                    ("Pho", "Vietnamese noodle soup", 10.99, "Asian", 26, 4.7),
                    ("Tempura", "Mixed tempura", 9.99, "Asian", 22, 4.5),
                    ("Bibimbap", "Korean rice bowl", 12.99, "Asian", 25, 4.7),
                    ("Miso Soup", "Traditional miso soup", 3.99, "Asian", 15, 4.4),

                    # Italian (10 блюд)
                    ("Spaghetti Carbonara", "Pasta with bacon and eggs", 12.99, "Italian", 22, 4.7),
                    ("Fettuccine Alfredo", "Creamy fettuccine pasta", 11.99, "Italian", 21, 4.6),
                    ("Lasagna", "Meat lasagna", 13.99, "Italian", 30, 4.8),
                    ("Risotto", "Mushroom risotto", 11.49, "Italian", 25, 4.5),
                    ("Bruschetta", "Tomato bruschetta", 7.99, "Italian", 15, 4.4),
                    ("Chicken Parmesan", "Breaded chicken with cheese", 14.99, "Italian", 28, 4.7),
                    ("Minestrone", "Vegetable soup", 8.99, "Italian", 20, 4.3),
                    ("Caprese Salad", "Tomato and mozzarella", 9.49, "Italian", 16, 4.5),
                    ("Garlic Bread", "Toasted garlic bread", 4.99, "Italian", 12, 4.4),
                    ("Tiramisu", "Coffee dessert", 6.99, "Italian", 18, 4.8),

                    # Desserts (10 блюд)
                    ("Chocolate Cake", "Rich chocolate cake", 6.99, "Dessert", 15, 4.8),
                    ("Cheesecake", "New York cheesecake", 7.49, "Dessert", 16, 4.7),
                    ("Ice Cream", "3 scoops of ice cream", 5.99, "Dessert", 12, 4.5),
                    ("Brownie", "Chocolate brownie", 4.99, "Dessert", 10, 4.6),
                    ("Apple Pie", "Homemade apple pie", 6.49, "Dessert", 18, 4.5),
                    ("Chocolate Chip Cookies", "Fresh baked cookies (4pcs)", 3.99, "Dessert", 12, 4.7),
                    ("Mousse", "Chocolate mousse", 5.49, "Dessert", 14, 4.6),
                    ("Cupcake", "Vanilla cupcake", 3.49, "Dessert", 10, 4.4),
                    ("Donut", "Glazed donut", 2.99, "Dessert", 8, 4.5),
                    ("Panna Cotta", "Italian cream dessert", 5.99, "Dessert", 16, 4.7),

                    # Mexican (10 блюд)
                    ("Burrito", "Chicken burrito", 10.99, "Mexican", 22, 4.7),
                    ("Tacos", "3 beef tacos", 9.99, "Mexican", 20, 4.6),
                    ("Quesadilla", "Cheese quesadilla", 8.99, "Mexican", 18, 4.5),
                    ("Nachos", "Nachos with cheese", 7.99, "Mexican", 16, 4.4),
                    ("Guacamole", "Fresh guacamole", 5.99, "Mexican", 14, 4.5),
                    ("Enchiladas", "Chicken enchiladas", 11.49, "Mexican", 24, 4.6),
                    ("Fajitas", "Beef fajitas", 13.99, "Mexican", 26, 4.7),
                    ("Churros", "Sweet churros", 4.99, "Mexican", 15, 4.8),
                    ("Mexican Rice", "Spanish rice", 3.99, "Mexican", 12, 4.3),
                    ("Salsa & Chips", "Chips with salsa", 4.49, "Mexican", 10, 4.4),
                ]

                # Добавляем все 100 блюд
                for dish in dishes_100:
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
                    "message": f"Added {count} dishes to database",
                    "dishes_count": count,
                    "categories": {
                        "Healthy": 20,
                        "Fast Food": 20,
                        "Pizza": 15,
                        "Asian": 15,
                        "Italian": 10,
                        "Dessert": 10,
                        "Mexican": 10
                    }
                }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dishes")
def get_dishes():
    """Получить все блюда. Если таблица пустая - создаём автоматически."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, есть ли таблица и данные
                cur.execute("""
                            SELECT EXISTS (SELECT
                                           FROM information_schema.tables
                                           WHERE table_schema = 'public'
                                             AND table_name = 'dishes');
                            """)
                table_exists = cur.fetchone()["exists"]

                if not table_exists:
                    # Таблицы нет - создаём её
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

                # Проверяем, есть ли данные
                cur.execute("SELECT COUNT(*) as cnt FROM dishes;")
                count = cur.fetchone()["cnt"]

                if count == 0:
                    # Данных нет - добавляем 20 популярных блюд автоматически
                    dishes_data = [
                        ("Chicken Hell", "Grilled chicken with vegetables", 12.99, "Healthy", 24, 4.8),
                        ("Salmon Heaven", "Baked salmon with quinoa", 15.99, "Healthy", 28, 4.7),
                        ("Avocado Toast", "Whole grain toast with avocado", 8.99, "Healthy", 15, 4.5),
                        ("Cheese Burger", "Classic cheeseburger with fries", 8.99, "Fast Food", 18, 4.6),
                        ("Margarita Pizza", "Classic tomato and cheese", 11.99, "Pizza", 25, 4.7),
                        ("Chicken Teriyaki", "Teriyaki chicken with rice", 11.99, "Asian", 22, 4.7),
                        ("Chocolate Cake", "Rich chocolate cake", 6.99, "Dessert", 15, 4.8),
                        ("Burrito", "Chicken burrito", 10.99, "Mexican", 22, 4.7),
                        ("Pancakes", "3 pancakes with syrup", 7.99, "Breakfast", 15, 4.7),
                        ("Spaghetti Carbonara", "Pasta with bacon and eggs", 12.99, "Italian", 22, 4.7),
                        ("Greek Salad", "Fresh Greek salad with feta", 9.99, "Healthy", 18, 4.4),
                        ("French Fries", "Golden crispy fries", 3.99, "Fast Food", 12, 4.5),
                        ("Sushi Roll", "California roll (8 pcs)", 9.99, "Asian", 20, 4.6),
                        ("Lasagna", "Meat lasagna", 13.99, "Italian", 30, 4.8),
                        ("Ice Cream", "3 scoops of ice cream", 5.99, "Dessert", 12, 4.5),
                        ("Tacos", "3 beef tacos", 9.99, "Mexican", 20, 4.6),
                        ("Ramen", "Japanese ramen soup", 10.99, "Asian", 24, 4.7),
                        ("BBQ Bacon Burger", "Burger with bacon and BBQ", 10.99, "Fast Food", 22, 4.8),
                        ("Tiramisu", "Coffee dessert", 6.99, "Italian", 18, 4.8),
                        ("Spring Rolls", "Vegetable spring rolls (4 pcs)", 6.99, "Asian", 18, 4.5),
                    ]

                    for dish in dishes_data:
                        name, description, price, category, delivery_time, rating = dish
                        cur.execute("""
                                    INSERT INTO dishes (name, description, price, category, delivery_time, rating)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    """, (name, description, price, category, delivery_time, rating))

                    conn.commit()
                    print(f"✅ Automatically created table and added {len(dishes_data)} dishes")

                # Теперь получаем все блюда
                cur.execute("SELECT * FROM dishes ORDER BY id;")
                dishes = cur.fetchall()

                return {
                    "success": True,
                    "count": len(dishes),
                    "dishes": dishes,
                    "auto_created": count == 0  # Показывает, были ли данные созданы автоматически
                }
    except Exception as e:
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
            "add_100_dishes": "POST /add-100-dishes",
            "get_dishes": "/dishes"
        }
    }