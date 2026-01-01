"""
Database connection and utilities for Stock Analysis
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Database configuration - supports Railway DATABASE_URL or local config
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Railway/Production: use DATABASE_URL
    DB_CONFIG = {'dsn': DATABASE_URL}
else:
    # Local development
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'database': os.environ.get('DB_NAME', 'stock_analysis'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD', 'postgres'),
        'port': int(os.environ.get('DB_PORT', 5432))
    }

@contextmanager
def get_connection():
    """Context manager untuk database connection"""
    conn = None
    try:
        if 'dsn' in DB_CONFIG:
            conn = psycopg2.connect(DB_CONFIG['dsn'])
        else:
            conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    finally:
        if conn:
            conn.close()

@contextmanager
def get_cursor(commit=True):
    """Context manager untuk database cursor"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

def execute_query(query, params=None, fetch=True):
    """Execute query dan return hasil"""
    with get_cursor() as cursor:
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        return None

def execute_many(query, params_list):
    """Execute many untuk batch insert"""
    with get_cursor() as cursor:
        cursor.executemany(query, params_list)

def test_connection():
    """Test database connection"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT version();")
            result = cursor.fetchone()
            print(f"Connected to: {result['version']}")
            return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
