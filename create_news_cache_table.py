"""Create news_cache table in PostgreSQL"""

import sys
sys.path.insert(0, 'dashboard')

from database import execute_query, get_cursor

# Create table SQL
create_table_sql = """
CREATE TABLE IF NOT EXISTS news_cache (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    source VARCHAR(100),
    published_at TIMESTAMP WITH TIME ZONE,
    sentiment VARCHAR(20),
    color VARCHAR(20),
    icon VARCHAR(10),
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(stock_code, url)
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_news_cache_stock_code ON news_cache(stock_code);
CREATE INDEX IF NOT EXISTS idx_news_cache_fetched_at ON news_cache(fetched_at);
CREATE INDEX IF NOT EXISTS idx_news_cache_published_at ON news_cache(published_at);
"""

# Create table to track last fetch time per stock
create_fetch_log_sql = """
CREATE TABLE IF NOT EXISTS news_fetch_log (
    stock_code VARCHAR(10) PRIMARY KEY,
    last_fetch TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    article_count INTEGER DEFAULT 0
);
"""

def create_tables():
    try:
        cursor = get_cursor()
        if cursor:
            cursor.execute(create_table_sql)
            cursor.execute(create_fetch_log_sql)
            cursor.connection.commit()
            cursor.close()
            print("✓ news_cache table created successfully")
            print("✓ news_fetch_log table created successfully")
            return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False

if __name__ == "__main__":
    create_tables()
