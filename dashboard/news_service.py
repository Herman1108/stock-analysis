"""
News Service - GNews API dengan Smart Caching
Jam kerja (08-16): 2 jam | Luar jam: 5 jam | Weekend: 6 jam
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

# GLOBAL CACHE
NEWS_CACHE = {}
CACHE_LOCK = threading.Lock()
LAST_REFRESH_TIME = None

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
    'PANI': ['Pantai Indah Kapuk', 'PANI saham'],
    'BREN': ['Barito Renewables', 'BREN saham'],
    'CUAN': ['Petrindo Jaya', 'CUAN saham'],
    'DSSA': ['Dian Swastatika', 'DSSA saham'],
    'AMMN': ['Amman Mineral', 'AMMN saham'],
}


def get_refresh_interval_hours():
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    if weekday >= 5:
        return 6.0
    if 8 <= hour < 16:
        return 2.0
    return 5.0


def get_refresh_mode_text():
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    if weekday >= 5:
        return "Weekend (per 6 jam)"
    elif 8 <= hour < 16:
        return "Jam Kerja (per 2 jam)"
    return "Luar Jam Kerja (per 5 jam)"


def is_cache_valid(stock_code):
    if stock_code not in NEWS_CACHE:
        return False
    cache_time = NEWS_CACHE[stock_code].get('timestamp')
    if not cache_time:
        return False
    interval_hours = get_refresh_interval_hours()
    age = datetime.now() - cache_time
    return age.total_seconds() < (interval_hours * 3600)


def get_cache_age_text(stock_code):
    if stock_code not in NEWS_CACHE:
        return "Belum ada data"
    cache_time = NEWS_CACHE[stock_code].get('timestamp')
    if not cache_time:
        return "Belum ada data"
    age = datetime.now() - cache_time
    minutes = int(age.total_seconds() / 60)
    if minutes < 1:
        return "Baru saja"
    elif minutes < 60:
        return f"{minutes} menit lalu"
    return f"{minutes // 60} jam lalu"


def get_stock_keywords(stock_code):
    keywords = STOCK_KEYWORDS.get(stock_code.upper(), [stock_code])
    return ' OR '.join([f'"{kw}"' for kw in keywords[:2]])


def fetch_news_gnews(stock_code, max_results=15):
    if not GNEWS_API_KEY:
        return []
    keywords = get_stock_keywords(stock_code)
    date_from = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%dT00:00:00Z')
    params = {
        'q': keywords, 'lang': 'id', 'country': 'id',
        'max': max_results, 'apikey': GNEWS_API_KEY,
        'sortby': 'publishedAt', 'from': date_from
    }
    try:
        response = requests.get(GNEWS_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        return [{
            'title': a.get('title', ''),
            'description': a.get('description', ''),
            'url': a.get('url', ''),
            'source': a.get('source', {}).get('name', 'Unknown'),
            'published_at': a.get('publishedAt', ''),
            'stock_code': stock_code
        } for a in articles]
    except Exception as e:
        print(f"Error: {e}")
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


def format_time_ago(dt):
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


def get_news_with_sentiment(stock_code, max_results=15, force_refresh=False):
    global NEWS_CACHE, LAST_REFRESH_TIME
    stock_code = stock_code.upper()

    # Use cache if valid
    if not force_refresh and is_cache_valid(stock_code):
        print(f"[CACHE HIT] {stock_code}")
        return NEWS_CACHE[stock_code]['articles']

    # Fetch fresh
    print(f"[CACHE MISS] {stock_code} - fetching")
    articles = fetch_news_gnews(stock_code, max_results)

    for article in articles:
        article.update(analyze_sentiment_simple(article.get('title', ''), article.get('description', '')))
        try:
            pub_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
            article['published_formatted'] = format_time_ago(pub_date)
        except:
            article['published_formatted'] = article.get('published_at', '')[:10]

    with CACHE_LOCK:
        NEWS_CACHE[stock_code] = {'articles': articles, 'timestamp': datetime.now()}
        LAST_REFRESH_TIME = datetime.now()

    return articles


def get_cache_info(stock_code=None):
    info = {
        'refresh_mode': get_refresh_mode_text(),
        'interval_hours': get_refresh_interval_hours(),
        'cached_stocks': len(NEWS_CACHE),
        'last_refresh': LAST_REFRESH_TIME.strftime('%H:%M') if LAST_REFRESH_TIME else '-'
    }
    if stock_code and stock_code.upper() in NEWS_CACHE:
        info['stock_cache_age'] = get_cache_age_text(stock_code.upper())
        info['stock_articles'] = len(NEWS_CACHE[stock_code.upper()].get('articles', []))
    return info


def get_latest_news_summary(stock_codes, max_total=10):
    all_articles = []
    for code in stock_codes:
        if code.upper() in NEWS_CACHE:
            all_articles.extend(NEWS_CACHE[code.upper()].get('articles', [])[:2])
    all_articles.sort(key=lambda x: x.get('published_at', ''), reverse=True)
    return all_articles[:max_total]

def get_all_stocks_news(stock_codes, max_per_stock=3):
    """Get news for multiple stocks"""
    all_news = {}
    for code in stock_codes:
        news = get_news_with_sentiment(code, max_per_stock)
        if news:
            all_news[code] = news
    return all_news
