"""
News Service - GNews API Integration untuk HermanStock
Mengambil berita saham Indonesia dan analisis dengan Claude AI
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"

# Mapping stock code to search keywords (Indonesian)
STOCK_KEYWORDS = {
    'BBCA': ['BBCA', 'Bank Central Asia', 'BCA'],
    'BMRI': ['BMRI', 'Bank Mandiri', 'Mandiri'],
    'BBRI': ['BBRI', 'Bank BRI', 'Bank Rakyat Indonesia'],
    'BBNI': ['BBNI', 'Bank BNI', 'Bank Negara Indonesia'],
    'TLKM': ['TLKM', 'Telkom', 'Telekomunikasi Indonesia'],
    'ASII': ['ASII', 'Astra International', 'Astra'],
    'UNVR': ['UNVR', 'Unilever Indonesia', 'Unilever'],
    'HMSP': ['HMSP', 'HM Sampoerna', 'Sampoerna'],
    'GGRM': ['GGRM', 'Gudang Garam'],
    'ICBP': ['ICBP', 'Indofood CBP', 'Indofood'],
    'INDF': ['INDF', 'Indofood Sukses Makmur'],
    'KLBF': ['KLBF', 'Kalbe Farma', 'Kalbe'],
    'PGAS': ['PGAS', 'Perusahaan Gas Negara', 'PGN'],
    'PTBA': ['PTBA', 'Bukit Asam', 'Tambang Batubara'],
    'ADRO': ['ADRO', 'Adaro Energy', 'Adaro'],
    'ANTM': ['ANTM', 'Aneka Tambang', 'Antam'],
    'INCO': ['INCO', 'Vale Indonesia', 'INCO'],
    'CPIN': ['CPIN', 'Charoen Pokphand', 'CP Indonesia'],
    'EXCL': ['EXCL', 'XL Axiata', 'XL'],
    'ISAT': ['ISAT', 'Indosat Ooredoo', 'Indosat'],
    'SMGR': ['SMGR', 'Semen Indonesia', 'Semen Gresik'],
    'INTP': ['INTP', 'Indocement', 'Semen Tiga Roda'],
    'UNTR': ['UNTR', 'United Tractors'],
    'JSMR': ['JSMR', 'Jasa Marga'],
    'WIKA': ['WIKA', 'Wijaya Karya'],
    'WSKT': ['WSKT', 'Waskita Karya'],
    'PTPP': ['PTPP', 'PP Persero', 'Pembangunan Perumahan'],
    'BSDE': ['BSDE', 'Bumi Serpong Damai', 'BSD'],
    'PWON': ['PWON', 'Pakuwon Jati'],
    'SMRA': ['SMRA', 'Summarecon Agung', 'Summarecon'],
}


def get_stock_keywords(stock_code: str) -> str:
    """Get search keywords for a stock code"""
    keywords = STOCK_KEYWORDS.get(stock_code.upper(), [stock_code])
    # Join with OR for broader search
    return ' OR '.join([f'"{kw}"' for kw in keywords[:2]])  # Limit to 2 keywords


def fetch_news_gnews(stock_code: str, max_results: int = 5) -> List[Dict]:
    """
    Fetch news from GNews API for a specific stock

    Args:
        stock_code: Stock code (e.g., 'BBCA')
        max_results: Maximum number of news articles (default 5)

    Returns:
        List of news articles with title, description, url, source, publishedAt
    """
    if not GNEWS_API_KEY:
        print("Warning: GNEWS_API_KEY not found in environment")
        return []

    keywords = get_stock_keywords(stock_code)

    params = {
        'q': keywords,
        'lang': 'id',  # Indonesian only
        'country': 'id',  # Indonesia
        'max': max_results,
        'apikey': GNEWS_API_KEY,
        'sortby': 'publishedAt'  # Latest first
    }

    try:
        response = requests.get(GNEWS_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        articles = data.get('articles', [])

        # Format articles
        formatted = []
        for article in articles:
            formatted.append({
                'title': article.get('title', ''),
                'description': article.get('description', ''),
                'content': article.get('content', ''),
                'url': article.get('url', ''),
                'image': article.get('image', ''),
                'source': article.get('source', {}).get('name', 'Unknown'),
                'published_at': article.get('publishedAt', ''),
                'stock_code': stock_code
            })

        return formatted

    except requests.exceptions.RequestException as e:
        print(f"Error fetching news for {stock_code}: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing news response: {e}")
        return []


def analyze_sentiment_simple(title: str, description: str) -> Dict:
    """
    Simple rule-based sentiment analysis (tanpa Claude API)
    Untuk menghemat biaya, gunakan ini sebagai default

    Returns:
        Dict with sentiment, score, color
    """
    text = (title + ' ' + description).lower()

    # Positive keywords (Indonesian)
    positive_words = [
        'naik', 'meningkat', 'tumbuh', 'positif', 'laba', 'untung', 'profit',
        'rekor', 'tertinggi', 'bagus', 'optimis', 'bullish', 'menguat',
        'akuisisi', 'ekspansi', 'dividen', 'buyback', 'pembelian',
        'upgrade', 'recommended', 'outperform', 'buy', 'beli'
    ]

    # Negative keywords (Indonesian)
    negative_words = [
        'turun', 'menurun', 'rugi', 'negatif', 'jatuh', 'anjlok', 'merosot',
        'terendah', 'buruk', 'pesimis', 'bearish', 'melemah', 'koreksi',
        'gagal', 'bangkrut', 'default', 'fraud', 'skandal', 'investigasi',
        'downgrade', 'underperform', 'sell', 'jual', 'suspend'
    ]

    pos_count = sum(1 for word in positive_words if word in text)
    neg_count = sum(1 for word in negative_words if word in text)

    if pos_count > neg_count:
        return {
            'sentiment': 'POSITIF',
            'score': min(pos_count * 20, 100),
            'color': 'success',
            'icon': '[+]'
        }
    elif neg_count > pos_count:
        return {
            'sentiment': 'NEGATIF',
            'score': min(neg_count * 20, 100),
            'color': 'danger',
            'icon': '[-]'
        }
    else:
        return {
            'sentiment': 'NETRAL',
            'score': 50,
            'color': 'secondary',
            'icon': '[~]'
        }


def get_news_with_sentiment(stock_code: str, max_results: int = 5) -> List[Dict]:
    """
    Get news articles with sentiment analysis

    Args:
        stock_code: Stock code (e.g., 'BBCA')
        max_results: Maximum number of news articles

    Returns:
        List of news articles with sentiment analysis
    """
    articles = fetch_news_gnews(stock_code, max_results)

    for article in articles:
        sentiment = analyze_sentiment_simple(
            article.get('title', ''),
            article.get('description', '')
        )
        article.update(sentiment)

        # Format published date
        try:
            pub_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
            article['published_formatted'] = format_time_ago(pub_date)
        except:
            article['published_formatted'] = article.get('published_at', '')[:10]

    return articles


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'X waktu lalu'"""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt

    if diff.days > 7:
        return dt.strftime('%d %b %Y')
    elif diff.days > 0:
        return f"{diff.days} hari lalu"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} jam lalu"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} menit lalu"
    else:
        return "Baru saja"


def get_all_stocks_news(stock_codes: List[str], max_per_stock: int = 3) -> Dict[str, List[Dict]]:
    """
    Get news for multiple stocks

    Args:
        stock_codes: List of stock codes
        max_per_stock: Maximum news per stock

    Returns:
        Dict mapping stock_code to list of news articles
    """
    all_news = {}

    for code in stock_codes:
        news = get_news_with_sentiment(code, max_per_stock)
        if news:
            all_news[code] = news

    return all_news


def get_latest_news_summary(stock_codes: List[str], max_total: int = 10) -> List[Dict]:
    """
    Get latest news across all stocks, sorted by date

    Args:
        stock_codes: List of stock codes
        max_total: Maximum total news to return

    Returns:
        List of latest news articles across all stocks
    """
    all_articles = []

    for code in stock_codes:
        articles = get_news_with_sentiment(code, max_results=2)
        all_articles.extend(articles)

    # Sort by published date (newest first)
    all_articles.sort(
        key=lambda x: x.get('published_at', ''),
        reverse=True
    )

    return all_articles[:max_total]


# Database caching functions (optional - untuk mengurangi API calls)
def cache_news_to_db(articles: List[Dict], db_execute_func=None):
    """Cache news articles to database to reduce API calls"""
    if not db_execute_func:
        return

    for article in articles:
        query = """
        INSERT INTO news_cache (stock_code, title, description, url, source, published_at, sentiment, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (url) DO UPDATE SET sentiment = EXCLUDED.sentiment
        """
        try:
            db_execute_func(query, (
                article.get('stock_code'),
                article.get('title'),
                article.get('description'),
                article.get('url'),
                article.get('source'),
                article.get('published_at'),
                article.get('sentiment')
            ))
        except Exception as e:
            print(f"Error caching news: {e}")


def get_cached_news(stock_code: str, hours: int = 6, db_query_func=None) -> List[Dict]:
    """Get cached news from database if still fresh"""
    if not db_query_func:
        return []

    query = """
    SELECT * FROM news_cache
    WHERE stock_code = %s AND created_at > NOW() - INTERVAL '%s hours'
    ORDER BY published_at DESC
    LIMIT 5
    """
    try:
        results = db_query_func(query, (stock_code, hours))
        return results or []
    except:
        return []


# Test function
if __name__ == "__main__":
    # Test fetching news
    print("Testing GNews API...")
    news = get_news_with_sentiment('BBCA', max_results=3)

    for article in news:
        print(f"\n{article['icon']} {article['sentiment']} | {article['published_formatted']}")
        print(f"   {article['title'][:60]}...")
        print(f"   Sumber: {article['source']}")
