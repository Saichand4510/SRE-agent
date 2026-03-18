import psycopg2
import os


def get_connection():
    
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        username TEXT
    )
    """)

    conn.commit()
    conn.close()