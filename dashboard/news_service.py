"""
News Service - GNews API dengan Persistent Cache (Database)
Jam kerja (08-16): 2 jam | Luar jam: 5 jam | Weekend: 6 jam
Cache disimpan di PostgreSQL agar tidak hilang saat restart
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import threading

from dotenv import load_dotenv
load_dotenv()

GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"

DB_LOCK = threading.Lock()

STOCK_KEYWORDS = {
    'BBCA': ['BBCA', 'Bank Central Asia'],
    'BMRI': ['BMRI', 'Bank Mandiri'],
    'BBRI': ['BBRI', 'Bank BRI'],
    'BBNI': ['BBNI', 'Bank BNI'],
    'TLKM': ['TLKM', 'Telkom'],
    'ASII': ['ASII', 'Astra'],
    'UNVR': ['UNVR', 'Unilever Indonesia'],
    'HMSP': ['HMSP', 'Sampoerna'],
    'GGRM': ['GGRM', 'Gudang Garam'],
    'ICBP': ['ICBP', 'Indofood CBP'],
    'INDF': ['INDF', 'Indofood'],
    'KLBF': ['KLBF', 'Kalbe Farma'],
    'PGAS': ['PGAS', 'PGN'],
    'PTBA': ['PTBA', 'Bukit Asam'],
    'ADRO': ['ADRO', 'Adaro'],
    'ANTM': ['ANTM', 'Antam'],
    'INCO': ['INCO', 'Vale Indonesia'],
    'CPIN': ['CPIN', 'Charoen Pokphand'],
    'EXCL': ['EXCL', 'XL Axiata'],
    'ISAT': ['ISAT', 'Indosat'],
    'SMGR': ['SMGR', 'Semen Indonesia'],
    'INTP': ['INTP', 'Indocement'],
    'UNTR': ['UNTR', 'United Tractors'],
    'JSMR': ['JSMR', 'Jasa Marga'],
    'WIKA': ['WIKA', 'Wijaya Karya'],
    'PANI': ['Pantai Indah Kapuk', 'PANI'],
    'BREN': ['Barito Renewables', 'BREN'],
    'CUAN': ['Petrindo Jaya', 'CUAN'],
    'DSSA': ['Dian Swastatika', 'DSSA'],
    'AMMN': ['Amman Mineral', 'AMMN'],
    'CDIA': ['Cisarua Mountain Dairy', 'CDIA'],
    'PTRO': ['Petrosea', 'PTRO'],
}


def get_db_cursor():
    try:
        from database import get_cursor
        return get_cursor()
    except Exception as e:
        print(f"[DB ERROR] Cannot connect: {e}")
        return None


TABLES_CREATED = False

def ensure_tables_exist():
    global TABLES_CREATED
    if TABLES_CREATED:
        return True
    cursor = get_db_cursor()
    if not cursor:
        return False
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_cache (
                id SERIAL PRIMARY KEY, stock_code VARCHAR(10) NOT NULL,
                title TEXT NOT NULL, description TEXT, url TEXT NOT NULL,
                source VARCHAR(100), published_at TIMESTAMP WITH TIME ZONE,
                sentiment VARCHAR(20), color VARCHAR(20), icon VARCHAR(10),
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(stock_code, url)
            );
            CREATE INDEX IF NOT EXISTS idx_news_cache_stock ON news_cache(stock_code);
            CREATE TABLE IF NOT EXISTS news_fetch_log (
                stock_code VARCHAR(10) PRIMARY KEY,
                last_fetch TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                article_count INTEGER DEFAULT 0
            );
        """)
        cursor.connection.commit()
        cursor.close()
        TABLES_CREATED = True
        print("[DB] News cache tables ready")
        return True
    except Exception as e:
        print(f"[DB ERROR] ensure_tables_exist: {e}")
        return False


def get_refresh_interval_hours():
    now = datetime.now()
    if now.weekday() >= 5:
        return 6.0
    if 8 <= now.hour < 16:
        return 2.0
    return 5.0


def get_refresh_mode_text():
    now = datetime.now()
    if now.weekday() >= 5:
        return "Weekend (per 6 jam)"
    elif 8 <= now.hour < 16:
        return "Jam Kerja (per 2 jam)"
    return "Luar Jam Kerja (per 5 jam)"


def is_cache_valid_db(stock_code):
    ensure_tables_exist()
    cursor = get_db_cursor()
    if not cursor:
        return False
    try:
        cursor.execute("SELECT last_fetch FROM news_fetch_log WHERE stock_code = %s", (stock_code.upper(),))
        result = cursor.fetchone()
        cursor.close()
        if not result:
            return False
        last_fetch = result[0] if isinstance(result, tuple) else result.get('last_fetch')
        if not last_fetch:
            return False
        if last_fetch.tzinfo:
            last_fetch = last_fetch.replace(tzinfo=None)
        age = datetime.now() - last_fetch
        return age.total_seconds() < (get_refresh_interval_hours() * 3600)
    except Exception as e:
        print(f"[DB ERROR] is_cache_valid_db: {e}")
        return False


def get_cache_age_text(stock_code):
    cursor = get_db_cursor()
    if not cursor:
        return "DB tidak tersedia"
    try:
        cursor.execute("SELECT last_fetch FROM news_fetch_log WHERE stock_code = %s", (stock_code.upper(),))
        result = cursor.fetchone()
        cursor.close()
        if not result:
            return "Belum ada data"
        last_fetch = result[0] if isinstance(result, tuple) else result.get('last_fetch')
        if not last_fetch:
            return "Belum ada data"
        if last_fetch.tzinfo:
            last_fetch = last_fetch.replace(tzinfo=None)
        age = datetime.now() - last_fetch
        minutes = int(age.total_seconds() / 60)
        if minutes < 1:
            return "Baru saja"
        elif minutes < 60:
            return f"{minutes} menit lalu"
        return f"{minutes // 60} jam lalu"
    except:
        return "Error"


def load_from_database(stock_code):
    cursor = get_db_cursor()
    if not cursor:
        return []
    try:
        cursor.execute("""
            SELECT title, description, url, source, published_at, sentiment, color, icon
            FROM news_cache WHERE stock_code = %s ORDER BY published_at DESC LIMIT 15
        """, (stock_code.upper(),))
        rows = cursor.fetchall()
        cursor.close()
        articles = []
        for row in rows:
            if isinstance(row, dict):
                article = dict(row)
            else:
                article = {
                    'title': row[0], 'description': row[1], 'url': row[2], 'source': row[3],
                    'published_at': row[4].isoformat() if row[4] else '',
                    'sentiment': row[5], 'color': row[6], 'icon': row[7]
                }
            article['stock_code'] = stock_code.upper()
            article['published_formatted'] = format_time_ago_str(article.get('published_at', ''))
            articles.append(article)
        return articles
    except Exception as e:
        print(f"[DB ERROR] load_from_database: {e}")
        return []


def save_to_database(stock_code, articles):
    if not articles:
        return
    cursor = get_db_cursor()
    if not cursor:
        return
    try:
        with DB_LOCK:
            cursor.execute("DELETE FROM news_cache WHERE stock_code = %s AND published_at < NOW() - INTERVAL '14 days'", (stock_code.upper(),))
            for article in articles:
                published_at = None
                if article.get('published_at'):
                    try:
                        published_at = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
                    except:
                        pass
                cursor.execute("""
                    INSERT INTO news_cache (stock_code, title, description, url, source, published_at, sentiment, color, icon)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stock_code, url) DO UPDATE SET
                        title = EXCLUDED.title, description = EXCLUDED.description,
                        sentiment = EXCLUDED.sentiment, color = EXCLUDED.color, icon = EXCLUDED.icon, fetched_at = NOW()
                """, (stock_code.upper(), article.get('title', ''), article.get('description', ''),
                      article.get('url', ''), article.get('source', ''), published_at,
                      article.get('sentiment', 'NETRAL'), article.get('color', 'secondary'), article.get('icon', '[~]')))
            cursor.execute("""
                INSERT INTO news_fetch_log (stock_code, last_fetch, article_count) VALUES (%s, NOW(), %s)
                ON CONFLICT (stock_code) DO UPDATE SET last_fetch = NOW(), article_count = EXCLUDED.article_count
            """, (stock_code.upper(), len(articles)))
            cursor.connection.commit()
            cursor.close()
            print(f"[DB SAVED] {stock_code}: {len(articles)} articles")
    except Exception as e:
        print(f"[DB ERROR] save_to_database: {e}")


def get_stock_keywords(stock_code):
    keywords = STOCK_KEYWORDS.get(stock_code.upper(), [stock_code, f"{stock_code} saham"])
    return ' OR '.join([f'"{kw}"' for kw in keywords[:2]])


def fetch_news_gnews(stock_code, max_results=15):
    if not GNEWS_API_KEY:
        print("[NEWS ERROR] GNEWS_API_KEY not set")
        return []
    keywords = get_stock_keywords(stock_code)
    date_from = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%dT00:00:00Z')
    params = {'q': keywords, 'lang': 'id', 'country': 'id', 'max': max_results,
              'apikey': GNEWS_API_KEY, 'sortby': 'publishedAt', 'from': date_from}
    try:
        response = requests.get(GNEWS_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'errors' in data:
            print(f"[API ERROR] {stock_code}: {data['errors']}")
            return []
        articles = data.get('articles', [])
        return [{'title': a.get('title', ''), 'description': a.get('description', ''),
                 'url': a.get('url', ''), 'source': a.get('source', {}).get('name', 'Unknown'),
                 'published_at': a.get('publishedAt', ''), 'stock_code': stock_code} for a in articles]
    except Exception as e:
        print(f"[NEWS ERROR] {stock_code}: {e}")
        return []


def analyze_sentiment_simple(title, description):
    text = (title + ' ' + description).lower()
    pos = ['naik', 'meningkat', 'tumbuh', 'positif', 'laba', 'untung', 'profit', 'rekor', 'tertinggi', 'optimis', 'bullish', 'menguat', 'dividen', 'akuisisi', 'ekspansi']
    neg = ['turun', 'menurun', 'rugi', 'negatif', 'jatuh', 'anjlok', 'merosot', 'terendah', 'buruk', 'pesimis', 'bearish', 'melemah', 'koreksi', 'gagal', 'bangkrut']
    pos_count = sum(1 for w in pos if w in text)
    neg_count = sum(1 for w in neg if w in text)
    if pos_count > neg_count:
        return {'sentiment': 'POSITIF', 'color': 'success', 'icon': '[+]'}
    elif neg_count > pos_count:
        return {'sentiment': 'NEGATIF', 'color': 'danger', 'icon': '[-]'}
    return {'sentiment': 'NETRAL', 'color': 'secondary', 'icon': '[~]'}


def format_time_ago_str(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        if diff.days > 7:
            return dt.strftime('%d %b %Y')
        elif diff.days > 0:
            return f"{diff.days} hari lalu"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} jam lalu"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} menit lalu"
        return "Baru saja"
    except:
        return str(dt_str)[:10] if dt_str else ""


def get_news_with_sentiment(stock_code, max_results=15, force_refresh=False):
    stock_code = stock_code.upper()
    if not force_refresh and is_cache_valid_db(stock_code):
        print(f"[CACHE HIT] {stock_code} - loading from database")
        articles = load_from_database(stock_code)
        if articles:
            return articles
    print(f"[CACHE MISS] {stock_code} - fetching from API")
    articles = fetch_news_gnews(stock_code, max_results)
    for article in articles:
        article.update(analyze_sentiment_simple(article.get('title', ''), article.get('description', '')))
        article['published_formatted'] = format_time_ago_str(article.get('published_at', ''))
    if articles:
        save_to_database(stock_code, articles)
    else:
        print(f"[FALLBACK] {stock_code} - loading old data from database")
        articles = load_from_database(stock_code)
    return articles


def get_cache_info(stock_code=None):
    cursor = get_db_cursor()
    cached_stocks = 0
    last_refresh = '-'
    if cursor:
        try:
            cursor.execute("SELECT COUNT(DISTINCT stock_code) FROM news_fetch_log")
            result = cursor.fetchone()
            cached_stocks = result[0] if result else 0
            cursor.execute("SELECT MAX(last_fetch) FROM news_fetch_log")
            result = cursor.fetchone()
            if result and result[0]:
                lr = result[0]
                if lr.tzinfo:
                    lr = lr.replace(tzinfo=None)
                last_refresh = lr.strftime('%H:%M')
            cursor.close()
        except Exception as e:
            print(f"[DB ERROR] get_cache_info: {e}")
    info = {'refresh_mode': get_refresh_mode_text(), 'interval_hours': get_refresh_interval_hours(),
            'cached_stocks': cached_stocks, 'last_refresh': last_refresh}
    if stock_code:
        info['stock_cache_age'] = get_cache_age_text(stock_code.upper())
        articles = load_from_database(stock_code)
        info['stock_articles'] = len(articles)
    return info


def get_latest_news_summary(stock_codes, max_total=10):
    for code in stock_codes:
        if not is_cache_valid_db(code):
            get_news_with_sentiment(code, max_results=10)
    cursor = get_db_cursor()
    if not cursor:
        return []
    try:
        placeholders = ','.join(['%s'] * len(stock_codes))
        cursor.execute(f"""
            SELECT stock_code, title, description, url, source, published_at, sentiment, color, icon
            FROM news_cache WHERE stock_code IN ({placeholders}) ORDER BY published_at DESC LIMIT %s
        """, (*[c.upper() for c in stock_codes], max_total))
        rows = cursor.fetchall()
        cursor.close()
        articles = []
        for row in rows:
            if isinstance(row, dict):
                article = dict(row)
            else:
                article = {'stock_code': row[0], 'title': row[1], 'description': row[2], 'url': row[3],
                           'source': row[4], 'published_at': row[5].isoformat() if row[5] else '',
                           'sentiment': row[6], 'color': row[7], 'icon': row[8]}
            article['published_formatted'] = format_time_ago_str(article.get('published_at', ''))
            articles.append(article)
        return articles
    except Exception as e:
        print(f"[DB ERROR] get_latest_news_summary: {e}")
        return []


def get_all_stocks_news(stock_codes, max_per_stock=3):
    all_news = {}
    for code in stock_codes:
        news = get_news_with_sentiment(code, max_per_stock)
        if news:
            all_news[code] = news
    return all_news
