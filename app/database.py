"""
Database connection and utilities for Stock Analysis
Optimized with connection pooling and query caching
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from contextlib import contextmanager
from functools import wraps
import hashlib
import time
import threading

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

# ============================================================
# CONNECTION POOLING
# ============================================================

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()

def get_pool():
    """Get or create connection pool (thread-safe)"""
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                try:
                    if 'dsn' in DB_CONFIG:
                        _connection_pool = pool.ThreadedConnectionPool(
                            minconn=2,
                            maxconn=20,
                            dsn=DB_CONFIG['dsn']
                        )
                    else:
                        _connection_pool = pool.ThreadedConnectionPool(
                            minconn=2,
                            maxconn=20,
                            **DB_CONFIG
                        )
                    print("Connection pool created successfully")
                except Exception as e:
                    print(f"Failed to create connection pool: {e}")
                    _connection_pool = None
    return _connection_pool

@contextmanager
def get_connection():
    """Context manager untuk database connection from pool"""
    conn = None
    pool_instance = get_pool()
    try:
        if pool_instance:
            conn = pool_instance.getconn()
        else:
            # Fallback to direct connection if pool fails
            if 'dsn' in DB_CONFIG:
                conn = psycopg2.connect(DB_CONFIG['dsn'])
            else:
                conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    finally:
        if conn:
            if pool_instance:
                pool_instance.putconn(conn)
            else:
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

# ============================================================
# QUERY CACHING (untuk data update harian)
# ============================================================

class QueryCache:
    """
    Simple in-memory cache for database queries.
    Perfect for daily-updated data - cache expires after 1 hour.
    """
    def __init__(self, default_ttl=3600):  # 1 hour default
        self._cache = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0

    def _make_key(self, query, params):
        """Generate cache key from query and params"""
        key_str = f"{query}:{str(params)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query, params=None):
        """Get cached result if valid"""
        key = self._make_key(query, params)
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() < entry['expires']:
                    self.hits += 1
                    return entry['data']
                else:
                    # Expired, remove it
                    del self._cache[key]
            self.misses += 1
            return None

    def set(self, query, params, data, ttl=None):
        """Cache query result"""
        key = self._make_key(query, params)
        ttl = ttl or self.default_ttl
        with self._lock:
            self._cache[key] = {
                'data': data,
                'expires': time.time() + ttl,
                'created': time.time()
            }

    def clear(self):
        """Clear all cache"""
        with self._lock:
            self._cache.clear()
            print("Query cache cleared")

    def clear_pattern(self, pattern):
        """Clear cache entries containing pattern in query"""
        with self._lock:
            keys_to_delete = []
            for key in self._cache:
                if pattern in str(self._cache[key].get('query', '')):
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                del self._cache[key]

    def stats(self):
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'entries': len(self._cache)
        }

# Global cache instance
query_cache = QueryCache(default_ttl=3600)  # 1 hour cache

# ============================================================
# CACHED QUERY EXECUTION
# ============================================================

def execute_query(query, params=None, fetch=True, use_cache=True, cache_ttl=None):
    """
    Execute query dengan optional caching.

    Args:
        query: SQL query string
        params: Query parameters
        fetch: Whether to fetch results
        use_cache: Enable/disable caching (default: True)
        cache_ttl: Custom TTL in seconds (default: 1 hour)
    """
    # Check cache first (only for SELECT queries)
    if use_cache and fetch and query.strip().upper().startswith('SELECT'):
        cached = query_cache.get(query, params)
        if cached is not None:
            return cached

    # Execute query
    with get_cursor() as cursor:
        cursor.execute(query, params)
        if fetch:
            result = cursor.fetchall()
            # Cache the result
            if use_cache and query.strip().upper().startswith('SELECT'):
                query_cache.set(query, params, result, cache_ttl)
            return result
        return None

def execute_query_no_cache(query, params=None, fetch=True):
    """Execute query without caching - for real-time needs"""
    return execute_query(query, params, fetch, use_cache=False)

def execute_many(query, params_list):
    """Execute many untuk batch insert"""
    with get_cursor() as cursor:
        cursor.executemany(query, params_list)

# ============================================================
# CACHE MANAGEMENT
# ============================================================

def clear_cache():
    """Clear all query cache - call after data update"""
    query_cache.clear()

def clear_stock_cache(stock_code):
    """Clear cache for specific stock"""
    query_cache.clear_pattern(stock_code)

def get_cache_stats():
    """Get cache statistics for monitoring"""
    return query_cache.stats()

def refresh_cache_for_stock(stock_code):
    """
    Refresh cache for a specific stock after data import.
    Call this after importing new data for a stock.
    """
    clear_stock_cache(stock_code)
    print(f"Cache cleared for stock: {stock_code}")

# ============================================================
# PRELOAD COMMON QUERIES
# ============================================================

def preload_stock_data(stock_code):
    """
    Preload common queries for a stock into cache.
    Call this to warm up cache for frequently accessed stocks.
    """
    try:
        # Preload stock list
        execute_query("SELECT DISTINCT stock_code FROM stock_daily ORDER BY stock_code")

        # Preload stock daily data
        execute_query("""
            SELECT * FROM stock_daily
            WHERE stock_code = %s
            ORDER BY date DESC LIMIT 365
        """, (stock_code,))

        # Preload broker summary
        execute_query("""
            SELECT * FROM broker_summary
            WHERE stock_code = %s
            ORDER BY date DESC
        """, (stock_code,))

        print(f"Cache preloaded for stock: {stock_code}")
    except Exception as e:
        print(f"Failed to preload cache: {e}")

# ============================================================
# CONNECTION MANAGEMENT
# ============================================================

def test_connection():
    """Test database connection"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT version();")
            result = cursor.fetchone()
            print(f"Connected to: {result['version']}")
            print(f"Cache stats: {get_cache_stats()}")
            return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

def close_pool():
    """Close connection pool - call on app shutdown"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        print("Connection pool closed")

if __name__ == "__main__":
    test_connection()
