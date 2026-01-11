"""
News Service - Dual API (GNews + Marketaux) dengan Claude AI Dedupe
Refresh: Per 1 jam | Cache: PostgreSQL persistent
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import threading
import json

from dotenv import load_dotenv
load_dotenv()

# API Keys
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
MARKETAUX_API_KEY = os.getenv('MARKETAUX_API_KEY')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# API URLs
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"
MARKETAUX_BASE_URL = "https://api.marketaux.com/v1/news/all"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

DB_LOCK = threading.Lock()
TABLES_CREATED = False

# Refresh intervals
# Jam kerja (08-16): 1 jam | Luar jam: 5 jam | Weekend: 6 jam

STOCK_KEYWORDS = {
    'BBCA': ['BBCA', 'Bank Central Asia', 'BCA'],
    'BMRI': ['BMRI', 'Bank Mandiri', 'Mandiri'],
    'BBRI': ['BBRI', 'Bank BRI', 'Bank Rakyat Indonesia'],
    'BBNI': ['BBNI', 'Bank BNI', 'Bank Negara Indonesia'],
    'TLKM': ['TLKM', 'Telkom', 'Telekomunikasi Indonesia'],
    'ASII': ['ASII', 'Astra', 'Astra International'],
    'UNVR': ['UNVR', 'Unilever Indonesia'],
    'HMSP': ['HMSP', 'Sampoerna', 'HM Sampoerna'],
    'GGRM': ['GGRM', 'Gudang Garam'],
    'ICBP': ['ICBP', 'Indofood CBP'],
    'INDF': ['INDF', 'Indofood'],
    'KLBF': ['KLBF', 'Kalbe Farma'],
    'PGAS': ['PGAS', 'PGN', 'Perusahaan Gas Negara'],
    'PTBA': ['PTBA', 'Bukit Asam'],
    'ADRO': ['ADRO', 'Adaro', 'Adaro Energy'],
    'ANTM': ['ANTM', 'Antam', 'Aneka Tambang'],
    'INCO': ['INCO', 'Vale Indonesia'],
    'CPIN': ['CPIN', 'Charoen Pokphand'],
    'EXCL': ['EXCL', 'XL Axiata'],
    'ISAT': ['ISAT', 'Indosat'],
    'SMGR': ['SMGR', 'Semen Indonesia'],
    'INTP': ['INTP', 'Indocement'],
    'UNTR': ['UNTR', 'United Tractors'],
    'JSMR': ['JSMR', 'Jasa Marga'],
    'WIKA': ['WIKA', 'Wijaya Karya'],
    'PANI': ['PANI', 'Pantai Indah Kapuk'],
    'BREN': ['BREN', 'Barito Renewables'],
    'CUAN': ['CUAN', 'Petrindo Jaya'],
    'DSSA': ['DSSA', 'Dian Swastatika'],
    'AMMN': ['AMMN', 'Amman Mineral'],
    'CDIA': ['CDIA', 'Cisarua Mountain Dairy'],
    'PTRO': ['PTRO', 'Petrosea'],
}


def get_db_cursor():
    try:
        from database import get_cursor
        return get_cursor()
    except Exception as e:
        print(f"[DB ERROR] Cannot connect: {e}")
        return None


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
                api_source VARCHAR(20) DEFAULT 'gnews',
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
    if now.weekday() >= 5:  # Weekend
        return 6.0
    if 8 <= now.hour < 16:  # Jam kerja
        return 1.0
    return 5.0  # Luar jam kerja


def get_refresh_mode_text():
    now = datetime.now()
    if now.weekday() >= 5:
        return "Weekend (per 6 jam)"
    elif 8 <= now.hour < 16:
        return "Jam Kerja (per 1 jam)"
    return "Luar Jam Kerja (per 5 jam)"


def get_current_api():
    """Jam genap=GNews, Jam ganjil=Marketaux (hanya jam kerja 08-16)"""
    now = datetime.now()
    if now.weekday() >= 5:  # Weekend - pakai GNews
        return 'gnews'
    if 8 <= now.hour < 16:  # Jam kerja - bergantian
        if now.hour % 2 == 0:  # Jam genap: 8,10,12,14,16
            return 'gnews'
        else:  # Jam ganjil: 9,11,13,15
            return 'marketaux'
    return 'gnews'  # Luar jam kerja - pakai GNews


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
        return age.total_seconds() < (REFRESH_INTERVAL_HOURS * 3600)
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
            SELECT title, description, url, source, published_at, sentiment, color, icon, api_source
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
                    'sentiment': row[5], 'color': row[6], 'icon': row[7],
                    'api_source': row[8] if len(row) > 8 else 'gnews'
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
                    INSERT INTO news_cache (stock_code, title, description, url, source, published_at, sentiment, color, icon, api_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stock_code, url) DO UPDATE SET
                        title = EXCLUDED.title, description = EXCLUDED.description,
                        sentiment = EXCLUDED.sentiment, color = EXCLUDED.color, icon = EXCLUDED.icon, fetched_at = NOW()
                """, (stock_code.upper(), article.get('title', ''), article.get('description', ''),
                      article.get('url', ''), article.get('source', ''), published_at,
                      article.get('sentiment', 'NETRAL'), article.get('color', 'secondary'),
                      article.get('icon', '[~]'), article.get('api_source', 'gnews')))
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
    return keywords


def fetch_news_gnews(stock_code, max_results=10):
    if not GNEWS_API_KEY:
        return []
    keywords = get_stock_keywords(stock_code)
    query = ' OR '.join([f'"{kw}"' for kw in keywords[:2]])
    date_from = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%dT00:00:00Z')
    params = {'q': query, 'lang': 'id', 'country': 'id', 'max': max_results,
              'apikey': GNEWS_API_KEY, 'sortby': 'publishedAt', 'from': date_from}
    try:
        response = requests.get(GNEWS_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'errors' in data:
            print(f"[GNEWS ERROR] {stock_code}: {data['errors']}")
            return []
        articles = data.get('articles', [])
        return [{'title': a.get('title', ''), 'description': a.get('description', ''),
                 'url': a.get('url', ''), 'source': a.get('source', {}).get('name', 'Unknown'),
                 'published_at': a.get('publishedAt', ''), 'stock_code': stock_code,
                 'api_source': 'gnews'} for a in articles]
    except Exception as e:
        print(f"[GNEWS ERROR] {stock_code}: {e}")
        return []


def fetch_news_marketaux(stock_code, max_results=10):
    if not MARKETAUX_API_KEY:
        return []
    keywords = get_stock_keywords(stock_code)
    # Marketaux uses search parameter
    search_query = ','.join(keywords[:2])
    params = {
        'api_token': MARKETAUX_API_KEY,
        'search': search_query,
        'language': 'id',
        'filter_entities': 'true',
        'limit': max_results
    }
    try:
        response = requests.get(MARKETAUX_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'error' in data:
            print(f"[MARKETAUX ERROR] {stock_code}: {data['error']}")
            return []
        articles = data.get('data', [])
        return [{'title': a.get('title', ''), 'description': a.get('description', ''),
                 'url': a.get('url', ''), 'source': a.get('source', 'Marketaux'),
                 'published_at': a.get('published_at', ''), 'stock_code': stock_code,
                 'api_source': 'marketaux'} for a in articles]
    except Exception as e:
        print(f"[MARKETAUX ERROR] {stock_code}: {e}")
        return []


def dedupe_with_claude(articles):
    """Use Claude AI to deduplicate similar news articles"""
    if not CLAUDE_API_KEY or len(articles) <= 1:
        return articles

    try:
        # Create summary of articles for Claude
        article_summaries = []
        for i, a in enumerate(articles):
            article_summaries.append(f"{i}: {a.get('title', '')[:100]}")

        prompt = f"""Analisis berita saham berikut dan identifikasi berita yang duplikat atau sangat mirip.

Daftar berita:
{chr(10).join(article_summaries)}

Berikan response dalam format JSON array berisi index berita yang UNIK (tidak duplikat).
Contoh response: [0, 2, 5, 7]

Hanya berikan JSON array, tanpa penjelasan lain."""

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01'
        }

        payload = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 200,
            'messages': [{'role': 'user', 'content': prompt}]
        }

        response = requests.post(CLAUDE_API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()

        # Parse response
        content = result.get('content', [{}])[0].get('text', '[]')
        # Extract JSON array from response
        import re
        match = re.search(r'\[([\d,\s]+)\]', content)
        if match:
            unique_indices = json.loads('[' + match.group(1) + ']')
            unique_articles = [articles[i] for i in unique_indices if i < len(articles)]
            print(f"[CLAUDE DEDUPE] {len(articles)} -> {len(unique_articles)} articles")
            return unique_articles if unique_articles else articles

        return articles
    except Exception as e:
        print(f"[CLAUDE ERROR] dedupe: {e}")
        return articles


def analyze_sentiment_claude(title, description):
    """Use Claude for sentiment analysis"""
    if not CLAUDE_API_KEY:
        return analyze_sentiment_simple(title, description)

    try:
        text = f"{title}. {description}"[:500]
        prompt = f"""Analisis sentiment berita saham berikut dalam 1 kata saja (POSITIF/NEGATIF/NETRAL):

"{text}"

Jawab hanya dengan 1 kata: POSITIF, NEGATIF, atau NETRAL"""

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01'
        }

        payload = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 10,
            'messages': [{'role': 'user', 'content': prompt}]
        }

        response = requests.post(CLAUDE_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        content = result.get('content', [{}])[0].get('text', '').upper().strip()

        if 'POSITIF' in content:
            return {'sentiment': 'POSITIF', 'color': 'success', 'icon': '[+]'}
        elif 'NEGATIF' in content:
            return {'sentiment': 'NEGATIF', 'color': 'danger', 'icon': '[-]'}
        return {'sentiment': 'NETRAL', 'color': 'secondary', 'icon': '[~]'}
    except Exception as e:
        print(f"[CLAUDE ERROR] sentiment: {e}")
        return analyze_sentiment_simple(title, description)


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

    # Check database cache first
    if not force_refresh and is_cache_valid_db(stock_code):
        print(f"[CACHE HIT] {stock_code} - loading from database")
        articles = load_from_database(stock_code)
        if articles:
            return articles

    # Fetch from current API (bergantian jam genap/ganjil)
    current_api = get_current_api()
    print(f"[CACHE MISS] {stock_code} - fetching from {current_api}")
    
    if current_api == 'marketaux':
        all_articles = fetch_news_marketaux(stock_code, max_results)
    else:
        all_articles = fetch_news_gnews(stock_code, max_results)
    
    print(f"[FETCH] {stock_code}: {current_api}={len(all_articles)} articles")
    
    # Load existing from DB to combine and dedupe
    existing = load_from_database(stock_code)
    if existing:
        all_articles = all_articles + existing
        # Deduplicate with Claude
        if len(all_articles) > 1:
            all_articles = dedupe_with_claude(all_articles)

    # Add sentiment analysis (use simple for speed, Claude for accuracy on first few)
    for i, article in enumerate(all_articles):
        if i < 3 and CLAUDE_API_KEY:  # Claude for top 3 articles
            article.update(analyze_sentiment_claude(article.get('title', ''), article.get('description', '')))
        else:
            article.update(analyze_sentiment_simple(article.get('title', ''), article.get('description', '')))
        article['published_formatted'] = format_time_ago_str(article.get('published_at', ''))

    # Limit to max_results
    all_articles = all_articles[:max_results]

    # Save to database
    if all_articles:
        save_to_database(stock_code, all_articles)
    else:
        print(f"[FALLBACK] {stock_code} - loading old data from database")
        all_articles = load_from_database(stock_code)

    return all_articles


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
