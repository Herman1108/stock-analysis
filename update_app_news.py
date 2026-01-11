"""Update app.py news import and add cache info"""

# Read app.py
with open('dashboard/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update import
old_import = '''# News service for stock news
try:
    from news_service import get_news_with_sentiment, get_all_stocks_news, get_latest_news_summary
except ImportError:
    print('Warning: news_service not available')
    def get_news_with_sentiment(stock_code, max_results=5): return []
    def get_all_stocks_news(codes, max_per=3): return {}
    def get_latest_news_summary(codes, max_total=10): return []'''

new_import = '''# News service for stock news
try:
    from news_service import get_news_with_sentiment, get_all_stocks_news, get_latest_news_summary, get_cache_info
except ImportError:
    print('Warning: news_service not available')
    def get_news_with_sentiment(stock_code, max_results=5): return []
    def get_all_stocks_news(codes, max_per=3): return {}
    def get_latest_news_summary(codes, max_total=10): return []
    def get_cache_info(stock_code=None): return {'refresh_mode': '-', 'interval_hours': 2, 'cached_stocks': 0, 'last_refresh': '-'}'''

content = content.replace(old_import, new_import)

# Update news page to show cache info - replace the info card
old_info_card = '''                # News Info Card
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([
                            html.I(className="fas fa-info-circle me-2 text-info"),
                            "Tentang Berita"
                        ], className="mb-0")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Sumber: "), "GNews API"
                        ], className="small mb-2"),
                        html.P([
                            html.Strong("Bahasa: "), "Indonesia"
                        ], className="small mb-2"),
                        html.P([
                            html.Strong("Sentiment Analysis: "), "AI-powered"
                        ], className="small mb-2"),'''

new_info_card = '''                # Cache Status Card
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([
                            html.I(className="fas fa-clock me-2 text-info"),
                            "Status Cache"
                        ], className="mb-0")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Mode: "), cache_info.get('refresh_mode', '-')
                        ], className="small mb-2"),
                        html.P([
                            html.Strong("Refresh: "), f"per {cache_info.get('interval_hours', 2)} jam"
                        ], className="small mb-2"),
                        html.P([
                            html.Strong("Emiten di cache: "), str(cache_info.get('cached_stocks', 0))
                        ], className="small mb-2"),
                        html.P([
                            html.Strong("Update terakhir: "), cache_info.get('last_refresh', '-')
                        ], className="small mb-2"),'''

content = content.replace(old_info_card, new_info_card)

# Add cache_info call after news_articles
old_try_block = '''    try:
        # Get available stocks
        stocks = get_available_stocks()

        # Fetch news for selected stock
        news_articles = get_news_with_sentiment(stock_code, max_results=15)

        # Get latest news across all stocks
        latest_all = get_latest_news_summary(stocks[:10], max_total=5)

    except Exception as e:
        news_articles = []
        latest_all = []
        print(f"Error loading news: {e}")'''

new_try_block = '''    try:
        # Get available stocks
        stocks = get_available_stocks()

        # Fetch news for selected stock
        news_articles = get_news_with_sentiment(stock_code, max_results=15)

        # Get latest news across all stocks (only from cache)
        latest_all = get_latest_news_summary(stocks[:10], max_total=5)

        # Get cache info
        cache_info = get_cache_info(stock_code)

    except Exception as e:
        news_articles = []
        latest_all = []
        cache_info = {'refresh_mode': '-', 'interval_hours': 2, 'cached_stocks': 0, 'last_refresh': '-'}
        print(f"Error loading news: {e}")'''

content = content.replace(old_try_block, new_try_block)

with open('dashboard/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("App.py updated with cache info!")
