from main import get_connection, app


@app.get("/test-db")
def test_db():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, version();")
                result = cur.fetchone()
                return {
                    "status": "connected",
                    "database": result["current_database"],
                    "user": result["current_user"],
                    "postgres_version": result["version"].split()[0]
                }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e)
        }