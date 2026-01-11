"""
News Service - GNews API + Google News RSS Fallback dengan Claude AI Dedupe
Primary: GNews API (dual accounts) | Fallback: Google News RSS (unlimited, free)
Refresh: Per 1 jam | Cache: PostgreSQL persistent
"""

import os
import requests
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict
from email.utils import parsedate_to_datetime
import threading
import json

from dotenv import load_dotenv
load_dotenv()

# API Keys - Dual GNews Accounts
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')      # Account 1 - jam genap
GNEWS_API_KEY_2 = os.getenv('GNEWS_API_KEY_2')  # Account 2 - jam ganjil/weekend/luar jam
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# API URLs
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
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


def get_db_connection():
    """Get direct database connection using DATABASE_URL"""
    try:
        import psycopg2
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("[DB ERROR] DATABASE_URL not set")
            return None
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"[DB ERROR] Cannot connect: {e}")
        return None


def get_db_cursor():
    """Get database cursor (caller must close cursor and connection)"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        # Attach connection to cursor for later commit/close
        cursor.connection = conn
        return cursor
    except Exception as e:
        print(f"[DB ERROR] Cannot get cursor: {e}")
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
        conn = cursor.connection
        cursor.close()
        conn.close()
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
    """Jam genap=GNews1, Jam ganjil=GNews2 (jam kerja 08-16), Luar jam=GNews2"""
    now = datetime.now()
    if now.weekday() >= 5:  # Weekend - pakai GNews Account 2
        return 'gnews2'
    if 8 <= now.hour < 16:  # Jam kerja - bergantian
        if now.hour % 2 == 0:  # Jam genap: 8,10,12,14,16
            return 'gnews1'
        else:  # Jam ganjil: 9,11,13,15
            return 'gnews2'
    return 'gnews2'  # Luar jam kerja - pakai GNews Account 2


def is_cache_valid_db(stock_code):
    """Check if cache is still valid based on refresh interval."""
    ensure_tables_exist()
    cursor = get_db_cursor()
    if not cursor:
        return False
    conn = cursor.connection
    try:
        # Use database NOW() to avoid timezone mismatch
        refresh_interval = get_refresh_interval_hours()
        cursor.execute("""
            SELECT last_fetch,
                   EXTRACT(EPOCH FROM (NOW() - last_fetch)) as age_seconds
            FROM news_fetch_log WHERE stock_code = %s
        """, (stock_code.upper(),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if not result:
            print(f"[CACHE] {stock_code}: No cache record found")
            return False

        age_seconds = result[1] if isinstance(result, tuple) else result.get('age_seconds')
        if age_seconds is None:
            return False

        max_age = refresh_interval * 3600
        is_valid = age_seconds < max_age

        print(f"[CACHE] {stock_code}: age={int(age_seconds)}s, max={int(max_age)}s, valid={is_valid}")
        return is_valid
    except Exception as e:
        print(f"[DB ERROR] is_cache_valid_db: {e}")
        try:
            conn.close()
        except:
            pass
        return False


def get_cache_age_text(stock_code):
    cursor = get_db_cursor()
    if not cursor:
        return "DB tidak tersedia"
    conn = cursor.connection
    try:
        cursor.execute("SELECT last_fetch FROM news_fetch_log WHERE stock_code = %s", (stock_code.upper(),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
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
        try:
            conn.close()
        except:
            pass
        return "Error"


def load_from_database(stock_code, limit=20):
    """Load news from database. Default limit 20 rows."""
    cursor = get_db_cursor()
    if not cursor:
        return []
    conn = cursor.connection
    try:
        cursor.execute("""
            SELECT title, description, url, source, published_at, sentiment, color, icon, api_source
            FROM news_cache WHERE stock_code = %s ORDER BY published_at DESC LIMIT %s
        """, (stock_code.upper(), limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
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
        try:
            conn.close()
        except:
            pass
        return []


def save_to_database(stock_code, articles):
    if not articles:
        return
    cursor = get_db_cursor()
    if not cursor:
        return
    conn = cursor.connection
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
            conn.commit()
            cursor.close()
            conn.close()
            print(f"[DB SAVED] {stock_code}: {len(articles)} articles")
    except Exception as e:
        print(f"[DB ERROR] save_to_database: {e}")
        try:
            conn.close()
        except:
            pass


def get_stock_keywords(stock_code):
    keywords = STOCK_KEYWORDS.get(stock_code.upper(), [stock_code, f"{stock_code} saham"])
    return keywords


def fetch_news_gnews(stock_code, max_results=10, use_account=1):
    """Fetch news from GNews API. use_account: 1 or 2"""
    api_key = GNEWS_API_KEY if use_account == 1 else GNEWS_API_KEY_2
    if not api_key:
        print(f"[GNEWS{use_account}] API key not configured")
        return []
    keywords = get_stock_keywords(stock_code)
    query = ' OR '.join([f'"{kw}"' for kw in keywords[:2]])
    date_from = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%dT00:00:00Z')
    params = {'q': query, 'lang': 'id', 'country': 'id', 'max': max_results,
              'apikey': api_key, 'sortby': 'publishedAt', 'from': date_from}
    try:
        response = requests.get(GNEWS_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'errors' in data:
            print(f"[GNEWS{use_account} ERROR] {stock_code}: {data['errors']}")
            return []
        articles = data.get('articles', [])
        return [{'title': a.get('title', ''), 'description': a.get('description', ''),
                 'url': a.get('url', ''), 'source': a.get('source', {}).get('name', 'Unknown'),
                 'published_at': a.get('publishedAt', ''), 'stock_code': stock_code,
                 'api_source': f'gnews{use_account}'} for a in articles]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"[GNEWS{use_account} LIMIT] {stock_code}: API limit reached")
        else:
            print(f"[GNEWS{use_account} ERROR] {stock_code}: {e}")
        return []
    except Exception as e:
        print(f"[GNEWS{use_account} ERROR] {stock_code}: {e}")
        return []


def fetch_news_google_rss(stock_code, max_results=10):
    """
    Fetch news from Google News RSS - FREE & UNLIMITED
    Fallback when GNews API limit reached or returns empty
    """
    keywords = get_stock_keywords(stock_code)
    # Use first 2 keywords for search
    query = '+'.join(keywords[:2])

    params = {
        'q': query,
        'hl': 'id',      # Bahasa Indonesia
        'gl': 'ID',      # Region Indonesia
        'ceid': 'ID:id'  # Country edition
    }

    try:
        response = requests.get(GOOGLE_NEWS_RSS_URL, params=params, timeout=15)
        response.raise_for_status()

        # Parse RSS XML
        root = ET.fromstring(response.content)
        articles = []

        # Find all items in the RSS feed
        for item in root.findall('.//item')[:max_results]:
            title = item.find('title')
            link = item.find('link')
            pub_date = item.find('pubDate')
            source = item.find('source')

            # Parse published date
            published_at = ''
            if pub_date is not None and pub_date.text:
                try:
                    dt = parsedate_to_datetime(pub_date.text)
                    published_at = dt.isoformat()
                except:
                    published_at = pub_date.text

            # Extract source name from title (format: "Title - Source")
            title_text = title.text if title is not None else ''
            source_name = 'Google News'
            if source is not None and source.text:
                source_name = source.text
            elif ' - ' in title_text:
                # Fallback: extract from title
                parts = title_text.rsplit(' - ', 1)
                if len(parts) == 2:
                    title_text = parts[0].strip()
                    source_name = parts[1].strip()

            # Get description from title (Google RSS doesn't have description)
            description = title_text[:200] if title_text else ''

            articles.append({
                'title': title_text,
                'description': description,
                'url': link.text if link is not None else '',
                'source': source_name,
                'published_at': published_at,
                'stock_code': stock_code,
                'api_source': 'google_rss'
            })

        print(f"[GOOGLE RSS] {stock_code}: {len(articles)} articles")
        return articles

    except ET.ParseError as e:
        print(f"[GOOGLE RSS ERROR] {stock_code}: XML parse error - {e}")
        return []
    except Exception as e:
        print(f"[GOOGLE RSS ERROR] {stock_code}: {e}")
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


def get_news_with_sentiment(stock_code, max_results=20, force_refresh=False):
    """
    Fetch news with sentiment. max_results default 20.
    News baru diletakkan di atas, news lama tetap ditampilkan.
    Priority: GNews Account 1/2 -> Google News RSS (fallback)
    """
    stock_code = stock_code.upper()

    # Check database cache first
    if not force_refresh and is_cache_valid_db(stock_code):
        print(f"[CACHE HIT] {stock_code} - loading from database")
        articles = load_from_database(stock_code, limit=max_results)
        if articles:
            return articles

    # Fetch from current API with fallback chain
    current_api = get_current_api()
    use_account = 1 if current_api == 'gnews1' else 2
    print(f"[CACHE MISS] {stock_code} - fetching from GNews Account {use_account}")

    new_articles = fetch_news_gnews(stock_code, max_results=10, use_account=use_account)

    # Fallback 1: Try other GNews account
    if not new_articles:
        fallback_account = 2 if use_account == 1 else 1
        print(f"[FALLBACK 1] {stock_code} - trying GNews Account {fallback_account}")
        new_articles = fetch_news_gnews(stock_code, max_results=10, use_account=fallback_account)

    # Fallback 2: Use Google News RSS (FREE & UNLIMITED)
    if not new_articles:
        print(f"[FALLBACK 2] {stock_code} - trying Google News RSS")
        new_articles = fetch_news_google_rss(stock_code, max_results=10)

    print(f"[FETCH] {stock_code}: {len(new_articles)} new articles")

    # Load existing from DB to combine (news lama tetap ditampilkan)
    existing = load_from_database(stock_code, limit=50)  # Load more for deduplication

    # Combine: new articles first, then existing
    if existing:
        # Get URLs of new articles to avoid duplicates
        new_urls = {a.get('url') for a in new_articles}
        # Filter existing that are not in new
        existing_unique = [a for a in existing if a.get('url') not in new_urls]
        all_articles = new_articles + existing_unique
    else:
        all_articles = new_articles

    # Deduplicate with Claude if too many
    if len(all_articles) > 25:
        all_articles = dedupe_with_claude(all_articles)

    # Add sentiment analysis (use simple for speed, Claude for accuracy on first few)
    for i, article in enumerate(all_articles):
        # Only analyze sentiment for new articles (no sentiment yet)
        if not article.get('sentiment'):
            if i < 3 and CLAUDE_API_KEY:  # Claude for top 3 new articles
                article.update(analyze_sentiment_claude(article.get('title', ''), article.get('description', '')))
            else:
                article.update(analyze_sentiment_simple(article.get('title', ''), article.get('description', '')))
        article['published_formatted'] = format_time_ago_str(article.get('published_at', ''))

    # Keep up to max_results (default 20)
    all_articles = all_articles[:max_results]

    # Save all to database (news lama + baru)
    if all_articles:
        save_to_database(stock_code, all_articles)
    else:
        print(f"[FALLBACK] {stock_code} - loading old data from database")
        all_articles = load_from_database(stock_code, limit=max_results)

    return all_articles


def get_cache_info(stock_code=None):
    cursor = get_db_cursor()
    cached_stocks = 0
    last_refresh = '-'
    if cursor:
        conn = cursor.connection
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
            conn.close()
        except Exception as e:
            print(f"[DB ERROR] get_cache_info: {e}")
            try:
                conn.close()
            except:
                pass
    info = {'refresh_mode': get_refresh_mode_text(), 'interval_hours': get_refresh_interval_hours(),
            'cached_stocks': cached_stocks, 'last_refresh': last_refresh}
    if stock_code:
        info['stock_cache_age'] = get_cache_age_text(stock_code.upper())
        articles = load_from_database(stock_code)
        info['stock_articles'] = len(articles)
    return info


def get_latest_news_summary(stock_codes, max_total=10):
    """
    Berita Terbaru Semua Emiten:
    - Jam kerja (08-16): tampilkan berita 2 jam terakhir (2 siklus refresh)
    - Luar jam kerja/weekend: tampilkan sampai refresh berikutnya
    """
    for code in stock_codes:
        if not is_cache_valid_db(code):
            get_news_with_sentiment(code, max_results=20)

    cursor = get_db_cursor()
    if not cursor:
        return []
    conn = cursor.connection

    try:
        now = datetime.now()
        placeholders = ','.join(['%s'] * len(stock_codes))

        # Determine time filter based on work hours
        if now.weekday() < 5 and 8 <= now.hour < 16:
            # Jam kerja: tampilkan berita 2 jam terakhir (2 siklus)
            time_filter = "AND fetched_at > NOW() - INTERVAL '2 hours'"
        else:
            # Luar jam kerja/weekend: tampilkan sampai refresh berikutnya
            # Calculate next refresh interval
            interval = get_refresh_interval_hours()
            time_filter = f"AND fetched_at > NOW() - INTERVAL '{int(interval)} hours'"

        cursor.execute(f"""
            SELECT stock_code, title, description, url, source, published_at, sentiment, color, icon
            FROM news_cache
            WHERE stock_code IN ({placeholders}) {time_filter}
            ORDER BY published_at DESC LIMIT %s
        """, (*[c.upper() for c in stock_codes], max_total))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

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

        # If no recent news, load from cache anyway
        if not articles:
            cursor2 = get_db_cursor()
            if cursor2:
                conn2 = cursor2.connection
                try:
                    cursor2.execute(f"""
                        SELECT stock_code, title, description, url, source, published_at, sentiment, color, icon
                        FROM news_cache WHERE stock_code IN ({placeholders})
                        ORDER BY published_at DESC LIMIT %s
                    """, (*[c.upper() for c in stock_codes], max_total))
                    rows = cursor2.fetchall()
                    cursor2.close()
                    conn2.close()
                    for row in rows:
                        if isinstance(row, dict):
                            article = dict(row)
                        else:
                            article = {'stock_code': row[0], 'title': row[1], 'description': row[2], 'url': row[3],
                                       'source': row[4], 'published_at': row[5].isoformat() if row[5] else '',
                                       'sentiment': row[6], 'color': row[7], 'icon': row[8]}
                        article['published_formatted'] = format_time_ago_str(article.get('published_at', ''))
                        articles.append(article)
                except Exception as e2:
                    print(f"[DB ERROR] get_latest_news_summary fallback: {e2}")
                    try:
                        conn2.close()
                    except:
                        pass

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
