"""
Stock Analysis Dashboard - Multi-Emiten Support
Dynamic analysis with file upload capability
"""
import sys
import os
import base64
import io

# Add app and dashboard directories to path
app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
dashboard_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)
sys.path.insert(0, dashboard_dir)

import dash
from dash import dcc, html, dash_table, callback, Input, Output, State, no_update, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from database import execute_query, get_cursor, clear_cache, clear_stock_cache, get_cache_stats, preload_stock_data
from zones_config import STOCK_ZONES, get_zones
try:
    from backtest_v11_universal import run_backtest as run_v11b1_backtest
except ImportError:
    run_v11b1_backtest = None

def get_v10_open_position(stock_code):
    """Get current open V11b1 position if any"""
    if not run_v11b1_backtest or not get_zones(stock_code):
        return None
    try:
        result = run_v11b1_backtest(stock_code)
        if result and result.get('trades'):
            # Find open position
            for trade in result['trades']:
                if trade.get('exit_reason') == 'OPEN':
                    return {
                        'type': trade.get('type', 'UNKNOWN'),
                        'entry_date': trade.get('entry_date', ''),
                        'entry_price': trade.get('entry_price', 0),
                        'sl': trade.get('sl', 0),
                        'tp': trade.get('tp', 0),
                        'zone_num': trade.get('zone_num', 0),
                        'current_pnl': trade.get('pnl', 0),
                        'entry_conditions': trade.get('entry_conditions'),  # V10 checklist at entry
                        'vol_ratio': trade.get('vol_ratio', 0),  # V11b1: volume ratio at entry
                    }
        return None
    except Exception:
        return None

# Cache for V10 running stocks (to avoid repeated backtests)
_v10_running_cache = {}
_v10_cache_time = None

def get_all_v10_running_stocks():
    """Get all stocks with V10 running positions (cached for 5 minutes)
    Returns dict with stock_code -> position data (entry_price, current_pnl, etc.)
    """
    global _v10_running_cache, _v10_cache_time
    from datetime import datetime, timedelta

    # Check cache validity (5 minutes)
    if _v10_cache_time and datetime.now() - _v10_cache_time < timedelta(minutes=5):
        return _v10_running_cache

    # Rebuild cache
    _v10_running_cache = {}
    if run_v11b1_backtest:
        for stock_code in STOCK_ZONES.keys():
            try:
                result = run_v11b1_backtest(stock_code)
                if result and result.get('trades'):
                    for trade in result['trades']:
                        if trade.get('exit_reason') == 'OPEN':
                            _v10_running_cache[stock_code] = {
                                'entry_price': trade.get('entry_price', 0),
                                'current_pnl': trade.get('pnl', 0),
                                'type': trade.get('type', ''),
                                'zone_num': trade.get('zone_num', 0),
                                'entry_date': trade.get('entry_date', ''),
                            }
                            break
            except:
                pass
    _v10_cache_time = datetime.now()
    return _v10_running_cache
from analyzer import (
    get_price_data, get_broker_data, run_full_analysis,
    get_top_accumulators, get_top_distributors,
    find_current_market_phase, check_accumulation_alerts,
    analyze_broker_accumulation, analyze_broker_price_correlation,
    calculate_optimal_lookback_days, get_bandarmology_summary,
    calculate_broker_consistency_score
)
from composite_analyzer import (
    calculate_broker_sensitivity_advanced,
    calculate_foreign_flow_momentum,
    calculate_smart_money_indicator,
    calculate_price_position,
    detect_accumulation_phase,
    calculate_composite_score,
    generate_alerts,
    get_comprehensive_analysis,
    get_broker_avg_buy,
    analyze_avg_buy_position,
    track_buy_signal,
    clear_analysis_cache,
    get_multi_period_summary,
    calculate_price_movements,
    calculate_foreign_flow_by_period,
    calculate_sensitive_broker_flow_by_period,
    analyze_support_resistance
)
from broker_config import (
    get_broker_type, get_broker_color, get_broker_info,
    classify_brokers, BROKER_COLORS, BROKER_TYPE_NAMES,
    FOREIGN_BROKER_CODES, is_foreign_broker
)
from parser import read_excel_data, import_price_data, import_broker_data, read_profile_data, import_profile_data, read_fundamental_data, import_fundamental_data
from signal_validation import (
    get_comprehensive_validation, get_company_profile, get_daily_flow_timeline,
    get_market_status, get_risk_events, get_all_broker_details, DEFAULT_PARAMS,
    get_unified_analysis_summary, calculate_volume_price_multi_horizon
)
from decision_panel import create_decision_panel, create_why_signal_checklist

# V6 Sideways Analyzer - Adaptive Threshold + Accumulation/Distribution
try:
    from sideways_v6_analyzer import get_v6_analysis, has_custom_formula
    print('sideways_v6_analyzer loaded OK')
except Exception as e:
    print(f'Warning: sideways_v6_analyzer error - {e}')
    def get_v6_analysis(stock_code, conn=None): return {'error': 'Module not loaded'}
    def has_custom_formula(stock_code): return False

# Signal History for custom formula stocks (PANI, BREN, MBMA)
try:
    from signal_history_sr import get_signal_history_sr, get_current_strong_sr, get_signal_history_auto, get_signal_history_v9
    print('signal_history_sr loaded OK')
except Exception as e:
    print(f'Warning: signal_history_sr error - {e}')
    def get_signal_history_sr(stock_code, start_date='2025-01-02'): return {'error': 'Module not loaded', 'signals': []}
    def get_current_strong_sr(stock_code): return None
    def get_signal_history_auto(stock_code, start_date='2025-01-02'): return get_signal_history_sr(stock_code, start_date)
    def get_signal_history_v9(stock_code, start_date='2025-01-02'): return {'error': 'Module not loaded', 'signals': []}

# Strong S/R Analyzer V8 for PTRO, CBDK, BREN, BRPT, CDIA (ATR-Quality based)
try:
    from strong_sr_v8_atr import get_strong_sr_analysis
    print('strong_sr_v8_atr loaded OK')
except Exception as e:
    print(f'Warning: strong_sr_v8_atr error - {e}')
    def get_strong_sr_analysis(stock_code): return {'error': 'Module not loaded'}

# News service for stock news
try:
    from news_service import get_news_with_sentiment, get_all_stocks_news, get_latest_news_summary, get_cache_info
    print('news_service loaded OK')
except Exception as e:
    print(f'Warning: news_service error - {e}')
    def get_news_with_sentiment(stock_code, max_results=5): return []
    def get_all_stocks_news(codes, max_per=3): return {}
    def get_latest_news_summary(codes, max_total=10): return []
    def get_cache_info(stock_code=None): return {'refresh_mode': '-', 'interval_hours': 2, 'cached_stocks': 0, 'last_refresh': '-'}

# Helper function to create colored broker code span
def colored_broker(broker_code: str, show_type: bool = False, with_badge: bool = False) -> html.Span:
    """Create a colored broker code span based on broker type.

    Args:
        broker_code: The broker code (e.g., 'AK', 'CC')
        show_type: If True, add superscript with type initial (F/B/L)
        with_badge: If True, add background color based on broker role
    """
    broker_type = get_broker_type(broker_code)
    broker_color = BROKER_COLORS.get(broker_type, BROKER_COLORS['LOCAL'])

    if with_badge:
        # Use CSS classes for badge - ensures proper override in light mode
        badge_class = f"broker-badge broker-badge-{broker_type.lower()}"
        if show_type:
            type_short = {'FOREIGN': 'F', 'BUMN': 'B', 'LOCAL': 'L'}.get(broker_type, 'L')
            return html.Span([
                html.Span(broker_code, className=badge_class),
                html.Sup(type_short, style={"fontSize": "8px", "marginLeft": "2px", "color": broker_color})
            ])
        return html.Span(broker_code, className=badge_class)
    else:
        # Regular colored text (no badge)
        broker_class = f"broker-{broker_type.lower()}"
        if show_type:
            type_short = {'FOREIGN': 'F', 'BUMN': 'B', 'LOCAL': 'L'}.get(broker_type, 'L')
            return html.Span([
                html.Span(broker_code, className=broker_class),
                html.Sup(type_short, className=broker_class, style={"fontSize": "8px", "marginLeft": "1px"})
            ])
        return html.Span(broker_code, className=broker_class)


# ============================================================
# TOOLTIP DEFINITIONS - Edukasi user dengan penjelasan singkat
# ============================================================
TERM_DEFINITIONS = {
    # Broker & Flow Terms
    'broker_sensitivity': 'Skor seberapa sering broker tertentu berhasil memprediksi pergerakan harga. Broker dengan sensitivity tinggi = "smart money".',
    'foreign_flow': 'Aliran dana investor asing (net buy - net sell). Positif = asing masuk (bullish), Negatif = asing keluar (bearish).',
    'net_flow': 'Selisih antara nilai beli dan jual. Positif = lebih banyak beli, Negatif = lebih banyak jual.',
    'net_lot': 'Selisih lot beli dan lot jual suatu broker dalam periode tertentu.',

    # Analysis Terms
    'cpr': 'Close Position Ratio - posisi harga penutupan dalam range harian. >60% = pembeli dominan, <40% = penjual dominan.',
    'accumulation': 'Fase di mana pelaku besar mengumpulkan saham secara bertahap sebelum harga naik.',
    'distribution': 'Fase di mana pelaku besar melepas saham secara bertahap sebelum harga turun.',
    'markup': 'Fase kenaikan harga setelah akumulasi selesai.',

    # Validation Terms
    'uvdv_ratio': 'Up Volume vs Down Volume - perbandingan volume saat harga naik vs turun.',
    'persistence': 'Konsistensi broker dalam membeli/menjual berturut-turut. >=5 hari = niat serius.',
    'elasticity': 'Hubungan antara perubahan volume dan perubahan harga. Volume^ + Harga stabil = absorpsi.',
    'rotation': 'Jumlah broker yang selaras (sama-sama beli atau jual).',

    # Price Terms
    'support': 'Level harga di mana tekanan beli cukup kuat untuk menahan penurunan.',
    'resistance': 'Level harga di mana tekanan jual cukup kuat untuk menahan kenaikan.',
    'entry_zone': 'Area harga ideal untuk masuk posisi (biasanya lower 40% dari range).',
    'invalidation': 'Level harga yang jika ditembus, sinyal dianggap gagal. Tutup posisi jika tembus.',

    # Fundamental Terms
    'per': 'Price to Earning Ratio - harga saham dibagi laba per saham. <15 = murah, >25 = mahal.',
    'pbv': 'Price to Book Value - harga saham dibagi nilai buku. <1 = di bawah nilai aset.',
    'roe': 'Return on Equity - laba bersih dibagi ekuitas. Semakin tinggi semakin efisien.',
    'npm': 'Net Profit Margin - laba bersih dibagi pendapatan. Ukuran profitabilitas.',

    # Decision Terms
    'confidence': 'Tingkat keyakinan sinyal berdasarkan jumlah validasi yang lolos (0-6 kriteria).',
    'decision_rule': 'Rekomendasi aksi berdasarkan gabungan semua analisis: WAIT/ENTRY/ADD/HOLD/EXIT.',

    # Volume Terms
    'rvol': 'Relative Volume - volume hari ini dibanding rata-rata. >1.5x = volume tinggi.',
    'volume_absorption': 'Volume tinggi tanpa pergerakan harga signifikan = ada yang menyerap.',

    # Momentum/Impulse Terms (NEW)
    'impulse': 'Pergerakan harga agresif tanpa fase akumulasi. Volume spike + breakout + CPR tinggi. Risiko tinggi.',
    'momentum': 'Kecepatan pergerakan harga. Momentum tinggi = harga bergerak cepat dalam satu arah.',
    'breakout': 'Harga menembus level resistance (naik) atau support (turun) dengan volume tinggi.',
    'volume_spike': 'Lonjakan volume signifikan (>2x rata-rata). Bisa indikasi pergerakan besar akan terjadi.',
    'near_impulse': 'Hampir memenuhi kriteria impulse (2 dari 3 kondisi). Pantau untuk konfirmasi.',

    # Signal Driver Terms (Primary Metrics)
    'market_phase': 'Fase pasar saat ini: AKUMULASI (beli bertahap), MARKUP (naik), DISTRIBUSI (jual bertahap), SIDEWAYS (belum ada arah).',
    'accum_phase': 'Fase akumulasi aktif = harga sideways dalam range sempit, menandakan pelaku besar sedang mengumpulkan saham.',
    'smart_money': 'Skor deteksi aktivitas "uang pintar" (institusi/bandar). >60 = ada akumulasi besar terdeteksi.',

    # Sentiment Terms
    'accum_ratio': 'Perbandingan total pembelian vs penjualan semua broker hari ini. >55% Buy = sentiment beli kuat.',
    'foreign_streak': 'Jumlah hari berturut-turut investor asing konsisten beli/jual. Streak panjang = trend kuat dan terarah.',
}

def with_tooltip(text: str, term_key: str, placement: str = 'top') -> html.Span:
    """
    Wrap text dengan tooltip penjelasan.

    Args:
        text: Teks yang ditampilkan
        term_key: Key dari TERM_DEFINITIONS
        placement: Posisi tooltip (top/bottom/left/right)

    Returns:
        html.Span dengan tooltip
    """
    definition = TERM_DEFINITIONS.get(term_key, '')
    if not definition:
        return html.Span(text)

    return html.Span([
        html.Span(
            text,
            style={
                'borderBottom': '1px dotted #6c757d',
                'cursor': 'help'
            },
            title=definition
        ),
        html.I(className="fas fa-info-circle ms-1", style={'fontSize': '10px', 'color': '#6c757d', 'cursor': 'help'}, title=definition)
    ])

def tooltip_badge(text: str, term_key: str, color: str = 'secondary') -> dbc.Badge:
    """
    Create a badge with tooltip.
    """
    definition = TERM_DEFINITIONS.get(term_key, '')
    return dbc.Badge(
        text,
        color=color,
        className="me-1",
        style={'cursor': 'help'},
        title=definition
    )


# ============================================================
# SKELETON LOADING COMPONENTS - Tampilan saat loading data
# ============================================================
def create_skeleton_card(title: str = "Loading...", rows: int = 3, height: str = "auto") -> dbc.Card:
    """
    Create a skeleton loading card with animated placeholders.

    Args:
        title: Card title
        rows: Number of skeleton rows to show
        height: Card height

    Returns:
        dbc.Card with skeleton animation
    """
    skeleton_rows = []
    widths = ["85%", "70%", "60%", "90%", "75%"]

    for i in range(rows):
        width = widths[i % len(widths)]
        skeleton_rows.append(
            html.Div(
                className="skeleton-line mb-2",
                style={
                    "width": width,
                    "height": "16px",
                    "backgroundColor": "rgba(255,255,255,0.1)",
                    "borderRadius": "4px",
                    "animation": "skeleton-pulse 1.5s ease-in-out infinite"
                }
            )
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div(
                className="skeleton-line",
                style={
                    "width": "40%",
                    "height": "20px",
                    "backgroundColor": "rgba(255,255,255,0.1)",
                    "borderRadius": "4px",
                    "animation": "skeleton-pulse 1.5s ease-in-out infinite"
                }
            )
        ]),
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-spinner fa-spin me-2 text-info"),
                html.Span(title, className="text-muted")
            ], className="text-center mb-3"),
            *skeleton_rows
        ])
    ], className="mb-3", color="dark", style={"height": height} if height != "auto" else {})


def create_skeleton_metrics() -> html.Div:
    """Create skeleton loading for metrics cards."""
    return dbc.Row([
        dbc.Col([
            html.Div([
                html.Div(className="skeleton-line mb-1", style={"width": "60%", "height": "12px", "backgroundColor": "rgba(255,255,255,0.1)", "borderRadius": "4px", "animation": "skeleton-pulse 1.5s ease-in-out infinite"}),
                html.Div(className="skeleton-line mb-1", style={"width": "40%", "height": "24px", "backgroundColor": "rgba(255,255,255,0.15)", "borderRadius": "4px", "animation": "skeleton-pulse 1.5s ease-in-out infinite"}),
                html.Div(className="skeleton-line", style={"width": "80%", "height": "10px", "backgroundColor": "rgba(255,255,255,0.08)", "borderRadius": "4px", "animation": "skeleton-pulse 1.5s ease-in-out infinite"}),
            ], className="text-center p-2")
        ], width=4) for _ in range(3)
    ], className="mb-2")


# CSS untuk skeleton animation (akan diinjeksi ke halaman)
SKELETON_CSS = """
@keyframes skeleton-pulse {
    0% { opacity: 0.4; }
    50% { opacity: 0.7; }
    100% { opacity: 0.4; }
}
.skeleton-line {
    background: linear-gradient(90deg, rgba(255,255,255,0.1) 25%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.1) 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.5s infinite;
}
@keyframes skeleton-shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes v10-blink {
    0%, 100% { opacity: 1; text-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00; }
    50% { opacity: 0.7; text-shadow: 0 0 20px #00ff00, 0 0 30px #00ff00, 0 0 40px #00ff00; }
}
.v10-running, .v10-running h3, .v10-running * {
    animation: v10-blink 1.5s ease-in-out infinite !important;
    color: #00ff00 !important;
}
.v10-running:hover, .v10-running:hover h3 {
    color: #00ff00 !important;
    text-decoration: none !important;
}
a.v10-running, a .v10-running {
    color: #00ff00 !important;
}
"""


def create_submenu_nav(current_page: str, stock_code: str = 'CDIA') -> html.Div:
    """
    Create consistent submenu navigation buttons for Analysis subpages.
    Order: Fundamental | Support & Resistance | Accumulation
    All buttons use solid colors for consistency with Analysis page.

    Args:
        current_page: Current page identifier ('fundamental', 'support-resistance', 'accumulation', 'analysis')
        stock_code: Current stock code
    """
    # Fundamental button - always solid green
    fundamental_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-chart-line me-2"),
            "Fundamental"
        ], color="success", size="sm", className="me-2"),
        href="/fundamental"
    )

    # Support & Resistance button - always solid teal/info
    sr_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-layer-group me-2"),
            "Support & Resistance"
        ], color="info", size="sm", className="me-2"),
        href="/support-resistance"
    )

    # Accumulation button - always solid orange/warning
    accum_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-cubes me-2"),
            "Accumulation"
        ], color="warning", size="sm", className="me-2"),
        href="/accumulation"
    )

    # Only show Analysis button if not on analysis page
    if current_page != 'analysis':
        analysis_btn = dcc.Link(
            dbc.Button([
                html.I(className="fas fa-arrow-left me-2"),
                "Analysis"
            ], color="primary", size="sm"),
            href="/analysis"
        )
        return html.Div([fundamental_btn, sr_btn, accum_btn, analysis_btn], className="d-inline-flex flex-wrap")

    return html.Div([fundamental_btn, sr_btn, accum_btn], className="d-inline-flex flex-wrap")


def create_dashboard_submenu_nav(current_page: str, stock_code: str = 'CDIA') -> html.Div:
    """
    Create consistent submenu navigation buttons for Dashboard subpages.
    Order: Profile | Broker Movement | Sensitive Broker | Position
    All buttons use solid colors matching Analysis submenu style.

    Args:
        current_page: Current page identifier ('profile', 'movement', 'sensitive', 'position', 'dashboard')
        stock_code: Current stock code
    """
    # Profile button - solid green
    profile_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-building me-2"),
            "Profile"
        ], color="success", size="sm", className="me-2 mb-1"),
        href="/profile"
    )

    # Broker Movement button - solid info/teal
    movement_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-exchange-alt me-2"),
            "Broker Movement"
        ], color="info", size="sm", className="me-2 mb-1"),
        href="/movement"
    )

    # Sensitive Broker button - solid info/cyan
    sensitive_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-crosshairs me-2"),
            "Sensitive Broker"
        ], color="info", size="sm", className="me-2 mb-1"),
        href="/sensitive"
    )

    # Position button - solid info
    position_btn = dcc.Link(
        dbc.Button([
            html.I(className="fas fa-chart-pie me-2"),
            "Position"
        ], color="info", size="sm", className="me-2 mb-1"),
        href="/position"
    )

    # Only show Dashboard button if not on dashboard page
    if current_page != 'dashboard':
        dashboard_btn = dcc.Link(
            dbc.Button([
                html.I(className="fas fa-arrow-left me-2"),
                "Dashboard"
            ], color="primary", size="sm", className="mb-1"),
            href="/dashboard"
        )
        return html.Div([profile_btn, movement_btn, sensitive_btn, position_btn, dashboard_btn], className="d-inline-flex flex-wrap")

    return html.Div([profile_btn, movement_btn, sensitive_btn, position_btn], className="d-inline-flex flex-wrap")


# Initialize Dash app with Font Awesome for help icons
FA_CSS = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"

# PWA Meta Tags for mobile optimization
PWA_META_TAGS = [
    # Viewport for responsive design
    {"name": "viewport", "content": "width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes, viewport-fit=cover"},
    {"http-equiv": "X-UA-Compatible", "content": "IE=edge"},
    # PWA specific
    {"name": "mobile-web-app-capable", "content": "yes"},
    {"name": "apple-mobile-web-app-capable", "content": "yes"},
    {"name": "apple-mobile-web-app-status-bar-style", "content": "black-translucent"},
    {"name": "apple-mobile-web-app-title", "content": "StockAnalysis"},
    # Theme colors
    {"name": "theme-color", "content": "#0f3460"},
    {"name": "msapplication-TileColor", "content": "#0f3460"},
    {"name": "msapplication-navbutton-color", "content": "#0f3460"},
    # Description
    {"name": "description", "content": "Dashboard analisis broker saham dengan Bandarmology"},
    {"name": "author", "content": "Stock Analysis Team"},
]

# Custom index string for PWA with manifest and service worker
PWA_INDEX_STRING = '''
<!DOCTYPE html>
<html lang="id">
    <head>
        {%metas%}
        <title>{%title%}</title>
        <!-- Google Analytics GA4 -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-JJ1WVNZLZE"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-JJ1WVNZLZE');
        </script>
        <!-- PWA Manifest -->
        <link rel="manifest" href="/assets/manifest.json">
        <!-- Apple Touch Icons -->
        <link rel="apple-touch-icon" sizes="192x192" href="/assets/icon-192.png">
        <link rel="apple-touch-icon" sizes="512x512" href="/assets/icon-512.png">
        <!-- Favicon -->
        <link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
        {%favicon%}
        {%css%}
        <!-- Splash screen for iOS -->
        <meta name="apple-mobile-web-app-title" content="StockAnalysis">
        <style>
            /* Critical CSS for fast first paint */
            body {
                background-color: #1a1a2e;
                color: #e8e8e8;
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            /* Loading placeholder */
            #_dash-loading {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                flex-direction: column;
            }
            #_dash-loading::after {
                content: 'Loading Stock Analysis...';
                color: #17a2b8;
                font-size: 1.2rem;
                margin-top: 1rem;
            }
            .loading-spinner {
                width: 50px;
                height: 50px;
                border: 4px solid #16213e;
                border-top: 4px solid #17a2b8;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            /* Light mode overrides */
            body.light-mode {
                background-color: #f8f9fa !important;
                color: #212529 !important;
            }
            body.light-mode .card {
                background-color: #ffffff !important;
                color: #212529 !important;
            }
            body.light-mode .navbar {
                background-color: #e9ecef !important;
            }
            body.light-mode .alert-secondary {
                background-color: #e9ecef !important;
                color: #212529 !important;
                border-color: #dee2e6 !important;
            }
            body.light-mode .text-muted {
                color: #6c757d !important;
            }
            body.light-mode .form-control,
            body.light-mode .form-select {
                background-color: #ffffff !important;
                color: #212529 !important;
                border-color: #ced4da !important;
            }
            body.light-mode .dropdown-menu {
                background-color: #ffffff !important;
            }
            body.light-mode .dropdown-item {
                color: #212529 !important;
            }
            body.light-mode .dropdown-item:hover {
                background-color: #e9ecef !important;
            }

            /* Forum Mobile Responsive */
            .forum-content,
            pre.forum-content {
                word-wrap: break-word !important;
                overflow-wrap: break-word !important;
                word-break: break-word !important;
                white-space: pre-wrap !important;
                max-width: 100% !important;
                font-family: inherit !important;
                background: transparent !important;
                border: none !important;
                padding: 0 !important;
                margin: 0 !important;
            }

            /* Mobile breakpoint */
            @media (max-width: 768px) {
                .card-body {
                    padding: 0.75rem !important;
                }
                .card-title {
                    font-size: 1rem !important;
                }
                .forum-content,
                pre.forum-content {
                    font-size: 0.85rem !important;
                    line-height: 1.5 !important;
                    white-space: pre-wrap !important;
                }
                /* Better badge sizing on mobile */
                .badge {
                    font-size: 0.65rem !important;
                    padding: 0.25rem 0.4rem !important;
                }
                /* Smaller buttons on mobile */
                .btn-sm {
                    font-size: 0.75rem !important;
                    padding: 0.2rem 0.4rem !important;
                }
                /* Thread card adjustments */
                .thread-meta {
                    font-size: 0.7rem !important;
                }
                /* Hide some elements on mobile for cleaner look */
                .d-none-mobile {
                    display: none !important;
                }
            }

            /* Extra small screens */
            @media (max-width: 480px) {
                .card-body {
                    padding: 0.5rem !important;
                }
                .forum-content,
                pre.forum-content {
                    font-size: 0.8rem !important;
                    white-space: pre-wrap !important;
                }
                h4, .h4 {
                    font-size: 1.1rem !important;
                }
                h5, .h5 {
                    font-size: 1rem !important;
                }
                h6, .h6 {
                    font-size: 0.9rem !important;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <!-- Service Worker Registration -->
        <script>
            if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                    navigator.serviceWorker.register('/assets/service-worker.js')
                        .then(function(registration) {
                            console.log('ServiceWorker registered:', registration.scope);
                        })
                        .catch(function(error) {
                            console.log('ServiceWorker registration failed:', error);
                        });
                });
            }

            // Handle PWA install prompt
            let deferredPrompt;
            window.addEventListener('beforeinstallprompt', (e) => {
                e.preventDefault();
                deferredPrompt = e;
                console.log('PWA install prompt available');
            });

            // Detect standalone mode
            if (window.matchMedia('(display-mode: standalone)').matches ||
                window.navigator.standalone === true) {
                console.log('Running as PWA');
                document.body.classList.add('pwa-mode');
            }
        </script>
    </body>
</html>
'''

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, FA_CSS],
    suppress_callback_exceptions=True,
    compress=True,  # Enable response compression
    meta_tags=PWA_META_TAGS,
    index_string=PWA_INDEX_STRING,
    # Assets folder for manifest, icons, css
    assets_folder='assets',
    # Exclude service-worker.js from being loaded as regular script
    assets_ignore='service-worker.*'
)
app.title = "Stock Broker Analysis"
server = app.server

# Enable Gzip compression for all responses
try:
    from flask_compress import Compress
    Compress(server)
    print("Flask-Compress enabled")
except ImportError:
    print("Flask-Compress not available, skipping compression")

# Configure server for better performance
server.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'text/xml', 'application/json',
    'application/javascript', 'text/javascript'
]
server.config['COMPRESS_LEVEL'] = 6
server.config['COMPRESS_MIN_SIZE'] = 500

# Flask route for PDF download from forum
from flask import Response, send_file
@server.route('/download-pdf/<int:thread_id>')
def download_thread_pdf(thread_id):
    """Download PDF attachment from a forum thread"""
    try:
        query = "SELECT pdf_data, pdf_filename FROM forum_threads WHERE id = %s"
        result = execute_query(query, (thread_id,))
        if result and result[0].get('pdf_data'):
            pdf_data = result[0]['pdf_data']
            filename = result[0].get('pdf_filename', f'attachment_{thread_id}.pdf')
            # Handle bytea/memoryview from PostgreSQL
            if isinstance(pdf_data, memoryview):
                pdf_data = bytes(pdf_data)
            return Response(
                pdf_data,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
        return "PDF not found", 404
    except Exception as e:
        return f"Error: {str(e)}", 500

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_value(val):
    """Format large numbers to readable format"""
    if pd.isna(val) or val == 0:
        return "0"
    if abs(val) >= 1e12:
        return f"{val/1e12:.1f}T"
    elif abs(val) >= 1e9:
        return f"{val/1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"{val/1e6:.1f}M"
    elif abs(val) >= 1e3:
        return f"{val/1e3:.1f}K"
    return f"{val:.0f}"

def get_available_stocks():
    """Get list of stocks available in database (no cache for fresh data)"""
    query = "SELECT DISTINCT stock_code FROM stock_daily ORDER BY stock_code"
    results = execute_query(query, use_cache=False)  # No cache to always get fresh list
    if results:
        return [r['stock_code'] for r in results]
    return ['CDIA']  # Default


# ============================================================
# BROKER POSITION ANALYSIS (IPO + Daily)
# ============================================================

def get_ipo_position(stock_code: str) -> pd.DataFrame:
    """Get IPO position data from database"""
    query = """
        SELECT broker_code, total_buy_value, total_buy_lot, avg_buy_price,
               total_sell_value, total_sell_lot, avg_sell_price,
               period_start, period_end
        FROM broker_ipo_position
        WHERE stock_code = %s
        ORDER BY total_buy_lot DESC
    """
    results = execute_query(query, (stock_code,))
    if results:
        return pd.DataFrame(results)
    return pd.DataFrame()


def get_daily_activity_after_ipo(stock_code: str, ipo_end_date) -> pd.DataFrame:
    """Get daily broker activity after IPO period end"""
    if ipo_end_date is None:
        return pd.DataFrame()

    query = """
        SELECT broker_code,
               SUM(buy_value) as daily_buy_value,
               SUM(buy_lot) as daily_buy_lot,
               SUM(sell_value) as daily_sell_value,
               SUM(sell_lot) as daily_sell_lot,
               CASE WHEN SUM(buy_lot) > 0
                    THEN SUM(buy_lot * buy_avg) / SUM(buy_lot)
                    ELSE 0 END as daily_buy_avg
        FROM broker_summary
        WHERE stock_code = %s AND date > %s
        GROUP BY broker_code
    """
    results = execute_query(query, (stock_code, ipo_end_date))
    if results:
        return pd.DataFrame(results)
    return pd.DataFrame()


def calculate_broker_current_position(stock_code: str) -> pd.DataFrame:
    """
    Calculate current broker position:
    Current Position = IPO Position + Daily Activity (after IPO period)

    Returns DataFrame with:
    - broker_code
    - ipo_buy_lot, ipo_sell_lot, ipo_avg_buy
    - daily_buy_lot, daily_sell_lot
    - current_net_lot (total position)
    - weighted_avg_buy
    - floating_pnl (based on current price)
    """
    # Get IPO position
    ipo_df = get_ipo_position(stock_code)
    if ipo_df.empty:
        return pd.DataFrame()

    # Get IPO period end date
    ipo_end_date = ipo_df['period_end'].iloc[0] if 'period_end' in ipo_df.columns else None

    # Get daily activity after IPO
    daily_df = get_daily_activity_after_ipo(stock_code, ipo_end_date)

    # Get current price
    price_df = get_price_data(stock_code)
    current_price = price_df['close_price'].iloc[-1] if not price_df.empty and 'close_price' in price_df.columns else 0

    # Merge IPO and daily data
    position_data = []

    for _, ipo_row in ipo_df.iterrows():
        broker = ipo_row['broker_code']

        # IPO data
        ipo_buy_lot = int(ipo_row['total_buy_lot']) if pd.notna(ipo_row['total_buy_lot']) else 0
        ipo_sell_lot = int(ipo_row['total_sell_lot']) if pd.notna(ipo_row['total_sell_lot']) else 0
        ipo_avg_buy = float(ipo_row['avg_buy_price']) if pd.notna(ipo_row['avg_buy_price']) else 0
        ipo_buy_value = float(ipo_row['total_buy_value']) if pd.notna(ipo_row['total_buy_value']) else 0

        # Daily data (after IPO)
        daily_buy_lot = 0
        daily_sell_lot = 0
        daily_buy_value = 0

        if not daily_df.empty:
            daily_row = daily_df[daily_df['broker_code'] == broker]
            if not daily_row.empty:
                daily_buy_lot = int(daily_row['daily_buy_lot'].iloc[0]) if pd.notna(daily_row['daily_buy_lot'].iloc[0]) else 0
                daily_sell_lot = int(daily_row['daily_sell_lot'].iloc[0]) if pd.notna(daily_row['daily_sell_lot'].iloc[0]) else 0
                daily_buy_value = float(daily_row['daily_buy_value'].iloc[0]) if pd.notna(daily_row['daily_buy_value'].iloc[0]) else 0

        # Calculate totals
        total_buy_lot = ipo_buy_lot + daily_buy_lot
        total_sell_lot = ipo_sell_lot + daily_sell_lot
        net_lot = total_buy_lot - total_sell_lot

        # Weighted average buy price - use IPO avg directly (more reliable)
        # Value/lot calculation doesn't work because value is in Rupiah, lot is in lots (not shares)
        weighted_avg_buy = ipo_avg_buy if ipo_avg_buy > 0 else 0

        # Floating P&L
        if net_lot > 0 and weighted_avg_buy > 0 and current_price > 0:
            floating_pnl_pct = ((current_price - weighted_avg_buy) / weighted_avg_buy) * 100
            floating_pnl_value = (current_price - weighted_avg_buy) * net_lot
        else:
            floating_pnl_pct = 0
            floating_pnl_value = 0

        position_data.append({
            'broker_code': broker,
            'ipo_buy_lot': ipo_buy_lot,
            'ipo_sell_lot': ipo_sell_lot,
            'ipo_avg_buy': ipo_avg_buy,
            'daily_buy_lot': daily_buy_lot,
            'daily_sell_lot': daily_sell_lot,
            'total_buy_lot': total_buy_lot,
            'total_sell_lot': total_sell_lot,
            'net_lot': net_lot,
            'weighted_avg_buy': weighted_avg_buy,
            'current_price': current_price,
            'floating_pnl_pct': floating_pnl_pct,
            'floating_pnl_value': floating_pnl_value
        })

    # Add brokers that only appear in daily (not in IPO)
    if not daily_df.empty:
        existing_brokers = set(ipo_df['broker_code'].tolist())
        for _, daily_row in daily_df.iterrows():
            broker = daily_row['broker_code']
            if broker not in existing_brokers:
                daily_buy_lot = int(daily_row['daily_buy_lot']) if pd.notna(daily_row['daily_buy_lot']) else 0
                daily_sell_lot = int(daily_row['daily_sell_lot']) if pd.notna(daily_row['daily_sell_lot']) else 0
                daily_buy_avg = float(daily_row['daily_buy_avg']) if 'daily_buy_avg' in daily_row and pd.notna(daily_row['daily_buy_avg']) else 0
                net_lot = daily_buy_lot - daily_sell_lot
                # Use daily_buy_avg if available, otherwise estimate from current price
                weighted_avg_buy = daily_buy_avg if daily_buy_avg > 0 else current_price

                if net_lot != 0:
                    if net_lot > 0 and weighted_avg_buy > 0 and current_price > 0:
                        floating_pnl_pct = ((current_price - weighted_avg_buy) / weighted_avg_buy) * 100
                        floating_pnl_value = (current_price - weighted_avg_buy) * net_lot
                    else:
                        floating_pnl_pct = 0
                        floating_pnl_value = 0

                    position_data.append({
                        'broker_code': broker,
                        'ipo_buy_lot': 0,
                        'ipo_sell_lot': 0,
                        'ipo_avg_buy': 0,
                        'daily_buy_lot': daily_buy_lot,
                        'daily_sell_lot': daily_sell_lot,
                        'total_buy_lot': daily_buy_lot,
                        'total_sell_lot': daily_sell_lot,
                        'net_lot': net_lot,
                        'weighted_avg_buy': weighted_avg_buy,
                        'current_price': current_price,
                        'floating_pnl_pct': floating_pnl_pct,
                        'floating_pnl_value': floating_pnl_value
                    })

    return pd.DataFrame(position_data)


def calculate_broker_position_from_daily(stock_code: str, days: int = 90) -> pd.DataFrame:
    """
    Calculate broker position from daily broker_summary data only.
    Used when IPO data is not available.

    Returns DataFrame with broker positions based on net accumulation over the period.
    """
    # Get current price
    price_df = get_price_data(stock_code)
    current_price = price_df['close_price'].iloc[-1] if not price_df.empty and 'close_price' in price_df.columns else 0

    # Query broker summary data
    # Note: buy_value is in Rupiah, buy_lot is in lots (100 shares)
    # weighted_avg_buy = buy_value / buy_lot / 100 = price per share
    query = """
        SELECT
            broker_code,
            SUM(buy_lot) as total_buy_lot,
            SUM(sell_lot) as total_sell_lot,
            SUM(buy_value) as total_buy_value,
            SUM(sell_value) as total_sell_value,
            SUM(net_lot) as net_lot,
            CASE WHEN SUM(buy_lot) > 0
                 THEN SUM(buy_value) / SUM(buy_lot) / 100
                 ELSE 0 END as weighted_avg_buy,
            COUNT(DISTINCT date) as active_days,
            MIN(date) as first_date,
            MAX(date) as last_date
        FROM broker_summary
        WHERE stock_code = %s
        AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY broker_code
        HAVING SUM(net_lot) != 0
        ORDER BY SUM(net_lot) DESC
    """
    results = execute_query(query, (stock_code, days))

    if not results:
        return pd.DataFrame()

    position_data = []
    for row in results:
        broker = row['broker_code']
        net_lot = int(row['net_lot']) if row['net_lot'] else 0
        total_buy_lot = int(row['total_buy_lot']) if row['total_buy_lot'] else 0
        total_sell_lot = int(row['total_sell_lot']) if row['total_sell_lot'] else 0
        weighted_avg_buy = float(row['weighted_avg_buy']) if row['weighted_avg_buy'] else current_price

        # Calculate floating P&L
        if net_lot > 0 and weighted_avg_buy > 0 and current_price > 0:
            floating_pnl_pct = ((current_price - weighted_avg_buy) / weighted_avg_buy) * 100
            floating_pnl_value = (current_price - weighted_avg_buy) * net_lot
        else:
            floating_pnl_pct = 0
            floating_pnl_value = 0

        position_data.append({
            'broker_code': broker,
            'ipo_buy_lot': 0,
            'ipo_sell_lot': 0,
            'ipo_avg_buy': 0,
            'daily_buy_lot': total_buy_lot,
            'daily_sell_lot': total_sell_lot,
            'total_buy_lot': total_buy_lot,
            'total_sell_lot': total_sell_lot,
            'net_lot': net_lot,
            'weighted_avg_buy': weighted_avg_buy,
            'current_price': current_price,
            'floating_pnl_pct': floating_pnl_pct,
            'floating_pnl_value': floating_pnl_value,
            'active_days': row['active_days'],
            'first_date': row['first_date'],
            'last_date': row['last_date']
        })

    return pd.DataFrame(position_data)


def get_support_resistance_from_positions(position_df: pd.DataFrame) -> dict:
    """
    Calculate support/resistance levels from broker cost basis

    Support: Price levels where many brokers have positions (they will defend)
    Resistance: Price levels where brokers are floating loss (they may sell)
    """
    if position_df.empty:
        return {'supports': [], 'resistances': []}

    current_price = position_df['current_price'].iloc[0] if 'current_price' in position_df.columns else 0

    # Get brokers with positive positions and their avg buy
    holders = position_df[position_df['net_lot'] > 0].copy()

    if holders.empty:
        return {'supports': [], 'resistances': []}

    # Support levels: avg buy below current price (holders are in profit, will defend)
    support_df = holders[holders['weighted_avg_buy'] < current_price].copy()
    support_df = support_df.sort_values('weighted_avg_buy', ascending=False)

    # Resistance levels: avg buy above current price (holders are in loss, may sell)
    resistance_df = holders[holders['weighted_avg_buy'] > current_price].copy()
    resistance_df = resistance_df.sort_values('weighted_avg_buy', ascending=True)

    supports = []
    for _, row in support_df.head(5).iterrows():
        supports.append({
            'price': row['weighted_avg_buy'],
            'broker': row['broker_code'],
            'lot': row['net_lot'],
            'pnl': row['floating_pnl_pct']
        })

    resistances = []
    for _, row in resistance_df.head(5).iterrows():
        resistances.append({
            'price': row['weighted_avg_buy'],
            'broker': row['broker_code'],
            'lot': row['net_lot'],
            'pnl': row['floating_pnl_pct']
        })

    return {'supports': supports, 'resistances': resistances, 'current_price': current_price}


# ============================================================
# PHASE ANALYSIS FUNCTIONS
# ============================================================

def get_recent_price_data(stock_code: str, days: int = 60) -> pd.DataFrame:
    """Get recent price data for phase analysis"""
    query = """
        SELECT date, open_price, high_price, low_price, close_price, volume
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date DESC
        LIMIT %s
    """
    results = execute_query(query, (stock_code, days))
    if results:
        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        return df
    return pd.DataFrame()


def get_recent_broker_flow(stock_code: str, days: int = 30) -> dict:
    """Get recent broker flow analysis (30 days)"""
    query = """
        SELECT
            date,
            SUM(CASE WHEN net_value > 0 THEN net_value ELSE 0 END) as total_buy_value,
            SUM(CASE WHEN net_value < 0 THEN ABS(net_value) ELSE 0 END) as total_sell_value,
            SUM(net_value) as net_value,
            SUM(CASE WHEN net_lot > 0 THEN net_lot ELSE 0 END) as total_buy_lot,
            SUM(CASE WHEN net_lot < 0 THEN ABS(net_lot) ELSE 0 END) as total_sell_lot,
            SUM(net_lot) as net_lot,
            COUNT(DISTINCT CASE WHEN net_lot > 0 THEN broker_code END) as buyer_count,
            COUNT(DISTINCT CASE WHEN net_lot < 0 THEN broker_code END) as seller_count
        FROM broker_summary
        WHERE stock_code = %s AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY date
        ORDER BY date
    """
    results = execute_query(query, (stock_code, days))

    if not results:
        return {
            'net_buy_days': 0, 'net_sell_days': 0,
            'total_net_lot': 0, 'total_net_value': 0,
            'avg_buyer_count': 0, 'avg_seller_count': 0,
            'trend': 'NEUTRAL', 'daily_data': []
        }

    df = pd.DataFrame(results)

    net_buy_days = len(df[df['net_lot'] > 0])
    net_sell_days = len(df[df['net_lot'] < 0])
    total_net_lot = df['net_lot'].sum()
    total_net_value = df['net_value'].sum()
    avg_buyer_count = df['buyer_count'].mean()
    avg_seller_count = df['seller_count'].mean()

    # Determine trend
    if net_buy_days > net_sell_days * 1.5 and total_net_lot > 0:
        trend = 'ACCUMULATION'
    elif net_sell_days > net_buy_days * 1.5 and total_net_lot < 0:
        trend = 'DISTRIBUTION'
    else:
        trend = 'NEUTRAL'

    return {
        'net_buy_days': net_buy_days,
        'net_sell_days': net_sell_days,
        'total_net_lot': total_net_lot,
        'total_net_value': total_net_value,
        'avg_buyer_count': avg_buyer_count,
        'avg_seller_count': avg_seller_count,
        'trend': trend,
        'daily_data': df.to_dict('records') if not df.empty else []
    }


def get_foreign_flow(stock_code: str, days: int = 30) -> dict:
    """Get foreign investor flow"""
    # Use correct foreign broker codes from broker_config
    # These are brokers with ACTUAL foreign parent companies
    # NOT including BUMN (CC=Mandiri, NI=BNI) which are local government-owned
    foreign_codes = list(FOREIGN_BROKER_CODES)  # From broker_config.py

    placeholders = ','.join(['%s'] * len(foreign_codes))
    query = f"""
        SELECT
            date,
            SUM(net_value) as foreign_net_value,
            SUM(net_lot) as foreign_net_lot
        FROM broker_summary
        WHERE stock_code = %s
          AND date >= CURRENT_DATE - INTERVAL '{days} days'
          AND broker_code IN ({placeholders})
        GROUP BY date
        ORDER BY date
    """

    params = [stock_code] + foreign_codes
    results = execute_query(query, tuple(params))

    if not results:
        return {'total_net_lot': 0, 'total_net_value': 0, 'trend': 'NEUTRAL', 'consecutive_days': 0}

    df = pd.DataFrame(results)
    total_net_lot = df['foreign_net_lot'].sum()
    total_net_value = df['foreign_net_value'].sum()

    # Calculate consecutive days of same direction
    if len(df) > 0:
        last_direction = 1 if df['foreign_net_lot'].iloc[-1] > 0 else -1
        consecutive = 0
        for i in range(len(df) - 1, -1, -1):
            current_direction = 1 if df['foreign_net_lot'].iloc[i] > 0 else -1
            if current_direction == last_direction:
                consecutive += 1
            else:
                break
    else:
        consecutive = 0

    if total_net_lot > 0:
        trend = 'INFLOW'
    elif total_net_lot < 0:
        trend = 'OUTFLOW'
    else:
        trend = 'NEUTRAL'

    return {
        'total_net_lot': total_net_lot,
        'total_net_value': total_net_value,
        'trend': trend,
        'consecutive_days': consecutive
    }


def detect_market_phase(stock_code: str) -> dict:
    """
    Detect current market phase based on price action and broker flow

    Phases:
    - ACCUMULATION: Smart money buying, price sideways/bottom
    - MARKUP: Price trending up
    - DISTRIBUTION: Smart money selling, price sideways/top
    - MARKDOWN: Price trending down
    """
    # Get price data
    price_df = get_recent_price_data(stock_code, 60)
    if price_df.empty:
        return {'phase': 'UNKNOWN', 'confidence': 0, 'signals': []}

    # Get broker flow
    broker_flow = get_recent_broker_flow(stock_code, 30)
    foreign_flow = get_foreign_flow(stock_code, 30)

    signals = []
    phase_scores = {'ACCUMULATION': 0, 'MARKUP': 0, 'DISTRIBUTION': 0, 'MARKDOWN': 0}

    # Price trend analysis (20 days)
    if len(price_df) >= 20:
        recent_20 = price_df.tail(20)
        price_change_20d = (recent_20['close_price'].iloc[-1] - recent_20['close_price'].iloc[0]) / recent_20['close_price'].iloc[0] * 100

        # Volatility (range)
        avg_range = ((recent_20['high_price'] - recent_20['low_price']) / recent_20['low_price'] * 100).mean()

        # Higher highs / lower lows pattern
        highs = recent_20['high_price'].values
        lows = recent_20['low_price'].values
        higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        lower_lows = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        # Price trend signals
        if price_change_20d > 10:
            signals.append(('Harga naik >10% dalam 20 hari', 'MARKUP'))
            phase_scores['MARKUP'] += 2
        elif price_change_20d < -10:
            signals.append(('Harga turun >10% dalam 20 hari', 'MARKDOWN'))
            phase_scores['MARKDOWN'] += 2
        elif abs(price_change_20d) < 5:
            if broker_flow['trend'] == 'ACCUMULATION':
                signals.append(('Harga sideways + broker akumulasi', 'ACCUMULATION'))
                phase_scores['ACCUMULATION'] += 2
            elif broker_flow['trend'] == 'DISTRIBUTION':
                signals.append(('Harga sideways + broker distribusi', 'DISTRIBUTION'))
                phase_scores['DISTRIBUTION'] += 2

        # Pattern signals
        if higher_highs > 12:
            signals.append(('Higher highs dominan (uptrend)', 'MARKUP'))
            phase_scores['MARKUP'] += 1
        if lower_lows > 12:
            signals.append(('Lower lows dominan (downtrend)', 'MARKDOWN'))
            phase_scores['MARKDOWN'] += 1

        # Volatility signals
        if avg_range < 2:
            signals.append(('Volatilitas rendah (konsolidasi)', 'ACCUMULATION'))
            phase_scores['ACCUMULATION'] += 1

    # Broker flow signals (local brokers)
    if broker_flow['trend'] == 'ACCUMULATION':
        signals.append((f"Broker net buy {broker_flow['net_buy_days']} hari dari 30 hari", 'ACCUMULATION'))
        phase_scores['ACCUMULATION'] += 2
    elif broker_flow['trend'] == 'DISTRIBUTION':
        signals.append((f"Broker net sell {broker_flow['net_sell_days']} hari dari 30 hari", 'DISTRIBUTION'))
        phase_scores['DISTRIBUTION'] += 1  # Lower weight, could be retail selling to foreign

    # Foreign flow signals (SMART MONEY - higher weight)
    # Foreign INFLOW = Smart money buying = ACCUMULATION/MARKUP, CONTRADICTS Distribution
    # Foreign OUTFLOW = Smart money selling = DISTRIBUTION/MARKDOWN, CONTRADICTS Accumulation
    if foreign_flow['trend'] == 'INFLOW':
        signals.append((f"Foreign INFLOW +{foreign_flow['total_net_lot']:,.0f} lot (Smart Money Buy)", 'ACCUMULATION'))
        phase_scores['ACCUMULATION'] += 3  # High weight - smart money signal
        phase_scores['MARKUP'] += 2
        # CONTRADICTS distribution - smart money buying, not selling
        phase_scores['DISTRIBUTION'] = max(0, phase_scores['DISTRIBUTION'] - 2)
        phase_scores['MARKDOWN'] = max(0, phase_scores['MARKDOWN'] - 1)
    elif foreign_flow['trend'] == 'OUTFLOW':
        signals.append((f"Foreign OUTFLOW {foreign_flow['total_net_lot']:,.0f} lot (Smart Money Sell)", 'DISTRIBUTION'))
        phase_scores['DISTRIBUTION'] += 3  # High weight - smart money signal
        phase_scores['MARKDOWN'] += 2
        # CONTRADICTS accumulation - smart money selling, not buying
        phase_scores['ACCUMULATION'] = max(0, phase_scores['ACCUMULATION'] - 2)
        phase_scores['MARKUP'] = max(0, phase_scores['MARKUP'] - 1)

    # Determine phase
    max_score = max(phase_scores.values())
    if max_score == 0:
        phase = 'UNKNOWN'
        confidence = 0
    else:
        phase = max(phase_scores, key=phase_scores.get)
        total_signals = sum(phase_scores.values())
        confidence = int((max_score / total_signals) * 100) if total_signals > 0 else 0

    return {
        'phase': phase,
        'confidence': confidence,
        'signals': signals,
        'broker_flow': broker_flow,
        'foreign_flow': foreign_flow,
        'phase_scores': phase_scores
    }


def create_phase_analysis_card(stock_code: str, current_price: float):
    """
    Create the Phase Analysis UI card - USES get_comprehensive_validation
    to be consistent with Accumulation page (30 days analysis)
    """
    # Use get_comprehensive_validation for consistency with Accumulation page
    validation = get_comprehensive_validation(stock_code, 30)

    if validation.get('error'):
        return dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-chart-line me-2"),
                    "Phase Analysis (30 Hari Terakhir)"
                ], className="mb-0")
            ]),
            dbc.CardBody([
                html.P(validation['error'], className="text-warning")
            ])
        ])

    # Extract data from validation (same source as Accumulation page)
    summary = validation.get('summary', {})
    confidence = validation.get('confidence', {})
    validations = validation.get('validations', {})

    # Overall signal: AKUMULASI, DISTRIBUSI, NETRAL
    overall_signal = summary.get('overall_signal', 'NETRAL')
    pass_rate = confidence.get('pass_rate', 0)

    # Map signal to phase for display
    phase_styles = {
        'AKUMULASI': {'color': '#17a2b8', 'icon': 'fa-layer-group', 'label': 'ACCUMULATION'},
        'DISTRIBUSI': {'color': '#ffc107', 'icon': 'fa-hand-holding-dollar', 'label': 'DISTRIBUTION'},
        'NETRAL': {'color': '#6c757d', 'icon': 'fa-balance-scale', 'label': 'NEUTRAL'}
    }

    style = phase_styles.get(overall_signal, phase_styles['NETRAL'])

    # Count signals from each validation
    accum_signals = 0
    distrib_signals = 0
    for v in validations.values():
        sig = v.get('signal', '')
        if sig == 'AKUMULASI':
            accum_signals += 1
        elif sig == 'DISTRIBUSI':
            distrib_signals += 1

    # Validation checklist with signal indicator
    check_mapping = [
        ('cpr', 'Sideway Valid (CPR)'),
        ('uvdv', 'Volume Absorption'),
        ('broker_influence', 'Broker Influence'),
        ('persistence', 'Persistence Cukup'),
        ('elasticity', 'Elastisitas Mendukung'),
        ('rotation', 'Multi-Broker Selaras'),
    ]

    checklist_items = []
    for key, label in check_mapping:
        v = validations.get(key, {})
        passed = v.get('passed', False)
        signal = v.get('signal', 'NETRAL')
        explanation = v.get('explanation', '')

        # Status icon
        status_icon = "[v]" if passed else "[x]"
        status_color = "text-success" if passed else "text-danger"

        # Signal badge
        if signal == 'AKUMULASI':
            signal_badge = html.Span("A", className="badge bg-info ms-2", style={"fontSize": "10px"})
        elif signal == 'DISTRIBUSI':
            signal_badge = html.Span("D", className="badge bg-warning ms-2", style={"fontSize": "10px"})
        else:
            signal_badge = html.Span("N", className="badge bg-secondary ms-2", style={"fontSize": "10px"})

        checklist_items.append(
            html.Div([
                html.Span(status_icon, className=f"{status_color} me-2 fw-bold"),
                html.Span(label, className="small"),
                signal_badge
            ], className="mb-1", title=explanation)
        )

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                html.I(className="fas fa-chart-line me-2"),
                "Phase Analysis (30 Hari Terakhir)"
            ], className="mb-0")
        ]),
        dbc.CardBody([
            # Current Phase Indicator - using validation signal
            html.Div([
                html.Div([
                    html.I(className=f"fas {style['icon']} me-2", style={"fontSize": "24px", "color": style['color']}),
                    html.Span(style['label'], className="fw-bold", style={"fontSize": "20px", "color": style['color']})
                ]),
                html.Div([
                    html.Small(f"Confidence: {pass_rate:.0f}% ({confidence.get('passed', 0)}/6 validasi)", className="text-muted")
                ])
            ], className="text-center mb-3 p-3 rounded info-box", style={
                "borderRadius": "10px",
                "border": f"2px solid {style['color']}"
            }),

            # Signal Breakdown - more intuitive
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Small("Sinyal Akumulasi", className="text-muted d-block"),
                        html.Span(
                            f"{accum_signals} validasi",
                            className="fw-bold text-info"
                        ),
                        html.Br(),
                        html.Small("menunjukkan akumulasi", className="text-muted")
                    ], className="text-center p-2 rounded metric-box")
                ], md=6),
                dbc.Col([
                    html.Div([
                        html.Small("Sinyal Distribusi", className="text-muted d-block"),
                        html.Span(
                            f"{distrib_signals} validasi",
                            className="fw-bold text-warning"
                        ),
                        html.Br(),
                        html.Small("menunjukkan distribusi", className="text-muted")
                    ], className="text-center p-2 rounded metric-box")
                ], md=6),
            ], className="mb-3"),

            # Validation Checklist with signal badges
            html.Hr(),
            html.H6("Detail Validasi (30 Hari):", className="mb-2"),
            html.Div(checklist_items, className="mb-3"),
            html.Small([
                html.Span("A", className="badge bg-info me-1"), "= Akumulasi  ",
                html.Span("D", className="badge bg-warning me-1"), "= Distribusi  ",
                html.Span("N", className="badge bg-secondary me-1"), "= Netral"
            ], className="text-muted"),

            # Phase explanation
            html.Hr(),
            html.Div([
                html.H6("Cara Baca:", className="text-info mb-2"),
                html.Ul([
                    html.Li("Fase ditentukan dari MAYORITAS sinyal validasi"),
                    html.Li([html.Strong("ACCUMULATION: ", style={"color": "#17a2b8"}), "Lebih banyak validasi menunjukkan akumulasi"]),
                    html.Li([html.Strong("DISTRIBUTION: ", style={"color": "#ffc107"}), "Lebih banyak validasi menunjukkan distribusi"]),
                    html.Li([html.Strong("NEUTRAL: ", style={"color": "#6c757d"}), "Sinyal seimbang, tidak ada dominasi"]),
                ], className="small")
            ])
        ])
    ])


# ============================================================
# ACCUMULATION SCORE CALCULATION (Backtest-based Formula)
# ============================================================

def calculate_accumulation_score(stock_code: str, lookback_days: int = 30) -> dict:
    """
    Calculate Accumulation Score based on backtested formula from PANI cycles.

    Formula Components (Total 100 points):
    1. Top Broker Buy/Sell Ratio (15 pts) - High ratio = aggressive buying
    2. Consolidation Pattern (20 pts) - Sideways = accumulation zone
    3. Price Distance from 52w Low (20 pts) - Near bottom = better entry
    4. Volume Contraction (15 pts) - Low volume = stealth accumulation
    5. Domestic Broker Net Positive (15 pts) - Local smart money
    6. Foreign Flow Starting (15 pts) - Foreign starting to enter

    Returns dict with score, components, and interpretation.
    """
    result = {
        'score': 0,
        'components': {},
        'interpretation': 'NO DATA',
        'signal': 'NEUTRAL',
        'details': []
    }

    try:
        # 1. TOP BROKER BUY/SELL RATIO (15 points)
        # Query top 5 net buyers and their buy/sell ratio
        ratio_query = """
            SELECT
                broker_code,
                SUM(buy_lot) as total_buy,
                SUM(sell_lot) as total_sell,
                CASE WHEN SUM(sell_lot) > 0
                     THEN ROUND(SUM(buy_lot)::numeric / SUM(sell_lot), 2)
                     ELSE 99 END as buy_sell_ratio
            FROM broker_summary
            WHERE stock_code = %s
            AND date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY broker_code
            HAVING SUM(net_lot) > 0
            ORDER BY SUM(net_lot) DESC
            LIMIT 5
        """
        ratio_results = execute_query(ratio_query, (stock_code, lookback_days))

        if ratio_results:
            avg_ratio = float(sum(float(r['buy_sell_ratio']) for r in ratio_results) / len(ratio_results))
            # Score: ratio 1.5 = 5pts, ratio 3.0 = 10pts, ratio 5+ = 15pts
            ratio_score = min(15, max(0, (avg_ratio - 1) * 5))
            result['components']['broker_ratio'] = {
                'value': round(avg_ratio, 2),
                'score': round(ratio_score, 1),
                'max': 15,
                'top_brokers': [r['broker_code'] for r in ratio_results[:3]]
            }
            result['details'].append(f"Top5 Broker Avg Ratio: {avg_ratio:.2f}x = {ratio_score:.1f}/15 pts")
        else:
            ratio_score = 0
            result['components']['broker_ratio'] = {'value': 0, 'score': 0, 'max': 15, 'top_brokers': []}

        # 2. CONSOLIDATION PATTERN (20 points)
        # Check price range over lookback period - tight range = consolidation
        consol_query = """
            SELECT
                MAX(high_price) as period_high,
                MIN(low_price) as period_low,
                (array_agg(close_price ORDER BY date))[1] as first_close,
                (array_agg(close_price ORDER BY date DESC))[1] as last_close,
                COUNT(*) as days
            FROM stock_daily
            WHERE stock_code = %s
            AND date >= CURRENT_DATE - INTERVAL '%s days'
        """
        consol_results = execute_query(consol_query, (stock_code, lookback_days))

        if consol_results and consol_results[0]['period_high']:
            r = consol_results[0]
            period_high = float(r['period_high'])
            period_low = float(r['period_low'])
            first_close = float(r['first_close'])
            last_close = float(r['last_close'])
            price_range_pct = ((period_high - period_low) / period_low * 100) if period_low > 0 else 100
            price_change_pct = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0

            # Consolidation: range < 15% and change < 10% = good accumulation zone
            if price_range_pct < 10 and abs(price_change_pct) < 5:
                consol_score = 20  # Perfect consolidation
            elif price_range_pct < 15 and abs(price_change_pct) < 8:
                consol_score = 15  # Good consolidation
            elif price_range_pct < 20 and abs(price_change_pct) < 12:
                consol_score = 10  # Moderate
            elif price_range_pct < 30:
                consol_score = 5   # Weak
            else:
                consol_score = 0   # No consolidation

            result['components']['consolidation'] = {
                'range_pct': round(price_range_pct, 1),
                'change_pct': round(price_change_pct, 1),
                'score': consol_score,
                'max': 20
            }
            result['details'].append(f"Price Range: {price_range_pct:.1f}%, Change: {price_change_pct:+.1f}% = {consol_score}/20 pts")
        else:
            consol_score = 0
            result['components']['consolidation'] = {'range_pct': 0, 'change_pct': 0, 'score': 0, 'max': 20}

        # 3. PRICE DISTANCE FROM 52-WEEK LOW (20 points)
        # Near bottom = better entry for accumulation
        low52_query = """
            SELECT
                MIN(low_price) as low_52w,
                MAX(high_price) as high_52w,
                (SELECT close_price FROM stock_daily
                 WHERE stock_code = %s ORDER BY date DESC LIMIT 1) as current_price
            FROM stock_daily
            WHERE stock_code = %s
            AND date >= CURRENT_DATE - INTERVAL '365 days'
        """
        low52_results = execute_query(low52_query, (stock_code, stock_code))

        if low52_results and low52_results[0]['low_52w']:
            r = low52_results[0]
            current_price = float(r['current_price'])
            low_52w = float(r['low_52w'])
            high_52w = float(r['high_52w'])
            distance_from_low = ((current_price - low_52w) / low_52w * 100) if low_52w > 0 else 100

            # Score: <10% from low = 20pts, <20% = 15pts, <30% = 10pts, <50% = 5pts
            if distance_from_low < 10:
                low_score = 20
            elif distance_from_low < 20:
                low_score = 15
            elif distance_from_low < 30:
                low_score = 10
            elif distance_from_low < 50:
                low_score = 5
            else:
                low_score = 0

            result['components']['price_position'] = {
                'current': current_price,
                'low_52w': low_52w,
                'high_52w': high_52w,
                'distance_from_low_pct': round(distance_from_low, 1),
                'score': low_score,
                'max': 20
            }
            result['details'].append(f"Distance from 52w Low: {distance_from_low:.1f}% = {low_score}/20 pts")
        else:
            low_score = 0
            result['components']['price_position'] = {'distance_from_low_pct': 100, 'score': 0, 'max': 20}

        # 4. VOLUME CONTRACTION (15 points)
        # Low volume during consolidation = stealth accumulation
        vol_query = """
            WITH recent_vol AS (
                SELECT AVG(volume) as recent_avg
                FROM stock_daily
                WHERE stock_code = %s
                AND date >= CURRENT_DATE - INTERVAL '%s days'
            ),
            historical_vol AS (
                SELECT AVG(volume) as hist_avg
                FROM stock_daily
                WHERE stock_code = %s
                AND date >= CURRENT_DATE - INTERVAL '90 days'
                AND date < CURRENT_DATE - INTERVAL '%s days'
            )
            SELECT
                r.recent_avg,
                h.hist_avg,
                CASE WHEN h.hist_avg > 0
                     THEN r.recent_avg / h.hist_avg
                     ELSE 1 END as volume_ratio
            FROM recent_vol r, historical_vol h
        """
        vol_results = execute_query(vol_query, (stock_code, lookback_days, stock_code, lookback_days))

        if vol_results and vol_results[0]['volume_ratio']:
            vol_ratio = float(vol_results[0]['volume_ratio'])

            # Volume contraction (ratio < 1) is bullish for accumulation
            # ratio 0.5 = 15pts (50% lower volume), ratio 0.7 = 10pts, ratio 1.0 = 5pts
            if vol_ratio < 0.5:
                vol_score = 15
            elif vol_ratio < 0.7:
                vol_score = 12
            elif vol_ratio < 0.9:
                vol_score = 8
            elif vol_ratio < 1.1:
                vol_score = 5
            else:
                vol_score = 0  # Volume expansion - not accumulation pattern

            result['components']['volume'] = {
                'ratio': round(vol_ratio, 2),
                'score': vol_score,
                'max': 15,
                'pattern': 'CONTRACTION' if vol_ratio < 0.9 else 'EXPANSION'
            }
            result['details'].append(f"Volume Ratio: {vol_ratio:.2f}x vs 90d avg = {vol_score}/15 pts")
        else:
            vol_score = 0
            result['components']['volume'] = {'ratio': 1, 'score': 0, 'max': 15, 'pattern': 'UNKNOWN'}

        # 5. DOMESTIC BROKER NET POSITIVE (15 points)
        # Domestic brokers accumulating = local smart money
        # Use correct FOREIGN_BROKER_CODES list
        foreign_codes_list = list(FOREIGN_BROKER_CODES)
        foreign_placeholders = ','.join(['%s'] * len(foreign_codes_list))
        domestic_query = f"""
            SELECT
                SUM(CASE WHEN broker_code NOT IN ({foreign_placeholders})
                         THEN net_lot ELSE 0 END) as domestic_net,
                COUNT(DISTINCT CASE WHEN broker_code NOT IN ({foreign_placeholders})
                                    AND net_lot > 0 THEN broker_code END) as domestic_buyers,
                COUNT(DISTINCT CASE WHEN broker_code NOT IN ({foreign_placeholders})
                                    AND net_lot < 0 THEN broker_code END) as domestic_sellers
            FROM broker_summary
            WHERE stock_code = %s
            AND date >= CURRENT_DATE - INTERVAL '{lookback_days} days'
        """
        # Parameters: foreign_codes (3x for each CASE) + stock_code
        domestic_params = tuple(foreign_codes_list * 3 + [stock_code])
        domestic_results = execute_query(domestic_query, domestic_params)

        if domestic_results:
            r = domestic_results[0]
            domestic_net = r['domestic_net'] or 0
            buyers = r['domestic_buyers'] or 0
            sellers = r['domestic_sellers'] or 0

            # Score based on net position and buyer/seller ratio
            if domestic_net > 0 and buyers > sellers * 1.5:
                domestic_score = 15
            elif domestic_net > 0 and buyers > sellers:
                domestic_score = 12
            elif domestic_net > 0:
                domestic_score = 8
            elif domestic_net == 0:
                domestic_score = 5
            else:
                domestic_score = 0

            result['components']['domestic_flow'] = {
                'net_lot': domestic_net,
                'buyers': buyers,
                'sellers': sellers,
                'score': domestic_score,
                'max': 15
            }
            result['details'].append(f"Domestic Net: {domestic_net:+,.0f} lot ({buyers}B/{sellers}S) = {domestic_score}/15 pts")
        else:
            domestic_score = 0
            result['components']['domestic_flow'] = {'net_lot': 0, 'score': 0, 'max': 15}

        # 6. FOREIGN FLOW STARTING (15 points)
        # Foreign starting to enter after domestic accumulation
        # Use correct FOREIGN_BROKER_CODES list
        foreign_query = f"""
            WITH weekly_foreign AS (
                SELECT
                    DATE_TRUNC('week', date) as week,
                    SUM(CASE WHEN broker_code IN ({foreign_placeholders})
                             THEN net_lot ELSE 0 END) as foreign_net
                FROM broker_summary
                WHERE stock_code = %s
                AND date >= CURRENT_DATE - INTERVAL '{lookback_days} days'
                GROUP BY DATE_TRUNC('week', date)
                ORDER BY week
            )
            SELECT
                COUNT(*) as weeks,
                SUM(CASE WHEN foreign_net > 0 THEN 1 ELSE 0 END) as positive_weeks,
                (array_agg(foreign_net ORDER BY week DESC))[1] as last_week_net,
                (array_agg(foreign_net ORDER BY week DESC))[2] as prev_week_net,
                SUM(foreign_net) as total_foreign
            FROM weekly_foreign
        """
        foreign_params = tuple(foreign_codes_list + [stock_code])
        foreign_results = execute_query(foreign_query, foreign_params)

        if foreign_results and foreign_results[0]['weeks']:
            r = foreign_results[0]
            total_foreign = r['total_foreign'] or 0
            positive_weeks = r['positive_weeks'] or 0
            last_week = r['last_week_net'] or 0
            prev_week = r['prev_week_net'] or 0

            # Score based on foreign flow trend
            # Best: recent inflow starting (last week positive, improving)
            if last_week > 0 and last_week > prev_week:
                foreign_score = 15  # Foreign accelerating in
            elif last_week > 0:
                foreign_score = 12  # Foreign buying
            elif total_foreign > 0:
                foreign_score = 8   # Net positive overall
            elif last_week > prev_week:
                foreign_score = 5   # Improving (less selling)
            else:
                foreign_score = 0   # Foreign selling

            result['components']['foreign_flow'] = {
                'total': total_foreign,
                'positive_weeks': positive_weeks,
                'last_week': last_week,
                'trend': 'ACCELERATING' if last_week > 0 and last_week > prev_week else
                         'INFLOW' if last_week > 0 else
                         'IMPROVING' if last_week > prev_week else 'OUTFLOW',
                'score': foreign_score,
                'max': 15
            }
            result['details'].append(f"Foreign Flow: {total_foreign:+,.0f} lot, Last week: {last_week:+,.0f} = {foreign_score}/15 pts")
        else:
            foreign_score = 0
            result['components']['foreign_flow'] = {'total': 0, 'score': 0, 'max': 15, 'trend': 'UNKNOWN'}

        # CALCULATE TOTAL SCORE
        total_score = ratio_score + consol_score + low_score + vol_score + domestic_score + foreign_score
        result['score'] = round(total_score, 1)

        # INTERPRETATION
        if total_score >= 70:
            result['interpretation'] = 'STRONG ACCUMULATION'
            result['signal'] = 'CONSIDER ENTRY'
            result['color'] = '#28a745'  # Green
        elif total_score >= 55:
            result['interpretation'] = 'MODERATE ACCUMULATION'
            result['signal'] = 'WATCH CLOSELY'
            result['color'] = '#17a2b8'  # Cyan
        elif total_score >= 40:
            result['interpretation'] = 'WEAK ACCUMULATION'
            result['signal'] = 'EARLY STAGE'
            result['color'] = '#ffc107'  # Yellow
        else:
            result['interpretation'] = 'NO ACCUMULATION'
            result['signal'] = 'AVOID'
            result['color'] = '#dc3545'  # Red

    except Exception as e:
        result['error'] = str(e)
        result['interpretation'] = 'ERROR'
        result['signal'] = 'N/A'
        result['color'] = '#6c757d'

    return result


def create_accumulation_score_card(stock_code: str):
    """Create UI card for Accumulation Score display"""
    acc_data = calculate_accumulation_score(stock_code, lookback_days=30)

    # Component progress bars
    component_bars = []
    component_order = ['broker_ratio', 'consolidation', 'price_position', 'volume', 'domestic_flow', 'foreign_flow']
    component_labels = {
        'broker_ratio': 'Top Broker Buy/Sell Ratio',
        'consolidation': 'Consolidation Pattern',
        'price_position': 'Price vs 52w Low',
        'volume': 'Volume Contraction',
        'domestic_flow': 'Domestic Broker Flow',
        'foreign_flow': 'Foreign Flow Trend'
    }

    for comp_key in component_order:
        if comp_key in acc_data['components']:
            comp = acc_data['components'][comp_key]
            pct = (comp['score'] / comp['max'] * 100) if comp['max'] > 0 else 0

            # Color based on score percentage
            if pct >= 70:
                bar_color = 'success'
            elif pct >= 50:
                bar_color = 'info'
            elif pct >= 30:
                bar_color = 'warning'
            else:
                bar_color = 'danger'

            component_bars.append(
                html.Div([
                    html.Div([
                        html.Small(component_labels.get(comp_key, comp_key), className="text-muted"),
                        html.Small(f"{comp['score']:.0f}/{comp['max']}", className="float-end")
                    ], className="d-flex justify-content-between"),
                    dbc.Progress(value=pct, color=bar_color, className="mb-2", style={"height": "8px"})
                ], className="mb-1")
            )

    # Detail items
    detail_items = [html.Li(d, className="small") for d in acc_data.get('details', [])]

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                html.I(className="fas fa-layer-group me-2"),
                "Accumulation Score (Backtest Formula)"
            ], className="mb-0")
        ]),
        dbc.CardBody([
            # Main Score Display
            html.Div([
                html.Div([
                    html.H1(f"{acc_data['score']:.0f}",
                            className="mb-0 display-4",
                            style={"color": acc_data.get('color', '#6c757d')}),
                    html.Span("/100", className="text-muted h4")
                ]),
                html.Div([
                    html.Span(acc_data['interpretation'],
                              className="badge fs-6",
                              style={"backgroundColor": acc_data.get('color', '#6c757d')})
                ], className="mt-2"),
                html.Div([
                    html.Strong(f"Signal: {acc_data['signal']}",
                               style={"color": acc_data.get('color', '#6c757d')})
                ], className="mt-1")
            ], className="text-center p-3 mb-3 rounded info-box", style={
                "borderRadius": "10px",
                "border": f"2px solid {acc_data.get('color', '#6c757d')}"
            }),

            # Component Breakdown
            html.H6("Component Breakdown:", className="mb-3"),
            html.Div(component_bars),

            # Details
            html.Hr(),
            html.H6("Calculation Details:", className="mb-2"),
            html.Ul(detail_items if detail_items else [
                html.Li("No data available", className="text-muted small")
            ], className="small mb-3", style={"paddingLeft": "20px"}),

            # Score Guide
            html.Hr(),
            html.Div([
                html.H6("Score Guide:", className="text-info mb-2"),
                html.Ul([
                    html.Li([html.Strong(">=70: ", style={"color": "#28a745"}), "STRONG ACCUMULATION - Consider Entry"]),
                    html.Li([html.Strong("55-69: ", style={"color": "#17a2b8"}), "MODERATE - Watch Closely"]),
                    html.Li([html.Strong("40-54: ", style={"color": "#ffc107"}), "WEAK/EARLY - Still Building"]),
                    html.Li([html.Strong("<40: ", style={"color": "#dc3545"}), "NO ACCUMULATION - Avoid"]),
                ], className="small")
            ])
        ])
    ])


# ============================================================
# DISTRIBUTION SCORE CALCULATION (Dynamic for all stocks)
# ============================================================

def calculate_distribution_score(stock_code: str, lookback_days: int = 30) -> dict:
    """
    Calculate Distribution Score - Early warning for selling.

    Berdasarkan backtest CDIA dan PANI, sinyal distribusi meliputi:
    1. Top Broker Sell Ratio (20 pts) - Broker besar net seller?
    2. Buyer Reversal (20 pts) - Pembeli kemarin jadi penjual?
    3. Volume Climax (15 pts) - Volume spike dengan reversal?
    4. Foreign Outflow (15 pts) - Asing keluar saat harga naik?
    5. Price Near High (15 pts) - Harga dekat 52-week high?
    6. Consecutive Down Days (15 pts) - Berturut-turut turun?

    Score tinggi = WARNING to SELL
    """
    from analyzer import get_price_data, get_broker_data

    result = {
        'score': 0,
        'max_score': 100,
        'components': {},
        'details': [],
        'interpretation': '',
        'signal': '',
        'color': '',
        'phase': 'UNKNOWN'
    }

    try:
        price_df = get_price_data(stock_code)
        broker_df = get_broker_data(stock_code)

        if price_df.empty:
            result['error'] = 'No price data'
            return result

        # Sort and get recent data
        price_df = price_df.sort_values('date').tail(lookback_days * 2).reset_index(drop=True)

        # Convert Decimal to float
        for col in ['close_price', 'open_price', 'high_price', 'low_price', 'volume', 'value']:
            if col in price_df.columns:
                price_df[col] = price_df[col].astype(float)

        current_price = float(price_df.iloc[-1]['close_price'])
        current_date = price_df.iloc[-1]['date']

        # ============================================================
        # COMPONENT 1: Top Broker Sell Ratio (20 pts)
        # Jika top 5 broker adalah net seller = distribusi signal
        # ============================================================
        broker_ratio_score = 0
        broker_ratio_max = 20
        broker_ratio_detail = ""

        if not broker_df.empty:
            recent_dates = sorted(broker_df['date'].unique())[-5:]
            recent_broker = broker_df[broker_df['date'].isin(recent_dates)]

            # Get top 5 brokers by absolute activity
            broker_totals = recent_broker.groupby('broker_code').agg({
                'net_value': 'sum',
                'buy_value': 'sum',
                'sell_value': 'sum'
            }).reset_index()
            broker_totals['abs_activity'] = abs(broker_totals['net_value'])
            top_brokers = broker_totals.nlargest(5, 'abs_activity')

            if not top_brokers.empty:
                sellers = (top_brokers['net_value'] < 0).sum()
                total_net = float(top_brokers['net_value'].sum())

                # Score based on how many top brokers are selling
                if sellers >= 4:
                    broker_ratio_score = 20
                elif sellers >= 3:
                    broker_ratio_score = 15
                elif sellers >= 2:
                    broker_ratio_score = 10
                elif total_net < 0:
                    broker_ratio_score = 5

                broker_ratio_detail = f"{sellers}/5 top brokers selling (Net: {total_net/1e9:.1f}B)"

        result['components']['broker_ratio'] = {
            'score': broker_ratio_score,
            'max': broker_ratio_max,
            'detail': broker_ratio_detail
        }
        result['details'].append(f"Top Broker Sell: {broker_ratio_detail}")

        # ============================================================
        # COMPONENT 2: Buyer Reversal Detection (20 pts)
        # Pembeli besar kemarin menjadi penjual hari ini = strong signal
        # ============================================================
        reversal_score = 0
        reversal_max = 20
        reversal_detail = ""

        if not broker_df.empty and len(broker_df['date'].unique()) >= 3:
            dates = sorted(broker_df['date'].unique())

            # Get last 3 days
            if len(dates) >= 3:
                prev_dates = dates[-4:-1]  # T-3 to T-1
                current_day = dates[-1]    # T

                prev_broker = broker_df[broker_df['date'].isin(prev_dates)]
                curr_broker = broker_df[broker_df['date'] == current_day]

                # Find big buyers in previous days
                prev_totals = prev_broker.groupby('broker_code')['net_value'].sum()
                big_buyers = prev_totals[prev_totals > 1e9].index.tolist()  # Bought > 1B

                # Check if they're selling today
                reversals = []
                for buyer in big_buyers:
                    today_net = curr_broker[curr_broker['broker_code'] == buyer]['net_value'].sum()
                    if today_net < -500e6:  # Selling > 500M
                        reversals.append(buyer)

                if len(reversals) >= 3:
                    reversal_score = 20
                elif len(reversals) >= 2:
                    reversal_score = 15
                elif len(reversals) >= 1:
                    reversal_score = 10

                reversal_detail = f"{len(reversals)} buyer(s) reversed to seller: {', '.join(reversals[:3])}" if reversals else "No buyer reversal"

        result['components']['buyer_reversal'] = {
            'score': reversal_score,
            'max': reversal_max,
            'detail': reversal_detail
        }
        result['details'].append(f"Buyer Reversal: {reversal_detail}")

        # ============================================================
        # COMPONENT 3: Volume Climax Detection (15 pts)
        # Volume spike dengan price reversal = distribution climax
        # ============================================================
        volume_climax_score = 0
        volume_climax_max = 15
        volume_climax_detail = ""

        if len(price_df) >= 10:
            avg_volume = price_df['volume'].tail(20).mean()
            recent_5 = price_df.tail(5)

            # Check for volume climax (volume > 2x average with reversal)
            climax_found = False
            for i in range(len(recent_5) - 1):
                row = recent_5.iloc[i]
                next_row = recent_5.iloc[i + 1]

                vol_ratio = float(row['volume']) / avg_volume if avg_volume > 0 else 0
                price_change = (float(next_row['close_price']) - float(row['close_price'])) / float(row['close_price']) * 100

                if vol_ratio > 2.0 and price_change < -2:  # Volume spike + down > 2%
                    climax_found = True
                    volume_climax_score = 15
                    volume_climax_detail = f"Volume climax {vol_ratio:.1f}x dengan reversal {price_change:.1f}%"
                    break
                elif vol_ratio > 1.5 and price_change < -1:
                    if volume_climax_score < 10:
                        volume_climax_score = 10
                        volume_climax_detail = f"Volume spike {vol_ratio:.1f}x dengan pullback {price_change:.1f}%"

            if not volume_climax_detail:
                volume_climax_detail = "No volume climax detected"

        result['components']['volume_climax'] = {
            'score': volume_climax_score,
            'max': volume_climax_max,
            'detail': volume_climax_detail
        }
        result['details'].append(f"Volume Climax: {volume_climax_detail}")

        # ============================================================
        # COMPONENT 4: Foreign Outflow (15 pts)
        # Asing keluar sementara harga naik = smart money distribusi
        # ============================================================
        foreign_score = 0
        foreign_max = 15
        foreign_detail = ""

        if not broker_df.empty:
            recent_dates = sorted(broker_df['date'].unique())[-5:]
            recent_broker = broker_df[broker_df['date'].isin(recent_dates)].copy()

            # Calculate foreign flow using correct FOREIGN_BROKER_CODES
            recent_broker['is_foreign'] = recent_broker['broker_code'].isin(FOREIGN_BROKER_CODES)
            foreign_flow = recent_broker[recent_broker['is_foreign']]['net_value'].sum()
            domestic_flow = recent_broker[~recent_broker['is_foreign']]['net_value'].sum()

            # Check price trend (is it going up while foreign selling?)
            price_change_5d = 0
            if len(price_df) >= 5:
                price_change_5d = (current_price - float(price_df.iloc[-5]['close_price'])) / float(price_df.iloc[-5]['close_price']) * 100

            # Scoring: Foreign outflow while price up = distribution
            if foreign_flow < -10e9:  # Foreign sell > 10B
                if price_change_5d >= 0:  # Price stable/up = distribution!
                    foreign_score = 15
                else:
                    foreign_score = 10
            elif foreign_flow < -5e9:  # Foreign sell > 5B
                if price_change_5d >= 0:
                    foreign_score = 12
                else:
                    foreign_score = 7
            elif foreign_flow < 0:  # Any foreign outflow
                foreign_score = 5

            foreign_detail = f"Foreign: {foreign_flow/1e9:.1f}B, Price 5D: {price_change_5d:+.1f}%"

        result['components']['foreign_outflow'] = {
            'score': foreign_score,
            'max': foreign_max,
            'detail': foreign_detail
        }
        result['details'].append(f"Foreign Flow: {foreign_detail}")

        # ============================================================
        # COMPONENT 5: Price Near 52-week High (15 pts)
        # Harga dekat high = zona distribusi
        # ============================================================
        price_high_score = 0
        price_high_max = 15
        price_high_detail = ""

        if len(price_df) >= 20:
            high_52w = price_df['high_price'].max()
            low_52w = price_df['low_price'].min()

            # Calculate position (0-100%)
            price_range = high_52w - low_52w
            if price_range > 0:
                position_pct = (current_price - low_52w) / price_range * 100
                distance_from_high = (high_52w - current_price) / high_52w * 100

                # Score based on proximity to high
                if distance_from_high < 5:  # Within 5% of high
                    price_high_score = 15
                elif distance_from_high < 10:
                    price_high_score = 12
                elif distance_from_high < 15:
                    price_high_score = 8
                elif position_pct > 70:  # In upper 30%
                    price_high_score = 5

                price_high_detail = f"Posisi {position_pct:.0f}% (High: {high_52w:,.0f}, {distance_from_high:.1f}% from high)"

        result['components']['price_near_high'] = {
            'score': price_high_score,
            'max': price_high_max,
            'detail': price_high_detail
        }
        result['details'].append(f"Price Position: {price_high_detail}")

        # ============================================================
        # COMPONENT 6: Consecutive Down Days (15 pts)
        # Berturut-turut turun = momentum distribution
        # ============================================================
        down_days_score = 0
        down_days_max = 15
        down_days_detail = ""

        if len(price_df) >= 5:
            recent_5 = price_df.tail(5)
            consecutive_down = 0
            max_consecutive = 0

            for i in range(1, len(recent_5)):
                if float(recent_5.iloc[i]['close_price']) < float(recent_5.iloc[i-1]['close_price']):
                    consecutive_down += 1
                    max_consecutive = max(max_consecutive, consecutive_down)
                else:
                    consecutive_down = 0

            if max_consecutive >= 4:
                down_days_score = 15
            elif max_consecutive >= 3:
                down_days_score = 12
            elif max_consecutive >= 2:
                down_days_score = 8
            elif max_consecutive >= 1:
                down_days_score = 4

            down_days_detail = f"{max_consecutive} hari turun berturut-turut (dari 5 hari)"

        result['components']['down_days'] = {
            'score': down_days_score,
            'max': down_days_max,
            'detail': down_days_detail
        }
        result['details'].append(f"Down Days: {down_days_detail}")

        # ============================================================
        # CALCULATE TOTAL SCORE
        # ============================================================
        total_score = sum(comp['score'] for comp in result['components'].values())
        result['score'] = total_score

        # ============================================================
        # INTERPRETATION
        # ============================================================
        if total_score >= 70:
            result['interpretation'] = 'STRONG SELL SIGNAL'
            result['signal'] = 'SELL NOW'
            result['color'] = '#dc3545'  # Red
            result['phase'] = 'DISTRIBUTION'
        elif total_score >= 55:
            result['interpretation'] = 'SELL WARNING'
            result['signal'] = 'CONSIDER SELLING'
            result['color'] = '#fd7e14'  # Orange
            result['phase'] = 'EARLY DISTRIBUTION'
        elif total_score >= 40:
            result['interpretation'] = 'WATCH CAREFULLY'
            result['signal'] = 'REDUCE POSITION'
            result['color'] = '#ffc107'  # Yellow
            result['phase'] = 'MARKUP ENDING'
        elif total_score >= 25:
            result['interpretation'] = 'MINOR WARNING'
            result['signal'] = 'HOLD/TRAIL STOP'
            result['color'] = '#17a2b8'  # Info blue
            result['phase'] = 'MARKUP'
        else:
            result['interpretation'] = 'NO DISTRIBUTION'
            result['signal'] = 'HOLD'
            result['color'] = '#28a745'  # Green
            result['phase'] = 'ACCUMULATION/MARKUP'

    except Exception as e:
        result['error'] = str(e)
        result['interpretation'] = 'ERROR'
        result['signal'] = 'N/A'
        result['color'] = '#6c757d'

    return result


def create_distribution_score_card(stock_code: str):
    """Create UI card for Distribution Score display"""
    dist_data = calculate_distribution_score(stock_code, lookback_days=30)

    # Component progress bars
    component_bars = []
    component_order = ['broker_ratio', 'buyer_reversal', 'volume_climax', 'foreign_outflow', 'price_near_high', 'down_days']
    component_labels = {
        'broker_ratio': 'Top Broker Sell Ratio',
        'buyer_reversal': 'Buyer Reversal',
        'volume_climax': 'Volume Climax',
        'foreign_outflow': 'Foreign Outflow',
        'price_near_high': 'Price Near High',
        'down_days': 'Consecutive Down Days'
    }

    for comp_key in component_order:
        if comp_key in dist_data['components']:
            comp = dist_data['components'][comp_key]
            pct = (comp['score'] / comp['max'] * 100) if comp['max'] > 0 else 0

            # Color - untuk distribution, score tinggi = danger (red)
            if pct >= 70:
                bar_color = 'danger'  # High distribution = red
            elif pct >= 50:
                bar_color = 'warning'
            elif pct >= 30:
                bar_color = 'info'
            else:
                bar_color = 'success'  # Low distribution = green

            component_bars.append(
                html.Div([
                    html.Div([
                        html.Small(component_labels.get(comp_key, comp_key), className="text-muted"),
                        html.Small(f"{comp['score']:.0f}/{comp['max']}", className="float-end")
                    ], className="d-flex justify-content-between"),
                    dbc.Progress(
                        value=pct,
                        color=bar_color,
                        className="mb-2",
                        style={"height": "8px"}
                    )
                ], className="mb-1")
            )

    # Detail items
    detail_items = [html.Li(detail, className="small") for detail in dist_data.get('details', [])]

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                "Distribution Score ",
                dbc.Badge(
                    f"{dist_data['score']:.0f}",
                    color="danger" if dist_data['score'] >= 55 else "warning" if dist_data['score'] >= 40 else "success",
                    className="ms-2"
                ),
                html.I(className="fas fa-info-circle ms-2 text-muted", id="dist-score-info", style={"cursor": "pointer"})
            ], className="mb-0 d-flex align-items-center"),
            dbc.Tooltip(
                "Distribution Score mengukur sinyal distribusi/jual. Score tinggi = pertimbangkan jual.",
                target="dist-score-info"
            )
        ]),
        dbc.CardBody([
            # Score Display
            html.Div([
                html.H1(f"{dist_data['score']:.0f}", className="display-4 mb-0 fw-bold"),
                html.Small("/100", className="text-muted")
            ], className="text-center mb-3", style={
                "backgroundColor": dist_data.get('color', '#6c757d') + "20",
                "padding": "20px",
                "borderRadius": "10px",
                "border": f"2px solid {dist_data.get('color', '#6c757d')}"
            }),

            # Signal Badge
            html.Div([
                dbc.Badge(
                    dist_data.get('signal', 'N/A'),
                    color="danger" if 'SELL' in dist_data.get('signal', '') else "warning" if 'REDUCE' in dist_data.get('signal', '') else "success",
                    className="fs-6 mb-2"
                ),
                html.P(dist_data.get('interpretation', ''), className="text-muted small mb-0")
            ], className="text-center mb-3"),

            # Phase indicator
            html.Div([
                html.Strong("Phase: "),
                dbc.Badge(
                    dist_data.get('phase', 'UNKNOWN'),
                    color={
                        'DISTRIBUTION': 'danger',
                        'EARLY DISTRIBUTION': 'warning',
                        'MARKUP ENDING': 'info',
                        'MARKUP': 'success',
                        'ACCUMULATION/MARKUP': 'success'
                    }.get(dist_data.get('phase', ''), 'secondary')
                )
            ], className="text-center mb-3"),

            # Component Breakdown
            html.H6("Component Breakdown:", className="mb-3"),
            html.Div(component_bars),

            # Details
            html.Hr(),
            html.H6("Calculation Details:", className="mb-2"),
            html.Ul(detail_items if detail_items else [
                html.Li("No data available", className="text-muted small")
            ], className="small mb-3", style={"paddingLeft": "20px"}),

            # Score Guide
            html.Hr(),
            html.Div([
                html.H6("Score Guide:", className="text-danger mb-2"),
                html.Ul([
                    html.Li([html.Strong(">=70: ", style={"color": "#dc3545"}), "STRONG SELL - Exit Position"]),
                    html.Li([html.Strong("55-69: ", style={"color": "#fd7e14"}), "SELL WARNING - Consider Selling"]),
                    html.Li([html.Strong("40-54: ", style={"color": "#ffc107"}), "WATCH - Reduce Position"]),
                    html.Li([html.Strong("25-39: ", style={"color": "#17a2b8"}), "MINOR - Use Trail Stop"]),
                    html.Li([html.Strong("<25: ", style={"color": "#28a745"}), "SAFE - Hold Position"]),
                ], className="small")
            ])
        ])
    ])


# ============================================================
# METRIC EXPLANATIONS (untuk user minimal knowledge)
# ============================================================
METRIC_EXPLANATIONS = {
    'composite_score': {
        'title': 'Composite Score',
        'short': 'Skor gabungan dari semua indikator untuk menentukan apakah layak beli/jual.',
        'detail': '''
Score ini menggabungkan 6 indikator utama:
* Broker Sensitivity (20%) - Apakah broker "pintar" sedang akumulasi?
* Foreign Flow (20%) - Apakah investor asing masuk atau keluar?
* Smart Money (15%) - Apakah ada tanda pembelian besar tersembunyi?
* Price Position (15%) - Posisi harga terhadap rata-rata pergerakan
* Accumulation (15%) - Apakah sedang dalam fase akumulasi?
* Volume Analysis (15%) - Apakah volume di atas rata-rata?

LAYER 1 FILTER: Syarat minimum (N Foreign >= 3 hari, RVOL >= 1.2x)
Jika tidak lolos, skor dibatasi maksimal 60-75.

Interpretasi:
>= 75 = STRONG BUY (semua sinyal align, momentum kuat)
60-74 = BUY (mayoritas sinyal positif)
45-59 = WATCH (sinyal mixed, pantau terus)
< 45 = NO ENTRY (sinyal belum mendukung)
'''
    },
    'broker_sensitivity': {
        'title': 'A. Broker Sensitivity',
        'short': 'Seberapa akurat broker tertentu dalam memprediksi kenaikan harga.',
        'detail': '''
Broker Sensitivity mengukur seberapa sering broker tertentu
berhasil "menebak" kenaikan harga.

Metrics:
* Win Rate = % kejadian broker akumulasi ^ harga naik >=10%
* Lead Time = Berapa hari sebelum naik, broker mulai beli
* Score = Gabungan dari Win Rate, Lead Time, dan Korelasi

Contoh: Jika broker MS punya Win Rate 70% dan Lead Time 3 hari,
artinya ketika MS beli, 70% kemungkinan harga naik >=10% dalam 10 hari,
dan biasanya naik sekitar 3 hari setelah MS mulai beli.
'''
    },
    'foreign_flow': {
        'title': 'B. Foreign Flow',
        'short': 'Aliran dana investor asing (apakah masuk atau keluar).',
        'detail': '''
Foreign Flow menunjukkan apakah investor asing (institusi besar)
sedang membeli atau menjual saham ini.

Indikator:
* INFLOW = Asing beli lebih banyak (positif untuk harga)
* OUTFLOW = Asing jual lebih banyak (negatif untuk harga)
* Consistency = Berapa hari berturut-turut inflow/outflow
* Momentum = Perubahan dibanding kemarin (akselerasi)

Kenapa penting? Investor asing biasanya punya riset lebih dalam
dan dana besar. Jika mereka masuk, seringkali harga ikut naik.
'''
    },
    'smart_money': {
        'title': 'C. Smart Money',
        'short': 'Deteksi pembelian besar oleh institusi/bandar.',
        'detail': '''
Smart Money Indicator mencari pola pembelian "tersembunyi"
dari pemain besar (institusi/bandar).

Cara deteksi:
* Volume naik TAPI frekuensi rendah = transaksi besar, sedikit pelaku
* Volume naik DAN frekuensi naik = banyak retail ikut-ikutan (FOMO)

Skor tinggi (Strong Accumulation) berarti:
Ada pembelian besar yang "diam-diam" oleh pemain besar.
Ini sering terjadi sebelum harga naik signifikan.

Skor rendah (Retail FOMO) berarti:
Banyak retail beli, biasanya tanda harga sudah kemahalan.
'''
    },
    'price_position': {
        'title': 'D. Price Position',
        'short': 'Posisi harga saat ini terhadap rata-rata pergerakan.',
        'detail': '''
Price Position menganalisis posisi harga terhadap berbagai acuan:

* Close vs Avg = Harga penutupan vs rata-rata hari ini
* Price vs MA5 = Harga vs rata-rata 5 hari
* Price vs MA20 = Harga vs rata-rata 20 hari
* Distance from Low = Jarak dari titik terendah 20 hari
* Breakout = Apakah tembus level tertinggi 5 hari?

Bullish = Harga di atas rata-rata (cenderung naik)
Bearish = Harga di bawah rata-rata (cenderung turun)

Ideal: Beli saat harga dekat support (bawah) tapi indikator lain positif.
'''
    },
    'accumulation_phase': {
        'title': 'E. Accumulation Phase',
        'short': 'Apakah saham sedang dalam fase pengumpulan sebelum naik?',
        'detail': '''
Accumulation Phase mendeteksi apakah saham sedang dikumpulkan
oleh pemain besar sebelum "diterbangkan".

Ciri-ciri fase akumulasi:
* Harga sideways (bergerak dalam range kecil, <10%)
* Volume mulai meningkat
* Foreign flow cenderung positif
* Broker sensitif mulai masuk
* Belum breakout

Jika semua kriteria terpenuhi = "STRONG ACCUMULATION"
Ini adalah waktu IDEAL untuk mulai mengumpulkan posisi.

Setelah akumulasi selesai, biasanya terjadi BREAKOUT (harga melonjak).
'''
    },
    'volume_analysis': {
        'title': 'F. Volume Analysis',
        'short': 'Analisis volume relatif (RVOL) dan tren volume-harga.',
        'detail': '''
Volume Analysis mengukur aktivitas trading dibandingkan rata-rata.

RVOL (Relative Volume) = Volume Hari Ini / Avg Volume 20 Hari:
* >= 2.0x = Very High (aktivitas sangat tinggi, perhatian besar)
* >= 1.5x = High (aktivitas tinggi)
* >= 1.2x = Above Average (di atas rata-rata)
* >= 0.8x = Normal
* < 0.8x = Low (aktivitas rendah, kurang menarik)

Volume-Price Trend (VPT):
* Volume naik + Harga naik = BULLISH (akumulasi kuat)
* Volume naik + Harga turun = DISTRIBUTION (distribusi/jual)
* Volume turun + Harga naik = WEAK RALLY (kenaikan lemah)
* Volume turun + Harga turun = CONSOLIDATION

RVOL tinggi + VPT Bullish = Sinyal akumulasi kuat!
'''
    },
    'buy_signal': {
        'title': 'Buy Signal Tracker',
        'short': 'Melacak kapan sinyal beli dimulai untuk menghindari FOMO.',
        'detail': '''
Buy Signal Tracker membantu Anda menghindari FOMO (Fear Of Missing Out)
dengan menunjukkan kapan sinyal beli PERTAMA muncul.

Cara baca:
* Tanggal Sinyal = Kapan sinyal beli pertama terdeteksi
* Harga Saat Sinyal = Harga saat sinyal muncul
* Harga Sekarang = Harga terkini
* Perubahan = Berapa persen harga sudah naik/turun dari sinyal

ZONE:
* SAFE (hijau) = Masih aman beli, harga dekat dengan sinyal (<3%)
* MODERATE (biru) = Boleh beli cicil, jangan all-in (3-7%)
* CAUTION (kuning) = Tunggu pullback lebih baik (7-12%)
* FOMO ALERT (merah) = Sudah terlambat, jangan kejar (>12%)
'''
    },
    'avg_buy': {
        'title': 'Avg Buy Broker',
        'short': 'Rata-rata harga beli broker untuk menentukan support level.',
        'detail': '''
Avg Buy menunjukkan rata-rata harga beli setiap broker.

Kenapa penting?
* Broker dengan Avg Buy > Harga Sekarang = Sedang RUGI (floating loss)
* Broker yang rugi cenderung akan DEFEND posisi mereka
* Area Avg Buy broker besar = SUPPORT LEVEL potensial

Contoh:
Jika broker XL punya Avg Buy di 1850 dan harga sekarang 1700:
- XL sedang rugi 8.8%
- Jika harga turun mendekati 1700-1750, XL mungkin akan beli lagi
- Area 1750-1850 menjadi SUPPORT yang kuat

Strategi: Beli di area support (sekitar Avg Buy broker besar)
'''
    },
    'win_rate': {
        'title': 'Win Rate',
        'short': 'Persentase keberhasilan broker memprediksi kenaikan.',
        'detail': '''
Win Rate = % kejadian di mana:
Broker akumulasi ^ Harga naik >=10% dalam 10 hari berikutnya

Contoh: Win Rate 60% berarti:
Dari 10 kali broker ini akumulasi, 6 kali harga naik >=10%.

Win Rate tinggi (>50%) = Broker ini "pintar", ikuti gerakannya
Win Rate rendah (<30%) = Broker ini kurang akurat, jangan terlalu percaya
'''
    },
    'lead_time': {
        'title': 'Lead Time',
        'short': 'Berapa hari sebelum harga naik, broker mulai akumulasi.',
        'detail': '''
Lead Time = Rata-rata berapa hari SEBELUM harga naik,
broker ini mulai melakukan akumulasi.

Contoh: Lead Time 3 hari berarti:
Rata-rata, broker ini mulai beli 3 hari sebelum harga naik.

Lead Time pendek (1-3 hari) = Broker ini masuk mendekati waktu breakout
Lead Time panjang (5-10 hari) = Broker ini sabar mengumpulkan

Strategi: Jika broker dengan Lead Time 3 hari baru mulai akumulasi,
perkirakan harga bisa naik dalam 3 hari ke depan.
'''
    }
}


def create_help_icon(metric_key: str) -> html.Span:
    """Create a help icon with tooltip explanation"""
    explanation = METRIC_EXPLANATIONS.get(metric_key, {})
    if not explanation:
        return html.Span()

    return html.Span([
        html.I(className="fas fa-question-circle text-muted ms-2", style={"fontSize": "12px"}),
        dbc.Tooltip(
            [
                html.Strong(explanation.get('title', '')),
                html.Br(),
                html.Small(explanation.get('short', ''))
            ],
            target=f"help-{metric_key}",
            placement="top"
        )
    ], id=f"help-{metric_key}", style={"cursor": "pointer"})

# ============================================================
# NAVBAR WITH STOCK SELECTOR
# ============================================================

def create_navbar():
    # Get stocks with fallback - callback will refresh options on page load
    try:
        stocks = get_available_stocks()
    except Exception as e:
        print(f"Warning: Failed to get stocks in navbar: {e}")
        stocks = []

    # Default value - will be updated by callback if stocks available
    default_value = stocks[0] if stocks else 'CDIA'

    return dbc.Navbar(
        dbc.Container([
            # LEFT SIDE: Brand + Stock Selector + Content Menus
            html.Div([
                # Brand
                dbc.NavbarBrand("HermanStock", href="/", className="me-2", style={"fontSize": "0.95rem"}),

                # Stock Selector - searchable dropdown
                # Value will be synced with URL by callback
                dcc.Dropdown(
                    id='stock-selector',
                    options=[{'label': s, 'value': s} for s in stocks] if stocks else [],
                    value=None,  # Will be set by sync_dropdown_with_url callback
                    style={'width': '100px', 'minWidth': '100px'},
                    clearable=False,
                    searchable=True,
                    placeholder="Emiten",
                    className="stock-dropdown me-2",
                    persistence=False  # Don't persist value between page loads
                ),

                # Desktop content menus
                dbc.Nav([
                    dbc.NavItem(dcc.Link(dbc.Button("Home", color="warning", size="sm", className="fw-bold text-white px-2 py-1"), href="/")),
                    dbc.NavItem(dcc.Link(dbc.Button("Dashboard", color="warning", size="sm", className="fw-bold text-white px-2 py-1"), href="/dashboard")),
                    dbc.NavItem(dcc.Link(dbc.Button("Analysis", color="warning", size="sm", className="fw-bold text-white px-2 py-1"), href="/analysis")),
                    dbc.NavItem(dcc.Link(dbc.Button([html.I(className="fas fa-newspaper me-1"), "News"], color="info", size="sm", className="fw-bold text-white px-2 py-1"), href="/news")),
                    dbc.NavItem(dcc.Link(dbc.Button("Discussion", color="info", size="sm", className="fw-bold text-white px-2 py-1"), href="/discussion")),
                    dbc.NavItem(dcc.Link(dbc.Button("Upload", color="warning", size="sm", className="fw-bold text-white px-2 py-1"), href="/upload")),
                ], className="d-none d-lg-flex", navbar=True, style={"gap": "3px"}),
            ], className="d-flex align-items-center flex-grow-1"),

            # SEPARATOR - Visual divider between content and auth
            html.Div("|", className="d-none d-lg-block text-muted mx-3", style={"fontSize": "1.5rem", "opacity": "0.3"}),

            # RIGHT SIDE: Theme + Auth (grouped together)
            html.Div([
                # Theme toggle
                dbc.Button(
                    html.I(className="fas fa-sun", id="theme-icon"),
                    id="theme-toggle",
                    color="link",
                    size="sm",
                    className="text-warning px-2",
                    title="Toggle Light/Dark Mode"
                ),

                # Auth buttons desktop (shown when not logged in) - visibility controlled by callback
                html.Div([
                    dcc.Link(dbc.Button([html.I(className="fas fa-sign-in-alt me-1"), "Login"], color="success", size="sm", className="fw-bold text-white px-2 py-1"), href="/login"),
                    dcc.Link(dbc.Button([html.I(className="fas fa-user-plus me-1"), "Sign Up"], color="light", size="sm", className="fw-bold text-dark px-2 py-1"), href="/signup"),
                ], id="auth-buttons-desktop", className="d-lg-flex", style={"gap": "3px", "display": "none"}),

                # Logout section desktop (shown when logged in) - visibility controlled by callback
                html.Div([
                    html.Span(id="user-display-desktop", className="text-light me-2 small"),
                    dbc.Button([html.I(className="fas fa-sign-out-alt me-1"), "Logout"], id="logout-btn-desktop", color="danger", size="sm", className="fw-bold text-white px-2 py-1"),
                ], id="logout-section-desktop", className="align-items-center", style={"display": "none"}),

                # Hamburger toggle button for mobile
                dbc.Button(
                    html.I(className="fas fa-bars"),
                    id="navbar-toggler",
                    color="warning",
                    size="sm",
                    className="d-lg-none ms-2",
                    n_clicks=0,
                    style={"border": "none"}
                ),
            ], className="d-flex align-items-center"),

            # Mobile dropdown menu - only visible when hamburger clicked
            dbc.Collapse(
                dbc.Nav([
                    dbc.NavItem(dcc.Link(dbc.Button("Home", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Dashboard", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/dashboard", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Analysis", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/analysis", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button([html.I(className="fas fa-newspaper me-1"), "News"], color="info", size="sm", className="fw-bold text-white mb-1 w-100"), href="/news", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Discussion", color="info", size="sm", className="fw-bold text-white mb-1 w-100"), href="/discussion", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Upload", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/upload", refresh=True)),
                    html.Hr(className="my-2", style={"borderColor": "white"}),
                    # Auth buttons - Login/Sign Up (shown when not logged in)
                    html.Div([
                        dcc.Link(dbc.Button([html.I(className="fas fa-sign-in-alt me-1"), "Login"], color="success", size="sm", className="fw-bold text-white mb-1 w-100"), href="/login", refresh=True),
                        dcc.Link(dbc.Button([html.I(className="fas fa-user-plus me-1"), "Sign Up"], color="light", size="sm", className="fw-bold text-dark mb-1 w-100"), href="/signup", refresh=True),
                    ], id="auth-buttons-mobile"),
                    # Logout button (shown when logged in)
                    html.Div([
                        html.Div(id="user-display-mobile", className="text-white small mb-1 text-center"),
                        dbc.Button([html.I(className="fas fa-sign-out-alt me-1"), "Logout"], id="logout-btn-mobile", color="danger", size="sm", className="fw-bold text-white w-100"),
                    ], id="logout-section-mobile", style={"display": "none"}),
                ], className="p-2 flex-column d-lg-none", navbar=True, style={"backgroundColor": "#fd7e14", "borderRadius": "8px"}),
                id="navbar-collapse",
                is_open=False,
                navbar=True,
                className="d-lg-none"
            ),
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-2 py-1",
        id="main-navbar"
    )


# ============================================================
# PAGE: LANDING / HOME
# ============================================================

def create_landing_page(is_admin: bool = False, is_logged_in: bool = False, is_expired: bool = False):
    """Create landing page with stock selection and overview using unified analysis data from 3 submenus.
    During maintenance, regular users only see stocks from snapshot."""
    stocks = get_available_stocks_for_user(is_admin)

    # Check if user can access analysis (logged in and not expired)
    can_access_analysis = is_logged_in and not is_expired

    # Get all V10 running stocks (cached for 5 minutes - fast!)
    v10_running_stocks = get_all_v10_running_stocks()

    if not stocks:
        return html.Div([
            dbc.Alert("Tidak ada data saham. Silakan upload data terlebih dahulu.", color="warning"),
            dbc.Button("Upload Data", href="/upload", color="primary")
        ])

    # Build stock cards with unified analysis summary
    stock_cards = []
    for stock_code in stocks:
        try:
            # Get unified analysis from 3 submenus (Fundamental, S&R, Accumulation)
            unified = get_unified_analysis_summary(stock_code)
            decision = unified.get('decision', {})
            accum = unified.get('accumulation', {})
            fundamental = unified.get('fundamental', {})
            sr = unified.get('support_resistance', {})
            summary = accum.get('summary', {})
            confidence = accum.get('confidence', {})
            markup_trigger = accum.get('markup_trigger', {})
            impulse_signal = accum.get('impulse_signal', {})

            # Get current price from S&R or Accum
            current_price = sr.get('current_price', 0) or accum.get('current_price', 0)
            entry_zone = unified.get('entry_zone', {})
            invalidation = unified.get('invalidation', 0)

            # Get basic data for additional info
            price_df = get_price_data(stock_code)
            price_change = 0
            if not price_df.empty and len(price_df) >= 2:
                price_df = price_df.sort_values('date') if 'date' in price_df.columns else price_df
                close_col = 'close_price' if 'close_price' in price_df.columns else 'close'
                if close_col in price_df.columns:
                    today = price_df[close_col].iloc[-1]
                    yesterday = price_df[close_col].iloc[-2]
                    if yesterday > 0:
                        price_change = ((today - yesterday) / yesterday) * 100

            # Determine action from decision
            action = decision.get('action', 'WAIT')
            action_color = decision.get('color', 'secondary')
            action_icon = decision.get('icon', '[~]')

            # Overall signal from accumulation
            overall_signal = summary.get('overall_signal', 'NETRAL')
            signal_color = "success" if overall_signal == 'AKUMULASI' else "danger" if overall_signal == 'DISTRIBUSI' else "secondary"

            # Get profile and fundamental data for teaser display
            profile = get_stock_profile(stock_code)

            # Company info from profile
            company_name = profile.get('company_name', stock_code) if profile else stock_code
            sector = profile.get('sector', '-') if profile else '-'
            industry = profile.get('industry', '-') if profile else '-'

            # Fundamental data
            per = fundamental.get('per', 0)
            pbv = fundamental.get('pbv', 0)
            roe = fundamental.get('roe', 0)
            has_fundamental = fundamental.get('has_data', False)

            # Check if V10 is running for this stock and get position data
            v10_position_data = v10_running_stocks.get(stock_code)
            v10_running = v10_position_data is not None
            running_pnl = v10_position_data.get('current_pnl', 0) if v10_position_data else 0

            # Create attractive TEASER card with Profile & Fundamental
            card = dbc.Col([
                dbc.Card([
                    # Header - Stock code and company name (blinking bg if V10 running)
                    dbc.CardHeader([
                        html.Div([
                            html.Div([
                                # Stock code - green if running, orange if not
                                html.H3(
                                    html.A(
                                        stock_code,
                                        href=f"/analysis?stock={stock_code}",
                                        style={"textDecoration": "none"}
                                    ) if can_access_analysis else stock_code,
                                    className="mb-0 fw-bold"
                                ),
                                html.Small(company_name[:25] + "..." if len(company_name) > 25 else company_name, className="text-muted d-block")
                            ]),
                            html.Div([
                                dbc.Badge([
                                    html.I(className="fas fa-play-circle me-1"),
                                    "RUNNING"
                                ], color="success", className="fs-6 px-2 py-1 me-1") if v10_running else None,
                                dbc.Badge([
                                    html.I(className="fas fa-crown me-1"),
                                    "Premium"
                                ], color="warning", className="fs-6 px-3 py-2")
                            ], className="d-flex align-items-center")
                        ], className="d-flex align-items-center justify-content-between")
                    ], className="v10-running-header" if v10_running else "bg-dark",
                       style={"background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"} if not v10_running else {}),

                    dbc.CardBody([
                        # Price & Change & P/L Row
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("Harga Terakhir", className="text-muted d-block"),
                                    html.H4(f"Rp {current_price:,.0f}", className="mb-0 text-warning"),
                                ], className="text-center")
                            ], width=4 if v10_running else 6),
                            dbc.Col([
                                html.Div([
                                    html.Small("Perubahan", className="text-muted d-block"),
                                    html.H4(
                                        f"{price_change:+.1f}%",
                                        className=f"mb-0 text-{'success' if price_change > 0 else 'danger' if price_change < 0 else 'muted'}"
                                    ),
                                ], className="text-center")
                            ], width=4 if v10_running else 6),
                            dbc.Col([
                                html.Div([
                                    html.Small("P/L Running", className="text-muted d-block"),
                                    html.H4(
                                        f"{running_pnl:+.1f}%",
                                        className=f"mb-0 text-{'primary' if running_pnl >= 0 else 'danger'}"
                                    ),
                                ], className="text-center")
                            ], width=4) if v10_running else None,
                        ], className="mb-3"),

                        html.Hr(className="my-2"),

                        # Profile Section
                        html.Div([
                            html.H6([
                                html.I(className="fas fa-building me-2 text-info"),
                                "Profil Perusahaan"
                            ], className="mb-2 small"),
                            dbc.Row([
                                dbc.Col([
                                    html.Small("Sektor", className="text-muted d-block"),
                                    html.Strong(sector[:15] if sector else "-", className="text-light small"),
                                ], width=6),
                                dbc.Col([
                                    html.Small("Industri", className="text-muted d-block"),
                                    html.Strong(industry[:15] if industry else "-", className="text-light small"),
                                ], width=6),
                            ])
                        ], className="mb-3 p-2 rounded", style={"backgroundColor": "rgba(23, 162, 184, 0.1)"}),

                        # Fundamental Section
                        html.Div([
                            html.H6([
                                html.I(className="fas fa-chart-pie me-2 text-success"),
                                "Fundamental"
                            ], className="mb-2 small"),
                            dbc.Row([
                                dbc.Col([
                                    html.Div([
                                        html.Small("PER", className="text-muted d-block"),
                                        html.Strong(
                                            f"{per:.1f}x" if has_fundamental and per > 0 else "-",
                                            className=f"text-{'success' if per < 15 else 'warning' if per < 25 else 'danger'}" if has_fundamental and per > 0 else "text-muted"
                                        ),
                                    ], className="text-center")
                                ], width=4),
                                dbc.Col([
                                    html.Div([
                                        html.Small("PBV", className="text-muted d-block"),
                                        html.Strong(
                                            f"{pbv:.1f}x" if has_fundamental and pbv > 0 else "-",
                                            className=f"text-{'success' if pbv < 1.5 else 'warning' if pbv < 3 else 'danger'}" if has_fundamental and pbv > 0 else "text-muted"
                                        ),
                                    ], className="text-center")
                                ], width=4),
                                dbc.Col([
                                    html.Div([
                                        html.Small("ROE", className="text-muted d-block"),
                                        html.Strong(
                                            f"{roe:.1f}%" if has_fundamental and roe > 0 else "-",
                                            className=f"text-{'success' if roe > 15 else 'warning' if roe > 10 else 'danger'}" if has_fundamental and roe > 0 else "text-muted"
                                        ),
                                    ], className="text-center")
                                ], width=4),
                            ])
                        ], className="mb-3 p-2 rounded", style={"backgroundColor": "rgba(40, 167, 69, 0.1)"}),

                        # Valuation Badge
                        html.Div([
                            dbc.Badge(
                                fundamental.get('valuation', 'N/A'),
                                color=fundamental.get('valuation_color', 'secondary'),
                                className="me-2"
                            ) if has_fundamental else html.Span(),
                            html.Small("Valuasi berdasarkan PER & PBV", className="text-muted")
                        ], className="text-center mb-3") if has_fundamental else html.Div(),

                        html.Hr(className="my-2"),

                        # CTA
                        html.Div([
                            html.P([
                                html.I(className="fas fa-unlock-alt me-2 text-warning"),
                                "Lihat sinyal & rekomendasi trading"
                            ], className="text-center small mb-2"),
                        ]),

                        # Buttons
                        html.Div([
                            dbc.Button([
                                html.I(className="fas fa-user-plus me-1"),
                                "Daftar Gratis"
                            ], href="/signup", color="warning", size="sm", className="me-1 flex-grow-1"),
                            dbc.Button([
                                html.I(className="fas fa-sign-in-alt me-1"),
                                "Login"
                            ], href="/login", color="outline-light", size="sm", className="flex-grow-1"),
                        ], className="d-flex")
                    ])
                ], className="h-100 shadow", color="dark", outline=True,
                   style={"borderColor": "var(--bs-warning)", "borderWidth": "2px", "background": "linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%)"})
            ], md=6, lg=4, className="mb-4 stock-card", id=f"stock-card-{stock_code}")

            stock_cards.append(card)

        except Exception as e:
            # Fallback card for error
            card = dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4(stock_code, className="mb-0")),
                    dbc.CardBody([
                        dbc.Alert(f"Error loading data: {str(e)[:50]}", color="warning", className="small"),
                        dbc.Button("Dashboard", href=f"/dashboard?stock={stock_code}", color="primary", size="sm")
                    ])
                ], className="h-100", color="dark", outline=True)
            ], md=6, lg=4, className="mb-4 stock-card", id=f"stock-card-{stock_code}-error")
            stock_cards.append(card)

    return html.Div([
        # Hero Section
        dbc.Container([
            html.Div([
                html.H1([
                    html.I(className="fas fa-chart-bar me-3"),
                    "HermanStock Analytics"
                ], className="display-5 text-center mb-3"),
                html.P(
                    "Platform analisis saham dengan metode Wyckoff & Bandarmology",
                    className="lead text-center text-muted mb-3"
                ),
                html.Div([
                    dbc.Badge([html.I(className="fas fa-robot me-1"), "AI-Powered"], color="info", className="me-2"),
                    dbc.Badge([html.I(className="fas fa-chart-line me-1"), "Real-time Data"], color="success", className="me-2"),
                    dbc.Badge([html.I(className="fas fa-users me-1"), "Broker Flow"], color="warning"),
                ], className="text-center mb-3"),
                html.P([
                    html.I(className="fas fa-star text-warning me-2"),
                    "Daftar GRATIS untuk akses analisis lengkap, sinyal trading, dan rekomendasi entry"
                ], className="text-center text-info small"),
                html.Hr(className="my-4"),
            ], className="py-4")
        ]),

        # Stock Selection
        dbc.Container([
            html.Div([
                # Title and search row
                html.Div([
                    html.H4([
                        html.I(className="fas fa-list-alt me-2"),
                        f"Pilih Emiten ({len(stocks)} tersedia)"
                    ], className="mb-0 me-3"),
                    # Search input
                    html.Div([
                        dbc.InputGroup([
                            dbc.InputGroupText(html.I(className="fas fa-search"), style={"backgroundColor": "#16213e", "borderColor": "#0f3460", "color": "#17a2b8"}),
                            dbc.Input(
                                id="landing-stock-search",
                                placeholder="Cari emiten...",
                                type="text",
                                style={"backgroundColor": "#1a1a2e", "borderColor": "#0f3460", "color": "#fff", "maxWidth": "150px"}
                            ),
                        ], size="sm"),
                    ], className="me-3"),
                    # Info badge
                    html.Div([
                        dbc.Badge([html.I(className="fas fa-lock me-1"), "Data Premium"], color="info", className="me-1 small"),
                        dbc.Badge([html.I(className="fas fa-unlock me-1"), "Signup untuk akses"], color="warning", className="small"),
                    ], className="d-inline-block")
                ], className="d-flex align-items-center flex-wrap gap-2"),
            ], className="mb-4"),

            dbc.Row(stock_cards),

            # CTA Section - Why Sign Up
            html.Hr(className="my-4"),
            dbc.Card([
                dbc.CardBody([
                    html.H4([
                        html.I(className="fas fa-gift me-2 text-warning"),
                        "Keuntungan Member"
                    ], className="text-center mb-4"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-signal fa-2x text-success mb-2"),
                                html.H6("Sinyal Trading", className="mb-1"),
                                html.Small("BUY/SELL/HOLD recommendations", className="text-muted")
                            ], className="text-center p-3")
                        ], md=3),
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-crosshairs fa-2x text-info mb-2"),
                                html.H6("Entry & Exit Zone", className="mb-1"),
                                html.Small("Level harga optimal untuk trading", className="text-muted")
                            ], className="text-center p-3")
                        ], md=3),
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-users fa-2x text-warning mb-2"),
                                html.H6("Broker Flow", className="mb-1"),
                                html.Small("Pantau pergerakan smart money", className="text-muted")
                            ], className="text-center p-3")
                        ], md=3),
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-bell fa-2x text-danger mb-2"),
                                html.H6("Alert System", className="mb-1"),
                                html.Small("Notifikasi sinyal penting", className="text-muted")
                            ], className="text-center p-3")
                        ], md=3),
                    ], className="mb-4"),
                    html.Div([
                        dbc.Button([
                            html.I(className="fas fa-user-plus me-2"),
                            "Daftar Sekarang - GRATIS!"
                        ], href="/signup", color="warning", size="lg", className="px-5")
                    ], className="text-center")
                ])
            ], className="mb-4", style={"background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)", "border": "2px solid var(--bs-warning)"})
        ], fluid=True)
    ])

# ============================================================
# PAGE: DISCUSSION FORUM
# ============================================================

ADMIN_PASSWORD = "12153800"  # Same as upload password for admin actions

def get_profanity_words():
    """Get profanity words from database"""
    query = "SELECT keyword, level FROM forum_profanity ORDER BY level"
    results = execute_query(query)
    words = {1: [], 2: [], 3: []}
    if results:
        for r in results:
            words[r['level']].append(r['keyword'].lower())
    return words

def check_profanity(text: str) -> dict:
    """Check text for profanity - returns level and matched words"""
    import re
    text_lower = text.lower()
    words = get_profanity_words()

    def is_whole_word_match(text, word):
        """Check if word appears as whole word, not part of another word"""
        # Use word boundary regex for accurate matching
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text))

    # Check level 1 (hard block) - whole word only
    for word in words[1]:
        if is_whole_word_match(text_lower, word):
            return {'level': 1, 'word': word, 'action': 'block'}

    # Check level 2 (provokatif) - can be substring for phrases
    for word in words[2]:
        if word in text_lower:
            return {'level': 2, 'word': word, 'action': 'flag'}

    # Check level 3 (warning) - can be substring for phrases
    for word in words[3]:
        if word in text_lower:
            return {'level': 3, 'word': word, 'action': 'warning'}

    return {'level': 0, 'word': None, 'action': 'ok'}

# ============================================================
# USER AUTHENTICATION FUNCTIONS
# ============================================================

import hashlib
import secrets
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email configuration - UPDATE THESE WITH YOUR SMTP SETTINGS
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'haborherman@gmail.com',  # Your Gmail address
    'sender_password': '',  # App password (need to set up)
    'site_url': 'https://www.hermanstock.com'
}

def hash_password(password: str) -> str:
    """Hash password using SHA256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash"""
    try:
        salt, hash_value = stored_hash.split(':')
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash == hash_value
    except:
        return False

def validate_password(password: str) -> tuple:
    """Validate password requirements - min 6 chars, must have letters and numbers"""
    if len(password) < 6:
        return False, "Password minimal 6 karakter"
    if not re.search(r'[a-zA-Z]', password):
        return False, "Password harus mengandung huruf"
    if not re.search(r'[0-9]', password):
        return False, "Password harus mengandung angka"
    return True, "OK"

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_verification_token() -> str:
    """Generate a random verification token"""
    return secrets.token_urlsafe(32)

def create_user(email: str, username: str, password: str) -> dict:
    """Create a new user with verification token"""
    # Validate inputs
    if not validate_email(email):
        return {'success': False, 'error': 'Format email tidak valid'}

    is_valid, msg = validate_password(password)
    if not is_valid:
        return {'success': False, 'error': msg}

    if len(username) < 3:
        return {'success': False, 'error': 'Username minimal 3 karakter'}

    # Check if email or username already exists
    check_query = "SELECT id FROM users WHERE email = %s OR username = %s"
    existing = execute_query(check_query, (email.lower(), username.lower()), use_cache=False)
    if existing:
        return {'success': False, 'error': 'Email atau username sudah terdaftar'}

    # Create user
    password_hash = hash_password(password)
    token = generate_verification_token()
    token_expiry = "CURRENT_TIMESTAMP + INTERVAL '24 hours'"

    insert_query = f"""
        INSERT INTO users (email, username, password_hash, plain_password, verification_token, token_expiry, member_type, member_start, member_end)
        VALUES (%s, %s, %s, %s, %s, {token_expiry}, 'trial', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '7 days')
        RETURNING id, verification_token
    """
    result = execute_query(insert_query, (email.lower(), username.lower(), password_hash, password, token), use_cache=False)

    if result:
        return {'success': True, 'user_id': result[0]['id'], 'token': token, 'email': email}
    return {'success': False, 'error': 'Gagal membuat akun'}

def verify_user_email(token: str) -> dict:
    """Verify user email with token"""
    # Find user with valid token
    query = """
        UPDATE users
        SET is_verified = TRUE, verification_token = NULL, token_expiry = NULL
        WHERE verification_token = %s AND token_expiry > CURRENT_TIMESTAMP AND is_verified = FALSE
        RETURNING id, email, username
    """
    result = execute_query(query, (token,), use_cache=False)

    if result:
        return {'success': True, 'user': result[0]}
    return {'success': False, 'error': 'Token tidak valid atau sudah kadaluarsa'}

def login_user(email: str, password: str) -> dict:
    """Login user and return user data"""
    query = """
        SELECT id, email, username, password_hash, is_verified, member_type, member_end
        FROM users WHERE email = %s
    """
    result = execute_query(query, (email.lower(),), use_cache=False)

    if not result:
        return {'success': False, 'error': 'Email tidak terdaftar'}

    user = result[0]

    if not verify_password(password, user['password_hash']):
        return {'success': False, 'error': 'Password salah'}

    if not user['is_verified']:
        return {'success': False, 'error': 'Email belum diverifikasi. Cek inbox email Anda.'}

    # Update last login
    update_query = "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s"
    execute_query(update_query, (user['id'],), fetch=False, use_cache=False)

    return {
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'member_type': user['member_type'],
            'member_end': user['member_end']
        }
    }

def get_user_membership_status(email: str) -> dict:
    """Get current membership status directly from database.
    Used to check real-time member_end when session might be stale."""
    query = """
        SELECT member_type, member_end, is_verified
        FROM users WHERE email = %s
    """
    result = execute_query(query, (email.lower(),), use_cache=False)
    if result:
        user = result[0]
        return {
            'member_type': user['member_type'],
            'member_end': user['member_end'],
            'is_verified': user['is_verified']
        }
    return None

def send_verification_email(email: str, token: str, username: str) -> dict:
    """Send verification email to user. Returns dict with success status and verification URL"""
    verification_url = f"{EMAIL_CONFIG['site_url']}/verify?token={token}"

    try:
        subject = "Verifikasi Email - HermanStock"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #17a2b8;">Selamat Datang di HermanStock!</h2>
                <p>Halo <strong>{username}</strong>,</p>
                <p>Terima kasih telah mendaftar di HermanStock. Silakan klik tombol di bawah untuk memverifikasi email Anda:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}"
                       style="background-color: #17a2b8; color: white; padding: 12px 30px;
                              text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Verifikasi Email
                    </a>
                </p>
                <p>Atau copy link berikut ke browser Anda:</p>
                <p style="background: #f5f5f5; padding: 10px; word-break: break-all;">{verification_url}</p>
                <p><strong>Link ini akan kadaluarsa dalam 24 jam.</strong></p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">
                    Jika Anda tidak mendaftar di HermanStock, abaikan email ini.
                </p>
            </div>
        </body>
        </html>
        """

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = email
        msg.attach(MIMEText(body, 'html'))

        # Send email only if password is configured
        if EMAIL_CONFIG['sender_password']:
            with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
                server.starttls()
                server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
                server.sendmail(EMAIL_CONFIG['sender_email'], email, msg.as_string())
            return {'sent': True, 'url': verification_url}
        else:
            # No email password configured - return URL for direct display
            print(f"[EMAIL] No SMTP configured. Verification URL for {email}: {verification_url}")
            return {'sent': False, 'url': verification_url}

    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email: {str(e)}")
        return {'sent': False, 'url': verification_url}

def get_user_by_id(user_id: int) -> dict:
    """Get user by ID"""
    query = """
        SELECT id, email, username, member_type, member_start, member_end, is_verified, last_login
        FROM users WHERE id = %s
    """
    result = execute_query(query, (user_id,), use_cache=False)
    return result[0] if result else None

def resend_verification(email: str) -> dict:
    """Resend verification email"""
    # Check if user exists and is not verified
    query = "SELECT id, username, is_verified FROM users WHERE email = %s"
    result = execute_query(query, (email.lower(),), use_cache=False)

    if not result:
        return {'success': False, 'error': 'Email tidak terdaftar'}

    user = result[0]
    if user['is_verified']:
        return {'success': False, 'error': 'Email sudah diverifikasi'}

    # Generate new token
    token = generate_verification_token()
    update_query = """
        UPDATE users SET verification_token = %s, token_expiry = CURRENT_TIMESTAMP + INTERVAL '24 hours'
        WHERE id = %s
    """
    execute_query(update_query, (token, user['id']), use_cache=False)

    # Send email
    if send_verification_email(email, token, user['username']):
        return {'success': True, 'message': 'Email verifikasi telah dikirim ulang'}
    return {'success': False, 'error': 'Gagal mengirim email'}


# ============================================================
# MEMBER MANAGEMENT FUNCTIONS
# ============================================================

def get_all_members():
    """Get all members (users) with calculated status"""
    query = """
        SELECT id, email, username as name, member_type, member_start as start_date,
            member_end as end_date, is_verified as is_active, last_login as last_online, created_at,
            CASE
                WHEN member_end IS NULL THEN FALSE
                WHEN member_end < CURRENT_TIMESTAMP THEN TRUE
                ELSE FALSE
            END as is_expired,
            CASE
                WHEN member_end IS NULL THEN NULL
                ELSE EXTRACT(DAY FROM (member_end - CURRENT_TIMESTAMP))
            END as days_remaining
        FROM users
        WHERE member_type IN ('trial', 'subscribe', 'admin')
        ORDER BY created_at DESC
    """
    return execute_query(query, use_cache=False) or []

def get_member_stats():
    """Get member statistics from users table"""
    query = """
        SELECT
            COUNT(*) FILTER (WHERE member_type = 'trial' AND is_verified = TRUE AND (member_end IS NULL OR member_end >= CURRENT_TIMESTAMP)) as active_trial,
            COUNT(*) FILTER (WHERE member_type IN ('subscribe', 'admin') AND is_verified = TRUE AND (member_end IS NULL OR member_end >= CURRENT_TIMESTAMP)) as active_subscribe,
            COUNT(*) FILTER (WHERE member_type = 'trial' AND (member_end < CURRENT_TIMESTAMP OR is_verified = FALSE)) as expired_trial,
            COUNT(*) FILTER (WHERE member_type IN ('subscribe', 'admin') AND (member_end < CURRENT_TIMESTAMP OR is_verified = FALSE)) as expired_subscribe,
            COUNT(*) FILTER (WHERE last_login >= CURRENT_TIMESTAMP - INTERVAL '15 minutes' AND member_type = 'trial') as online_trial,
            COUNT(*) FILTER (WHERE last_login >= CURRENT_TIMESTAMP - INTERVAL '15 minutes' AND member_type IN ('subscribe', 'admin')) as online_subscribe,
            COUNT(*) FILTER (WHERE member_type IN ('trial', 'subscribe', 'admin')) as total_members
        FROM users
        WHERE member_type IN ('trial', 'subscribe', 'admin')
    """
    result = execute_query(query, use_cache=False)
    if result and len(result) > 0:
        return result[0]
    return {
        'active_trial': 0, 'active_subscribe': 0,
        'expired_trial': 0, 'expired_subscribe': 0,
        'online_trial': 0, 'online_subscribe': 0,
        'total_members': 0
    }

def get_members_by_type(member_type: str):
    """Get users filtered by type with expiry info"""
    # For 'subscribe' tab, also show admin users
    if member_type == 'subscribe':
        query = """
            SELECT id, email, username as name, member_type, member_start as start_date, member_end as end_date,
                is_verified as is_active, last_login as last_online, created_at,
                CASE
                    WHEN member_end IS NULL THEN NULL
                    WHEN member_end < CURRENT_TIMESTAMP THEN 0
                    ELSE EXTRACT(DAY FROM (member_end - CURRENT_TIMESTAMP))
                END as days_remaining,
                CASE
                    WHEN last_login >= CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN TRUE
                    ELSE FALSE
                END as is_online
            FROM users
            WHERE member_type IN ('subscribe', 'admin')
            ORDER BY
                CASE WHEN is_verified AND (member_end IS NULL OR member_end >= CURRENT_TIMESTAMP) THEN 0 ELSE 1 END,
                member_end ASC
        """
        return execute_query(query, use_cache=False) or []
    else:
        query = """
            SELECT id, email, username as name, member_type, member_start as start_date, member_end as end_date,
                is_verified as is_active, last_login as last_online, created_at,
                CASE
                    WHEN member_end IS NULL THEN NULL
                    WHEN member_end < CURRENT_TIMESTAMP THEN 0
                    ELSE EXTRACT(DAY FROM (member_end - CURRENT_TIMESTAMP))
                END as days_remaining,
                CASE
                    WHEN last_login >= CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN TRUE
                    ELSE FALSE
                END as is_online
            FROM users
            WHERE member_type = %s
            ORDER BY
                CASE WHEN is_verified AND (member_end IS NULL OR member_end >= CURRENT_TIMESTAMP) THEN 0 ELSE 1 END,
                member_end ASC
        """
        return execute_query(query, (member_type,), use_cache=False) or []

def add_member(email: str, name: str, member_type: str):
    """Add new member to users table - trial gets 7 days, subscribe gets 30 days"""
    days = 7 if member_type == 'trial' else 30
    # Generate a random password for new member (they can reset later)
    temp_password = secrets.token_urlsafe(8)
    password_hash_val = hash_password(temp_password)

    query = f"""
        INSERT INTO users (email, username, password_hash, is_verified, member_type, member_start, member_end)
        VALUES (%s, %s, %s, TRUE, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '{days} days')
        ON CONFLICT (email) DO UPDATE SET
            username = EXCLUDED.username,
            member_type = EXCLUDED.member_type,
            member_start = CURRENT_TIMESTAMP,
            member_end = CURRENT_TIMESTAMP + INTERVAL '{days} days',
            is_verified = TRUE
        RETURNING id
    """
    return execute_query(query, (email.lower(), name, password_hash_val, member_type), use_cache=False)

def extend_member(member_id: int, days: int = 30):
    """Extend member subscription by days"""
    query = f"""
        UPDATE users
        SET member_end = CASE
                WHEN member_end < CURRENT_TIMESTAMP THEN CURRENT_TIMESTAMP + INTERVAL '{days} days'
                ELSE member_end + INTERVAL '{days} days'
            END,
            is_verified = TRUE
        WHERE id = %s
        RETURNING id
    """
    return execute_query(query, (member_id,), use_cache=False)

def deactivate_member(member_id: int):
    """Deactivate a member"""
    query = "UPDATE users SET is_verified = FALSE WHERE id = %s RETURNING id"
    return execute_query(query, (member_id,), use_cache=False)

def update_member_online(member_id: int):
    """Update member's last online timestamp"""
    query = "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s"
    execute_query(query, (member_id,), fetch=False, use_cache=False)


# ============================================================
# ACCOUNT MANAGEMENT FUNCTIONS (for Admin)
# ============================================================

def get_all_accounts():
    """Get all user accounts for admin management"""
    query = """
        SELECT id, email, username, password_hash, plain_password, member_type, is_verified,
               member_start, member_end, last_login, created_at
        FROM users
        ORDER BY created_at DESC
    """
    return execute_query(query, use_cache=False) or []

def get_account_by_id(user_id: int):
    """Get single account by ID"""
    query = "SELECT * FROM users WHERE id = %s"
    result = execute_query(query, (user_id,), use_cache=False)
    return result[0] if result else None

def update_account(user_id: int, username: str = None, password: str = None,
                   member_type: str = None, is_verified: bool = None):
    """Update user account - only update provided fields"""
    from datetime import datetime, timedelta

    updates = []
    params = []

    if username:
        updates.append("username = %s")
        params.append(username)

    if password:
        new_hash = hash_password(password)
        updates.append("password_hash = %s")
        params.append(new_hash)
        updates.append("plain_password = %s")
        params.append(password)

    if member_type:
        updates.append("member_type = %s")
        params.append(member_type)
        # Update member_end based on new member type
        updates.append("member_start = %s")
        params.append(datetime.now())
        if member_type in ['admin', 'superuser']:
            # Admin/Superuser: 100 years (essentially unlimited)
            updates.append("member_end = %s")
            params.append(datetime.now() + timedelta(days=36500))
        elif member_type == 'subscribe':
            # Subscribe: 30 days
            updates.append("member_end = %s")
            params.append(datetime.now() + timedelta(days=30))
        elif member_type == 'trial':
            # Trial: 7 days
            updates.append("member_end = %s")
            params.append(datetime.now() + timedelta(days=7))

    if is_verified is not None:
        updates.append("is_verified = %s")
        params.append(is_verified)

    if not updates:
        return None

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id"
    return execute_query(query, tuple(params), use_cache=False)

def delete_account(user_id: int):
    """Delete user account"""
    query = "DELETE FROM users WHERE id = %s RETURNING id"
    return execute_query(query, (user_id,), use_cache=False)

# ============================================================
# DATA MANAGEMENT FUNCTIONS
# ============================================================

def get_stock_data_summary():
    """Get summary of all stock data (rows, brokers, date range, row_range)"""
    query = """
        SELECT
            bs.stock_code,
            COUNT(*) as rows,
            COUNT(DISTINCT bs.broker_code) as brokers,
            MIN(bs.date) as first_date,
            MAX(bs.date) as last_date,
            (SELECT uh.row_range FROM upload_history uh
             WHERE uh.stock_code = bs.stock_code
             ORDER BY uh.uploaded_at DESC LIMIT 1) as row_range
        FROM broker_summary bs
        GROUP BY bs.stock_code
        ORDER BY bs.stock_code
    """
    return execute_query(query, use_cache=False) or []

def get_upload_history(limit: int = 5):
    """Get last N upload history records"""
    query = """
        SELECT id, stock_code, uploaded_by, upload_type, rows_uploaded,
               brokers_count, date_range_start, date_range_end, uploaded_at, row_range
        FROM upload_history
        ORDER BY uploaded_at DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), use_cache=False) or []

def add_upload_history(stock_code: str, uploaded_by: str, rows: int, brokers: int,
                       date_start, date_end, upload_type: str = 'broker_summary',
                       row_range: str = 'A-H, L-X'):
    """Add a record to upload history"""
    query = """
        INSERT INTO upload_history (stock_code, uploaded_by, upload_type, rows_uploaded,
                                    brokers_count, date_range_start, date_range_end, row_range)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    return execute_query(query, (stock_code, uploaded_by, upload_type, rows, brokers,
                                  date_start, date_end, row_range), use_cache=False)

def delete_stock_data(stock_code: str):
    """Delete all data for a stock code"""
    queries = [
        "DELETE FROM broker_summary WHERE stock_code = %s",
        "DELETE FROM stock_daily WHERE stock_code = %s",
        "DELETE FROM broker_accumulation WHERE stock_code = %s",
        "DELETE FROM broker_sensitivity WHERE stock_code = %s",
        "DELETE FROM broker_ipo_position WHERE stock_code = %s",
        "DELETE FROM sideways_zones WHERE stock_code = %s",
        "DELETE FROM alerts WHERE stock_code = %s",
    ]
    total_deleted = 0
    for query in queries:
        try:
            result = execute_query(query, (stock_code,), fetch=False, use_cache=False)
            if result:
                total_deleted += 1
        except:
            pass
    return total_deleted > 0

def get_freezable_accounts():
    """Get trial and subscribe accounts that can be frozen"""
    query = """
        SELECT id, email, username, member_type, is_frozen, is_verified, member_end
        FROM users
        WHERE member_type IN ('trial', 'subscribe')
        ORDER BY member_type, username
    """
    return execute_query(query, use_cache=False) or []

def toggle_freeze_account(user_id: int, freeze: bool):
    """Freeze or unfreeze a user account"""
    query = "UPDATE users SET is_frozen = %s WHERE id = %s RETURNING id"
    return execute_query(query, (freeze, user_id), use_cache=False)

# ============================================================
# MAINTENANCE MODE FUNCTIONS
# ============================================================

def get_maintenance_mode():
    """Get current maintenance mode status"""
    query = "SELECT value, updated_at, updated_by FROM system_settings WHERE key = 'maintenance_mode'"
    result = execute_query(query, use_cache=False)
    if result:
        return {
            'is_on': result[0]['value'] == 'on',
            'updated_at': result[0]['updated_at'],
            'updated_by': result[0]['updated_by']
        }
    return {'is_on': False, 'updated_at': None, 'updated_by': None}

def set_maintenance_mode(is_on: bool, updated_by: str = None):
    """Set maintenance mode on or off. Saves stock snapshot when turning ON."""
    value = 'on' if is_on else 'off'
    
    # Save stock snapshot when enabling maintenance
    if is_on:
        save_stock_snapshot()
    
    query = """
        UPDATE system_settings
        SET value = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE key = 'maintenance_mode'
        RETURNING value
    """
    return execute_query(query, (value, updated_by), use_cache=False)

def get_frozen_data_snapshot():
    """Get the data snapshot timestamp when maintenance was enabled"""
    query = "SELECT updated_at FROM system_settings WHERE key = 'maintenance_mode' AND value = 'on'"
    result = execute_query(query, use_cache=False)
    if result:
        return result[0]['updated_at']
    return None

def save_stock_snapshot():
    """Save current stock list as snapshot when maintenance is enabled"""
    import json
    stocks = get_available_stocks()
    stocks_json = json.dumps(stocks)
    query = """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES ('maintenance_stock_snapshot', %s, CURRENT_TIMESTAMP)
        ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
    """
    execute_query(query, (stocks_json, stocks_json), fetch=False, use_cache=False)
    return stocks

def get_stock_snapshot():
    """Get stock list snapshot saved during maintenance"""
    import json
    query = "SELECT value FROM system_settings WHERE key = 'maintenance_stock_snapshot'"
    result = execute_query(query, use_cache=False)
    if result and result[0]['value']:
        try:
            return json.loads(result[0]['value'])
        except:
            pass
    return None

def get_available_stocks_for_user(is_admin: bool = False):
    """Get available stocks considering maintenance mode.
    Admin always sees real-time data, regular users see snapshot during maintenance."""
    if is_admin:
        return get_available_stocks()
    
    # Check if maintenance mode is on
    maintenance = get_maintenance_mode()
    if maintenance.get('is_on', False):
        # Return snapshot for regular users during maintenance
        snapshot = get_stock_snapshot()
        if snapshot:
            return snapshot
    
    # Return real-time data
    return get_available_stocks()

def is_stock_accessible_for_user(stock_code: str, is_admin: bool = False) -> bool:
    """Check if a stock is accessible for the user.
    During maintenance, regular users can only access stocks in the snapshot."""
    if is_admin:
        return True
    
    # Check if maintenance mode is on
    maintenance = get_maintenance_mode()
    if maintenance.get('is_on', False):
        snapshot = get_stock_snapshot()
        if snapshot:
            return stock_code in snapshot
    
    # Outside maintenance, check if stock exists in database
    return stock_code in get_available_stocks()

def get_password_display(password_hash: str) -> str:
    """Extract readable info from password hash for display (NOT the actual password)"""
    # Password hash format: salt:hash
    # We can't recover the password, so just show that it's set
    if password_hash and ':' in password_hash:
        return "********"  # Just show dots to indicate password is set
    return "(tidak ada)"


def get_member_history_data():
    """Get member join history for chart (last 30 days)"""
    query = """
        SELECT
            DATE(created_at) as join_date,
            member_type,
            COUNT(*) as count
        FROM users
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            AND member_type IN ('trial', 'subscribe')
        GROUP BY DATE(created_at), member_type
        ORDER BY join_date
    """
    return execute_query(query, use_cache=False) or []

def get_forum_threads(stock_code: str = None, limit: int = 50):
    """Get forum threads, pinned first, then by score"""
    if stock_code:
        query = """
            SELECT * FROM forum_threads
            WHERE (stock_code = %s OR stock_code IS NULL) AND is_hidden = FALSE
            ORDER BY is_pinned DESC, score DESC, created_at DESC
            LIMIT %s
        """
        results = execute_query(query, (stock_code, limit), use_cache=False)  # No cache for real-time forum
    else:
        query = """
            SELECT * FROM forum_threads
            WHERE is_hidden = FALSE
            ORDER BY is_pinned DESC, score DESC, created_at DESC
            LIMIT %s
        """
        results = execute_query(query, (limit,), use_cache=False)  # No cache for real-time forum
    return results or []

def get_thread_comments(thread_id: int):
    """Get comments for a thread"""
    query = """
        SELECT * FROM forum_comments
        WHERE thread_id = %s AND is_hidden = FALSE
        ORDER BY created_at ASC
    """
    results = execute_query(query, (thread_id,), use_cache=False)
    return results or []

def text_with_linebreaks(text: str) -> list:
    """Convert text with newlines to list of html elements with Br tags"""
    if not text:
        return []
    lines = text.split('\n')
    result = []
    for i, line in enumerate(lines):
        if i > 0:
            result.append(html.Br())
        result.append(line)
    return result

def create_comment_card(comment: dict) -> html.Div:
    """Create a comment display"""
    time_str = comment['created_at'].strftime("%d %b %Y, %H:%M") if comment.get('created_at') else ""
    is_admin = comment.get('author_type') == 'admin'

    return html.Div([
        html.Div([
            html.Small([
                html.Span("[U] ", className="me-1"),
                html.Strong(comment['author_name'], className="text-info" if is_admin else ""),
                html.Span(" (Admin)" if is_admin else "", className="text-info small"),
                html.Span(f" * {time_str}", className="text-muted ms-2"),
            ]),
        ], className="mb-1"),
        html.Div(text_with_linebreaks(comment['content']), className="mb-1 small", style={"marginLeft": "1.5rem"}),
    ], className="border-start border-2 ps-2 mb-2", style={"borderColor": "#17a2b8" if is_admin else "#6c757d"})

def create_thread_card(thread: dict) -> dbc.Card:
    """Create a card for a forum thread"""
    is_admin = thread['author_type'] == 'admin'
    is_pinned = thread['is_pinned']
    is_frozen = thread['is_frozen']
    is_provokatif = thread['flag'] == 'provokatif'
    is_collapsed = thread['collapsed']

    # Card styling based on type - using theme-aware borders
    if is_admin and is_pinned:
        card_class = "border-info"
        card_style = {"borderWidth": "2px", "backgroundColor": "rgba(23, 162, 184, 0.1)"}
        badge = dbc.Badge("[i] ADMIN INSIGHT", color="info", className="me-2")
    elif is_provokatif:
        card_class = "border-warning"
        card_style = {"opacity": "0.7"}
        badge = dbc.Badge("[!] Provokatif", color="warning", className="me-2")
    else:
        card_class = "border-secondary"
        card_style = {}
        badge = None

    # Time formatting
    created = thread['created_at']
    time_str = created.strftime("%d %b %Y, %H:%M") if created else ""

    # Score display
    score = thread['score']
    score_color = "success" if score > 0 else "danger" if score < 0 else "secondary"

    # Content - show preview with expand option for long content
    content_full = thread['content']
    is_long_content = len(content_full) > 500

    card_body = [
        # Header
        html.Div([
            badge,
            html.Strong(thread['title']),
            html.Span(f" * {thread['stock_code']}", className="text-info ms-2") if thread['stock_code'] else None,
        ], className="mb-2"),

        # Content with expand/collapse for long posts
        html.Div([
            # Preview (always shown)
            html.Div([
                html.Div(
                    text_with_linebreaks(content_full[:500] + "..." if is_long_content else content_full),
                    className="mb-2 small forum-content"
                ),
            ], id={"type": "thread-preview", "index": thread['id']}),
            # Full content (hidden by default for long posts)
            dbc.Collapse([
                html.Div(
                    text_with_linebreaks(content_full),
                    className="mb-2 small forum-content"
                ),
            ], id={"type": "thread-full", "index": thread['id']}, is_open=False) if is_long_content else None,
            # Expand button
            dbc.Button([
                html.I(className="fas fa-chevron-down me-1"),
                "Lihat selengkapnya"
            ], id={"type": "expand-content", "index": thread['id']},
               color="link", size="sm", className="p-0 text-info") if is_long_content else None,
        ], id={"type": "thread-content", "index": thread['id']}),

        # PDF Attachment
        html.Div([
            html.A([
                html.I(className="fas fa-file-pdf me-2 text-danger"),
                thread['pdf_filename']
            ], href=f"/download-pdf/{thread['id']}", target="_blank",
               className="btn btn-light btn-sm mb-2")
        ]) if thread.get('pdf_filename') else None,

        # Footer
        html.Div([
            html.Small([
                html.Span(f"[U] {thread['author_name']}", className="me-2"),
                html.Span(f"[T] {time_str}", className="me-2 text-muted d-none-mobile"),
                html.Span(f"[C] {thread['comment_count']}", className="me-2"),
                html.Span(f"[+] {thread['view_count']}", className="me-2 text-muted d-none-mobile"),
            ], className="thread-meta"),
            # Score & Reactions
            html.Div([
                dbc.Badge(f"Score: {score:+d}", color=score_color, className="me-2"),
                dbc.Button("[+1]", id={"type": "upvote", "index": thread['id']}, color="success", size="sm", outline=True, className="me-1"),
                dbc.Button("[!]", id={"type": "warn-vote", "index": thread['id']}, color="warning", size="sm", outline=True, className="me-1"),
                dbc.Button("[-1]", id={"type": "downvote", "index": thread['id']}, color="danger", size="sm", outline=True, className="me-1"),
            ], className="mt-2") if not is_frozen else None,
        ], className="d-flex justify-content-between align-items-center flex-wrap"),

        # Frozen notice
        html.Div([
            html.Small("[L] Thread ini dikunci oleh Admin", className="text-muted fst-italic")
        ], className="mt-2") if is_frozen else None,

        # Admin controls (edit/delete)
        html.Div([
            html.Hr(className="my-2"),
            html.Small("Admin: ", className="text-muted me-2"),
            dbc.Button([html.I(className="fas fa-edit me-1"), "Edit"],
                      id={"type": "edit-thread", "index": thread['id']},
                      color="info", size="sm", outline=True, className="me-1"),
            dbc.Button([html.I(className="fas fa-trash me-1"), "Delete"],
                      id={"type": "delete-thread", "index": thread['id']},
                      color="danger", size="sm", outline=True),
        ], className="mt-2", id={"type": "admin-controls", "index": thread['id']}),

        # Comment section
        html.Div([
            html.Hr(className="my-2"),
            # Toggle comments button
            dbc.Button([
                html.I(className="fas fa-comments me-1"),
                f"Komentar ({thread['comment_count']})"
            ], id={"type": "toggle-comments", "index": thread['id']},
               color="secondary", size="sm", outline=True, className="mb-2"),

            # Comments container (collapsible)
            dbc.Collapse([
                # Existing comments
                html.Div(
                    id={"type": "comments-list", "index": thread['id']},
                    children=[create_comment_card(c) for c in get_thread_comments(thread['id'])] or [
                        html.Small("Belum ada komentar.", className="text-muted")
                    ]
                ),
                # Add comment form (if not frozen)
                html.Div([
                    html.Hr(className="my-2"),
                    dbc.InputGroup([
                        dbc.Input(
                            id={"type": "comment-author", "index": thread['id']},
                            placeholder="Nama Anda",
                            size="sm",
                            style={"maxWidth": "150px"}
                        ),
                        dbc.Textarea(
                            id={"type": "comment-content", "index": thread['id']},
                            placeholder="Tulis komentar...",
                            size="sm",
                            rows=2,
                            style={"flex": "1"}
                        ),
                        dbc.Button(
                            html.I(className="fas fa-paper-plane"),
                            id={"type": "submit-comment", "index": thread['id']},
                            color="primary",
                            size="sm"
                        ),
                    ], size="sm"),
                    html.Div(id={"type": "comment-feedback", "index": thread['id']}, className="mt-1"),
                ], className="mt-2") if not is_frozen else None,
            ], id={"type": "comments-collapse", "index": thread['id']}, is_open=False),
        ]) if not is_frozen else None,
    ]

    # Collapse wrapper for provokatif posts
    if is_collapsed or is_provokatif:
        return dbc.Card([
            dbc.CardHeader([
                html.Span("[!] Post ini mengandung bahasa provokatif. ", className="text-warning"),
                dbc.Button("Lihat", id={"type": "expand-thread", "index": thread['id']}, size="sm", color="link")
            ]),
            dbc.Collapse(
                dbc.CardBody(card_body),
                id={"type": "thread-collapse", "index": thread['id']},
                is_open=False
            )
        ], className=f"mb-3 {card_class}", style=card_style)

    return dbc.Card([
        dbc.CardBody(card_body)
    ], className=f"mb-3 {card_class}", style=card_style)


# ============================================================
# PAGE: NEWS - Berita Saham Indonesia
# ============================================================

def create_news_page(stock_code: str = 'BBCA'):
    """Create news page with stock-related news from GNews API"""
    try:
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
        print(f"Error loading news: {e}")

    # Create news cards
    def create_news_card(article):
        sentiment = article.get('sentiment', 'NETRAL')
        color = article.get('color', 'secondary')
        icon = article.get('icon', '[~]')

        return dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Sentiment Badge
                    dbc.Col([
                        html.Div([
                            html.Span(icon, style={"fontSize": "24px", "fontWeight": "bold"}),
                            dbc.Badge(sentiment, color=color, className="ms-2")
                        ], className="text-center")
                    ], width=2, className="d-flex align-items-center justify-content-center"),

                    # News Content
                    dbc.Col([
                        html.A(
                            html.H6(article.get('title', 'No Title')[:80] + ('...' if len(article.get('title', '')) > 80 else ''),
                                   className="mb-1 text-info"),
                            href=article.get('url', '#'), target="_blank", style={"textDecoration": "none"}
                        ),
                        html.P(article.get('description', '')[:150] + ('...' if len(article.get('description', '')) > 150 else ''),
                               className="text-muted small mb-1"),
                        html.Div([
                            dbc.Badge(article.get('source', 'Unknown'), color="dark", className="me-2"),
                            html.Small(article.get('published_formatted', ''), className="text-muted"),
                        ])
                    ], width=10)
                ])
            ])
        ], className="mb-2", style={"borderLeft": f"4px solid var(--bs-{color})"})

    return html.Div([
        # Page Header
        html.Div([
            html.H4([
                html.I(className="fas fa-newspaper me-2"),
                f"Berita Saham - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            dbc.Badge(f"{len(news_articles)} berita", color="info", className="me-2"),
            dbc.Button([
                html.I(className="fas fa-sync-alt me-1"),
                "Refresh"
            ], id="refresh-news-btn", color="outline-info", size="sm"),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        dbc.Row([
            # Left Column - News for Selected Stock
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-rss me-2 text-warning"),
                            f"Berita {stock_code}"
                        ], className="mb-0")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        html.Div([
                            create_news_card(article) for article in news_articles
                        ]) if news_articles else dbc.Alert([
                            html.I(className="fas fa-info-circle me-2"),
                            f"Tidak ada berita terbaru untuk {stock_code}. ",
                            html.Br(),
                            html.Small("Coba refresh atau pilih emiten lain.", className="text-muted")
                        ], color="info")
                    ], style={"maxHeight": "600px", "overflowY": "auto"})
                ])
            ], md=8),

            # Right Column - Latest Across All Stocks + Info
            dbc.Col([
                # Cache Status Card
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
                        ], className="small mb-2"),
                        html.Hr(),
                        html.Div([
                            html.H6("Legenda Sentiment:", className="small mb-2"),
                            html.Div([
                                dbc.Badge("[+] POSITIF", color="success", className="me-1 mb-1"),
                                html.Small(" - Berita baik untuk saham", className="text-muted d-block small"),
                            ], className="mb-1"),
                            html.Div([
                                dbc.Badge("[~] NETRAL", color="secondary", className="me-1 mb-1"),
                                html.Small(" - Berita umum/informatif", className="text-muted d-block small"),
                            ], className="mb-1"),
                            html.Div([
                                dbc.Badge("[-] NEGATIF", color="danger", className="me-1 mb-1"),
                                html.Small(" - Berita kurang baik", className="text-muted d-block small"),
                            ]),
                        ])
                    ])
                ], className="mb-3"),

                # Latest All Stocks
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([
                            html.I(className="fas fa-globe me-2 text-success"),
                            "Berita Terbaru Semua Emiten"
                        ], className="mb-0")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        html.Div([
                            html.Div([
                                html.A(
                                    html.Span([
                                        dbc.Badge(art.get('stock_code', ''), color=art.get('color', 'secondary'), className="me-2"),
                                        art.get('title', '')[:50] + '...'
                                    ]),
                                    href=art.get('url', '#'), target="_blank",
                                    className="text-light small", style={"textDecoration": "none"}
                                ),
                                html.Br(),
                                html.Small(art.get('published_formatted', ''), className="text-muted"),
                                html.Hr(className="my-2")
                            ]) for art in latest_all
                        ]) if latest_all else html.Small("Tidak ada berita", className="text-muted")
                    ], style={"maxHeight": "300px", "overflowY": "auto"})
                ])
            ], md=4)
        ]),

        # Disclaimer
        html.Div([
            html.Hr(className="my-4"),
            html.Small([
                html.I(className="fas fa-exclamation-triangle me-2 text-warning"),
                "Disclaimer: Berita dikumpulkan otomatis dari berbagai sumber. Sentiment analysis bersifat indikatif. ",
                "Selalu lakukan riset mandiri sebelum mengambil keputusan investasi."
            ], className="text-muted")
        ], className="text-center")
    ])


def create_discussion_page(stock_code: str = None):
    """Create discussion forum page"""
    threads = get_forum_threads(stock_code)

    # Separate admin pinned vs community
    admin_threads = [t for t in threads if t['is_pinned'] and t['author_type'] == 'admin']
    community_threads = [t for t in threads if not (t['is_pinned'] and t['author_type'] == 'admin')]

    return html.Div([
        # Header
        html.Div([
            html.H4([
                html.I(className="fas fa-comments me-2"),
                "Discussion Forum",
                html.Span(f" - {stock_code}", className="text-info") if stock_code else ""
            ], className="mb-0"),
        ], className="mb-3"),

        # Guidelines Banner
        dbc.Alert([
            html.Div([
                html.I(className="fas fa-info-circle me-2"),
                html.Strong("Panduan Diskusi"),
            ], className="mb-2"),
            html.Small([
                "Thread teratas adalah pandangan admin sebagai konteks. ",
                "Diskusi di bawah bebas, tapi gunakan bahasa rasional & berbasis data. ",
                "Post provokatif akan di-collapse dan mendapat score negatif."
            ], className="text-muted")
        ], color="info", className="mb-3"),

        # Action button
        html.Div([
            dbc.Button([
                html.I(className="fas fa-plus me-2"),
                "Buat Thread Baru"
            ], id="new-thread-btn", color="primary", size="sm")
        ], className="mb-4 text-end"),

        # New Thread Form (hidden by default)
        dbc.Collapse([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-edit me-2"),
                    "Buat Thread Baru"
                ]),
                dbc.CardBody([
                    dbc.Label("Nama (akan ditampilkan)", className="small"),
                    dbc.Input(id="thread-author", placeholder="Nama Anda", size="sm", className="mb-3"),
                    dbc.Label("Judul Thread", className="small"),
                    dbc.Input(id="thread-title", placeholder="Judul diskusi...", className="mb-3"),
                    dbc.Label("Isi Thread", className="small"),
                    dbc.Textarea(id="thread-content", placeholder="Tulis pendapat atau analisa Anda...", rows=5, className="mb-3"),

                    # PDF Upload
                    dbc.Label("Lampiran PDF (opsional)", className="small"),
                    dcc.Upload(
                        id="thread-pdf-upload",
                        children=html.Div([
                            html.I(className="fas fa-file-pdf me-2 text-danger"),
                            "Drag & drop atau ",
                            html.A("klik untuk upload PDF", className="text-info")
                        ]),
                        style={
                            'width': '100%',
                            'height': '50px',
                            'lineHeight': '50px',
                            'borderWidth': '1px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'cursor': 'pointer'
                        },
                        className="mb-2 border-secondary",
                        accept=".pdf",
                        max_size=5*1024*1024  # 5MB max
                    ),
                    html.Div(id="pdf-upload-status", className="small text-muted mb-3"),

                    # Admin section (hidden by default)
                    dbc.Collapse([
                        html.Hr(),
                        dbc.Label("Admin Password", className="small text-warning fw-bold"),
                        dbc.Input(id="admin-password", type="password", placeholder="Password admin...", size="sm", className="mb-3"),
                        dbc.Checklist(
                            id="admin-options",
                            options=[
                                {"label": " [i] Pin sebagai Admin Insight", "value": "pinned"},
                                {"label": " [L] Freeze (tidak bisa dikomentari)", "value": "frozen"},
                            ],
                            value=[],
                            switch=True,
                            className="mb-2",
                            style={"fontSize": "0.95rem"}
                        ),
                    ], id="admin-section", is_open=False),

                    # Warning for admin-like names
                    html.Div(id="admin-name-warning", className="mb-2"),

                    html.Div(id="thread-submit-feedback", className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Button("Saya Admin", id="toggle-admin-btn", color="link", size="sm"),
                        ]),
                        dbc.Col([
                            dbc.Button([
                                html.I(className="fas fa-paper-plane me-2"),
                                "Kirim Thread"
                            ], id="submit-thread-btn", color="success"),
                        ], className="text-end"),
                    ]),
                ])
            ], className="mb-4 border-info")
        ], id="new-thread-form", is_open=False),

        # Admin Pinned Threads Section (always at top)
        html.Div([
            html.H6([
                html.I(className="fas fa-thumbtack me-2 text-info"),
                "Admin Insight"
            ], className="mb-3 text-info", id="admin-insight-header"),
            html.Div(
                id="admin-threads-container",
                children=[create_thread_card(t) for t in admin_threads] if admin_threads else []
            ),
            html.Hr(className="my-4", id="admin-separator")
        ], id="admin-section-wrapper", style={} if admin_threads else {"display": "none"}),

        # Community Threads Section
        html.Div([
            html.H6([
                html.I(className="fas fa-users me-2"),
                "Community Discussion"
            ], className="mb-3"),
            html.Div(
                id="community-threads-container",
                children=[create_thread_card(t) for t in community_threads] if community_threads else [
                    dbc.Alert("Belum ada diskusi. Jadilah yang pertama!", color="secondary")
                ]
            )
        ]),

        # Hidden store for thread data
        dcc.Store(id="forum-data-store"),
        dcc.Store(id="selected-thread-id"),

        # Edit Thread Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Edit Thread")),
            dbc.ModalBody([
                dbc.Label("Admin Password", className="small text-warning"),
                dbc.Input(id="edit-admin-password", type="password", placeholder="Password admin...", className="mb-3"),
                dbc.Label("Judul", className="small"),
                dbc.Input(id="edit-thread-title", placeholder="Judul thread...", className="mb-3"),
                dbc.Label("Isi Thread", className="small"),
                dbc.Textarea(id="edit-thread-content", rows=5, className="mb-3"),
                html.Div(id="edit-feedback"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Batal", id="cancel-edit-btn", color="secondary", className="me-2"),
                dbc.Button("Simpan", id="save-edit-btn", color="primary"),
            ])
        ], id="edit-thread-modal", is_open=False, size="lg"),

        # Delete Confirmation Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Hapus Thread")),
            dbc.ModalBody([
                html.P("Apakah Anda yakin ingin menghapus thread ini?", className="text-danger"),
                dbc.Label("Admin Password", className="small text-warning"),
                dbc.Input(id="delete-admin-password", type="password", placeholder="Password admin...", className="mb-3"),
                html.Div(id="delete-feedback"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Batal", id="cancel-delete-btn", color="secondary", className="me-2"),
                dbc.Button("Hapus", id="confirm-delete-btn", color="danger"),
            ])
        ], id="delete-thread-modal", is_open=False),
    ])


# ============================================================
# PAGE: UPLOAD DATA (Password Protected)
# ============================================================

UPLOAD_PASSWORD = "12153800"  # Password untuk akses upload

def create_upload_page():
    """Create upload page with password protection"""
    return html.Div([
        html.H4("Upload Data Broker Summary", className="mb-4"),

        # Password Gate
        html.Div(id='upload-password-gate', children=[
            dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="fas fa-lock me-2"),
                        "Akses Terbatas"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    html.P("Halaman ini memerlukan password untuk mengakses.", className="text-muted"),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Password:"),
                            dbc.Input(
                                id='upload-password-input',
                                type='password',
                                placeholder='Masukkan password',
                                className="mb-3"
                            ),
                            dbc.Button([
                                html.I(className="fas fa-unlock me-2"),
                                "Masuk"
                            ], id='upload-password-submit', color="primary", className="w-100"),
                            html.Div(id='upload-password-error', className="mt-2")
                        ], md=4)
                    ])
                ])
            ], className="mb-4")
        ]),

        # Upload Form (hidden until password correct)
        html.Div(id='upload-form-container', style={'display': 'none'}, children=[
            # Tabs for Upload and Member Management
            dbc.Tabs([
                # TAB 1: UPLOAD DATA
                dbc.Tab(label="[UP] Upload Data", tab_id="tab-upload", children=[
                    html.Div(className="pt-3", children=[
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader(html.H5("Upload Excel File", className="mb-0")),
                                    dbc.CardBody([
                                        # Stock Code Input
                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Label("Kode Saham:"),
                                                dbc.Input(
                                                    id='upload-stock-code',
                                                    type='text',
                                                    placeholder='Contoh: CDIA, BBCA, TLKM',
                                                    value='',
                                                    className="mb-3"
                                                ),
                                            ], width=4),
                                        ]),

                                        # File Upload with Loading
                                        dcc.Loading(
                                            id="upload-loading",
                                            type="circle",
                                            color="#0d6efd",
                                            children=[
                                                dcc.Upload(
                                                    id='upload-data',
                                                    children=html.Div([
                                                        html.I(className="fas fa-cloud-upload-alt fa-2x mb-2"),
                                                        html.Br(),
                                                        'Drag and Drop atau ',
                                                        html.A('Klik untuk Upload', className="text-primary")
                                                    ]),
                                                    className="upload-area",
                                                    style={
                                                        'width': '100%',
                                                        'height': '120px',
                                                        'lineHeight': '40px',
                                                        'borderWidth': '2px',
                                                        'borderStyle': 'dashed',
                                                        'borderRadius': '10px',
                                                        'textAlign': 'center',
                                                        'padding': '20px',
                                                        'margin': '10px 0',
                                                        'cursor': 'pointer'
                                                    },
                                                    multiple=False,
                                                    accept='.xlsx,.xls'
                                                ),
                                                html.Div(id='upload-status', className="mt-3"),
                                            ]
                                        ),

                                        html.Hr(),

                                        # Format Info
                                        dbc.Alert([
                                            html.H6("Format Excel yang Diharapkan:", className="alert-heading"),
                                            html.P("File Excel harus memiliki format seperti berikut:", className="mb-2"),
                                            html.Ul([
                                                html.Li([html.Strong("Kolom A-H: "), "Data Broker Summary (Buy/Sell)"]),
                                                html.Li("Kolom A: Buy Broker Code"),
                                                html.Li("Kolom B: Buy Value (contoh: 35.7B, 500M)"),
                                                html.Li("Kolom C: Buy Lot"),
                                                html.Li("Kolom D: Buy Avg Price"),
                                                html.Li("Kolom E: Sell Broker Code"),
                                                html.Li("Kolom F: Sell Value"),
                                                html.Li("Kolom G: Sell Lot"),
                                                html.Li("Kolom H: Sell Avg Price"),
                                                html.Li([html.Strong("Kolom L-X: "), "Data Harga (Date, Close, Change, Volume, dll)"]),
                                            ], className="small"),
                                            html.P([
                                                "Contoh file: ",
                                                html.Code("C:\\doc Herman\\cdia.xlsx")
                                            ], className="mb-0 small")
                                        ], color="info"),
                                    ])
                                ])
                            ], width=8),

                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader(html.H5("Data yang Tersedia", className="mb-0")),
                                    dbc.CardBody(id='available-stocks-list')
                                ])
                            ], width=4),
                        ], className="mb-4"),

                        # Import History/Log
                        dbc.Card([
                            dbc.CardHeader("Import Log"),
                            dbc.CardBody(id='import-log')
                        ])
                    ])
                ]),

                # TAB 2: MEMBER MANAGEMENT
                dbc.Tab(label="[P] Member Management", tab_id="tab-members", children=[
                    html.Div(className="pt-3", children=[
                        # Member Stats Cards
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-user-clock fa-2x text-warning"),
                                        ], className="float-end"),
                                        html.H6("Trial Members", className="text-muted"),
                                        html.H3(id="stat-trial-active", className="mb-0"),
                                        html.Small(id="stat-trial-online", className="text-success"),
                                    ])
                                ], color="dark", outline=True)
                            ], md=3),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-user-check fa-2x text-success"),
                                        ], className="float-end"),
                                        html.H6("Subscribe Members", className="text-muted"),
                                        html.H3(id="stat-subscribe-active", className="mb-0"),
                                        html.Small(id="stat-subscribe-online", className="text-success"),
                                    ])
                                ], color="dark", outline=True)
                            ], md=3),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-user-times fa-2x text-danger"),
                                        ], className="float-end"),
                                        html.H6("Expired Members", className="text-muted"),
                                        html.H3(id="stat-expired-total", className="mb-0"),
                                        html.Small("Trial + Subscribe", className="text-muted"),
                                    ])
                                ], color="dark", outline=True)
                            ], md=3),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-users fa-2x text-info"),
                                        ], className="float-end"),
                                        html.H6("Total Members", className="text-muted"),
                                        html.H3(id="stat-total-members", className="mb-0"),
                                        html.Small("All time", className="text-muted"),
                                    ])
                                ], color="dark", outline=True)
                            ], md=3),
                        ], className="mb-4"),

                        # Add Member Form
                        dbc.Card([
                            dbc.CardHeader([
                                html.H5([html.I(className="fas fa-user-plus me-2"), "Tambah Member Baru"], className="mb-0")
                            ]),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Email"),
                                        dbc.Input(id="new-member-email", type="email", placeholder="email@example.com"),
                                    ], md=3),
                                    dbc.Col([
                                        dbc.Label("Nama"),
                                        dbc.Input(id="new-member-name", type="text", placeholder="Nama lengkap"),
                                    ], md=3),
                                    dbc.Col([
                                        dbc.Label("Tipe Member"),
                                        dbc.Select(
                                            id="new-member-type",
                                            options=[
                                                {"label": "[T] Trial (7 hari)", "value": "trial"},
                                                {"label": "[*] Subscribe (30 hari)", "value": "subscribe"},
                                            ],
                                            value="trial"
                                        ),
                                    ], md=3),
                                    dbc.Col([
                                        dbc.Label(" "),
                                        dbc.Button([
                                            html.I(className="fas fa-plus me-2"),
                                            "Tambah Member"
                                        ], id="add-member-btn", color="success", className="w-100 mt-1"),
                                    ], md=3),
                                ]),
                                html.Div(id="add-member-feedback", className="mt-2"),
                            ])
                        ], className="mb-4"),

                        # Member Graph
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Grafik Member (30 Hari Terakhir)"),
                                    dbc.CardBody([
                                        dcc.Graph(id="member-history-chart", style={"height": "300px"})
                                    ])
                                ])
                            ], md=6),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Status Member Online"),
                                    dbc.CardBody([
                                        dcc.Graph(id="member-online-chart", style={"height": "300px"})
                                    ])
                                ])
                            ], md=6),
                        ], className="mb-4"),

                        # Member Lists in Tabs
                        dbc.Card([
                            dbc.CardHeader([
                                dbc.Tabs([
                                    dbc.Tab(label="[T] Trial Members", tab_id="subtab-trial"),
                                    dbc.Tab(label="[*] Subscribe Members", tab_id="subtab-subscribe"),
                                ], id="member-list-tabs", active_tab="subtab-trial")
                            ]),
                            dbc.CardBody([
                                html.Div(id="member-list-container"),
                                dbc.Button([
                                    html.I(className="fas fa-sync me-2"),
                                    "Refresh Data"
                                ], id="refresh-members-btn", color="secondary", size="sm", className="mt-3"),
                            ])
                        ])
                    ])
                ]),

                # TAB 3: LIST MEMBER (Account Management)
                dbc.Tab(label="[LIST] List Member", tab_id="tab-list-member", children=[
                    html.Div(className="pt-3", children=[
                        # Header with refresh button
                        dbc.Row([
                            dbc.Col([
                                html.H5([
                                    html.I(className="fas fa-users-cog me-2"),
                                    "Daftar Akun Member"
                                ], className="mb-0"),
                            ], md=8),
                            dbc.Col([
                                dbc.Button([
                                    html.I(className="fas fa-sync me-2"),
                                    "Refresh"
                                ], id="refresh-account-list-btn", color="primary", size="sm", className="float-end"),
                            ], md=4),
                        ], className="mb-3"),

                        # Feedback div
                        html.Div(id="account-action-feedback", className="mb-3"),

                        # Account List Table
                        dbc.Card([
                            dbc.CardBody([
                                html.Div(id="account-list-container", children=[
                                    dbc.Spinner(color="primary", size="sm"),
                                    " Loading..."
                                ])
                            ])
                        ]),

                        # Edit Account Modal
                        dbc.Modal([
                            dbc.ModalHeader(dbc.ModalTitle([
                                html.I(className="fas fa-user-edit me-2"),
                                "Edit Akun Member"
                            ])),
                            dbc.ModalBody([
                                dcc.Store(id="edit-account-id", data=None),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Email"),
                                        dbc.Input(id="edit-account-email", type="email", disabled=True),
                                    ], className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Username"),
                                        dbc.Input(id="edit-account-username", type="text"),
                                    ], className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Password Baru (kosongkan jika tidak ingin mengubah)"),
                                        dbc.Input(id="edit-account-password", type="text", placeholder="Password baru..."),
                                    ], className="mb-3"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Tipe Member"),
                                        dbc.Select(
                                            id="edit-account-type",
                                            options=[
                                                {"label": "[T] Trial", "value": "trial"},
                                                {"label": "[*] Subscribe", "value": "subscribe"},
                                                {"label": "[E] Superuser", "value": "superuser"},
                                                {"label": "[i] Admin", "value": "admin"},
                                            ]
                                        ),
                                    ], md=6),
                                    dbc.Col([
                                        dbc.Label("Status"),
                                        dbc.Select(
                                            id="edit-account-status",
                                            options=[
                                                {"label": "[OK] Aktif (Verified)", "value": "true"},
                                                {"label": "[X] Nonaktif", "value": "false"},
                                            ]
                                        ),
                                    ], md=6),
                                ]),
                                html.Div(id="edit-account-feedback", className="mt-3"),
                            ]),
                            dbc.ModalFooter([
                                dbc.Button("Batal", id="cancel-edit-account-btn", color="secondary"),
                                dbc.Button([
                                    html.I(className="fas fa-save me-2"),
                                    "Simpan"
                                ], id="save-edit-account-btn", color="success"),
                            ]),
                        ], id="edit-account-modal", is_open=False, size="lg"),

                        # Delete Confirmation Modal
                        dbc.Modal([
                            dbc.ModalHeader(dbc.ModalTitle([
                                html.I(className="fas fa-exclamation-triangle me-2 text-danger"),
                                "Konfirmasi Hapus"
                            ])),
                            dbc.ModalBody([
                                dcc.Store(id="delete-account-id", data=None),
                                html.P(id="delete-confirm-text"),
                                html.P("Tindakan ini tidak dapat dibatalkan!", className="text-danger fw-bold"),
                            ]),
                            dbc.ModalFooter([
                                dbc.Button("Batal", id="cancel-delete-account-btn", color="secondary"),
                                dbc.Button([
                                    html.I(className="fas fa-trash me-2"),
                                    "Hapus"
                                ], id="confirm-delete-account-btn", color="danger"),
                            ]),
                        ], id="delete-account-modal", is_open=False),
                    ])
                ]),

                # TAB 4: DATA MANAGEMENT
                dbc.Tab(label="[#] Data Management", tab_id="tab-data-mgmt", children=[
                    html.Div(className="pt-3", children=[
                        # Header
                        dbc.Row([
                            dbc.Col([
                                html.H5([
                                    html.I(className="fas fa-database me-2"),
                                    "Management Data Upload"
                                ], className="mb-0"),
                            ], md=8),
                            dbc.Col([
                                dbc.Button([
                                    html.I(className="fas fa-sync me-2"),
                                    "Refresh"
                                ], id="refresh-data-mgmt-btn", color="primary", size="sm", className="float-end"),
                            ], md=4),
                        ], className="mb-3"),

                        # Stock Data Summary Card
                        dbc.Card([
                            dbc.CardHeader([
                                html.H6([html.I(className="fas fa-chart-bar me-2"), "Data Emiten"], className="mb-0")
                            ]),
                            dbc.CardBody([
                                html.Div(id="stock-data-summary-container", children=[
                                    dbc.Spinner(color="primary", size="sm"),
                                    " Loading data..."
                                ])
                            ])
                        ], className="mb-4"),

                        # Upload History Card
                        dbc.Card([
                            dbc.CardHeader([
                                html.H6([html.I(className="fas fa-history me-2"), "Riwayat Upload (5 Terakhir)"], className="mb-0")
                            ]),
                            dbc.CardBody([
                                html.Div(id="upload-history-container", children=[
                                    dbc.Spinner(color="primary", size="sm"),
                                    " Loading history..."
                                ])
                            ])
                        ], className="mb-4"),

                        # Maintenance Mode Card
                        dbc.Card([
                            dbc.CardHeader([
                                html.H6([html.I(className="fas fa-tools me-2"), "Maintenance Mode"], className="mb-0")
                            ]),
                            dbc.CardBody([
                                html.P([
                                    "Saat maintenance aktif, user biasa melihat data sebelum maintenance. ",
                                    "Admin & Superuser tetap melihat data real-time."
                                ], className="text-muted small mb-3"),
                                html.Div(id="maintenance-mode-container", children=[
                                    dbc.Spinner(color="primary", size="sm"),
                                    " Loading status..."
                                ])
                            ])
                        ]),

                        # Delete Stock Data Modal
                        dbc.Modal([
                            dbc.ModalHeader(dbc.ModalTitle([
                                html.I(className="fas fa-exclamation-triangle me-2 text-danger"),
                                "Konfirmasi Hapus Data"
                            ])),
                            dbc.ModalBody([
                                dcc.Store(id="delete-stock-code", data=None),
                                html.P(id="delete-stock-confirm-text"),
                                html.P("Semua data broker dan harga untuk emiten ini akan dihapus!", className="text-danger fw-bold"),
                            ]),
                            dbc.ModalFooter([
                                dbc.Button("Batal", id="cancel-delete-stock-btn", color="secondary"),
                                dbc.Button([
                                    html.I(className="fas fa-trash me-2"),
                                    "Hapus Data"
                                ], id="confirm-delete-stock-btn", color="danger"),
                            ]),
                        ], id="delete-stock-modal", is_open=False),

                        # Feedback div
                        html.Div(id="data-mgmt-feedback", className="mt-3"),
                    ])
                ]),

            ], id="admin-tabs", active_tab="tab-upload"),

            # Interval for auto-refresh member stats
            dcc.Interval(id='member-stats-interval', interval=60000, n_intervals=0),  # Every 60 seconds
        ])
    ])


# ============================================================
# PAGE: SIGN UP
# ============================================================

def create_signup_page():
    """Create sign up page"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4([
                                html.I(className="fas fa-user-plus me-2"),
                                "Daftar Akun Baru"
                            ], className="mb-0 text-center")
                        ]),
                        dbc.CardBody([
                            # Email
                            dbc.Label("Email", html_for="signup-email"),
                            dbc.Input(
                                id="signup-email",
                                type="email",
                                placeholder="email@example.com",
                                className="mb-3"
                            ),

                            # Username
                            dbc.Label("Username", html_for="signup-username"),
                            dbc.Input(
                                id="signup-username",
                                type="text",
                                placeholder="Username (min 3 karakter)",
                                className="mb-3"
                            ),

                            # Password
                            dbc.Label("Password", html_for="signup-password"),
                            dbc.Input(
                                id="signup-password",
                                type="password",
                                placeholder="Min 6 karakter, huruf + angka",
                                className="mb-1"
                            ),
                            html.Small("Password harus minimal 6 karakter, mengandung huruf dan angka",
                                      className="text-muted d-block mb-3"),

                            # Confirm Password
                            dbc.Label("Konfirmasi Password", html_for="signup-confirm"),
                            dbc.Input(
                                id="signup-confirm",
                                type="password",
                                placeholder="Ulangi password",
                                className="mb-3"
                            ),

                            # Submit button
                            dbc.Button([
                                html.I(className="fas fa-paper-plane me-2"),
                                "Daftar"
                            ], id="signup-submit", color="success", className="w-100 mb-3"),

                            # Feedback
                            html.Div(id="signup-feedback"),

                            html.Hr(),

                            # Login link
                            html.P([
                                "Sudah punya akun? ",
                                dcc.Link("Login di sini", href="/login", className="text-info")
                            ], className="text-center mb-0")
                        ])
                    ], className="shadow")
                ], md=6, lg=4, className="mx-auto")
            ], className="min-vh-75 align-items-center justify-content-center")
        ], className="py-5")
    ])


# ============================================================
# PAGE: LOGIN
# ============================================================

def create_login_page():
    """Create login page"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4([
                                html.I(className="fas fa-sign-in-alt me-2"),
                                "Login"
                            ], className="mb-0 text-center")
                        ]),
                        dbc.CardBody([
                            # Email
                            dbc.Label("Email", html_for="login-email"),
                            dbc.Input(
                                id="login-email",
                                type="email",
                                placeholder="email@example.com",
                                className="mb-3"
                            ),

                            # Password
                            dbc.Label("Password", html_for="login-password"),
                            dbc.Input(
                                id="login-password",
                                type="password",
                                placeholder="Password Anda",
                                className="mb-3"
                            ),

                            # Submit button
                            dbc.Button([
                                html.I(className="fas fa-sign-in-alt me-2"),
                                "Login"
                            ], id="login-submit", color="primary", className="w-100 mb-3"),

                            # Feedback
                            html.Div(id="login-feedback"),

                            html.Hr(),

                            # Signup link
                            html.P([
                                "Belum punya akun? ",
                                dcc.Link("Daftar di sini", href="/signup", className="text-info")
                            ], className="text-center mb-2"),

                            # Resend verification
                            html.P([
                                "Belum menerima email verifikasi? ",
                                dbc.Button("Kirim Ulang", id="resend-verification-btn",
                                          color="link", size="sm", className="p-0")
                            ], className="text-center small mb-0")
                        ])
                    ], className="shadow")
                ], md=6, lg=4, className="mx-auto")
            ], className="min-vh-75 align-items-center justify-content-center")
        ], className="py-5")
    ])


# ============================================================
# PAGE: EMAIL VERIFICATION
# ============================================================

def create_verify_page(token: str = None):
    """Create email verification page"""
    if not token:
        return html.Div([
            dbc.Container([
                dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    "Token verifikasi tidak valid."
                ], color="danger", className="text-center")
            ], className="py-5")
        ])

    # Try to verify
    result = verify_user_email(token)

    if result['success']:
        return html.Div([
            dbc.Container([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-check-circle fa-5x text-success mb-3"),
                        ], className="text-center"),
                        html.H3("Email Berhasil Diverifikasi!", className="text-center text-success"),
                        html.P(f"Selamat {result['user']['username']}, akun Anda sudah aktif.",
                              className="text-center text-muted"),
                        html.P("Anda mendapatkan akses Trial selama 7 hari.", className="text-center"),
                        html.Div([
                            dbc.Button([
                                html.I(className="fas fa-sign-in-alt me-2"),
                                "Login Sekarang"
                            ], href="/login", color="success", className="me-2"),
                        ], className="text-center mt-4")
                    ])
                ], className="shadow")
            ], className="py-5", style={"maxWidth": "500px", "margin": "0 auto"})
        ])
    else:
        return html.Div([
            dbc.Container([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-times-circle fa-5x text-danger mb-3"),
                        ], className="text-center"),
                        html.H3("Verifikasi Gagal", className="text-center text-danger"),
                        html.P(result['error'], className="text-center text-muted"),
                        html.Div([
                            dbc.Button("Kembali ke Login", href="/login", color="secondary"),
                        ], className="text-center mt-4")
                    ])
                ], className="shadow")
            ], className="py-5", style={"maxWidth": "500px", "margin": "0 auto"})
        ])


# ============================================================
# HELPER: ACCUMULATION/DISTRIBUTION VALIDATION CARD (15 Elements)
# ============================================================

def create_validation_card(stock_code: str):
    """
    Create comprehensive validation card with ALL 15+ trust-building elements
    sesuai dengan spec accumulation.txt
    """
    try:
        validation = get_comprehensive_validation(stock_code, 30)
        company = get_company_profile(stock_code)
        timeline_data = get_daily_flow_timeline(stock_code, 20)
        market_status = get_market_status(stock_code, 30)
        risk_events = get_risk_events(stock_code)
        all_brokers = get_all_broker_details(stock_code, 30)

        # Multi-horizon Volume vs Price analysis
        price_df = get_price_data(stock_code)
        vol_price_multi = calculate_volume_price_multi_horizon(price_df) if not price_df.empty else {
            'status': 'NO_DATA', 'significance': 'INSUFFICIENT', 'horizons': {}, 'conclusion': 'Data tidak tersedia'
        }
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader(html.H5("Signal Validation", className="mb-0")),
            dbc.CardBody(html.P(f"Error loading validation: {str(e)}", className="text-danger"))
        ], className="mb-4", color="dark")

    if validation.get('error'):
        return dbc.Card([
            dbc.CardHeader(html.H5("Signal Validation", className="mb-0")),
            dbc.CardBody(html.P(validation['error'], className="text-warning"))
        ], className="mb-4", color="dark")

    # Extract data
    current_price = validation.get('current_price', 0)
    analysis_date = validation.get('analysis_date')
    validations = validation.get('validations', {})
    summary = validation.get('summary', {})
    confidence = validation.get('confidence', {})
    detection = validation.get('detection')
    markup_trigger = validation.get('markup_trigger', {})
    decision_rule = validation.get('decision_rule', {})

    # Calculate score (0-100)
    pass_rate = confidence.get('pass_rate', 0)
    overall_signal = summary.get('overall_signal', 'NETRAL')

    # Score color & status label
    if pass_rate >= 80:
        score_color = 'success'
        status_label = 'Strong Accumulation' if overall_signal == 'AKUMULASI' else 'Strong Distribution' if overall_signal == 'DISTRIBUSI' else 'Strong Signal'
    elif pass_rate >= 60:
        score_color = 'success'
        status_label = 'Weak Accumulation' if overall_signal == 'AKUMULASI' else 'Weak Distribution' if overall_signal == 'DISTRIBUSI' else 'Moderate Signal'
    elif pass_rate >= 40:
        score_color = 'warning'
        status_label = 'Neutral'
    else:
        score_color = 'danger'
        status_label = 'Weak Distribution' if overall_signal == 'DISTRIBUSI' else 'Weak Signal'

    # Signal color
    signal_colors = {'AKUMULASI': 'success', 'DISTRIBUSI': 'danger', 'NETRAL': 'secondary'}
    signal_color = signal_colors.get(overall_signal, 'secondary')

    # Market status color
    market_colors = {'SIDEWAYS': 'info', 'TRENDING UP': 'success', 'TRENDING DOWN': 'danger', 'UNKNOWN': 'secondary'}
    market_color = market_colors.get(market_status.get('status', 'UNKNOWN'), 'secondary')

    # CPR data
    cpr = validations.get('cpr', {})
    cpr_value = cpr.get('avg_cpr', 0.5)
    cpr_pct = int(cpr_value * 100)

    # UV/DV data
    uvdv = validations.get('uvdv', {})
    uvdv_ratio = uvdv.get('uvdv_ratio', 1.0)

    # Broker influence
    broker_inf = validations.get('broker_influence', {})
    top_accum = broker_inf.get('top_accumulators', [])[:5]
    top_distrib = broker_inf.get('top_distributors', [])[:5]

    # Persistence
    persistence = validations.get('persistence', {})
    max_streak = persistence.get('max_streak', 0)
    persistent_brokers = persistence.get('persistent_brokers', [])[:5]

    # Failed breaks
    failed = validations.get('failed_breaks', {})
    failed_bd = failed.get('failed_breakdowns', 0)
    failed_bo = failed.get('failed_breakouts', 0)

    # Elasticity
    elasticity = validations.get('elasticity', {})
    vol_change = elasticity.get('volume_change_pct', 0)
    price_change = elasticity.get('price_change_pct', 0)

    # Rotation
    rotation = validations.get('rotation', {})
    num_accum = rotation.get('num_accumulators', 0)
    num_distrib = rotation.get('num_distributors', 0)

    # === 1. ONE-LINE INSIGHT (gunakan insight dari validation yang sudah context-aware) ===
    insight_text = summary.get('insight', f"Harga bergerak {market_status.get('status', 'N/A').lower()} dengan sinyal campuran dari {confidence.get('passed', 0)}/6 validasi.")

    # === 6. TIMELINE PERSISTENCE (Daily Strip) ===
    timeline_strip = []
    for day in timeline_data:
        buy_lot = day.get('buy_lot', 0)
        sell_lot = day.get('sell_lot', 0)
        date_str = str(day.get('date', ''))[:10] if day.get('date') else 'N/A'

        if day['status'] == 'BUY':
            icon_class = "text-success"
            icon = "*"
            title = f"{date_str}: BUY Dominan (Buy:{buy_lot:,.0f} vs Sell:{sell_lot:,.0f})"
        elif day['status'] == 'SELL':
            icon_class = "text-danger"
            icon = "*"
            title = f"{date_str}: SELL Dominan (Buy:{buy_lot:,.0f} vs Sell:{sell_lot:,.0f})"
        else:
            icon_class = "text-secondary"
            icon = "o"
            title = f"{date_str}: Seimbang (Buy:{buy_lot:,.0f} vs Sell:{sell_lot:,.0f})"
        timeline_strip.append(html.Span(icon, className=f"{icon_class} me-1 fs-4", title=title, style={"cursor": "pointer"}))

    # === 11. CHECKLIST VALIDASI ===
    check_mapping = [
        ('cpr', 'Sideway Valid (CPR)', cpr.get('explanation', '')),
        ('uvdv', 'Volume Absorption', uvdv.get('explanation', '')),
        ('broker_influence', 'Broker Influence', broker_inf.get('explanation', '')),
        ('persistence', 'Persistence Cukup', persistence.get('explanation', '')),
        ('elasticity', 'Elastisitas Mendukung', elasticity.get('explanation', '')),
        ('rotation', 'Multi-Broker Selaras', rotation.get('explanation', '')),
    ]
    checklist_items = []
    for key, label, explanation in check_mapping:
        v = validations.get(key, {})
        passed = v.get('passed', False)
        icon = "YES" if passed else "NO"
        color = "text-success" if passed else "text-danger"
        checklist_items.append(
            html.Div([
                html.Span(icon, className=f"{color} me-2 fw-bold small"),
                html.Span(label, className="small"),
            ], className="mb-1", title=explanation)
        )

    # === 3. CONFIDENCE LEVEL ===
    conf_level = confidence.get('level', 'LOW')
    conf_colors = {'VERY_HIGH': 'success', 'HIGH': 'success', 'MEDIUM': 'warning', 'LOW': 'danger', 'VERY_LOW': 'danger'}
    conf_color = conf_colors.get(conf_level, 'secondary')

    # === BUILD BROKER HORIZONTAL BARS ===
    def create_broker_bars(brokers, is_buy=True):
        if not brokers:
            return html.Small("Tidak ada data", className="text-muted")
        max_val = max(abs(b.get('net_lot', 0)) for b in brokers) if brokers else 1
        bars = []
        for b in brokers[:5]:
            net_lot = b.get('net_lot', 0)
            pct = (abs(net_lot) / max_val * 100) if max_val > 0 else 0
            color = "success" if is_buy else "danger"
            bg_color = "#28a745" if is_buy else "#dc3545"
            broker_code = b.get('broker_code', 'N/A')
            bars.append(html.Div([
                html.Span([colored_broker(broker_code, with_badge=True)], style={"width": "55px", "display": "inline-block", "flexShrink": "0"}),
                html.Div([
                    html.Div(style={"width": f"{max(pct, 5)}%", "height": "18px", "backgroundColor": bg_color, "borderRadius": "3px", "minWidth": "5px"})
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.1)", "borderRadius": "3px", "margin": "0 8px"}),
                html.Span(f"{'+' if is_buy else ''}{net_lot:,.0f}", className=f"text-{color} small fw-bold", style={"width": "90px", "textAlign": "right", "flexShrink": "0"})
            ], className="d-flex align-items-center mb-1"))
        return html.Div(bars)

    # === BUILD RISK FLAGS ===
    risk_flags = []
    for risk in risk_events:
        severity_color = {'HIGH': 'danger', 'MEDIUM': 'warning', 'LOW': 'info'}.get(risk.get('severity', 'LOW'), 'secondary')
        risk_flags.append(
            dbc.Alert([
                html.Span(risk.get('icon', '[!]'), className="me-2"),
                html.Span(risk.get('message', ''), className="small")
            ], color=severity_color, className="py-1 px-2 mb-1 small")
        )

    return dbc.Card([
        # === 0. HEADER METADATA ===
        dbc.CardHeader([
            html.Div([
                html.H5([
                    html.I(className="fas fa-chart-area me-2"),
                    "Deteksi Akumulasi & Distribusi"
                ], className="mb-0 d-inline text-info"),
                dbc.Badge(overall_signal, color=signal_color, className="ms-2 px-3 py-2"),
            ], className="d-flex align-items-center"),
        ], style={"background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)", "borderBottom": "2px solid #0f3460"}),

        dbc.CardBody([
            # === HEADER INFO ROW ===
            html.Div([
                html.Small([
                    html.I(className="fas fa-info-circle me-1 text-info"),
                    "Info dasar saham & kondisi market saat ini. Range <15% = Sideways (ideal untuk deteksi akumulasi)."
                ], className="text-muted fst-italic mb-2 d-block")
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(stock_code, className="text-warning mb-0 fw-bold"),
                        html.P(company.get('company_name', stock_code), className="text-muted mb-0 small"),
                    ])
                ], md=2),
                dbc.Col([
                    html.Div([
                        html.Small("Periode Analisa", className="text-muted d-block"),
                        html.Span(f"30 hari terakhir", className="fw-bold"),
                    ])
                ], md=2),
                dbc.Col([
                    html.Div([
                        html.Small("Sinyal Pertama Terdeteksi", className="text-muted d-block"),
                        html.Div([
                            html.Span(
                                f"{str(detection.get('detection_date', ''))[:10]}" if detection and detection.get('detection_date') else "Belum ada",
                                className="fw-bold me-2"
                            ),
                            dbc.Badge(
                                f"{detection.get('detection_signal', 'N/A')} ({detection.get('detection_strength', '')})" if detection and detection.get('detection_signal') else "N/A",
                                color="success" if detection and detection.get('detection_signal') == 'ACCUMULATION' else "danger" if detection and detection.get('detection_signal') == 'DISTRIBUTION' else "secondary",
                                className="small"
                            ) if detection and detection.get('detection_signal') else None,
                        ]),
                        html.Small(
                            f"@ Rp {detection.get('detection_price', 0):,.0f}" if detection and detection.get('detection_price') else "",
                            className="text-warning"
                        ),
                    ])
                ], md=3),
                dbc.Col([
                    html.Div([
                        html.Small("Status Market", className="text-muted d-block"),
                        dbc.Badge(market_status.get('status', 'N/A'), color=market_color, className="px-2"),
                        html.Small(f" ({market_status.get('range_pct', 0):.1f}%)", className="text-muted"),
                    ])
                ], md=2),
                dbc.Col([
                    html.Div([
                        html.Small("Harga Sekarang", className="text-muted d-block"),
                        html.Span(f"Rp {current_price:,.0f}", className="fw-bold text-info"),
                        html.Small(
                            f" ({detection.get('price_change_pct', 0):+.1f}%)" if detection and detection.get('detection_price') else "",
                            className=f"text-{'success' if detection and detection.get('price_change_pct', 0) >= 0 else 'danger'}"
                        ) if detection else None,
                    ])
                ], md=3),
            ], className="mb-3 p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"}),

            # === SIGNAL HISTORY TIMELINE ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-history me-2"), "Riwayat Perubahan Sinyal"], className="mb-0 text-info d-inline"),
                    html.Small(" - Timeline dari deteksi pertama sampai sekarang", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Timeline menunjukkan kapan sinyal berubah (Akumulasi <-> Distribusi <-> Netral) dan tingkat kekuatannya (Weak/Moderate/Strong)."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    html.Div([
                        html.Div([
                            html.Div([
                                # Date
                                html.Span(
                                    str(h.get('date', ''))[:10],
                                    className="fw-bold small",
                                    style={"width": "85px", "display": "inline-block"}
                                ),
                                # Signal badge
                                dbc.Badge(
                                    f"{h.get('signal', 'N/A')}" + (f" ({h.get('strength', '')})" if h.get('strength') else ""),
                                    color="success" if h.get('signal') == 'ACCUMULATION' else "danger" if h.get('signal') == 'DISTRIBUTION' else "secondary",
                                    className="me-2",
                                    style={"width": "150px", "textAlign": "center"}
                                ),
                                # Price
                                html.Span(
                                    f"Rp {h.get('price', 0):,.0f}",
                                    className="text-warning me-3 small",
                                    style={"width": "90px", "display": "inline-block"}
                                ),
                                # CPR
                                html.Span(
                                    f"CPR: {h.get('cpr', 0):.0f}%",
                                    className="text-muted small me-2",
                                    style={"width": "70px", "display": "inline-block"}
                                ),
                                # Net lot
                                html.Span(
                                    f"Net: {h.get('net_lot', 0):+,.0f}",
                                    className=f"small text-{'success' if h.get('net_lot', 0) > 0 else 'danger' if h.get('net_lot', 0) < 0 else 'muted'}",
                                    style={"width": "100px", "display": "inline-block"}
                                ),
                            ], className="d-flex align-items-center py-1 px-2 rounded mb-1",
                               style={"backgroundColor": "rgba(40,167,69,0.1)" if h.get('signal') == 'ACCUMULATION' else "rgba(220,53,69,0.1)" if h.get('signal') == 'DISTRIBUTION' else "rgba(255,255,255,0.03)"})
                            for h in (detection.get('signal_history', []) if detection else [])[-15:]  # Show last 15 changes
                        ]) if detection and detection.get('signal_history') else html.Small("Tidak ada riwayat sinyal", className="text-muted"),
                    ], style={"maxHeight": "250px", "overflowY": "auto"}),
                    # Legend
                    html.Div([
                        html.Hr(className="my-2"),
                        html.Small([
                            html.Span("Keterangan: ", className="text-muted me-2"),
                            dbc.Badge("ACCUMULATION", color="success", className="me-1"), html.Small("= Pembeli dominan ", className="text-muted me-2"),
                            dbc.Badge("DISTRIBUTION", color="danger", className="me-1"), html.Small("= Penjual dominan ", className="text-muted me-2"),
                            dbc.Badge("NEUTRAL", color="secondary", className="me-1"), html.Small("= Seimbang", className="text-muted"),
                        ]),
                        html.Br(),
                        html.Small([
                            html.Span("Strength: ", className="text-muted me-2"),
                            html.Span("STRONG", className="text-success me-1"), html.Small("= CPR >70%/>30% + Net tinggi + >5 broker ", className="text-muted me-2"),
                            html.Span("MODERATE", className="text-warning me-1"), html.Small("= Standar ", className="text-muted me-2"),
                            html.Span("WEAK", className="text-danger me-1"), html.Small("= CPR borderline/<3 broker", className="text-muted"),
                        ], className="d-block mt-1"),
                    ], className="mt-2")
                ])
            ], className="mb-3", color="dark", outline=True),

            # === MARKUP TRIGGER ALERT (jika aktif) ===
            dbc.Alert([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span("[FIRE]", style={"fontSize": "28px"}),
                            html.Strong(" MARKUP TRIGGER DETECTED", className="text-warning fs-5 ms-2"),
                        ], className="d-flex align-items-center"),
                        html.P([
                            "Harga breakout ",
                            html.Strong(f"+{markup_trigger.get('breakout_pct', 0):.1f}%"),
                            " dari resistance terdekat (Rp ",
                            html.Strong(f"{markup_trigger.get('recent_high', 0):,.0f}"),
                            ") setelah akumulasi ",
                            html.Strong(f"({markup_trigger.get('source_strength', 'N/A')})"),
                            " terdeteksi sebelumnya."
                        ], className="mb-1 small"),
                    ], md=8),
                    dbc.Col([
                        html.Div([
                            html.Small("Volume Spike", className="text-muted d-block"),
                            dbc.Badge(
                                f"+{markup_trigger.get('volume_spike_pct', 0):.0f}%" if markup_trigger.get('volume_spike') else "Normal",
                                color="success" if markup_trigger.get('volume_spike') else "secondary",
                                className="me-2"
                            ),
                        ], className="mb-2"),
                        html.Div([
                            html.Small("Net Flow Hari Ini", className="text-muted d-block"),
                            html.Span(
                                f"{markup_trigger.get('net_flow', 0):+,.0f} lot",
                                className=f"fw-bold text-{'success' if markup_trigger.get('positive_flow') else 'danger'}"
                            ),
                        ]),
                    ], md=4, className="text-end"),
                ]),
                html.Hr(className="my-2"),
                html.Small([
                    html.I(className="fas fa-info-circle me-1"),
                    "Markup Phase = transisi dari akumulasi ke kenaikan harga. Ini validasi retrospektif bahwa akumulasi sebelumnya berhasil."
                ], className="text-muted fst-italic")
            ], color="warning", className="mb-3", style={"backgroundColor": "rgba(255,193,7,0.15)", "border": "2px solid #ffc107"})
            if markup_trigger.get('markup_triggered') else html.Div(),

            # === 1. ONE-LINE INSIGHT ===
            html.Div([
                html.H6([
                    html.I(className="fas fa-lightbulb me-2 text-warning"),
                    insight_text
                ], className="text-info mb-1"),
            ], className="border-start border-warning border-4 ps-3 mb-3 py-2", style={"backgroundColor": "rgba(255,193,7,0.05)"}),

            # === 2. SCORE GAUGE + 3. CONFIDENCE ===
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Small([html.I(className="fas fa-info-circle me-1"), "Skor total dari 6 validasi. >60 = sinyal kuat"], className="text-muted d-block mb-2 small"),
                        html.Div([
                            html.Span(f"{pass_rate:.0f}", className=f"display-3 text-{score_color} fw-bold"),
                            html.Span("/100", className="text-muted fs-4"),
                        ], className="text-center"),
                        html.Div([
                            dbc.Progress(value=pass_rate, color=score_color, className="mb-2", style={"height": "10px"}),
                        ]),
                        html.Div([
                            html.Span(status_label, className=f"text-{score_color} fw-bold"),
                        ], className="text-center"),
                    ], className="p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"})
                ], md=4),
                dbc.Col([
                    html.Div([
                        html.Small([html.I(className="fas fa-info-circle me-1"), "Tingkat keyakinan berdasarkan jumlah validasi yang lolos"], className="text-muted d-block mb-2 small"),
                        html.Strong("Confidence Level", className="d-block mb-2"),
                        html.Div([
                            dbc.Badge(conf_level.replace('_', ' '), color=conf_color, className="px-4 py-2 fs-6"),
                        ], className="mb-2"),
                        html.Small(f"Based on: {confidence.get('passed', 0)} of 6 validations passed", className="text-muted d-block"),
                    ], className="p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"})
                ], md=4),
                dbc.Col([
                    html.Div([
                        html.Small([html.I(className="fas fa-info-circle me-1"), "Kondisi trend harga dalam periode analisis"], className="text-muted d-block mb-2 small"),
                        html.Strong("Fase Market", className="d-block mb-2"),
                        dbc.Badge(market_status.get('status', 'N/A'), color=market_color, className="px-3 py-2 me-2"),
                        html.Div([
                            html.Small(f"Change: {market_status.get('change_pct', 0):+.1f}%", className=f"text-{'success' if market_status.get('change_pct', 0) >= 0 else 'danger'} d-block mt-2"),
                            html.Small(f"Low: Rp {market_status.get('low', 0):,.0f}", className="text-muted d-block"),
                            html.Small(f"High: Rp {market_status.get('high', 0):,.0f}", className="text-muted d-block"),
                        ], className="mt-2"),
                    ], className="p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"})
                ], md=4),
            ], className="mb-4"),

            # === DECISION RULE PANEL ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-compass me-2"), "Decision Rule"], className="mb-0 text-warning d-inline"),
                    html.Small(" - Apa yang harus dilakukan sekarang?", className="text-muted ms-2")
                ], style={"background": "linear-gradient(135deg, #2d2d44 0%, #1a1a2e 100%)"}),
                dbc.CardBody([
                    dbc.Row([
                        # Decision Badge
                        dbc.Col([
                            html.Div([
                                html.Span(decision_rule.get('icon', '[~]'), style={"fontSize": "40px"}),
                                html.H3(decision_rule.get('decision', 'WAIT'), className=f"text-{decision_rule.get('color', 'secondary')} fw-bold mb-0 mt-2"),
                            ], className="text-center")
                        ], md=2),
                        # Reason & Entry Zone
                        dbc.Col([
                            html.P(decision_rule.get('reason', ''), className="mb-2"),
                            html.Div([
                                html.Small([
                                    html.I(className="fas fa-map-marker-alt me-1 text-success"),
                                    "Zona Entry: ",
                                    html.Strong(f"Rp {decision_rule.get('entry_zone', {}).get('low', 0):,.0f} - Rp {decision_rule.get('entry_zone', {}).get('high', 0):,.0f}") if decision_rule.get('entry_zone') else "N/A"
                                ], className="d-block text-muted"),
                                html.Small([
                                    html.I(className="fas fa-shield-alt me-1 text-info"),
                                    "Support: ",
                                    html.Strong(f"Rp {decision_rule.get('support_level', 0):,.0f}") if decision_rule.get('support_level') else "N/A"
                                ], className="d-block text-muted"),
                                html.Small([
                                    html.I(className="fas fa-exclamation-triangle me-1 text-danger"),
                                    "Invalidation: ",
                                    html.Strong(f"Rp {decision_rule.get('invalidation_price', 0):,.0f}") if decision_rule.get('invalidation_price') else "N/A",
                                    html.Span(" (tutup posisi jika tembus)", className="text-muted fst-italic")
                                ], className="d-block text-muted"),
                            ], className="mt-2")
                        ], md=7),
                        # Current Position vs Entry Zone
                        dbc.Col([
                            html.Div([
                                html.Small("Posisi Harga Saat Ini", className="text-muted d-block mb-1"),
                                dbc.Badge(
                                    "DI ATAS ZONA" if decision_rule.get('current_vs_entry') == 'ABOVE' else
                                    "DI ZONA ENTRY" if decision_rule.get('current_vs_entry') == 'IN_ZONE' else
                                    "DI BAWAH ZONA",
                                    color="warning" if decision_rule.get('current_vs_entry') == 'ABOVE' else
                                          "success" if decision_rule.get('current_vs_entry') == 'IN_ZONE' else
                                          "danger",
                                    className="px-3 py-2"
                                ),
                                html.Small(
                                    "Tunggu pullback" if decision_rule.get('current_vs_entry') == 'ABOVE' else
                                    "Peluang entry" if decision_rule.get('current_vs_entry') == 'IN_ZONE' else
                                    "Waspada breakdown",
                                    className="d-block mt-1 text-muted fst-italic"
                                )
                            ], className="text-center")
                        ], md=3),
                    ]),
                    # Legend
                    html.Hr(className="my-2"),
                    html.Div([
                        html.Small([
                            html.Span("[~]", className="me-1"), html.Span("WAIT", className="text-secondary fw-bold me-2"), html.Span("= Observasi ", className="text-muted me-3"),
                            html.Span("[G]", className="me-1"), html.Span("ENTRY", className="text-success fw-bold me-2"), html.Span("= Masuk bertahap ", className="text-muted me-3"),
                            html.Span("[+]", className="me-1"), html.Span("ADD", className="text-primary fw-bold me-2"), html.Span("= Tambah posisi ", className="text-muted me-3"),
                            html.Span("[H]", className="me-1"), html.Span("HOLD", className="text-info fw-bold me-2"), html.Span("= Tahan/kelola ", className="text-muted me-3"),
                            html.Span("[!!]", className="me-1"), html.Span("EXIT", className="text-danger fw-bold me-2"), html.Span("= Kurangi/keluar", className="text-muted"),
                        ])
                    ])
                ])
            ], className="mb-3", style={"border": f"2px solid var(--bs-{decision_rule.get('color', 'secondary')})", "background": "rgba(0,0,0,0.2)"}),

            # === 4. CPR INDICATOR ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-crosshairs me-2"), "CPR Indicator (Close Position Ratio)"], className="mb-0 text-info d-inline"),
                    html.Small(" - Di mana harga ditutup setiap hari?", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "CPR mengukur posisi harga penutupan dalam range harian. Jika close selalu dekat HIGH = pembeli menang, dekat LOW = penjual menang."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                dbc.Progress(value=cpr_pct, color="success" if cpr_pct >= 60 else "warning" if cpr_pct >= 40 else "danger", className="mb-2", style={"height": "25px"}),
                                html.Div([
                                    html.Span("LOW (Seller)", className="text-danger small"),
                                    html.Span(f"{cpr_pct}%", className=f"text-{score_color} fw-bold fs-5 mx-3"),
                                    html.Span("HIGH (Buyer)", className="text-success small"),
                                ], className="d-flex justify-content-between"),
                            ])
                        ], md=8),
                        dbc.Col([
                            html.P(
                                "Pembeli dominan - close dekat HIGH." if cpr_pct >= 60 else
                                "Penjual dominan - close dekat LOW." if cpr_pct <= 40 else
                                "Seimbang - close di tengah range.",
                                className="text-muted small fst-italic mb-0"
                            )
                        ], md=4),
                    ])
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 5. VOLUME VS PRICE RANGE (MULTI-HORIZON) ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-balance-scale me-2"), "Volume vs Price (Multi-Horizon Analysis)"], className="mb-0 text-info d-inline"),
                    html.Small(" - Absorption detection dengan validasi multi-waktu", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Volume dinilai signifikan jika peningkatan bertahan minimal 3-5 hari tanpa diikuti pelebaran range harga. "
                        "Lonjakan volume satu hari belum tentu akumulasi - sistem mencari konsistensi, bukan kebetulan."
                    ], className="text-muted d-block mb-3 fst-italic"),

                    # Significance Badge
                    html.Div([
                        dbc.Badge(
                            vol_price_multi.get('significance', 'NONE'),
                            color="success" if vol_price_multi.get('significance') == 'SIGNIFICANT' else
                                  "info" if vol_price_multi.get('significance') == 'MODERATE' else
                                  "warning" if vol_price_multi.get('significance') == 'EARLY' else "secondary",
                            className="px-3 py-2 fs-6"
                        ),
                    ], className="text-center mb-3"),

                    # Multi-Horizon Breakdown Table
                    html.Table([
                        html.Thead([
                            html.Tr([
                                html.Th("Horizon", className="text-center", style={"width": "20%"}),
                                html.Th("Volume D", className="text-center", style={"width": "20%"}),
                                html.Th("Price D", className="text-center", style={"width": "20%"}),
                                html.Th("Range", className="text-center", style={"width": "20%"}),
                                html.Th("AKSI?", className="text-center", style={"width": "20%"}, title="Akumulasi/Distribusi"),
                            ])
                        ]),
                        html.Tbody([
                            # 1 Day (Micro)
                            html.Tr([
                                html.Td([html.Strong("1 Hari"), html.Br(), html.Small("(Micro)", className="text-muted")], className="text-center"),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('1d', {}).get('volume_change_pct', 0):+.0f}%"
                                    if vol_price_multi.get('horizons', {}).get('1d') else "-",
                                    className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('1d', {}).get('volume_change_pct', 0) > 0 else 'danger'}"
                                ),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('1d', {}).get('price_change_pct', 0):+.1f}%"
                                    if vol_price_multi.get('horizons', {}).get('1d') else "-",
                                    className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('1d', {}).get('price_change_pct', 0) > 0 else 'danger'}"
                                ),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('1d', {}).get('price_range_pct', 0):.1f}%"
                                    if vol_price_multi.get('horizons', {}).get('1d') else "-",
                                    className="text-center"
                                ),
                                html.Td(
                                    dbc.Badge(
                                        vol_price_multi.get('horizons', {}).get('1d', {}).get('absorption_type', 'Ya'),
                                        color="success" if vol_price_multi.get('horizons', {}).get('1d', {}).get('absorption_type') == 'AKUMULASI' else "danger"
                                    ) if vol_price_multi.get('horizons', {}).get('1d', {}).get('is_absorption') else
                                    dbc.Badge("Tidak", color="secondary"),
                                    className="text-center"
                                ),
                            ], style={"backgroundColor": "rgba(255,193,7,0.1)" if vol_price_multi.get('micro_absorption') else "transparent"}),

                            # 5 Day (Core) - MOST IMPORTANT
                            html.Tr([
                                html.Td([html.Strong("5 Hari", className="text-warning"), html.Br(), html.Small("(Core)", className="text-warning")], className="text-center"),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('5d', {}).get('volume_change_pct', 0):+.0f}%"
                                    if vol_price_multi.get('horizons', {}).get('5d') else "-",
                                    className=f"text-center fw-bold text-{'success' if vol_price_multi.get('horizons', {}).get('5d', {}).get('volume_change_pct', 0) > 0 else 'danger'}"
                                ),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('5d', {}).get('price_change_pct', 0):+.1f}%"
                                    if vol_price_multi.get('horizons', {}).get('5d') else "-",
                                    className=f"text-center fw-bold text-{'success' if vol_price_multi.get('horizons', {}).get('5d', {}).get('price_change_pct', 0) > 0 else 'danger'}"
                                ),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('5d', {}).get('price_range_pct', 0):.1f}%"
                                    if vol_price_multi.get('horizons', {}).get('5d') else "-",
                                    className="text-center fw-bold"
                                ),
                                html.Td(
                                    dbc.Badge(
                                        vol_price_multi.get('horizons', {}).get('5d', {}).get('absorption_type', 'Ya'),
                                        color="success" if vol_price_multi.get('horizons', {}).get('5d', {}).get('absorption_type') == 'AKUMULASI' else "danger"
                                    ) if vol_price_multi.get('horizons', {}).get('5d', {}).get('is_absorption') else
                                    dbc.Badge("Tidak", color="secondary"),
                                    className="text-center fw-bold"
                                ),
                            ], style={"backgroundColor": "rgba(23,162,184,0.15)" if vol_price_multi.get('core_absorption') else "rgba(255,193,7,0.05)", "borderLeft": "3px solid #ffc107"}),

                            # 10 Day (Structural)
                            html.Tr([
                                html.Td([html.Strong("10 Hari"), html.Br(), html.Small("(Structural)", className="text-muted")], className="text-center"),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('10d', {}).get('volume_change_pct', 0):+.0f}%"
                                    if vol_price_multi.get('horizons', {}).get('10d') else "-",
                                    className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('10d', {}).get('volume_change_pct', 0) > 0 else 'danger'}"
                                ),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('10d', {}).get('price_change_pct', 0):+.1f}%"
                                    if vol_price_multi.get('horizons', {}).get('10d') else "-",
                                    className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('10d', {}).get('price_change_pct', 0) > 0 else 'danger'}"
                                ),
                                html.Td(
                                    f"{vol_price_multi.get('horizons', {}).get('10d', {}).get('price_range_pct', 0):.1f}%"
                                    if vol_price_multi.get('horizons', {}).get('10d') else "-",
                                    className="text-center"
                                ),
                                html.Td(
                                    dbc.Badge(
                                        vol_price_multi.get('horizons', {}).get('10d', {}).get('absorption_type', 'Ya'),
                                        color="success" if vol_price_multi.get('horizons', {}).get('10d', {}).get('absorption_type') == 'AKUMULASI' else "danger"
                                    ) if vol_price_multi.get('horizons', {}).get('10d', {}).get('is_absorption') else
                                    dbc.Badge("Tidak", color="secondary"),
                                    className="text-center"
                                ),
                            ], style={"backgroundColor": "rgba(40,167,69,0.1)" if vol_price_multi.get('structural_absorption') else "transparent"}),
                        ])
                    ], className="table table-sm table-dark", style={"fontSize": "12px"}),

                    # Legend
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Volume D = perubahan volume vs periode sebelumnya | ",
                        "Price D = perubahan harga close-to-close | ",
                        "Range = high-low sebagai % dari mid price"
                    ], className="text-muted d-block mb-2"),
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        html.Strong("AKUMULASI", className="text-success"), " = Volume naik + Harga turun (smart money beli) | ",
                        html.Strong("DISTRIBUSI", className="text-danger"), " = Volume naik + Harga naik (smart money jual)"
                    ], className="text-muted d-block mb-3"),

                    # KESIMPULAN
                    html.Hr(className="my-3"),
                    html.Div([
                        html.Strong([html.I(className="fas fa-clipboard-check me-2"), "Kesimpulan: "], className="text-info"),
                        html.Span(
                            vol_price_multi.get('conclusion', 'Tidak ada data'),
                            className="fw-bold " + (
                                "text-success" if vol_price_multi.get('significance') in ['SIGNIFICANT', 'MODERATE'] else
                                "text-warning" if vol_price_multi.get('significance') == 'EARLY' else
                                "text-info"
                            )
                        )
                    ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"})
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 6. TOP BROKER FLOW ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-users me-2"), "Top 5 Broker Flow (Influence-Based)"], className="mb-0 text-info d-inline"),
                    html.Small(" - Siapa pelaku utama?", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Broker dengan net buy terbesar = sedang mengumpulkan. Net sell terbesar = sedang melepas. Perhatikan siapa yang dominan."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    dbc.Row([
                        dbc.Col([
                            html.Strong("Net Buyers (Akumulasi)", className="text-success d-block mb-2"),
                            create_broker_bars(top_accum, is_buy=True)
                        ], md=6),
                        dbc.Col([
                            html.Strong("Net Sellers (Distribusi)", className="text-danger d-block mb-2"),
                            create_broker_bars(top_distrib, is_buy=False)
                        ], md=6),
                    ])
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 7. BROKER PERSISTENCE ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-history me-2"), "Broker Persistence"], className="mb-0 text-info d-inline"),
                    html.Small(" - Seberapa serius niat broker?", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Broker yang beli berturut-turut >= 5 hari = serius. >= 10 hari = kemungkinan institusi. Ini tanda niat kuat."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.Strong(f"{max_streak}", className="display-6 text-info"),
                                    html.Span(" hari berturut", className="text-muted"),
                                ]),
                                html.Small(
                                    "Institutional Behavior (>= 10 hari)" if max_streak >= 10 else "Meaningful (>= 5 hari)" if max_streak >= 5 else "Normal",
                                    className=f"text-{'success' if max_streak >= 10 else 'warning' if max_streak >= 5 else 'muted'}"
                                )
                            ])
                        ], md=4),
                        dbc.Col([
                            html.Strong("Top Persistent Brokers:", className="d-block mb-2 text-muted"),
                            html.Div([
                                html.Div([
                                    colored_broker(pb.get('broker', 'N/A'), with_badge=True),
                                    html.Span(f" {pb.get('max_accum_streak', 0)} hari", className="text-info small ms-2"),
                                    html.Span(f" (+{pb.get('total_net_lot', 0):,.0f} lot)", className="text-success small" if pb.get('total_net_lot', 0) > 0 else "text-danger small"),
                                ], className="mb-1 d-flex align-items-center") for pb in persistent_brokers[:3]
                            ] if persistent_brokers else [html.Small("Tidak ada data", className="text-muted")])
                        ], md=8),
                    ])
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 8. TIMELINE PERSISTENCE ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-stream me-2"), "Timeline Persistence (Daily Flow Strip)"], className="mb-0 text-info d-inline"),
                    html.Small(" - Pola harian 20 hari terakhir", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Setiap lingkaran = 1 hari. Hijau = pembeli dominan, Merah = penjual dominan. Banyak hijau berturut = akumulasi konsisten."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    html.Div([
                        html.Div(timeline_strip if timeline_strip else [html.Small("No timeline data", className="text-muted")], className="d-flex flex-wrap"),
                        html.Div([
                            html.Span("*", className="text-success me-1"), html.Small("Buy Dominan (>55%)", className="text-muted me-3"),
                            html.Span("*", className="text-danger me-1"), html.Small("Sell Dominan (<45%)", className="text-muted me-3"),
                            html.Span("o", className="text-secondary me-1"), html.Small("Seimbang", className="text-muted"),
                        ], className="mt-2 small"),
                        html.Small("Hover untuk detail tanggal dan volume", className="text-info d-block mt-1")
                    ])
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 9. FAILED MOVE COUNTER ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-shield-alt me-2"), "Failed Move Counter"], className="mb-0 text-info d-inline"),
                    html.Small(" - Berapa kali harga gagal tembus?", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Breakdown gagal = harga coba turun tapi ditahan (ada pembeli). Breakout gagal = harga coba naik tapi ditolak (ada penjual)."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Span(f"{failed_bd}x", className="display-6 text-success fw-bold"),
                                html.Span(" breakdown gagal", className="text-muted"),
                                html.Small("Harga coba turun tapi ditahan", className="d-block text-muted mt-1")
                            ], className="text-center")
                        ], md=6),
                        dbc.Col([
                            html.Div([
                                html.Span(f"{failed_bo}x", className="display-6 text-danger fw-bold"),
                                html.Span(" breakout gagal", className="text-muted"),
                                html.Small("Harga coba naik tapi ditolak", className="d-block text-muted mt-1")
                            ], className="text-center")
                        ], md=6),
                    ]),
                    html.Div([
                        html.Small(
                            "Support sangat kuat - ada niat akumulasi!" if failed_bd >= 3 else
                            "Support cukup kuat" if failed_bd >= 2 else
                            "Resistance sangat kuat - ada niat distribusi!" if failed_bo >= 3 else
                            "Resistance cukup kuat" if failed_bo >= 2 else
                            "Tidak ada false break signifikan",
                            className=f"text-{'success' if failed_bd >= 2 else 'danger' if failed_bo >= 2 else 'muted'} fst-italic"
                        )
                    ], className="text-center mt-2")
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 10. BEFORE VS AFTER ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-exchange-alt me-2"), "Before vs After Snapshot"], className="mb-0 text-info d-inline"),
                    html.Small(" - Ringkasan kondisi saat ini", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Table([
                        html.Thead([
                            html.Tr([
                                html.Th("Parameter", className="text-muted", style={"width": "30%"}),
                                html.Th("Nilai", className="text-center text-muted", style={"width": "35%"}),
                                html.Th("Status", className="text-center text-muted", style={"width": "35%"}),
                            ])
                        ]),
                        html.Tbody([
                            html.Tr([
                                html.Td("Volume Change"),
                                html.Td(f"{vol_change:+.0f}%", className=f"text-center text-{'success' if vol_change > 0 else 'danger'}"),
                                html.Td(dbc.Badge("Naik" if vol_change > 10 else "Turun" if vol_change < -10 else "Stabil", color="success" if vol_change > 10 else "danger" if vol_change < -10 else "secondary"), className="text-center"),
                            ]),
                            html.Tr([
                                html.Td("Price Range"),
                                html.Td(f"{market_status.get('range_pct', 0):.1f}%", className="text-center"),
                                html.Td(dbc.Badge("Sempit" if market_status.get('range_pct', 0) < 10 else "Lebar", color="info" if market_status.get('range_pct', 0) < 10 else "warning"), className="text-center"),
                            ]),
                            html.Tr([
                                html.Td("Broker Dominasi"),
                                html.Td(f"{num_accum} akum / {num_distrib} distrib", className="text-center"),
                                html.Td(dbc.Badge("Buyers" if num_accum > num_distrib else "Sellers" if num_distrib > num_accum else "Balanced", color="success" if num_accum > num_distrib else "danger" if num_distrib > num_accum else "secondary"), className="text-center"),
                            ]),
                            html.Tr([
                                html.Td("CPR"),
                                html.Td(f"{cpr_pct}%", className="text-center"),
                                html.Td(dbc.Badge(cpr.get('signal', 'N/A'), color="success" if cpr.get('signal') == 'AKUMULASI' else "danger" if cpr.get('signal') == 'DISTRIBUSI' else "secondary"), className="text-center"),
                            ]),
                        ])
                    ], className="table table-dark table-sm table-hover mb-0")
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 11. CHECKLIST VALIDASI ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-tasks me-2"), "Checklist Validasi (Trust Builder)"], className="mb-0 text-info d-inline"),
                    html.Small(" - 6 kriteria harus terpenuhi", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        "Semakin banyak YES = semakin kuat sinyal. Minimal 4/6 YES untuk sinyal yang dipercaya."
                    ], className="text-muted d-block mb-3 fst-italic"),
                    dbc.Row([
                        dbc.Col(checklist_items[:3], md=6),
                        dbc.Col(checklist_items[3:], md=6),
                    ])
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 12. MARKET CONTEXT + 13. RISK FLAG ===
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([html.I(className="fas fa-globe me-2"), "Market Context"], className="mb-0 text-info d-inline"),
                        ]),
                        dbc.CardBody([
                            html.Small("Kondisi pasar saat ini", className="text-muted d-block mb-2"),
                            html.Div([
                                dbc.Badge(f"Market: {market_status.get('status', 'N/A')}", color=market_color, className="me-2 mb-1"),
                                dbc.Badge(f"Signal: {overall_signal}", color=signal_color, className="me-2 mb-1"),
                            ])
                        ])
                    ], color="dark", outline=True)
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([html.I(className="fas fa-exclamation-triangle me-2"), "Risk Flags"], className="mb-0 text-warning d-inline"),
                        ]),
                        dbc.CardBody([
                            html.Small("Peringatan yang perlu diperhatikan", className="text-muted d-block mb-2"),
                            html.Div(risk_flags if risk_flags else [html.Small("Tidak ada risk flag aktif - aman", className="text-success")])
                        ])
                    ], color="dark", outline=True)
                ], md=6),
            ], className="mb-3"),

            # === 14. HIDDEN/EXPANDABLE SECTION ===
            dbc.Accordion([
                dbc.AccordionItem([
                    dbc.Tabs([
                        dbc.Tab([
                            html.Div([
                                html.H6("Parameter yang Digunakan:", className="text-info mb-3"),
                                html.Table([
                                    html.Tbody([
                                        html.Tr([html.Td("Analysis Days", className="text-muted"), html.Td(f"{DEFAULT_PARAMS['analysis_days']} hari")]),
                                        html.Tr([html.Td("Sideways Threshold", className="text-muted"), html.Td(f"< {DEFAULT_PARAMS['sideways_threshold']}%")]),
                                        html.Tr([html.Td("CPR Akumulasi", className="text-muted"), html.Td(f">= {DEFAULT_PARAMS['cpr_accum']*100:.0f}%")]),
                                        html.Tr([html.Td("CPR Distribusi", className="text-muted"), html.Td(f"<= {DEFAULT_PARAMS['cpr_distrib']*100:.0f}%")]),
                                        html.Tr([html.Td("UV/DV Akumulasi", className="text-muted"), html.Td(f"> {DEFAULT_PARAMS['uvdv_accum']}")]),
                                        html.Tr([html.Td("UV/DV Distribusi", className="text-muted"), html.Td(f"< {DEFAULT_PARAMS['uvdv_distrib']}")]),
                                        html.Tr([html.Td("Min Persistence", className="text-muted"), html.Td(f"{DEFAULT_PARAMS['min_persistence']} hari")]),
                                        html.Tr([html.Td("Min Broker Rotasi", className="text-muted"), html.Td(f"{DEFAULT_PARAMS['min_brokers_rotation']} broker")]),
                                    ])
                                ], className="table table-dark table-sm")
                            ], className="p-2")
                        ], label="Parameter & Rumus", tab_id="tab-params"),
                        dbc.Tab([
                            html.Div([
                                html.H6(f"Total {all_brokers.get('total_accumulators', 0)} Broker Akumulasi:", className="text-success mb-2"),
                                html.Div([
                                    html.Div([
                                        html.Span(b.get('broker_code', ''), className="fw-bold me-2"),
                                        html.Span(f"+{b.get('total_net_lot', 0):,.0f} lot", className="text-success small me-2"),
                                        html.Span(f"({b.get('buy_days', 0)} hari beli)", className="text-muted small"),
                                    ], className="mb-1") for b in all_brokers.get('accumulators', [])[:10]
                                ]),
                                html.Hr(),
                                html.H6(f"Total {all_brokers.get('total_distributors', 0)} Broker Distribusi:", className="text-danger mb-2"),
                                html.Div([
                                    html.Div([
                                        html.Span(b.get('broker_code', ''), className="fw-bold me-2"),
                                        html.Span(f"{b.get('total_net_lot', 0):,.0f} lot", className="text-danger small me-2"),
                                        html.Span(f"({b.get('sell_days', 0)} hari jual)", className="text-muted small"),
                                    ], className="mb-1") for b in all_brokers.get('distributors', [])[:10]
                                ]),
                            ], className="p-2", style={"maxHeight": "300px", "overflowY": "auto"})
                        ], label="Semua Broker", tab_id="tab-brokers"),
                        dbc.Tab([
                            html.Div([
                                html.H6("Raw Validation Data:", className="text-info mb-2"),
                                html.Pre(str({
                                    'overall_signal': overall_signal,
                                    'pass_rate': pass_rate,
                                    'cpr': cpr_pct,
                                    'uvdv_ratio': round(uvdv_ratio, 2),
                                    'num_accumulators': num_accum,
                                    'num_distributors': num_distrib,
                                    'max_streak': max_streak,
                                    'failed_breakdowns': failed_bd,
                                    'failed_breakouts': failed_bo,
                                    'vol_change': round(vol_change, 1),
                                    'price_change': round(price_change, 2),
                                }), className="text-muted small", style={"whiteSpace": "pre-wrap"})
                            ], className="p-2")
                        ], label="Raw Data", tab_id="tab-raw"),
                    ], active_tab="tab-params")
                ], title="Advanced Details (Click to Expand)")
            ], start_collapsed=True, className="mb-0"),
        ])
    ], className="mb-4", style={"background": "linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%)", "border": "1px solid #0f3460"})


# ============================================================
# HELPER: SIGNAL EDUCATION CARD (Dinamis - Bukan Template)
# ============================================================

def generate_signal_education_data(validation_data: dict, broker_data: dict = None) -> dict:
    """
    Generate dynamic educational explanation based on actual data.
    Bukan template - analisis berdasarkan kondisi real.
    """
    validations = validation_data.get('validations', {})
    decision_rule = validation_data.get('decision_rule', {})
    summary = validation_data.get('summary', {})
    detection = validation_data.get('detection', {})

    signal = summary.get('overall_signal', 'NETRAL')
    decision = decision_rule.get('decision', 'WAIT')

    # Get CPR
    cpr_data = validations.get('cpr', {})
    cpr_pct = int(cpr_data.get('avg_cpr', 0.5) * 100)

    education = {
        'signal_explanation': '',
        'why_not_buy': [],
        'wait_for_confirmation': [],
        'positive_factors': [],
        'warning_factors': []
    }

    # ==============================================================
    # ANALISIS KONDISI AKTUAL (bukan template)
    # ==============================================================

    # 1. Analisis CPR
    if cpr_pct < 30:
        education['why_not_buy'].append(f"CPR hanya {cpr_pct}% - harga ditutup dekat LOW, seller masih dominan")
        education['wait_for_confirmation'].append("CPR naik ke >50% (close mendekati HIGH)")
    elif cpr_pct > 70:
        education['positive_factors'].append(f"CPR {cpr_pct}% - buyer berhasil push harga ke atas")

    # 2. Analisis UVDV (Up Volume vs Down Volume)
    uvdv_data = validations.get('uvdv', {})
    uvdv_signal = uvdv_data.get('signal', '')
    if 'DISTRIBUSI' in str(uvdv_signal).upper():
        education['why_not_buy'].append("Volume saat harga turun lebih besar dari volume saat naik")
        education['wait_for_confirmation'].append("Volume buying > volume selling konsisten 3+ hari")
    elif 'AKUMULASI' in str(uvdv_signal).upper():
        education['positive_factors'].append("Volume buying mendominasi - institusi aktif mengumpulkan")

    # 3. Analisis Broker Influence
    broker_inf = validations.get('broker_influence', {})
    broker_sig = broker_inf.get('signal', '')
    if 'AKUMULASI' in str(broker_sig).upper():
        education['positive_factors'].append("Broker besar sedang akumulasi - smart money masuk")
    elif 'DISTRIBUSI' in str(broker_sig).upper():
        education['why_not_buy'].append("Broker besar sedang jual - smart money keluar")
        education['wait_for_confirmation'].append("Broker institusi berbalik dari sell ke buy")

    # 4. Analisis Persistence
    persist_data = validations.get('persistence', {})
    if persist_data.get('passed'):
        education['positive_factors'].append("Pola akumulasi sudah berlangsung konsisten (persistence)")

    # 5. Analisis Failed Breaks
    failed_data = validations.get('failed_breaks', {})
    if failed_data.get('signal') == 'AKUMULASI':
        education['positive_factors'].append("Ada buying saat breakdown gagal - support kuat")
    if failed_data.get('active_resistance'):
        education['why_not_buy'].append("Resistance aktif di atas - seller defend di level tersebut")
        education['wait_for_confirmation'].append("Breakout menembus resistance dengan volume tinggi")

    # 6. Analisis Elasticity
    elastic_data = validations.get('elasticity', {})
    elastic_sig = elastic_data.get('signal', '')
    if 'PENAHAN' in str(elastic_sig).upper():
        education['positive_factors'].append("Ada penahan di bawah - support aktif")
    elif 'DISTRIBUSI' in str(elastic_sig).upper():
        education['why_not_buy'].append("Harga mudah turun tapi sulit naik - supply masih besar")
        education['wait_for_confirmation'].append("Harga mampu bertahan di atas resistance sebelumnya")

    # 7. Analisis Rotation
    rotation_data = validations.get('rotation', {})
    rotation_sig = rotation_data.get('signal', '')
    if 'SEHAT' in str(rotation_sig).upper():
        education['positive_factors'].append("Rotasi broker sehat - bukan pump and dump")
    elif 'GORENG' in str(rotation_sig).upper():
        education['warning_factors'].append("Hati-hati: Pola rotasi tidak sehat, potensi saham gorengan")

    # 8. Broker data (jika tersedia)
    if broker_data:
        foreign_net = broker_data.get('foreign_net', 0)
        if foreign_net < 0:
            education['warning_factors'].append(f"Asing net sell - foreign outflow")
        elif foreign_net > 0:
            education['positive_factors'].append(f"Asing net buy - foreign inflow")

    # ==============================================================
    # GENERATE MAIN EXPLANATION
    # ==============================================================

    if signal == 'NETRAL' or decision == 'WAIT':
        if education['why_not_buy'] and education['positive_factors']:
            education['signal_explanation'] = (
                f"Meskipun ada {len(education['positive_factors'])} sinyal positif, "
                f"masih ada {len(education['why_not_buy'])} kondisi yang belum mendukung. "
                f"Sistem menunggu konfirmasi sebelum entry untuk melindungi dari false signal."
            )
        elif education['why_not_buy']:
            education['signal_explanation'] = (
                f"Terdeteksi {len(education['why_not_buy'])} kondisi negatif. "
                f"Sistem menyarankan WAIT sampai kondisi membaik."
            )
        else:
            education['signal_explanation'] = (
                f"Belum ada sinyal dominan yang jelas. "
                f"Kondisi market sideways atau dalam transisi."
            )

    elif 'AKUMULASI' in signal:
        education['signal_explanation'] = (
            f"{len(education['positive_factors'])} faktor positif terdeteksi. "
            f"Institusi sedang mengumpulkan saham."
        )

    elif 'DISTRIBUSI' in signal:
        education['signal_explanation'] = (
            f"Terdeteksi {len(education['why_not_buy'])} sinyal distribusi. "
            f"Institusi sedang menjual/mengurangi posisi."
        )

    return education


# ============================================================
# V6 SIDEWAYS ANALYSIS CARD - Adaptive Threshold
# ============================================================

def create_v6_analysis_card(stock_code: str):
    """
    Create V6 Sideways Analysis Card with:
    - Adaptive Threshold Detection
    - Accumulation/Distribution Phase
    - Entry Signal with Risk Management
    - Educational Content
    """
    try:
        v6_data = get_v6_analysis(stock_code)

        if v6_data.get('error'):
            return dbc.Card([
                dbc.CardBody(html.P(f"V6 Analysis Error: {v6_data['error']}", className="text-warning"))
            ], className="mb-4")

        sideways = v6_data.get('sideways', {})
        phase = v6_data.get('phase', {})
        entry = v6_data.get('entry', {})
        education = v6_data.get('education', {})
        current_price = v6_data.get('current_price', 0)

    except Exception as e:
        return dbc.Card([
            dbc.CardBody(html.P(f"Error loading V6 analysis: {str(e)}", className="text-danger"))
        ], className="mb-4")

    # Determine colors based on phase
    phase_colors = {
        'ACCUMULATION': {'bg': 'success', 'icon': 'fa-layer-group', 'label': 'AKUMULASI'},
        'DISTRIBUTION': {'bg': 'danger', 'icon': 'fa-hand-holding-dollar', 'label': 'DISTRIBUSI'},
        'NEUTRAL': {'bg': 'secondary', 'icon': 'fa-balance-scale', 'label': 'NETRAL'},
        'UNKNOWN': {'bg': 'secondary', 'icon': 'fa-question', 'label': 'UNKNOWN'}
    }
    phase_style = phase_colors.get(phase.get('phase', 'UNKNOWN'), phase_colors['UNKNOWN'])

    # Action colors
    action_colors = {
        'ENTRY': {'bg': 'success', 'icon': 'fa-check-circle'},
        'WATCH': {'bg': 'info', 'icon': 'fa-eye'},
        'EXIT': {'bg': 'danger', 'icon': 'fa-times-circle'},
        'WAIT': {'bg': 'secondary', 'icon': 'fa-clock'}
    }
    action_style = action_colors.get(entry.get('action', 'WAIT'), action_colors['WAIT'])

    # Build the card
    return dbc.Card([
        # Header
        dbc.CardHeader([
            html.Div([
                html.I(className="fas fa-chart-area me-2 text-info"),
                html.Strong("Analisis Sideways V6", className="text-info"),
                html.Small(" - Adaptive Threshold", className="text-muted ms-2")
            ], className="d-flex align-items-center")
        ], style={"background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)", "borderBottom": "2px solid #17a2b8"}),

        dbc.CardBody([
            # Row 1: Sideways Status + Phase
            dbc.Row([
                # Sideways Status
                dbc.Col([
                    html.Div([
                        html.H6("Status Sideways", className="text-muted mb-2"),
                        html.Div([
                            dbc.Badge(
                                "SIDEWAYS" if sideways.get('is_sideways') else "TRENDING",
                                color="info" if sideways.get('is_sideways') else "warning",
                                className="fs-6 me-2"
                            ),
                            html.Small(f"({sideways.get('days', 0)} hari)", className="text-muted")
                        ]),
                        html.Div([
                            html.Small([
                                f"Range: Rp {sideways.get('low', 0):,.0f} - Rp {sideways.get('high', 0):,.0f}"
                            ], className="text-muted d-block mt-1"),
                            html.Small([
                                f"Range%: {sideways.get('range_pct', 0):.1f}% ",
                                html.Span(
                                    f"({'<' if sideways.get('is_sideways') else '>'} {sideways.get('threshold', 0):.1f}%)",
                                    className="text-success" if sideways.get('is_sideways') else "text-warning"
                                )
                            ], className="text-muted d-block"),
                        ], className="mt-2")
                    ], className="p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"})
                ], md=4),

                # Phase Analysis
                dbc.Col([
                    html.Div([
                        html.H6("Fase Pasar", className="text-muted mb-2"),
                        html.Div([
                            html.I(className=f"fas {phase_style['icon']} me-2 fs-4 text-{phase_style['bg']}"),
                            html.Strong(phase_style['label'], className=f"fs-5 text-{phase_style['bg']}")
                        ]),
                        html.Div([
                            html.Small([
                                f"Volume Ratio: {phase.get('vol_ratio', 0):.2f}"
                            ], className="text-muted d-block mt-1"),
                            html.Small([
                                f"Score: ACC {phase.get('acc_score', 0)} vs DIST {phase.get('dist_score', 0)}"
                            ], className="text-muted d-block"),
                        ], className="mt-2")
                    ], className="p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"})
                ], md=4),

                # Action Signal
                dbc.Col([
                    html.Div([
                        html.H6("Sinyal Aksi", className="text-muted mb-2"),
                        html.Div([
                            html.I(className=f"fas {action_style['icon']} me-2 fs-4 text-{action_style['bg']}"),
                            html.Strong(entry.get('action', 'WAIT'), className=f"fs-5 text-{action_style['bg']}")
                        ]),
                        html.Div([
                            html.Small(entry.get('action_reason', ''), className="text-muted d-block mt-1")
                        ], className="mt-2")
                    ], className="p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"})
                ], md=4),
            ], className="mb-3"),

            # Row 2: Entry Confirmation (if applicable)
            html.Div([
                html.Hr(className="my-3"),
                html.H6([
                    html.I(className="fas fa-clipboard-check me-2"),
                    "Konfirmasi Entry"
                ], className="text-info mb-3"),

                dbc.Row([
                    # Confirmation Checklist
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span(
                                    "[v] " if entry.get('signals', {}).get('near_support', {}).get('passed') else "[x] ",
                                    className="text-success fw-bold" if entry.get('signals', {}).get('near_support', {}).get('passed') else "text-danger fw-bold"
                                ),
                                html.Span("Near Support ", className="small"),
                                html.Small(f"({entry.get('pos_in_range', 0):.0f}% dari range)", className="text-muted")
                            ], className="mb-1"),
                            html.Div([
                                html.Span(
                                    "[v] " if entry.get('signals', {}).get('bullish_candle', {}).get('passed') else "[x] ",
                                    className="text-success fw-bold" if entry.get('signals', {}).get('bullish_candle', {}).get('passed') else "text-danger fw-bold"
                                ),
                                html.Span("Bullish Candle", className="small")
                            ], className="mb-1"),
                            html.Div([
                                html.Span(
                                    "[v] " if entry.get('signals', {}).get('range_expansion', {}).get('passed') else "[x] ",
                                    className="text-success fw-bold" if entry.get('signals', {}).get('range_expansion', {}).get('passed') else "text-danger fw-bold"
                                ),
                                html.Span("Range Expansion ", className="small"),
                                html.Small(f"({entry.get('signals', {}).get('range_expansion', {}).get('value', 0):.2f}x)", className="text-muted")
                            ], className="mb-1"),
                            html.Div([
                                html.Span(
                                    "[v] " if entry.get('signals', {}).get('volume_surge', {}).get('passed') else "[x] ",
                                    className="text-success fw-bold" if entry.get('signals', {}).get('volume_surge', {}).get('passed') else "text-danger fw-bold"
                                ),
                                html.Span("Volume Surge ", className="small"),
                                html.Small(f"({entry.get('signals', {}).get('volume_surge', {}).get('value', 0):.2f}x)", className="text-muted")
                            ], className="mb-1"),
                            html.Div([
                                html.Strong(f"Score: {entry.get('score', 0)}/4", className="text-info")
                            ], className="mt-2")
                        ])
                    ], md=6),

                    # Risk Management
                    dbc.Col([
                        html.Div([
                            html.H6("Risk Management", className="text-warning mb-2"),
                            html.Div([
                                html.Span("Entry: ", className="text-muted"),
                                html.Strong(f"Rp {current_price:,.0f}", className="text-light")
                            ], className="mb-1"),
                            html.Div([
                                html.Span("Stop Loss: ", className="text-muted"),
                                html.Strong(f"Rp {entry.get('stop_loss', 0):,.0f}", className="text-danger"),
                                html.Small(f" (-{entry.get('risk_pct', 0):.1f}%)", className="text-danger")
                            ], className="mb-1"),
                            html.Div([
                                html.Span("Target: ", className="text-muted"),
                                html.Strong(f"Rp {entry.get('target', 0):,.0f}", className="text-success"),
                                html.Small(f" (+{entry.get('reward_pct', 0):.1f}%)", className="text-success")
                            ], className="mb-1"),
                            html.Div([
                                html.Span("R:R Ratio: ", className="text-muted"),
                                html.Strong(
                                    f"1:{entry.get('rr_ratio', 0):.1f}",
                                    className="text-success" if entry.get('rr_ratio', 0) >= 1.5 else "text-warning"
                                )
                            ], className="mt-2")
                        ], className="p-3 rounded", style={"backgroundColor": "rgba(255,193,7,0.1)"})
                    ], md=6),
                ])
            ]) if sideways.get('is_sideways') else html.Div(),

            # Row 3: Education - Why Not Buy
            html.Div([
                html.Hr(className="my-3"),
                html.H6([
                    html.I(className="fas fa-graduation-cap me-2 text-info"),
                    "Kenapa Belum Buy?"
                ], className="text-danger mb-2"),
                html.Div([
                    html.Div([
                        html.Span(f"{i}. ", className="text-danger fw-bold"),
                        html.Span(reason, className="small")
                    ], className="mb-1") for i, reason in enumerate(education.get('why_not_buy', []), 1)
                ])
            ]) if education.get('why_not_buy') else html.Div(),

            # Row 4: Phase Explanation
            html.Div([
                html.Hr(className="my-3"),
                html.H6([
                    html.I(className="fas fa-info-circle me-2"),
                    f"Penjelasan Fase {phase_style['label']}"
                ], className=f"text-{phase_style['bg']} mb-2"),
                html.P(education.get('phase_explanation', ''), className="small mb-0")
            ]) if education.get('phase_explanation') else html.Div(),

            # Row 5: Action Explanation
            html.Div([
                html.Hr(className="my-3"),
                html.Div([
                    html.I(className=f"fas {action_style['icon']} me-2 text-{action_style['bg']}"),
                    html.Strong(education.get('action_explanation', ''), className="small")
                ])
            ]) if education.get('action_explanation') else html.Div(),

            # Footer: Formula Info
            html.Div([
                html.Hr(className="my-3"),
                html.Details([
                    html.Summary([
                        html.I(className="fas fa-calculator me-2"),
                        html.Span("Lihat Formula V6", className="small text-info")
                    ], className="mb-2", style={"cursor": "pointer"}),
                    html.Pre(
                        education.get('formula_explanation', ''),
                        className="small text-muted",
                        style={"fontSize": "11px", "backgroundColor": "rgba(0,0,0,0.3)", "padding": "10px", "borderRadius": "5px", "whiteSpace": "pre-wrap"}
                    )
                ])
            ])
        ])
    ], className="mb-4", style={"background": "linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%)", "border": "1px solid #17a2b8"})


def create_signal_education_card(stock_code: str, validation_data: dict = None, broker_data: dict = None):
    """
    Create educational card explaining WHY the signal is what it is.
    Dinamis berdasarkan kondisi aktual - bukan template.
    """
    try:
        if validation_data is None:
            validation_data = get_comprehensive_validation(stock_code, 30)

        education = generate_signal_education_data(validation_data, broker_data)
        summary = validation_data.get('summary', {})
        decision_rule = validation_data.get('decision_rule', {})

        signal = summary.get('overall_signal', 'NETRAL')
        decision = decision_rule.get('decision', 'WAIT')
        cpr_data = validation_data.get('validations', {}).get('cpr', {})
        cpr_pct = int(cpr_data.get('avg_cpr', 0.5) * 100)

    except Exception as e:
        return dbc.Card([
            dbc.CardBody(html.P(f"Error loading education: {str(e)}", className="text-danger"))
        ], className="mb-4")

    # Signal color
    signal_colors = {'AKUMULASI': 'success', 'DISTRIBUSI': 'danger', 'NETRAL': 'warning'}
    signal_color = signal_colors.get(signal, 'secondary')

    # Build content sections
    sections = []

    # A. Main explanation box
    sections.append(
        html.Div([
            html.H6([
                html.I(className="fas fa-question-circle me-2"),
                f"Kenapa Status {signal}?"
            ], className=f"text-{signal_color} mb-2"),
            html.P(education['signal_explanation'], className="mb-0 small",
                   style={"backgroundColor": "rgba(255,255,255,0.05)", "padding": "10px", "borderRadius": "5px"})
        ], className="mb-3")
    )

    # B. Absorption explanation (if WAIT with positive net buy)
    if decision == 'WAIT' and cpr_pct < 40:
        sections.append(
            dbc.Alert([
                html.H6([
                    html.I(className="fas fa-info-circle me-2"),
                    "Kenapa WAIT padahal ada Net Buy?"
                ], className="text-warning mb-2"),
                html.P([
                    f"Meskipun ada pembelian, harga masih ditutup di area bawah (CPR {cpr_pct}%). ",
                    "Ini menandakan ", html.Strong("ABSORPTION"), " - supply masih aktif menyerap buying pressure. ",
                    "Sistem menunggu konfirmasi buyer berhasil mengangkat harga."
                ], className="mb-0 small")
            ], color="warning", className="mb-3", style={"backgroundColor": "rgba(255,193,7,0.1)"})
        )

    # C. Why not buy (if any)
    if education['why_not_buy']:
        sections.append(
            html.Div([
                html.H6([
                    html.I(className="fas fa-times-circle me-2 text-danger"),
                    "Kenapa Belum Buy?"
                ], className="text-danger mb-2"),
                html.Div([
                    html.Div([
                        html.Span(f"{i}. ", className="text-danger fw-bold"),
                        html.Span(reason, className="small")
                    ], className="mb-1") for i, reason in enumerate(education['why_not_buy'], 1)
                ])
            ], className="mb-3")
        )

    # D. Wait for confirmation (if any)
    if education['wait_for_confirmation']:
        sections.append(
            html.Div([
                html.H6([
                    html.I(className="fas fa-clock me-2 text-info"),
                    "Tunggu Konfirmasi Apa?"
                ], className="text-info mb-2"),
                html.Div([
                    html.Div([
                        html.Span("^ ", className="text-success fw-bold"),
                        html.Span(conf, className="small")
                    ], className="mb-1") for conf in education['wait_for_confirmation']
                ])
            ], className="mb-3")
        )

    # E. Positive factors (if any)
    if education['positive_factors']:
        sections.append(
            html.Div([
                html.H6([
                    html.I(className="fas fa-check-circle me-2 text-success"),
                    "Faktor Positif"
                ], className="text-success mb-2"),
                html.Div([
                    html.Div([
                        html.Span("+ ", className="text-success fw-bold"),
                        html.Span(factor, className="small text-success")
                    ], className="mb-1") for factor in education['positive_factors']
                ])
            ], className="mb-3")
        )

    # F. Warning factors (if any)
    if education['warning_factors']:
        sections.append(
            html.Div([
                html.H6([
                    html.I(className="fas fa-exclamation-triangle me-2 text-warning"),
                    "Peringatan"
                ], className="text-warning mb-2"),
                html.Div([
                    html.Div([
                        html.Span("! ", className="text-warning fw-bold"),
                        html.Span(warn, className="small text-warning")
                    ], className="mb-1") for warn in education['warning_factors']
                ])
            ], className="mb-3")
        )

    # G. Important note
    sections.append(
        html.Div([
            html.Hr(className="my-2"),
            html.Small([
                html.I(className="fas fa-shield-alt me-1 text-info"),
                "Sistem ini dirancang untuk ",
                html.Strong("MELINDUNGI", className="text-info"),
                " investor dari entry prematur. Signal WAIT bukan berarti saham jelek - tapi timing belum tepat."
            ], className="text-muted fst-italic")
        ])
    )

    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.I(className="fas fa-graduation-cap me-2 text-info"),
                html.Strong("Edukasi: Memahami Sinyal", className="text-info"),
            ], className="d-flex align-items-center")
        ], style={"background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)", "borderBottom": "2px solid #17a2b8"}),
        dbc.CardBody(sections)
    ], className="mb-4", style={"background": "linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%)", "border": "1px solid #17a2b8"})


# ============================================================
# HELPER: BUY SIGNAL TRACKER CARD
# ============================================================

def create_buy_signal_card(buy_signal, stock_code: str = None):
    """
    Create Signal Tracker card - Anti FOMO feature
    Menunjukkan kapan sinyal BUY/SELL dimulai dan status saat ini
    Support Dynamic Threshold dengan Market Cap Category

    Args:
        buy_signal: Signal data dictionary
        stock_code: Stock code for broker chart (optional)
    """
    # Get dynamic threshold info
    dynamic_threshold = buy_signal.get('dynamic_threshold', {})
    cap_category = dynamic_threshold.get('cap_category', 'N/A')
    if cap_category == 'N/A':
        # Fallback for old format
        cap_category = 'BIG_CAP' if dynamic_threshold.get('is_big_cap') else 'SMALL_CAP'
    confidence = dynamic_threshold.get('confidence', 'N/A')

    # Color mapping for cap category
    # BIG_CAP uses 'dark' for white text, MID_CAP uses 'info', SMALL_CAP uses 'warning'
    cap_colors = {'BIG_CAP': 'dark', 'MID_CAP': 'info', 'SMALL_CAP': 'warning'}
    cap_color = cap_colors.get(cap_category, 'secondary')

    # Color mapping for confidence
    conf_colors = {'HIGH': 'success', 'MEDIUM': 'info', 'LOW': 'warning', 'NO_DATA': 'secondary', 'NO_PATTERN': 'secondary'}
    conf_color = conf_colors.get(confidence, 'secondary')

    # Get signal type
    signal_type = buy_signal.get('signal_type')  # BUY, SELL, BUY_PENDING, SELL_PENDING, or None

    # Dynamic threshold info for display
    accum_threshold = dynamic_threshold.get('accumulation', {})
    distrib_threshold = dynamic_threshold.get('distribution', {})
    breakout_pct = accum_threshold.get('breakout_pct', 0) * 100
    breakdown_pct = abs(distrib_threshold.get('breakdown_pct', 0)) * 100

    if not buy_signal.get('has_signal'):
        # No active signal - show waiting state with same format as active signal
        zone = buy_signal.get('zone', 'NO SIGNAL')
        zone_color = buy_signal.get('zone_color', 'secondary')

        # Get phase tracking data
        phase_tracking = buy_signal.get('phase_tracking', {})
        market_phase = phase_tracking.get('market_phase', 'N/A')
        foreign_flow = phase_tracking.get('foreign_flow_10d', 0)

        # Get current price from interpretation or default
        current_price = buy_signal.get('current_price', 0)

        return dbc.Card([
            dbc.CardHeader([
                html.H5([
                    "Signal Tracker ",
                    dbc.Badge(zone, color=zone_color, className="ms-2"),
                ], className="mb-0 d-inline"),
                html.Small(" - Fitur Anti-FOMO", className="text-muted ms-2")
            ], className="bg-dark"),
            dbc.CardBody([
                dbc.Row([
                    # LEFT COLUMN - Current Status
                    dbc.Col([
                        html.P([
                            html.Strong("Status: "),
                            html.Span("Menunggu Sinyal", className="text-warning")
                        ], className="mb-2"),
                        html.P([
                            html.Strong("Harga Sekarang: "),
                            html.Span(f"Rp {current_price:,.0f}" if current_price else "N/A", className="text-info")
                        ], className="mb-2"),
                        html.P([
                            html.Strong("Fase Saat Ini: "),
                            dbc.Badge(
                                market_phase,
                                color={
                                    'RALLY': 'success', 'DECLINE': 'danger', 'ACCUMULATION': 'info',
                                    'DISTRIBUTION': 'warning', 'SIDEWAYS': 'secondary', 'TRANSITION': 'secondary'
                                }.get(market_phase, 'secondary'),
                                className="ms-1"
                            ),
                            html.Span(f" ({foreign_flow:+.1f}B)" if foreign_flow else "", className="text-muted small")
                        ], className="mb-0"),
                    ], md=4),

                    # MIDDLE COLUMN - Threshold Info
                    dbc.Col([
                        html.H6("Dynamic Threshold", className="text-info mb-3"),
                        html.P([
                            html.Strong("Breakout Target: "),
                            f"+{breakout_pct:.1f}%"
                        ], className="mb-2"),
                        html.P([
                            html.Strong("Breakdown Target: "),
                            f"-{breakdown_pct:.1f}%"
                        ], className="mb-2"),
                        html.P([
                            html.Strong("Min Sideways: "),
                            f"{accum_threshold.get('min_sideways_days', 'N/A')} hari"
                        ], className="mb-2"),
                        html.P([
                            html.Strong("Confidence: "),
                            dbc.Badge(confidence, color=conf_color)
                        ], className="mb-0"),
                    ], md=4),

                    # RIGHT COLUMN - Action
                    dbc.Col([
                        html.Div([
                            dbc.Button(
                                "WAIT",
                                color="secondary",
                                size="lg",
                                className="w-100 mb-2 fw-bold",
                                style={"fontSize": "1.2rem"}
                            ),
                            html.P(
                                buy_signal.get('message', 'Tunggu sinyal akumulasi/distribusi'),
                                className="small text-muted text-center mb-0"
                            ),
                        ], className="text-center")
                    ], md=4),
                ]),
                html.Hr(className="my-3"),
                # Interpretasi
                html.P([
                    html.Strong("Interpretasi: "),
                    html.Span(buy_signal.get('interpretation', {}).get('threshold_info', 'N/A'), className="text-info")
                ], className="mb-2"),
                # Grafik Broker Sensitif
                html.Div([
                    html.Hr(className="my-3"),
                    html.Strong("Grafik Pergerakan Broker Sensitif (30 Hari):", className="d-block mb-2"),
                    create_sensitive_broker_daily_chart(stock_code) if stock_code else html.Div("Stock code not available", className="text-muted")
                ]) if stock_code else None,
            ])
        ], className="mb-4", color="dark")

    zone_color = buy_signal.get('zone_color', 'secondary')

    # Determine signal label based on type
    is_sell_signal = signal_type == 'SELL'
    signal_label = "SELL" if is_sell_signal else "BUY"
    signal_label_color = "danger" if is_sell_signal else "success"

    # Get phase tracking data
    phase_tracking = buy_signal.get('phase_tracking', {})
    foreign_flow = phase_tracking.get('foreign_flow_10d', 0)
    phase_status = phase_tracking.get('status', 'UNKNOWN')

    # Trigger sinyal as inline text
    trigger_reasons = buy_signal.get('signal_reasons', [])
    trigger_text = ", ".join(trigger_reasons) if trigger_reasons else "N/A"

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                f"Buy Signal Tracker " if not is_sell_signal else "Sell Signal Tracker ",
                dbc.Badge(buy_signal['zone'], color=zone_color, className="ms-2"),
            ], className="mb-0 d-inline"),
            html.Small(" - Fitur Anti-FOMO", className="text-muted ms-2")
        ], className="bg-dark"),
        dbc.CardBody([
            dbc.Row([
                # LEFT COLUMN - Signal Info
                dbc.Col([
                    html.P([
                        html.Strong(f"Sinyal {signal_label} Dimulai: "),
                        html.Span(
                            buy_signal['signal_date'].strftime('%d %b %Y') if buy_signal.get('signal_date') else 'N/A',
                            className=f"text-{signal_label_color}"
                        )
                    ], className="mb-2"),
                    html.P([
                        html.Strong("Harga Saat Sinyal: "),
                        html.Span(
                            f"Rp {buy_signal['signal_price']:,.0f}",
                            className=f"text-{signal_label_color}"
                        )
                    ], className="mb-2"),
                    html.P([
                        html.Strong("Harga Sekarang: "),
                        html.Span(
                            f"Rp {buy_signal['current_price']:,.0f} ",
                            className=f"text-{zone_color}"
                        ),
                        html.Span(
                            f"({buy_signal['price_change_pct']:+.1f}%)",
                            className=f"text-{'success' if buy_signal['price_change_pct'] >= 0 else 'danger'}"
                        )
                    ], className="mb-2"),
                    html.P([
                        html.Strong("Harga Tertinggi: " if not is_sell_signal else "Harga Terendah: "),
                        html.Span(
                            f"Rp {phase_tracking.get('highest_price', buy_signal['current_price']):,.0f} ",
                            className="text-warning"
                        ),
                        html.Span(
                            f"({phase_tracking.get('max_gain_pct', 0):+.1f}%)",
                            className="text-warning"
                        )
                    ], className="mb-0") if phase_tracking else None,
                ], md=4),

                # MIDDLE COLUMN - Safe Entry Zone
                dbc.Col([
                    html.H6("Safe Entry Zone" if not is_sell_signal else "Target Zone", className=f"text-{'info' if not is_sell_signal else 'danger'} mb-3"),
                    html.P([
                        html.Strong("Harga Ideal: "),
                        f"< Rp {buy_signal['safe_entry']['ideal_price']:,.0f}" if not is_sell_signal else f"Rp {buy_signal.get('signal_price', 0) * 0.95:,.0f}"
                    ], className="mb-2"),
                    html.P([
                        html.Strong("Harga Maksimal: "),
                        f"< Rp {buy_signal['safe_entry']['max_price']:,.0f}" if not is_sell_signal else f"Rp {buy_signal.get('signal_price', 0) * 1.03:,.0f}"
                    ], className="mb-2"),
                    html.P([
                        html.Strong("Status: "),
                        html.Span(
                            "AMAN" if buy_signal['safe_entry']['is_safe'] else "MAHAL",
                            className=f"text-{'success' if buy_signal['safe_entry']['is_safe'] else 'danger'} fw-bold"
                        ) if not is_sell_signal else html.Span("DISTRIBUSI", className="text-danger fw-bold")
                    ], className="mb-2"),
                    html.P([
                        html.Strong("Fase: "),
                        dbc.Badge(
                            phase_status,
                            color={
                                'ACCUMULATION': 'info', 'ACCUMULATING': 'info',
                                'MARKUP': 'success', 'RALLY': 'success',
                                'DISTRIBUTION': 'danger', 'DECLINE': 'danger',
                                'SIDEWAYS': 'warning', 'ENDED': 'secondary',
                            }.get(phase_status, 'secondary'),
                            className="me-1"
                        ),
                        html.Span(
                            f"({foreign_flow:+.1f}B)" if foreign_flow else "",
                            className="text-muted small"
                        )
                    ], className="mb-0"),
                ], md=4),

                # RIGHT COLUMN - Recommendation
                dbc.Col([
                    html.Div([
                        dbc.Button(
                            buy_signal['recommendation'],
                            color=zone_color,
                            size="lg",
                            className="w-100 mb-2 fw-bold",
                            style={"fontSize": "1.2rem"}
                        ),
                        html.P(
                            buy_signal['zone_desc'],
                            className="small text-muted text-center mb-0"
                        ),
                    ], className="text-center")
                ], md=4),
            ]),
            html.Hr(className="my-3"),
            # Trigger Sinyal - inline text format
            html.P([
                html.Strong("Trigger Sinyal: "),
                html.Span(trigger_text, className="text-muted")
            ], className="mb-2"),
            # Penjelasan Zone - expanded
            html.Div([
                html.Strong("Penjelasan Zone:", className="d-block mb-2"),
                html.Small([
                    "* BETTER ENTRY: Harga turun <5% dari sinyal ^ kesempatan entry lebih baik", html.Br(),
                    "* DISCOUNTED: Harga turun 5-10% ^ hati-hati, sinyal mungkin melemah", html.Br(),
                    "* SIGNAL FAILED: Harga turun >10% ^ review ulang, sinyal mungkin gagal", html.Br(),
                    "* SAFE/MODERATE: Harga naik <7% dari sinyal ^ masih aman", html.Br(),
                    "* CAUTION/FOMO: Harga naik >7% dari sinyal ^ risiko tinggi, tunggu pullback", html.Br(),
                    "* PHASE ENDED: Harga pernah naik >10% lalu turun ke <5% ^ fase akumulasi selesai, tunggu sinyal baru",
                ], className="text-muted")
            ]),
            # Sensitive Broker Daily Chart
            html.Div([
                html.Hr(className="my-3"),
                html.Strong("Grafik Pergerakan Broker Sensitif (30 Hari):", className="d-block mb-2"),
                create_sensitive_broker_daily_chart(stock_code) if stock_code else html.Div("Stock code not available", className="text-muted")
            ]) if stock_code else None,
        ])
    ], className="mb-4", color="dark")


# ============================================================
# HELPER: MULTI-PERIOD SUMMARY CARD
# ============================================================

def create_multi_period_card(stock_code):
    """
    Create multi-period summary card showing:
    - Price movements (1D, 1W, 2W, 3W, 1M)
    - Foreign flow by period
    - Sensitive broker flow by period
    """
    try:
        summary = get_multi_period_summary(stock_code)
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader(html.H5("Pergerakan Multi-Periode", className="mb-0")),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-4", color="dark")

    price_data = summary.get('price', {})
    foreign_data = summary.get('foreign', {})
    sensitive_data = summary.get('sensitive', {})
    periods = summary.get('periods', ['1D', '1W', '2W', '3W', '1M'])
    period_labels = summary.get('period_labels', {})

    # Helper function for color coding
    def get_value_color(value, is_percentage=False):
        if value is None:
            return 'text-muted'
        if value > 0:
            return 'text-success'
        elif value < 0:
            return 'text-danger'
        return 'text-muted'

    def format_value(value, prefix='', suffix='', decimals=1):
        if value is None:
            return '-'
        if abs(value) >= 1e9:
            return f"{prefix}{value/1e9:+.{decimals}f}B{suffix}"
        elif abs(value) >= 1e6:
            return f"{prefix}{value/1e6:+.{decimals}f}M{suffix}"
        else:
            return f"{prefix}{value:+.{decimals}f}{suffix}"

    # Create period columns
    period_cols = []
    for period in periods:
        label = period_labels.get(period, period)

        # Price movement
        price_period = price_data.get('periods', {}).get(period, {})
        price_pct = price_period.get('change_pct')
        price_color = get_value_color(price_pct)

        # Foreign flow
        foreign_period = foreign_data.get('periods', {}).get(period, {})
        foreign_net = foreign_period.get('net_flow', 0)
        foreign_color = get_value_color(foreign_net)

        # Sensitive broker flow
        sens_period = sensitive_data.get('periods', {}).get(period, {})
        sens_net = sens_period.get('net_flow', 0)
        sens_color = get_value_color(sens_net)

        period_cols.append(
            dbc.Col([
                html.Div([
                    html.H6(label, className="text-center text-muted mb-2"),

                    # Price
                    html.Div([
                        html.Small("Harga", className="text-muted d-block text-center"),
                        html.Span(
                            f"{price_pct:+.1f}%" if price_pct is not None else "-",
                            className=f"{price_color} fw-bold d-block text-center"
                        )
                    ], className="mb-2"),

                    # Foreign
                    html.Div([
                        html.Small([
                            html.I(className="fas fa-globe me-1", style={"color": BROKER_COLORS['FOREIGN']}),
                            "Foreign"
                        ], className="text-muted d-block text-center"),
                        html.Span(
                            format_value(foreign_net),
                            className=f"{foreign_color} d-block text-center",
                            style={"fontSize": "12px"}
                        )
                    ], className="mb-2"),

                    # Sensitive
                    html.Div([
                        html.Small([
                            html.I(className="fas fa-star me-1", style={"color": "#ffc107"}),
                            "Sensitif"
                        ], className="text-muted d-block text-center"),
                        html.Span(
                            format_value(sens_net),
                            className=f"{sens_color} d-block text-center",
                            style={"fontSize": "12px"}
                        )
                    ])
                ], className="border rounded p-2 metric-box")
            ], width=True)
        )

    # Broker type legend
    legend = html.Div([
        html.Small("Legenda: ", className="text-muted me-2"),
        html.Span([
            html.I(className="fas fa-circle me-1", style={"color": BROKER_COLORS['FOREIGN'], "fontSize": "8px"}),
            "Asing "
        ], className="me-3", style={"fontSize": "11px"}),
        html.Span([
            html.I(className="fas fa-circle me-1", style={"color": BROKER_COLORS['BUMN'], "fontSize": "8px"}),
            "BUMN "
        ], className="me-3", style={"fontSize": "11px"}),
        html.Span([
            html.I(className="fas fa-circle me-1", style={"color": BROKER_COLORS['LOCAL'], "fontSize": "8px"}),
            "Lokal "
        ], style={"fontSize": "11px"}),
    ], className="mt-2")

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                "Pergerakan Multi-Periode ",
                html.I(className="fas fa-info-circle text-muted", id="multi-period-info",
                      style={"fontSize": "14px", "cursor": "pointer"})
            ], className="mb-0 d-inline"),
            dbc.Tooltip(
                "Perbandingan pergerakan harga, foreign flow, dan broker sensitif dalam berbagai periode waktu",
                target="multi-period-info"
            )
        ]),
        dbc.CardBody([
            # Current price header
            html.Div([
                html.Span("Harga Sekarang: ", className="text-muted"),
                html.Span(
                    f"Rp {price_data.get('current_price', 0):,.0f}",
                    className="text-info fw-bold"
                )
            ], className="mb-3 text-center"),

            # Period comparison row
            dbc.Row(period_cols, className="g-2"),

            html.Hr(),

            # Legend
            legend,

            # Interpretation
            html.Small([
                html.Strong("Cara Baca: "),
                "Bandingkan arah harga dengan arah flow. ",
                "Jika harga naik + Foreign/Sensitif akumulasi = sinyal kuat. ",
                "Jika harga naik tapi broker distribusi = waspada reversal."
            ], className="text-muted d-block mt-2")
        ])
    ], className="mb-4")


# ============================================================
# HELPER: AVG BUY ANALYSIS CARD
# ============================================================

def create_avg_buy_card(avg_buy_analysis, stock_code, sr_analysis=None):
    """
    Create Avg Buy Analysis card
    Menunjukkan rata-rata harga beli broker dan support/resistance level
    Support/Resistance sekarang menggunakan multi-method analysis dari sr_analysis
    """
    if 'error' in avg_buy_analysis:
        return dbc.Card([
            dbc.CardHeader(html.H5("Analisis Avg Buy Broker", className="mb-0")),
            dbc.CardBody([
                html.P("Data tidak tersedia", className="text-muted")
            ])
        ], className="mb-4", color="dark")

    summary = avg_buy_analysis.get('summary', {})
    current_price = avg_buy_analysis.get('current_price', 0)
    resistance_levels = avg_buy_analysis.get('resistance_levels', [])  # Above current price
    interest_zone_value = avg_buy_analysis.get('interest_zone', None)

    # Check if stock has V10 zones
    v10_zones = get_zones(stock_code)

    # Get Support Zone (from V10 zones if available)
    if v10_zones:
        # Find nearest support zone below current price
        support_zone = None
        for zone_num, zone_data in sorted(v10_zones.items(), reverse=True):
            if zone_data['high'] < current_price:
                support_zone = zone_data
                support_zone['num'] = zone_num
                break

        if support_zone:
            support_display = f"Rp {support_zone['low']:,.0f} - {support_zone['high']:,.0f}"
            support_class = "text-success"
            support_pct = (current_price - support_zone['high']) / current_price * 100
            support_note = f"Z{support_zone['num']} (-{abs(support_pct):.1f}%)"
        else:
            support_display = "-"
            support_class = "text-muted"
            support_note = "(di bawah semua zona)"
    elif sr_analysis and 'key_support' in sr_analysis:
        # Fallback to dynamic S/R
        support_price = sr_analysis['key_support']
        support_low = support_price * 0.98  # Create zone ±2%
        support_high = support_price * 1.02
        support_display = f"Rp {support_low:,.0f} - {support_high:,.0f}"
        support_class = "text-success"
        support_pct = sr_analysis.get('interpretation', {}).get('support_distance_pct', 0)
        support_note = f"(-{abs(support_pct):.1f}%)"
    else:
        estimated_support = current_price * 0.95
        support_display = f"~Rp {estimated_support:,.0f}"
        support_class = "text-warning"
        support_note = "(estimasi -5%)"

    # Get Interest/Resistance Zone (from V10 zones if available)
    if v10_zones:
        # Find nearest resistance zone above current price
        interest_zone = None
        for zone_num, zone_data in sorted(v10_zones.items()):
            if zone_data['low'] > current_price:
                interest_zone = zone_data
                interest_zone['num'] = zone_num
                break

        if interest_zone:
            interest_display = f"Rp {interest_zone['low']:,.0f} - {interest_zone['high']:,.0f}"
            interest_pct = (interest_zone['low'] - current_price) / current_price * 100
            interest_note = f"Z{interest_zone['num']} (+{interest_pct:.1f}%)"
        else:
            interest_display = "-"
            interest_note = "(di atas semua zona)"
    elif interest_zone_value and interest_zone_value > current_price:
        # Fallback to broker-based interest zone
        interest_low = interest_zone_value * 0.98
        interest_high = interest_zone_value * 1.02
        interest_display = f"Rp {interest_low:,.0f} - {interest_high:,.0f}"
        interest_note = f"({len(resistance_levels)} broker loss)"
    else:
        interest_display = "-"
        interest_note = ""

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                "Analisis Avg Buy Broker ",
                html.Small("(60 hari terakhir)", className="text-muted")
            ], className="mb-0 d-inline"),
        ]),
        dbc.CardBody([
            # Summary Row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H6("Harga Sekarang", className="text-muted small"),
                        html.H4(f"Rp {current_price:,.0f}", className="text-info mb-0")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H6("Broker Profit", className="text-muted small"),
                        html.H4([
                            html.Span(f"{summary.get('profit_brokers', 0)}", className="text-success"),
                            html.Small(f" ({summary.get('profit_value_pct', 0):.0f}%)", className="text-muted")
                        ], className="mb-0")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H6("Broker Loss", className="text-muted small"),
                        html.H4([
                            html.Span(f"{summary.get('loss_brokers', 0)}", className="text-danger"),
                            html.Small(f" ({summary.get('loss_value_pct', 0):.0f}%)", className="text-muted")
                        ], className="mb-0")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H6([
                            "Support Zone ",
                            html.I(className="fas fa-arrow-down", style={"fontSize": "10px"})
                        ], className="text-muted small"),
                        html.H4(support_display, className=f"{support_class} mb-0", style={"fontSize": "1.1rem"}),
                        html.Small(support_note, className="text-muted", style={"fontSize": "10px"})
                    ], className="text-center")
                ], width=3),
            ], className="mb-2"),

            # Second row: Interest/Resistance Zone (if exists)
            dbc.Row([
                dbc.Col(width=9),
                dbc.Col([
                    html.Div([
                        html.H6([
                            "Resistance Zone ",
                            html.I(className="fas fa-arrow-up", style={"fontSize": "10px"})
                        ], className="text-muted small"),
                        html.H4(interest_display, className="text-danger mb-0", style={"fontSize": "1.1rem"}),
                        html.Small(interest_note, className="text-muted", style={"fontSize": "10px"}) if interest_note else None
                    ], className="text-center")
                ], width=3),
            ], className="mb-3") if interest_display != "-" else None,

            html.Hr(),

            # Interpretation
            html.Small([
                html.Strong("Cara Baca: "),
                html.Br(),
                html.Span("* Support Zone", className="text-success"), " = Area di bawah harga dimana harga cenderung mantul naik",
                html.Br(),
                html.Span("* Resistance Zone", className="text-danger"), " = Area di atas harga yang menjadi penghalang kenaikan",
                html.Br(),
                html.Strong("Tips: "), "Zona ini berdasarkan Formula V11b1 (jika tersedia) atau analisis dinamis."
            ], className="text-muted")
        ])
    ], className="mb-4", color="dark", outline=True)


def create_sr_chart(stock_code: str, sr_analysis: dict, days: int = 60):
    """
    Create candlestick chart with S/R lines and volume bars.

    Features:
    - Candlestick price chart
    - Support lines (green, dashed)
    - Resistance lines (red, dashed)
    - Volume bars (colored by price direction)
    - Current price line
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    price_df = get_price_data(stock_code)

    if price_df.empty:
        return html.Div("No price data available", className="text-muted p-4")

    # Get last N days
    df = price_df.sort_values('date').tail(days).copy()

    # Convert to float
    for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    # Get S/R levels
    supports = sr_analysis.get('supports', [])
    resistances = sr_analysis.get('resistances', [])
    key_support = sr_analysis.get('key_support', 0)
    key_resistance = sr_analysis.get('key_resistance', 0)
    current_price = sr_analysis.get('current_price', 0)

    # Create figure with secondary y-axis for volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('', '')
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df['date'],
            open=df['open_price'],
            high=df['high_price'],
            low=df['low_price'],
            close=df['close_price'],
            name='Price',
            increasing_line_color='#00C853',
            decreasing_line_color='#FF1744',
            increasing_fillcolor='#00C853',
            decreasing_fillcolor='#FF1744'
        ),
        row=1, col=1
    )

    # Volume bars with color based on price direction
    colors = ['#00C853' if close >= open_p else '#FF1744'
              for close, open_p in zip(df['close_price'], df['open_price'])]

    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.7
        ),
        row=2, col=1
    )

    # Add average volume line
    avg_volume = df['volume'].mean()
    fig.add_hline(
        y=avg_volume,
        line_dash="dot",
        line_color="yellow",
        line_width=1,
        annotation_text=f"Avg Vol: {avg_volume/1e6:.1f}M",
        annotation_position="right",
        row=2, col=1
    )

    # Check if stock has V10 zones - if yes, skip dynamic S/R lines
    fixed_zones = get_zones(stock_code)

    # Only show dynamic S/R lines if NO V10 zones configured
    if not fixed_zones:
        # Add Support lines (green) - only for stocks without V10 zones
        support_colors = ['#00E676', '#00C853', '#00A844', '#008B35', '#006D27']
        for i, sup in enumerate(supports[:5]):
            level = sup['level']
            color = support_colors[min(i, len(support_colors)-1)]
            confirmations = sup.get('confirmations', 1)
            line_width = 1 + confirmations

            fig.add_hline(
                y=level,
                line_dash="dash",
                line_color=color,
                line_width=line_width,
                annotation_text=f"S: {level:,.0f}",
                annotation_position="left",
                annotation_font_color=color,
                annotation_font_size=10,
                row=1, col=1
            )

        # Add Resistance lines (red) - only for stocks without V10 zones
        resistance_colors = ['#FF5252', '#FF1744', '#D50000', '#B71C1C', '#8B0000']
        for i, res in enumerate(resistances[:5]):
            level = res['level']
            color = resistance_colors[min(i, len(resistance_colors)-1)]
            confirmations = res.get('confirmations', 1)
            line_width = 1 + confirmations

            fig.add_hline(
                y=level,
                line_dash="dash",
                line_color=color,
                line_width=line_width,
                annotation_text=f"R: {level:,.0f}",
                annotation_position="right",
                annotation_font_color=color,
                annotation_font_size=10,
                row=1, col=1
            )

    # Add current price line (blue)
    fig.add_hline(
        y=current_price,
        line_dash="solid",
        line_color="#2196F3",
        line_width=2,
        annotation_text=f"Current: {current_price:,.0f}",
        annotation_position="right",
        annotation_font_color="#2196F3",
        row=1, col=1
    )

    # Add Fixed V10 Zones as horizontal bands (use variable already defined above)
    if fixed_zones:
        zone_colors = ['rgba(255,193,7,0.2)', 'rgba(255,152,0,0.2)', 'rgba(255,87,34,0.2)',
                      'rgba(233,30,99,0.2)', 'rgba(156,39,176,0.2)']
        for i, (zone_num, zone_data) in enumerate(sorted(fixed_zones.items())):
            zone_low = zone_data['low']
            zone_high = zone_data['high']
            zone_color = zone_colors[min(i, len(zone_colors)-1)]

            # Add shaded area for zone
            fig.add_hrect(
                y0=zone_low,
                y1=zone_high,
                fillcolor=zone_color,
                line=dict(color="rgba(255,193,7,0.6)", width=1),
                annotation_text=f"Z{zone_num}",
                annotation_position="top left",
                annotation_font_color="#ffc107",
                annotation_font_size=10,
                row=1, col=1
            )

    # Update layout
    fig.update_layout(
        title=dict(
            text=f'{stock_code} - Support & Resistance Chart ({days} days)',
            font=dict(size=16, color='white')
        ),
        template='plotly_dark',
        height=500,
        margin=dict(l=60, r=60, t=50, b=30),
        showlegend=False,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )

    # Update y-axes
    fig.update_yaxes(title_text="Price (Rp)", row=1, col=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(title_text="Volume", row=2, col=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_xaxes(gridcolor='rgba(128,128,128,0.2)')

    return dcc.Graph(figure=fig, config={'displayModeBar': True, 'scrollZoom': True})


def create_v8_sr_chart(stock_code: str, v8_data: dict, days: int = 60):
    """
    Create candlestick chart with V8 ATR-Quality Support/Resistance zones.

    V8 Method:
    - ATR(14) for dynamic tolerance
    - Pivot detection (fractal 3L/3R)
    - Clustering levels into buckets
    - Filter: Touches >= 3, Quality >= 0.5
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if not v8_data or 'error' in v8_data:
        return html.Div([
            dbc.Alert("V8 S/R Analysis tidak tersedia untuk emiten ini", color="warning"),
            html.Small("V8 hanya untuk: PTRO, CBDK, BREN, BRPT, CDIA", className="text-muted")
        ])

    price_df = get_price_data(stock_code)

    if price_df.empty:
        return html.Div("No price data available", className="text-muted p-4")

    # Get last N days
    df = price_df.sort_values('date').tail(days).copy()

    # Convert to float
    for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    # Get V8 data
    current_price = v8_data.get('current_price', 0)
    support_price = v8_data.get('support', 0)
    resistance_price = v8_data.get('resistance', 0)
    stop_loss = v8_data.get('stop_loss', 0)
    target = v8_data.get('target', 0)
    tolerance = v8_data.get('tolerance', 0)
    support_touches = v8_data.get('support_touches', 0)
    support_quality = v8_data.get('support_quality', 0)
    resistance_touches = v8_data.get('resistance_touches', 0)
    resistance_quality = v8_data.get('resistance_quality', 0)
    all_supports = v8_data.get('all_supports', [])
    all_resistances = v8_data.get('all_resistances', [])

    # Create figure with secondary y-axis for volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('', '')
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df['date'],
            open=df['open_price'],
            high=df['high_price'],
            low=df['low_price'],
            close=df['close_price'],
            name='Price',
            increasing_line_color='#00C853',
            decreasing_line_color='#FF1744',
            increasing_fillcolor='#00C853',
            decreasing_fillcolor='#FF1744'
        ),
        row=1, col=1
    )

    # Volume bars
    colors = ['#00C853' if close >= open_p else '#FF1744'
              for close, open_p in zip(df['close_price'], df['open_price'])]

    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.7
        ),
        row=2, col=1
    )

    # Add Support Zone (with tolerance as shaded area)
    if support_price > 0 and tolerance > 0:
        fig.add_hrect(
            y0=support_price - tolerance,
            y1=support_price + tolerance,
            fillcolor="rgba(0,200,83,0.15)",
            line_width=0,
            row=1, col=1
        )
        fig.add_hline(
            y=support_price,
            line_dash="solid",
            line_color="#00C853",
            line_width=2,
            annotation_text=f"Support: {support_price:,.0f} (Q:{support_quality:.0%}, {support_touches}x)",
            annotation_position="left",
            annotation_font_color="#00C853",
            annotation_font_size=11,
            row=1, col=1
        )

    # Add Resistance Zone (with tolerance as shaded area)
    if resistance_price > 0 and tolerance > 0:
        fig.add_hrect(
            y0=resistance_price - tolerance,
            y1=resistance_price + tolerance,
            fillcolor="rgba(255,23,68,0.15)",
            line_width=0,
            row=1, col=1
        )
        fig.add_hline(
            y=resistance_price,
            line_dash="solid",
            line_color="#FF1744",
            line_width=2,
            annotation_text=f"Resistance: {resistance_price:,.0f} (Q:{resistance_quality:.0%}, {resistance_touches}x)",
            annotation_position="right",
            annotation_font_color="#FF1744",
            annotation_font_size=11,
            row=1, col=1
        )

    # Add other support levels (lighter)
    for i, sup in enumerate(all_supports[1:4]):  # Skip first (main support)
        level = sup.get('level', 0)
        touches = sup.get('touches', 0)
        quality = sup.get('quality', 0)
        if level > 0:
            fig.add_hline(
                y=level,
                line_dash="dot",
                line_color="rgba(0,200,83,0.5)",
                line_width=1,
                annotation_text=f"S{i+2}: {level:,.0f} ({touches}x)",
                annotation_position="left",
                annotation_font_color="rgba(0,200,83,0.7)",
                annotation_font_size=9,
                row=1, col=1
            )

    # Add other resistance levels (lighter)
    for i, res in enumerate(all_resistances[1:4]):  # Skip first (main resistance)
        level = res.get('level', 0)
        touches = res.get('touches', 0)
        quality = res.get('quality', 0)
        if level > 0:
            fig.add_hline(
                y=level,
                line_dash="dot",
                line_color="rgba(255,23,68,0.5)",
                line_width=1,
                annotation_text=f"R{i+2}: {level:,.0f} ({touches}x)",
                annotation_position="right",
                annotation_font_color="rgba(255,23,68,0.7)",
                annotation_font_size=9,
                row=1, col=1
            )

    # Add Stop Loss line
    if stop_loss > 0:
        fig.add_hline(
            y=stop_loss,
            line_dash="dash",
            line_color="#FF5722",
            line_width=1,
            annotation_text=f"SL: {stop_loss:,.0f}",
            annotation_position="left",
            annotation_font_color="#FF5722",
            annotation_font_size=10,
            row=1, col=1
        )

    # Add Target line
    if target > 0:
        fig.add_hline(
            y=target,
            line_dash="dash",
            line_color="#4CAF50",
            line_width=1,
            annotation_text=f"TP: {target:,.0f}",
            annotation_position="right",
            annotation_font_color="#4CAF50",
            annotation_font_size=10,
            row=1, col=1
        )

    # Add current price line
    fig.add_hline(
        y=current_price,
        line_dash="solid",
        line_color="#2196F3",
        line_width=2,
        annotation_text=f"Current: {current_price:,.0f}",
        annotation_position="right",
        annotation_font_color="#2196F3",
        annotation_font_size=11,
        row=1, col=1
    )

    # Update layout
    phase = v8_data.get('phase', 'NEUTRAL')
    phase_color = {'STRONG_ACCUMULATION': '#00C853', 'ACCUMULATION': '#4CAF50',
                   'WEAK_ACCUMULATION': '#8BC34A', 'NEUTRAL': '#9E9E9E',
                   'WEAK_DISTRIBUTION': '#FF9800', 'DISTRIBUTION': '#FF5722',
                   'STRONG_DISTRIBUTION': '#F44336'}.get(phase, '#9E9E9E')

    fig.update_layout(
        title=dict(
            text=f'{stock_code} - V8 ATR-Quality S/R ({days} days) | Phase: {phase}',
            font=dict(size=14, color=phase_color)
        ),
        template='plotly_dark',
        height=450,
        margin=dict(l=60, r=100, t=50, b=30),
        showlegend=False,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )

    fig.update_yaxes(title_text="Price (Rp)", row=1, col=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(title_text="Volume", row=2, col=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_xaxes(gridcolor='rgba(128,128,128,0.2)')

    return dcc.Graph(figure=fig, config={'displayModeBar': True, 'scrollZoom': True})


def create_v8_sr_card(stock_code: str, v8_data: dict):
    """
    Create V8 ATR-Quality Support/Resistance information card.
    Shows key V8 metrics: Support, Resistance, Quality, Touches, Phase.
    """
    if not v8_data or 'error' in v8_data:
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-line me-2"),
                html.Strong("V8 ATR-Quality S/R")
            ], className="bg-secondary"),
            dbc.CardBody([
                dbc.Alert([
                    html.I(className="fas fa-info-circle me-2"),
                    "V8 Analysis tidak tersedia untuk emiten ini. ",
                    html.Br(),
                    html.Small("V8 hanya untuk: PTRO, CBDK, BREN, BRPT, CDIA", className="text-muted")
                ], color="warning")
            ])
        ], className="mb-4")

    # Extract V8 data
    current_price = v8_data.get('current_price', 0)
    support = v8_data.get('support', 0)
    resistance = v8_data.get('resistance', 0)
    support_touches = v8_data.get('support_touches', 0)
    support_quality = v8_data.get('support_quality', 0)
    resistance_touches = v8_data.get('resistance_touches', 0)
    resistance_quality = v8_data.get('resistance_quality', 0)
    stop_loss = v8_data.get('stop_loss', 0)
    target = v8_data.get('target', 0)
    phase = v8_data.get('phase', 'NEUTRAL')
    vr = v8_data.get('vr', 0)
    action = v8_data.get('action', 'WAIT')
    action_reason = v8_data.get('action_reason', '')
    dist_from_support = v8_data.get('dist_from_support', 0)
    dist_from_resistance = v8_data.get('dist_from_resistance', 0)
    tolerance = v8_data.get('tolerance', 0)
    atr14 = v8_data.get('atr14', 0)

    # Phase colors
    phase_colors = {
        'STRONG_ACCUMULATION': 'success',
        'ACCUMULATION': 'success',
        'WEAK_ACCUMULATION': 'info',
        'NEUTRAL': 'secondary',
        'WEAK_DISTRIBUTION': 'warning',
        'DISTRIBUTION': 'danger',
        'STRONG_DISTRIBUTION': 'danger'
    }
    phase_color = phase_colors.get(phase, 'secondary')

    # Action colors
    action_colors = {'ENTRY': 'success', 'WAIT': 'warning', 'AVOID': 'danger'}
    action_color = action_colors.get(action, 'secondary')

    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-crosshairs me-2"),
            html.Strong("Status V8 ATR-Quality"),
            dbc.Badge(phase, color=phase_color, className="ms-2"),
            dbc.Badge(action, color=action_color, className="ms-2")
        ], className=f"bg-{phase_color} text-white"),
        dbc.CardBody([
            # Main metrics row
            dbc.Row([
                # Support info
                dbc.Col([
                    html.Div([
                        html.H6("Support V8", className="text-success mb-2"),
                        html.H4(f"Rp {support:,.0f}", className="text-success fw-bold mb-1"),
                        html.Div([
                            dbc.Badge(f"Q: {support_quality:.0%}", color="success", className="me-1"),
                            dbc.Badge(f"{support_touches}x touches", color="dark"),
                        ], className="mb-2"),
                        html.Small([
                            "Jarak: ",
                            html.Span(f"{dist_from_support:.1f}%", className=f"fw-bold text-{'success' if dist_from_support <= 5 else 'warning'}")
                        ], className="d-block text-muted"),
                        html.Small(f"Zone: {support-tolerance:,.0f} - {support+tolerance:,.0f}", className="d-block text-muted")
                    ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(40,167,69,0.1)"})
                ], md=4),

                # Current Price & Phase
                dbc.Col([
                    html.Div([
                        html.H6("Harga & Fase", className="text-info mb-2"),
                        html.H4(f"Rp {current_price:,.0f}", className="text-info fw-bold mb-1"),
                        html.Div([
                            html.Span(
                                "🟢" if 'ACCUMULATION' in phase else "🔴" if 'DISTRIBUTION' in phase else "⚪",
                                style={"fontSize": "24px"}
                            ),
                            html.Strong(phase, className=f"ms-2 text-{phase_color}")
                        ], className="mb-2"),
                        html.Small([
                            "VR: ",
                            html.Span(f"{vr:.2f}x", className=f"fw-bold text-{'success' if vr >= 1.5 else 'warning' if vr >= 1.0 else 'danger'}")
                        ], className="d-block"),
                        html.Small(f"ATR(14): {atr14:,.0f}", className="d-block text-muted")
                    ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(23,162,184,0.1)"})
                ], md=4),

                # Resistance info
                dbc.Col([
                    html.Div([
                        html.H6("Resistance V8", className="text-danger mb-2"),
                        html.H4(f"Rp {resistance:,.0f}", className="text-danger fw-bold mb-1"),
                        html.Div([
                            dbc.Badge(f"Q: {resistance_quality:.0%}", color="danger", className="me-1"),
                            dbc.Badge(f"{resistance_touches}x touches", color="dark"),
                        ], className="mb-2"),
                        html.Small([
                            "Jarak: ",
                            html.Span(f"{dist_from_resistance:.1f}%", className="fw-bold")
                        ], className="d-block text-muted"),
                        html.Small(f"Zone: {resistance-tolerance:,.0f} - {resistance+tolerance:,.0f}", className="d-block text-muted")
                    ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(220,53,69,0.1)"})
                ], md=4),
            ], className="mb-3"),

            html.Hr(),

            # Trading Levels
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Small("STOP LOSS", className="text-danger d-block"),
                        html.H5(f"Rp {stop_loss:,.0f}", className="text-danger mb-0"),
                        html.Small("Support - 5%", className="text-muted")
                    ], className="text-center")
                ], md=4),
                dbc.Col([
                    html.Div([
                        html.Small("ENTRY ZONE", className="text-info d-block"),
                        html.H5(f"< Rp {support + (support * 0.05):,.0f}", className="text-info mb-0"),
                        html.Small("Near Support (≤5%)", className="text-muted")
                    ], className="text-center")
                ], md=4),
                dbc.Col([
                    html.Div([
                        html.Small("TARGET", className="text-success d-block"),
                        html.H5(f"Rp {target:,.0f}", className="text-success mb-0"),
                        html.Small("Resistance - 2%", className="text-muted")
                    ], className="text-center")
                ], md=4),
            ], className="mb-3"),

            html.Hr(),

            # V8 Entry Criteria
            html.Div([
                html.H6([html.I(className="fas fa-check-circle me-2"), "Kriteria Entry V8"], className="mb-2"),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span("✓" if dist_from_support <= 5 else "✗",
                                     className=f"me-2 text-{'success' if dist_from_support <= 5 else 'danger'}"),
                            html.Strong("Near Support", className="me-2"),
                            html.Small(f"({dist_from_support:.1f}% ≤ 5%)" if dist_from_support <= 5 else f"({dist_from_support:.1f}% > 5%)",
                                      className="text-muted")
                        ], className="mb-2"),
                        html.Div([
                            html.Span("✓" if 'ACCUMULATION' in phase else "✗",
                                     className=f"me-2 text-{'success' if 'ACCUMULATION' in phase else 'danger'}"),
                            html.Strong("Valid Phase", className="me-2"),
                            html.Small(f"({phase})", className="text-muted")
                        ], className="mb-2"),
                    ], md=6),
                    dbc.Col([
                        html.Div([
                            html.Span("✓" if support_quality >= 0.5 else "✗",
                                     className=f"me-2 text-{'success' if support_quality >= 0.5 else 'danger'}"),
                            html.Strong("Quality ≥ 50%", className="me-2"),
                            html.Small(f"({support_quality:.0%})", className="text-muted")
                        ], className="mb-2"),
                        html.Div([
                            html.Span("✓" if support_touches >= 3 else "✗",
                                     className=f"me-2 text-{'success' if support_touches >= 3 else 'danger'}"),
                            html.Strong("Touches ≥ 3", className="me-2"),
                            html.Small(f"({support_touches}x)", className="text-muted")
                        ], className="mb-2"),
                    ], md=6),
                ])
            ], className="p-3 rounded", style={"backgroundColor": "rgba(108,117,125,0.1)"}),
        ])
    ], className="mb-4", style={"border": f"2px solid var(--bs-{phase_color})"})


def create_fixed_zones_card(stock_code):
    """Create card showing fixed S/R zones from zones_config.py (Formula V10 zones)"""
    zones = get_zones(stock_code)
    if not zones:
        return None

    try:
        price_df = get_price_data(stock_code)
        if price_df.empty:
            return None
        current_price = float(price_df['close'].iloc[-1])
    except:
        return None

    support_zones = []
    resistance_zones = []
    current_zone = None

    for zone_num, zone_data in sorted(zones.items()):
        zone_low = zone_data['low']
        zone_high = zone_data['high']
        zone_mid = (zone_low + zone_high) / 2

        zone_info = {
            'num': zone_num,
            'low': zone_low,
            'high': zone_high,
            'mid': zone_mid,
            'range': f"{zone_low:,.0f} - {zone_high:,.0f}",
            'width_pct': (zone_high - zone_low) / zone_mid * 100
        }

        if current_price >= zone_low and current_price <= zone_high:
            current_zone = zone_info
            zone_info['status'] = 'INSIDE'
        elif zone_high < current_price:
            distance_pct = (current_price - zone_high) / current_price * 100
            zone_info['distance_pct'] = distance_pct
            zone_info['status'] = 'SUPPORT'
            support_zones.append(zone_info)
        else:
            distance_pct = (zone_low - current_price) / current_price * 100
            zone_info['distance_pct'] = distance_pct
            zone_info['status'] = 'RESISTANCE'
            resistance_zones.append(zone_info)

    support_zones.sort(key=lambda x: x.get('distance_pct', 999))
    resistance_zones.sort(key=lambda x: x.get('distance_pct', 999))

    nearest_support = support_zones[0] if support_zones else None
    nearest_resistance = resistance_zones[0] if resistance_zones else None

    risk_reward = None
    if nearest_support and nearest_resistance:
        risk = current_price - nearest_support['high']
        reward = nearest_resistance['low'] - current_price
        if risk > 0:
            risk_reward = reward / risk

    # Build zone list components
    support_list = []
    for z in support_zones:
        support_list.append(html.Div([
            html.Span(f"Z{z['num']}", className="badge bg-success me-2"),
            html.Span(f"Rp {z['range']}", className="fw-bold me-2"),
            html.Small(f"-{z.get('distance_pct', 0):.1f}%", className="text-success")
        ], className="p-2 mb-2 rounded", style={"backgroundColor": "rgba(40,167,69,0.15)"}))

    resistance_list = []
    for z in resistance_zones:
        resistance_list.append(html.Div([
            html.Span(f"Z{z['num']}", className="badge bg-danger me-2"),
            html.Span(f"Rp {z['range']}", className="fw-bold me-2"),
            html.Small(f"+{z.get('distance_pct', 0):.1f}%", className="text-danger")
        ], className="p-2 mb-2 rounded", style={"backgroundColor": "rgba(220,53,69,0.15)"}))

    # Position text
    if current_zone:
        pos_text = f"Di dalam Z{current_zone['num']}"
    elif not resistance_zones:
        pos_text = "Di atas semua zona"
    elif not support_zones:
        pos_text = f"Di bawah Z{resistance_zones[0]['num']}"
    else:
        pos_text = f"Antara Z{support_zones[0]['num']} dan Z{resistance_zones[0]['num']}"

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                html.I(className="fas fa-crosshairs me-2"),
                "Formula V11b1 - Support & Resistance Zones ",
                dbc.Badge("FIX", color="warning", className="ms-2")
            ], className="mb-0"),
        ]),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H6("Harga Sekarang", className="text-muted small text-center"),
                    html.H3(f"Rp {current_price:,.0f}", className="text-info mb-0 text-center"),
                    html.Small(pos_text, className="text-muted d-block text-center")
                ], width=4),
                dbc.Col([
                    html.H6("Nearest Support", className="text-muted small text-center"),
                    html.H3(f"Rp {nearest_support['high']:,.0f}" if nearest_support else "-", className="text-success mb-0 text-center"),
                    html.Small(f"Z{nearest_support['num']}" if nearest_support else "", className="text-muted d-block text-center")
                ], width=4),
                dbc.Col([
                    html.H6("Nearest Resistance", className="text-muted small text-center"),
                    html.H3(f"Rp {nearest_resistance['low']:,.0f}" if nearest_resistance else "-", className="text-danger mb-0 text-center"),
                    html.Small(f"Z{nearest_resistance['num']}" if nearest_resistance else "", className="text-muted d-block text-center")
                ], width=4),
            ], className="mb-4"),
            html.Div([
                html.Strong("Risk/Reward: "),
                html.Span(f"{risk_reward:.2f}x" if risk_reward else "N/A",
                         className="text-success fw-bold" if risk_reward and risk_reward >= 2 else "text-warning fw-bold")
            ], className="p-2 mb-3 rounded", style={"backgroundColor": "rgba(108,117,125,0.1)"}),
            dbc.Row([
                dbc.Col([
                    html.H6("Support Zones", className="text-success mb-2"),
                ] + (support_list if support_list else [html.Small("Tidak ada", className="text-muted")]), md=6),
                dbc.Col([
                    html.H6("Resistance Zones", className="text-danger mb-2"),
                ] + (resistance_list if resistance_list else [html.Small("Tidak ada", className="text-muted")]), md=6),
            ])
        ])
    ], className="mb-4", color="dark", style={"border": "2px solid #ffc107"})


def create_sr_levels_card(sr_analysis, stock_code):
    """
    Create Support/Resistance Levels card dengan 3 metode:
    1. Volume Profile - area transaksi terbesar
    2. Price Bounce - harga sering memantul
    3. Broker Position - posisi broker besar
    """
    if not sr_analysis or 'error' in sr_analysis:
        return dbc.Card([
            dbc.CardHeader(html.H5("Support & Resistance Levels", className="mb-0")),
            dbc.CardBody([html.P("Data tidak tersedia", className="text-muted")])
        ], className="mb-4", color="dark")

    current_price = sr_analysis.get('current_price', 0)
    supports = sr_analysis.get('supports', [])
    resistances = sr_analysis.get('resistances', [])
    strongest_support = sr_analysis.get('strongest_support')
    strongest_resistance = sr_analysis.get('strongest_resistance')
    key_support = sr_analysis.get('key_support', 0)
    key_resistance = sr_analysis.get('key_resistance', 0)
    interpretation = sr_analysis.get('interpretation', {})

    # Source color mapping
    source_colors = {
        'Volume Profile': '#17a2b8',  # info/cyan
        'Price Bounce': '#ffc107',    # warning/yellow
        'Broker Position': '#6f42c1',  # purple
        'Multi-Confirmed': '#28a745'   # green for multi-confirmed
    }

    def create_level_badge(level_data):
        """Create badge for a support/resistance level with multi-confirmation indicator"""
        source = level_data.get('source', '')
        confirmations = level_data.get('confirmations', 1)
        strength = level_data.get('strength', 0)
        color = source_colors.get(source, '#6c757d')

        # Multi-confirmation indicator
        confirm_badge = None
        if confirmations >= 2:
            confirm_badge = dbc.Badge(
                f"{confirmations}x",
                color="success",
                className="me-1",
                style={"fontSize": "9px"}
            )

        # Strength indicator (stars based on score)
        strength_stars = ""
        if strength >= 100:
            strength_stars = "[*][*][*]"
        elif strength >= 50:
            strength_stars = "[*][*]"
        elif strength >= 20:
            strength_stars = "[*]"

        return html.Div([
            html.Span(
                f"Rp {level_data['level']:,.0f}",
                className="fw-bold me-2"
            ),
            confirm_badge,
            dbc.Badge(
                source,
                style={"backgroundColor": color, "fontSize": "10px"},
                className="me-2"
            ),
            html.Span(strength_stars, className="text-warning me-2", style={"fontSize": "10px"}) if strength_stars else None,
            html.Small(
                level_data.get('description', ''),
                className="text-muted"
            )
        ], className="mb-2 p-2 rounded metric-box")

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                html.I(className="fas fa-layer-group me-2"),
                "Support & Resistance Levels ",
                html.Small("(Multi-Method Analysis)", className="text-muted")
            ], className="mb-0 d-inline"),
        ]),
        dbc.CardBody([
            # Key Levels Summary
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H6("Harga Sekarang", className="text-muted small"),
                        html.H3(f"Rp {current_price:,.0f}", className="text-info mb-0")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H6([
                            html.I(className="fas fa-arrow-down text-success me-1"),
                            "Key Support"
                        ], className="text-muted small"),
                        html.H3(f"Rp {key_support:,.0f}", className="text-success mb-0"),
                        html.Small(f"-{interpretation.get('support_distance_pct', 0):.1f}%", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H6([
                            html.I(className="fas fa-arrow-up text-danger me-1"),
                            "Key Resistance"
                        ], className="text-muted small"),
                        html.H3(f"Rp {key_resistance:,.0f}", className="text-danger mb-0"),
                        html.Small(f"+{interpretation.get('resistance_distance_pct', 0):.1f}%", className="text-muted")
                    ], className="text-center")
                ], width=4),
            ], className="mb-3"),

            # Risk/Reward Ratio
            html.Div([
                html.Strong("Risk/Reward Ratio: "),
                html.Span(
                    f"{interpretation.get('risk_reward', 0):.2f}x",
                    className="fw-bold text-warning"
                ),
                html.Small(
                    " (Potential gain vs potential loss dari level saat ini)",
                    className="text-muted ms-2"
                )
            ], className="mb-3 p-2 rounded info-box"),

            html.Hr(),

            # Support & Resistance Lists
            dbc.Row([
                dbc.Col([
                    html.H6([
                        html.I(className="fas fa-shield-alt text-success me-2"),
                        "Support Levels (Nearest First)"
                    ], className="mb-3"),
                    html.Div([
                        create_level_badge(s) for s in supports[:5]
                    ]) if supports else html.P("Tidak ada support terdeteksi", className="text-muted")
                ], width=6),
                dbc.Col([
                    html.H6([
                        html.I(className="fas fa-hand-paper text-danger me-2"),
                        "Resistance Levels (Nearest First)"
                    ], className="mb-3"),
                    html.Div([
                        create_level_badge(r) for r in resistances[:5]
                    ]) if resistances else html.P("Tidak ada resistance terdeteksi", className="text-muted")
                ], width=6),
            ]),

            html.Hr(),

            # Legend
            html.Div([
                html.Small("Sumber Analisis: ", className="text-muted me-2"),
                html.Span([
                    html.I(className="fas fa-square me-1", style={"color": source_colors['Volume Profile']}),
                    "Volume Profile "
                ], className="me-3", style={"fontSize": "11px"}),
                html.Span([
                    html.I(className="fas fa-square me-1", style={"color": source_colors['Price Bounce']}),
                    "Price Bounce "
                ], className="me-3", style={"fontSize": "11px"}),
                html.Span([
                    html.I(className="fas fa-square me-1", style={"color": source_colors['Broker Position']}),
                    "Broker Position "
                ], style={"fontSize": "11px"}),
            ], className="mb-2"),

            # Interpretation
            html.Small([
                html.Strong("Cara Baca: "),
                html.Br(),
                html.Span("* Volume Profile", style={"color": source_colors['Volume Profile']}),
                " = Area dengan transaksi terbesar (banyak buyer/seller tertarik)",
                html.Br(),
                html.Span("* Price Bounce", style={"color": source_colors['Price Bounce']}),
                " = Level harga yang sering memantul (historically proven)",
                html.Br(),
                html.Span("* Broker Position", style={"color": source_colors['Broker Position']}),
                " = Avg Buy broker besar (akan defend/sell di area ini)",
            ], className="text-muted")
        ])
    ], className="mb-4")


def create_top_brokers_card(avg_buy_analysis, stock_code):
    """
    Create Top 10 Broker by Buy Value card
    Menampilkan broker dengan buy value terbesar dalam 60 hari terakhir
    """
    if 'error' in avg_buy_analysis:
        return dbc.Card([
            dbc.CardHeader(html.H5("Top 10 Broker by Buy Value", className="mb-0")),
            dbc.CardBody([html.P("Data tidak tersedia", className="text-muted")])
        ], className="mb-4", color="dark")

    brokers = avg_buy_analysis.get('brokers', [])[:10]
    current_price = avg_buy_analysis.get('current_price', 0)

    # Get sensitive brokers list
    try:
        broker_sens = calculate_broker_sensitivity_advanced(stock_code)
        sensitive_brokers = set(broker_sens.get('top_5_brokers', []))
    except:
        sensitive_brokers = set()

    if not brokers:
        return dbc.Card([
            dbc.CardHeader(html.H5("Top 10 Broker by Buy Value", className="mb-0")),
            dbc.CardBody([html.P("Tidak ada data broker", className="text-muted")])
        ], className="mb-4", color="dark")

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                html.I(className="fas fa-users me-2"),
                "Top 10 Broker by Buy Value ",
                html.Small("(60 hari terakhir)", className="text-muted")
            ], className="mb-0"),
        ]),
        dbc.CardBody([
            # Current price reference
            html.Div([
                html.Strong("Harga Sekarang: "),
                html.Span(f"Rp {current_price:,.0f}", className="text-info")
            ], className="mb-3"),

            # Broker type legend
            html.Div([
                html.Small("Legenda Broker: ", className="text-muted me-2"),
                html.Span([
                    html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['FOREIGN'], "fontSize": "10px"}),
                    "Asing "
                ], className="me-2", style={"fontSize": "10px"}),
                html.Span([
                    html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['BUMN'], "fontSize": "10px"}),
                    "BUMN "
                ], className="me-2", style={"fontSize": "10px"}),
                html.Span([
                    html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['LOCAL'], "fontSize": "10px"}),
                    "Lokal "
                ], style={"fontSize": "10px"}),
            ], className="mb-3"),

            # Top 10 Brokers Table
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Broker", style={"width": "80px"}),
                    html.Th("Tipe", style={"width": "120px"}),
                    html.Th("Avg Buy", style={"width": "100px"}),
                    html.Th("Buy Value", style={"width": "90px"}),
                    html.Th("Net", style={"width": "80px"}),
                    html.Th("Floating", style={"width": "80px"}),
                    html.Th("Status", style={"width": "70px"})
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(colored_broker(b['broker_code'], with_badge=True)),
                        html.Td(html.Span(
                            get_broker_info(b['broker_code'])['type_name'],
                            className=f"broker-{get_broker_type(b['broker_code']).lower()}"
                        )),
                        # Avg Buy - orange background for sensitive brokers
                        html.Td(
                            html.Span(
                                f"Rp {b['avg_buy_price']:,.0f}",
                                style={"backgroundColor": "#FF8C00", "color": "#000", "fontWeight": "bold", "padding": "2px 6px", "borderRadius": "4px", "display": "inline-block"}
                            ) if b['broker_code'] in sensitive_brokers else f"Rp {b['avg_buy_price']:,.0f}"
                        ),
                        html.Td(f"{b['total_buy_value']/1e9:.1f}B"),
                        # Net - orange background for sensitive brokers
                        html.Td(
                            html.Span(
                                f"{b['net_value']/1e9:+.1f}B",
                                style={"backgroundColor": "#FF8C00", "color": "#000", "fontWeight": "bold", "padding": "2px 6px", "borderRadius": "4px", "display": "inline-block"}
                            ) if b['broker_code'] in sensitive_brokers else html.Span(
                                f"{b['net_value']/1e9:+.1f}B",
                                className="text-success" if b['net_value'] > 0 else "text-danger"
                            )
                        ),
                        html.Td(f"{b.get('floating_pct', 0):+.1f}%", className="text-success" if b.get('floating_pct', 0) > 0 else "text-danger"),
                        html.Td(b.get('position', '-'), className="text-success" if b.get('position') == 'PROFIT' else "text-danger" if b.get('position') == 'LOSS' else "")
                    ]) for b in brokers
                ])
            ], className="table table-sm table-dark table-hover", style={"fontSize": "12px"}),

            html.Hr(),

            # Interpretation
            html.Small([
                html.Strong("Cara Baca: "),
                html.Br(),
                "* ", html.Span("Avg Buy", className="text-info"), " = Rata-rata harga beli broker dalam 60 hari",
                html.Br(),
                "* ", html.Span("Floating +%", className="text-success"), " = Broker sedang profit",
                html.Br(),
                "* ", html.Span("Floating -%", className="text-danger"), " = Broker sedang loss (mungkin defend/averaging)",
                html.Br(),
                "* Net positif = akumulasi, Net negatif = distribusi",
                html.Br(),
                "* ", html.Span("Background Orange", style={"backgroundColor": "#FF8C00", "color": "#000", "padding": "1px 4px", "borderRadius": "3px"}), " = Broker Sensitive (pola akumulasi akurat)"
            ], className="text-muted")
        ])
    ], className="mb-4", color="dark", outline=True)


# ============================================================
# PAGE: SUPPORT & RESISTANCE (New Sub-menu from Analysis)
# ============================================================

def create_support_resistance_page(stock_code='CDIA'):
    """Create Support & Resistance analysis page - moved from Analysis page"""
    try:
        # Get Avg Buy Analysis
        avg_buy_analysis = analyze_avg_buy_position(stock_code)

        # Get Support/Resistance Analysis (Multi-Method)
        sr_analysis = analyze_support_resistance(stock_code)

    except Exception as e:
        return html.Div([
            dbc.Alert(f"Error loading S/R analysis for {stock_code}: {str(e)}", color="danger"),
            html.P("Pastikan data sudah diupload dengan benar")
        ])

    # Check if stock has fixed V10 zones
    fixed_zones_card = create_fixed_zones_card(stock_code)

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-layer-group me-2"),
                f"Support & Resistance - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_submenu_nav('support-resistance', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # ========== FIXED V11b1 ZONES (primary - only show this) ==========
        fixed_zones_card if fixed_zones_card else dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            f"Emiten {stock_code} belum memiliki konfigurasi zona V11b1. ",
            "Hubungi admin untuk menambahkan zona support & resistance."
        ], color="warning", className="mb-4"),

        # ========== S/R CHART WITH V11b1 ZONES ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-chart-area me-2"),
                    "Price Chart with V11b1 Zones" if fixed_zones_card else "Price Chart"
                ], className="mb-0"),
            ]),
            dbc.CardBody([
                create_sr_chart(stock_code, sr_analysis, days=60)
            ], className="p-2")
        ], className="mb-4", color="dark"),

        # ========== AVG BUY ANALYSIS ==========
        create_avg_buy_card(avg_buy_analysis, stock_code, sr_analysis),

        # ========== TOP 10 BROKER BY BUY VALUE ==========
        create_top_brokers_card(avg_buy_analysis, stock_code),

    ], className="container-fluid p-4")


# ============================================================
# NEW DASHBOARD SECTIONS - Replacing Top 10 Acc/Dist duplicates
# ============================================================

def create_quick_sentiment_summary(stock_code='CDIA'):
    """
    Section 1: Quick Sentiment Summary
    - Foreign flow hari ini vs kemarin
    - Rasio akumulasi vs distribusi
    - Trend mingguan
    - By broker type
    """
    try:
        broker_df = get_broker_data(stock_code)
        price_df = get_price_data(stock_code)
        foreign_flow = calculate_foreign_flow_momentum(stock_code)

        if broker_df.empty:
            return dbc.Card([
                dbc.CardHeader("[#] Market Sentiment"),
                dbc.CardBody(html.P("No data available", className="text-muted"))
            ], className="mb-3", color="dark")

        # Get latest and previous day data
        latest_date = broker_df['date'].max()
        prev_date = broker_df[broker_df['date'] < latest_date]['date'].max() if len(broker_df['date'].unique()) > 1 else latest_date

        # Today's data
        today_data = broker_df[broker_df['date'] == latest_date]
        prev_data = broker_df[broker_df['date'] == prev_date]

        # Calculate accumulation ratio
        today_buy = today_data[today_data['net_value'] > 0]['net_value'].sum()
        today_sell = abs(today_data[today_data['net_value'] < 0]['net_value'].sum())
        total_flow = today_buy + today_sell
        accum_ratio = (today_buy / total_flow * 100) if total_flow > 0 else 50

        # Foreign flow - use correct keys from calculate_foreign_flow_momentum
        # latest_foreign is already in billions
        foreign_today = foreign_flow.get('latest_foreign', 0)
        # Calculate yesterday from today - momentum (momentum is the difference)
        foreign_momentum = foreign_flow.get('momentum', 0)
        foreign_yesterday = foreign_today - foreign_momentum
        foreign_signal = foreign_flow.get('direction_label', 'FLAT')  # INFLOW/OUTFLOW/FLAT
        foreign_consistency = foreign_flow.get('consistency', 0)  # Positive = inflow, negative = outflow
        foreign_streak = abs(foreign_consistency)  # Streak count
        foreign_streak_direction = 'beli' if foreign_consistency > 0 else 'jual'

        # Weekly trend (last 5 days)
        weekly_data = []
        dates_sorted = sorted(broker_df['date'].unique(), reverse=True)[:5]
        for d in reversed(dates_sorted):
            day_net = broker_df[broker_df['date'] == d]['net_value'].sum() / 1e9
            weekly_data.append({'date': d, 'net': day_net})
        weekly_total = sum([d['net'] for d in weekly_data])

        # By broker type
        type_flow = {}
        for _, row in today_data.iterrows():
            broker_type = get_broker_info(row['broker_code'])['type']
            if broker_type not in type_flow:
                type_flow[broker_type] = 0
            type_flow[broker_type] += row['net_value']

        # Subtitles for sentiment (Indonesian)
        foreign_subtitle = "Netral dibanding kemarin" if abs(foreign_today - foreign_yesterday) < 0.5 else (
            "Lebih tinggi dari kemarin" if foreign_today > foreign_yesterday else "Lebih rendah dari kemarin"
        )
        accum_subtitle = "Belum ada dominasi" if 45 <= accum_ratio <= 55 else (
            "Pembeli mendominasi" if accum_ratio > 55 else "Penjual mendominasi"
        )
        streak_subtitle = "Belum ada tren beli/jual beruntun" if foreign_streak == 0 else (
            f"Tren {foreign_streak_direction} {foreign_streak} hari berturut"
        )

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-pie me-2"),
                html.Span("Sentimen Pasar Hari Ini", className="fw-bold")
            ]),
            dbc.CardBody([
                # Top row: 3 metric cards with Indonesian labels
                dbc.Row([
                    # 1. Aliran Dana Asing
                    dbc.Col([
                        html.Div([
                            html.Small([
                                html.I(className="fas fa-globe me-1"),
                                html.Span("Aliran Dana Asing", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                                         title=TERM_DEFINITIONS.get('foreign_flow', '')),
                            ], className="text-muted"),
                            html.H4([
                                f"{foreign_today:+.1f}B ",
                                html.Span("[G]" if foreign_today > 0 else ("[R]" if foreign_today < 0 else "[N]"), style={"fontSize": "16px"})
                            ], className="mb-0"),
                            html.Small(foreign_subtitle, className="text-muted", style={"fontSize": "10px"})
                        ], className="text-center p-2 rounded metric-box")
                    ], width=4),

                    # 2. Rasio Beli vs Jual
                    dbc.Col([
                        html.Div([
                            html.Small([
                                html.I(className="fas fa-balance-scale me-1"),
                                html.Span("Rasio Beli vs Jual", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                                         title=TERM_DEFINITIONS.get('accum_ratio', '')),
                            ], className="text-muted"),
                            html.H4([
                                f"{accum_ratio:.0f}% Buy | {100-accum_ratio:.0f}% Sell",
                            ], className=f"mb-0 text-{'success' if accum_ratio > 55 else ('danger' if accum_ratio < 45 else 'warning')}", style={"fontSize": "14px"}),
                            html.Small(accum_subtitle, className="text-muted", style={"fontSize": "10px"})
                        ], className="text-center p-2 rounded metric-box")
                    ], width=4),

                    # 3. Konsistensi Asing
                    dbc.Col([
                        html.Div([
                            html.Small([
                                html.I(className="fas fa-sync-alt me-1"),
                                html.Span("Konsistensi Asing", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                                         title=TERM_DEFINITIONS.get('foreign_streak', '')),
                            ], className="text-muted"),
                            html.H4([
                                f"{foreign_streak} hari ",
                            ], className="mb-0"),
                            html.Small(streak_subtitle, className="text-muted", style={"fontSize": "10px"})
                        ], className="text-center p-2 rounded metric-box")
                    ], width=4),
                ], className="mb-3"),

                # Weekly trend mini chart (Indonesian)
                html.Div([
                    html.Small("Tren Mingguan: ", className="text-muted me-2"),
                    *[html.Span([
                        html.Span(f"{d['net']:+.1f}B ",
                                 className=f"text-{'success' if d['net'] > 0 else 'danger'} me-2",
                                 style={"fontSize": "11px"})
                    ]) for d in weekly_data],
                    html.Span(f"Total: {weekly_total:+.1f}B",
                             className=f"fw-bold text-{'success' if weekly_total > 0 else 'danger'}")
                ], className="mb-2", style={"fontSize": "11px"}),

                # By broker type (Indonesian)
                html.Div([
                    html.Small("Per Tipe Broker: ", className="text-muted me-2"),
                    html.Span([
                        html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS.get('FOREIGN', '#dc3545'), "fontSize": "8px"}),
                        f"Asing: {type_flow.get('FOREIGN', 0)/1e9:+.1f}B "
                    ], className="me-2", style={"fontSize": "11px"}),
                    html.Span([
                        html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS.get('BUMN', '#28a745'), "fontSize": "8px"}),
                        f"BUMN: {type_flow.get('BUMN', 0)/1e9:+.1f}B "
                    ], className="me-2", style={"fontSize": "11px"}),
                    html.Span([
                        html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS.get('LOCAL', '#6f42c1'), "fontSize": "8px"}),
                        f"Lokal: {type_flow.get('LOCAL', 0)/1e9:+.1f}B"
                    ], style={"fontSize": "11px"}),
                ]),
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("[#] Market Sentiment"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def create_key_metrics_compact(stock_code='CDIA'):
    """
    Section 2: Signal Drivers & Supporting Metrics
    - Hierarchical layout: Primary (decision drivers) vs Secondary (context)
    - Primary: Smart Money, Accum Phase, Market Phase
    - Secondary: Broker Sensitivity, Foreign Flow, RVOL, S/R
    """
    try:
        full_analysis = get_comprehensive_analysis(stock_code)
        broker_sens = full_analysis.get('broker_sensitivity', {})
        foreign_flow = full_analysis.get('foreign_flow', {})
        smart_money = full_analysis.get('smart_money', {})
        accum_phase = full_analysis.get('accumulation_phase', {})
        volume_analysis = full_analysis.get('volume_analysis', {})
        sr_analysis = analyze_support_resistance(stock_code)

        def primary_metric_card(title, value, subtitle, color="info", tooltip_key=None, icon=None):
            """Larger card for primary signal drivers"""
            if tooltip_key and tooltip_key in TERM_DEFINITIONS:
                title_element = html.Div([
                    html.I(className=f"fas {icon} me-1 text-{color}") if icon else None,
                    html.Span(title, style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS[tooltip_key]),
                ], className="d-flex align-items-center justify-content-center")
            else:
                title_element = html.Div([
                    html.I(className=f"fas {icon} me-1 text-{color}") if icon else None,
                    html.Span(title),
                ], className="d-flex align-items-center justify-content-center")

            return html.Div([
                html.Small(title_element, className="text-muted", style={"fontSize": "11px"}),
                html.H4(value, className=f"text-{color} mb-0 mt-1"),
                html.Small(subtitle, className="text-muted", style={"fontSize": "10px"})
            ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)", "border": f"1px solid var(--bs-{color})"})

        def secondary_metric_card(title, value, subtitle, color="secondary", tooltip_key=None):
            """Smaller card for supporting metrics"""
            if tooltip_key and tooltip_key in TERM_DEFINITIONS:
                title_element = html.Small([
                    html.Span(title, style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS[tooltip_key]),
                ], className="text-muted", style={"fontSize": "9px"})
            else:
                title_element = html.Small(title, className="text-muted", style={"fontSize": "9px"})

            return html.Div([
                title_element,
                html.H6(value, className=f"text-{color} mb-0"),
                html.Small(subtitle, className="text-muted", style={"fontSize": "8px"})
            ], className="text-center p-2 rounded metric-box")

        # Get values
        sens_score = broker_sens.get('avg_win_rate', 0) if broker_sens else 0
        top_brokers = broker_sens.get('top_5_brokers', [])[:2] if broker_sens else []

        foreign_score = foreign_flow.get('score', 0)
        foreign_signal = foreign_flow.get('signal', 'NEUTRAL')

        smart_score = smart_money.get('score', 0)
        smart_detected = smart_money.get('detection', 'NO')

        accum_in = accum_phase.get('in_accumulation', False)
        accum_range = accum_phase.get('range_pct', 0)
        accum_days = accum_phase.get('days_in_range', 0)

        rvol = volume_analysis.get('rvol', 1.0)
        vpt_signal = volume_analysis.get('vpt_signal', 'NEUTRAL')

        key_support = sr_analysis.get('key_support', 0) if sr_analysis else 0
        key_resistance = sr_analysis.get('key_resistance', 0) if sr_analysis else 0
        current_price = sr_analysis.get('current_price', 0) if sr_analysis else 0

        support_pct = ((current_price - key_support) / current_price * 100) if current_price > 0 and key_support > 0 else 0
        resist_pct = ((key_resistance - current_price) / current_price * 100) if current_price > 0 and key_resistance > 0 else 0

        # Determine market phase
        if accum_in and smart_score > 60:
            market_phase = "AKUMULASI"
            phase_color = "success"
            phase_desc = "Fase beli bertahap"
        elif not accum_in and rvol > 1.5:
            market_phase = "MARKUP"
            phase_color = "warning"
            phase_desc = "Fase kenaikan harga"
        elif foreign_score < -30 or smart_score < 30:
            market_phase = "DISTRIBUSI"
            phase_color = "danger"
            phase_desc = "Fase jual bertahap"
        else:
            market_phase = "SIDEWAYS"
            phase_color = "secondary"
            phase_desc = "Belum ada arah jelas"

        # Phase descriptions (Indonesian - FINAL COPYWRITING)
        phase_desc_detail = {
            'AKUMULASI': 'Arah belum jelas, perlu konfirmasi',
            'MARKUP': 'Fase kenaikan harga aktif',
            'DISTRIBUSI': 'Fase pelepasan saham',
            'SIDEWAYS': 'Arah belum jelas, perlu konfirmasi'
        }.get(market_phase, 'Analisis fase pasar')

        # Accum phase description
        accum_desc = "Range terlalu lebar / data belum valid" if not accum_in else f"Range {accum_range:.1f}% selama {accum_days} hari"

        # Smart money description
        smart_desc = "Belum ada akumulasi signifikan" if smart_score < 50 else ("Ada tanda akumulasi besar" if smart_score >= 60 else "Tanda awal akumulasi")

        # Foreign direction description
        foreign_dir = "positif ringan" if 0 < foreign_score <= 20 else ("positif kuat" if foreign_score > 20 else ("negatif ringan" if -20 <= foreign_score < 0 else ("negatif kuat" if foreign_score < -20 else "netral")))

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-bullseye me-2 text-warning"),
                html.Span("Signal Drivers", className="fw-bold text-warning"),
            ], className="bg-transparent"),
            dbc.CardBody([
                # === PRIMARY (menentukan aksi) ===
                html.Div([
                    html.Small([
                        html.I(className="fas fa-star me-1 text-warning"),
                        "PRIMARY (menentukan aksi):"
                    ], className="text-warning fw-bold", style={"fontSize": "10px"})
                ], className="mb-2"),

                dbc.Row([
                    # 1. Struktur Pasar Jangka Pendek (7 Hari)
                    dbc.Col([
                        primary_metric_card(
                            "Struktur Pasar (7 Hari)",
                            market_phase,
                            phase_desc_detail,
                            phase_color,
                            tooltip_key="market_phase",
                            icon="fa-compass"
                        )
                    ], md=4, className="mb-2"),

                    # 2. Fase Akumulasi
                    dbc.Col([
                        primary_metric_card(
                            "Fase Akumulasi",
                            "AKTIF" if accum_in else "TIDAK",
                            accum_desc,
                            "success" if accum_in else "secondary",
                            tooltip_key="accum_phase",
                            icon="fa-layer-group"
                        )
                    ], md=4, className="mb-2"),

                    # 3. Dana Besar
                    dbc.Col([
                        primary_metric_card(
                            "Dana Besar",
                            f"{smart_score:.0f}",
                            smart_desc,
                            "success" if smart_score > 60 else ("warning" if smart_score > 40 else "secondary"),
                            tooltip_key="smart_money",
                            icon="fa-coins"
                        )
                    ], md=4, className="mb-2"),
                ], className="mb-3"),

                # === SUPPORTING (konfirmasi konteks) ===
                html.Div([
                    html.Small([
                        html.I(className="fas fa-layer-group me-1 text-info"),
                        "SUPPORTING (konfirmasi konteks):"
                    ], className="text-info", style={"fontSize": "10px"})
                ], className="mb-2"),

                dbc.Row([
                    dbc.Col([
                        secondary_metric_card(
                            "Sensitivitas Broker",
                            f"{sens_score:.0f}%",
                            html.Span(["Top: ", colored_broker(top_brokers[0], with_badge=True)] if top_brokers else "N/A"),
                            "info" if sens_score > 50 else "secondary",
                            tooltip_key="broker_sensitivity"
                        )
                    ], width=3),
                    dbc.Col([
                        secondary_metric_card(
                            "Arah Asing",
                            f"{foreign_score:+.0f}",
                            foreign_dir,
                            "success" if foreign_score > 0 else ("danger" if foreign_score < 0 else "secondary"),
                            tooltip_key="foreign_flow"
                        )
                    ], width=3),
                    dbc.Col([
                        secondary_metric_card(
                            "Volume (RVOL)",
                            f"{rvol:.1f}x",
                            "tinggi" if rvol > 1.2 else ("normal" if rvol > 0.8 else "rendah"),
                            "success" if rvol > 1.2 else ("warning" if rvol > 0.8 else "secondary"),
                            tooltip_key="rvol"
                        )
                    ], width=3),
                    dbc.Col([
                        secondary_metric_card(
                            "Support/Resist",
                            f"-{support_pct:.0f}% ke S",
                            f"+{resist_pct:.0f}% ke R",
                            "info"
                        )
                    ], width=3),
                ]),

                html.Hr(className="my-2"),

                # Quick Guide (WAJIB ADA)
                html.Div([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        html.Strong("Quick Guide: "),
                        "PRIMARY menentukan aksi (Buy / Wait). ",
                        "SUPPORTING membantu membaca konteks & risiko."
                    ], className="text-muted", style={"fontSize": "9px"})
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,193,7,0.1)"})
            ])
        ], className="mb-3", style={"border": "1px solid var(--bs-warning)"})
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("[S] Key Metrics"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def create_broker_movement_alert(stock_code='CDIA'):
    """
    Section 3: Broker Movement Alert
    FINAL UI COPYWRITING V2 - Professional, edukatif, actionable
    """
    try:
        broker_df = get_broker_data(stock_code)

        if broker_df.empty:
            return dbc.Card([
                dbc.CardHeader("[MEMO] Broker Movement Alert"),
                dbc.CardBody(html.P("Data tidak tersedia", className="text-muted"))
            ], className="mb-3", color="dark")

        # Get last 2 days
        dates_sorted = sorted(broker_df['date'].unique(), reverse=True)
        if len(dates_sorted) < 2:
            return dbc.Card([
                dbc.CardHeader("[MEMO] Broker Movement Alert"),
                dbc.CardBody(html.P("Membutuhkan minimal 2 hari data", className="text-muted"))
            ], className="mb-3", color="dark")

        today = dates_sorted[0]
        yesterday = dates_sorted[1]

        today_df = broker_df[broker_df['date'] == today].copy()
        yesterday_df = broker_df[broker_df['date'] == yesterday].copy()

        # Calculate daily net by broker
        today_net = today_df.groupby('broker_code')['net_value'].sum().to_dict()
        yesterday_net = yesterday_df.groupby('broker_code')['net_value'].sum().to_dict()

        # Find biggest movements (change from yesterday)
        movements = []
        for broker in set(list(today_net.keys()) + list(yesterday_net.keys())):
            t_val = today_net.get(broker, 0)
            y_val = yesterday_net.get(broker, 0)
            change = t_val - y_val
            movements.append({
                'broker': broker,
                'today': t_val,
                'yesterday': y_val,
                'change': change,
                'type': get_broker_info(broker)['type_name']
            })

        # Sort by absolute change
        movements.sort(key=lambda x: abs(x['change']), reverse=True)
        top_movements = movements[:5]

        # Find new accumulation (was negative/neutral, now positive)
        new_accum = [m for m in movements if m['yesterday'] <= 0 and m['today'] > 1e9][:3]

        # Find new distribution (was positive/neutral, now negative)
        new_dist = [m for m in movements if m['yesterday'] >= 0 and m['today'] < -1e9][:3]

        # Determine dominant movement for sub-headline
        total_accum = sum(m['today'] for m in new_accum) if new_accum else 0
        total_dist = abs(sum(m['today'] for m in new_dist)) if new_dist else 0

        if total_dist > total_accum:
            sub_headline = "Terjadi tekanan jual baru dari beberapa broker besar hari ini."
            sub_color = "danger"
        elif total_accum > total_dist:
            sub_headline = "Terjadi pergeseran beli signifikan oleh broker tertentu hari ini."
            sub_color = "success"
        else:
            sub_headline = "Pergerakan broker relatif seimbang hari ini."
            sub_color = "secondary"

        # Build accumulation items
        accum_items = [html.Div([
            colored_broker(m['broker'], with_badge=True),
            html.Span(f" +{m['today']/1e9:.1f}B", className="text-success fw-bold ms-2")
        ], className="d-inline-flex align-items-center me-3 mb-1") for m in new_accum] if new_accum else [html.Small("Tidak ada hari ini", className="text-muted")]

        # Build distribution items
        dist_items = [html.Div([
            colored_broker(m['broker'], with_badge=True),
            html.Span(f" {m['today']/1e9:.1f}B", className="text-danger fw-bold ms-2")
        ], className="d-inline-flex align-items-center me-3 mb-1") for m in new_dist] if new_dist else [html.Small("Tidak ada hari ini", className="text-muted")]

        return dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-bell me-2"),
                    html.Span("Broker Movement Alert", className="fw-bold"),
                ], className="d-flex align-items-center")
            ]),
            dbc.CardBody([
                # Sub-headline dinamis
                html.P([
                    html.I(className=f"fas fa-{'exclamation-triangle' if sub_color == 'danger' else 'arrow-up' if sub_color == 'success' else 'minus-circle'} me-2 text-{sub_color}"),
                    html.Span(sub_headline, className=f"text-{sub_color}")
                ], className="mb-3", style={"fontSize": "14px"}),

                dbc.Row([
                    # New Accumulation Signal
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span("[G]", className="me-2"),
                                html.Span("New Accumulation", className="text-success fw-bold")
                            ], className="mb-2"),
                            html.Small("Broker yang sebelumnya netral atau jual, hari ini mulai membeli signifikan.",
                                      className="text-muted d-block mb-2", style={"fontSize": "11px"}),
                            html.Div(accum_items, className="d-flex flex-wrap"),
                            html.Small([
                                html.I(className="fas fa-lightbulb me-1"),
                                "Ini sering menjadi sinyal awal perubahan arah."
                            ], className="text-muted fst-italic d-block mt-2", style={"fontSize": "10px"})
                        ], className="p-3 rounded alert-box-success h-100")
                    ], width=12, lg=6, className="mb-3 mb-lg-0"),

                    # New Distribution Warning
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span("[R]", className="me-2"),
                                html.Span("New Distribution", className="text-danger fw-bold")
                            ], className="mb-2"),
                            html.Small("Broker yang sebelumnya netral atau beli, hari ini mulai jual besar.",
                                      className="text-muted d-block mb-2", style={"fontSize": "11px"}),
                            html.Div(dist_items, className="d-flex flex-wrap"),
                            html.Small([
                                html.I(className="fas fa-exclamation-circle me-1"),
                                "Jika terjadi beruntun, risiko tekanan harga lanjutan meningkat."
                            ], className="text-muted fst-italic d-block mt-2", style={"fontSize": "10px"})
                        ], className="p-3 rounded alert-box-danger h-100")
                    ], width=12, lg=6),
                ], className="mb-3"),

                # Biggest Movement Section
                html.Div([
                    html.Div([
                        html.Span("[#]", className="me-2"),
                        html.Span("Perubahan Terbesar Hari Ini vs Kemarin", className="fw-bold")
                    ], className="mb-2"),
                    html.Small("Broker dengan perubahan perilaku paling signifikan.",
                              className="text-muted d-block mb-2", style={"fontSize": "11px"}),
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th("Broker", className="table-header"),
                            html.Th("Tipe", className="table-header"),
                            html.Th([html.Span("Today", title="Net value hari ini")], className="table-header"),
                            html.Th([html.Span("Yest", title="Net value kemarin")], className="table-header"),
                            html.Th([html.Span("Change", title="Perubahan sikap broker")], className="table-header"),
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(colored_broker(m['broker'], with_badge=True), className="table-cell"),
                                html.Td(html.Span(m['type'][:6], className=f"broker-{get_broker_type(m['broker']).lower()}"), className="table-cell"),
                                html.Td(f"{m['today']/1e9:+.1f}B", className="table-cell"),
                                html.Td(f"{m['yesterday']/1e9:+.1f}B", className="table-cell"),
                                html.Td(html.Span(f"{m['change']/1e9:+.1f}B", className="text-success fw-bold" if m['change'] > 0 else "text-danger fw-bold"), className="table-cell"),
                            ]) for m in top_movements
                        ])
                    ], className="table table-sm", style={'width': '100%'}),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Fokus pada broker dengan perubahan ekstrem, karena ini biasanya bukan transaksi acak."
                    ], className="text-muted fst-italic", style={"fontSize": "10px"})
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"}),
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("[MEMO] Broker Movement"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def create_broker_sensitivity_pattern(stock_code='CDIA'):
    """
    Section 4: Top 5 Broker Sensitivity Pattern
    - Historical pattern: win rate, lead time, duration, lot, gain
    - Current status: apakah sedang akumulasi
    """
    try:
        broker_sens = calculate_broker_sensitivity_advanced(stock_code)
        broker_df = get_broker_data(stock_code)
        avg_buy_df = get_broker_avg_buy(stock_code, days=60)

        if not broker_sens or not broker_sens.get('brokers'):
            return dbc.Card([
                dbc.CardHeader("[S] Top 5 Broker Sensitivity Pattern"),
                dbc.CardBody(html.P("No sensitivity data available", className="text-muted"))
            ], className="mb-3", color="dark")

        top_5 = broker_sens['brokers'][:5]

        # Get current status for each broker
        latest_date = broker_df['date'].max() if not broker_df.empty else None

        # Calculate current accumulation status
        broker_status = []
        for b in top_5:
            broker_code = b['broker_code']
            broker_data = broker_df[broker_df['broker_code'] == broker_code].sort_values('date', ascending=False)

            # Check last 5 days for streak
            last_5 = broker_data.head(5)
            streak = 0
            status = "NEUTRAL"
            total_lot = 0
            today_net = 0

            if not last_5.empty:
                today_net = last_5.iloc[0]['net_value'] if len(last_5) > 0 else 0

                for _, row in last_5.iterrows():
                    if row['net_value'] > 0:
                        streak += 1
                        total_lot += row.get('net_lot', 0)
                    else:
                        break

                if streak >= 2:
                    status = "ACCUM"
                elif today_net < -1e9:
                    status = "DIST"

            # Get avg buy for this broker
            avg_buy = 0
            if not avg_buy_df.empty:
                broker_avg = avg_buy_df[avg_buy_df['broker_code'] == broker_code]
                if not broker_avg.empty:
                    avg_buy = broker_avg.iloc[0]['avg_buy_price']

            broker_status.append({
                'broker': broker_code,
                'type': get_broker_info(broker_code)['type_name'][:6],  # Asing, BUMN/P, Lokal
                'win_rate': b['win_rate'],
                'lead_time': b['avg_lead_time'],
                'signals': b['successful_signals'],
                'status': status,
                'streak': streak,
                'today_net': today_net,
                'total_lot': total_lot,
                'avg_buy': avg_buy
            })

        # Find brokers currently accumulating
        accum_brokers = [b for b in broker_status if b['status'] == 'ACCUM']

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-crosshairs me-2"),
                html.Span("Top 5 Broker Sensitivity Pattern", className="fw-bold"),
                html.Small(" - Pola akumulasi sampai harga naik >=10%", className="text-muted ms-2")
            ]),
            dbc.CardBody([
                # Historical Pattern Table - dengan warna broker
                html.Small("Historical Performance", className="text-muted fw-bold mb-2 d-block"),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("#", className="table-header", style={"width": "40px"}),
                        html.Th("Broker", className="table-header"),
                        html.Th("Tipe", className="table-header"),
                        html.Th("Win%", className="table-header"),
                        html.Th("Lead", className="table-header"),
                        html.Th("Sigs", className="table-header"),
                        html.Th("Avg Buy", className="table-header"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(str(i+1), className="table-cell fw-bold"),
                            html.Td(colored_broker(b['broker'], with_badge=True), className="table-cell"),
                            html.Td(html.Span(b['type'], className=f"broker-{get_broker_type(b['broker']).lower()}"), className="table-cell"),
                            html.Td(f"{b['win_rate']:.0f}%", className="table-cell"),
                            html.Td(f"{b['lead_time']:.0f}d", className="table-cell"),
                            html.Td(str(b['signals']), className="table-cell"),
                            html.Td(f"Rp {b['avg_buy']:,.0f}" if b['avg_buy'] > 0 else "-", className="table-cell"),
                        ]) for i, b in enumerate(broker_status)
                    ])
                ], className="table table-sm", style={'width': '100%'}),

                html.Hr(className="my-2"),

                # Current Status - dengan warna broker
                html.Small("Current Status - Are they accumulating now?", className="text-muted fw-bold mb-2 d-block"),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Broker", className="table-header"),
                        html.Th("Tipe", className="table-header"),
                        html.Th("Status", className="table-header"),
                        html.Th("Streak", className="table-header"),
                        html.Th("Today", className="table-header"),
                        html.Th("Tot Lot", className="table-header"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(colored_broker(b['broker'], with_badge=True), className="table-cell"),
                            html.Td(html.Span(b['type'], className=f"broker-{get_broker_type(b['broker']).lower()}"), className="table-cell"),
                            html.Td('[G] ACCUM' if b['status']=='ACCUM' else '[R] DIST' if b['status']=='DIST' else '[N] NEUTRAL', className="table-cell"),
                            html.Td(f"{b['streak']}d" if b['streak'] > 0 else "-", className="table-cell"),
                            html.Td(f"{b['today_net']/1e9:+.1f}B", className="table-cell"),
                            html.Td(f"{b['total_lot']/1e6:.1f}M" if b['total_lot'] > 0 else "-", className="table-cell"),
                        ]) for b in broker_status
                    ])
                ], className="table table-sm", style={'width': '100%'}),

                # Insight box
                html.Div([
                    html.Small("[i] Insight: ", className="fw-bold"),
                    html.Small(
                        f"{len(accum_brokers)} broker sensitif sedang akumulasi: {', '.join([b['broker'] for b in accum_brokers])}"
                        if accum_brokers else "Belum ada broker sensitif yang mulai akumulasi",
                        className="text-success" if accum_brokers else "text-muted"
                    )
                ], className=f"mt-2 p-2 rounded {'alert-box-success' if accum_brokers else 'metric-box'}"),

                html.Hr(className="my-2"),

                # Penjelasan Section
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Cara Baca: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("TABEL HISTORICAL:"),
                        html.Br(),
                        html.Strong("* Win%: "), "Persentase kejadian broker ini akumulasi ^ harga naik >=10% dalam 10 hari. ",
                        html.Span("Makin tinggi makin bagus!", className="text-success"),
                        html.Br(),
                        html.Strong("* Lead: "), "Rata-rata berapa hari SEBELUM harga naik, broker ini mulai akumulasi. ",
                        "Lead 3d = beli 3 hari sebelum harga naik",
                        html.Br(),
                        html.Strong("* Sigs: "), "Jumlah sinyal berhasil (akumulasi ^ harga naik >=10%)",
                        html.Br(),
                        html.Strong("* Avg Buy: "), "Harga rata-rata pembelian broker ini (60 hari)",
                        html.Br(), html.Br(),
                        html.Strong("TABEL CURRENT STATUS:"),
                        html.Br(),
                        html.Strong("* Status: "), "ACCUM = sedang akumulasi >=2 hari, DIST = sedang distribusi, NEUTRAL = tidak ada pola",
                        html.Br(),
                        html.Strong("* Streak: "), "Berapa hari berturut-turut akumulasi",
                        html.Br(),
                        html.Strong("* Tot Lot: "), "Total lot yang dibeli selama streak",
                        html.Br(), html.Br(),
                        html.Strong("[i] Strategi: "), "Jika broker dengan Win% tinggi dan Lead Time pendek mulai akumulasi, ",
                        html.Span("pertimbangkan untuk ikut beli!", className="text-warning")
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box")
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("[S] Broker Sensitivity Pattern"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def calculate_broker_streak_history(stock_code, broker_codes, days=30):
    """
    Calculate historical streak data for selected brokers.
    Returns daily streak values (positive = accumulation, negative = distribution)
    Also includes net_lot for Stockbit-style units.
    """
    # Debug log
    print(f"[CALC_STREAK] Called with broker_codes: {broker_codes}")

    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Filter by date range
    end_date = broker_df['date'].max()
    start_date = end_date - pd.Timedelta(days=days)
    filtered_df = broker_df[broker_df['date'] >= start_date]

    if filtered_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Get all unique dates
    all_dates = sorted(filtered_df['date'].unique())

    streak_history = []

    # IMPORTANT: Only process the passed broker_codes
    for broker in broker_codes:
        b_data = filtered_df[filtered_df['broker_code'] == broker].sort_values('date')

        if b_data.empty:
            continue

        # Calculate running streak for each day
        current_accum_streak = 0
        current_dist_streak = 0

        for date in all_dates:
            day_data = b_data[b_data['date'] == date]

            if day_data.empty:
                # No activity - reset streaks
                current_accum_streak = 0
                current_dist_streak = 0
                streak_value = 0
                net_lot = 0
                net_value = 0
            else:
                net_value = day_data['net_value'].iloc[0]
                net_lot = day_data['net_lot'].iloc[0] if 'net_lot' in day_data.columns else 0

                if net_value > 0:
                    # Accumulation
                    current_accum_streak += 1
                    current_dist_streak = 0
                    streak_value = current_accum_streak
                elif net_value < 0:
                    # Distribution
                    current_dist_streak += 1
                    current_accum_streak = 0
                    streak_value = -current_dist_streak
                else:
                    # Neutral - reset
                    current_accum_streak = 0
                    current_dist_streak = 0
                    streak_value = 0

            streak_history.append({
                'date': date,
                'broker_code': broker,
                'streak': streak_value,
                'net_lot': net_lot,
                'net_value': net_value
            })

    # Calculate ALL brokers total for comparison
    all_brokers_daily = filtered_df.groupby('date').agg({
        'net_lot': 'sum',
        'net_value': 'sum'
    }).reset_index()

    return pd.DataFrame(streak_history), all_brokers_daily


def create_broker_streak_chart(stock_code='CDIA', selected_brokers=None, days=30):
    """
    Create interactive area chart showing accumulation/distribution streak history.
    Uses LOT units (like Stockbit). Shows 2 total net lines:
    - Total Net ALL brokers (tebal)
    - Total Net Selected brokers (tipis)
    """
    print(f"[CHART FUNC] create_broker_streak_chart ENTERED! stock={stock_code}, brokers={selected_brokers}", flush=True)
    try:
        # Get streak brokers if none selected
        if not selected_brokers:
            streak_brokers = get_streak_brokers(stock_code)
            selected_brokers = streak_brokers['accum'][:3] if streak_brokers['accum'] else streak_brokers['all'][:3]

        if not selected_brokers:
            return html.Div("Tidak ada broker dengan streak aktif", className="text-muted text-center py-3")

        # Calculate streak history - returns (selected_df, all_brokers_df)
        streak_df, all_brokers_df = calculate_broker_streak_history(stock_code, selected_brokers, days)

        if streak_df.empty:
            return html.Div("Tidak ada data streak", className="text-muted text-center py-3")

        # Create figure with secondary y-axis for total net
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Color palette for brokers
        colors_positive = ['rgba(0, 255, 136, 0.4)', 'rgba(0, 212, 255, 0.4)', 'rgba(255, 230, 109, 0.4)',
                          'rgba(78, 205, 196, 0.4)', 'rgba(149, 225, 211, 0.4)']
        colors_negative = ['rgba(255, 107, 107, 0.4)', 'rgba(255, 159, 64, 0.4)', 'rgba(255, 99, 132, 0.4)',
                          'rgba(255, 182, 193, 0.4)', 'rgba(255, 140, 0, 0.4)']
        line_colors = ['#00ff88', '#00d4ff', '#ffe66d', '#4ecdc4', '#95e1d3']

        # Calculate SELECTED brokers total net (LOT) - USE streak_df which is already filtered
        # This ensures we use the SAME data source as the area charts
        selected_net_df = streak_df.groupby('date').agg({
            'net_lot': 'sum'
        }).reset_index().sort_values('date')
        selected_net_df['cumulative_lot'] = selected_net_df['net_lot'].cumsum()

        # Debug: Log broker list and data verification - FLUSH to see immediately
        streak_brokers_in_df = streak_df['broker_code'].unique().tolist() if not streak_df.empty else []
        print(f"[STREAK DEBUG] === CALLBACK TRIGGERED ===", flush=True)
        print(f"[STREAK DEBUG] selected_brokers param: {selected_brokers}", flush=True)
        print(f"[STREAK DEBUG] brokers in streak_df: {streak_brokers_in_df}", flush=True)
        print(f"[STREAK DEBUG] streak_df rows: {len(streak_df)}, selected_net_df rows: {len(selected_net_df)}", flush=True)
        if not selected_net_df.empty:
            print(f"[STREAK DEBUG] selected_net_df cumulative: {selected_net_df['cumulative_lot'].iloc[-1]}", flush=True)

        # Calculate ALL brokers cumulative (LOT)
        all_brokers_df = all_brokers_df.sort_values('date')
        all_brokers_df['cumulative_lot'] = all_brokers_df['net_lot'].cumsum()

        # Add broker streak areas
        for i, broker in enumerate(selected_brokers):
            broker_data = streak_df[streak_df['broker_code'] == broker].sort_values('date')

            if broker_data.empty:
                continue

            # Separate positive and negative for different colors
            positive_streak = broker_data['streak'].apply(lambda x: max(0, x))
            negative_streak = broker_data['streak'].apply(lambda x: min(0, x))

            # Add positive area (accumulation)
            fig.add_trace(go.Scatter(
                x=broker_data['date'],
                y=positive_streak,
                name=f'{broker}',
                mode='lines',
                line=dict(width=1.5, color=line_colors[i % len(line_colors)]),
                fill='tozeroy',
                fillcolor=colors_positive[i % len(colors_positive)],
                hovertemplate=f'{broker}<br>Streak Beli: %{{y}} hari<extra></extra>'
            ), secondary_y=False)

            # Add negative area (distribution)
            fig.add_trace(go.Scatter(
                x=broker_data['date'],
                y=negative_streak,
                name=f'{broker} (Jual)',
                mode='lines',
                line=dict(width=1.5, color=colors_negative[i % len(colors_negative)].replace('0.4', '0.7')),
                fill='tozeroy',
                fillcolor=colors_negative[i % len(colors_negative)],
                showlegend=False,
                hovertemplate=f'{broker}<br>Streak Jual: %{{y}} hari<extra></extra>'
            ), secondary_y=False)

        # Add Total Net ALL brokers (THICK white line)
        fig.add_trace(go.Scatter(
            x=all_brokers_df['date'],
            y=all_brokers_df['cumulative_lot'] / 1e6,  # Convert to million lots
            name='[#] Net ALL (Juta Lot)',
            mode='lines',
            line=dict(width=4, color='white', dash='solid'),
            hovertemplate='Net ALL Broker: %{y:,.2f} Juta Lot<extra></extra>'
        ), secondary_y=True)

        # Add Total Net SELECTED brokers (THIN yellow line)
        fig.add_trace(go.Scatter(
            x=selected_net_df['date'],
            y=selected_net_df['cumulative_lot'] / 1e6,  # Convert to million lots
            name='[*] Net Selected (Juta Lot)',
            mode='lines+markers',
            line=dict(width=2, color='#ffe66d', dash='dot'),
            marker=dict(size=4, color='#ffe66d'),
            hovertemplate='Net Selected: %{y:,.2f} Juta Lot<extra></extra>'
        ), secondary_y=True)

        # Add zero line for streak axis
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, secondary_y=False)

        # Update layout
        fig.update_layout(
            template='plotly_dark',
            height=420,
            margin=dict(l=60, r=70, t=40, b=50),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=9),
                bgcolor='rgba(0,0,0,0.5)'
            ),
            hovermode='x unified',
            title=dict(
                text=f"<b>Streak History & Net Flow ({days} Hari)</b>",
                font=dict(size=12, color='#aaa'),
                x=0.5
            )
        )

        # Update LEFT Y-axis (Streak)
        fig.update_yaxes(
            title_text="<b>Streak</b><br><sup>Hari berturut-turut beli(+)/jual(-)</sup>",
            title_font=dict(size=10, color='#00ff88'),
            tickfont=dict(color='#00ff88'),
            zeroline=True,
            zerolinecolor='gray',
            zerolinewidth=1,
            gridcolor='rgba(255,255,255,0.1)',
            secondary_y=False
        )

        # Update RIGHT Y-axis (Net Lot)
        fig.update_yaxes(
            title_text="<b>Net Lot Kumulatif</b><br><sup>Dalam Juta Lot</sup>",
            title_font=dict(size=10, color='white'),
            tickfont=dict(color='white'),
            tickformat=',.1f',
            gridcolor='rgba(255,255,255,0.05)',
            secondary_y=True
        )

        # Update X-axis
        fig.update_xaxes(
            title_text="<b>Tanggal</b>",
            title_font=dict(size=10, color='#aaa'),
            tickformat="%d %b",
            gridcolor='rgba(255,255,255,0.1)'
        )

        # Calculate summary stats
        latest_selected = selected_net_df['cumulative_lot'].iloc[-1] if not selected_net_df.empty else 0
        latest_all = all_brokers_df['cumulative_lot'].iloc[-1] if not all_brokers_df.empty else 0

        selected_signal = "AKUMULASI" if latest_selected > 0 else "DISTRIBUSI" if latest_selected < 0 else "NETRAL"
        all_signal = "AKUMULASI" if latest_all > 0 else "DISTRIBUSI" if latest_all < 0 else "NETRAL"
        selected_color = "success" if latest_selected > 0 else "danger" if latest_selected < 0 else "secondary"
        all_color = "success" if latest_all > 0 else "danger" if latest_all < 0 else "secondary"

        # Debug: create timestamp to verify re-render
        import datetime as dt_debug
        debug_ts = dt_debug.datetime.now().strftime("%H:%M:%S")

        return html.Div([
            dcc.Graph(figure=fig, config={'displayModeBar': False}),
            # Debug info - shows which brokers are actually used
            html.Div([
                html.Small([
                    html.I(className="fas fa-bug me-1 text-warning"),
                    f"DEBUG [{debug_ts}]: Brokers={selected_brokers}, Net={latest_selected/1e6:+,.2f}M"
                ], className="text-warning", style={"fontSize": "9px"})
            ], className="mb-1"),
            # Summary Section
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.Small([
                            html.Strong("[#] ALL Broker: "),
                            html.Span(f"{all_signal} ", className=f"badge bg-{all_color} me-1"),
                            html.Span(f"{latest_all/1e6:+,.2f} Juta Lot", className=f"text-{all_color}")
                        ])
                    ], width=6),
                    dbc.Col([
                        html.Small([
                            html.Strong("[*] Selected ({0}): ".format(len(selected_brokers))),
                            html.Span(f"{selected_signal} ", className=f"badge bg-{selected_color} me-1"),
                            html.Span(f"{latest_selected/1e6:+,.2f} Juta Lot", className=f"text-{selected_color}")
                        ])
                    ], width=6),
                ], className="text-center")
            ], className="mt-2 p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),
            # Legend explanation
            html.Div([
                html.Small([
                    html.I(className="fas fa-info-circle me-1 text-info"),
                    html.Strong("Keterangan: "),
                    "Area warna = streak per broker (atas=beli, bawah=jual). ",
                    html.Span("Garis putih tebal", style={"color": "white", "fontWeight": "bold"}),
                    " = Net Lot semua broker. ",
                    html.Span("Garis kuning putus-putus", style={"color": "#ffe66d"}),
                    " = Net Lot broker yang dipilih."
                ], className="text-muted", style={"fontSize": "10px"})
            ], className="mt-1")
        ])

    except Exception as e:
        return html.Div(f"Error: {str(e)}", className="text-danger text-center py-3")


def get_streak_brokers(stock_code='CDIA'):
    """
    Get brokers from Accumulation Streak and Distribution Warning lists.
    Returns dict with 'accum' and 'dist' broker lists.
    """
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return {'accum': [], 'dist': [], 'all': []}

    # Calculate streaks for all brokers
    brokers = broker_df['broker_code'].unique()
    broker_streaks = []

    for broker in brokers:
        b_data = broker_df[broker_df['broker_code'] == broker].sort_values('date', ascending=False)

        accum_streak = 0
        dist_streak = 0
        total_net = b_data['net_value'].sum()

        for _, row in b_data.iterrows():
            if row['net_value'] > 0:
                if dist_streak == 0:
                    accum_streak += 1
                else:
                    break
            elif row['net_value'] < 0:
                if accum_streak == 0:
                    dist_streak += 1
                else:
                    break
            else:
                break

        broker_streaks.append({
            'broker': broker,
            'accum_streak': accum_streak,
            'dist_streak': dist_streak,
            'total_net': total_net
        })

    # Top accumulation streaks (>= 2 days)
    accum_watch = [b for b in broker_streaks if b['accum_streak'] >= 2]
    accum_watch.sort(key=lambda x: (x['accum_streak'], x['total_net']), reverse=True)
    accum_brokers = [b['broker'] for b in accum_watch[:5]]

    # Top distribution warning (>= 2 days)
    dist_watch = [b for b in broker_streaks if b['dist_streak'] >= 2]
    dist_watch.sort(key=lambda x: (x['dist_streak'], abs(x['total_net'])), reverse=True)
    dist_brokers = [b['broker'] for b in dist_watch[:5]]

    # Combined unique list
    all_brokers = list(dict.fromkeys(accum_brokers + dist_brokers))

    return {
        'accum': accum_brokers,
        'dist': dist_brokers,
        'all': all_brokers
    }


def create_broker_streak_section(stock_code='CDIA'):
    """
    Create the complete broker streak section with dropdown and chart.
    Uses brokers from Accumulation Streak and Distribution Warning lists.
    """
    try:
        # Get brokers from accumulation and distribution streak lists
        streak_brokers = get_streak_brokers(stock_code)
        accum_brokers = streak_brokers['accum']
        dist_brokers = streak_brokers['dist']
        all_brokers = streak_brokers['all']

        if not all_brokers:
            return html.Div([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-chart-area me-2 text-info"),
                        html.Strong("Streak History", className="text-info"),
                    ], className="bg-transparent border-info"),
                    dbc.CardBody([
                        html.P("Tidak ada broker dengan streak >= 2 hari", className="text-muted text-center")
                    ])
                ], className="mb-3", style={"borderColor": "var(--bs-info)"})
            ])

        # Create dropdown options with labels showing streak type
        dropdown_options = []
        for broker in accum_brokers:
            dropdown_options.append({'label': f'[G] {broker} (Akumulasi)', 'value': broker})
        for broker in dist_brokers:
            if broker not in accum_brokers:  # Avoid duplicates
                dropdown_options.append({'label': f'[R] {broker} (Distribusi)', 'value': broker})

        # Default: select all accum brokers (max 5)
        default_selected = accum_brokers[:5] if accum_brokers else all_brokers[:3]

        return dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-chart-area me-2 text-info"),
                    html.Strong("Streak History - Broker Aktif", className="text-info"),
                    html.Small(f" ({len(accum_brokers)} akumulasi, {len(dist_brokers)} distribusi)", className="text-muted ms-2")
                ], className="d-flex align-items-center")
            ], className="bg-transparent border-info"),
            dbc.CardBody([
                # Broker Selection Dropdown
                html.Div([
                    html.Small("Pilih Broker:", className="text-muted me-2"),
                    dcc.Dropdown(
                        id='streak-broker-dropdown',
                        options=dropdown_options,
                        value=default_selected,
                        multi=True,
                        placeholder="Pilih broker untuk ditampilkan...",
                        style={
                            'backgroundColor': '#1a1a2e',
                            'color': '#ffffff',
                            'border': '1px solid #3d3d5c'
                        },
                        className="dash-dropdown-dark"
                    )
                ], className="mb-3"),

                # Chart Container
                html.Div(id='streak-chart-container', children=create_broker_streak_chart(stock_code, default_selected)),

                # Info Section
                html.Div([
                    html.Hr(className="my-2", style={"opacity": "0.2"}),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1 text-info"),
                        html.Strong("Cara Membaca: "),
                        "Area hijau ke atas = streak akumulasi. ",
                        "Area merah ke bawah = streak distribusi. ",
                        html.Span("Garis putih = Total Net (semua broker yang dipilih).", className="text-white fw-bold")
                    ], className="text-muted", style={"fontSize": "10px"}),
                    html.Br(),
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        html.Strong("Insight: "),
                        "Total Net positif = lebih banyak akumulasi. Total Net negatif = lebih banyak distribusi."
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="mt-2")
            ])
        ], className="mb-3", style={"borderColor": "var(--bs-info)"})

    except Exception as e:
        return html.Div()


def create_broker_watchlist(stock_code='CDIA'):
    """
    Section 5: Broker Watchlist
    - Accumulation streak
    - Distribution warning
    - Floating loss terbesar
    """
    try:
        broker_df = get_broker_data(stock_code)
        avg_buy_df = get_broker_avg_buy(stock_code, days=60)
        price_df = get_price_data(stock_code)

        if broker_df.empty:
            return dbc.Card([
                dbc.CardHeader("[+] Broker Watchlist"),
                dbc.CardBody(html.P("No data available", className="text-muted"))
            ], className="mb-3", color="dark")

        current_price = price_df['close_price'].iloc[-1] if not price_df.empty else 0

        # Calculate streaks for all brokers
        brokers = broker_df['broker_code'].unique()
        broker_streaks = []

        for broker in brokers:
            b_data = broker_df[broker_df['broker_code'] == broker].sort_values('date', ascending=False)

            # Calculate accumulation streak
            accum_streak = 0
            dist_streak = 0
            total_net = b_data['net_value'].sum()

            for _, row in b_data.iterrows():
                if row['net_value'] > 0:
                    if dist_streak == 0:
                        accum_streak += 1
                    else:
                        break
                elif row['net_value'] < 0:
                    if accum_streak == 0:
                        dist_streak += 1
                    else:
                        break
                else:
                    break

            # Get avg buy
            avg_buy = 0
            floating_pct = 0
            if not avg_buy_df.empty and current_price > 0:
                broker_avg = avg_buy_df[avg_buy_df['broker_code'] == broker]
                if not broker_avg.empty:
                    avg_buy = broker_avg.iloc[0]['avg_buy_price']
                    if avg_buy > 0:
                        floating_pct = (current_price - avg_buy) / avg_buy * 100

            broker_type = get_broker_info(broker)['type_name']

            broker_streaks.append({
                'broker': broker,
                'type': broker_type,
                'accum_streak': accum_streak,
                'dist_streak': dist_streak,
                'total_net': total_net,
                'avg_buy': avg_buy,
                'floating_pct': floating_pct
            })

        # Top accumulation streaks (>= 2 days)
        accum_watch = [b for b in broker_streaks if b['accum_streak'] >= 2]
        accum_watch.sort(key=lambda x: (x['accum_streak'], x['total_net']), reverse=True)
        accum_watch = accum_watch[:5]

        # Top distribution warning (>= 2 days)
        dist_watch = [b for b in broker_streaks if b['dist_streak'] >= 2]
        dist_watch.sort(key=lambda x: (x['dist_streak'], abs(x['total_net'])), reverse=True)
        dist_watch = dist_watch[:5]

        # Biggest floating loss
        float_loss = [b for b in broker_streaks if b['floating_pct'] < -5 and b['avg_buy'] > 0]
        float_loss.sort(key=lambda x: x['floating_pct'])
        float_loss = float_loss[:5]

        # Build list items with colored broker codes - better spacing for desktop
        accum_items = [html.Div([
            html.Span([
                colored_broker(b['broker'], with_badge=True),
            ], style={"display": "inline-block", "minWidth": "55px"}),
            html.Span(f"{b['accum_streak']}d", className="badge bg-success", style={"marginLeft": "8px", "marginRight": "8px"}),
            html.Span(f"{b['total_net']/1e9:+.1f}B", className="text-muted", style={"fontSize": "13px"})
        ], className="d-flex align-items-center mb-1", style={"fontSize": "13px"}) for b in accum_watch] if accum_watch else [html.Small("No streak", className="text-muted")]

        dist_items = [html.Div([
            html.Span([
                colored_broker(b['broker'], with_badge=True),
            ], style={"display": "inline-block", "minWidth": "55px"}),
            html.Span(f"{b['dist_streak']}d", className="badge bg-danger", style={"marginLeft": "8px", "marginRight": "8px"}),
            html.Span(f"{b['total_net']/1e9:.1f}B", className="text-muted", style={"fontSize": "13px"})
        ], className="d-flex align-items-center mb-1", style={"fontSize": "13px"}) for b in dist_watch] if dist_watch else [html.Small("No warning", className="text-muted")]

        float_items = [html.Div([
            html.Span([
                colored_broker(b['broker'], with_badge=True),
            ], style={"display": "inline-block", "minWidth": "55px"}),
            html.Span(f"{b['floating_pct']:.1f}%", className="text-danger fw-bold", style={"marginLeft": "8px", "marginRight": "5px", "fontSize": "13px"}),
            html.Span(f"@{b['avg_buy']:,.0f}", className="text-muted", style={"fontSize": "12px"})
        ], className="d-flex align-items-center mb-1", style={"fontSize": "13px"}) for b in float_loss] if float_loss else [html.Small("No significant loss", className="text-muted")]

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-eye me-2"),
                html.Span("Broker Watchlist", className="fw-bold")
            ]),
            dbc.CardBody([
                dbc.Row([
                    # Accumulation Streak
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span("[FIRE]", className="me-2"),
                                html.Span("Accumulation Streak", className="text-success fw-bold")
                            ], className="mb-2"),
                            html.Small("Broker yang membeli berturut-turut selama beberapa hari.",
                                      className="text-muted d-block mb-2", style={"fontSize": "10px"}),
                            *accum_items,
                            html.Small([
                                html.I(className="fas fa-lightbulb me-1"),
                                "Streak panjang + net besar = conviction kuat. Ikuti broker, bukan candle [?]"
                            ], className="text-success fst-italic d-block mt-2", style={"fontSize": "9px"})
                        ], className="p-2 rounded h-100 alert-box-success")
                    ], xs=12, md=4, className="mb-2 mb-md-0"),

                    # Distribution Warning
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span("[!]", className="me-2"),
                                html.Span("Distribution Warning", className="text-danger fw-bold")
                            ], className="mb-2"),
                            html.Small("Broker yang jual berturut-turut, indikasi pelepasan posisi.",
                                      className="text-muted d-block mb-2", style={"fontSize": "10px"}),
                            *dist_items,
                            html.Small([
                                html.I(className="fas fa-exclamation-circle me-1"),
                                "Semakin panjang streak jual, semakin besar risiko supply lanjutan."
                            ], className="text-danger fst-italic d-block mt-2", style={"fontSize": "9px"})
                        ], className="p-2 rounded h-100 alert-box-danger")
                    ], xs=12, md=4, className="mb-2 mb-md-0"),

                    # Floating Loss
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span("[#]", className="me-2"),
                                html.Span("Floating Loss", className="text-warning fw-bold")
                            ], className="mb-2"),
                            html.Small("Broker dengan avg buy lebih tinggi dari harga sekarang.",
                                      className="text-muted d-block mb-2", style={"fontSize": "10px"}),
                            *float_items,
                            html.Small([
                                html.I(className="fas fa-info-circle me-1"),
                                "Area avg buy mereka sering jadi zona reaksi harga."
                            ], className="text-warning fst-italic d-block mt-2", style={"fontSize": "9px"})
                        ], className="p-2 rounded h-100 alert-box-warning")
                    ], xs=12, md=4),
                ]),

                html.Hr(className="my-3"),

                # Why This Matters Section
                html.Div([
                    html.Div([
                        html.I(className="fas fa-question-circle me-2 text-info"),
                        html.Strong("Cara Membaca Broker Movement", className="text-info")
                    ], className="mb-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.Strong("New Accumulation ^ ", className="text-success"),
                                "Awal niat beli"
                            ], className="d-block mb-1"),
                            html.Small([
                                html.Strong("Distribution Warning ^ ", className="text-danger"),
                                "Pelepasan posisi"
                            ], className="d-block mb-1"),
                        ], width=6),
                        dbc.Col([
                            html.Small([
                                html.Strong("Accumulation Streak ^ ", className="text-success"),
                                "Keyakinan broker"
                            ], className="d-block mb-1"),
                            html.Small([
                                html.Strong("Floating Loss ^ ", className="text-warning"),
                                "Area potensial support/tekanan"
                            ], className="d-block mb-1"),
                        ], width=6),
                    ]),
                    html.Div([
                        html.Small([
                            html.I(className="fas fa-quote-left me-1 text-muted"),
                            html.Span("Harga bisa bohong. Broker jarang.", className="fst-italic text-muted")
                        ], style={"fontSize": "11px"})
                    ], className="mt-2 text-center")
                ], className="p-2 rounded", style={"backgroundColor": "rgba(23, 162, 184, 0.1)"}),

                html.Hr(className="my-3"),

                # Strategi Praktis Section
                html.Div([
                    html.Div([
                        html.I(className="fas fa-bullseye me-2 text-warning"),
                        html.Strong("Strategi Praktis untuk Trader", className="text-warning")
                    ], className="mb-2"),
                    html.Ul([
                        html.Li(html.Small("Ikuti Accumulation Streak terpanjang, bukan yang cuma 1 hari.")),
                        html.Li(html.Small([
                            "Waspadai saham jika: ",
                            html.Span("banyak broker masuk Distribution Warning ", className="text-danger"),
                            "atau ",
                            html.Span("broker besar muncul di Floating Loss", className="text-warning")
                        ])),
                        html.Li(html.Small("Gunakan avg buy broker sebagai support/resistance dinamis")),
                        html.Li(html.Small([
                            html.Strong("Jangan melawan: "),
                            "distribusi beruntun + volume naik = no hero trade"
                        ])),
                    ], className="mb-2 ps-3", style={"fontSize": "11px"}),
                    html.Div([
                        html.Small([
                            html.I(className="fas fa-shield-alt me-1"),
                            "Trader ritel selamat bukan karena cepat, tapi karena tahu kapan tidak ikut."
                        ], className="text-muted fst-italic", style={"fontSize": "10px"})
                    ], className="text-center")
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255, 193, 7, 0.1)"})
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("[+] Broker Watchlist"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


# ============================================================
# PAGE: COMPANY PROFILE
# ============================================================

def get_stock_profile(stock_code: str) -> dict:
    """Get stock profile from database"""
    import json
    query = """
        SELECT * FROM stock_profile WHERE stock_code = %s
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    if result and len(result) > 0:
        row = result[0]
        # Parse directors/commissioners - could be JSON, semicolon-separated, or already parsed
        def parse_people_list(val):
            if not val:
                return []
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                # Try JSON first
                try:
                    return json.loads(val)
                except:
                    # Split by semicolon
                    return [x.strip() for x in val.split(';') if x.strip()]
            return []

        directors = parse_people_list(row.get('directors'))
        commissioners = parse_people_list(row.get('commissioners'))
        shareholder_history = row.get('shareholder_history')
        if isinstance(shareholder_history, str):
            try:
                shareholder_history = json.loads(shareholder_history) if shareholder_history else []
            except:
                shareholder_history = []
        elif not shareholder_history:
            shareholder_history = []

        return {
            'stock_code': row.get('stock_code'),
            'company_name': row.get('company_name'),
            'listing_board': row.get('listing_board'),
            'sector': row.get('sector'),
            'subsector': row.get('subsector'),
            'industry': row.get('industry'),
            'business_activity': row.get('business_activity'),
            'listing_date': row.get('listing_date'),
            'effective_date': row.get('effective_date'),
            'nominal_value': float(row.get('nominal_value') or 0) if row.get('nominal_value') else None,
            'ipo_price': float(row.get('ipo_price') or 0) if row.get('ipo_price') else None,
            'ipo_shares': row.get('ipo_shares'),
            'ipo_amount': float(row.get('ipo_amount') or 0) if row.get('ipo_amount') else None,
            'underwriter': row.get('underwriter'),
            'share_registrar': row.get('share_registrar'),
            'company_background': row.get('company_background'),
            'major_shareholder': row.get('major_shareholder'),
            'major_shareholder_pct': float(row.get('major_shareholder_pct') or 0),
            'public_pct': float(row.get('public_pct') or 0),
            'total_shares': row.get('total_shares', 0),
            'president_director': row.get('president_director'),
            'president_commissioner': row.get('president_commissioner'),
            'directors': directors,
            'commissioners': commissioners,
            'shareholder_history': shareholder_history,
        }
    return {}


# ============================================================
# PAGE: ACCUMULATION (New Sub-menu from Analysis)
# ============================================================

def get_market_snapshot_data(stock_code: str, target_date: str = None) -> dict:
    """
    Get Market Snapshot data for a specific date.
    Returns OHLC, Avg, Value, Volume, Freq, Foreign flow data.
    """
    try:
        # Query to get all market data including foreign buy/sell
        query = """
            SELECT date, open_price, high_price, low_price, close_price, avg_price,
                   volume, value, frequency, foreign_buy, foreign_sell, net_foreign,
                   change_value, change_percent
            FROM stock_daily
            WHERE stock_code = %s
            ORDER BY date DESC
            LIMIT 30
        """
        results = execute_query(query, (stock_code,))

        if not results:
            return None

        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])

        # If target_date specified, find that row
        if target_date:
            target = pd.to_datetime(target_date)
            row = df[df['date'] == target]
            if row.empty:
                row = df.iloc[[0]]  # Use latest if not found
            else:
                row = row.iloc[[0]]
        else:
            row = df.iloc[[0]]  # Latest data

        latest = row.iloc[0]

        # Calculate averages for comparison (20 day)
        avg_value = df['value'].mean() if len(df) > 1 else latest['value']
        avg_volume = df['volume'].mean() if len(df) > 1 else latest['volume']
        avg_freq = df['frequency'].mean() if 'frequency' in df.columns and len(df) > 1 else 0

        # Get values
        close_price = float(latest['close_price']) if pd.notna(latest['close_price']) else 0
        open_price = float(latest['open_price']) if pd.notna(latest['open_price']) else 0
        change_value = float(latest['change_value']) if pd.notna(latest.get('change_value')) else 0
        change_percent = float(latest['change_percent']) if pd.notna(latest.get('change_percent')) else 0

        # Calculate change_percent if it's 0 but change_value exists
        if change_percent == 0 and change_value != 0:
            # Calculate from previous close (close - change_value)
            prev_close = close_price - change_value
            if prev_close != 0:
                change_percent = (change_value / prev_close) * 100
        # If still 0 and we have open price, calculate from open
        elif change_percent == 0 and open_price != 0 and close_price != open_price:
            change_value = close_price - open_price
            change_percent = (change_value / open_price) * 100

        return {
            'date': latest['date'],
            'open': open_price,
            'high': float(latest['high_price']) if pd.notna(latest['high_price']) else 0,
            'low': float(latest['low_price']) if pd.notna(latest['low_price']) else 0,
            'close': close_price,
            'avg': float(latest['avg_price']) if pd.notna(latest.get('avg_price')) else 0,
            'change': change_percent,
            'change_value': change_value,
            'volume': int(latest['volume']) if pd.notna(latest['volume']) else 0,
            'value': float(latest['value']) if pd.notna(latest['value']) else 0,
            'frequency': int(latest['frequency']) if pd.notna(latest.get('frequency')) else 0,
            'foreign_buy': float(latest['foreign_buy']) if pd.notna(latest.get('foreign_buy')) else 0,
            'foreign_sell': float(latest['foreign_sell']) if pd.notna(latest.get('foreign_sell')) else 0,
            'net_foreign': float(latest['net_foreign']) if pd.notna(latest.get('net_foreign')) else 0,
            'avg_value_20d': avg_value,
            'avg_volume_20d': avg_volume,
            'avg_freq_20d': avg_freq,
            'available_dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            # Previous day data for comparison
            'prev_day': {
                'date': df.iloc[1]['date'] if len(df) > 1 else None,
                'close': float(df.iloc[1]['close_price']) if len(df) > 1 and pd.notna(df.iloc[1]['close_price']) else 0,
                'value': float(df.iloc[1]['value']) if len(df) > 1 and pd.notna(df.iloc[1]['value']) else 0,
                'volume': int(df.iloc[1]['volume']) if len(df) > 1 and pd.notna(df.iloc[1]['volume']) else 0,
                'net_foreign': float(df.iloc[1]['net_foreign']) if len(df) > 1 and pd.notna(df.iloc[1].get('net_foreign')) else 0,
            } if len(df) > 1 else None
        }
    except Exception as e:
        print(f"Error getting market snapshot: {e}")
        return None


def generate_market_narrative(data: dict) -> dict:
    """
    Generate 3 narrative sentences for Market Snapshot based on POINT 1 methodology.
    Returns dict with 3 narratives: closing, weight, foreign
    """
    if not data:
        return {
            'closing': 'Data tidak tersedia',
            'weight': 'Data tidak tersedia',
            'foreign': 'Data tidak tersedia'
        }

    # 1. Arah & Kualitas Penutupan
    change = data.get('change', 0)
    close = data.get('close', 0)
    high = data.get('high', 0)
    low = data.get('low', 0)
    avg = data.get('avg', 0)
    open_price = data.get('open', 0)

    # Determine direction
    if change > 0.5:
        direction = "naik"
        direction_desc = "mengangkat"
    elif change < -0.5:
        direction = "turun"
        direction_desc = "menggulung"
    else:
        direction = "datar"
        direction_desc = "mengunci"

    # Determine closing quality based on OHLC structure
    price_range = high - low if high > low else 1
    close_position = (close - low) / price_range if price_range > 0 else 0.5

    if close_position >= 0.7:
        ohlc_quality = "pembeli menang sampai penutupan"
    elif close_position <= 0.3:
        ohlc_quality = "penjual menang sampai penutupan"
    else:
        ohlc_quality = "tarik-menarik, belum ada keputusan kuat"

    # Close vs Avg quality
    if avg > 0:
        if close > avg:
            avg_quality = "kuat (ditutup di atas rata-rata transaksi)"
        else:
            avg_quality = "lemah (ditutup di bawah rata-rata transaksi)"
    else:
        avg_quality = "tidak dapat dinilai"

    closing_narrative = f"Hari ini ditutup {direction} ({change:+.2f}%), dan penutupan {avg_quality}. {ohlc_quality.capitalize()}."

    # 2. Bobot Pergerakan
    value = data.get('value', 0)
    volume = data.get('volume', 0)
    freq = data.get('frequency', 0)
    avg_value = data.get('avg_value_20d', value)
    avg_volume = data.get('avg_volume_20d', volume)
    avg_freq = data.get('avg_freq_20d', freq)

    # Determine activity level
    value_ratio = value / avg_value if avg_value > 0 else 1
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1

    if value_ratio > 1.3 or volume_ratio > 1.3:
        activity_level = "ramai"
        weight = "berbobot"
    elif value_ratio < 0.7 or volume_ratio < 0.7:
        activity_level = "sepi"
        weight = "ringan"
    else:
        activity_level = "normal"
        weight = "standar"

    # Combined interpretation
    if direction == "naik" and activity_level == "sepi":
        weight_interpretation = "naik ringan, rawan ditarik balik"
    elif direction == "turun" and activity_level == "sepi":
        weight_interpretation = "turun ringan, bisa cuma lemah sesaat"
    elif direction == "naik" and activity_level == "ramai":
        weight_interpretation = "naik berbobot, pergerakan valid"
    elif direction == "turun" and activity_level == "ramai":
        weight_interpretation = "jualnya serius, waspada"
    else:
        weight_interpretation = f"pergerakan {weight}"

    weight_narrative = f"Aktivitas pasar {activity_level} (Value {value_ratio:.1f}x avg), jadi {weight_interpretation}."

    # 3. Konteks Asing
    net_foreign = data.get('net_foreign', 0)
    foreign_buy = data.get('foreign_buy', 0)
    foreign_sell = data.get('foreign_sell', 0)

    if net_foreign > 0:
        foreign_action = "net buy"
        foreign_stance = "mendukung"
    elif net_foreign < 0:
        foreign_action = "net sell"
        foreign_stance = "menekan"
    else:
        foreign_action = "netral"
        foreign_stance = "tidak aktif"

    # Check if price follows or against foreign
    if (net_foreign > 0 and change > 0) or (net_foreign < 0 and change < 0):
        price_reaction = "menurut"
    elif (net_foreign > 0 and change <= 0) or (net_foreign < 0 and change >= 0):
        price_reaction = "melawan"
    else:
        price_reaction = "netral terhadap"

    # Anomaly detection
    anomaly = ""
    if net_foreign < 0 and change > 0:
        anomaly = " Ada penahan - asing jual tapi harga tidak jatuh."
    elif net_foreign > 0 and change < 0:
        anomaly = " Ada pelepas - asing beli tapi harga tidak kuat."

    foreign_narrative = f"Asing {foreign_action} (Rp {net_foreign/1e9:.2f}B), dan harga {price_reaction} arus asing.{anomaly}"

    return {
        'closing': closing_narrative,
        'weight': weight_narrative,
        'foreign': foreign_narrative,
        'direction': direction,
        'activity': activity_level,
        'foreign_stance': foreign_stance
    }


def generate_comparison_narrative(data: dict) -> str:
    """
    Generate narrative comparing today with previous day.
    Returns a single sentence comparison.
    """
    if not data or not data.get('prev_day'):
        return "Data hari sebelumnya tidak tersedia untuk perbandingan."

    prev = data['prev_day']

    # Compare activity
    today_value = data.get('value', 0)
    prev_value = prev.get('value', 0)

    if prev_value > 0:
        value_change = ((today_value - prev_value) / prev_value) * 100
        if value_change > 20:
            activity_comp = "aktivitas MENINGKAT SIGNIFIKAN"
        elif value_change > 5:
            activity_comp = "aktivitas meningkat"
        elif value_change < -20:
            activity_comp = "aktivitas MENURUN SIGNIFIKAN"
        elif value_change < -5:
            activity_comp = "aktivitas menurun"
        else:
            activity_comp = "aktivitas relatif sama"
    else:
        activity_comp = "aktivitas tidak dapat dibandingkan"

    # Compare foreign
    today_foreign = data.get('net_foreign', 0)
    prev_foreign = prev.get('net_foreign', 0)

    if today_foreign > 0 and prev_foreign > 0:
        foreign_comp = "asing tetap net buy"
    elif today_foreign < 0 and prev_foreign < 0:
        foreign_comp = "asing tetap net sell"
    elif today_foreign > 0 and prev_foreign <= 0:
        foreign_comp = "asing BERBALIK menjadi net buy"
    elif today_foreign < 0 and prev_foreign >= 0:
        foreign_comp = "asing BERBALIK menjadi net sell"
    else:
        foreign_comp = "asing relatif netral"

    # Compare price direction
    today_change = data.get('change', 0)
    prev_close = prev.get('close', 0)
    today_close = data.get('close', 0)

    if today_close > prev_close:
        price_comp = "harga melanjutkan kenaikan" if today_change > 0 else "harga rebound dari hari sebelumnya"
    elif today_close < prev_close:
        price_comp = "harga melanjutkan penurunan" if today_change < 0 else "harga terkoreksi dari hari sebelumnya"
    else:
        price_comp = "harga stagnan"

    return f"Dibanding hari sebelumnya: {activity_comp}, {foreign_comp}, dan {price_comp}."


def determine_day_significance(data: dict) -> dict:
    """
    Determine if the day is significant enough for deeper analysis.
    Returns conclusion about day type and recommendation.
    """
    if not data:
        return {
            'significant': False,
            'day_type': 'TIDAK DIKETAHUI',
            'recommendation': 'Data tidak tersedia',
            'reasons': [],
            'color': 'secondary'
        }

    # Get key metrics
    change = abs(data.get('change', 0))
    value = data.get('value', 0)
    avg_value = data.get('avg_value_20d', value)
    volume = data.get('volume', 0)
    avg_volume = data.get('avg_volume_20d', volume)
    close = data.get('close', 0)
    high = data.get('high', 0)
    low = data.get('low', 0)
    avg = data.get('avg', 0)
    net_foreign = data.get('net_foreign', 0)

    # Calculate ratios
    value_ratio = value / avg_value if avg_value > 0 else 1
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1
    price_range = high - low if high > low else 1
    close_position = (close - low) / price_range if price_range > 0 else 0.5

    # Scoring system for significance
    significance_score = 0
    reasons = []

    # 1. Activity level (0-30 points)
    if value_ratio > 1.5:
        significance_score += 30
        reasons.append("Aktivitas SANGAT RAMAI (>1.5x avg)")
    elif value_ratio > 1.2:
        significance_score += 20
        reasons.append("Aktivitas RAMAI (>1.2x avg)")
    elif value_ratio > 0.8:
        significance_score += 10
        reasons.append("Aktivitas NORMAL")
    else:
        reasons.append("Aktivitas SEPI (<0.8x avg)")

    # 2. Price movement (0-25 points)
    if change > 3:
        significance_score += 25
        reasons.append(f"Pergerakan BESAR ({change:.1f}%)")
    elif change > 1.5:
        significance_score += 15
        reasons.append(f"Pergerakan SEDANG ({change:.1f}%)")
    elif change > 0.5:
        significance_score += 5
        reasons.append(f"Pergerakan KECIL ({change:.1f}%)")
    else:
        reasons.append(f"Pergerakan DATAR ({change:.1f}%)")

    # 3. Close position clarity (0-20 points)
    if close_position > 0.8 or close_position < 0.2:
        significance_score += 20
        reasons.append("Keputusan JELAS (close di ekstrem)")
    elif close_position > 0.6 or close_position < 0.4:
        significance_score += 10
        reasons.append("Keputusan CUKUP JELAS")
    else:
        reasons.append("Keputusan BELUM JELAS (close di tengah)")

    # 4. Foreign participation (0-15 points)
    foreign_ratio = abs(net_foreign) / value if value > 0 else 0
    if foreign_ratio > 0.1:
        significance_score += 15
        reasons.append("Partisipasi asing SIGNIFIKAN")
    elif foreign_ratio > 0.05:
        significance_score += 8
        reasons.append("Partisipasi asing MODERAT")
    else:
        reasons.append("Partisipasi asing MINIMAL")

    # 5. Close vs Avg alignment (0-10 points)
    if avg > 0:
        close_vs_avg = (close - avg) / avg * 100
        if abs(close_vs_avg) > 1:
            significance_score += 10
            reasons.append(f"Kualitas penutupan JELAS ({close_vs_avg:+.1f}% vs avg)")
        else:
            significance_score += 3
            reasons.append("Kualitas penutupan NETRAL")

    # Determine day type based on OHLC structure (with context warning)
    price_change = data.get('change', 0)

    if close_position > 0.7 and price_change > 0:
        day_type = "HARI DIDORONG"
        day_desc = "Harga bergerak naik dan penutupan nyaman di atas"
        day_context = "Perlu dibandingkan dengan hari sebelumnya untuk konfirmasi tren"
    elif close_position < 0.3 and price_change < 0:
        day_type = "HARI DIBUANG"
        day_desc = "Harga jatuh dan penutupan lemah di bawah"
        day_context = "Tanpa konteks tren - bisa awal downtrend atau akhir koreksi"
    elif 0.4 <= close_position <= 0.6:
        day_type = "HARI DITAHAN"
        day_desc = "Harga dicoba digeser tapi balik lagi ke tengah"
        day_context = "Pasar belum memutuskan arah - perlu observasi lanjutan"
    elif close_position > 0.7 and price_change <= 0:
        day_type = "HARI RECOVERY"
        day_desc = "Sempat turun tapi ditutup kuat di atas"
        day_context = "Ada penahan di bawah - perlu konfirmasi besok"
    elif close_position < 0.3 and price_change >= 0:
        day_type = "HARI REJECTION"
        day_desc = "Sempat naik tapi ditutup lemah di bawah"
        day_context = "Ada tekanan di atas - perlu konfirmasi besok"
    else:
        day_type = "HARI TRANSISI"
        day_desc = "Pergerakan belum menunjukkan arah jelas"
        day_context = "Tidak ada sinyal kuat - lebih baik observasi"

    # Determine significance level (INTENSITAS HARI, bukan keyakinan analisa)
    if significance_score >= 70:
        significant = True
        level = "INTENSITAS TINGGI"
        recommendation = "LANJUT ANALISIS - Hari ini layak dianalisis lebih dalam. Lanjutkan ke Point 2-6."
        color = "success"
        icon = "fa-fire"
    elif significance_score >= 50:
        significant = True
        level = "INTENSITAS SEDANG"
        recommendation = "PERTIMBANGKAN - Ada beberapa aktivitas menarik. Bisa lanjut analisis dengan hati-hati."
        color = "info"
        icon = "fa-thermometer-half"
    elif significance_score >= 30:
        significant = False
        level = "INTENSITAS RENDAH"
        recommendation = "CATAT SAJA - Hari ini cukup dicatat. Tidak perlu diulik terlalu dalam."
        color = "warning"
        icon = "fa-thermometer-quarter"
    else:
        significant = False
        level = "INTENSITAS MINIMAL"
        recommendation = "SKIP - Hari ini sepi dan tidak berbobot. Hemat energi untuk hari lain."
        color = "danger"
        icon = "fa-thermometer-empty"

    # Decision type (dengan klarifikasi: harian, bukan tren)
    if significant and (close_position > 0.7 or close_position < 0.3):
        decision_type = "HARI KEPUTUSAN"
        decision_desc = "Keputusan arah HARIAN, bukan konfirmasi tren"
    else:
        decision_type = "HARI TUNGGU"
        decision_desc = "Belum ada kejelasan, lebih baik observasi"

    return {
        'significant': significant,
        'significance_score': significance_score,
        'significance_level': level,
        'day_type': day_type,
        'day_desc': day_desc,
        'day_context': day_context,
        'decision_type': decision_type,
        'decision_desc': decision_desc,
        'recommendation': recommendation,
        'reasons': reasons,
        'color': color,
        'icon': icon
    }


def analyze_price_movement_anatomy(data: dict) -> dict:
    """
    POINT 2 - Price Movement Anatomy
    Analyze HOW price moved, not WHY.
    Returns narrative analysis of intraday price behavior.
    """
    if not data:
        return {
            'flow': {'type': 'UNKNOWN', 'narrative': 'Data tidak tersedia'},
            'range_structure': {'type': 'UNKNOWN', 'narrative': 'Data tidak tersedia'},
            'close_location': {'type': 'UNKNOWN', 'narrative': 'Data tidak tersedia'},
            'rhythm': {'type': 'UNKNOWN', 'narrative': 'Data tidak tersedia'},
            'avg_relation': {'type': 'UNKNOWN', 'narrative': 'Data tidak tersedia'},
            'full_narrative': 'Data tidak tersedia untuk analisis.',
            'summary_questions': {}
        }

    open_price = data.get('open', 0)
    high = data.get('high', 0)
    low = data.get('low', 0)
    close = data.get('close', 0)
    avg = data.get('avg', 0)
    change = data.get('change', 0)

    # Calculate key metrics
    price_range = high - low if high > low else 1
    close_position = (close - low) / price_range if price_range > 0 else 0.5
    open_position = (open_price - low) / price_range if price_range > 0 else 0.5
    range_percent = (price_range / low * 100) if low > 0 else 0

    # ========== 2.1 ARAH GERAK INTRAHARI (FLOW) ==========
    if open_position > 0.7 and close_position < 0.3:
        flow_type = "DITEKAN"
        flow_narrative = "Harga dibuka tinggi lalu ditekan turun hingga penutupan"
        flow_icon = "fa-arrow-down"
        flow_color = "danger"
    elif open_position < 0.3 and close_position > 0.7:
        flow_type = "DIPULIHKAN"
        flow_narrative = "Harga dibuka rendah lalu dipulihkan hingga penutupan kuat"
        flow_icon = "fa-arrow-up"
        flow_color = "success"
    elif open_position > 0.6 and close_position > 0.6:
        flow_type = "DIPERTAHANKAN ATAS"
        flow_narrative = "Harga dibuka dan ditutup di area atas, tekanan jual tidak efektif"
        flow_icon = "fa-shield-alt"
        flow_color = "success"
    elif open_position < 0.4 and close_position < 0.4:
        flow_type = "DIPERTAHANKAN BAWAH"
        flow_narrative = "Harga dibuka dan ditutup di area bawah, tekanan beli tidak efektif"
        flow_icon = "fa-shield-alt"
        flow_color = "danger"
    elif open_position > 0.5 and close_position < 0.5:
        flow_type = "MELEMAH"
        flow_narrative = "Harga dibuka di atas tengah lalu turun ke bawah tengah"
        flow_icon = "fa-angle-double-down"
        flow_color = "warning"
    elif open_position < 0.5 and close_position > 0.5:
        flow_type = "MENGUAT"
        flow_narrative = "Harga dibuka di bawah tengah lalu naik ke atas tengah"
        flow_icon = "fa-angle-double-up"
        flow_color = "info"
    else:
        flow_type = "NETRAL"
        flow_narrative = "Harga dibuka dan ditutup di area yang relatif sama"
        flow_icon = "fa-minus"
        flow_color = "secondary"

    flow = {
        'type': flow_type,
        'narrative': flow_narrative,
        'icon': flow_icon,
        'color': flow_color,
        'open_pos': f"{open_position*100:.0f}%",
        'close_pos': f"{close_position*100:.0f}%"
    }

    # ========== 2.2 STRUKTUR RANGE ==========
    # Get average range from previous days if available
    avg_value = data.get('avg_value_20d', data.get('value', 0))
    today_value = data.get('value', 0)
    value_ratio = today_value / avg_value if avg_value > 0 else 1

    # Determine range structure
    is_wide_range = range_percent > 3  # > 3% range considered wide
    is_directional = abs(close_position - 0.5) > 0.3  # Close far from middle

    if is_wide_range and not is_directional:
        range_type = "LEBAR & KASAR"
        range_narrative = "Range lebar dengan penutupan tidak tegas - harga dilepas, kontrol rendah"
        range_icon = "fa-expand-arrows-alt"
        range_color = "warning"
        range_control = "RENDAH"
    elif is_wide_range and is_directional:
        range_type = "LEBAR & TERARAH"
        range_narrative = "Range lebar dengan arah jelas - dorongan satu arah yang kuat"
        range_icon = "fa-arrows-alt-v"
        range_color = "info"
        range_control = "SEDANG"
    elif not is_wide_range and is_directional:
        range_type = "SEMPIT & TERARAH"
        range_narrative = "Range sempit dengan arah jelas - pergerakan terkontrol dan efisien"
        range_icon = "fa-compress-arrows-alt"
        range_color = "success"
        range_control = "TINGGI"
    elif not is_wide_range and not is_directional:
        range_type = "SEMPIT & RAPI"
        range_narrative = "Range sempit dengan penutupan netral - harga dikurung, kontrol tinggi"
        range_icon = "fa-lock"
        range_color = "secondary"
        range_control = "TINGGI"
    else:
        range_type = "NORMAL"
        range_narrative = "Range dan struktur dalam batas normal"
        range_icon = "fa-equals"
        range_color = "secondary"
        range_control = "SEDANG"

    range_structure = {
        'type': range_type,
        'narrative': range_narrative,
        'icon': range_icon,
        'color': range_color,
        'control': range_control,
        'range_percent': f"{range_percent:.2f}%",
        'range_value': f"{price_range:,.0f}"
    }

    # ========== 2.3 LOKASI PENUTUPAN ==========
    if close_position >= 0.8:
        close_type = "SANGAT DEKAT HIGH"
        close_narrative = "Pembeli dominan penuh sampai akhir - penutupan sangat kuat"
        close_icon = "fa-arrow-circle-up"
        close_color = "success"
        winner = "PEMBELI"
    elif close_position >= 0.6:
        close_type = "DEKAT HIGH"
        close_narrative = "Pembeli dominan sampai akhir - penutupan cukup kuat"
        close_icon = "fa-arrow-up"
        close_color = "success"
        winner = "PEMBELI"
    elif close_position <= 0.2:
        close_type = "SANGAT DEKAT LOW"
        close_narrative = "Penjual dominan penuh sampai akhir - penutupan sangat lemah"
        close_icon = "fa-arrow-circle-down"
        close_color = "danger"
        winner = "PENJUAL"
    elif close_position <= 0.4:
        close_type = "DEKAT LOW"
        close_narrative = "Penjual dominan sampai akhir - penutupan cukup lemah"
        close_icon = "fa-arrow-down"
        close_color = "danger"
        winner = "PENJUAL"
    else:
        close_type = "DI TENGAH"
        close_narrative = "Tarik-menarik belum selesai - tidak ada pemenang jelas hari ini"
        close_icon = "fa-arrows-alt-h"
        close_color = "warning"
        winner = "SERI"

    close_location = {
        'type': close_type,
        'narrative': close_narrative,
        'icon': close_icon,
        'color': close_color,
        'winner': winner,
        'position_pct': f"{close_position*100:.0f}%"
    }

    # ========== 2.4 RITME PERGERAKAN ==========
    # Sesuai spesifikasi: Volume, Freq, Range, Change
    # Volume & Freq = intensitas partisipasi
    # Range = lebar pergerakan
    # Change = arah dan magnitude

    # Get volume and frequency data
    today_volume = data.get('volume', 0)
    today_freq = data.get('frequency', 0)
    avg_volume_20d = data.get('avg_volume_20d', today_volume)
    avg_freq_20d = data.get('avg_freq_20d', today_freq)

    # Calculate ratios
    volume_ratio = today_volume / avg_volume_20d if avg_volume_20d > 0 else 1
    freq_ratio = today_freq / avg_freq_20d if avg_freq_20d > 0 else 1

    # Determine activity level (gabungan volume + freq)
    is_high_volume = volume_ratio > 1.3
    is_low_volume = volume_ratio < 0.7
    is_high_freq = freq_ratio > 1.3
    is_low_freq = freq_ratio < 0.7

    # Combined activity score
    is_ramai = is_high_volume and is_high_freq  # Keduanya tinggi = ramai
    is_sepi = is_low_volume and is_low_freq      # Keduanya rendah = sepi
    is_mixed = (is_high_volume and is_low_freq) or (is_low_volume and is_high_freq)

    # Change magnitude untuk menentukan urgensi
    change_magnitude = abs(change) if change else 0
    is_big_move = change_magnitude > 2  # > 2% dianggap pergerakan besar
    is_small_move = change_magnitude < 0.5  # < 0.5% dianggap pergerakan kecil

    # Determine rhythm type berdasarkan kombinasi semua faktor
    if is_wide_range and is_ramai and is_big_move:
        rhythm_type = "CEPAT & RAMAI"
        rhythm_narrative = f"Pergerakan cepat (range {range_percent:.1f}%) dengan volume {volume_ratio:.1f}x dan frekuensi {freq_ratio:.1f}x dari rata-rata - ada urgensi di pasar"
        rhythm_icon = "fa-bolt"
        rhythm_color = "danger"
        rhythm_feel = "PANIC/EUFORIA"
    elif is_wide_range and is_sepi:
        rhythm_type = "LIAR & SEPI"
        rhythm_narrative = f"Range lebar ({range_percent:.1f}%) tapi volume {volume_ratio:.1f}x dan frekuensi {freq_ratio:.1f}x rendah - pergerakan mudah dimanipulasi"
        rhythm_icon = "fa-random"
        rhythm_color = "warning"
        rhythm_feel = "TIDAK NATURAL"
    elif is_wide_range and is_mixed:
        rhythm_type = "TIDAK SEIMBANG"
        rhythm_narrative = f"Range lebar ({range_percent:.1f}%) dengan ketidakseimbangan volume/frekuensi - perlu perhatian"
        rhythm_icon = "fa-exclamation-triangle"
        rhythm_color = "warning"
        rhythm_feel = "WASPADA"
    elif not is_wide_range and is_ramai:
        rhythm_type = "TERKONTROL & RAMAI"
        rhythm_narrative = f"Pergerakan terkendali (range {range_percent:.1f}%) dengan volume {volume_ratio:.1f}x dan frekuensi {freq_ratio:.1f}x tinggi - ada yang mengatur"
        rhythm_icon = "fa-hand-paper"
        rhythm_color = "info"
        rhythm_feel = "CONTROLLED"
    elif not is_wide_range and is_sepi:
        rhythm_type = "DIAM & SEPI"
        rhythm_narrative = f"Range sempit ({range_percent:.1f}%) dan volume/frekuensi rendah - pasar tidak tertarik"
        rhythm_icon = "fa-moon"
        rhythm_color = "secondary"
        rhythm_feel = "WAIT & SEE"
    elif is_ramai and is_small_move:
        rhythm_type = "RAMAI TAPI DATAR"
        rhythm_narrative = f"Volume {volume_ratio:.1f}x dan frekuensi {freq_ratio:.1f}x tinggi tapi pergerakan hanya {change_magnitude:.1f}% - ada yang menahan"
        rhythm_icon = "fa-compress-arrows-alt"
        rhythm_color = "info"
        rhythm_feel = "ABSORPTION"
    elif is_sepi and is_big_move:
        rhythm_type = "GERAK RINGAN"
        rhythm_narrative = f"Pergerakan {change_magnitude:.1f}% dengan volume/frekuensi rendah - mudah berbalik"
        rhythm_icon = "fa-feather"
        rhythm_color = "warning"
        rhythm_feel = "RAWAN REVERSAL"
    else:
        rhythm_type = "NORMAL"
        rhythm_narrative = f"Ritme pergerakan dalam batas wajar (volume {volume_ratio:.1f}x, frekuensi {freq_ratio:.1f}x)"
        rhythm_icon = "fa-heartbeat"
        rhythm_color = "secondary"
        rhythm_feel = "NORMAL"

    rhythm = {
        'type': rhythm_type,
        'narrative': rhythm_narrative,
        'icon': rhythm_icon,
        'color': rhythm_color,
        'feel': rhythm_feel,
        'volume_ratio': f"{volume_ratio:.2f}x",
        'freq_ratio': f"{freq_ratio:.2f}x",
        'change_magnitude': f"{change_magnitude:.2f}%"
    }

    # ========== 2.5 HUBUNGAN DENGAN AVG ==========
    if avg > 0:
        close_vs_avg_pct = ((close - avg) / avg) * 100
        open_vs_avg_pct = ((open_price - avg) / avg) * 100

        if close > avg and open_price > avg:
            avg_type = "SELALU DI ATAS AVG"
            avg_narrative = "Sepanjang hari harga dominan di atas rata-rata transaksi - jalur pembeli"
            avg_icon = "fa-level-up-alt"
            avg_color = "success"
            avg_dominance = "PEMBELI"
        elif close < avg and open_price < avg:
            avg_type = "SELALU DI BAWAH AVG"
            avg_narrative = "Sepanjang hari harga dominan di bawah rata-rata transaksi - jalur penjual"
            avg_icon = "fa-level-down-alt"
            avg_color = "danger"
            avg_dominance = "PENJUAL"
        elif open_price > avg and close < avg:
            avg_type = "TURUN MENEMBUS AVG"
            avg_narrative = "Harga dibuka di atas avg lalu turun menembus - tekanan jual menerobos"
            avg_icon = "fa-angle-double-down"
            avg_color = "danger"
            avg_dominance = "PENJUAL MENANG"
        elif open_price < avg and close > avg:
            avg_type = "NAIK MENEMBUS AVG"
            avg_narrative = "Harga dibuka di bawah avg lalu naik menembus - tekanan beli menerobos"
            avg_icon = "fa-angle-double-up"
            avg_color = "success"
            avg_dominance = "PEMBELI MENANG"
        else:
            avg_type = "BOLAK-BALIK AVG"
            avg_narrative = "Harga bolak-balik menyeberangi rata-rata - tidak ada dominasi jelas"
            avg_icon = "fa-sync"
            avg_color = "warning"
            avg_dominance = "TIDAK JELAS"
    else:
        avg_type = "N/A"
        avg_narrative = "Data rata-rata tidak tersedia"
        avg_icon = "fa-question"
        avg_color = "secondary"
        avg_dominance = "N/A"
        close_vs_avg_pct = 0

    avg_relation = {
        'type': avg_type,
        'narrative': avg_narrative,
        'icon': avg_icon,
        'color': avg_color,
        'dominance': avg_dominance,
        'close_vs_avg': f"{close_vs_avg_pct:+.2f}%"
    }

    # ========== GENERATE FULL NARRATIVE PARAGRAPH ==========
    # Build narrative based on all components
    direction_word = "turun" if change < 0 else ("naik" if change > 0 else "datar")

    # Determine movement style word (aligned with summary_questions)
    # KASAR = only for chaos/wild moves, TERARAH = directional even if wide
    if range_control == "TINGGI":
        movement_style = "terkontrol"
    elif range_control == "SEDANG" and is_directional:
        movement_style = "terarah"  # Wide but directional = terarah, not kasar
    elif range_control == "RENDAH":
        movement_style = "liar"  # Only truly chaotic moves
    else:
        movement_style = "normal"

    narrative_parts = []

    # Part 1: Opening and flow
    if flow_type == "DITEKAN":
        narrative_parts.append(f"Harga dibuka relatif tinggi, namun sejak awal tekanan jual muncul dan harga bergerak turun secara {movement_style}.")
    elif flow_type == "DIPULIHKAN":
        narrative_parts.append(f"Harga dibuka rendah, namun tekanan beli berhasil memulihkan harga secara {movement_style}.")
    elif flow_type == "DIPERTAHANKAN ATAS":
        narrative_parts.append("Harga dibuka dan dipertahankan di area atas sepanjang hari, tekanan jual tidak mampu menekan.")
    elif flow_type == "DIPERTAHANKAN BAWAH":
        narrative_parts.append("Harga dibuka dan terjebak di area bawah sepanjang hari, tekanan beli tidak mampu mengangkat.")
    else:
        narrative_parts.append(f"Harga bergerak {direction_word} dengan pola {flow_type.lower()}.")

    # Part 2: Range structure
    narrative_parts.append(f"Range pergerakan {range_type.lower()} ({range_percent:.1f}%), menunjukkan {range_narrative.split(' - ')[1] if ' - ' in range_narrative else 'pergerakan normal'}.")

    # Part 3: Close location
    narrative_parts.append(f"Penutupan terjadi {close_type.lower()} ({close_position*100:.0f}% dari range), {close_narrative.split(' - ')[1] if ' - ' in close_narrative else ''}.")

    # Part 4: Avg relation
    if avg > 0:
        narrative_parts.append(f"Sepanjang hari, {avg_narrative.lower()}.")

    full_narrative = " ".join(narrative_parts)

    # ========== SUMMARY QUESTIONS ==========
    # Aligned terminology: TERKONTROL / TERARAH / LIAR
    if range_control == "TINGGI":
        control_answer = "TERKONTROL"
    elif range_control == "SEDANG" and is_directional:
        control_answer = "TERARAH"
    elif range_control == "RENDAH":
        control_answer = "LIAR"
    else:
        control_answer = "NORMAL"

    summary_questions = {
        'didorong_ditekan_dikurung': flow_type,
        'kasar_atau_terkontrol': control_answer,
        'siapa_menang': winner,
        'selesai_atau_proses': "SELESAI" if abs(close_position - 0.5) > 0.3 else "MASIH PROSES",
        'selesai_note': "Keputusan intrahari, bukan konfirmasi tren"  # Clarification
    }

    return {
        'flow': flow,
        'range_structure': range_structure,
        'close_location': close_location,
        'rhythm': rhythm,
        'avg_relation': avg_relation,
        'full_narrative': full_narrative,
        'summary_questions': summary_questions
    }


def get_multiday_data(stock_code: str, days: int = 10) -> list:
    """
    Get multi-day OHLCV data for compression & absorption analysis.
    Returns list of daily data ordered from oldest to newest.
    """
    try:
        query = """
            SELECT date, open_price, high_price, low_price, close_price, avg_price,
                   volume, value, frequency, net_foreign, change_value, change_percent
            FROM stock_daily
            WHERE stock_code = %s
            ORDER BY date DESC
            LIMIT %s
        """
        results = execute_query(query, (stock_code, days))

        if not results:
            return []

        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])

        # Sort by date ascending (oldest first) for proper change calculation
        df = df.sort_values('date', ascending=True).reset_index(drop=True)

        # Convert to list of dicts, ordered oldest to newest
        data_list = []
        prev_close = None

        for idx, row in df.iterrows():
            close_price = float(row['close_price']) if pd.notna(row['close_price']) else 0
            open_price = float(row['open_price']) if pd.notna(row['open_price']) else 0
            high_price = float(row['high_price']) if pd.notna(row['high_price']) else 0
            low_price = float(row['low_price']) if pd.notna(row['low_price']) else 0

            # Calculate change_percent
            change_pct = float(row['change_percent']) if pd.notna(row.get('change_percent')) else 0

            # If change_percent is 0 or NULL, calculate from previous close
            if change_pct == 0 and prev_close is not None and prev_close != 0:
                change_pct = ((close_price - prev_close) / prev_close) * 100
            # If still 0 and no prev_close, try from change_value
            elif change_pct == 0 and pd.notna(row.get('change_value')) and row['change_value'] != 0:
                change_val = float(row['change_value'])
                calc_prev = close_price - change_val
                if calc_prev != 0:
                    change_pct = (change_val / calc_prev) * 100

            data_list.append({
                'date': row['date'],
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'avg': float(row['avg_price']) if pd.notna(row.get('avg_price')) else 0,
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'value': float(row['value']) if pd.notna(row['value']) else 0,
                'frequency': int(row['frequency']) if pd.notna(row.get('frequency')) else 0,
                'net_foreign': float(row['net_foreign']) if pd.notna(row.get('net_foreign')) else 0,
                'change': change_pct,
            })

            prev_close = close_price

        return data_list
    except Exception as e:
        print(f"Error getting multiday data: {e}")
        return []


def get_weekly_analysis(stock_code: str) -> dict:
    """
    Get weekly ACCUMULATION analysis for 4 weeks (1, 2, 3, 4 minggu).
    Uses V6 formula: Volume in lower half vs upper half to detect accumulation.
    """
    try:
        # Get 20 trading days data (approx 4 weeks)
        query = """
            SELECT date, open_price, high_price, low_price, close_price,
                   volume, value, change_percent,
                   foreign_buy, foreign_sell, net_foreign
            FROM stock_daily
            WHERE stock_code = %s
            ORDER BY date DESC
            LIMIT 20
        """
        results = execute_query(query, (stock_code,))

        if not results or len(results) < 5:
            return {'error': 'Data tidak cukup', 'weeks': {}}

        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=True).reset_index(drop=True)

        # Convert numeric columns
        for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 'value', 'change_percent', 'foreign_buy', 'foreign_sell', 'net_foreign']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        weeks_data = {}
        total_days = len(df)

        # Split into 4 weeks (5 trading days each)
        for week_num in range(1, 5):
            end_idx = total_days - (week_num - 1) * 5
            start_idx = max(0, end_idx - 5)

            if start_idx >= end_idx or end_idx <= 0:
                continue

            week_df = df.iloc[start_idx:end_idx].copy()

            if len(week_df) == 0:
                continue

            # Calculate weekly price metrics
            week_open = week_df['open_price'].iloc[0]
            week_close = week_df['close_price'].iloc[-1]
            week_high = week_df['high_price'].max()
            week_low = week_df['low_price'].min()
            week_range = ((week_high - week_low) / week_low * 100) if week_low > 0 else 0
            week_avg_volume = week_df['volume'].mean()
            week_total_volume = week_df['volume'].sum()

            # === FOREIGN FLOW ===
            week_foreign_buy = week_df['foreign_buy'].sum()
            week_foreign_sell = week_df['foreign_sell'].sum()
            week_net_foreign = week_df['net_foreign'].sum()

            # Convert foreign from Rupiah to Lot (Value / AvgPrice / 100)
            week_avg_price = week_df['close_price'].mean()
            if week_avg_price > 0:
                week_net_foreign_lot = week_net_foreign / week_avg_price / 100
            else:
                week_net_foreign_lot = 0

            # === V6 ACCUMULATION ANALYSIS ===
            # Calculate midpoint of weekly range
            midpoint = (week_high + week_low) / 2

            # Calculate volume in lower half vs upper half
            vol_lower = 0
            vol_upper = 0
            days_lower = 0
            days_upper = 0

            for _, row in week_df.iterrows():
                avg_price = (row['high_price'] + row['low_price'] + row['close_price']) / 3
                if avg_price <= midpoint:
                    vol_lower += row['volume']
                    days_lower += 1
                else:
                    vol_upper += row['volume']
                    days_upper += 1

            # Calculate volume ratio (V6 formula)
            vol_ratio = vol_lower / vol_upper if vol_upper > 0 else (2.0 if vol_lower > 0 else 1.0)

            # Determine phase based on volume ratio (V6.1 - Updated threshold)
            # ACCUMULATION requires VR > 3.0 (backtest proven)
            if vol_ratio > 4.0:
                phase = 'ACCUMULATION'
                phase_color = 'success'
                phase_icon = '🟢'
            elif vol_ratio < 0.8:
                phase = 'DISTRIBUTION'
                phase_color = 'danger'
                phase_icon = '🔴'
            elif vol_ratio > 1.5:
                phase = 'WEAK ACC'
                phase_color = 'warning'
                phase_icon = '🟡'
            else:
                phase = 'NEUTRAL'
                phase_color = 'secondary'
                phase_icon = '⚪'

            # Calculate accumulation score (0-100)
            if vol_ratio > 1:
                acc_score = min(100, int((vol_ratio - 1) * 100))
            else:
                acc_score = max(0, int((1 - (1 / vol_ratio)) * -100)) if vol_ratio > 0 else 0

            # Chart data for volume bars
            chart_data = {
                'dates': week_df['date'].dt.strftime('%d/%m').tolist(),
                'volumes': week_df['volume'].tolist(),
                'closes': week_df['close_price'].tolist(),
                'vol_lower': vol_lower,
                'vol_upper': vol_upper,
            }

            week_label = f"Minggu {week_num}" if week_num == 1 else f"{week_num} Minggu Lalu"

            weeks_data[week_num] = {
                'label': week_label,
                'start_date': week_df['date'].iloc[0].strftime('%d %b'),
                'end_date': week_df['date'].iloc[-1].strftime('%d %b'),
                'high': week_high,
                'low': week_low,
                'midpoint': midpoint,
                'range_pct': week_range,
                'avg_volume': week_avg_volume,
                'total_volume': week_total_volume,
                # Foreign flow
                'foreign_buy': week_foreign_buy,
                'foreign_sell': week_foreign_sell,
                'net_foreign': week_net_foreign,
                'net_foreign_lot': week_net_foreign_lot,
                'avg_price': week_avg_price,
                # V6 Accumulation metrics
                'vol_lower': vol_lower,
                'vol_upper': vol_upper,
                'vol_ratio': vol_ratio,
                'days_lower': days_lower,
                'days_upper': days_upper,
                'phase': phase,
                'phase_color': phase_color,
                'phase_icon': phase_icon,
                'acc_score': acc_score,
                'chart_data': chart_data,
                'days_count': len(week_df),
            }

        return {'weeks': weeks_data, 'total_days': total_days}

    except Exception as e:
        print(f"Error getting weekly analysis: {e}")
        return {'error': str(e), 'weeks': {}}


def analyze_compression_absorption(multiday_data: list) -> dict:
    """
    POINT 3 - Compression & Absorption Analysis
    Analyzes multi-day data to detect:
    - Compression: range narrowing, volatility decreasing
    - Absorption: pressure failing to continue

    Returns narrative analysis of market phase.
    """
    if not multiday_data or len(multiday_data) < 5:
        return {
            'compression': {'detected': False, 'type': 'N/A', 'narrative': 'Data tidak cukup untuk analisis (minimal 5 hari)'},
            'absorption': {'detected': False, 'type': 'N/A', 'narrative': 'Data tidak cukup untuk analisis'},
            'phase': 'TIDAK DAPAT DIANALISIS',
            'full_narrative': 'Data historis tidak mencukupi untuk analisis compression & absorption.',
            'key_questions': {},
            'data_used': []
        }

    # ========== CALCULATE METRICS ==========
    n = len(multiday_data)

    # Extract arrays for analysis
    ranges = [(d['high'] - d['low']) for d in multiday_data]
    closes = [d['close'] for d in multiday_data]
    highs = [d['high'] for d in multiday_data]
    lows = [d['low'] for d in multiday_data]
    volumes = [d['volume'] for d in multiday_data]
    values = [d['value'] for d in multiday_data]
    freqs = [d['frequency'] for d in multiday_data]
    changes = [d['change'] for d in multiday_data]

    # Split into periods for comparison (first half vs second half)
    mid = n // 2
    early_ranges = ranges[:mid]
    recent_ranges = ranges[mid:]

    avg_early_range = sum(early_ranges) / len(early_ranges) if early_ranges else 0
    avg_recent_range = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0

    # Range trend (is it narrowing?)
    range_ratio = avg_recent_range / avg_early_range if avg_early_range > 0 else 1
    is_range_narrowing = range_ratio < 0.8  # Recent range < 80% of early range
    is_range_stable = 0.8 <= range_ratio <= 1.2
    is_range_widening = range_ratio > 1.2

    # Close position consistency (are closes clustering?)
    recent_closes = closes[mid:]
    close_std = pd.Series(recent_closes).std() if len(recent_closes) > 1 else 0
    avg_close = sum(recent_closes) / len(recent_closes) if recent_closes else 0
    close_cv = (close_std / avg_close * 100) if avg_close > 0 else 0  # Coefficient of variation
    is_close_clustering = close_cv < 2  # Low variation = clustering

    # ========== COMPRESSION ANALYSIS ==========
    # Compression = range narrowing + close clustering + market still alive
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    recent_volume_ratio = (sum(volumes[mid:]) / len(volumes[mid:])) / avg_volume if avg_volume > 0 else 1
    is_market_alive = recent_volume_ratio > 0.5  # Volume not dead

    compression_detected = is_range_narrowing and is_market_alive
    compression_strong = compression_detected and is_close_clustering

    if compression_strong:
        compression_type = "COMPRESSION KUAT"
        compression_narrative = f"Range menyempit signifikan ({range_ratio:.0%} dari sebelumnya) dengan close yang mengumpul. Pasar masih hidup (volume {recent_volume_ratio:.1f}x rata-rata). Harga seperti sedang dikurung."
        compression_icon = "fa-compress-arrows-alt"
        compression_color = "info"
    elif compression_detected:
        compression_type = "COMPRESSION MODERAT"
        compression_narrative = f"Range mulai menyempit ({range_ratio:.0%} dari sebelumnya). Volatilitas menurun meski pasar masih aktif."
        compression_icon = "fa-compress"
        compression_color = "primary"
    elif is_range_stable:
        compression_type = "TIDAK ADA COMPRESSION"
        compression_narrative = "Range relatif stabil, tidak ada tanda-tanda pengurangan volatilitas yang signifikan."
        compression_icon = "fa-equals"
        compression_color = "secondary"
    else:
        compression_type = "EXPANSION"
        compression_narrative = f"Range justru melebar ({range_ratio:.0%} dari sebelumnya). Volatilitas meningkat, bukan compression."
        compression_icon = "fa-expand-arrows-alt"
        compression_color = "warning"

    compression = {
        'detected': compression_detected,
        'strong': compression_strong,
        'type': compression_type,
        'narrative': compression_narrative,
        'icon': compression_icon,
        'color': compression_color,
        'range_ratio': f"{range_ratio:.0%}",
        'close_clustering': f"{close_cv:.1f}%"
    }

    # ========== ABSORPTION ANALYSIS ==========
    # Absorption = pressure comes but fails to continue
    # Check if lows are holding (sell pressure absorbed) or highs are capped (buy pressure absorbed)

    recent_lows = lows[mid:]
    recent_highs = highs[mid:]
    early_lows = lows[:mid]
    early_highs = highs[:mid]

    # Count down days and up days
    down_days = sum(1 for c in changes[mid:] if c < -0.5)
    up_days = sum(1 for c in changes[mid:] if c > 0.5)

    # Check if lows are holding despite down pressure
    min_early_low = min(early_lows) if early_lows else 0
    min_recent_low = min(recent_lows) if recent_lows else 0
    lows_holding = min_recent_low >= min_early_low * 0.98  # Recent low not breaking early low

    # Check if highs are capped despite up pressure
    max_early_high = max(early_highs) if early_highs else 0
    max_recent_high = max(recent_highs) if recent_highs else 0
    highs_capped = max_recent_high <= max_early_high * 1.02  # Recent high not breaking early high

    # Determine absorption type
    sell_absorption = down_days >= 2 and lows_holding
    buy_absorption = up_days >= 2 and highs_capped

    if sell_absorption and not buy_absorption:
        absorption_type = "ABSORPTION JUAL"
        absorption_narrative = f"Tekanan jual muncul ({down_days} hari turun) namun low tidak makin rendah. Tekanan jual mulai diserap."
        absorption_icon = "fa-hand-holding"
        absorption_color = "success"
        absorption_detected = True
        absorption_direction = "SELL ABSORBED"
    elif buy_absorption and not sell_absorption:
        absorption_type = "ABSORPTION BELI"
        absorption_narrative = f"Tekanan beli muncul ({up_days} hari naik) namun high tidak makin tinggi. Tekanan beli mulai diserap."
        absorption_icon = "fa-hand-paper"
        absorption_color = "warning"
        absorption_detected = True
        absorption_direction = "BUY ABSORBED"
    elif sell_absorption and buy_absorption:
        absorption_type = "ABSORPTION DUA ARAH"
        absorption_narrative = "Baik tekanan jual maupun beli tidak menghasilkan kelanjutan. Harga tertahan di area yang sama."
        absorption_icon = "fa-hands"
        absorption_color = "info"
        absorption_detected = True
        absorption_direction = "BOTH ABSORBED"
    else:
        absorption_type = "BELUM ADA ABSORPTION"
        absorption_narrative = "Tekanan masih efektif menggerakkan harga. Belum ada tanda penyerapan."
        absorption_icon = "fa-arrows-alt-v"
        absorption_color = "secondary"
        absorption_detected = False
        absorption_direction = "NONE"

    absorption = {
        'detected': absorption_detected,
        'type': absorption_type,
        'narrative': absorption_narrative,
        'icon': absorption_icon,
        'color': absorption_color,
        'direction': absorption_direction,
        'down_days': down_days,
        'up_days': up_days,
        'lows_holding': lows_holding,
        'highs_capped': highs_capped
    }

    # ========== DETERMINE PHASE ==========
    # Each phase includes an education_note to help users understand the context
    if compression_strong and absorption_detected:
        if absorption_direction == "SELL ABSORBED":
            phase = "COMPRESSION + ABSORPTION JUAL"
            phase_narrative = "Fase penahanan harga (compression) terbentuk akibat tekanan jual yang mulai diserap. Range mengecil dan low bertahan."
            phase_color = "success"
            phase_implication = "Tekanan turun mulai kehilangan daya. Belum berarti naik, tapi turun mulai mentok."
            education_note = "Fase ini menarik karena tekanan jual sudah tidak efektif. Perhatikan apakah kondisi ini berlanjut."
        elif absorption_direction == "BUY ABSORBED":
            phase = "COMPRESSION + ABSORPTION BELI"
            phase_narrative = "Fase penahanan harga (compression) terbentuk akibat tekanan beli yang mulai diserap. Range mengecil dan high tertahan."
            phase_color = "warning"
            phase_implication = "Tekanan naik mulai kehilangan momentum. Belum berarti turun, tapi naik mulai berat."
            education_note = "Fase ini menunjukkan kelelahan pembeli. Perhatikan apakah tekanan beli masih datang tanpa hasil."
        else:
            phase = "COMPRESSION + ABSORPTION DUA ARAH"
            phase_narrative = "Fase penahanan harga (compression) dengan kedua tekanan yang diserap. Pasar dalam keseimbangan."
            phase_color = "info"
            phase_implication = "Pasar menunggu. Tidak ada arah jelas."
            education_note = "Kedua sisi tertahan. Biasanya fase ini berakhir dengan breakout ke salah satu arah."
    elif compression_detected:
        phase = "COMPRESSION TANPA ABSORPTION JELAS"
        phase_narrative = "Range menyempit tapi belum terlihat tekanan yang jelas diserap. Fase menunggu."
        phase_color = "secondary"
        phase_implication = "Volatilitas menurun, pasar dalam mode tunggu."
        education_note = "Range mengecil tapi belum ada tekanan signifikan yang gagal. Tunggu konfirmasi lebih lanjut."
    elif absorption_detected:
        phase = f"ABSORPTION TANPA COMPRESSION"
        phase_narrative = f"Tekanan mulai diserap tapi range belum menyempit. Proses mungkin baru dimulai."
        phase_color = absorption['color']
        phase_implication = "Ada perlawanan terhadap tekanan, tapi belum terkurung."
        education_note = "Tanda awal ada yang mulai menahan tekanan. Jika berlanjut, range akan mulai menyempit."
    else:
        phase = "TIDAK ADA COMPRESSION/ABSORPTION"
        phase_narrative = "Tidak terdeteksi fase penahanan atau penyerapan. Harga masih bergerak bebas."
        phase_color = "secondary"
        phase_implication = "Belum ada fase menarik untuk analisis lanjutan."
        education_note = "Fase compression/absorption biasanya muncul setelah tekanan mulai gagal. Saat ini tekanan masih bekerja normal."

    # ========== GENERATE FULL NARRATIVE ==========
    # Determine prior trend for context
    total_change = sum(changes)
    if total_change < -5:
        prior_trend = "setelah penurunan"
    elif total_change > 5:
        prior_trend = "setelah kenaikan"
    else:
        prior_trend = "dalam kondisi sideways"

    full_narrative_parts = []
    full_narrative_parts.append(f"{prior_trend.capitalize()}, {phase_narrative.lower()}")

    if compression_detected:
        full_narrative_parts.append(f"Range pergerakan menyempit menjadi {range_ratio:.0%} dari periode sebelumnya.")

    if absorption_detected:
        if absorption_direction == "SELL ABSORBED":
            full_narrative_parts.append("Tekanan jual tidak lagi mendorong harga lebih rendah.")
        elif absorption_direction == "BUY ABSORBED":
            full_narrative_parts.append("Tekanan beli tidak lagi mendorong harga lebih tinggi.")

    full_narrative_parts.append(phase_implication)
    full_narrative = " ".join(full_narrative_parts)

    # ========== KEY QUESTIONS ==========
    key_questions = {
        'tekanan_efektif': "TIDAK" if absorption_detected else "YA",
        'harga_bebas': "TIDAK" if compression_detected else "YA",
        'kegagalan_berulang': "YA" if absorption_detected and (down_days >= 3 or up_days >= 3) else "TIDAK",
        'range_menyempit': "YA" if is_range_narrowing else "TIDAK"
    }

    # Data summary for display
    data_summary = []
    for d in multiday_data[-5:]:  # Last 5 days
        data_summary.append({
            'date': d['date'].strftime('%d %b') if hasattr(d['date'], 'strftime') else str(d['date'])[:10],
            'range': f"{((d['high'] - d['low']) / d['low'] * 100):.1f}%" if d['low'] > 0 else "N/A",
            'close_pos': f"{((d['close'] - d['low']) / (d['high'] - d['low']) * 100):.0f}%" if (d['high'] - d['low']) > 0 else "50%",
            'change': f"{d['change']:+.1f}%",
            'volume': d['volume']
        })

    return {
        'compression': compression,
        'absorption': absorption,
        'phase': phase,
        'phase_color': phase_color,
        'phase_narrative': phase_narrative,
        'phase_implication': phase_implication,
        'education_note': education_note,
        'full_narrative': full_narrative,
        'key_questions': key_questions,
        'data_summary': data_summary,
        'prior_trend': prior_trend,
        'days_analyzed': n
    }


def analyze_accumulation_distribution(point3_result: dict, multiday_data: list) -> dict:
    """
    POINT 4 - Akumulasi & Distribusi
    Membaca NIAT pasar berdasarkan fase yang sudah tervalidasi di Point 3.

    ATURAN ARSITEKTUR:
    - Point 4 TIDAK BOLEH aktif jika Point 3 belum jelas
    - Point 4 membaca arah niat, bukan bertindak

    Returns one of three statuses:
    - POTENSI AKUMULASI
    - POTENSI DISTRIBUSI
    - BELUM DAPAT DITENTUKAN
    """

    # ========== GATE CHECK: Point 3 harus valid dulu ==========
    compression_detected = point3_result.get('compression', {}).get('detected', False)
    absorption_detected = point3_result.get('absorption', {}).get('detected', False)
    prior_trend = point3_result.get('prior_trend', '')

    # Jika Point 3 belum jelas, Point 4 harus diam
    if not compression_detected and not absorption_detected:
        return {
            'active': False,
            'status': 'POINT 4 TIDAK AKTIF',
            'status_color': 'secondary',
            'reason': 'Point 3 belum mendeteksi compression atau absorption. Point 4 menunggu.',
            'narrative': 'Fase penahanan harga belum terbentuk. Analisis akumulasi/distribusi belum dapat dilakukan karena harga masih bergerak bebas.',
            'education_note': 'Point 4 hanya aktif setelah Point 3 mendeteksi fase penahanan. Ini mencegah analisis prematur.',
            'signals': {},
            'confidence': 0
        }

    # ========== CONTEXT CHECK: Akumulasi setelah turun, Distribusi setelah naik ==========
    is_after_decline = 'penurunan' in prior_trend.lower()
    is_after_rise = 'kenaikan' in prior_trend.lower()
    is_sideways = 'sideways' in prior_trend.lower()

    # Get absorption direction from Point 3
    absorption_direction = point3_result.get('absorption', {}).get('direction', 'NONE')

    # ========== ANALYZE MULTI-DAY DATA FOR ACCUMULATION/DISTRIBUTION SIGNALS ==========
    if not multiday_data or len(multiday_data) < 5:
        return {
            'active': False,
            'status': 'DATA TIDAK CUKUP',
            'status_color': 'secondary',
            'reason': 'Data historis tidak mencukupi untuk analisis akumulasi/distribusi.',
            'narrative': 'Minimal 5 hari data diperlukan untuk analisis Point 4.',
            'education_note': 'Akumulasi dan distribusi adalah proses, bukan peristiwa. Butuh data beberapa hari.',
            'signals': {},
            'confidence': 0
        }

    n = len(multiday_data)
    mid = n // 2

    # Extract data
    closes = [d['close'] for d in multiday_data]
    highs = [d['high'] for d in multiday_data]
    lows = [d['low'] for d in multiday_data]
    volumes = [d['volume'] for d in multiday_data]
    changes = [d['change'] for d in multiday_data]

    # Recent period analysis
    recent_data = multiday_data[mid:]
    recent_closes = closes[mid:]
    recent_highs = highs[mid:]
    recent_lows = lows[mid:]
    recent_changes = changes[mid:]

    # ========== SIGNAL ANALYSIS ==========

    # 1. Arah tekanan yang GAGAL (Jantung Point 4)
    down_days = sum(1 for c in recent_changes if c < -0.5)
    up_days = sum(1 for c in recent_changes if c > 0.5)

    # Check if lows are holding (sell pressure failing)
    min_recent_low = min(recent_lows) if recent_lows else 0
    min_early_low = min(lows[:mid]) if lows[:mid] else 0
    lows_holding = min_recent_low >= min_early_low * 0.98

    # Check if highs are capped (buy pressure failing)
    max_recent_high = max(recent_highs) if recent_highs else 0
    max_early_high = max(highs[:mid]) if highs[:mid] else 0
    highs_capped = max_recent_high <= max_early_high * 1.02

    # 2. Perilaku Close
    # For accumulation: close often not at extreme low
    avg_close_position = 0
    for d in recent_data:
        rng = d['high'] - d['low']
        if rng > 0:
            pos = (d['close'] - d['low']) / rng
            avg_close_position += pos
    avg_close_position = avg_close_position / len(recent_data) if recent_data else 0.5

    close_not_at_low = avg_close_position > 0.35  # Close typically above 35% of range
    close_not_at_high = avg_close_position < 0.65  # Close typically below 65% of range

    # 3. Range behavior (from Point 3)
    range_ratio = point3_result.get('compression', {}).get('range_ratio', '100%')
    try:
        range_ratio_val = float(range_ratio.replace('%', '')) / 100
    except:
        range_ratio_val = 1.0
    range_narrowing = range_ratio_val < 0.9

    # 4. Activity weight (ramai tapi tidak jalan)
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    recent_avg_volume = sum(volumes[mid:]) / len(volumes[mid:]) if volumes[mid:] else 0
    volume_ratio = recent_avg_volume / avg_volume if avg_volume > 0 else 1

    total_recent_change = sum(recent_changes)
    active_but_stuck = volume_ratio > 0.8 and abs(total_recent_change) < 3  # Volume normal tapi harga tidak kemana-mana

    # ========== DETERMINE ACCUMULATION OR DISTRIBUTION ==========

    # Accumulation signals
    accumulation_signals = {
        'context_valid': is_after_decline,  # Must be after decline
        'sell_pressure_failing': down_days >= 2 and lows_holding,
        'close_behavior': close_not_at_low,
        'range_narrowing': range_narrowing,
        'active_but_stuck': active_but_stuck,
        'absorption_type_match': absorption_direction in ['SELL ABSORBED', 'BOTH ABSORBED']
    }

    # Distribution signals
    distribution_signals = {
        'context_valid': is_after_rise,  # Must be after rise
        'buy_pressure_failing': up_days >= 2 and highs_capped,
        'close_behavior': close_not_at_high,
        'range_narrowing': range_narrowing,
        'active_but_stuck': active_but_stuck,
        'absorption_type_match': absorption_direction in ['BUY ABSORBED', 'BOTH ABSORBED']
    }

    # Count signals
    acc_score = sum(1 for v in accumulation_signals.values() if v)
    dist_score = sum(1 for v in distribution_signals.values() if v)

    # ========== DETERMINE STATUS ==========

    if acc_score >= 4 and accumulation_signals['context_valid']:
        status = "POTENSI AKUMULASI"
        status_color = "success"
        confidence = min(acc_score / 6 * 100, 100)
        narrative = f"Terlihat fase penahanan setelah penurunan, di mana tekanan jual mulai kehilangan efektivitas. Low bertahan meski ada {down_days} hari tekanan turun. Close rata-rata di posisi {avg_close_position*100:.0f}% dari range (tidak di ekstrem bawah)."
        education_note = "Akumulasi adalah proses pengumpulan. Banyak yang ingin jual, tapi harga tidak mau turun jauh. Ini BUKAN sinyal entry, tapi indikasi arah niat."

        signals_detail = {
            'Konteks (setelah turun)': '✓ Valid' if accumulation_signals['context_valid'] else '✗ Tidak valid',
            'Tekanan jual gagal': f"✓ {down_days} hari turun tapi low bertahan" if accumulation_signals['sell_pressure_failing'] else '✗ Tekanan masih efektif',
            'Close tidak di low': f"✓ Rata-rata {avg_close_position*100:.0f}%" if accumulation_signals['close_behavior'] else f'✗ Close di {avg_close_position*100:.0f}%',
            'Range menyempit': '✓ Ya' if accumulation_signals['range_narrowing'] else '✗ Tidak',
            'Aktif tapi stuck': '✓ Ya' if accumulation_signals['active_but_stuck'] else '✗ Tidak',
        }

    elif dist_score >= 4 and distribution_signals['context_valid']:
        status = "POTENSI DISTRIBUSI"
        status_color = "warning"
        confidence = min(dist_score / 6 * 100, 100)
        narrative = f"Terlihat fase penahanan setelah kenaikan, di mana dorongan beli mulai kehilangan lanjutan. High tertahan meski ada {up_days} hari tekanan naik. Close rata-rata di posisi {avg_close_position*100:.0f}% dari range (tidak di ekstrem atas)."
        education_note = "Distribusi adalah proses pelepasan. Banyak yang ingin beli, tapi harga tidak mau naik jauh. Ini BUKAN sinyal exit, tapi indikasi arah niat."

        signals_detail = {
            'Konteks (setelah naik)': '✓ Valid' if distribution_signals['context_valid'] else '✗ Tidak valid',
            'Tekanan beli gagal': f"✓ {up_days} hari naik tapi high tertahan" if distribution_signals['buy_pressure_failing'] else '✗ Tekanan masih efektif',
            'Close tidak di high': f"✓ Rata-rata {avg_close_position*100:.0f}%" if distribution_signals['close_behavior'] else f'✗ Close di {avg_close_position*100:.0f}%',
            'Range menyempit': '✓ Ya' if distribution_signals['range_narrowing'] else '✗ Tidak',
            'Aktif tapi stuck': '✓ Ya' if distribution_signals['active_but_stuck'] else '✗ Tidak',
        }

    elif compression_detected or absorption_detected:
        # Ada fase penahanan tapi belum cukup sinyal untuk akumulasi/distribusi
        status = "BELUM DAPAT DITENTUKAN"
        status_color = "info"
        confidence = max(acc_score, dist_score) / 6 * 100

        if is_sideways:
            narrative = "Fase penahanan terdeteksi dalam kondisi sideways. Konteks belum jelas apakah ini akumulasi atau distribusi."
            context_note = "Tanpa prior trend yang jelas (naik/turun), sulit menentukan niat di balik penahanan."
        elif not accumulation_signals['context_valid'] and not distribution_signals['context_valid']:
            narrative = "Fase penahanan terdeteksi, namun konteks tidak sesuai. Akumulasi butuh prior trend turun, distribusi butuh prior trend naik."
            context_note = "Konteks adalah kunci. Akumulasi di puncak atau distribusi di dasar adalah kesalahan klasik."
        else:
            narrative = "Fase penahanan terdeteksi, namun sinyal belum cukup kuat untuk disimpulkan sebagai akumulasi atau distribusi."
            context_note = "Tunggu lebih banyak konfirmasi. Proses ini butuh waktu."

        education_note = context_note
        signals_detail = {
            'Skor Akumulasi': f"{acc_score}/6 sinyal",
            'Skor Distribusi': f"{dist_score}/6 sinyal",
            'Konteks setelah turun': '✓' if is_after_decline else '✗',
            'Konteks setelah naik': '✓' if is_after_rise else '✗',
        }
    else:
        # Fallback
        status = "BELUM DAPAT DITENTUKAN"
        status_color = "secondary"
        confidence = 0
        narrative = "Belum ada cukup data atau sinyal untuk menentukan akumulasi atau distribusi."
        education_note = "Point 4 membutuhkan fase penahanan yang tervalidasi di Point 3."
        signals_detail = {}

    return {
        'active': True if (compression_detected or absorption_detected) else False,
        'status': status,
        'status_color': status_color,
        'confidence': confidence,
        'narrative': narrative,
        'education_note': education_note,
        'signals': signals_detail,
        'metrics': {
            'down_days': down_days,
            'up_days': up_days,
            'lows_holding': lows_holding,
            'highs_capped': highs_capped,
            'avg_close_position': f"{avg_close_position*100:.0f}%",
            'volume_ratio': f"{volume_ratio:.2f}x",
            'total_recent_change': f"{total_recent_change:+.1f}%"
        },
        'prior_trend': prior_trend,
        'acc_score': acc_score,
        'dist_score': dist_score
    }


def analyze_entry_confirmation(point4_result: dict, point3_result: dict, multiday_data: list, snapshot: dict) -> dict:
    """
    POINT 5 - Entry Confirmation
    Membaca apakah NIAT mulai DIEKSEKUSI oleh pasar.

    ATURAN ARSITEKTUR:
    - Point 5 HANYA aktif jika Point 4 AKTIF
    - Point 5 mencari MOMEN eksekusi, bukan harga murah/mahal

    Returns one of three statuses:
    - ENTRY CONFIRMED — BULLISH (akumulasi → pelepasan ke atas)
    - ENTRY CONFIRMED — BEARISH (distribusi → pelepasan ke bawah)
    - ENTRY NOT CONFIRMED (niat ada, eksekusi belum)
    """

    # ========== GATE CHECK: Point 4 harus AKTIF ==========
    point4_active = point4_result.get('active', False)
    point4_status = point4_result.get('status', '')

    if not point4_active:
        return {
            'active': False,
            'status': 'POINT 5 TIDAK AKTIF',
            'status_color': 'secondary',
            'reason': 'Point 4 belum aktif. Entry confirmation menunggu fase akumulasi/distribusi tervalidasi.',
            'narrative': 'Belum ada fase akumulasi atau distribusi yang terdeteksi. Point 5 tidak dapat mengkonfirmasi entry tanpa niat pasar yang jelas dari Point 4.',
            'education_note': 'Point 5 hanya aktif setelah Point 4 mendeteksi potensi akumulasi atau distribusi. Ini pengaman sistem.',
            'signals': {},
            'entry_type': None
        }

    # Determine expected direction based on Point 4
    is_accumulation = 'AKUMULASI' in point4_status.upper()
    is_distribution = 'DISTRIBUSI' in point4_status.upper()

    if not is_accumulation and not is_distribution:
        return {
            'active': False,
            'status': 'POINT 5 MENUNGGU',
            'status_color': 'info',
            'reason': 'Point 4 aktif tapi belum menentukan akumulasi atau distribusi.',
            'narrative': 'Fase penahanan terdeteksi namun arah niat belum jelas. Point 5 menunggu konfirmasi dari Point 4.',
            'education_note': 'Entry harus berdasarkan niat yang sudah teridentifikasi, bukan tebakan.',
            'signals': {},
            'entry_type': None
        }

    # ========== GET DATA FOR ANALYSIS ==========
    if not multiday_data or len(multiday_data) < 3:
        return {
            'active': True,
            'status': 'DATA TIDAK CUKUP',
            'status_color': 'secondary',
            'reason': 'Data tidak mencukupi untuk analisis entry.',
            'narrative': 'Minimal 3 hari data diperlukan untuk konfirmasi entry.',
            'education_note': 'Entry confirmation membutuhkan data terbaru untuk melihat pelepasan.',
            'signals': {},
            'entry_type': 'ACCUMULATION' if is_accumulation else 'DISTRIBUTION'
        }

    # Get compression metrics from Point 3
    compression_range_ratio = point3_result.get('compression', {}).get('range_ratio', '100%')
    try:
        compression_range_val = float(compression_range_ratio.replace('%', ''))
    except:
        compression_range_val = 100

    # Latest day data (today)
    today = multiday_data[-1]
    yesterday = multiday_data[-2] if len(multiday_data) >= 2 else today
    day_before = multiday_data[-3] if len(multiday_data) >= 3 else yesterday

    # Calculate today's metrics
    today_range = today['high'] - today['low']
    today_range_pct = (today_range / today['low'] * 100) if today['low'] > 0 else 0
    today_close_pos = (today['close'] - today['low']) / today_range if today_range > 0 else 0.5
    today_change = today['change']

    # Calculate average range during compression (last 5 days before today)
    compression_days = multiday_data[-6:-1] if len(multiday_data) >= 6 else multiday_data[:-1]
    avg_compression_range = sum((d['high'] - d['low']) for d in compression_days) / len(compression_days) if compression_days else today_range

    # Range expansion check
    range_expansion_ratio = today_range / avg_compression_range if avg_compression_range > 0 else 1
    is_range_expanding = range_expansion_ratio > 1.3  # Range 30% lebih besar dari compression

    # Activity check
    avg_volume = sum(d['volume'] for d in compression_days) / len(compression_days) if compression_days else today['volume']
    volume_ratio = today['volume'] / avg_volume if avg_volume > 0 else 1
    is_volume_supporting = volume_ratio > 1.2  # Volume 20% lebih tinggi

    # ========== ENTRY CONFIRMATION LOGIC ==========

    if is_accumulation:
        # Looking for BULLISH breakout
        # 1. Price breaking out upward from compression
        is_breaking_up = today_change > 1.5  # Significant up move
        # 2. Close near high (not ambiguous)
        is_close_strong = today_close_pos > 0.7  # Close in upper 30% of range
        # 3. Range expanding with direction
        is_directional_expansion = is_range_expanding and today_change > 0
        # 4. Volume supporting
        has_volume_support = is_volume_supporting

        # Count confirmation signals
        bullish_signals = {
            'breaking_up': is_breaking_up,
            'close_strong': is_close_strong,
            'range_expanding': is_directional_expansion,
            'volume_support': has_volume_support
        }
        confirmation_score = sum(1 for v in bullish_signals.values() if v)

        if confirmation_score >= 3:
            status = "ENTRY CONFIRMED — BULLISH"
            status_color = "success"
            narrative = f"Setelah fase penahanan pasca penurunan (akumulasi), harga mulai keluar dari area kurungan dengan pergerakan {today_change:+.1f}%. Range melebar {range_expansion_ratio:.1f}x dari fase compression. Penutupan di {today_close_pos*100:.0f}% (dekat high), dengan volume {volume_ratio:.1f}x dari rata-rata. Pelepasan ke atas mulai dieksekusi."
            education_note = "Entry BULLISH terkonfirmasi. Ini bukan jaminan profit, tapi konfirmasi bahwa niat akumulasi mulai dieksekusi pasar."
            signals_detail = {
                'Breakout ke atas': f"✓ Change {today_change:+.1f}%" if is_breaking_up else f"✗ Change {today_change:+.1f}%",
                'Close kuat (>70%)': f"✓ Close di {today_close_pos*100:.0f}%" if is_close_strong else f"✗ Close di {today_close_pos*100:.0f}%",
                'Range melebar': f"✓ {range_expansion_ratio:.1f}x" if is_directional_expansion else f"✗ {range_expansion_ratio:.1f}x",
                'Volume mendukung': f"✓ {volume_ratio:.1f}x" if has_volume_support else f"✗ {volume_ratio:.1f}x"
            }
        else:
            status = "ENTRY NOT CONFIRMED"
            status_color = "warning"
            narrative = f"Meskipun terdapat fase akumulasi sebelumnya, harga belum menunjukkan pelepasan ke atas yang konsisten. Change hari ini {today_change:+.1f}%, close di {today_close_pos*100:.0f}%, range {range_expansion_ratio:.1f}x. Entry bullish belum terkonfirmasi."
            education_note = "Niat akumulasi sudah ada, tapi eksekusi belum terlihat. Sabar menunggu konfirmasi."
            signals_detail = {
                'Breakout ke atas': f"✓ Change {today_change:+.1f}%" if is_breaking_up else f"✗ Change {today_change:+.1f}% (butuh >1.5%)",
                'Close kuat (>70%)': f"✓ Close di {today_close_pos*100:.0f}%" if is_close_strong else f"✗ Close di {today_close_pos*100:.0f}%",
                'Range melebar': f"✓ {range_expansion_ratio:.1f}x" if is_directional_expansion else f"✗ {range_expansion_ratio:.1f}x (butuh >1.3x)",
                'Volume mendukung': f"✓ {volume_ratio:.1f}x" if has_volume_support else f"✗ {volume_ratio:.1f}x (butuh >1.2x)"
            }

        entry_type = 'BULLISH'

    else:  # is_distribution
        # Looking for BEARISH breakout
        # 1. Price breaking down from compression
        is_breaking_down = today_change < -1.5  # Significant down move
        # 2. Close near low (decisive)
        is_close_weak = today_close_pos < 0.3  # Close in lower 30% of range
        # 3. Range expanding with direction
        is_directional_expansion = is_range_expanding and today_change < 0
        # 4. Volume supporting
        has_volume_support = is_volume_supporting

        # Count confirmation signals
        bearish_signals = {
            'breaking_down': is_breaking_down,
            'close_weak': is_close_weak,
            'range_expanding': is_directional_expansion,
            'volume_support': has_volume_support
        }
        confirmation_score = sum(1 for v in bearish_signals.values() if v)

        if confirmation_score >= 3:
            status = "ENTRY CONFIRMED — BEARISH"
            status_color = "danger"
            narrative = f"Setelah fase penahanan pasca kenaikan (distribusi), harga mulai melemah keluar dari area kurungan dengan pergerakan {today_change:+.1f}%. Range melebar {range_expansion_ratio:.1f}x ke bawah. Penutupan di {today_close_pos*100:.0f}% (dekat low), dengan volume {volume_ratio:.1f}x. Pelepasan ke bawah mulai dieksekusi."
            education_note = "Entry BEARISH terkonfirmasi. Ini konfirmasi bahwa niat distribusi mulai dieksekusi pasar."
            signals_detail = {
                'Breakout ke bawah': f"✓ Change {today_change:+.1f}%" if is_breaking_down else f"✗ Change {today_change:+.1f}%",
                'Close lemah (<30%)': f"✓ Close di {today_close_pos*100:.0f}%" if is_close_weak else f"✗ Close di {today_close_pos*100:.0f}%",
                'Range melebar': f"✓ {range_expansion_ratio:.1f}x" if is_directional_expansion else f"✗ {range_expansion_ratio:.1f}x",
                'Volume mendukung': f"✓ {volume_ratio:.1f}x" if has_volume_support else f"✗ {volume_ratio:.1f}x"
            }
        else:
            status = "ENTRY NOT CONFIRMED"
            status_color = "warning"
            narrative = f"Meskipun terdapat fase distribusi sebelumnya, harga belum menunjukkan pelepasan ke bawah yang konsisten. Change hari ini {today_change:+.1f}%, close di {today_close_pos*100:.0f}%, range {range_expansion_ratio:.1f}x. Entry bearish belum terkonfirmasi."
            education_note = "Niat distribusi sudah ada, tapi eksekusi belum terlihat. Sabar menunggu konfirmasi."
            signals_detail = {
                'Breakout ke bawah': f"✓ Change {today_change:+.1f}%" if is_breaking_down else f"✗ Change {today_change:+.1f}% (butuh <-1.5%)",
                'Close lemah (<30%)': f"✓ Close di {today_close_pos*100:.0f}%" if is_close_weak else f"✗ Close di {today_close_pos*100:.0f}%",
                'Range melebar': f"✓ {range_expansion_ratio:.1f}x" if is_directional_expansion else f"✗ {range_expansion_ratio:.1f}x (butuh >1.3x)",
                'Volume mendukung': f"✓ {volume_ratio:.1f}x" if has_volume_support else f"✗ {volume_ratio:.1f}x (butuh >1.2x)"
            }

        entry_type = 'BEARISH'

    return {
        'active': True,
        'status': status,
        'status_color': status_color,
        'narrative': narrative,
        'education_note': education_note,
        'signals': signals_detail,
        'entry_type': entry_type,
        'confirmation_score': confirmation_score,
        'metrics': {
            'today_change': f"{today_change:+.1f}%",
            'close_position': f"{today_close_pos*100:.0f}%",
            'range_expansion': f"{range_expansion_ratio:.1f}x",
            'volume_ratio': f"{volume_ratio:.1f}x",
            'today_range_pct': f"{today_range_pct:.1f}%"
        },
        'point4_status': point4_status
    }


def analyze_risk_exit_management(point5_result: dict, multiday_data: list, snapshot: dict) -> dict:
    """
    POINT 6 - Risk, Exit & Trade Management
    Mengelola posisi setelah Entry Confirmed (bukan cari sinyal baru).

    ATURAN ARSITEKTUR:
    - Point 6 HANYA aktif jika Point 5 = ENTRY CONFIRMED
    - Point 6 bukan prediksi target, tapi aturan manajemen

    Returns:
    - Invalidation: batas salah (jika ditembus, tesis runtuh)
    - Hold Management: SEHAT / WASPADA / TIDAK SEHAT
    - Exit: DEFENSIF (stop) atau PROTEKSI (take profit)
    """

    # ========== GATE CHECK: Point 5 harus ENTRY CONFIRMED ==========
    point5_status = point5_result.get('status', '')
    point5_active = point5_result.get('active', False)
    entry_type = point5_result.get('entry_type', None)

    is_entry_confirmed = 'ENTRY CONFIRMED' in point5_status.upper()

    if not is_entry_confirmed:
        return {
            'active': False,
            'status': 'POINT 6 TIDAK AKTIF',
            'status_color': 'secondary',
            'reason': 'Point 5 belum mengkonfirmasi entry. Tidak ada posisi untuk dikelola.',
            'narrative': 'Manajemen risiko dan exit hanya relevan setelah entry terkonfirmasi. Tanpa entry yang valid, Point 6 tidak boleh "mengarang exit".',
            'education_note': 'Point 6 hanya aktif setelah Point 5 menyatakan ENTRY CONFIRMED. Ini mencegah manajemen posisi yang tidak ada.',
            'hold_status': None,
            'invalidation': None,
            'exit_type': None,
            'checklist': {}
        }

    # ========== GET DATA FOR ANALYSIS ==========
    if not multiday_data or len(multiday_data) < 5:
        return {
            'active': True,
            'status': 'DATA TIDAK CUKUP',
            'status_color': 'secondary',
            'reason': 'Data tidak mencukupi untuk analisis manajemen posisi.',
            'narrative': 'Minimal 5 hari data diperlukan untuk menentukan level invalidation dan manajemen posisi.',
            'education_note': 'Manajemen risiko membutuhkan konteks multi-hari.',
            'hold_status': None,
            'invalidation': None,
            'exit_type': None,
            'checklist': {}
        }

    is_bullish = entry_type == 'BULLISH'
    is_bearish = entry_type == 'BEARISH'

    # Latest data
    today = multiday_data[-1]
    yesterday = multiday_data[-2]

    # Calculate key levels from compression phase (last 5-7 days)
    compression_days = multiday_data[-7:-1] if len(multiday_data) >= 7 else multiday_data[:-1]

    # Find invalidation level
    if is_bullish:
        # For bullish: invalidation is below the compression low
        compression_low = min(d['low'] for d in compression_days)
        invalidation_level = compression_low
        invalidation_desc = f"di bawah Rp {compression_low:,.0f} (low fase penahanan)"
    else:
        # For bearish: invalidation is above the compression high
        compression_high = max(d['high'] for d in compression_days)
        invalidation_level = compression_high
        invalidation_desc = f"di atas Rp {compression_high:,.0f} (high fase penahanan)"

    # ========== HOLD MANAGEMENT ANALYSIS ==========
    today_close = today['close']
    today_change = today['change']
    today_range = today['high'] - today['low']
    today_close_pos = (today['close'] - today['low']) / today_range if today_range > 0 else 0.5

    # Calculate trend metrics
    recent_closes = [d['close'] for d in multiday_data[-5:]]
    recent_changes = [d['change'] for d in multiday_data[-3:]]
    avg_recent_change = sum(recent_changes) / len(recent_changes) if recent_changes else 0

    # Volume analysis
    recent_volumes = [d['volume'] for d in multiday_data[-5:]]
    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else today['volume']
    volume_ratio = today['volume'] / avg_volume if avg_volume > 0 else 1

    # Check if still above/below invalidation
    # Activity supporting or weakening
    # For bullish: high volume on up days is good, high volume on down days is bad
    up_days_volume = sum(d['volume'] for d in multiday_data[-5:] if d['change'] > 0)
    down_days_volume = sum(d['volume'] for d in multiday_data[-5:] if d['change'] < 0)

    if is_bullish:
        thesis_valid = today_close > invalidation_level
        moving_in_direction = avg_recent_change > 0
        close_strength = today_close_pos > 0.5
        activity_supporting = up_days_volume > down_days_volume

        # Check for distribution signs (failure to make new highs)
        recent_highs = [d['high'] for d in multiday_data[-3:]]
        failing_highs = recent_highs[-1] < max(recent_highs[:-1]) if len(recent_highs) > 1 else False

        # Count weak closes (close in lower 40% of range)
        weak_close_count = 0
        for d in multiday_data[-3:]:
            rng = d['high'] - d['low']
            if rng > 0:
                close_pos = (d['close'] - d['low']) / rng
                if close_pos < 0.4:
                    weak_close_count += 1
        weak_closes = weak_close_count >= 2

        opposite_phase_signs = failing_highs or weak_closes
    else:
        thesis_valid = today_close < invalidation_level
        moving_in_direction = avg_recent_change < 0
        close_strength = today_close_pos < 0.5
        activity_supporting = down_days_volume > up_days_volume

        # Check for accumulation signs (failure to make new lows)
        recent_lows = [d['low'] for d in multiday_data[-3:]]
        failing_lows = recent_lows[-1] > min(recent_lows[:-1]) if len(recent_lows) > 1 else False

        # Count strong closes (close in upper 60% of range)
        strong_close_count = 0
        for d in multiday_data[-3:]:
            rng = d['high'] - d['low']
            if rng > 0:
                close_pos = (d['close'] - d['low']) / rng
                if close_pos > 0.6:
                    strong_close_count += 1
        strong_closes = strong_close_count >= 2

        opposite_phase_signs = failing_lows or strong_closes

    # ========== DETERMINE HOLD STATUS ==========
    checklist = {
        'thesis_valid': thesis_valid,
        'moving_in_direction': moving_in_direction,
        'opposite_phase_signs': opposite_phase_signs,
        'activity_supporting': activity_supporting
    }

    # Count positive signals
    positive_count = sum([
        thesis_valid,
        moving_in_direction,
        not opposite_phase_signs,
        activity_supporting
    ])

    # Determine status
    if not thesis_valid:
        # Invalidation breached
        hold_status = "EXIT (Defensif)"
        hold_status_color = "danger"
        exit_type = "DEFENSIF"
        if is_bullish:
            hold_narrative = f"Tesis bullish BATAL. Harga telah menembus area penahanan {invalidation_desc}. Tekanan jual kembali efektif dan fase akumulasi gagal. KELUAR dari posisi."
        else:
            hold_narrative = f"Tesis bearish BATAL. Harga telah menembus area penahanan {invalidation_desc}. Dorongan beli kembali efektif dan fase distribusi gagal. KELUAR dari posisi."
        education_note = "Exit defensif adalah perlindungan modal. Salah cepat selesai lebih baik daripada salah berkepanjangan."

    elif positive_count >= 3:
        # Healthy hold
        hold_status = "HOLD (Sehat)"
        hold_status_color = "success"
        exit_type = None
        if is_bullish:
            hold_narrative = f"Posisi masih VALID. Harga tetap di atas area penahanan (Rp {invalidation_level:,.0f}), bergerak searah tesis, dan belum menunjukkan tanda distribusi. Aktivitas pasar mendukung. Lanjutkan hold."
        else:
            hold_narrative = f"Posisi masih VALID. Harga tetap di bawah area penahanan (Rp {invalidation_level:,.0f}), bergerak searah tesis, dan belum menunjukkan tanda akumulasi. Aktivitas pasar mendukung. Lanjutkan hold."
        education_note = "Hold sehat berarti tesis masih berjalan. Jangan keluar hanya karena profit kecil."

    elif positive_count == 2:
        # Cautious hold
        hold_status = "HOLD (Waspada)"
        hold_status_color = "warning"
        exit_type = None
        if is_bullish:
            hold_narrative = f"Posisi belum batal, namun muncul tanda kehilangan momentum. Harga masih di atas Rp {invalidation_level:,.0f}, tapi {'' if moving_in_direction else 'tidak lagi bergerak naik, '}{'' if not opposite_phase_signs else 'mulai muncul tanda distribusi kecil, '}{'' if activity_supporting else 'aktivitas jual meningkat'}. Siapkan pengurangan posisi jika memburuk."
        else:
            hold_narrative = f"Posisi belum batal, namun muncul tanda kehilangan momentum. Harga masih di bawah Rp {invalidation_level:,.0f}, tapi {'' if moving_in_direction else 'tidak lagi bergerak turun, '}{'' if not opposite_phase_signs else 'mulai muncul tanda akumulasi kecil, '}{'' if activity_supporting else 'aktivitas beli meningkat'}. Siapkan pengurangan posisi jika memburuk."
        education_note = "Waspada bukan berarti panik. Tapi mulai siapkan skenario exit jika kondisi memburuk."

    else:
        # Unhealthy / Take profit zone
        hold_status = "TAKE PROFIT / REDUCE"
        hold_status_color = "info"
        exit_type = "PROTEKSI"
        if is_bullish:
            hold_narrative = f"Meskipun tesis belum batal secara teknis, muncul banyak tanda kelemahan: momentum hilang, tanda distribusi muncul, dan aktivitas tidak lagi mendukung. Pertimbangkan ambil profit atau kurangi posisi untuk melindungi keuntungan."
        else:
            hold_narrative = f"Meskipun tesis belum batal secara teknis, muncul banyak tanda kelemahan: momentum hilang, tanda akumulasi muncul, dan aktivitas tidak lagi mendukung. Pertimbangkan ambil profit atau kurangi posisi untuk melindungi keuntungan."
        education_note = "Exit proteksi adalah kematangan. Profit yang direalisasi tidak bisa hilang."

    # Build checklist descriptions
    checklist_detail = {}
    if is_bullish:
        checklist_detail['Tesis masih valid?'] = f"{'✓ Ya' if thesis_valid else '✗ Tidak'} — harga {'masih di atas' if thesis_valid else 'sudah di bawah'} Rp {invalidation_level:,.0f}"
        checklist_detail['Bergerak searah tesis?'] = f"{'✓ Ya' if moving_in_direction else '✗ Tidak'} — rata-rata change 3 hari: {avg_recent_change:+.2f}%"
        checklist_detail['Tanda distribusi muncul?'] = f"{'✗ Ya (buruk)' if opposite_phase_signs else '✓ Tidak'} — {'gagal buat high baru / close lemah berulang' if opposite_phase_signs else 'belum ada tanda distribusi'}"
        checklist_detail['Aktivitas mendukung?'] = f"{'✓ Ya' if activity_supporting else '✗ Tidak'} — volume up-days {'>' if activity_supporting else '<'} down-days"
    else:
        checklist_detail['Tesis masih valid?'] = f"{'✓ Ya' if thesis_valid else '✗ Tidak'} — harga {'masih di bawah' if thesis_valid else 'sudah di atas'} Rp {invalidation_level:,.0f}"
        checklist_detail['Bergerak searah tesis?'] = f"{'✓ Ya' if moving_in_direction else '✗ Tidak'} — rata-rata change 3 hari: {avg_recent_change:+.2f}%"
        checklist_detail['Tanda akumulasi muncul?'] = f"{'✗ Ya (buruk)' if opposite_phase_signs else '✓ Tidak'} — {'gagal buat low baru / close kuat berulang' if opposite_phase_signs else 'belum ada tanda akumulasi'}"
        checklist_detail['Aktivitas mendukung?'] = f"{'✓ Ya' if activity_supporting else '✗ Tidak'} — volume down-days {'>' if activity_supporting else '<'} up-days"

    return {
        'active': True,
        'status': hold_status,
        'status_color': hold_status_color,
        'narrative': hold_narrative,
        'education_note': education_note,
        'entry_type': entry_type,
        'hold_status': hold_status,
        'invalidation': {
            'level': invalidation_level,
            'description': invalidation_desc,
            'breached': not thesis_valid
        },
        'exit_type': exit_type,
        'checklist': checklist_detail,
        'checklist_raw': checklist,
        'positive_signals': positive_count,
        'metrics': {
            'today_close': f"Rp {today_close:,.0f}",
            'today_change': f"{today_change:+.1f}%",
            'avg_3d_change': f"{avg_recent_change:+.2f}%",
            'volume_ratio': f"{volume_ratio:.1f}x",
            'invalidation_level': f"Rp {invalidation_level:,.0f}"
        }
    }


def create_accumulation_page(stock_code='CDIA'):
    """Create Accumulation Analysis page - POINT 1, 2, 3, 4, 5, & 6:
    - Point 1: Market Snapshot (EOD) - Hari ini hari apa?
    - Point 2: Price Movement Anatomy - Harga bergerak dengan cara apa?
    - Point 3: Compression & Absorption - Apakah ada fase penahanan/penyerapan?
    - Point 4: Akumulasi & Distribusi - Jika ditahan, untuk tujuan apa?
    - Point 5: Entry Confirmation - Apakah niat mulai dieksekusi?
    - Point 6: Risk, Exit & Trade Management - Bagaimana mengelola posisi?
    """
    try:
        # Get market snapshot data
        snapshot = get_market_snapshot_data(stock_code)

        if not snapshot:
            return html.Div([
                dbc.Alert(f"Data tidak tersedia untuk {stock_code}", color="warning"),
                html.P("Pastikan data sudah diupload dengan benar")
            ])

        # Generate narratives
        narrative = generate_market_narrative(snapshot)

        # Determine day significance
        conclusion = determine_day_significance(snapshot)

        # Generate comparison with previous day
        comparison = generate_comparison_narrative(snapshot)

        # POINT 2: Price Movement Anatomy
        anatomy = analyze_price_movement_anatomy(snapshot)

        # POINT 3: Compression & Absorption (multi-day analysis)
        multiday_data = get_multiday_data(stock_code, days=10)
        point3 = analyze_compression_absorption(multiday_data)

        # POINT 4: Akumulasi & Distribusi (berdasarkan Point 3)
        point4 = analyze_accumulation_distribution(point3, multiday_data)

        # POINT 5: Entry Confirmation (berdasarkan Point 4)
        point5 = analyze_entry_confirmation(point4, point3, multiday_data, snapshot)

        # POINT 6: Risk, Exit & Trade Management (berdasarkan Point 5)
        point6 = analyze_risk_exit_management(point5, multiday_data, snapshot)

        # V6 ANALYSIS - Adaptive Sideways & Phase Detection
        v6_data = get_v6_analysis(stock_code)
        v6_sideways = v6_data.get('sideways', {}) if not v6_data.get('error') else {}
        v6_phase = v6_data.get('phase', {}) if not v6_data.get('error') else {}
        v6_entry = v6_data.get('entry', {}) if not v6_data.get('error') else {}

        # V8 ANALYSIS - ATR-Quality S/R (untuk PTRO, CBDK, BREN, BRPT, CDIA)
        v8_data = None
        if stock_code.upper() in ['PTRO', 'CBDK', 'BREN', 'BRPT', 'CDIA']:
            try:
                v8_data = get_strong_sr_analysis(stock_code)
            except Exception as e:
                print(f"V8 Analysis error for {stock_code}: {e}")
                v8_data = None

        # WEEKLY ANALYSIS - 4 weeks historical
        weekly_data = get_weekly_analysis(stock_code)
        weeks = weekly_data.get('weeks', {})

        # Format values for display
        def format_rupiah(val):
            abs_val = abs(val)
            sign = "-" if val < 0 else ""
            if abs_val >= 1e12:
                return f"Rp {sign}{abs_val/1e12:.2f}T"
            elif abs_val >= 1e9:
                return f"Rp {sign}{abs_val/1e9:.2f}B"
            elif abs_val >= 1e6:
                return f"Rp {sign}{abs_val/1e6:.2f}M"
            else:
                return f"Rp {val:,.0f}"

        def format_volume(val):
            if val >= 1e9:
                return f"{val/1e9:.2f}B"
            elif val >= 1e6:
                return f"{val/1e6:.2f}M"
            elif val >= 1e3:
                return f"{val/1e3:.1f}K"
            else:
                return f"{val:,.0f}"

        # Determine colors based on values
        change_color = "success" if snapshot['change'] > 0 else ("danger" if snapshot['change'] < 0 else "secondary")
        foreign_color = "success" if snapshot['net_foreign'] > 0 else ("danger" if snapshot['net_foreign'] < 0 else "secondary")

        # Close vs Avg color
        close_vs_avg_color = "success" if snapshot['close'] > snapshot['avg'] else "danger"

        # Activity level color
        value_ratio = snapshot['value'] / snapshot['avg_value_20d'] if snapshot['avg_value_20d'] > 0 else 1
        activity_color = "success" if value_ratio > 1.2 else ("warning" if value_ratio > 0.8 else "danger")

    except Exception as e:
        return html.Div([
            dbc.Alert(f"Error loading Market Snapshot for {stock_code}: {str(e)}", color="danger"),
            html.P("Pastikan data sudah diupload dengan benar")
        ])

    return html.Div([
        # Page Header
        html.Div([
            html.H4([
                html.I(className="fas fa-chart-bar me-2"),
                f"Market Snapshot - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_submenu_nav('accumulation', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # ========== DATE IDENTIFIER ==========
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.I(className="fas fa-calendar-day me-2 text-info"),
                            html.Span("Tanggal Data", className="text-muted small"),
                        ]),
                        html.H3(snapshot['date'].strftime('%d %B %Y'), className="mb-0 text-info"),
                        html.Small(snapshot['date'].strftime('%A'), className="text-muted")
                    ], md=4),
                    dbc.Col([
                        html.Div([
                            html.I(className="fas fa-info-circle me-2 text-warning"),
                            html.Span("Tujuan Snapshot", className="text-muted small"),
                        ]),
                        html.P("Menjawab 3 pertanyaan dasar: Bagaimana harga bergerak? Berat atau ringan? Siapa jadi angin (foreign)?",
                               className="mb-0 small")
                    ], md=8),
                ], className="align-items-center")
            ])
        ], className="mb-4", style={"borderLeft": "4px solid var(--bs-info)"}),

        # ========== PRICE SECTION: Close & Change ==========
        dbc.Row([
            # Close Price & Change
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-dollar-sign me-2"),
                        html.Strong("Harga Penutupan & Arah Hari Ini")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("CLOSE", className="text-muted d-block"),
                                html.H2(f"Rp {snapshot['close']:,.0f}", className=f"text-{change_color} mb-0 fw-bold"),
                            ], width=6),
                            dbc.Col([
                                html.Small("CHANGE", className="text-muted d-block"),
                                html.H2(f"{snapshot['change']:+.2f}%", className=f"text-{change_color} mb-0 fw-bold"),
                                html.Small(f"({snapshot['change_value']:+,.0f})", className="text-muted")
                            ], width=6),
                        ]),
                        html.Hr(),
                        html.Div([
                            html.I(className=f"fas fa-{'arrow-up' if snapshot['change'] > 0 else ('arrow-down' if snapshot['change'] < 0 else 'minus')} me-2"),
                            html.Span(
                                "Hari Naik - Pasar Mengangkat" if snapshot['change'] > 0.5 else
                                ("Hari Turun - Pasar Menggulung" if snapshot['change'] < -0.5 else "Hari Datar - Pasar Mengunci"),
                                className="fw-bold"
                            )
                        ], className=f"text-{change_color} text-center p-2 rounded",
                           style={"backgroundColor": f"rgba({'40,167,69' if change_color == 'success' else ('220,53,69' if change_color == 'danger' else '108,117,125')}, 0.1)"})
                    ])
                ], className="h-100")
            ], md=6, className="mb-3"),

            # OHLC Structure
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-chart-candlestick me-2"),
                        html.Strong("Struktur Pergerakan Harga (OHLC)")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("OPEN", className="text-muted d-block"),
                                html.H5(f"{snapshot['open']:,.0f}", className="mb-0"),
                            ], width=3, className="text-center"),
                            dbc.Col([
                                html.Small("HIGH", className="text-muted d-block"),
                                html.H5(f"{snapshot['high']:,.0f}", className="mb-0 text-success"),
                            ], width=3, className="text-center"),
                            dbc.Col([
                                html.Small("LOW", className="text-muted d-block"),
                                html.H5(f"{snapshot['low']:,.0f}", className="mb-0 text-danger"),
                            ], width=3, className="text-center"),
                            dbc.Col([
                                html.Small("CLOSE", className="text-muted d-block"),
                                html.H5(f"{snapshot['close']:,.0f}", className=f"mb-0 text-{change_color}"),
                            ], width=3, className="text-center"),
                        ]),
                        html.Hr(),
                        # Close position indicator
                        html.Div([
                            html.Small("Posisi Close dalam Range:", className="text-muted d-block mb-2"),
                            dbc.Progress([
                                dbc.Progress(value=(snapshot['close']-snapshot['low'])/(snapshot['high']-snapshot['low'])*100 if snapshot['high'] > snapshot['low'] else 50,
                                            color=change_color, bar=True)
                            ], className="mb-2", style={"height": "20px"}),
                            html.Small(
                                "Close dekat High - Pembeli menang" if snapshot['high'] > snapshot['low'] and (snapshot['close']-snapshot['low'])/(snapshot['high']-snapshot['low']) > 0.7 else
                                ("Close dekat Low - Penjual menang" if snapshot['high'] > snapshot['low'] and (snapshot['close']-snapshot['low'])/(snapshot['high']-snapshot['low']) < 0.3 else
                                "Close di tengah - Tarik-menarik"),
                                className="text-muted"
                            )
                        ])
                    ])
                ], className="h-100")
            ], md=6, className="mb-3"),
        ]),

        # ========== AVG PRICE & ACTIVITY ==========
        dbc.Row([
            # Avg Price Analysis
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-balance-scale me-2"),
                        html.Strong("Harga Rata-rata (Kualitas Penutupan)")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("AVG PRICE", className="text-muted d-block"),
                                html.H3(f"Rp {snapshot['avg']:,.0f}", className="mb-0"),
                            ], width=6),
                            dbc.Col([
                                html.Small("CLOSE vs AVG", className="text-muted d-block"),
                                html.H3(
                                    f"{((snapshot['close']-snapshot['avg'])/snapshot['avg']*100):+.2f}%" if snapshot['avg'] > 0 else "N/A",
                                    className=f"mb-0 text-{close_vs_avg_color}"
                                ),
                            ], width=6),
                        ]),
                        html.Hr(),
                        html.Div([
                            html.I(className=f"fas fa-{'thumbs-up' if snapshot['close'] > snapshot['avg'] else 'thumbs-down'} me-2"),
                            html.Span(
                                "Penutupan KUAT - Close di atas rata-rata transaksi" if snapshot['close'] > snapshot['avg'] else
                                "Penutupan LEMAH - Close di bawah rata-rata transaksi",
                                className="fw-bold"
                            )
                        ], className=f"text-{close_vs_avg_color} text-center p-2 rounded",
                           style={"backgroundColor": f"rgba({'40,167,69' if close_vs_avg_color == 'success' else '220,53,69'}, 0.1)"})
                    ])
                ], className="h-100")
            ], md=6, className="mb-3"),

            # Market Activity
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-chart-area me-2"),
                        html.Strong("Aktivitas Pasar (Bobot Pergerakan)")
                    ], className="bg-dark"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("VALUE", className="text-muted d-block"),
                                html.H5(format_rupiah(snapshot['value']), className="mb-1"),
                                html.Small(f"{value_ratio:.1f}x avg", className=f"text-{activity_color}")
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("VOLUME", className="text-muted d-block"),
                                html.H5(format_volume(snapshot['volume']), className="mb-1"),
                                html.Small("lot", className="text-muted")
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("FREQ", className="text-muted d-block"),
                                html.H5(f"{snapshot['frequency']:,}", className="mb-1"),
                                html.Small("transaksi", className="text-muted")
                            ], width=4, className="text-center"),
                        ]),
                        html.Hr(),
                        html.Div([
                            html.I(className=f"fas fa-{'fire' if activity_color == 'success' else ('minus' if activity_color == 'warning' else 'snowflake')} me-2"),
                            html.Span(
                                "RAMAI - Pergerakan berbobot & valid" if value_ratio > 1.2 else
                                ("NORMAL - Pergerakan standar" if value_ratio > 0.8 else "SEPI - Pergerakan ringan, mudah dipengaruhi"),
                                className="fw-bold"
                            )
                        ], className=f"text-{activity_color} text-center p-2 rounded",
                           style={"backgroundColor": f"rgba({'40,167,69' if activity_color == 'success' else ('255,193,7' if activity_color == 'warning' else '220,53,69')}, 0.1)"})
                    ])
                ], className="h-100")
            ], md=6, className="mb-3"),
        ]),

        # ========== FOREIGN FLOW ==========
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-globe me-2"),
                html.Strong("Foreign Flow (Konteks Asing)")
            ], className="bg-dark"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Small("F BUY", className="text-muted d-block"),
                        html.H4(format_rupiah(snapshot['foreign_buy']), className="mb-0 text-success"),
                    ], width=4, className="text-center"),
                    dbc.Col([
                        html.Small("F SELL", className="text-muted d-block"),
                        html.H4(format_rupiah(snapshot['foreign_sell']), className="mb-0 text-danger"),
                    ], width=4, className="text-center"),
                    dbc.Col([
                        html.Small("NET FOREIGN", className="text-muted d-block"),
                        html.H4(format_rupiah(snapshot['net_foreign']), className=f"mb-0 text-{foreign_color} fw-bold"),
                    ], width=4, className="text-center"),
                ]),
                html.Hr(),
                html.Div([
                    html.I(className=f"fas fa-{'plane-arrival' if snapshot['net_foreign'] > 0 else ('plane-departure' if snapshot['net_foreign'] < 0 else 'minus')} me-2"),
                    html.Span(
                        "Asing NET BUY - Mendukung hari ini" if snapshot['net_foreign'] > 0 else
                        ("Asing NET SELL - Menekan hari ini" if snapshot['net_foreign'] < 0 else "Asing NETRAL"),
                        className="fw-bold"
                    )
                ], className=f"text-{foreign_color} text-center p-2 rounded mb-3",
                   style={"backgroundColor": f"rgba({'40,167,69' if foreign_color == 'success' else ('220,53,69' if foreign_color == 'danger' else '108,117,125')}, 0.1)"}),

                # Anomaly detection
                html.Div([
                    html.Small("Anomali:", className="text-warning d-block"),
                    html.Span(
                        "⚠️ Asing jual tapi harga tidak jatuh → Ada PENAHAN" if snapshot['net_foreign'] < 0 and snapshot['change'] > 0 else
                        ("⚠️ Asing beli tapi harga tidak kuat → Ada PELEPAS" if snapshot['net_foreign'] > 0 and snapshot['change'] < 0 else
                        "✓ Tidak ada anomali - harga mengikuti arus asing"),
                        className="small"
                    )
                ], className="text-center p-2 rounded", style={"backgroundColor": "rgba(255,193,7,0.1)"}) if (snapshot['net_foreign'] < 0 and snapshot['change'] > 0) or (snapshot['net_foreign'] > 0 and snapshot['change'] < 0) else None
            ])
        ], className="mb-4"),

        # ========================================================================
        # CONDITIONAL: V8 for 5 emiten, V6 for others
        # ========================================================================
        html.Hr(className="my-4"),

        # V8 ATR-QUALITY S/R ANALYSIS (only for PTRO, CBDK, BREN, BRPT, CDIA)
        html.Div([
            html.Div([
                html.H4([
                    html.I(className="fas fa-crosshairs me-2"),
                    "ANALISIS V8 — ATR-QUALITY SUPPORT & RESISTANCE"
                ], className="text-info mb-1"),
                html.P("Metode V8: ATR(14) tolerance + Pivot fractal 3L/3R + Filter Touches≥3, Quality≥50%", className="text-muted mb-0 small")
            ], className="mb-4"),

            # V8 Chart
            create_v8_sr_chart(stock_code, v8_data, days=60) if v8_data and not v8_data.get('error') else html.Div(),

            # V8 Status Card
            create_v8_sr_card(stock_code, v8_data) if v8_data and not v8_data.get('error') else html.Div(),

            # V8 Action Reason
            dbc.Alert([
                html.I(className="fas fa-bullhorn me-2"),
                html.Strong("Kesimpulan V8: "),
                html.Span(v8_data.get('action_reason', 'Data tidak tersedia') if v8_data else '')
            ], color="success" if v8_data and v8_data.get('action') == 'ENTRY' else
                   "warning" if v8_data and v8_data.get('action') == 'WAIT' else
                   "danger" if v8_data and v8_data.get('action') == 'AVOID' else "secondary",
               className="mb-4") if v8_data and not v8_data.get('error') else html.Div(),

            # V8 Formula Explanation
            dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                html.Strong("Formula V8: "),
                "Tolerance = 0.5 × ATR(14) | ",
                "Pivot = Fractal 3L/3R | ",
                "Filter: Touches ≥ 3, Quality ≥ 50% | ",
                "Entry = Near Support (≤5%) + Valid Phase + Quality OK"
            ], color="secondary", className="mb-4 text-center small"),
        ]) if stock_code.upper() in ['PTRO', 'CBDK', 'BREN', 'BRPT', 'CDIA'] else html.Div(),

        # ========================================================================
        # ANALISIS AKUMULASI 4 MINGGU (V6 FORMULA)
        # Volume di bawah midpoint vs di atas midpoint
        # ========================================================================
        html.Hr(className="my-4"),

        html.Div([
            html.H4([
                html.I(className="fas fa-layer-group me-2"),
                "ANALISIS AKUMULASI 4 MINGGU TERAKHIR"
            ], className="text-warning mb-1"),
            html.P("Deteksi akumulasi/distribusi per minggu menggunakan formula V6 (Volume Lower vs Upper)", className="text-muted mb-0 small")
        ], className="mb-4"),

        # ========== WEEKLY ACCUMULATION CARDS ==========
        dbc.Row([
            # Helper function for creating weekly card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span(weeks.get(w, {}).get('phase_icon', '⚪'), className="me-2", style={"fontSize": "20px"}),
                        html.Strong(f"{'Minggu Ini' if w == 1 else f'{w} Minggu Lalu'}"),
                        dbc.Badge(
                            weeks.get(w, {}).get('phase', 'N/A'),
                            color=weeks.get(w, {}).get('phase_color', 'secondary'),
                            className="ms-2"
                        )
                    ], className=f"bg-{weeks.get(w, {}).get('phase_color', 'secondary')} text-white"),
                    dbc.CardBody([
                        # Date range
                        html.Small(f"{weeks.get(w, {}).get('start_date', '')}-{weeks.get(w, {}).get('end_date', '')}", className="text-muted d-block text-center mb-2"),

                        # Volume Ratio Bar Chart - Using Bootstrap Progress
                        html.Div([
                            html.Div([
                                html.Small("Lower", className="text-success"),
                                html.Small("Upper", className="text-danger float-end"),
                            ], className="mb-1"),
                            dbc.Progress([
                                dbc.Progress(
                                    value=weeks.get(w, {}).get('vol_lower', 0) / max(1, weeks.get(w, {}).get('vol_lower', 0) + weeks.get(w, {}).get('vol_upper', 0)) * 100,
                                    color="success",
                                    bar=True,
                                    style={"height": "30px"}
                                ),
                                dbc.Progress(
                                    value=weeks.get(w, {}).get('vol_upper', 0) / max(1, weeks.get(w, {}).get('vol_lower', 0) + weeks.get(w, {}).get('vol_upper', 0)) * 100,
                                    color="danger",
                                    bar=True,
                                    style={"height": "30px"}
                                ),
                            ], style={"height": "30px"}),
                        ], className="mb-3"),

                        # Volume Ratio Display
                        html.Div([
                            html.H3(f"{weeks.get(w, {}).get('vol_ratio', 0):.2f}x", className=f"text-{weeks.get(w, {}).get('phase_color', 'secondary')} mb-0 text-center fw-bold"),
                            html.Small("Vol Ratio", className="text-muted d-block text-center"),
                        ], className="mb-2 p-2 rounded", style={"backgroundColor": f"rgba({'40,167,69' if weeks.get(w, {}).get('phase') == 'ACCUMULATION' else '220,53,69' if weeks.get(w, {}).get('phase') == 'DISTRIBUTION' else '108,117,125'}, 0.2)"}),

                        # Metrics
                        dbc.Row([
                            dbc.Col([
                                html.Small("Vol Lower", className="text-muted d-block"),
                                html.Strong(f"{weeks.get(w, {}).get('vol_lower', 0)/1e6:.1f}M", className="text-success small")
                            ], width=6, className="text-center"),
                            dbc.Col([
                                html.Small("Vol Upper", className="text-muted d-block"),
                                html.Strong(f"{weeks.get(w, {}).get('vol_upper', 0)/1e6:.1f}M", className="text-danger small")
                            ], width=6, className="text-center"),
                        ], className="mb-2"),

                        # Net Market (Total) - based on vol_lower - vol_upper
                        html.Div([
                            html.Small("Net Market (Total)", className="text-muted d-block text-center"),
                            html.Strong([
                                html.Span(
                                    f"{'NET BUY' if weeks.get(w, {}).get('vol_lower', 0) > weeks.get(w, {}).get('vol_upper', 0) else 'NET SELL'} ",
                                    className=f"text-{'success' if weeks.get(w, {}).get('vol_lower', 0) > weeks.get(w, {}).get('vol_upper', 0) else 'danger'}"
                                ),
                                html.Span(
                                    f"{abs(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0))/100:,.0f} Lot",
                                    className=f"text-{'success' if weeks.get(w, {}).get('vol_lower', 0) > weeks.get(w, {}).get('vol_upper', 0) else 'danger'}"
                                )
                            ], className="d-block text-center small")
                        ], className="mb-1 p-1 rounded", style={"backgroundColor": f"rgba({'40,167,69' if weeks.get(w, {}).get('vol_lower', 0) > weeks.get(w, {}).get('vol_upper', 0) else '220,53,69'}, 0.1)"}),

                        # Net Foreign (in Lot)
                        html.Div([
                            html.Small("Net Foreign", className="text-muted d-block text-center"),
                            html.Strong([
                                html.Span(
                                    f"{'NET BUY' if weeks.get(w, {}).get('net_foreign_lot', 0) > 0 else 'NET SELL'} ",
                                    className=f"text-{'success' if weeks.get(w, {}).get('net_foreign_lot', 0) > 0 else 'danger'}"
                                ),
                                html.Span(
                                    f"{abs(weeks.get(w, {}).get('net_foreign_lot', 0)):,.0f} Lot",
                                    className=f"text-{'success' if weeks.get(w, {}).get('net_foreign_lot', 0) > 0 else 'danger'}"
                                )
                            ], className="d-block text-center small")
                        ], className="mb-2 p-1 rounded", style={"backgroundColor": f"rgba({'40,167,69' if weeks.get(w, {}).get('net_foreign_lot', 0) > 0 else '220,53,69'}, 0.1)"}),

                        html.Hr(className="my-2"),
                        html.Small([
                            f"Range: Rp {weeks.get(w, {}).get('low', 0):,.0f} - {weeks.get(w, {}).get('high', 0):,.0f}"
                        ], className="text-muted d-block text-center")
                    ])
                ], className="h-100", style={"border": f"2px solid var(--bs-{weeks.get(w, {}).get('phase_color', 'secondary')})"})
            ], md=6, lg=3, className="mb-3") for w in [1, 2, 3, 4]
        ]),

        # Weekly Accumulation Summary
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-pie me-2"),
                html.Strong("Ringkasan Akumulasi 4 Minggu")
            ], className="bg-warning text-dark"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6("Fase per Minggu", className="text-muted mb-2"),
                        html.Div([
                            html.Span(weeks.get(4, {}).get('phase_icon', '⚪'), style={"fontSize": "24px"}),
                            html.I(className="fas fa-arrow-right mx-2 text-muted"),
                            html.Span(weeks.get(3, {}).get('phase_icon', '⚪'), style={"fontSize": "24px"}),
                            html.I(className="fas fa-arrow-right mx-2 text-muted"),
                            html.Span(weeks.get(2, {}).get('phase_icon', '⚪'), style={"fontSize": "24px"}),
                            html.I(className="fas fa-arrow-right mx-2 text-muted"),
                            html.Span(weeks.get(1, {}).get('phase_icon', '⚪'), style={"fontSize": "24px"}),
                        ], className="text-center")
                    ], md=4),
                    dbc.Col([
                        html.H6("Avg Vol Ratio 4 Minggu", className="text-muted mb-2"),
                        html.H3(
                            f"{sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4:.2f}x",
                            className=f"text-{'success' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 3.0 else 'warning' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5 else 'danger' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 < 0.8 else 'secondary'} mb-0 text-center"
                        ),
                        html.Small(
                            "ACCUMULATION" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 3.0 else "WEAK ACC" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5 else "DISTRIBUTION" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 < 0.8 else "NEUTRAL",
                            className=f"text-{'success' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 3.0 else 'warning' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5 else 'danger' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 < 0.8 else 'secondary'} d-block text-center fw-bold"
                        )
                    ], md=4, className="text-center"),
                    dbc.Col([
                        html.H6("Net Foreign 4 Minggu", className="text-muted mb-2"),
                        html.H4(
                            f"{abs(sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5))):,.0f} Lot",
                            className=f"text-{'success' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'danger'} mb-0 text-center"
                        ),
                        html.Small(
                            f"{'NET BUY' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'NET SELL'}",
                            className=f"text-{'success' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'danger'} d-block text-center fw-bold"
                        )
                    ], md=4, className="text-center"),
                ]),
                html.Hr(className="my-2"),
                # Total Net Market
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Small("Net Market (Total) 4 Minggu", className="text-muted d-block"),
                            html.H5([
                                html.Span(
                                    f"{'NET BUY' if sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)) > 0 else 'NET SELL'} ",
                                    className=f"text-{'success' if sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)) > 0 else 'danger'}"
                                ),
                                html.Span(
                                    f"{abs(sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)))/100:,.0f} Lot",
                                    className=f"text-{'success' if sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)) > 0 else 'danger'}"
                                )
                            ], className="mb-0"),
                            html.Small("(Selisih Vol Lower - Vol Upper)", className="text-muted")
                        ], className="p-2 rounded text-center", style={"backgroundColor": f"rgba({'40,167,69' if sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)) > 0 else '220,53,69'}, 0.15)"})
                    ], md=12)
                ], className="mb-2"),
                html.Hr(className="my-2"),
                # Count phases
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span("🟢", style={"fontSize": "20px"}),
                            html.Strong(f" {sum(1 for w in range(1, 5) if weeks.get(w, {}).get('phase') == 'ACCUMULATION')} minggu", className="text-success"),
                            html.Small(" Akumulasi", className="text-muted")
                        ])
                    ], width=4, className="text-center"),
                    dbc.Col([
                        html.Div([
                            html.Span("⚪", style={"fontSize": "20px"}),
                            html.Strong(f" {sum(1 for w in range(1, 5) if weeks.get(w, {}).get('phase') == 'NEUTRAL')} minggu", className="text-secondary"),
                            html.Small(" Netral", className="text-muted")
                        ])
                    ], width=4, className="text-center"),
                    dbc.Col([
                        html.Div([
                            html.Span("🔴", style={"fontSize": "20px"}),
                            html.Strong(f" {sum(1 for w in range(1, 5) if weeks.get(w, {}).get('phase') == 'DISTRIBUTION')} minggu", className="text-danger"),
                            html.Small(" Distribusi", className="text-muted")
                        ])
                    ], width=4, className="text-center"),
                ])
            ])
        ], className="mb-4"),

        # ========================================================================
        # ANALISIS HUBUNGAN AKUMULASI & ZONA V11b1
        # ========================================================================
        html.Hr(className="my-4"),

        html.Div([
            html.H4([
                html.I(className="fas fa-crosshairs me-2"),
                "ANALISIS ZONA V11b1 & AKUMULASI"
            ], className="text-success mb-1"),
            html.P("Hubungan antara fase akumulasi dengan Support & Resistance zona V11b1", className="text-muted mb-0 small")
        ], className="mb-4") if stock_code.upper() in STOCK_ZONES else html.Div(),

        # V11b1 Zone Analysis Card
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-layer-group me-2"),
                html.Strong("Posisi Harga vs Zona V11b1"),
                dbc.Badge(f"{len(get_zones(stock_code))} Zona", color="info", className="ms-2")
            ], className="bg-success text-white"),
            dbc.CardBody([
                # Current Price Position
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Small("Harga Terakhir", className="text-muted d-block"),
                            html.H3(f"Rp {snapshot['close']:,.0f}", className="text-info mb-1"),
                            html.Small([
                                "Posisi: ",
                                html.Span(
                                    "DI DALAM ZONA" if any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) else
                                    "DI ATAS SEMUA ZONA" if snapshot['close'] > max(z['high'] for z in get_zones(stock_code).values()) else
                                    "DI BAWAH SEMUA ZONA" if snapshot['close'] < min(z['low'] for z in get_zones(stock_code).values()) else
                                    "DI ANTARA ZONA",
                                    className=f"fw-bold text-{'warning' if any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) else 'danger' if snapshot['close'] > max(z['high'] for z in get_zones(stock_code).values()) else 'success' if snapshot['close'] < min(z['low'] for z in get_zones(stock_code).values()) else 'info'}"
                                )
                            ])
                        ], className="text-center")
                    ], md=4),
                    dbc.Col([
                        html.Div([
                            html.Small("Support Aktif (V11b1)", className="text-muted d-block"),
                            html.H4([
                                html.Span(f"Z{min((znum for znum, z in get_zones(stock_code).items() if z['high'] <= snapshot['close']), default='-')}", className="text-success"),
                            ] if any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) else [
                                html.Span("Tidak ada", className="text-secondary")
                            ], className="mb-1"),
                            html.Small([
                                f"Rp {[z for znum, z in sorted(get_zones(stock_code).items(), reverse=True) if z['high'] <= snapshot['close']][0]['low']:,.0f} - {[z for znum, z in sorted(get_zones(stock_code).items(), reverse=True) if z['high'] <= snapshot['close']][0]['high']:,.0f}"
                            ] if any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) else ["-"], className="text-success")
                        ], className="text-center")
                    ], md=4),
                    dbc.Col([
                        html.Div([
                            html.Small("Resistance Aktif (V11b1)", className="text-muted d-block"),
                            html.H4([
                                html.Span(f"Z{min((znum for znum, z in get_zones(stock_code).items() if z['low'] >= snapshot['close']), default='-')}", className="text-danger"),
                            ] if any(z['low'] >= snapshot['close'] for z in get_zones(stock_code).values()) else [
                                html.Span("Tidak ada", className="text-secondary")
                            ], className="mb-1"),
                            html.Small([
                                f"Rp {[z for znum, z in sorted(get_zones(stock_code).items()) if z['low'] >= snapshot['close']][0]['low']:,.0f} - {[z for znum, z in sorted(get_zones(stock_code).items()) if z['low'] >= snapshot['close']][0]['high']:,.0f}"
                            ] if any(z['low'] >= snapshot['close'] for z in get_zones(stock_code).values()) else ["-"], className="text-danger")
                        ], className="text-center")
                    ], md=4),
                ]),
                html.Hr(),
                # Zones Table
                html.Div([
                    html.Table([
                        html.Thead([
                            html.Tr([
                                html.Th("Zona", className="text-center", style={"width": "15%"}),
                                html.Th("Range", className="text-center", style={"width": "35%"}),
                                html.Th("Status", className="text-center", style={"width": "25%"}),
                                html.Th("Jarak", className="text-center", style={"width": "25%"}),
                            ])
                        ]),
                        html.Tbody([
                            html.Tr([
                                html.Td(f"Z{znum}", className="text-center fw-bold"),
                                html.Td(f"Rp {z['low']:,.0f} - {z['high']:,.0f}", className="text-center"),
                                html.Td(
                                    dbc.Badge("INSIDE", color="warning") if z['low'] <= snapshot['close'] <= z['high'] else
                                    dbc.Badge("SUPPORT", color="success") if z['high'] < snapshot['close'] else
                                    dbc.Badge("RESISTANCE", color="danger"),
                                    className="text-center"
                                ),
                                html.Td(
                                    "0%" if z['low'] <= snapshot['close'] <= z['high'] else
                                    f"+{((snapshot['close'] - z['high']) / z['high'] * 100):.1f}%" if z['high'] < snapshot['close'] else
                                    f"-{((z['low'] - snapshot['close']) / snapshot['close'] * 100):.1f}%",
                                    className=f"text-center text-{'warning' if z['low'] <= snapshot['close'] <= z['high'] else 'success' if z['high'] < snapshot['close'] else 'danger'}"
                                ),
                            ]) for znum, z in sorted(get_zones(stock_code).items())
                        ])
                    ], className="table table-sm table-dark mb-0")
                ])
            ])
        ], className="mb-4", style={"border": "2px solid var(--bs-success)"}) if stock_code.upper() in STOCK_ZONES else html.Div(),

        # Combined Analysis Card
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-brain me-2"),
                html.Strong("Kesimpulan: Akumulasi + Zona V11b1")
            ], className="bg-warning text-dark"),
            dbc.CardBody([
                dbc.Row([
                    # Left: Accumulation Summary
                    dbc.Col([
                        html.Div([
                            html.H6("Fase Akumulasi (4 Minggu)", className="text-muted mb-2"),
                            html.Div([
                                html.Span(
                                    "🟢 AKUMULASI" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 3.0 else
                                    "🟡 WEAK ACC" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5 else
                                    "🔴 DISTRIBUSI" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 < 0.8 else
                                    "⚪ NETRAL",
                                    className=f"fw-bold text-{'success' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 3.0 else 'warning' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5 else 'danger' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 < 0.8 else 'secondary'}",
                                    style={"fontSize": "18px"}
                                )
                            ], className="mb-2"),
                            html.Small(f"Vol Ratio: {sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4:.2f}x", className="text-muted d-block"),
                            html.Small(f"Net Foreign: {'BUY' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'SELL'} {abs(sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5))):,.0f} Lot", className=f"text-{'success' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'danger'} d-block"),
                        ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(255,193,7,0.1)"})
                    ], md=4),
                    # Middle: Zone Position
                    dbc.Col([
                        html.Div([
                            html.H6("Posisi di Zona V11b1", className="text-muted mb-2"),
                            html.Div([
                                html.Span(
                                    "📍 DI SUPPORT" if any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) or (
                                        any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) and
                                        min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']) < 5
                                    ) else
                                    "📈 JAUH DARI ZONA" if snapshot['close'] > max(z['high'] for z in get_zones(stock_code).values()) else
                                    "📉 DI BAWAH ZONA" if snapshot['close'] < min(z['low'] for z in get_zones(stock_code).values()) else
                                    "📊 ANTARA ZONA",
                                    className="fw-bold",
                                    style={"fontSize": "18px"}
                                )
                            ], className="mb-2"),
                            html.Small([
                                "Jarak ke Support: ",
                                html.Span(
                                    f"{min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']):.1f}%"
                                    if any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) else "N/A",
                                    className="text-success fw-bold"
                                )
                            ], className="d-block"),
                            html.Small([
                                "Jarak ke Resistance: ",
                                html.Span(
                                    f"{min((z['low'] - snapshot['close']) / snapshot['close'] * 100 for z in get_zones(stock_code).values() if z['low'] >= snapshot['close']):.1f}%"
                                    if any(z['low'] >= snapshot['close'] for z in get_zones(stock_code).values()) else "N/A",
                                    className="text-danger fw-bold"
                                )
                            ], className="d-block"),
                        ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(40,167,69,0.1)"})
                    ], md=4),
                    # Right: Combined Signal
                    dbc.Col([
                        html.Div([
                            html.H6("Sinyal Gabungan", className="text-muted mb-2"),
                            html.Div([
                                html.Span(
                                    "✅ ENTRY ZONE" if (
                                        (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5) and
                                        (any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) or
                                         (any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) and
                                          min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']) < 5))
                                    ) else
                                    "👀 WATCH" if (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.2) else
                                    "⏸️ WAIT" if (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 >= 0.8) else
                                    "🚫 AVOID",
                                    className=f"fw-bold text-{'success' if (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5) and (any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) or (any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) and min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']) < 5)) else 'info' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.2 else 'warning' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 >= 0.8 else 'danger'}",
                                    style={"fontSize": "20px"}
                                )
                            ], className="mb-2"),
                            html.Small(
                                "Akumulasi + Near Support = Entry Signal" if (
                                    (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5) and
                                    (any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) or
                                     (any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) and
                                      min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']) < 5))
                                ) else
                                "Weak Acc, perlu konfirmasi zona" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.2 else
                                "Netral, tunggu sinyal lebih jelas" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 >= 0.8 else
                                "Distribusi, hindari entry",
                                className="text-muted d-block"
                            ),
                        ], className="text-center p-3 rounded", style={"backgroundColor": f"rgba({'40,167,69' if (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5) and (any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) or (any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) and min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']) < 5)) else '23,162,184' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.2 else '255,193,7' if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 >= 0.8 else '220,53,69'}, 0.15)"})
                    ], md=4),
                ]),
                html.Hr(),
                # Interpretation
                html.Div([
                    html.I(className="fas fa-info-circle me-2 text-info"),
                    html.Strong("Interpretasi: ", className="text-info"),
                    html.Span(
                        "Fase akumulasi terdeteksi DAN harga berada dekat zona support V11b1. Kondisi ideal untuk entry dengan SL di bawah zona." if (
                            (sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5) and
                            (any(z['low'] <= snapshot['close'] <= z['high'] for z in get_zones(stock_code).values()) or
                             (any(z['high'] <= snapshot['close'] for z in get_zones(stock_code).values()) and
                              min((snapshot['close'] - z['high']) / z['high'] * 100 for z in get_zones(stock_code).values() if z['high'] <= snapshot['close']) < 5))
                        ) else
                        "Sinyal akumulasi lemah. Harga perlu mendekati zona V11b1 untuk entry yang lebih aman." if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.2 else
                        "Fase netral/sideways. Tunggu konfirmasi akumulasi dan posisi harga di zona support." if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 >= 0.8 else
                        "Fase distribusi terdeteksi. Hindari entry, lebih baik wait atau reduce position.",
                        className="small"
                    )
                ], className="p-2 rounded", style={"backgroundColor": "rgba(23,162,184,0.1)"})
            ])
        ], className="mb-4", style={"border": "2px solid var(--bs-warning)"}) if stock_code.upper() in STOCK_ZONES else html.Div(),

        # Interpretation
        dbc.Alert([
            html.I(className="fas fa-lightbulb me-2"),
            html.Strong("Cara Membaca: "),
            "Vol Ratio > 4.0 = AKUMULASI KUAT (entry signal), Vol Ratio 1.5-4.0 = Weak Acc (observasi), Vol Ratio < 0.8 = Distribusi.",
            "Jika 3-4 minggu konsisten akumulasi, kemungkinan breakout ke atas lebih tinggi."
        ], color="info", className="mb-4"),

    ])


def create_company_profile_page(stock_code='CDIA'):
    """Create Company Profile page with attractive, colorful design"""
    try:
        profile = get_stock_profile(stock_code)
    except Exception as e:
        return html.Div([
            html.Div([
                html.H4([
                    html.I(className="fas fa-building me-2"),
                    f"Company Profile - {stock_code}"
                ], className="mb-0 d-inline-block me-3"),
                create_dashboard_submenu_nav('profile', stock_code),
            ], className="d-flex align-items-center flex-wrap mb-4"),
            dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Error loading profile: {str(e)}"
            ], color="danger")
        ])

    if not profile:
        return html.Div([
            # Page Header with submenu navigation
            html.Div([
                html.H4([
                    html.I(className="fas fa-building me-2"),
                    f"Company Profile - {stock_code}"
                ], className="mb-0 d-inline-block me-3"),
                create_dashboard_submenu_nav('profile', stock_code),
            ], className="d-flex align-items-center flex-wrap mb-4"),
            dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                f"Belum ada data profile untuk {stock_code}. ",
                "Silakan upload file Excel yang berisi data profile di kolom AI-AJ."
            ], color="info")
        ])

    # Define colors for sections
    colors = {
        'identity': {'bg': '#E8F6F3', 'header': '#1ABC9C', 'border': '#16A085'},
        'history': {'bg': '#FEF9E7', 'header': '#F39C12', 'border': '#E67E22'},
        'background': {'bg': '#EBF5FB', 'header': '#3498DB', 'border': '#2980B9'},
        'shareholders': {'bg': '#F5EEF8', 'header': '#9B59B6', 'border': '#8E44AD'},
        'directors': {'bg': '#FDEDEC', 'header': '#E74C3C', 'border': '#C0392B'},
        'commissioners': {'bg': '#E8F8F5', 'header': '#1ABC9C', 'border': '#16A085'},
    }

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-building me-2", style={'color': '#3498DB'}),
                f"Company Profile - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_dashboard_submenu_nav('profile', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # Company Name Banner
        dbc.Card([
            dbc.CardBody([
                html.H3(profile.get('company_name', stock_code), className="text-center mb-1", style={'color': '#2C3E50'}),
                html.P(f"Kode Saham: {profile.get('stock_code', stock_code)}", className="text-center text-muted mb-0")
            ])
        ], className="mb-4", style={'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'border': 'none'}),

        dbc.Row([
            # Left Column
            dbc.Col([
                # Identity Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-id-card me-2"),
                        "Identitas Perusahaan"
                    ], style={'backgroundColor': colors['identity']['header'], 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.Div([
                            html.Div([
                                html.Small("Papan Pencatatan", className="text-muted"),
                                html.P(profile.get('listing_board', '-'), className="mb-2 fw-bold")
                            ], className="mb-2"),
                            html.Div([
                                html.Small("Sektor", className="text-muted"),
                                html.P(profile.get('sector', '-'), className="mb-2 fw-bold")
                            ], className="mb-2"),
                            html.Div([
                                html.Small("Sub Sektor", className="text-muted"),
                                html.P(profile.get('subsector', '-'), className="mb-2 fw-bold")
                            ], className="mb-2"),
                            html.Div([
                                html.Small("Industri", className="text-muted"),
                                html.P(profile.get('industry', '-'), className="mb-2 fw-bold")
                            ], className="mb-2"),
                            html.Div([
                                html.Small("Aktivitas Bisnis", className="text-muted"),
                                html.P(profile.get('business_activity', '-'), className="mb-0", style={'fontSize': '0.9rem'})
                            ])
                        ])
                    ], style={'backgroundColor': colors['identity']['bg']})
                ], className="mb-3", style={'border': f"2px solid {colors['identity']['border']}"}),

                # IPO History Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-history me-2"),
                        "Sejarah & IPO"
                    ], style={'backgroundColor': colors['history']['header'], 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("Tanggal Listing", className="text-muted"),
                                html.P(str(profile.get('listing_date', '-')) if profile.get('listing_date') else '-', className="mb-2 fw-bold")
                            ], width=6),
                            dbc.Col([
                                html.Small("Harga IPO", className="text-muted"),
                                html.P(f"Rp {profile.get('ipo_price', 0):,.0f}" if profile.get('ipo_price') else '-', className="mb-2 fw-bold")
                            ], width=6),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                html.Small("Saham IPO", className="text-muted"),
                                html.P(f"{profile.get('ipo_shares', 0):,.0f}" if profile.get('ipo_shares') else '-', className="mb-2 fw-bold")
                            ], width=6),
                            dbc.Col([
                                html.Small("Dana IPO", className="text-muted"),
                                html.P(f"Rp {profile.get('ipo_amount', 0)/1e9:,.1f} M" if profile.get('ipo_amount') else '-', className="mb-2 fw-bold")
                            ], width=6),
                        ]),
                        html.Hr(),
                        html.Div([
                            html.Small("Penjamin Emisi", className="text-muted"),
                            html.P(profile.get('underwriter', '-'), className="mb-2", style={'fontSize': '0.85rem'})
                        ]),
                        html.Div([
                            html.Small("BAE (Biro Administrasi Efek)", className="text-muted"),
                            html.P(profile.get('share_registrar', '-'), className="mb-0", style={'fontSize': '0.85rem'})
                        ])
                    ], style={'backgroundColor': colors['history']['bg']})
                ], className="mb-3", style={'border': f"2px solid {colors['history']['border']}"}),

                # Company Background
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-book-open me-2"),
                        "Latar Belakang"
                    ], style={'backgroundColor': colors['background']['header'], 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.P(profile.get('company_background', '-'), style={'textAlign': 'justify', 'fontSize': '0.9rem'})
                    ], style={'backgroundColor': colors['background']['bg']})
                ], className="mb-3", style={'border': f"2px solid {colors['background']['border']}"})
            ], md=6),

            # Right Column
            dbc.Col([
                # Shareholders Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-users me-2"),
                        "Pemegang Saham"
                    ], style={'backgroundColor': colors['shareholders']['header'], 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        # Major shareholder
                        html.Div([
                            html.Div([
                                html.Span(profile.get('major_shareholder', '-'), className="fw-bold"),
                                html.Span(f" {profile.get('major_shareholder_pct', 0):.2f}%", className="text-success fw-bold ms-2")
                            ], className="d-flex justify-content-between align-items-center"),
                            dbc.Progress(value=profile.get('major_shareholder_pct', 0), color="success", className="mb-2", style={'height': '8px'})
                        ], className="mb-3"),
                        # Public
                        html.Div([
                            html.Div([
                                html.Span("Publik", className="fw-bold"),
                                html.Span(f" {profile.get('public_pct', 0):.2f}%", className="text-info fw-bold ms-2")
                            ], className="d-flex justify-content-between align-items-center"),
                            dbc.Progress(value=profile.get('public_pct', 0), color="info", className="mb-2", style={'height': '8px'})
                        ], className="mb-3"),
                        html.Hr(),
                        html.Div([
                            html.Small("Total Saham Beredar", className="text-muted"),
                            html.P(f"{profile.get('total_shares', 0):,.0f} lembar" if profile.get('total_shares') else '-', className="fw-bold mb-0")
                        ]),
                        # Shareholder history
                        html.Hr() if profile.get('shareholder_history') else None,
                        html.Div([
                            html.Small("Jumlah Investor", className="text-muted d-block mb-2"),
                            html.Div([
                                html.Div([
                                    html.Small(h.get('period', ''), className="text-muted"),
                                    # Parse count to color the change: green for +, red for -
                                    html.Span([
                                        html.Span(h.get('count', '').split('(')[0].strip(), className="fw-bold"),
                                        html.Span(
                                            f" ({h.get('count', '').split('(')[1]}" if '(' in h.get('count', '') else '',
                                            className="fw-bold text-success" if '+' in h.get('count', '') else "fw-bold text-danger"
                                        )
                                    ], className="ms-2")
                                ], className="mb-1")
                                for h in (profile.get('shareholder_history', []) or [])[:4]
                            ])
                        ]) if profile.get('shareholder_history') else None
                    ], style={'backgroundColor': colors['shareholders']['bg']})
                ], className="mb-3", style={'border': f"2px solid {colors['shareholders']['border']}"}),

                # Board of Directors
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-user-tie me-2"),
                        "Direksi"
                    ], style={'backgroundColor': colors['directors']['header'], 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.Div([
                            html.P(
                                d.get('name', d) if isinstance(d, dict) else str(d),
                                className="mb-2 fw-bold", style={'fontSize': '0.9rem'}
                            )
                            for d in (profile.get('directors', []) or [])
                        ]) if profile.get('directors') else html.P("-", className="text-muted")
                    ], style={'backgroundColor': colors['directors']['bg']})
                ], className="mb-3", style={'border': f"2px solid {colors['directors']['border']}"}),

                # Board of Commissioners
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-user-shield me-2"),
                        "Komisaris"
                    ], style={'backgroundColor': colors['commissioners']['header'], 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.Div([
                            html.P(
                                c.get('name', c) if isinstance(c, dict) else str(c),
                                className="mb-2 fw-bold", style={'fontSize': '0.9rem'}
                            )
                            for c in (profile.get('commissioners', []) or [])
                        ]) if profile.get('commissioners') else html.P("-", className="text-muted")
                    ], style={'backgroundColor': colors['commissioners']['bg']})
                ], className="mb-3", style={'border': f"2px solid {colors['commissioners']['border']}"})
            ], md=6)
        ])
    ])


# ============================================================
# PAGE: BROKER MOVEMENT (Movement Alert + Watchlist)
# ============================================================

def create_broker_movement_page(stock_code='CDIA'):
    """Create dedicated Broker Movement page with alerts and watchlist"""
    price_df = get_price_data(stock_code)
    current_price = price_df['close_price'].iloc[-1] if not price_df.empty and 'close_price' in price_df.columns else 0

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-exchange-alt me-2"),
                f"Broker Movement - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_dashboard_submenu_nav('movement', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-2"),

        # [i] INTRO TEXT - Explain purpose of this page
        html.Div([
            html.P([
                html.I(className="fas fa-info-circle me-2 text-info"),
                "Menu ini fokus mendeteksi ",
                html.Strong("perubahan perilaku broker besar", className="text-warning"),
                ". Bukan siapa paling banyak beli, tapi ",
                html.Strong("siapa mulai berubah arah", className="text-info"),
                "."
            ], className="mb-0 small")
        ], className="mb-3 p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)", "borderLeft": "3px solid var(--bs-info)"}),

        # Broker Movement Alert Container
        html.Div(id="movement-alert-container", children=create_broker_movement_alert(stock_code)),

        # Broker Watchlist Container
        html.Div(id="movement-watchlist-container", children=create_broker_watchlist(stock_code)),

        # Broker Streak History Chart (Interactive)
        html.Div(id="movement-streak-container", children=create_broker_streak_section(stock_code)),

        # Refresh Button with last refresh time
        html.Div([
            dbc.Button([
                html.I(className="fas fa-sync-alt me-2"),
                "Refresh Data"
            ], id="movement-refresh-btn", color="primary", className="mt-3"),
            html.Small(id="movement-last-refresh", className="text-muted ms-3")
        ], className="text-center d-flex align-items-center justify-content-center")
    ])


# ============================================================
# PAGE: SENSITIVE BROKER (Broker Sensitivity + Activity)
# ============================================================

def create_broker_activity_table(stock_code, broker_codes, days):
    """Create activity table for specific brokers over N days"""
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return html.Div("No data", className="text-muted")

    # Filter for date range
    end_date = broker_df['date'].max()
    start_date = end_date - pd.Timedelta(days=days)
    period_df = broker_df[(broker_df['date'] >= start_date) & (broker_df['broker_code'].isin(broker_codes))]

    if period_df.empty:
        return html.Div("No activity in this period", className="text-muted small")

    # Get avg buy price for each broker
    avg_buy_df = get_broker_avg_buy(stock_code, days=days)
    avg_buy_dict = {}
    if not avg_buy_df.empty:
        avg_buy_dict = dict(zip(avg_buy_df['broker_code'], avg_buy_df['avg_buy_price']))

    # Aggregate by broker
    activity = period_df.groupby('broker_code').agg({
        'buy_value': 'sum',
        'sell_value': 'sum',
        'net_value': 'sum',
        'buy_lot': 'sum',
        'sell_lot': 'sum',
        'net_lot': 'sum'
    }).reset_index()

    # Sort by net_value
    activity = activity.sort_values('net_value', ascending=False)

    rows = []
    for _, row in activity.iterrows():
        net_val = row['net_value']
        net_lot = row['net_lot']
        action = "BUY" if net_val > 0 else "SELL" if net_val < 0 else "HOLD"
        action_color = "text-success" if net_val > 0 else "text-danger" if net_val < 0 else "text-muted"

        # Get avg buy price for this broker
        avg_buy = avg_buy_dict.get(row['broker_code'], 0)

        rows.append(html.Tr([
            html.Td(colored_broker(row['broker_code'], with_badge=True), className="table-cell"),
            html.Td(html.Span(action, className=f"fw-bold {action_color}"), className="table-cell"),
            html.Td(f"{net_val/1e9:+.2f}B", className=f"table-cell {action_color}"),
            html.Td(f"{net_lot/1e6:+.2f}M", className=f"table-cell {action_color}"),
            html.Td(f"Rp {avg_buy:,.0f}" if avg_buy > 0 else "-", className="table-cell"),
        ]))

    return html.Table([
        html.Thead(html.Tr([
            html.Th("Broker", className="table-header"),
            html.Th("Action", className="table-header"),
            html.Th("Net Val", className="table-header"),
            html.Th("Net Lot", className="table-header"),
            html.Th("Avg Buy", className="table-header"),
        ])),
        html.Tbody(rows)
    ], className="table table-sm", style={'width': '100%'})


def create_broker_summary_card(stock_code, broker_codes):
    """
    Create summary card showing accumulation/distribution/neutral status for each broker
    Uses each broker's avg_lead_time from sensitivity analysis as the accumulation window
    """
    broker_df = get_broker_data(stock_code)
    if broker_df.empty or not broker_codes:
        return html.Div("No data available", className="text-muted")

    # Get sensitivity data with lead_time for each broker
    broker_sens = calculate_broker_sensitivity_advanced(stock_code)
    broker_sens_dict = {}
    if broker_sens and broker_sens.get('brokers'):
        for b in broker_sens['brokers']:
            broker_sens_dict[b['broker_code']] = b

    end_date = broker_df['date'].max()

    summary_rows = []
    for broker_code in broker_codes:
        # Get this broker's avg_lead_time (default 5 days if not found)
        broker_info = broker_sens_dict.get(broker_code, {})
        avg_lead_time = broker_info.get('avg_lead_time', 5.0)
        win_rate = broker_info.get('win_rate', 0)

        # Use lead_time as the accumulation window (round up to ensure coverage)
        accum_window = max(int(np.ceil(avg_lead_time)), 3)  # Minimum 3 days

        # Calculate activity for the accumulation window
        start_date = end_date - pd.Timedelta(days=accum_window)
        period_df = broker_df[(broker_df['date'] >= start_date) & (broker_df['broker_code'] == broker_code)]

        if period_df.empty:
            continue

        # Count consecutive accumulation days (streak from most recent)
        period_df_sorted = period_df.sort_values('date', ascending=False)
        streak = 0
        streak_net = 0
        for _, row in period_df_sorted.iterrows():
            if row['net_value'] > 0:
                streak += 1
                streak_net += row['net_value']
            else:
                break

        # Total net in the window
        total_net = period_df['net_value'].sum()
        total_days = len(period_df)
        positive_days = len(period_df[period_df['net_value'] > 0])
        negative_days = len(period_df[period_df['net_value'] < 0])

        # Determine status based on activity in accumulation window
        # AKUMULASI: majority positive days AND positive total
        # DISTRIBUSI: majority negative days AND negative total
        if positive_days > negative_days and total_net > 0:
            status = "AKUMULASI"
            status_color = "text-success"
            status_icon = "[G]"
        elif negative_days > positive_days and total_net < 0:
            status = "DISTRIBUSI"
            status_color = "text-danger"
            status_icon = "[R]"
        else:
            status = "NETRAL"
            status_color = "text-warning"
            status_icon = "[Y]"

        # Progress indicator - how far into accumulation pattern
        if streak >= accum_window:
            progress = "[OK] READY"
            progress_color = "text-success fw-bold"
        elif streak >= accum_window * 0.5:
            progress = f"[~] {streak}/{accum_window}d"
            progress_color = "text-info"
        elif streak > 0:
            progress = f"[R] {streak}/{accum_window}d"
            progress_color = "text-muted"
        else:
            progress = "[~] -"
            progress_color = "text-muted"

        # Day detail (show last N days activity)
        day_indicators = []
        recent_days = period_df_sorted.head(min(accum_window, 5))  # Show up to 5 days
        for i, (_, row) in enumerate(recent_days.iterrows()):
            day_label = f"D{i+1}"
            if row['net_value'] > 0:
                day_indicators.append(html.Span(f"[v]", className="text-success me-1", style={"fontSize": "11px"}, title=f"{day_label}: +{row['net_value']/1e9:.1f}B"))
            else:
                day_indicators.append(html.Span(f"[x]", className="text-danger me-1", style={"fontSize": "11px"}, title=f"{day_label}: {row['net_value']/1e9:.1f}B"))

        summary_rows.append(html.Tr([
            html.Td(colored_broker(broker_code, with_badge=True), className="table-cell"),
            html.Td([
                html.Span(f"{status_icon} ", style={"fontSize": "14px"}),
                html.Span(status, className=f"fw-bold {status_color}")
            ], className="table-cell"),
            html.Td([
                html.Span(f"{accum_window}d", className="text-info fw-bold me-2"),
                html.Small(f"(Win:{win_rate:.0f}%)", className="text-muted")
            ], className="table-cell"),
            html.Td(day_indicators, className="table-cell"),
            html.Td(html.Span(progress, className=progress_color), className="table-cell"),
            html.Td(f"{total_net/1e9:+.2f}B", className=f"table-cell {'text-success' if total_net > 0 else 'text-danger' if total_net < 0 else 'text-muted'}"),
        ]))

    return html.Table([
        html.Thead(html.Tr([
            html.Th("Broker", className="table-header"),
            html.Th("Status", className="table-header"),
            html.Th("Window", className="table-header"),
            html.Th("Hari Terakhir", className="table-header"),
            html.Th("Progress", className="table-header"),
            html.Th("Net Value", className="table-header"),
        ])),
        html.Tbody(summary_rows)
    ], className="table table-sm", style={'width': '100%'})


def create_sensitive_broker_page(stock_code='CDIA'):
    """Create dedicated Sensitive Broker page with sensitivity pattern and activity"""
    price_df = get_price_data(stock_code)
    current_price = price_df['close_price'].iloc[-1] if not price_df.empty and 'close_price' in price_df.columns else 0

    # Get top 5 sensitive brokers
    broker_sens = calculate_broker_sensitivity_advanced(stock_code)
    top_5_codes = []
    if broker_sens and broker_sens.get('brokers'):
        top_5_codes = [b['broker_code'] for b in broker_sens['brokers'][:5]]

    # Get market phase for context warning
    validation_result = get_comprehensive_validation(stock_code, 30)
    overall_signal = validation_result.get('summary', {}).get('overall_signal', 'NETRAL')
    is_distribution = overall_signal == 'DISTRIBUSI'

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-crosshairs me-2"),
                f"Sensitive Broker - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_dashboard_submenu_nav('sensitive', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-2"),

        # [!] GLOBAL WARNING - Context Dependent
        dbc.Alert([
            html.Div([
                html.I(className="fas fa-exclamation-triangle me-2"),
                html.Strong("Perhatian: ", className="me-1"),
                "Broker sensitif hanya valid jika ",
                html.Strong("sejalan dengan fase pasar", className="text-warning"),
                ". ",
                html.Span(
                    "Pada fase DISTRIBUTION, sinyal akumulasi broker lebih sering gagal.",
                    className="text-danger fw-bold"
                ) if is_distribution else html.Span(
                    "Fase saat ini mendukung penggunaan sinyal broker sensitif.",
                    className="text-success"
                ),
            ], className="mb-2"),
            html.Hr(className="my-2", style={"opacity": "0.3"}),
            html.Div([
                html.Small([
                    html.Strong("[S] Cara Pakai Sinyal Broker Sensitif:", className="d-block mb-1"),
                    html.Span("1. Fokus broker ", className="me-1"),
                    html.Span("AKUMULASI", className="badge bg-success me-1"),
                    html.Span("+ Progress ", className="me-1"),
                    html.Span("READY", className="badge bg-info me-2"),
                    html.Br(),
                    html.Span("2. ", className="me-1"),
                    html.Span("Abaikan jika Market Phase masih DISTRIBUTION", className="text-warning"),
                    html.Br(),
                    html.Span("3. Ideal dipakai saat fase ", className="me-1"),
                    html.Span("SIDEWAYS ^ BREAKOUT", className="text-info fw-bold"),
                ], style={"fontSize": "11px"})
            ])
        ], color="warning" if is_distribution else "info", className="mb-3", style={"borderLeft": "4px solid"}),

        # Broker Sensitivity Pattern Container
        html.Div(id="sensitive-pattern-container", children=create_broker_sensitivity_pattern(stock_code)),

        # Summary Card - Accumulation/Distribution/Neutral
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-balance-scale me-2"),
                html.Span("[#] Summary Status Broker Sensitif", className="fw-bold"),
                html.Small(" - Akumulasi / Distribusi / Netral", className="text-muted ms-2")
            ]),
            dbc.CardBody([
                html.Div(id="broker-summary-container", children=create_broker_summary_card(stock_code, top_5_codes)),
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Keterangan: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("* Window: "), "Jumlah hari akumulasi rata-rata broker sebelum harga naik >=10% (dari data historis)",
                        html.Br(),
                        html.Strong("* Win%: "), "Persentase keberhasilan sinyal akumulasi broker ini",
                        html.Br(),
                        html.Strong("* Hari Terakhir: "), "[v] = net buy, [x] = net sell (D1=hari ini, D2=kemarin, dst)",
                        html.Br(),
                        html.Strong("* Progress: "), "[OK] READY = akumulasi sudah cukup, [~] = sedang proses, [R] = baru mulai",
                        html.Br(),
                        html.Strong("[i] Signal: "), "Broker dengan status AKUMULASI dan Progress READY = potensi harga naik dalam beberapa hari!"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box mt-2")
            ])
        ], className="mb-3"),

        # Broker Activity Over Time Periods
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-line me-2"),
                html.Span("[#] Aktivitas Top 5 Broker Sensitif", className="fw-bold"),
                html.Small(" - Perbandingan periode waktu", className="text-muted ms-2")
            ]),
            dbc.CardBody([
                dbc.Row([
                    # 1 Week
                    dbc.Col([
                        html.Div([
                            html.H6("[N] 1 Minggu Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-1week", children=create_broker_activity_table(stock_code, top_5_codes, 7))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),

                    # 2 Weeks
                    dbc.Col([
                        html.Div([
                            html.H6("[N] 2 Minggu Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-2weeks", children=create_broker_activity_table(stock_code, top_5_codes, 14))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),

                    # 3 Weeks
                    dbc.Col([
                        html.Div([
                            html.H6("[N] 3 Minggu Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-3weeks", children=create_broker_activity_table(stock_code, top_5_codes, 21))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),

                    # 1 Month
                    dbc.Col([
                        html.Div([
                            html.H6("[N] 1 Bulan Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-1month", children=create_broker_activity_table(stock_code, top_5_codes, 30))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),
                ]),

                # Explanation
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Cara Baca Aktivitas: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("* Action: "), "BUY = net positif (lebih banyak beli), SELL = net negatif",
                        html.Br(),
                        html.Strong("* Net Val: "), "Total nilai bersih (beli - jual) dalam miliar rupiah",
                        html.Br(),
                        html.Strong("* Net Lot: "), "Total lot bersih dalam juta lot",
                        html.Br(),
                        html.Strong("[i] Tip: "), "Bandingkan aktivitas antar periode. Jika broker konsisten BUY di semua periode, kemungkinan sedang akumulasi besar!"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box mt-2")
            ])
        ], className="mb-3"),

        # Refresh Button with last refresh time
        html.Div([
            dbc.Button([
                html.I(className="fas fa-sync-alt me-2"),
                "Refresh Data"
            ], id="sensitive-refresh-btn", color="primary", className="mt-3"),
            html.Small(id="sensitive-last-refresh", className="text-muted ms-3")
        ], className="text-center d-flex align-items-center justify-content-center")
    ])


# ============================================================
# PAGE: FUNDAMENTAL ANALYSIS
# ============================================================

def get_stock_fundamental(stock_code: str) -> dict:
    """Get stock fundamental from database"""
    query = """
        SELECT * FROM stock_fundamental
        WHERE stock_code = %s
        ORDER BY report_date DESC
        LIMIT 1
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    if result and len(result) > 0:
        row = result[0]
        return {
            'stock_code': row['stock_code'],
            'report_date': row['report_date'],
            'issued_shares': row['issued_shares'],
            'market_cap': float(row['market_cap']) if row['market_cap'] else 0,
            'stock_index': float(row['stock_index']) if row['stock_index'] else 0,
            'sales': float(row['sales']) if row['sales'] else 0,
            'assets': float(row['assets']) if row['assets'] else 0,
            'liability': float(row['liability']) if row['liability'] else 0,
            'equity': float(row['equity']) if row['equity'] else 0,
            'capex': float(row['capex']) if row['capex'] else 0,
            'operating_expense': float(row['operating_expense']) if row['operating_expense'] else 0,
            'operating_cashflow': float(row['operating_cashflow']) if row['operating_cashflow'] else 0,
            'net_cashflow': float(row['net_cashflow']) if row['net_cashflow'] else 0,
            'operating_profit': float(row['operating_profit']) if row['operating_profit'] else 0,
            'net_profit': float(row['net_profit']) if row['net_profit'] else 0,
            'dps': float(row['dps']) if row['dps'] else 0,
            'eps': float(row['eps']) if row['eps'] else 0,
            'rps': float(row['rps']) if row['rps'] else 0,
            'bvps': float(row['bvps']) if row['bvps'] else 0,
            'cfps': float(row['cfps']) if row['cfps'] else 0,
            'ceps': float(row['ceps']) if row['ceps'] else 0,
            'navs': float(row['navs']) if row['navs'] else 0,
            'dividend_yield': float(row['dividend_yield']) if row['dividend_yield'] else 0,
            'per': float(row['per']) if row['per'] else 0,
            'psr': float(row['psr']) if row['psr'] else 0,
            'pbvr': float(row['pbvr']) if row['pbvr'] else 0,
            'pcfr': float(row['pcfr']) if row['pcfr'] else 0,
            'dpr': float(row['dpr']) if row['dpr'] else 0,
            'gpm': float(row['gpm']) if row['gpm'] else 0,
            'opm': float(row['opm']) if row['opm'] else 0,
            'npm': float(row['npm']) if row['npm'] else 0,
            'ebitm': float(row['ebitm']) if row['ebitm'] else 0,
            'roe': float(row['roe']) if row['roe'] else 0,
            'roa': float(row['roa']) if row['roa'] else 0,
            'der': float(row['der']) if row['der'] else 0,
            'cash_ratio': float(row['cash_ratio']) if row['cash_ratio'] else 0,
            'quick_ratio': float(row['quick_ratio']) if row['quick_ratio'] else 0,
            'current_ratio': float(row['current_ratio']) if row['current_ratio'] else 0,
        }
    return {}


def get_fundamental_summary(fund: dict) -> dict:
    """Generate fundamental summary with ratings"""
    if not fund:
        return {}

    # Valuation Analysis
    per = fund.get('per', 0)
    pbvr = fund.get('pbvr', 0)
    psr = fund.get('psr', 0)

    if per > 0 and per < 15:
        valuation_rating = 'Murah'
        valuation_color = 'success'
    elif per >= 15 and per < 25:
        valuation_rating = 'Wajar'
        valuation_color = 'info'
    elif per >= 25 and per < 50:
        valuation_rating = 'Premium'
        valuation_color = 'warning'
    else:
        valuation_rating = 'Mahal'
        valuation_color = 'danger'

    # Profitability Analysis
    npm = fund.get('npm', 0) * 100
    roe = fund.get('roe', 0) * 100
    gpm = fund.get('gpm', 0) * 100

    if npm > 20:
        profit_rating = 'Sangat Baik'
        profit_color = 'success'
    elif npm > 10:
        profit_rating = 'Baik'
        profit_color = 'info'
    elif npm > 5:
        profit_rating = 'Cukup'
        profit_color = 'warning'
    else:
        profit_rating = 'Rendah'
        profit_color = 'danger'

    # Liquidity Analysis
    current_ratio = fund.get('current_ratio', 0) * 100
    der = fund.get('der', 0) * 100

    if current_ratio > 150 and der < 100:
        liquidity_rating = 'Sehat'
        liquidity_color = 'success'
    elif current_ratio > 100:
        liquidity_rating = 'Cukup'
        liquidity_color = 'info'
    else:
        liquidity_rating = 'Perlu Perhatian'
        liquidity_color = 'warning'

    # Overall Score
    score = 0
    if per > 0 and per < 25: score += 25
    elif per > 0 and per < 50: score += 15
    if npm > 10: score += 25
    elif npm > 5: score += 15
    if roe > 10: score += 25
    elif roe > 5: score += 15
    if current_ratio > 100: score += 25
    elif current_ratio > 50: score += 15

    if score >= 80:
        overall = 'SANGAT BAIK'
        overall_color = 'success'
    elif score >= 60:
        overall = 'BAIK'
        overall_color = 'info'
    elif score >= 40:
        overall = 'CUKUP'
        overall_color = 'warning'
    else:
        overall = 'KURANG'
        overall_color = 'danger'

    return {
        'valuation_rating': valuation_rating,
        'valuation_color': valuation_color,
        'profit_rating': profit_rating,
        'profit_color': profit_color,
        'liquidity_rating': liquidity_rating,
        'liquidity_color': liquidity_color,
        'overall': overall,
        'overall_color': overall_color,
        'score': score
    }


def create_fundamental_page(stock_code='CDIA'):
    """Create Fundamental Analysis page with attractive design"""
    fund = get_stock_fundamental(stock_code)
    summary = get_fundamental_summary(fund)

    if not fund:
        return html.Div([
            # Page Header with submenu navigation
            html.Div([
                html.H4([
                    html.I(className="fas fa-chart-line me-2"),
                    f"Fundamental Analysis - {stock_code}"
                ], className="mb-0 d-inline-block me-3"),
                create_submenu_nav('fundamental', stock_code),
            ], className="d-flex align-items-center flex-wrap mb-4"),
            dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                f"Belum ada data fundamental untuk {stock_code}. ",
                "Silakan upload file Excel yang berisi data fundamental di kolom AL-AM."
            ], color="info")
        ])

    def format_trillion(val):
        if val >= 1e12:
            return f"Rp {val/1e12:,.2f} T"
        elif val >= 1e9:
            return f"Rp {val/1e9:,.2f} M"
        else:
            return f"Rp {val:,.0f}"

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-chart-line me-2", style={'color': '#2E86AB'}),
                f"Fundamental Analysis - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_submenu_nav('fundamental', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # ============ SUMMARY HERO CARD ============
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Overall Score
                    dbc.Col([
                        html.Div([
                            html.H1(f"{summary.get('score', 0)}",
                                   className=f"display-2 text-{summary.get('overall_color', 'secondary')} mb-0 fw-bold"),
                            html.P("FUNDAMENTAL SCORE", className="text-muted mb-1"),
                            dbc.Badge(summary.get('overall', 'N/A'),
                                     color=summary.get('overall_color', 'secondary'),
                                     className="fs-6 px-3 py-2")
                        ], className="text-center")
                    ], md=3),
                    # Summary Cards
                    dbc.Col([
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("Valuasi", className="text-muted mb-1"),
                                        html.H4(summary.get('valuation_rating', '-'),
                                               className=f"text-{summary.get('valuation_color', 'secondary')} mb-0"),
                                        html.Small(f"PER: {fund.get('per', 0):.1f}x | PBV: {fund.get('pbvr', 0):.1f}x")
                                    ], className="text-center py-2")
                                ], style={'border': f"2px solid", 'borderColor': 'var(--bs-' + summary.get('valuation_color', 'secondary') + ')'})
                            ], md=4),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("Profitabilitas", className="text-muted mb-1"),
                                        html.H4(summary.get('profit_rating', '-'),
                                               className=f"text-{summary.get('profit_color', 'secondary')} mb-0"),
                                        html.Small(f"NPM: {fund.get('npm', 0)*100:.1f}% | ROE: {fund.get('roe', 0)*100:.1f}%")
                                    ], className="text-center py-2")
                                ], style={'border': f"2px solid", 'borderColor': 'var(--bs-' + summary.get('profit_color', 'secondary') + ')'})
                            ], md=4),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("Likuiditas", className="text-muted mb-1"),
                                        html.H4(summary.get('liquidity_rating', '-'),
                                               className=f"text-{summary.get('liquidity_color', 'secondary')} mb-0"),
                                        html.Small(f"CR: {fund.get('current_ratio', 0)*100:.0f}% | DER: {fund.get('der', 0)*100:.0f}%")
                                    ], className="text-center py-2")
                                ], style={'border': f"2px solid", 'borderColor': 'var(--bs-' + summary.get('liquidity_color', 'secondary') + ')'})
                            ], md=4),
                        ])
                    ], md=9)
                ])
            ])
        ], className="mb-4", style={'background': 'linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%)'}),

        # ============ KEY METRICS ROW ============
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6([html.I(className="fas fa-building me-2 text-primary"), "Kapitalisasi Pasar"], className="mb-2"),
                        html.H4(format_trillion(fund.get('market_cap', 0)), className="text-primary mb-0")
                    ])
                ], className="h-100", style={'borderLeft': '4px solid #2E86AB'})
            ], md=3, className="mb-3"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6([html.I(className="fas fa-coins me-2 text-success"), "Laba Bersih"], className="mb-2"),
                        html.H4(format_trillion(fund.get('net_profit', 0)), className="text-success mb-0")
                    ])
                ], className="h-100", style={'borderLeft': '4px solid #58B368'})
            ], md=3, className="mb-3"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6([html.I(className="fas fa-chart-bar me-2 text-info"), "Total Aset"], className="mb-2"),
                        html.H4(format_trillion(fund.get('assets', 0)), className="text-info mb-0")
                    ])
                ], className="h-100", style={'borderLeft': '4px solid #00B4D8'})
            ], md=3, className="mb-3"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6([html.I(className="fas fa-hand-holding-usd me-2 text-warning"), "Total Ekuitas"], className="mb-2"),
                        html.H4(format_trillion(fund.get('equity', 0)), className="text-warning mb-0")
                    ])
                ], className="h-100", style={'borderLeft': '4px solid #F18F01'})
            ], md=3, className="mb-3"),
        ]),

        dbc.Row([
            # Left Column - Financial Position & Per Share
            dbc.Col([
                # Financial Position
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-balance-scale me-2"),
                        "Posisi Keuangan"
                    ], style={'backgroundColor': '#F18F01', 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.Table([
                            html.Tbody([
                                html.Tr([html.Td("Total Pendapatan", className="fw-bold"), html.Td(format_trillion(fund.get('sales', 0)), className="text-end")]),
                                html.Tr([html.Td("Total Aset", className="fw-bold"), html.Td(format_trillion(fund.get('assets', 0)), className="text-end")]),
                                html.Tr([html.Td("Total Kewajiban", className="fw-bold"), html.Td(format_trillion(fund.get('liability', 0)), className="text-end")]),
                                html.Tr([html.Td("Total Ekuitas", className="fw-bold"), html.Td(format_trillion(fund.get('equity', 0)), className="text-end")]),
                                html.Tr([html.Td("Belanja Modal", className="fw-bold"), html.Td(format_trillion(fund.get('capex', 0)), className="text-end")]),
                                html.Tr([html.Td("Laba Operasi", className="fw-bold"), html.Td(format_trillion(fund.get('operating_profit', 0)), className="text-end")]),
                                html.Tr([html.Td("Laba Bersih", className="fw-bold"), html.Td(format_trillion(fund.get('net_profit', 0)), className="text-end text-success")]),
                            ])
                        ], className="table table-sm table-borderless mb-0")
                    ], style={'backgroundColor': '#FFF3E0'})
                ], className="mb-3"),

                # Per Share Data
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-chart-pie me-2"),
                        "Data Per Lembar Saham"
                    ], style={'backgroundColor': '#9B5DE5', 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.Table([
                            html.Tbody([
                                html.Tr([html.Td("EPS (Laba/Saham)", className="fw-bold"), html.Td(f"Rp {fund.get('eps', 0):,.2f}", className="text-end")]),
                                html.Tr([html.Td("BVPS (Nilai Buku/Saham)", className="fw-bold"), html.Td(f"Rp {fund.get('bvps', 0):,.2f}", className="text-end")]),
                                html.Tr([html.Td("DPS (Dividen/Saham)", className="fw-bold"), html.Td(f"Rp {fund.get('dps', 0):,.0f}", className="text-end")]),
                                html.Tr([html.Td("RPS (Pendapatan/Saham)", className="fw-bold"), html.Td(f"Rp {fund.get('rps', 0):,.2f}", className="text-end")]),
                                html.Tr([html.Td("NAVS (Aset Bersih/Saham)", className="fw-bold"), html.Td(f"Rp {fund.get('navs', 0):,.2f}", className="text-end")]),
                            ])
                        ], className="table table-sm table-borderless mb-0")
                    ], style={'backgroundColor': '#F3E8FF'})
                ], className="mb-3"),
            ], md=6),

            # Right Column - Valuation & Ratios
            dbc.Col([
                # Valuation Metrics
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-tags me-2"),
                        "Metrik Valuasi"
                    ], style={'backgroundColor': '#00B4D8', 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.H3(f"{fund.get('per', 0):.1f}x", className="mb-0 text-primary"),
                                    html.Small("PER", className="text-muted")
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.H3(f"{fund.get('pbvr', 0):.1f}x", className="mb-0 text-info"),
                                    html.Small("PBV", className="text-muted")
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.H3(f"{fund.get('psr', 0):.1f}x", className="mb-0 text-secondary"),
                                    html.Small("PSR", className="text-muted")
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-3"),
                        html.Hr(),
                        html.Div([
                            html.Span("Dividend Yield: ", className="fw-bold"),
                            html.Span(f"{fund.get('dividend_yield', 0)*100:.2f}%", className="text-success")
                        ])
                    ], style={'backgroundColor': '#E0F7FA'})
                ], className="mb-3"),

                # Profitability Ratios
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-percentage me-2"),
                        "Rasio Profitabilitas"
                    ], style={'backgroundColor': '#E56B6F', 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        html.Div([
                            html.Div([
                                html.Span("Margin Laba Kotor (GPM)", className="small"),
                                html.Span(f"{fund.get('gpm', 0)*100:.1f}%", className="fw-bold float-end")
                            ]),
                            dbc.Progress(value=min(fund.get('gpm', 0)*100, 100), color="success", className="mb-2", style={'height': '8px'})
                        ]),
                        html.Div([
                            html.Div([
                                html.Span("Margin Laba Operasi (OPM)", className="small"),
                                html.Span(f"{fund.get('opm', 0)*100:.1f}%", className="fw-bold float-end")
                            ]),
                            dbc.Progress(value=min(fund.get('opm', 0)*100, 100), color="info", className="mb-2", style={'height': '8px'})
                        ]),
                        html.Div([
                            html.Div([
                                html.Span("Margin Laba Bersih (NPM)", className="small"),
                                html.Span(f"{fund.get('npm', 0)*100:.1f}%", className="fw-bold float-end")
                            ]),
                            dbc.Progress(value=min(fund.get('npm', 0)*100, 100), color="primary", className="mb-2", style={'height': '8px'})
                        ]),
                        html.Hr(),
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.H4(f"{fund.get('roe', 0)*100:.1f}%", className="mb-0 text-success"),
                                    html.Small("ROE", className="text-muted")
                                ], className="text-center")
                            ], width=6),
                            dbc.Col([
                                html.Div([
                                    html.H4(f"{fund.get('roa', 0)*100:.1f}%", className="mb-0 text-info"),
                                    html.Small("ROA", className="text-muted")
                                ], className="text-center")
                            ], width=6),
                        ])
                    ], style={'backgroundColor': '#FFE4E6'})
                ], className="mb-3"),

                # Liquidity Ratios
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-tint me-2"),
                        "Rasio Likuiditas & Solvabilitas"
                    ], style={'backgroundColor': '#355070', 'color': 'white', 'fontWeight': 'bold'}),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.H4(f"{fund.get('current_ratio', 0)*100:.0f}%", className="mb-0"),
                                    html.Small("Current Ratio", className="text-muted")
                                ], className="text-center")
                            ], width=6),
                            dbc.Col([
                                html.Div([
                                    html.H4(f"{fund.get('quick_ratio', 0)*100:.0f}%", className="mb-0"),
                                    html.Small("Quick Ratio", className="text-muted")
                                ], className="text-center")
                            ], width=6),
                        ], className="mb-3"),
                        html.Hr(),
                        html.Div([
                            html.Div([
                                html.Span("Debt to Equity Ratio (DER)", className="small"),
                                html.Span(f"{fund.get('der', 0)*100:.1f}%", className="fw-bold float-end")
                            ]),
                            dbc.Progress(value=min(fund.get('der', 0)*100, 100),
                                        color="danger" if fund.get('der', 0) > 1 else "success",
                                        className="mb-2", style={'height': '8px'})
                        ]),
                        html.Div([
                            html.Div([
                                html.Span("Cash Ratio", className="small"),
                                html.Span(f"{fund.get('cash_ratio', 0)*100:.1f}%", className="fw-bold float-end")
                            ]),
                            dbc.Progress(value=min(fund.get('cash_ratio', 0)*100, 100), color="info", className="mb-2", style={'height': '8px'})
                        ])
                    ], style={'backgroundColor': '#E8EEF4'})
                ], className="mb-3"),
            ], md=6),
        ]),

        # Report Date
        html.Div([
            html.Small(f"Data per: {fund.get('report_date', '-')}", className="text-muted")
        ], className="text-end mt-2")
    ])


# ============================================================
# PAGE: COMPREHENSIVE ANALYSIS (Unified from 3 Submenus)
# ============================================================

def create_analysis_page(stock_code='CDIA'):
    """
    Create unified analysis page combining data from 3 submenus:
    1. Fundamental (PER, PBV, ROE)
    2. Support & Resistance (Key levels)
    3. Accumulation (Decision rule, signals)
    """
    try:
        # Get unified analysis from all 3 submenus
        unified = get_unified_analysis_summary(stock_code)
        decision = unified.get('decision', {})
        accum = unified.get('accumulation', {})
        fundamental = unified.get('fundamental', {})
        sr = unified.get('support_resistance', {})
        key_points = unified.get('key_points', [])
        warnings = unified.get('warnings', [])

        # Extract nested data
        summary = accum.get('summary', {})
        confidence = accum.get('confidence', {})
        validations = accum.get('validations', {})
        detection = accum.get('detection', {})
        markup_trigger = accum.get('markup_trigger', {})
        impulse_signal = accum.get('impulse_signal', {})

        current_price = sr.get('current_price', 0) or accum.get('current_price', 0)

        # Multi-horizon Volume vs Price analysis
        price_df = get_price_data(stock_code)
        vol_price_multi = calculate_volume_price_multi_horizon(price_df) if not price_df.empty else {
            'status': 'NO_DATA', 'significance': 'INSUFFICIENT', 'horizons': {}, 'conclusion': 'Data tidak tersedia'
        }

        # V11b Volume Ratio Calculation (today volume / 20-day avg)
        v11b_vol_ratio = 1.0  # Default
        if not price_df.empty and len(price_df) >= 20:
            price_df_vol = price_df.sort_values('date', ascending=False).reset_index(drop=True)
            today_volume = price_df_vol['volume'].iloc[0] if len(price_df_vol) > 0 else 0
            avg_volume_20d = price_df_vol['volume'].iloc[1:21].mean() if len(price_df_vol) >= 21 else price_df_vol['volume'].mean()
            v11b_vol_ratio = today_volume / avg_volume_20d if avg_volume_20d > 0 else 1.0

        # Calculate price changes (today, 1 week, 1 month)
        change_today = 0
        change_1w = 0
        change_1m = 0
        if not price_df.empty and len(price_df) > 0:
            price_df_sorted = price_df.sort_values('date', ascending=False).reset_index(drop=True)
            if len(price_df_sorted) >= 1:
                current = price_df_sorted['close_price'].iloc[0]
                # Today change
                if len(price_df_sorted) >= 2:
                    prev_day = price_df_sorted['close_price'].iloc[1]
                    change_today = ((current - prev_day) / prev_day * 100) if prev_day else 0
                # 1 week change (5 trading days)
                if len(price_df_sorted) >= 6:
                    prev_week = price_df_sorted['close_price'].iloc[5]
                    change_1w = ((current - prev_week) / prev_week * 100) if prev_week else 0
                # 1 month change (20 trading days)
                if len(price_df_sorted) >= 21:
                    prev_month = price_df_sorted['close_price'].iloc[20]
                    change_1m = ((current - prev_month) / prev_month * 100) if prev_month else 0

        # V6 Sideways Analysis for accurate Support/Resistance levels
        v6_data = get_v6_analysis(stock_code)
        v6_sideways = v6_data.get('sideways', {}) if not v6_data.get('error') else {}
        v6_entry = v6_data.get('entry', {}) if not v6_data.get('error') else {}

        # For PANI/BREN/MBMA: Use Strong S/R Analyzer (separate module)
        strong_sr_data = None
        if has_custom_formula(stock_code):
            strong_sr_data = get_strong_sr_analysis(stock_code)
            if strong_sr_data and not strong_sr_data.get('error'):
                # Override sr values with Strong S/R
                sr['support_20d'] = strong_sr_data.get('support', sr.get('support_20d', 0))
                sr['resistance_20d'] = strong_sr_data.get('resistance', sr.get('resistance_20d', 0))
                sr['strong_sr'] = True
                sr['support_touches'] = strong_sr_data.get('support_touches', 0)
                sr['resistance_touches'] = strong_sr_data.get('resistance_touches', 0)
                # Recalculate distances
                if current_price and sr['support_20d']:
                    sr['dist_from_support'] = (current_price - sr['support_20d']) / current_price * 100
                if current_price and sr['resistance_20d']:
                    sr['dist_from_resistance'] = (sr['resistance_20d'] - current_price) / current_price * 100
                # Override v6_entry with Strong S/R values
                v6_entry['stop_loss'] = strong_sr_data.get('stop_loss')
                v6_entry['target'] = strong_sr_data.get('target')
                v6_entry['formula_info'] = strong_sr_data.get('formula_info', {})
                v6_entry['action'] = strong_sr_data.get('action', 'WAIT')
                v6_entry['action_reason'] = strong_sr_data.get('action_reason', '')
                v6_entry['phase'] = strong_sr_data.get('phase', 'NEUTRAL')
                v6_entry['vr'] = strong_sr_data.get('vr', 0)
                # V10 Performance & Trade History
                v6_entry['v10_performance'] = strong_sr_data.get('v10_performance', {})
                v6_entry['v10_trades'] = strong_sr_data.get('v10_trades', [])
                v6_entry['v10_criteria'] = strong_sr_data.get('v10_criteria')
                v6_entry['v10_position'] = strong_sr_data.get('v10_position')
                # Update v6_sideways for consistency
                v6_sideways['low'] = strong_sr_data.get('support', v6_sideways.get('low', 0))
                v6_sideways['high'] = strong_sr_data.get('resistance', v6_sideways.get('high', 0))

        # Weekly Analysis for 4-week accumulation data
        weekly_data = get_weekly_analysis(stock_code)
        weeks = weekly_data.get('weeks', {})

    except Exception as e:
        return html.Div([
            dbc.Alert(f"Error loading analysis for {stock_code}: {str(e)}", color="danger"),
            html.P("Pastikan data sudah diupload dengan benar")
        ])

    # Generate one-line insight based on analysis
    overall_signal = summary.get('overall_signal', 'NETRAL')
    conf_level = confidence.get('level', 'LOW')
    pass_rate = confidence.get('pass_rate', 0)
    action = decision.get('action', 'WAIT')

    # Check impulse signal first (highest priority)
    if impulse_signal.get('impulse_detected'):
        imp_strength = impulse_signal.get('strength', 'WEAK')
        vol_ratio = impulse_signal.get('metrics', {}).get('volume_ratio', 0)
        insight_text = f"[!] {stock_code} IMPULSE BREAKOUT ({imp_strength})! Volume {vol_ratio:.1f}x rata-rata. Momentum tinggi, risiko tinggi."
        insight_color = "danger"
    elif impulse_signal.get('near_impulse'):
        conds_met = impulse_signal.get('trigger_conditions', {}).get('conditions_met', 0)
        insight_text = f"[+] {stock_code} hampir memenuhi kriteria impulse ({conds_met}/3). Pantau volume dan breakout."
        insight_color = "info"
    elif overall_signal == 'AKUMULASI' and conf_level in ['HIGH', 'VERY_HIGH']:
        insight_text = f"[G] {stock_code} menunjukkan pola akumulasi kuat ({pass_rate:.0f}% validasi lolos). Perhatikan zona entry."
        insight_color = "success"
    elif overall_signal == 'AKUMULASI':
        insight_text = f"[Y] {stock_code} menunjukkan sinyal akumulasi awal. Pantau konsistensi broker flow."
        insight_color = "info"
    elif overall_signal == 'DISTRIBUSI' and conf_level in ['HIGH', 'VERY_HIGH']:
        insight_text = f"[R] {stock_code} dalam fase distribusi kuat ({pass_rate:.0f}% validasi). Hati-hati posisi beli baru."
        insight_color = "danger"
    elif overall_signal == 'DISTRIBUSI':
        insight_text = f"[ ] {stock_code} menunjukkan sinyal distribusi. Pertimbangkan pengurangan posisi."
        insight_color = "warning"
    else:
        insight_text = f"[~] {stock_code} dalam fase netral. Tidak ada sinyal kuat - observasi dulu."
        insight_color = "secondary"

    # === V6 SYSTEM VARIABLES (BEFORE RETURN) ===
    v6_action = v6_entry.get('action', 'WAIT') if v6_entry else 'WAIT'
    v6_action_reason = v6_entry.get('action_reason', '') if v6_entry else ''
    v11_confirm_type = 'WAIT'  # Initialize - will be updated based on price direction
    breakout_days_above = 0  # Initialize for checklist
    came_from_below = False  # Initialize for checklist

    # Check for V10 open position
    v10_position = get_v10_open_position(stock_code)
    if v10_position:
        v6_action = 'RUNNING'
        v6_action_reason = f"Posisi {v10_position['type']} Z{v10_position['zone_num']} sejak {v10_position['entry_date']}"
    elif stock_code.upper() in STOCK_ZONES:
        # For V10 stocks, action is based on V10 status, not Strong S/R
        v10_zones = get_zones(stock_code)
        if v10_zones:
            # Check if price is in any support zone
            v10_in_zone = any(z['low'] <= current_price <= z['high'] * 1.02 for z in v10_zones.values())

            # Find active support zone (nearest zone below or containing current price)
            support_zone = next((z for zn, z in sorted(v10_zones.items(), reverse=True) if z['low'] <= current_price <= z['high'] * 1.02), None)
            if not support_zone:
                # If not in zone, find nearest support below
                support_zone = next((z for zn, z in sorted(v10_zones.items(), reverse=True) if z['high'] < current_price), None)

            # Find resistance zone (nearest zone above current price)
            resistance_zone = next((z for zn, z in sorted(v10_zones.items()) if z['low'] > current_price), None)

            # === V11b1 Price Direction Detection ===
            # RETEST: Harga TURUN dari resistance ke support
            # BREAKOUT: Harga NAIK dari bawah menembus zona
            came_from_below = False
            price_trend_up = False
            v11_confirm_type = 'WAIT'
            breakout_days_above = 0
            touch_support = False

            if not price_df.empty and len(price_df) >= 7 and support_zone:
                price_df_check = price_df.sort_values('date', ascending=False).reset_index(drop=True)
                lookback_days = min(14, len(price_df_check))

                # Check last 7 days for price below support zone_low (BREAKOUT candidate)
                for i in range(min(7, len(price_df_check))):
                    if price_df_check['close_price'].iloc[i] < support_zone['low']:
                        came_from_below = True
                        break

                # Check price trend: compare current vs 7 days ago
                if len(price_df_check) >= 7:
                    price_7d_ago = price_df_check['close_price'].iloc[6]
                    price_trend_up = current_price > price_7d_ago

                # Check if price touched support zone (low <= zone_high)
                today_low = price_df_check['low_price'].iloc[0] if len(price_df_check) > 0 else 0
                if today_low <= support_zone['high']:
                    touch_support = True

                # Count consecutive days with close > zone_high (for BREAKOUT)
                for i in range(min(7, len(price_df_check))):
                    if price_df_check['close_price'].iloc[i] > support_zone['high']:
                        breakout_days_above += 1
                    else:
                        break

                # Determine confirmation type based on trend and position
                if came_from_below and price_trend_up:
                    # BREAKOUT scenario - harga naik dari bawah
                    if current_price > support_zone['high']:
                        if breakout_days_above >= 3:
                            v11_confirm_type = 'BREAKOUT_OK'
                        else:
                            v11_confirm_type = f'BREAKOUT ({breakout_days_above}/3)'
                    else:
                        v11_confirm_type = 'BREAKOUT_WAIT'
                elif not price_trend_up:
                    # RETEST scenario - harga turun (dari atas)
                    if touch_support and v10_in_zone:
                        v11_confirm_type = 'RETEST_OK'
                    elif touch_support:
                        # Low menyentuh zona, meskipun close sedikit di atas
                        v11_confirm_type = 'RETEST'
                    elif v10_in_zone:
                        v11_confirm_type = 'RETEST'
                    else:
                        v11_confirm_type = 'RETEST_WAIT'
                else:
                    # Price trend up but didn't come from below recently
                    # This is NOT a breakout - just normal price movement between zones
                    if v10_in_zone:
                        v11_confirm_type = 'RETEST'
                    else:
                        # Harga di antara zona, bukan breakout baru
                        # Tunggu retest ke support atau breakout ke resistance baru
                        v11_confirm_type = 'PANTAU'

            # Get phase from v6_entry
            phase = v6_entry.get('phase', 'NEUTRAL') if v6_entry else 'NEUTRAL'

            if v10_in_zone:
                # Price is in a support zone - check for entry conditions (V11b: + Volume >= 1.0x)
                if phase in ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']:
                    if v11b_vol_ratio >= 1.0:
                        # V11b: Volume confirmed - ENTRY
                        v6_action = 'ENTRY'
                        v6_action_reason = f"V11b: Zona {support_zone['low']:,.0f}-{support_zone['high']:,.0f} | {phase} | Vol {v11b_vol_ratio:.2f}x OK"
                    else:
                        # V11b1: Volume belum cukup - MENUNGGU VOLUME (max 7 hari)
                        # Hitung berapa hari sudah dalam zona dengan vol < 1.0x
                        days_waiting = 0
                        if not price_df.empty and len(price_df) >= 2:
                            price_df_check = price_df.sort_values('date', ascending=False).reset_index(drop=True)
                            for i in range(min(7, len(price_df_check))):
                                row_price = price_df_check['close_price'].iloc[i]
                                row_vol = price_df_check['volume'].iloc[i]
                                row_avg_vol = price_df_check['volume'].iloc[1:21].mean() if len(price_df_check) >= 21 else price_df_check['volume'].mean()
                                row_vol_ratio = row_vol / row_avg_vol if row_avg_vol > 0 else 1.0
                                # Cek apakah dalam zona dan vol < 1.0x
                                if support_zone and support_zone['low'] <= row_price <= support_zone['high'] * 1.02 and row_vol_ratio < 1.0:
                                    days_waiting += 1
                                else:
                                    break

                        if days_waiting >= 7:
                            # Sudah 7 hari menunggu, skip sinyal ini
                            v6_action = 'WAIT'
                            v6_action_reason = f"V11b1: Menunggu volume >7 hari - sinyal expired, tunggu setup baru"
                        else:
                            v6_action = 'WATCH'
                            v6_action_reason = f"V11b1: MENUNGGU VOLUME | Zona OK, {phase} OK | Vol {v11b_vol_ratio:.2f}x < 1.0x | Hari ke-{days_waiting + 1}/7"
                else:
                    v6_action = 'WATCH'
                    v6_action_reason = f"V11b1: Dalam zona tapi fase {phase} - pantau akumulasi"
            elif support_zone and resistance_zone:
                # Price is between zones - check if BREAKOUT confirmed
                if v11_confirm_type == 'BREAKOUT_OK':
                    v6_action = 'ENTRY'
                    v6_action_reason = f"V11b1: BREAKOUT confirmed! 3+ hari di atas zona {support_zone['low']:,.0f}-{support_zone['high']:,.0f} | Vol OK"
                elif 'BREAKOUT' in v11_confirm_type:
                    v6_action = 'WATCH'
                    v6_action_reason = f"V11b1: Breakout dalam proses ({v11_confirm_type}) - tunggu konfirmasi 3 hari"
                else:
                    v6_action = 'WAIT'
                    v6_action_reason = f"V11b1: Di antara zona S {support_zone['low']:,.0f}-{support_zone['high']:,.0f} dan R {resistance_zone['low']:,.0f}-{resistance_zone['high']:,.0f} - tunggu retest"
            elif support_zone and not resistance_zone:
                # Price is above all zones
                v6_action = 'WATCH'
                v6_action_reason = f"V11b1: Di atas semua zona - pantau breakout atau retest ke {support_zone['low']:,.0f}-{support_zone['high']:,.0f}"
            else:
                # No support zone (price below all zones)
                v6_action = 'AVOID'
                v6_action_reason = f"V11b1: Harga di bawah semua zona support"

    # Use Strong S/R phase for PANI/BREN/MBMA, otherwise use v6_data phase
    if v6_entry.get('formula_info', {}).get('type') == 'STRONG_SR':
        v6_phase = v6_entry.get('phase', 'NEUTRAL')
    else:
        v6_phase = v6_data.get('phase', {}).get('phase', 'NEUTRAL') if v6_data and not v6_data.get('error') else 'NEUTRAL'
    v6_action_map = {
        'ENTRY': {'icon': '🟢', 'color': 'success', 'desc': 'Sinyal masuk - Akumulasi terdeteksi'},
        'ALREADY_ENTRY': {'icon': '📈', 'color': 'primary', 'desc': 'Sudah entry - Posisi terbuka V11b1'},
        'RUNNING': {'icon': '🚀', 'color': 'primary', 'desc': 'Posisi V11b1 sedang berjalan'},
        'WATCH': {'icon': '👁️', 'color': 'info', 'desc': 'Observasi - Tunggu konfirmasi'},
        'EXIT': {'icon': '🔴', 'color': 'danger', 'desc': 'Sinyal keluar - Distribusi terdeteksi'},
        'AVOID': {'icon': '⛔', 'color': 'danger', 'desc': 'Hindari - Distribusi kuat'},
        'WAIT': {'icon': '⏸️', 'color': 'secondary', 'desc': 'Tunggu - Belum ada sinyal jelas'}
    }
    v6_style = v6_action_map.get(v6_action, v6_action_map['WAIT'])

    # === SIGNAL HISTORY FOR CUSTOM FORMULA STOCKS (PANI, BREN, MBMA) ===
    use_custom_formula = has_custom_formula(stock_code)
    signal_history = None
    if use_custom_formula:
        try:
            # Auto-select V8 or V9 based on custom S/R zones
            signal_history = get_signal_history_auto(stock_code, '2025-01-02')
        except Exception as e:
            print(f"Error loading signal history: {e}")
            signal_history = {'error': str(e), 'signals': []}

    # ========== BUILD THE PAGE ==========
    return html.Div([
        # === ONE-LINE INSIGHT BAR (TOP HEADLINE) - INDONESIAN ===
        dbc.Alert([
            html.Div([
                html.I(className="fas fa-lightbulb me-2 text-warning"),
                html.Strong("Insight Hari Ini: ", className="me-1"),
                html.Span(insight_text),
            ], className="d-flex align-items-center flex-wrap")
        ], color=insight_color, className="mb-3 py-2", style={
            "borderLeft": f"4px solid var(--bs-{insight_color})",
            "backgroundColor": f"rgba(var(--bs-{insight_color}-rgb), 0.1)"
        }),

        # === PAGE HEADER WITH SUBMENU NAVIGATION ===
        # Title and submenu - stacked on mobile, inline on desktop
        html.Div([
            html.H4([
                html.I(className="fas fa-chart-pie me-2"),
                f"Analisis Detail - {stock_code}"
            ], className="mb-2 mb-lg-0"),
        ], className="mb-2"),
        html.Div([
            dcc.Link(dbc.Button([html.I(className="fas fa-chart-line me-2"), "Fundamental"], color="success", size="sm", className="me-2 mb-2 mb-lg-0"), href="/fundamental"),
            dcc.Link(dbc.Button([html.I(className="fas fa-layer-group me-2"), "Support & Resistance"], color="info", size="sm", className="me-2 mb-2 mb-lg-0"), href="/support-resistance"),
            dcc.Link(dbc.Button([html.I(className="fas fa-cubes me-2"), "Accumulation"], color="warning", size="sm", className="mb-2 mb-lg-0"), href="/accumulation"),
        ], className="d-flex flex-wrap mb-3"),

        # === 1. DECISION HERO CARD (V6 SYSTEM) ===
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Decision Icon & Action - NOW V6
                    dbc.Col([
                        html.Div([
                            html.Span(v6_style['icon'], style={"fontSize": "80px"}),
                            html.H1(v6_action, className=f"text-{v6_style['color']} fw-bold mb-0"),
                            html.P(v6_style['desc'], className="text-muted"),
                            # V10 Position Details (for RUNNING)
                            (lambda entry2, entry3, avg_price_2, avg_price_3, pl_e1, pl_avg2, pl_avg3, show_avg2, show_avg3: html.Div([
                                html.Hr(className="my-2"),
                                html.Div([
                                    html.Div([
                                        html.Small("Tanggal: ", className="text-muted"),
                                        html.Span(f"{v10_position['entry_date']}", className="text-warning fw-bold"),
                                    ], className="mb-1"),
                                    html.Div([
                                        html.Small("Entry 1: ", className="text-muted"),
                                        html.Span(f"Rp {v10_position['entry_price']:,.0f}", className="text-info fw-bold"),
                                        html.Span(" (30%)", className="text-warning fw-bold"),
                                    ], className="mb-1"),
                                    html.Div([
                                        html.Small("Entry 2: ", className="text-muted"),
                                        html.Span(f"Rp {entry2:,.0f}", className="text-info"),
                                        html.Span(" (30%)", className="text-warning"),
                                    ], className="mb-1"),
                                    html.Div([
                                        html.Small("Entry 3: ", className="text-muted"),
                                        html.Span(f"Rp {entry3:,.0f}", className="text-info"),
                                        html.Span(" (40%)", className="text-warning"),
                                    ], className="mb-1"),
                                    html.Hr(className="my-1"),
                                    html.Div([
                                        html.Small("Target: ", className="text-muted"),
                                        html.Span(f"Rp {v10_position['tp']:,.0f}", className="text-success fw-bold"),
                                    ], className="mb-1"),
                                    html.Div([
                                        html.Small("Stop Loss: ", className="text-muted"),
                                        html.Span(f"Rp {v10_position['sl']:,.0f}", className="text-danger fw-bold"),
                                    ], className="mb-1"),
                                    html.Hr(className="my-1"),
                                    # E1 Only
                                    html.Div([
                                        html.Small("E1 Only: ", className="text-muted fw-bold"),
                                        html.Span(f"P/L {pl_e1:+.1f}%", className=f"text-{'success' if pl_e1 > 0 else 'danger'} me-2"),
                                        html.Span(f"TP +{(v10_position['tp']-v10_position['entry_price'])/v10_position['entry_price']*100:.1f}%", className="text-success me-2"),
                                        html.Span(f"SL {(v10_position['sl']-v10_position['entry_price'])/v10_position['entry_price']*100:.1f}%", className="text-danger"),
                                    ], className="mb-1"),
                                    # Avg 1+2 - only show if price reached Entry 2
                                    html.Div([
                                        html.Small("Avg(1+2): ", className="text-muted fw-bold"),
                                        html.Span(f"P/L {pl_avg2:+.1f}%", className=f"text-{'success' if pl_avg2 > 0 else 'danger'} me-2"),
                                        html.Span(f"TP +{(v10_position['tp']-avg_price_2)/avg_price_2*100:.1f}%", className="text-success me-2"),
                                        html.Span(f"SL {(v10_position['sl']-avg_price_2)/avg_price_2*100:.1f}%", className="text-danger"),
                                        html.Small(f" @{avg_price_2:,.0f}", className="text-muted"),
                                    ], className="mb-1") if show_avg2 else None,
                                    # Avg 1+2+3 - only show if price reached Entry 3
                                    html.Div([
                                        html.Small("Avg(1+2+3): ", className="text-warning fw-bold"),
                                        html.Span(f"P/L {pl_avg3:+.1f}%", className=f"fw-bold text-{'success' if pl_avg3 > 0 else 'danger'} me-2"),
                                        html.Span(f"TP +{(v10_position['tp']-avg_price_3)/avg_price_3*100:.1f}%", className="text-success fw-bold me-2"),
                                        html.Span(f"SL {(v10_position['sl']-avg_price_3)/avg_price_3*100:.1f}%", className="text-danger fw-bold"),
                                        html.Small(f" @{avg_price_3:,.0f}", className="text-muted"),
                                    ]) if show_avg3 else None,
                                ], className="text-start small")
                            ], className="mt-2"))(
                                # Entry 2 = Entry1 - (Entry1 - SL) / 3
                                (e2 := v10_position['entry_price'] - (v10_position['entry_price'] - v10_position['sl']) / 3),
                                # Entry 3 = Entry1 - 2 * (Entry1 - SL) / 3
                                (e3 := v10_position['entry_price'] - 2 * (v10_position['entry_price'] - v10_position['sl']) / 3),
                                # Avg price for 1+2 (50% each)
                                (avg2 := 0.5 * v10_position['entry_price'] + 0.5 * e2),
                                # Avg price for 1+2+3 (30%, 30%, 40%)
                                (avg3 := 0.3 * v10_position['entry_price'] + 0.3 * e2 + 0.4 * e3),
                                # P/L for E1 only
                                (current_price - v10_position['entry_price']) / v10_position['entry_price'] * 100,
                                # P/L for Avg 1+2
                                (current_price - avg2) / avg2 * 100,
                                # P/L for Avg 1+2+3
                                (current_price - avg3) / avg3 * 100,
                                # Show Avg 1+2 only if current price <= Entry 2
                                current_price <= e2,
                                # Show Avg 1+2+3 only if current price <= Entry 3
                                current_price <= e3,
                            ) if v10_position else (
                            # V10 Criteria (only for ALREADY_ENTRY)
                            html.Div([
                                html.Hr(className="my-2"),
                                html.P([html.I(className="fas fa-check-double me-1"), "Kriteria Terpenuhi:"], className="text-success fw-bold small mb-2"),
                                html.Div([
                                    html.Div([html.I(className="fas fa-check text-success me-1"), html.Small(v6_entry.get('v10_criteria', {}).get('high_touch_resistance_desc', ''))], className="mb-1"),
                                    html.Div([html.I(className="fas fa-check text-success me-1"), html.Small(v6_entry.get('v10_criteria', {}).get('low_touch_support_desc', ''))], className="mb-1"),
                                    html.Div([html.I(className="fas fa-check text-success me-1"), html.Small(v6_entry.get('v10_criteria', {}).get('in_range_35pct_desc', ''))], className="mb-1"),
                                    html.Div([html.I(className="fas fa-check text-success me-1"), html.Small(v6_entry.get('v10_criteria', {}).get('hold_above_support_desc', ''))], className="mb-1"),
                                    html.Div([html.I(className="fas fa-check text-success me-1"), html.Small(v6_entry.get('v10_criteria', {}).get('confirmation_desc', ''))], className="mb-1"),
                                ], className="text-start small")
                            ], className="mt-2") if v6_action == 'ALREADY_ENTRY' and v6_entry and v6_entry.get('v10_criteria') else html.Div())
                        ], className="text-center")
                    ], md=3, className="border-end d-flex align-items-center justify-content-center"),

                    # Main Info
                    dbc.Col([
                        # Current Price & Change
                        html.Div([
                            html.H2([
                                html.Span(f"Rp {current_price:,.0f}", className="text-warning me-3"),
                                dbc.Badge(
                                    f"{accum.get('decision_rule', {}).get('current_vs_entry', 'N/A')}",
                                    color="success" if accum.get('decision_rule', {}).get('current_vs_entry') == 'IN_ZONE' else "warning" if accum.get('decision_rule', {}).get('current_vs_entry') == 'ABOVE' else "danger"
                                )
                            ], className="mb-2"),
                            # Price changes: Today, 1W, 1M
                            html.Div([
                                html.Span([
                                    html.Small("Hari Ini: ", className="text-muted"),
                                    html.Span(f"{change_today:+.2f}%", className=f"fw-bold text-{'success' if change_today > 0 else 'danger' if change_today < 0 else 'secondary'}")
                                ], className="me-3"),
                                html.Span([
                                    html.Small("1 Minggu: ", className="text-muted"),
                                    html.Span(f"{change_1w:+.2f}%", className=f"fw-bold text-{'success' if change_1w > 0 else 'danger' if change_1w < 0 else 'secondary'}")
                                ], className="me-3"),
                                html.Span([
                                    html.Small("1 Bulan: ", className="text-muted"),
                                    html.Span(f"{change_1m:+.2f}%", className=f"fw-bold text-{'success' if change_1m > 0 else 'danger' if change_1m < 0 else 'secondary'}")
                                ]),
                            ], className="mb-2"),
                            html.P(v6_action_reason if v6_action_reason else decision.get('reason', ''), className="mb-2"),
                        ]),

                        # V10 Metrics Row - Konfirmasi V11b1 based on price direction
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("Konfirmasi V11b1", className="text-muted"),
                                    html.Div([
                                        html.Strong(
                                            v11_confirm_type,
                                            className='text-' + (
                                                'success' if v11_confirm_type in ['RETEST_OK', 'BREAKOUT_OK'] else
                                                'info' if 'BREAKOUT' in str(v11_confirm_type) else
                                                'warning' if 'RETEST' in str(v11_confirm_type) else
                                                'secondary'
                                            )
                                        )
                                    ])
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small("Support Fix", className="text-muted"),
                                    html.Div([
                                        html.Strong(
                                            (lambda zones: next((f"{z['low']:,}-{z['high']:,}" for zn, z in sorted(zones.items(), reverse=True) if z['high'] < current_price), "N/A") if zones else "N/A")(get_zones(stock_code)),
                                            className='text-success'
                                        )
                                    ])
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small("Foreign 1 Minggu", className="text-muted"),
                                    html.Div([
                                        html.Strong(
                                            f"{'BUY' if weeks.get(1, {}).get('net_foreign_lot', 0) > 0 else 'SELL'} {abs(weeks.get(1, {}).get('net_foreign_lot', 0))/1000:.0f}K",
                                            className='text-' + ('success' if weeks.get(1, {}).get('net_foreign_lot', 0) > 0 else 'danger')
                                        )
                                    ])
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-3 py-2", style={"backgroundColor": "rgba(255,255,255,0.05)", "borderRadius": "8px"}),

                        # Formula V10 Zones Info
                        (lambda v10_zones, v10_support, v10_resistance, v10_s_dist, v10_r_dist, v10_in_zone, v10_has_position: dbc.Row([
                            dbc.Col([
                                html.H6([html.I(className="fas fa-layer-group text-info me-2"), "Formula V11b1"], className="mb-2"),
                                html.Div([
                                    html.Div([
                                        html.Span("S ", className="text-success fw-bold"),
                                        html.Span(v10_support, className="text-success small"),
                                        html.Span(f" ({v10_s_dist})", className="text-muted small"),
                                    ], className="mb-1"),
                                    html.Div([
                                        html.Span("R ", className="text-danger fw-bold"),
                                        html.Span(v10_resistance, className="text-danger small"),
                                        html.Span(f" ({v10_r_dist})", className="text-muted small"),
                                    ], className="mb-1"),
                                    html.Div([
                                        html.Span("Harga: ", className="text-muted small"),
                                        html.Span(f"Rp {current_price:,.0f}", className="text-warning fw-bold small"),
                                    ], className="mb-1"),
                                ]) if v10_zones else html.Small(f"Zona V11b1 belum dikonfigurasi untuk {stock_code}", className="text-muted")
                            ], md=6),
                            dbc.Col([
                                html.H6([html.I(className="fas fa-crosshairs text-warning me-2"), "Status V11b1"], className="mb-2"),
                                html.Div([
                                    dbc.Badge(
                                        # Use v11_confirm_type for consistency
                                        "BREAKOUT ZONE" if 'BREAKOUT' in v11_confirm_type and v10_in_zone else
                                        "BREAKOUT" if 'BREAKOUT' in v11_confirm_type else
                                        "RETEST ZONE" if v10_in_zone else
                                        "DI ANTARA ZONA" if v11_confirm_type == 'PANTAU' else
                                        "DI ATAS ZONA" if v10_resistance == "-" else "DI ANTARA ZONA",
                                        color="info" if 'BREAKOUT' in v11_confirm_type else "success" if v10_in_zone else "secondary",
                                        className="mb-2"
                                    ),
                                    html.Div([
                                        html.Small("Entry: ", className="text-muted"),
                                        html.Small(
                                            "TAMBAH POSISI 30% (avg)" if v10_has_position and v10_in_zone else
                                            "Tunggu retest untuk avg" if v10_has_position and not v10_in_zone and 'RETEST' in v11_confirm_type else
                                            "Tunggu breakout konfirmasi" if 'BREAKOUT' in v11_confirm_type and 'OK' not in v11_confirm_type else
                                            "Siap entry (breakout)" if 'BREAKOUT_OK' in v11_confirm_type else
                                            "Siap entry 30%" if v10_in_zone and 'RETEST' in v11_confirm_type else
                                            "Tunggu retest" if 'RETEST' in v11_confirm_type else
                                            "Tunggu retest/breakout" if v11_confirm_type == 'PANTAU' else "Pantau",
                                            className="text-success fw-bold" if 'OK' in v11_confirm_type or (v10_in_zone and 'RETEST' in v11_confirm_type) else "text-info"
                                        ),
                                    ]),
                                ]) if v10_zones else html.Small("-", className="text-muted")
                            ], md=6),
                        ]))(
                            get_zones(stock_code),
                            (lambda zs: next((f"{z['low']:,}-{z['high']:,}" for zn, z in sorted(zs.items(), reverse=True) if z['high'] < current_price), "-") if zs else "-")(get_zones(stock_code)),
                            (lambda zs: next((f"{z['low']:,}-{z['high']:,}" for zn, z in sorted(zs.items()) if z['low'] > current_price), "-") if zs else "-")(get_zones(stock_code)),
                            (lambda zs: next((f"{abs(current_price - z['high'])/current_price*100:.1f}%" for zn, z in sorted(zs.items(), reverse=True) if z['high'] < current_price), "-") if zs else "-")(get_zones(stock_code)),
                            (lambda zs: next((f"{abs(z['low'] - current_price)/current_price*100:.1f}%" for zn, z in sorted(zs.items()) if z['low'] > current_price), "-") if zs else "-")(get_zones(stock_code)),
                            (lambda zs: any(z['low'] <= current_price <= z['high'] * 1.02 for z in zs.values()) if zs else False)(get_zones(stock_code)),
                            v10_position is not None,
                        )
                    ], md=9)
                ])
            ])
        ], className="mb-4", style={"border": f"3px solid var(--bs-{v6_style['color']})", "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"}),

        # === DISCLAIMER ===
        html.Div([
            html.Small([
                html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                html.Strong("Disclaimer: ", className="text-warning"),
                "Informasi di atas bukan merupakan ajakan untuk membeli atau menjual saham tertentu. ",
                "Analisis ini dibuat berdasarkan formulasi teknikal dan data historis yang tidak menjamin hasil di masa depan. ",
                "Keputusan investasi sepenuhnya menjadi tanggung jawab Anda. ",
                "Untuk keputusan investasi yang lebih tepat, ",
                html.Strong("konsultasikan dengan penasihat keuangan profesional"),
                " yang memahami profil risiko dan tujuan keuangan Anda."
            ], className="text-muted", style={"fontSize": "11px", "lineHeight": "1.4"})
        ], className="text-center mb-3 px-3 py-2", style={
            "backgroundColor": "rgba(255,193,7,0.1)",
            "borderRadius": "5px",
            "border": "1px dashed rgba(255,193,7,0.3)"
        }),

        # === IMPULSE/MOMENTUM ALERT (tertinggi prioritas) - INDONESIAN ===
        dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("[!]", style={"fontSize": "32px"}),
                        html.Strong(f" MOMENTUM TERDETEKSI ({impulse_signal.get('strength', '')})", className="text-danger fs-5 ms-2"),
                    ], className="d-flex align-items-center"),
                    html.P([
                        html.Strong("Pergerakan agresif tanpa fase akumulasi. "),
                        "Volume ", html.Strong(f"{impulse_signal.get('metrics', {}).get('volume_ratio', 0):.1f}x"),
                        " rata-rata dengan breakout ", html.Strong(f"+{impulse_signal.get('metrics', {}).get('breakout_pct', 0):.1f}%"),
                        " dari high terdekat."
                    ], className="mb-0 small"),
                ], md=8),
                dbc.Col([
                    html.Div([
                        html.Small("Kondisi Pemicu", className="text-muted d-block"),
                        html.Div([
                            dbc.Badge("[v] Vol 2x" if impulse_signal.get('metrics', {}).get('is_volume_spike') else "o Vol 2x",
                                      color="success" if impulse_signal.get('metrics', {}).get('is_volume_spike') else "secondary", className="me-1"),
                            dbc.Badge("[v] Breakout" if impulse_signal.get('metrics', {}).get('is_breakout') else "o Breakout",
                                      color="success" if impulse_signal.get('metrics', {}).get('is_breakout') else "secondary", className="me-1"),
                            dbc.Badge(f"[v] CPR {impulse_signal.get('metrics', {}).get('today_cpr_pct', 0):.0f}%" if impulse_signal.get('metrics', {}).get('is_cpr_bullish') else f"o CPR {impulse_signal.get('metrics', {}).get('today_cpr_pct', 0):.0f}%",
                                      color="success" if impulse_signal.get('metrics', {}).get('is_cpr_bullish') else "secondary"),
                        ])
                    ]),
                ], md=4, className="text-end"),
            ]),
        ], color="danger", className="mb-3", style={"backgroundColor": "rgba(220,53,69,0.15)", "border": "2px solid #dc3545"})
        if impulse_signal.get('impulse_detected') else html.Div(),

        # === NEAR IMPULSE ALERT (hampir impulse) - INDONESIAN ===
        dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("[+]", style={"fontSize": "28px"}),
                        html.Strong(f" HAMPIR IMPULSE ({impulse_signal.get('trigger_conditions', {}).get('conditions_met', 0)}/3 kondisi)", className="text-info fs-6 ms-2"),
                    ], className="d-flex align-items-center"),
                    html.P("Satu atau dua kondisi belum terpenuhi. Pantau volume dan pergerakan harga besok.", className="mb-0 small"),
                ], md=12),
            ]),
        ], color="info", className="mb-3", style={"backgroundColor": "rgba(23,162,184,0.15)", "border": "1px solid #17a2b8"})
        if impulse_signal.get('near_impulse') and not impulse_signal.get('impulse_detected') else html.Div(),

        # === MARKUP TRIGGER ALERT (setelah akumulasi) - INDONESIAN ===
        dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("[FIRE]", style={"fontSize": "28px"}),
                        html.Strong(" MARKUP TERDETEKSI", className="text-warning fs-5 ms-2"),
                    ], className="d-flex align-items-center"),
                    html.P([
                        "Harga breakout ", html.Strong(f"+{markup_trigger.get('breakout_pct', 0):.1f}%"),
                        " dari resistance terdekat setelah akumulasi terdeteksi sebelumnya."
                    ], className="mb-0 small"),
                ], md=9),
                dbc.Col([
                    html.Div([
                        html.Small("Lonjakan Volume", className="text-muted d-block"),
                        dbc.Badge(f"+{markup_trigger.get('volume_spike_pct', 0):.0f}%" if markup_trigger.get('volume_spike') else "Normal",
                                  color="success" if markup_trigger.get('volume_spike') else "secondary"),
                    ]),
                ], md=3, className="text-end"),
            ]),
        ], color="warning", className="mb-3", style={"backgroundColor": "rgba(255,193,7,0.15)", "border": "2px solid #ffc107"})
        if markup_trigger.get('markup_triggered') and not impulse_signal.get('impulse_detected') else html.Div(),

        # === 2. QUICK SUMMARY FROM 3 SUBMENUS (Cards) ===
        dbc.Row([
            # FUNDAMENTAL CARD
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-chart-line me-2 text-success"), "Fundamental"], className="mb-0 d-inline"),
                        dcc.Link(html.Small("Detail ^", className="float-end text-info"), href="/fundamental")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small([
                                        html.Span("PER", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS['per']),
                                        html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                                    ], className="text-muted d-block"),
                                    html.H4(f"{fundamental.get('per', 0):.1f}x" if fundamental.get('has_data') else "N/A", className="mb-0 text-info"),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small([
                                        html.Span("PBV", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS['pbv']),
                                        html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                                    ], className="text-muted d-block"),
                                    html.H4(f"{fundamental.get('pbvr', 0):.1f}x" if fundamental.get('has_data') else "N/A", className="mb-0 text-info"),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small([
                                        html.Span("ROE", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS['roe']),
                                        html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                                    ], className="text-muted d-block"),
                                    html.H4(f"{fundamental.get('roe', 0)*100:.1f}%" if fundamental.get('has_data') else "N/A", className="mb-0 text-info"),
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-2"),
                        html.Hr(className="my-2"),
                        html.Div([
                            html.Small("Valuasi: ", className="text-muted"),
                            dbc.Badge(fundamental.get('valuation', 'N/A'), color=fundamental.get('valuation_color', 'secondary'))
                        ], className="text-center")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], md=4),

            # SUPPORT & RESISTANCE FIX CARD
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-layer-group me-2 text-info"), "S/R Fix (V11b1)"], className="mb-0 d-inline"),
                    ]),
                    dbc.CardBody([
                        # Get fixed zones for stock
                        html.Div([
                            # Find nearest support and resistance from fixed zones
                            *([
                                html.Div([
                                    html.Div([
                                        html.Span(f"S: {support_zone['low']:,}-{support_zone['high']:,}", className="small text-success"),
                                    ], className="text-start", style={"width": "40%"}),
                                    html.Div([
                                        html.Span(f"Rp {current_price:,.0f}", className="small text-warning fw-bold"),
                                    ], className="text-center", style={"width": "20%"}),
                                    html.Div([
                                        html.Span(f"R: {resistance_zone['low']:,}-{resistance_zone['high']:,}", className="small text-danger"),
                                    ], className="text-end", style={"width": "40%"}),
                                ], className="d-flex justify-content-between mb-2"),
                                html.Div([
                                    dbc.Progress([
                                        dbc.Progress(value=min(100, max(0, int((current_price - support_zone['high']) / (resistance_zone['low'] - support_zone['high']) * 100) if resistance_zone['low'] > support_zone['high'] else 50)), color="info", bar=True),
                                    ], style={"height": "8px"})
                                ], className="mb-2"),
                                html.Div([
                                    html.Small(f"Jarak S: {abs(current_price - support_zone['high'])/current_price*100:.1f}%", className="text-success me-2"),
                                    html.Small(f"Jarak R: {abs(resistance_zone['low'] - current_price)/current_price*100:.1f}%", className="text-danger"),
                                ], className="text-center small"),
                            ] if (zones := get_zones(stock_code)) and
                                 (support_zone := next((z for zn, z in sorted(zones.items(), reverse=True) if z['high'] < current_price), None)) and
                                 (resistance_zone := next((z for zn, z in sorted(zones.items()) if z['low'] > current_price), None))
                              else [html.Small(f"Zona belum dikonfigurasi untuk {stock_code}", className="text-muted text-center d-block")]),
                        ]),
                        html.Hr(className="my-2"),
                        html.Div([
                            html.Small("Posisi: ", className="text-muted"),
                            dbc.Badge(
                                "Dekat Support" if (zones := get_zones(stock_code)) and any(z['low'] <= current_price <= z['high'] * 1.03 for z in zones.values()) else
                                "Dekat Resistance" if zones and any(z['low'] * 0.97 <= current_price <= z['high'] for z in zones.values()) else
                                "Di Antara Zona",
                                color="success" if (zones := get_zones(stock_code)) and any(z['low'] <= current_price <= z['high'] * 1.03 for z in zones.values()) else
                                      "danger" if zones and any(z['low'] * 0.97 <= current_price <= z['high'] for z in zones.values()) else "secondary"
                            )
                        ], className="text-center") if get_zones(stock_code) else None
                    ])
                ], color="dark", outline=True, className="h-100")
            ], md=4),

            # KONFIRMASI V11b1 CARD
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([
                            html.I(className="fas fa-clipboard-check me-2 text-warning"),
                            html.Span("Konfirmasi V11b1")
                        ], className="mb-0 d-inline"),
                    ]),
                    dbc.CardBody([
                        # Fase
                        html.Div([
                            html.Small("Fase", className="text-muted d-block"),
                            dbc.Badge(
                                "RUNNING" if v10_position else ("SIAP ENTRY" if (lambda zs: any(z['low'] <= current_price <= z['high'] * 1.02 for z in zs.values()) if zs else False)(get_zones(stock_code)) else "WAIT"),
                                color="warning" if v10_position else ("success" if (lambda zs: any(z['low'] <= current_price <= z['high'] * 1.02 for z in zs.values()) if zs else False)(get_zones(stock_code)) else "secondary"),
                                className="text-dark" if v10_position else "",
                            ),
                        ], className="text-center mb-2"),
                        html.Hr(className="my-2"),
                        # V10 Checklist - different for BREAKOUT vs RETEST
                        html.Small(f"Checklist V11b1 ({'BREAKOUT' if 'BREAKOUT' in v11_confirm_type else 'PANTAU' if v11_confirm_type == 'PANTAU' else 'RETEST'}):", className="text-muted d-block mb-1"),
                        (lambda ec, pos_vol: html.Div([
                            # Use stored entry conditions from position
                            html.Div([
                                html.I(className=f"fas fa-{'check' if ec.get('touch_support') else 'times'} text-{'success' if ec.get('touch_support') else 'danger'} me-1"),
                                html.Small("Touch Support", className="text-muted"),
                            ], className="mb-1"),
                            html.Div([
                                html.I(className=f"fas fa-{'check' if ec.get('hold_above_slow') else 'times'} text-{'success' if ec.get('hold_above_slow') else 'danger'} me-1"),
                                html.Small("Hold di Atas S_low", className="text-muted"),
                            ], className="mb-1"),
                            html.Div([
                                html.I(className=f"fas fa-{'check' if ec.get('within_35pct') else 'times'} text-{'success' if ec.get('within_35pct') else 'danger'} me-1"),
                                html.Small("Dalam 35% ke TP", className="text-muted"),
                            ], className="mb-1"),
                            html.Div([
                                html.I(className=f"fas fa-{'check' if ec.get('prior_r_touch') else 'times'} text-{'success' if ec.get('prior_r_touch') else 'danger'} me-1"),
                                html.Small("Prior R Touch", className="text-muted"),
                            ], className="mb-1"),
                            html.Div([
                                html.I(className=f"fas fa-{'check' if ec.get('reclaim') else 'times'} text-{'success' if ec.get('reclaim') else 'danger'} me-1"),
                                html.Small("Konfirmasi Reclaim", className="text-muted"),
                            ], className="mb-1"),
                            # V11b1: Volume >= 1.0x (use vol_ratio from position directly)
                            html.Div([
                                html.I(className=f"fas fa-{'check' if pos_vol >= 1.0 else 'times'} text-{'success' if pos_vol >= 1.0 else 'danger'} me-1"),
                                html.Small(f"Volume >= 1.0x ({pos_vol:.2f}x)", className="text-muted"),
                            ], className="mb-1"),
                        ]))(v10_position.get('entry_conditions', {}), v10_position.get('vol_ratio', 0)) if v10_position and v10_position.get('entry_conditions') else (
                        # Calculate current conditions - different checklist for BREAKOUT vs RETEST
                        (lambda zones, support_zone, cur_vol_ratio, is_breakout, days_above, from_below: html.Div([
                            # BREAKOUT checklist
                            html.Div([
                                html.I(className=f"fas fa-{'check' if from_below else 'times'} text-{'success' if from_below else 'danger'} me-1"),
                                html.Small("Dari Bawah Zona (7 hari)", className="text-muted"),
                            ], className="mb-1") if is_breakout else html.Div([
                                html.I(className=f"fas fa-{'check' if support_zone and current_price <= support_zone['high'] * 1.02 else 'times'} text-{'success' if support_zone and current_price <= support_zone['high'] * 1.02 else 'danger'} me-1"),
                                html.Small("Touch Support", className="text-muted"),
                            ], className="mb-1"),

                            html.Div([
                                html.I(className=f"fas fa-{'check' if support_zone and current_price > support_zone['high'] else 'times'} text-{'success' if support_zone and current_price > support_zone['high'] else 'danger'} me-1"),
                                html.Small("Close > Zone High", className="text-muted"),
                            ], className="mb-1") if is_breakout else html.Div([
                                html.I(className=f"fas fa-{'check' if support_zone and current_price >= support_zone['low'] else 'times'} text-{'success' if support_zone and current_price >= support_zone['low'] else 'danger'} me-1"),
                                html.Small("Hold di Atas S_low", className="text-muted"),
                            ], className="mb-1"),

                            html.Div([
                                html.I(className=f"fas fa-{'check' if days_above >= 3 else 'times'} text-{'success' if days_above >= 3 else 'warning'} me-1"),
                                html.Small(f"3 Hari di Atas Zona ({days_above}/3)", className="text-muted"),
                            ], className="mb-1") if is_breakout else html.Div([
                                html.I(className=f"fas fa-{'check' if support_zone and (lambda tp: current_price <= support_zone['high'] + 0.35 * (tp - support_zone['high']))(next((z['low'] * 0.98 for zn, z in sorted(zones.items()) if z['low'] > current_price), current_price * 1.2)) else 'times'} text-{'success' if support_zone and (lambda tp: current_price <= support_zone['high'] + 0.35 * (tp - support_zone['high']))(next((z['low'] * 0.98 for zn, z in sorted(zones.items()) if z['low'] > current_price), current_price * 1.2)) else 'danger'} me-1"),
                                html.Small("Dalam 35% ke TP", className="text-muted"),
                            ], className="mb-1"),

                            # V11b1: Volume >= 1.0x (same for both)
                            html.Div([
                                html.I(className=f"fas fa-{'check' if cur_vol_ratio >= 1.0 else 'times'} text-{'success' if cur_vol_ratio >= 1.0 else 'danger'} me-1"),
                                html.Small(f"Volume >= 1.0x ({cur_vol_ratio:.2f}x)", className="text-muted"),
                            ], className="mb-1"),
                        ]) if zones else html.Small("Zona belum dikonfigurasi", className="text-muted"))(
                            get_zones(stock_code),
                            (lambda zs: next((z for zn, z in sorted(zs.items(), reverse=True) if z['high'] < current_price * 1.02), None) if zs else None)(get_zones(stock_code)),
                            v11b_vol_ratio,
                            'BREAKOUT' in v11_confirm_type,
                            breakout_days_above if 'breakout_days_above' in dir() else 0,
                            came_from_below if 'came_from_below' in dir() else False
                        ))
                    ])
                ], color="dark", outline=True, className="h-100")
            ], md=4),
        ], className="mb-4"),

        # === 5.5 BACKTEST HISTORY V11b1 ===
        (lambda bt_result: dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-history me-2 text-info"),
                    "Backtest V11b1 History"
                ], className="mb-0 d-inline"),
                dbc.Badge(
                    f"{len(bt_result.get('trades', []))} trades" if bt_result else "No data",
                    color="info",
                    className="ms-2"
                ),
                dbc.Badge(
                    f"Win Rate: {bt_result.get('win_rate', 0):.0f}%" if bt_result else "",
                    color="success" if bt_result and bt_result.get('win_rate', 0) >= 70 else "warning" if bt_result and bt_result.get('win_rate', 0) >= 50 else "danger",
                    className="ms-2"
                ) if bt_result and bt_result.get('trades') else None,
                dbc.Badge(
                    f"Total: {bt_result.get('total_pnl', 0):+.1f}%" if bt_result else "",
                    color="success" if bt_result and bt_result.get('total_pnl', 0) > 0 else "danger",
                    className="ms-2"
                ) if bt_result and bt_result.get('trades') else None,
            ]),
            dbc.CardBody([
                # Trade list
                html.Div([
                    html.Div([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    # Trade number and type badge
                                    html.Span(f"#{idx}", className="fw-bold text-muted me-2"),
                                    dbc.Badge(
                                        t.get('type', 'UNKNOWN'),
                                        color="warning" if 'RETEST' in t.get('type', '') else "info",
                                        className="me-2 text-dark" if 'RETEST' in t.get('type', '') else "me-2"
                                    ),
                                    dbc.Badge(
                                        f"Z{t.get('zone_num', '?')}",
                                        color="secondary",
                                        className="me-2"
                                    ),
                                ], className="mb-1"),
                                # Dates
                                html.Div([
                                    html.I(className="fas fa-sign-in-alt text-success me-1"),
                                    html.Small(t.get('entry_date', '-'), className="text-success me-3"),
                                    html.I(className="fas fa-sign-out-alt text-danger me-1"),
                                    html.Small(t.get('exit_date', '-'), className="text-danger me-2"),
                                    html.Small(f"({t.get('exit_reason', '-')})", className="text-muted"),
                                ], className="mb-1"),
                            ], width=6),
                            dbc.Col([
                                # Prices
                                html.Div([
                                    html.Small("Entry: ", className="text-muted"),
                                    html.Span(f"Rp {t.get('entry_price', 0):,.0f}", className="text-info me-3"),
                                    html.Small("Exit: ", className="text-muted"),
                                    html.Span(f"Rp {t.get('exit_price', 0):,.0f}", className="text-warning"),
                                ], className="mb-1"),
                                # P/L
                                html.Div([
                                    html.Small("SL: ", className="text-muted"),
                                    html.Span(f"{t.get('sl', 0):,.0f}", className="text-danger small me-3"),
                                    html.Small("TP: ", className="text-muted"),
                                    html.Span(f"{t.get('tp', 0):,.0f}", className="text-success small me-3"),
                                    dbc.Badge(
                                        f"{t.get('pnl', 0):+.1f}%",
                                        color="success" if t.get('pnl', 0) > 0 else "danger",
                                        className="ms-2 fs-6"
                                    ),
                                ]),
                            ], width=6, className="text-end"),
                        ], className="align-items-center"),
                        html.Hr(className="my-2") if idx < len(bt_result.get('trades', [])) else None,
                    ]) for idx, t in enumerate(bt_result.get('trades', []), 1)
                ], style={"maxHeight": "400px", "overflowY": "auto"}) if bt_result and bt_result.get('trades') else html.Div([
                    html.I(className="fas fa-info-circle text-muted me-2"),
                    html.Span("Tidak ada data backtest untuk saham ini", className="text-muted")
                ], className="text-center py-3"),
                # Summary footer
                html.Div([
                    html.Hr(className="my-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small("Total Trades", className="text-muted d-block"),
                            html.Strong(f"{len(bt_result.get('trades', []))}", className="text-info"),
                        ], className="text-center"),
                        dbc.Col([
                            html.Small("Wins", className="text-muted d-block"),
                            html.Strong(f"{bt_result.get('wins', 0)}", className="text-success"),
                        ], className="text-center"),
                        dbc.Col([
                            html.Small("Losses", className="text-muted d-block"),
                            html.Strong(f"{bt_result.get('losses', 0)}", className="text-danger"),
                        ], className="text-center"),
                        dbc.Col([
                            html.Small("Win Rate", className="text-muted d-block"),
                            html.Strong(f"{bt_result.get('win_rate', 0):.0f}%",
                                       className=f"text-{'success' if bt_result.get('win_rate', 0) >= 70 else 'warning' if bt_result.get('win_rate', 0) >= 50 else 'danger'}"),
                        ], className="text-center"),
                        dbc.Col([
                            html.Small("Total P/L", className="text-muted d-block"),
                            html.Strong(f"{bt_result.get('total_pnl', 0):+.1f}%",
                                       className=f"text-{'success' if bt_result.get('total_pnl', 0) > 0 else 'danger'}"),
                        ], className="text-center"),
                    ])
                ]) if bt_result and bt_result.get('trades') else None,
            ])
        ], color="dark", outline=True, className="mb-4") if get_zones(stock_code) else html.Div())(
            run_v11b1_backtest(stock_code) if run_v11b1_backtest and get_zones(stock_code) else None
        ),

        # === 6. WEEKLY ACCUMULATION ANALYSIS (Key Point dari Accumulation) ===
        dbc.Card([
            dbc.CardHeader([
                html.H5([html.I(className="fas fa-layer-group me-2"), "Akumulasi 4 Minggu Terakhir"], className="mb-0 d-inline"),
                dbc.Badge(
                    f"Avg VR: {sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4:.2f}x",
                    color="success" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 4.0 else
                          "warning" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 > 1.5 else
                          "danger" if sum(weeks.get(w, {}).get('vol_ratio', 1) for w in range(1, 5)) / 4 < 0.8 else "secondary",
                    className="ms-2"
                ),
            ]),
            dbc.CardBody([
                # Weekly Vol Ratio Cards - Compact
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Small(f"{'Minggu Ini' if w == 1 else f'{w}W Lalu'}", className="text-muted d-block text-center"),
                            html.Div([
                                html.Span(weeks.get(w, {}).get('phase_icon', '?'), style={"fontSize": "18px"}),
                                html.Strong(f" {weeks.get(w, {}).get('vol_ratio', 0):.1f}x",
                                           className=f"text-{weeks.get(w, {}).get('phase_color', 'secondary')}")
                            ], className="text-center"),
                            # Vol Lower vs Upper bar
                            dbc.Progress([
                                dbc.Progress(
                                    value=weeks.get(w, {}).get('vol_lower', 0) / max(1, weeks.get(w, {}).get('vol_lower', 0) + weeks.get(w, {}).get('vol_upper', 0)) * 100,
                                    color="success", bar=True
                                ),
                                dbc.Progress(
                                    value=weeks.get(w, {}).get('vol_upper', 0) / max(1, weeks.get(w, {}).get('vol_lower', 0) + weeks.get(w, {}).get('vol_upper', 0)) * 100,
                                    color="danger", bar=True
                                ),
                            ], style={"height": "8px"}, className="mt-1"),
                            # Net Market & Foreign compact
                            html.Small([
                                html.Span(
                                    f"{'B' if weeks.get(w, {}).get('vol_lower', 0) > weeks.get(w, {}).get('vol_upper', 0) else 'S'} ",
                                    className=f"text-{'success' if weeks.get(w, {}).get('vol_lower', 0) > weeks.get(w, {}).get('vol_upper', 0) else 'danger'} fw-bold"
                                ),
                                html.Span(f"{abs(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0))/100/1000:.0f}K", className="text-muted")
                            ], className="d-block text-center"),
                            html.Small([
                                html.Span("F:", className="text-muted"),
                                html.Span(
                                    f"{'B' if weeks.get(w, {}).get('net_foreign_lot', 0) > 0 else 'S'}",
                                    className=f"text-{'success' if weeks.get(w, {}).get('net_foreign_lot', 0) > 0 else 'danger'} fw-bold"
                                ),
                                html.Span(f"{abs(weeks.get(w, {}).get('net_foreign_lot', 0))/1000:.0f}K", className="text-muted")
                            ], className="d-block text-center"),
                        ], className="p-2 rounded", style={"backgroundColor": f"rgba({'40,167,69' if weeks.get(w, {}).get('phase') == 'ACCUMULATION' else '220,53,69' if weeks.get(w, {}).get('phase') == 'DISTRIBUTION' else '108,117,125'}, 0.15)"})
                    ], width=3) for w in [1, 2, 3, 4]
                ], className="mb-3"),

                # Phase Progression & Summary
                html.Div([
                    # Phase progression icons
                    html.Div([
                        html.Span(weeks.get(4, {}).get('phase_icon', '?'), style={"fontSize": "20px"}),
                        html.I(className="fas fa-arrow-right mx-1 text-muted small"),
                        html.Span(weeks.get(3, {}).get('phase_icon', '?'), style={"fontSize": "20px"}),
                        html.I(className="fas fa-arrow-right mx-1 text-muted small"),
                        html.Span(weeks.get(2, {}).get('phase_icon', '?'), style={"fontSize": "20px"}),
                        html.I(className="fas fa-arrow-right mx-1 text-muted small"),
                        html.Span(weeks.get(1, {}).get('phase_icon', '?'), style={"fontSize": "20px"}),
                    ], className="text-center mb-2"),

                    # Summary stats
                    dbc.Row([
                        dbc.Col([
                            html.Small("Net Market 4W", className="text-muted d-block text-center"),
                            html.Strong([
                                html.Span(
                                    f"{'BUY' if sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)) > 0 else 'SELL'} ",
                                    className=f"text-{'success' if sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)) > 0 else 'danger'}"
                                ),
                                html.Span(f"{abs(sum(weeks.get(w, {}).get('vol_lower', 0) - weeks.get(w, {}).get('vol_upper', 0) for w in range(1, 5)))/100/1e6:.2f}M Lot")
                            ], className="d-block text-center small")
                        ], width=4),
                        dbc.Col([
                            html.Small("Net Foreign 4W", className="text-muted d-block text-center"),
                            html.Strong([
                                html.Span(
                                    f"{'BUY' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'SELL'} ",
                                    className=f"text-{'success' if sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)) > 0 else 'danger'}"
                                ),
                                html.Span(f"{abs(sum(weeks.get(w, {}).get('net_foreign_lot', 0) for w in range(1, 5)))/1e6:.2f}M Lot")
                            ], className="d-block text-center small")
                        ], width=4),
                        dbc.Col([
                            html.Small("Minggu Akumulasi", className="text-muted d-block text-center"),
                            html.Strong([
                                html.Span(f"{sum(1 for w in range(1, 5) if weeks.get(w, {}).get('phase') == 'ACCUMULATION')}/4",
                                         className=f"text-{'success' if sum(1 for w in range(1, 5) if weeks.get(w, {}).get('phase') == 'ACCUMULATION') >= 3 else 'warning' if sum(1 for w in range(1, 5) if weeks.get(w, {}).get('phase') == 'ACCUMULATION') >= 2 else 'danger'}")
                            ], className="d-block text-center")
                        ], width=4),
                    ])
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"}),

                # Vol Ratio Threshold Guide
                html.Hr(className="my-2"),
                html.Small([
                    html.I(className="fas fa-info-circle me-1"),
                    html.Span("VR>4.0", className="text-success fw-bold"), "=Akumulasi Kuat | ",
                    html.Span("VR 1.5-4.0", className="text-warning fw-bold"), "=Weak Acc | ",
                    html.Span("VR<0.8", className="text-danger fw-bold"), "=Distribusi"
                ], className="text-muted text-center d-block")
            ])
        ], className="mb-4", color="dark", outline=True),
    ])


def create_enhanced_alerts_list(alerts):
    """Create enhanced alerts list with priority indicators and broker type info - Mobile Responsive"""
    if not alerts:
        return dbc.Alert("No active alerts", color="secondary")

    alert_items = []
    for alert in alerts:
        priority_color = {
            'HIGH': 'danger',
            'MEDIUM': 'warning',
            'LOW': 'info'
        }.get(alert.get('priority', 'LOW'), 'secondary')

        # Check if alert has broker info
        broker_code = alert.get('broker', None)
        broker_badge = None

        if broker_code:
            broker_type = get_broker_type(broker_code)

            # Map broker type to label
            type_labels = {
                'FOREIGN': 'ASING',
                'BUMN': 'BUMN',
                'LOCAL': 'LOKAL'
            }
            type_label = type_labels.get(broker_type, 'LOKAL')

            broker_badge = html.Span([
                html.Span(
                    broker_code,
                    className=f"broker-badge broker-badge-{broker_type.lower()} me-1",
                    style={'fontSize': '0.7rem', 'padding': '2px 6px'}
                ),
                html.Span(
                    type_label,
                    className=f"broker-badge broker-badge-{broker_type.lower()}",
                    style={'opacity': '0.85', 'fontSize': '0.65rem', 'padding': '2px 4px'}
                )
            ], className="d-block d-md-inline mt-1 mt-md-0")

        # Mobile-friendly layout: stack vertically on mobile, horizontal on desktop
        alert_items.append(
            dbc.Alert([
                # Badges row - wrap on mobile
                html.Div([
                    dbc.Badge(alert.get('priority', 'N/A'), color=priority_color, className="me-1 mb-1", style={'fontSize': '0.7rem'}),
                    dbc.Badge(alert.get('type', '').replace('_', ' '), color="light", text_color="dark", className="me-1 mb-1", style={'fontSize': '0.65rem'}),
                    broker_badge if broker_badge else None,
                ], className="d-flex flex-wrap align-items-center mb-2"),
                # Message
                html.Div([
                    html.Strong(alert.get('message', ''), style={'fontSize': '0.85rem'}),
                    html.Br(),
                    html.Small(alert.get('detail', ''), className="text-muted", style={'fontSize': '0.75rem'})
                ])
            ], color=priority_color, className="mb-2 py-2 px-2")
        )

    return html.Div(alert_items)


def create_broker_sensitivity_table(data):
    """Create broker sensitivity ranking table with Lead Time, Win Rate, and Broker Type"""
    if not data or not data.get('brokers'):
        return html.Div("No sensitivity data available")

    brokers = data['brokers'][:20]  # Top 20
    lookback_days = data.get('lookback_days', 60)  # Get lookback period

    # Create HTML table with proper broker colors
    table = html.Table([
        html.Thead(html.Tr([
            html.Th("#", style={"width": "40px"}),
            html.Th("Broker", style={"width": "70px"}),
            html.Th("Tipe", style={"width": "120px"}),
            html.Th("Win Rate", style={"width": "80px"}),
            html.Th("Lead Time", style={"width": "80px"}),
            html.Th("Correlation", style={"width": "90px"}),
            html.Th("Score", style={"width": "60px"}),
            html.Th("Accum Days", style={"width": "90px"}),
            html.Th("Signals", style={"width": "70px"})
        ])),
        html.Tbody([
            html.Tr([
                html.Td(i + 1),
                html.Td(colored_broker(b['broker_code'], with_badge=True)),
                html.Td(html.Span(
                    get_broker_info(b['broker_code'])['type_name'],
                    className=f"broker-{get_broker_type(b['broker_code']).lower()}"
                )),
                html.Td(f"{b['win_rate']:.0f}%"),
                html.Td(f"{b['avg_lead_time']:.1f}d"),
                html.Td(f"{b['correlation']:.0f}%"),
                html.Td(f"{b['sensitivity_score']:.0f}"),
                html.Td(b['accum_days']),
                html.Td(b['successful_signals'])
            ]) for i, b in enumerate(brokers)
        ])
    ], className="table table-sm table-dark table-hover", style={"fontSize": "12px"})

    # Broker legend
    broker_legend = html.Div([
        html.Small("Legenda Broker: ", className="text-muted me-2"),
        html.Span([
            html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['FOREIGN'], "fontSize": "10px"}),
            "Asing "
        ], className="me-3", style={"fontSize": "11px"}),
        html.Span([
            html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['BUMN'], "fontSize": "10px"}),
            "BUMN "
        ], className="me-3", style={"fontSize": "11px"}),
        html.Span([
            html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['LOCAL'], "fontSize": "10px"}),
            "Lokal "
        ], style={"fontSize": "11px"}),
    ], className="mb-2")

    # Add legend/explanation
    legend = html.Div([
        html.Hr(),
        html.H6("Penjelasan Kolom:", className="text-info mb-2"),
        dbc.Row([
            dbc.Col([
                html.Small([
                    html.Strong("Win Rate: "), "% kejadian broker akumulasi -> harga naik >= 10% dalam 10 hari.", html.Br(),
                    html.Strong("Lead Time: "), "Rata-rata berapa hari SEBELUM harga naik, broker mulai akumulasi."
                ], className="text-muted")
            ], width=6),
            dbc.Col([
                html.Small([
                    html.Strong("Score: "), "Gabungan Win Rate, Lead Time, dan Korelasi (0-100).", html.Br(),
                    html.Strong("Signals: "), "Jumlah sinyal akumulasi yang berhasil (harga naik >= 10%)."
                ], className="text-muted")
            ], width=6)
        ]),
        html.Small([
            html.I(className="fas fa-lightbulb text-warning me-1"),
            "Tip: Perhatikan broker dengan Win Rate tinggi (>50%) dan Lead Time pendek (1-3 hari). ",
            "Jika broker tersebut mulai akumulasi, kemungkinan besar harga akan naik dalam beberapa hari."
        ], className="text-info d-block mt-2")
    ], className="mt-3")

    return html.Div([
        html.Small(f"Periode Analisis: {lookback_days} hari terakhir", className="text-muted d-block mb-2"),
        broker_legend,
        table,
        legend
    ])


def create_price_position_detail(price_pos):
    """Create price position detail view"""
    details = price_pos.get('details', {})

    rows = []
    for key, val in details.items():
        label = key.replace('_', ' ').title()
        value = val.get('value', 0)
        bullish = val.get('bullish')
        score = val.get('score', 0)

        bullish_icon = "V" if bullish else ("X" if bullish is False else "-")
        bullish_color = "success" if bullish else ("danger" if bullish is False else "secondary")

        rows.append(html.Tr([
            html.Td(label),
            html.Td(f"{value:.2f}%" if 'pct' in key or key != 'breakout' else f"{value:.2f}"),
            html.Td(html.Span(bullish_icon, className=f"text-{bullish_color} fw-bold")),
            html.Td(f"{score:.0f}")
        ]))

    return html.Table([
        html.Thead(html.Tr([
            html.Th("Metric"),
            html.Th("Value"),
            html.Th("Bullish"),
            html.Th("Score")
        ])),
        html.Tbody(rows)
    ], className="table table-sm table-dark")


def create_accumulation_criteria_table(criteria):
    """Create accumulation phase criteria checklist"""
    if not criteria:
        return html.Div("No criteria data")

    items = []
    for key, val in criteria.items():
        label = key.replace('_', ' ').title()
        met = val.get('met', False)
        score = val.get('score', 0)

        # Get additional info based on criteria type
        extra_info = ""
        if key == 'sideways':
            extra_info = f"Range: {val.get('range_pct', 0):.1f}%"
        elif key == 'volume_increasing':
            extra_info = f"Change: {val.get('change_pct', 0):+.1f}%"
        elif key == 'foreign_positive':
            extra_info = f"10D Total: {val.get('total_10d', 0):.2f}B"
        elif key == 'sensitive_brokers_active':
            extra_info = f"{val.get('count', 0)} brokers active"

        items.append(
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Span(
                                "V" if met else "X",
                                className=f"h4 text-{'success' if met else 'danger'} me-2"
                            ),
                            html.Span(label, className="fw-bold")
                        ]),
                        html.P(extra_info, className="text-muted small mb-1"),
                        html.Small(f"Score: {score:.0f}")
                    ], className="py-2")
                ], color="dark", outline=True)
            ], width=True)
        )

    return dbc.Row(items)


# ============================================================
# PAGE: BANDARMOLOGY (Legacy - kept for reference)
# ============================================================

def create_bandarmology_page(stock_code='CDIA'):
    """Create Bandarmology analysis page"""
    bandar = get_bandarmology_summary(stock_code)

    if not bandar:
        return html.Div([
            dbc.Alert(f"Tidak ada data untuk {stock_code}", color="warning"),
            html.P("Silakan upload data terlebih dahulu di menu Upload Data")
        ])

    lookback = bandar.get('lookback_days', 10)

    return html.Div([
        html.H4(f"Bandarmology Analysis - {stock_code}", className="mb-4"),

        # Overall Score Card
        dbc.Card([
            dbc.CardHeader(html.H5("Bandar Score (Overall)", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.H1(
                                f"{bandar['bandar_score']:.0f}",
                                className=f"display-3 text-{bandar['signal_color']}"
                            ),
                            html.P("/100", className="text-muted")
                        ], className="text-center")
                    ], width=3),
                    dbc.Col([
                        html.H4([
                            dbc.Badge(
                                bandar['overall_signal'].replace('_', ' '),
                                color=bandar['signal_color'],
                                className="fs-4"
                            )
                        ]),
                        html.P(f"Berdasarkan analisis {lookback} hari terakhir", className="text-muted"),
                        html.Hr(),
                        html.Small([
                            html.Strong("Komponen Score:"),
                            html.Ul([
                                html.Li(f"Smart Money vs Distribution Balance"),
                                html.Li(f"Foreign Flow Index"),
                                html.Li(f"Price Pressure (Buying vs Selling days)"),
                                html.Li(f"Active Accumulators Count"),
                            ], className="mb-0")
                        ], className="text-muted")
                    ], width=9),
                ])
            ])
        ], className="mb-4"),

        # Indicator Cards Row
        dbc.Row([
            # Smart Money Indicator
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6("Smart Money Indicator", className="mb-0 d-inline"),
                        dbc.Badge(
                            bandar['smart_money']['latest_signal'],
                            color="success" if 'BUY' in bandar['smart_money']['latest_signal'] else "secondary",
                            className="ms-2"
                        )
                    ]),
                    dbc.CardBody([
                        html.H3(f"{bandar['smart_money']['latest_score']:.0f}", className="text-info"),
                        html.P(f"Avg {lookback}d: {bandar['smart_money']['avg_score']:.0f}", className="text-muted mb-1"),
                        html.Small(f"Strong Buy Days: {bandar['smart_money']['strong_buy_days']}")
                    ])
                ], color="dark", outline=True),
                html.Small([
                    "Volume tinggi + Freq rendah + Close > Avg = Smart Money aktif"
                ], className="text-muted d-block mt-1")
            ], width=3),

            # Distribution Signal
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6("Distribution Signal", className="mb-0 d-inline"),
                        dbc.Badge(
                            bandar['distribution']['latest_signal'],
                            color="danger" if 'DIST' in bandar['distribution']['latest_signal'] else "secondary",
                            className="ms-2"
                        )
                    ]),
                    dbc.CardBody([
                        html.H3(f"{bandar['distribution']['latest_score']:.0f}", className="text-warning"),
                        html.P(f"Avg {lookback}d: {bandar['distribution']['avg_score']:.0f}", className="text-muted mb-1"),
                        html.Small(f"Strong Dist Days: {bandar['distribution']['strong_dist_days']}")
                    ])
                ], color="dark", outline=True),
                html.Small([
                    "Volume tinggi + Freq tinggi + Close < Avg = Distribusi aktif"
                ], className="text-muted d-block mt-1")
            ], width=3),

            # Foreign Accumulation Index
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6("Foreign Accumulation", className="mb-0 d-inline"),
                        dbc.Badge(
                            bandar['foreign_accumulation']['trend'].replace('_', ' ').title(),
                            color="success" if 'accum' in bandar['foreign_accumulation']['trend'] else "danger",
                            className="ms-2"
                        )
                    ]),
                    dbc.CardBody([
                        html.H3(f"{bandar['foreign_accumulation']['fai_billion']:.1f}B",
                               className="text-success" if bandar['foreign_accumulation']['fai'] > 0 else "text-danger"),
                        html.P(f"Total: {bandar['foreign_accumulation']['total_net_foreign_billion']:.1f}B", className="text-muted mb-1"),
                        html.Small(f"Momentum: {bandar['foreign_accumulation']['momentum']}")
                    ])
                ], color="dark", outline=True),
                html.Small([
                    "Rata-rata net foreign per hari (positif = asing akumulasi)"
                ], className="text-muted d-block mt-1")
            ], width=3),

            # Price Pressure
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6("Price Pressure", className="mb-0 d-inline"),
                        dbc.Badge(
                            bandar['price_pressure']['latest_pressure'].title(),
                            color="success" if bandar['price_pressure']['latest_pressure'] == 'buying' else "danger",
                            className="ms-2"
                        )
                    ]),
                    dbc.CardBody([
                        html.H3([
                            html.Span(f"{bandar['price_pressure']['buying_days']}", className="text-success"),
                            " vs ",
                            html.Span(f"{bandar['price_pressure']['selling_days']}", className="text-danger")
                        ]),
                        html.P(f"Buying vs Selling days", className="text-muted mb-1"),
                        html.Small(f"Avg Spread: {bandar['price_pressure']['avg_spread_pct']:.1f}%")
                    ])
                ], color="dark", outline=True),
                html.Small([
                    "Close > Avg = Buying pressure, Close < Avg = Selling"
                ], className="text-muted d-block mt-1")
            ], width=3),
        ], className="mb-4"),

        # Active Accumulators
        dbc.Card([
            dbc.CardHeader([
                html.H5("Broker Consistency Score", className="mb-0 d-inline"),
                dbc.Badge(
                    f"{bandar['broker_consistency']['active_accumulators']} Active Accumulators",
                    color="success",
                    className="ms-2"
                )
            ]),
            dbc.CardBody([
                create_broker_consistency_table(bandar['broker_consistency'].get('full_data', pd.DataFrame())),
                html.Hr(),
                html.Div([
                    html.H6("Penjelasan Kolom:", className="text-info"),
                    html.Ul([
                        html.Li([html.Strong("Current Streak: "), "Hari berturut-turut net buy (hijau = sedang aktif)"]),
                        html.Li([html.Strong("Max Streak: "), "Streak terpanjang sepanjang data"]),
                        html.Li([html.Strong("Consistency Ratio: "), "Persentase hari net buy vs total hari aktif"]),
                        html.Li([html.Strong("Consistency Score: "), "Skor gabungan (0-100) - makin tinggi makin konsisten akumulasi"]),
                        html.Li([html.Strong("Status: "), "accumulating = streak >= 3 hari, active = streak > 0, idle = tidak aktif"]),
                    ], className="small")
                ])
            ])
        ], className="mb-4"),

        # Formula Reference
        dbc.Card([
            dbc.CardHeader(html.H5("Formula & Indikator Bandarmology", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6("Faktor Analisa Harga:", className="text-info"),
                        html.Ul([
                            html.Li([html.Code("Close > Avg"), " = Buying Pressure (smart money accumulating)"]),
                            html.Li([html.Code("Close < Avg"), " = Selling Pressure (distribution)"]),
                            html.Li([html.Code("Spread High-Low"), " = Volatilitas intraday"]),
                        ])
                    ], width=6),
                    dbc.Col([
                        html.H6("Indikator Utama:", className="text-info"),
                        html.Ul([
                            html.Li([html.Strong("1. Net Broker Accumulation: "), html.Code("SUM(buy_val - sell_val)")]),
                            html.Li([html.Strong("2. Foreign Accumulation Index: "), html.Code("SUM(Net Foreign) / n hari")]),
                            html.Li([html.Strong("3. Smart Money Indicator: "), "Vol tinggi + Freq rendah + Close > Avg"]),
                            html.Li([html.Strong("4. Distribution Signal: "), "Vol tinggi + Freq tinggi + Close < Avg"]),
                            html.Li([html.Strong("5. Broker Consistency Score: "), "Streak days + Ratio + Net value"]),
                        ])
                    ], width=6),
                ])
            ])
        ])
    ])


def create_broker_consistency_table(df):
    """Create broker consistency score table"""
    if df.empty:
        return html.Div("No data available")

    # Format for display
    display_df = df.head(20).copy()
    display_df['Net (B)'] = display_df['total_net'].apply(lambda x: f"{x/1e9:.1f}")
    display_df['Streak Val (B)'] = display_df['current_streak_value'].apply(lambda x: f"{x/1e9:.1f}")
    display_df['Ratio'] = display_df['consistency_ratio'].apply(lambda x: f"{x:.0f}%")
    display_df['Score'] = display_df['consistency_score'].apply(lambda x: f"{x:.0f}")

    return dash_table.DataTable(
        data=display_df[[
            'broker_code', 'current_streak', 'max_streak',
            'days_net_buy', 'days_net_sell', 'Ratio',
            'Net (B)', 'Score', 'status'
        ]].to_dict('records'),
        columns=[
            {'name': 'Broker', 'id': 'broker_code'},
            {'name': 'Current Streak', 'id': 'current_streak'},
            {'name': 'Max Streak', 'id': 'max_streak'},
            {'name': 'Buy Days', 'id': 'days_net_buy'},
            {'name': 'Sell Days', 'id': 'days_net_sell'},
            {'name': 'Ratio', 'id': 'Ratio'},
            {'name': 'Total Net', 'id': 'Net (B)'},
            {'name': 'Score', 'id': 'Score'},
            {'name': 'Status', 'id': 'status'},
        ],
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'backgroundColor': '#303030',
            'color': 'white',
            'padding': '8px'
        },
        style_header={
            'backgroundColor': '#404040',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
            {
                'if': {'filter_query': '{status} = "accumulating"'},
                'backgroundColor': '#1a472a',
            },
            {
                'if': {'filter_query': '{current_streak} >= 5'},
                'color': '#28a745',
                'fontWeight': 'bold'
            }
        ],
        sort_action='native',
        page_size=20
    )

# ============================================================
# PAGE: DASHBOARD (Dynamic)
# ============================================================

def create_broker_dominan_card(stock_code: str) -> html.Div:
    """
    Create card showing dominant broker activity by type (Foreign/Local/BUMN)
    Helps user understand WHO is driving the distribution/accumulation
    """
    try:
        broker_df = get_broker_data(stock_code)
        if broker_df.empty:
            return html.Div()

        # Get latest date
        latest_date = broker_df['date'].max()
        today_df = broker_df[broker_df['date'] == latest_date].copy()

        if today_df.empty:
            return html.Div()

        # Add broker type
        today_df['broker_type'] = today_df['broker_code'].apply(get_broker_type)

        # Aggregate by type
        type_summary = today_df.groupby('broker_type').agg({
            'net_val': 'sum',
            'net_lot': 'sum',
            'broker_code': 'count'
        }).reset_index()
        type_summary.columns = ['type', 'net_val', 'net_lot', 'count']

        # Get top sellers by type
        foreign_net = type_summary[type_summary['type'] == 'FOREIGN']['net_val'].sum() if 'FOREIGN' in type_summary['type'].values else 0
        local_net = type_summary[type_summary['type'] == 'LOCAL']['net_val'].sum() if 'LOCAL' in type_summary['type'].values else 0
        bumn_net = type_summary[type_summary['type'] == 'BUMN']['net_val'].sum() if 'BUMN' in type_summary['type'].values else 0

        # Get top 2 brokers for each selling type
        top_foreign_sellers = today_df[(today_df['broker_type'] == 'FOREIGN') & (today_df['net_val'] < 0)].nsmallest(2, 'net_val')['broker_code'].tolist()
        top_local_sellers = today_df[(today_df['broker_type'] == 'LOCAL') & (today_df['net_val'] < 0)].nsmallest(2, 'net_val')['broker_code'].tolist()

        # Build display elements
        elements = []

        # Foreign status
        if foreign_net < -100000000:  # > 100M sell
            foreign_text = f"[R] Asing ({', '.join(top_foreign_sellers) if top_foreign_sellers else 'N/A'}) ^ Net Sell Besar"
            foreign_class = "text-danger"
        elif foreign_net > 100000000:
            foreign_text = "[G] Asing ^ Net Buy"
            foreign_class = "text-success"
        else:
            foreign_text = "[N] Asing ^ Netral"
            foreign_class = "text-muted"

        elements.append(html.Div(foreign_text, className=f"small {foreign_class}"))

        # Local status
        if local_net < -100000000:
            local_text = "[Y] Lokal ^ belum menahan harga"
            local_class = "text-warning"
        elif local_net > 100000000:
            local_text = "[G] Lokal ^ menahan harga"
            local_class = "text-success"
        else:
            local_text = "[N] Lokal ^ Netral"
            local_class = "text-muted"

        elements.append(html.Div(local_text, className=f"small {local_class}"))

        # Conclusion
        if foreign_net < -100000000 and local_net < 0:
            conclusion = "[!] Distribusi bukan ritel, tapi institusi"
            conclusion_class = "text-danger fw-bold"
        elif foreign_net > 100000000:
            conclusion = "[!] Asing sedang akumulasi"
            conclusion_class = "text-success fw-bold"
        else:
            conclusion = "[!] Tidak ada dominasi jelas"
            conclusion_class = "text-muted"

        elements.append(html.Div(conclusion, className=f"small mt-1 {conclusion_class}"))

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-users me-2 text-warning"),
                html.Strong("Broker Dominan Hari Ini", className="text-warning")
            ], className="bg-transparent border-warning py-2"),
            dbc.CardBody(elements, className="py-2")
        ], className="mb-3", style={"border": "1px solid var(--bs-warning)"})

    except Exception as e:
        return html.Div()


def create_sensitive_broker_notice(stock_code: str, overall_signal: str) -> html.Div:
    """
    Create notice explaining when/why sensitive broker signals are being ignored
    Builds trust by showing the system is 'thinking'
    """
    try:
        if overall_signal == 'DISTRIBUSI':
            return html.Div([
                dbc.Alert([
                    html.Div([
                        html.I(className="fas fa-robot me-2"),
                        html.Strong("Catatan Sistem: ", className="text-warning"),
                        html.Span("Sinyal Sensitive Broker ", className="me-1"),
                        html.Strong("diabaikan", className="text-danger"),
                        html.Span(" karena fase pasar masih DISTRIBUTION. "),
                        html.Small("(Efektivitas historis rendah di fase ini)", className="text-muted")
                    ])
                ], color="dark", className="mb-3 py-2", style={"borderLeft": "3px solid var(--bs-warning)"})
            ])
        elif overall_signal == 'AKUMULASI':
            return html.Div([
                dbc.Alert([
                    html.Div([
                        html.I(className="fas fa-robot me-2"),
                        html.Strong("Catatan Sistem: ", className="text-success"),
                        html.Span("Sinyal Sensitive Broker "),
                        html.Strong("aktif dipertimbangkan", className="text-success"),
                        html.Span(" - fase pasar mendukung. "),
                        html.Small("(Efektivitas historis tinggi saat akumulasi)", className="text-muted")
                    ])
                ], color="dark", className="mb-3 py-2", style={"borderLeft": "3px solid var(--bs-success)"})
            ])
        else:
            return html.Div()  # No notice for neutral

    except Exception as e:
        return html.Div()


def create_position_context_card(stock_code: str) -> html.Div:
    """
    Create card showing position/cost basis context from Position submenu
    Links Position analysis to Dashboard
    """
    try:
        # Get position data
        position_df = calculate_broker_current_position(stock_code)
        if position_df.empty:
            position_df = calculate_broker_position_from_daily(stock_code, days=90)

        if position_df.empty:
            return html.Div()

        # Calculate stats
        holders = position_df[position_df['net_lot'] > 0]
        if holders.empty:
            return html.Div()

        in_profit = len(holders[holders['floating_pnl_pct'] > 0])
        in_loss = len(holders[holders['floating_pnl_pct'] < 0])
        total_holders = len(holders)
        avg_pnl = holders['floating_pnl_pct'].mean()

        # Determine context message
        if in_loss > in_profit and avg_pnl < -5:
            context_icon = "[SPEAK]"
            context_text = f"Mayoritas broker ({in_loss}/{total_holders}) berada di posisi rugi"
            context_sub = "^ rebound berpotensi jadi tekanan jual, bukan awal tren"
            context_color = "danger"
        elif in_profit > in_loss and avg_pnl > 5:
            context_icon = "[SPEAK]"
            context_text = f"Mayoritas broker ({in_profit}/{total_holders}) berada di posisi profit"
            context_sub = "^ support kuat dari cost basis, defender aktif"
            context_color = "success"
        else:
            context_icon = "[SPEAK]"
            context_text = f"Posisi broker seimbang ({in_profit} profit, {in_loss} loss)"
            context_sub = "^ belum ada tekanan dominan dari cost basis"
            context_color = "secondary"

        return dbc.Card([
            dbc.CardHeader([
                html.Span(context_icon, className="me-2"),
                html.Strong("Konteks Posisi", className=f"text-{context_color}")
            ], className="bg-transparent py-2", style={"borderBottom": f"1px solid var(--bs-{context_color})"}),
            dbc.CardBody([
                html.Div(context_text, className=f"small text-{context_color}"),
                html.Small(context_sub, className="text-muted")
            ], className="py-2")
        ], className="mb-3", style={"border": f"1px solid var(--bs-{context_color})"})

    except Exception as e:
        return html.Div()


def create_dashboard_education_block() -> html.Div:
    """
    Create education block explaining how Dashboard synthesizes all submenus
    Helps user understand the 'big picture'
    """
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-puzzle-piece me-2 text-info"),
            html.Strong("Bagaimana Dashboard Ini Dibuat?", className="text-info")
        ], className="bg-transparent border-info py-2"),
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.I(className="fas fa-exchange-alt me-2 text-primary"),
                    html.Strong("Broker Movement", className="text-primary"),
                    html.Span(" ^ siapa beli/jual hari ini", className="text-muted ms-1")
                ], className="mb-1 small"),
                html.Div([
                    html.I(className="fas fa-crosshairs me-2 text-info"),
                    html.Strong("Sensitive Broker", className="text-info"),
                    html.Span(" ^ siapa biasanya 'benar lebih dulu'", className="text-muted ms-1")
                ], className="mb-1 small"),
                html.Div([
                    html.I(className="fas fa-chart-pie me-2 text-success"),
                    html.Strong("Position", className="text-success"),
                    html.Span(" ^ di mana tekanan jual / support nyata", className="text-muted ms-1")
                ], className="mb-2 small"),
                html.Hr(className="my-2", style={"opacity": "0.2"}),
                html.Div([
                    html.I(className="fas fa-arrow-right me-1 text-warning"),
                    html.Strong("Dashboard = ringkasan dari 3 analisa ini.", className="text-warning small")
                ])
            ])
        ], className="py-2")
    ], className="mb-3", style={"border": "1px solid var(--bs-info)"})


def create_one_line_insight(stock_code: str) -> html.Div:
    """
    Generate a one-line insight bar for quick market context.
    FINAL COPYWRITING V2: Data-driven, edukatif, membantu pengambilan keputusan.
    """
    try:
        # Get unified analysis for insight
        unified = get_unified_analysis_summary(stock_code)
        accum = unified.get('accumulation', {})
        decision = unified.get('decision', {})

        summary = accum.get('summary', {})
        confidence = accum.get('confidence', {})
        overall_signal = summary.get('overall_signal', 'NETRAL')
        conf_level = confidence.get('level', 'LOW')

        # Generate contextual insight - FINAL COPYWRITING
        if overall_signal == 'DISTRIBUSI' and conf_level in ['HIGH', 'VERY_HIGH']:
            insight = f"[R] {stock_code} sedang dalam tekanan jual. Risiko pelepasan masih dominan. Hindari pembelian baru sementara."
            color = "danger"
            icon = "fas fa-arrow-trend-down"
        elif overall_signal == 'DISTRIBUSI':
            insight = f"[ ] {stock_code} menunjukkan tanda pelepasan saham. Pertimbangkan untuk mengurangi posisi."
            color = "warning"
            icon = "fas fa-exclamation-triangle"
        elif overall_signal == 'AKUMULASI' and conf_level in ['HIGH', 'VERY_HIGH']:
            insight = f"[G] {stock_code} menunjukkan pola akumulasi kuat. Peluang masuk mulai terbuka, fokus pada area support."
            color = "success"
            icon = "fas fa-arrow-trend-up"
        elif overall_signal == 'AKUMULASI':
            insight = f"[Y] {stock_code} mulai menunjukkan tanda akumulasi. Pantau konsistensi dan konfirmasi volume."
            color = "info"
            icon = "fas fa-chart-line"
        else:
            insight = f"[~] {stock_code} dalam fase netral. Pasar belum memberikan konfirmasi arah. Observasi lebih aman daripada spekulasi."
            color = "secondary"
            icon = "fas fa-clock"

    except Exception as e:
        insight = f"[#] Sedang menganalisis {stock_code}. Silakan tunggu sebentar..."
        color = "secondary"
        icon = "fas fa-spinner fa-spin"

    # Tooltip edukatif
    tooltip_text = "Insight ini disusun dari kombinasi struktur harga, perilaku broker, dan volume transaksi."

    return html.Div([
        dbc.Alert([
            html.Div([
                html.I(className=f"{icon} me-2"),
                html.Strong("Insight Hari Ini: ", className="me-1",
                           style={'cursor': 'help', 'borderBottom': '1px dotted'},
                           title=tooltip_text),
                html.Span(insight),
            ], className="d-flex align-items-center flex-wrap")
        ], color=color, className="mb-3 py-2", style={
            "borderLeft": f"4px solid var(--bs-{color})",
            "backgroundColor": f"rgba(var(--bs-{color}-rgb), 0.1)"
        })
    ])


def create_dashboard_page(stock_code='CDIA'):
    # Pre-fetch data for Decision Panel and Why Signal
    try:
        unified_data = get_unified_analysis_summary(stock_code)
        validation_result = get_comprehensive_validation(stock_code, 30)
        # Get overall signal for context-aware components
        accum = unified_data.get('accumulation', {})
        summary = accum.get('summary', {})
        overall_signal = summary.get('overall_signal', 'NETRAL')
    except:
        unified_data = {}
        validation_result = {}
        overall_signal = 'NETRAL'

    return html.Div([
        # === ONE-LINE INSIGHT BAR (NEW) ===
        create_one_line_insight(stock_code),

        # === DECISION PANEL - "APA YANG HARUS DILAKUKAN HARI INI?" ===
        create_decision_panel(stock_code, unified_data),

        # === CONTEXT CARDS ROW - Broker Dominan + Position Context ===
        dbc.Row([
            dbc.Col([
                create_broker_dominan_card(stock_code),
            ], xs=12, md=6),
            dbc.Col([
                create_position_context_card(stock_code),
            ], xs=12, md=6),
        ], className="mb-2"),

        # === SENSITIVE BROKER NOTICE (Context-aware) ===
        create_sensitive_broker_notice(stock_code, overall_signal),

        # Header with submenu navigation
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H4(f"Dashboard - {stock_code}", className="mb-0 d-inline-block me-3"),
                    create_dashboard_submenu_nav('dashboard', stock_code),
                ], className="d-flex align-items-center flex-wrap")
            ], xs=12, md=8),
            dbc.Col([
                dbc.Button("Refresh Data", id="refresh-btn", color="primary", size="sm"),
                html.Span(id="last-refresh", className="ms-3 text-muted small")
            ], xs=12, md=4, className="text-end mt-2 mt-md-0")
        ], className="mb-3"),

        # Summary Cards
        html.Div(id="summary-cards"),

        # Price Chart
        dbc.Card([
            dbc.CardHeader(f"Price & Volume Chart - {stock_code}"),
            dbc.CardBody(id="price-chart-container")
        ], className="mb-4"),

        # Broker Flow
        dbc.Card([
            dbc.CardHeader("Daily Net Flow (All Brokers)"),
            dbc.CardBody(id="flow-chart-container")
        ], className="mb-4"),

        # ============================================================
        # NEW SECTIONS - Replacing Top 10 Acc/Dist duplicates
        # ============================================================

        # Quick Sentiment + Key Metrics (responsive: stack on mobile, side-by-side on desktop)
        dbc.Row([
            dbc.Col([
                html.Div(id="sentiment-container")
            ], xs=12, md=6),
            dbc.Col([
                html.Div(id="metrics-container")
            ], xs=12, md=6),
        ], className="mb-3"),

        # === WHY THIS SIGNAL? - Checklist Validasi ===
        create_why_signal_checklist(stock_code, validation_result),

        # Broker Detail (Indonesian - FINAL COPYWRITING)
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-user-tie me-2"),
                "Detail Aktivitas Broker - ",
                dcc.Dropdown(
                    id='broker-select',
                    options=[],
                    value=None,
                    placeholder="Pilih broker...",
                    style={'width': '150px', 'display': 'inline-block', 'color': 'black'},
                    clearable=False
                )
            ]),
            dbc.CardBody(id="broker-detail-container")
        ], className="mb-4"),

        # === EDUCATION BLOCK - How Dashboard is Built ===
        create_dashboard_education_block(),
    ])

def create_accumulation_table(df, stock_code='CDIA'):
    if df.empty:
        return "No data"

    # Get Avg Buy data
    avg_buy_df = get_broker_avg_buy(stock_code, days=60)
    avg_buy_dict = {}
    if not avg_buy_df.empty:
        avg_buy_dict = dict(zip(avg_buy_df['broker_code'], avg_buy_df['avg_buy_price']))

    df_filtered = df[df['days_net_buy'] >= 3].head(30).copy()
    df_filtered['Net (B)'] = df_filtered['total_net'].apply(lambda x: f"{x/1e9:,.1f}")
    df_filtered['Buy Ratio'] = df_filtered['buy_ratio'].apply(lambda x: f"{x*100:.0f}%")
    df_filtered['Avg Buy'] = df_filtered['broker_code'].apply(
        lambda x: f"Rp {avg_buy_dict.get(x, 0):,.0f}" if avg_buy_dict.get(x, 0) > 0 else "-"
    )

    # Add broker type column
    df_filtered['Type'] = df_filtered['broker_code'].apply(get_broker_type)

    return dash_table.DataTable(
        data=df_filtered[['broker_code', 'Type', 'Net (B)', 'Avg Buy', 'days_active', 'days_net_buy', 'Buy Ratio', 'max_streak', 'current_streak']].to_dict('records'),
        columns=[
            {'name': 'Broker', 'id': 'broker_code'},
            {'name': 'Type', 'id': 'Type'},
            {'name': 'Net (B)', 'id': 'Net (B)'},
            {'name': 'Avg Buy', 'id': 'Avg Buy'},
            {'name': 'Days Active', 'id': 'days_active'},
            {'name': 'Buy Days', 'id': 'days_net_buy'},
            {'name': 'Buy Ratio', 'id': 'Buy Ratio'},
            {'name': 'Max Streak', 'id': 'max_streak'},
            {'name': 'Current', 'id': 'current_streak'},
        ],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '10px'},
        style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
            {'if': {'filter_query': '{current_streak} >= 3', 'column_id': 'current_streak'}, 'backgroundColor': '#28a745', 'fontWeight': 'bold'},
            # Broker type colors
            {'if': {'filter_query': '{Type} = "FOREIGN"', 'column_id': 'Type'}, 'backgroundColor': '#dc3545', 'color': 'white', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{Type} = "BUMN"', 'column_id': 'Type'}, 'backgroundColor': '#28a745', 'color': 'white', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{Type} = "LOCAL"', 'column_id': 'Type'}, 'backgroundColor': '#6f42c1', 'color': 'white', 'fontWeight': 'bold'},
            # Broker code colors based on type
            {'if': {'filter_query': '{Type} = "FOREIGN"', 'column_id': 'broker_code'}, 'color': '#dc3545', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{Type} = "BUMN"', 'column_id': 'broker_code'}, 'color': '#28a745', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{Type} = "LOCAL"', 'column_id': 'broker_code'}, 'color': '#6f42c1', 'fontWeight': 'bold'},
        ],
        sort_action='native',
        page_size=15
    )


def create_recent_activity_chart(broker_df):
    if broker_df.empty:
        return "No data"
    recent_dates = sorted(broker_df['date'].unique())[-7:]
    recent = broker_df[broker_df['date'].isin(recent_dates)]
    top_brokers = recent.groupby('broker_code')['net_value'].sum().abs().nlargest(15).index.tolist()
    recent_top = recent[recent['broker_code'].isin(top_brokers)]

    pivot = recent_top.pivot_table(index='broker_code', columns='date', values='net_value', aggfunc='sum').fillna(0)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values / 1e9,
        x=[d.strftime('%d %b') for d in pivot.columns],
        y=pivot.index,
        colorscale='RdYlGn',
        zmid=0,
        text=[[f"{v/1e9:.1f}B" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont={"size": 10}
    ))
    fig.update_layout(template='plotly_dark', height=400, xaxis_title='Date', yaxis_title='Broker')
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def create_sensitive_broker_daily_chart(stock_code: str, days: int = 30):
    """
    Create a line chart showing daily sensitive broker net lot movement.

    Args:
        stock_code: Stock code
        days: Number of days to show (default 30)

    Returns:
        dcc.Graph with line chart
    """
    from composite_analyzer import calculate_broker_sensitivity_advanced, get_broker_data

    # Get sensitive brokers
    sens_analysis = calculate_broker_sensitivity_advanced(stock_code)
    if 'error' in sens_analysis or not sens_analysis.get('brokers'):
        return html.Div("No sensitive broker data", className="text-muted text-center py-3")

    # Get top 5 sensitive brokers
    sensitive_brokers = [b['broker_code'] for b in sens_analysis.get('brokers', [])[:5]]

    if not sensitive_brokers:
        return html.Div("No sensitive brokers found", className="text-muted text-center py-3")

    # Get broker data
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return html.Div("No broker data", className="text-muted text-center py-3")

    # Convert to float
    for col in ['net_lot', 'net_value']:
        if col in broker_df.columns:
            broker_df[col] = broker_df[col].astype(float)

    # Filter by date range
    latest_date = broker_df['date'].max()
    cutoff_date = latest_date - timedelta(days=days)
    broker_df = broker_df[broker_df['date'] >= cutoff_date]

    # Filter sensitive brokers only
    sens_df = broker_df[broker_df['broker_code'].isin(sensitive_brokers)]

    if sens_df.empty:
        return html.Div("No sensitive broker activity", className="text-muted text-center py-3")

    # Aggregate daily total for all sensitive brokers
    daily_total = sens_df.groupby('date').agg({
        'net_lot': 'sum'
    }).reset_index().sort_values('date')

    # Also get per-broker daily data for individual lines
    broker_daily = sens_df.pivot_table(
        index='date',
        columns='broker_code',
        values='net_lot',
        aggfunc='sum'
    ).fillna(0).reset_index()

    # Calculate cumulative for total
    daily_total['cumulative_lot'] = daily_total['net_lot'].cumsum()

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Color palette for brokers
    colors = ['#00d4ff', '#ff6b6b', '#4ecdc4', '#ffe66d', '#95e1d3']

    # Add individual broker lines (left y-axis)
    for i, broker in enumerate(sensitive_brokers):
        if broker in broker_daily.columns:
            fig.add_trace(
                go.Scatter(
                    x=broker_daily['date'],
                    y=broker_daily[broker],
                    name=broker,
                    mode='lines+markers',
                    line=dict(width=1.5, color=colors[i % len(colors)]),
                    marker=dict(size=4),
                    opacity=0.7
                ),
                secondary_y=False
            )

    # Add cumulative total line (right y-axis) - thicker, more prominent
    fig.add_trace(
        go.Scatter(
            x=daily_total['date'],
            y=daily_total['cumulative_lot'],
            name='Total Kumulatif',
            mode='lines',
            line=dict(width=3, color='#00ff88', dash='solid'),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 136, 0.1)'
        ),
        secondary_y=True
    )

    # Add zero line for reference
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, secondary_y=False)

    # Update layout - increased height by 75% (250 -> 440)
    fig.update_layout(
        template='plotly_dark',
        height=440,
        margin=dict(l=10, r=10, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10)
        ),
        hovermode='x unified'
    )

    # Update axes
    fig.update_yaxes(title_text="Net Lot Harian", secondary_y=False, title_font=dict(size=10))
    fig.update_yaxes(title_text="Kumulatif", secondary_y=True, title_font=dict(size=10))
    fig.update_xaxes(title_text="", tickformat="%d %b")

    # Get latest data for summary
    latest_date = daily_total['date'].max()
    latest_row = daily_total[daily_total['date'] == latest_date].iloc[0]
    latest_net_lot = latest_row['net_lot']
    latest_cumulative = latest_row['cumulative_lot']

    # Get latest broker breakdown
    latest_broker_data = sens_df[sens_df['date'] == latest_date]
    broker_summary = []
    for broker in sensitive_brokers:
        broker_row = latest_broker_data[latest_broker_data['broker_code'] == broker]
        if not broker_row.empty:
            net_lot = float(broker_row['net_lot'].iloc[0])
            net_value = float(broker_row['net_value'].iloc[0]) if 'net_value' in broker_row.columns else 0
            broker_summary.append({
                'broker': broker,
                'net_lot': net_lot,
                'net_value': net_value
            })

    # Get price data for latest date
    from database import execute_query
    price_query = """SELECT close_price FROM stock_daily
                     WHERE stock_code = %s AND date = %s"""
    price_result = execute_query(price_query, (stock_code, latest_date), use_cache=False)
    latest_price = float(price_result[0]['close_price']) if price_result else 0

    # Build summary section
    summary_items = [
        html.Small([
            html.Strong("Data Terakhir: "),
            f"{latest_date.strftime('%d %b %Y')} | ",
            f"Harga: Rp {latest_price:,.0f}"
        ], className="d-block text-muted"),
        html.Small([
            html.Strong("Net Lot Hari Ini: "),
            html.Span(
                f"{latest_net_lot:+,.0f} lot",
                className=f"text-{'success' if latest_net_lot > 0 else 'danger'}"
            ),
            f" | Total Kumulatif: ",
            html.Span(
                f"{latest_cumulative:+,.0f} lot",
                className=f"text-{'success' if latest_cumulative > 0 else 'danger'}"
            )
        ], className="d-block"),
    ]

    # Add per-broker breakdown
    if broker_summary:
        broker_texts = []
        for bs in broker_summary:
            if bs['net_lot'] != 0:
                broker_texts.append(f"{bs['broker']}: {bs['net_lot']:+,.0f}")
        if broker_texts:
            summary_items.append(
                html.Small([
                    html.Strong("Detail Broker: "),
                    " | ".join(broker_texts)
                ], className="d-block text-muted mt-1")
            )

    return html.Div([
        dcc.Graph(figure=fig, config={'displayModeBar': False}),
        html.Div(summary_items, className="mt-2 p-2 border-top")
    ])


# ============================================================
# PAGE: SUMMARY (Dynamic)
# ============================================================

def create_summary_page(stock_code='CDIA'):
    correlation = analyze_broker_price_correlation(stock_code)

    if not correlation:
        return html.Div([
            dbc.Alert(f"Tidak ada data untuk analisis {stock_code}", color="warning"),
            html.P("Silakan upload data terlebih dahulu")
        ])

    uptrend_periods = correlation.get('uptrend_periods', [])
    broker_sensitivity = correlation.get('broker_sensitivity', [])
    current_status = correlation.get('current_status', {})
    pattern_match = correlation.get('pattern_match', {})
    lookback_params = correlation.get('lookback_params', {})
    lookback_days = current_status.get('lookback_days', 10)

    return html.Div([
        html.H4(f"Summary - {stock_code} Broker Sensitivity Analysis", className="mb-4"),

        # Parameter Card
        dbc.Card([
            dbc.CardHeader([
                html.H5("Parameter Analisis (Auto-calculated)", className="mb-0 d-inline"),
                dbc.Badge("AUTO", color="info", className="ms-2")
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([html.Strong("Lookback: "), html.Span(f"{lookback_days} hari", className="text-info")], width=3),
                    dbc.Col([html.Strong("Method: "), html.Span(lookback_params.get('method', 'default'))], width=3),
                    dbc.Col([html.Strong("Uptrends: "), html.Span(f"{lookback_params.get('uptrend_count', 0)}")], width=3),
                    dbc.Col([html.Strong("Patterns: "), html.Span(f"{lookback_params.get('accumulation_patterns', 0)}")], width=3),
                ]),
                html.Small(lookback_params.get('recommendation', ''), className="text-muted d-block mt-2")
            ])
        ], className="mb-4", color="dark", outline=True),

        # Status Cards
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Current Price", className="text-muted"),
                        html.H3(f"Rp {current_status.get('current_price', 0):,.0f}"),
                        html.P([
                            f"{lookback_days}d: ",
                            html.Span(f"{current_status.get('price_period_change', 0):+.1f}%",
                                     className="text-success" if current_status.get('price_period_change', 0) >= 0 else "text-danger")
                        ])
                    ])
                ], color="dark", outline=True)
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Sensitive Brokers Active", className="text-muted"),
                        html.H3(f"{current_status.get('sensitive_brokers_accumulating', 0)} / {current_status.get('total_sensitive_brokers', 0)}"),
                        html.P("accumulating (streak >= 3)")
                    ])
                ], color="dark", outline=True)
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Pattern Match", className="text-muted"),
                        html.H3([dbc.Badge("MATCH" if pattern_match.get('is_matching') else "NO MATCH",
                                          color="success" if pattern_match.get('is_matching') else "secondary")]),
                        html.P(f"Confidence: {pattern_match.get('confidence', 0):.0f}%")
                    ])
                ], color="success" if pattern_match.get('is_matching') else "dark", outline=True)
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Historical Return", className="text-muted"),
                        html.H3(f"+{pattern_match.get('avg_historical_return', 0):.1f}%" if pattern_match.get('is_matching') else "-"),
                        html.P("avg when pattern matches")
                    ])
                ], color="dark", outline=True)
            ], width=3),
        ], className="mb-4"),

        # Broker Sensitivity Table
        dbc.Card([
            dbc.CardHeader(html.H5("Broker Sensitivity Score")),
            dbc.CardBody([
                create_sensitivity_table(broker_sensitivity) if broker_sensitivity else "No data"
            ])
        ], className="mb-4"),

        # Uptrend History
        dbc.Card([
            dbc.CardHeader([html.H5("Historical Uptrends"), dbc.Badge(f"{len(uptrend_periods)} periods", color="info", className="ms-2")]),
            dbc.CardBody([
                create_uptrend_table(uptrend_periods) if uptrend_periods else "No uptrend data"
            ])
        ])
    ])


def create_sensitivity_table(data):
    if not data:
        return "No data"
    df = pd.DataFrame(data)
    df['Participation'] = df['participation_rate'].apply(lambda x: f"{x:.0f}%")
    df['Avg Days'] = df['avg_accumulation_days'].apply(lambda x: f"{x:.1f}")
    df['Avg Return'] = df['avg_uptrend_return'].apply(lambda x: f"+{x:.1f}%")
    df['Score'] = df['sensitivity_score'].apply(lambda x: f"{x:.0f}")

    return dash_table.DataTable(
        data=df[['broker_code', 'uptrend_participated', 'Participation', 'Avg Days', 'Avg Return', 'Score']].head(15).to_dict('records'),
        columns=[
            {'name': 'Broker', 'id': 'broker_code'},
            {'name': 'Uptrends', 'id': 'uptrend_participated'},
            {'name': 'Participation', 'id': 'Participation'},
            {'name': 'Avg Days', 'id': 'Avg Days'},
            {'name': 'Avg Return', 'id': 'Avg Return'},
            {'name': 'Score', 'id': 'Score'},
        ],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '10px'},
        style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
            {'if': {'filter_query': '{Score} >= 40'}, 'backgroundColor': '#28a745'}
        ],
        sort_action='native'
    )


def create_uptrend_table(periods):
    if not periods:
        return "No data"
    data = []
    for i, p in enumerate(periods, 1):
        data.append({
            'No': i,
            'Start': p['start_date'].strftime('%d %b %Y'),
            'End': p['end_date'].strftime('%d %b %Y'),
            'Days': p['duration_days'],
            'Return': f"+{p['change_pct']:.1f}%"
        })
    return dash_table.DataTable(
        data=data,
        columns=[{'name': c, 'id': c} for c in ['No', 'Start', 'End', 'Days', 'Return']],
        style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '8px'},
        style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'}
    )

# ============================================================
# DASHBOARD CHART COMPONENTS
# ============================================================

def create_summary_cards(stock_code='CDIA'):
    """
    Snapshot Market - 4 kotak kecil
    FINAL COPYWRITING: Indonesian labels, clear subtitles.
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty:
        return dbc.Alert(f"Tidak ada data harga untuk {stock_code}", color="warning")

    latest_price = price_df['close_price'].iloc[-1] if not price_df.empty else 0
    prev_price = price_df['close_price'].iloc[-2] if len(price_df) > 1 else latest_price
    price_change = ((latest_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

    phase = find_current_market_phase(price_df)
    phase_name = phase['phase'].upper()
    range_pct = phase['details'].get('range_percent', 0)
    alerts = check_accumulation_alerts(broker_df, stock_code) if not broker_df.empty else []

    latest_date = broker_df['date'].max() if not broker_df.empty else None
    top_acc = get_top_accumulators(broker_df, latest_date, 1) if not broker_df.empty else pd.DataFrame()
    top_acc_name = top_acc['broker_code'].iloc[0] if not top_acc.empty else '-'
    top_acc_val = top_acc['net_value'].iloc[0] / 1e9 if not top_acc.empty else 0

    # Phase subtitle (Indonesian)
    phase_subtitle = {
        'UPTREND': 'Tren besar sedang menguat',
        'DOWNTREND': 'Tren besar masih melemah',
        'SIDEWAYS': 'Belum ada arah yang jelas',
        'ACCUMULATION': 'Fase pengumpulan saham'
    }.get(phase_name, 'Analisis fase pasar')

    # Alert subtitle based on count
    alert_subtitle = "Indikasi awal akumulasi" if len(alerts) > 0 else "Tidak ada sinyal aktif"

    # Responsive card style
    card_header_style = {"fontSize": "11px", "padding": "8px"}
    card_body_style = {"padding": "10px"}
    value_class = "h5 mb-1"
    subtitle_class = "small mb-0 text-muted"

    return dbc.Row([
        # 1. Harga Saat Ini
        dbc.Col(dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-line me-1"),
                "Harga Saat Ini"
            ], style=card_header_style),
            dbc.CardBody([
                html.Div(f"Rp {latest_price:,.0f}", className=value_class),
                html.P(f"({price_change:+.2f}%)", className=f"{subtitle_class} text-{'success' if price_change >= 0 else 'danger'}")
            ], style=card_body_style)
        ], color="dark", outline=True), xs=6, md=3, className="mb-2"),

        # 2. Market Phase (30 Hari)
        dbc.Col(dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-compass me-1"),
                "Market Phase (30 Hari)"
            ], style=card_header_style),
            dbc.CardBody([
                html.Div(phase_name, className=value_class),
                html.P(phase_subtitle, className=subtitle_class, style={"fontSize": "10px"}),
                html.P(f"Range: {range_pct:.1f}%", className=subtitle_class)
            ], style=card_body_style)
        ], color="dark", outline=True), xs=6, md=3, className="mb-2"),

        # 3. Akumulator Terbesar
        dbc.Col(dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-user-tie me-1"),
                "Akumulator Terbesar"
            ], style=card_header_style),
            dbc.CardBody([
                html.Div([
                    html.Span(
                        top_acc_name,
                        className=f"broker-badge broker-badge-{get_broker_type(top_acc_name).lower()}",
                        style={"fontSize": "14px", "padding": "4px 8px"}
                    ) if top_acc_name != '-' else '-'
                ], className="mb-1"),
                html.P(f"Net: Rp {top_acc_val:.1f}B", className=subtitle_class)
            ], style=card_body_style)
        ], color="dark", outline=True), xs=6, md=3, className="mb-2"),

        # 4. Sinyal Aktif
        dbc.Col(dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-bell me-1"),
                "Sinyal Aktif"
            ], style=card_header_style),
            dbc.CardBody([
                html.Div(f"{len(alerts)}", className=value_class),
                html.P(alert_subtitle, className=subtitle_class, style={"fontSize": "10px"})
            ], style=card_body_style)
        ], color="warning" if alerts else "dark", outline=True), xs=6, md=3, className="mb-2"),
    ], className="mb-3")


def create_price_chart(stock_code='CDIA'):
    price_df = get_price_data(stock_code)
    if price_df.empty:
        return html.Div("No price data")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=price_df['date'], open=price_df['open_price'], high=price_df['high_price'],
                                  low=price_df['low_price'], close=price_df['close_price'], name=stock_code), row=1, col=1)
    colors = ['green' if row['close_price'] >= row['open_price'] else 'red' for _, row in price_df.iterrows()]
    fig.add_trace(go.Bar(x=price_df['date'], y=price_df['volume'], marker_color=colors, name='Volume'), row=2, col=1)
    fig.update_layout(template='plotly_dark', height=500, xaxis_rangeslider_visible=False, showlegend=False)
    return dcc.Graph(figure=fig, id='price-chart')


def create_broker_flow_chart(stock_code='CDIA'):
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return html.Div("No broker data")

    daily_flow = broker_df.groupby('date').agg({'net_value': 'sum'}).reset_index()
    colors = ['green' if v >= 0 else 'red' for v in daily_flow['net_value']]
    fig = go.Figure(go.Bar(x=daily_flow['date'], y=daily_flow['net_value'] / 1e9, marker_color=colors))
    fig.update_layout(template='plotly_dark', height=300, yaxis_title='Net Flow (Billion)')
    return dcc.Graph(figure=fig, id='broker-flow-chart')


def create_top_brokers_table(stock_code='CDIA'):
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return html.Div("No data")

    top_acc = get_top_accumulators(broker_df, top_n=10)
    top_dist = get_top_distributors(broker_df, top_n=10)

    # Get Avg Buy data
    avg_buy_df = get_broker_avg_buy(stock_code, days=60)
    avg_buy_dict = {}
    if not avg_buy_df.empty:
        avg_buy_dict = dict(zip(avg_buy_df['broker_code'], avg_buy_df['avg_buy_price']))

    # Add Avg Buy and broker type to accumulators
    top_acc_data = []
    for _, row in top_acc.iterrows():
        broker = row['broker_code']
        avg_buy = avg_buy_dict.get(broker, 0)
        broker_info = get_broker_info(broker)
        top_acc_data.append({
            'broker_code': broker,
            'type': broker_info['type_name'],
            'type_color': broker_info['color'],
            'net_b': f"{row['net_value']/1e9:,.1f}",
            'avg_buy': f"Rp {avg_buy:,.0f}" if avg_buy > 0 else "-"
        })

    # Add Avg Buy and broker type to distributors
    top_dist_data = []
    for _, row in top_dist.iterrows():
        broker = row['broker_code']
        avg_buy = avg_buy_dict.get(broker, 0)
        broker_info = get_broker_info(broker)
        top_dist_data.append({
            'broker_code': broker,
            'type': broker_info['type_name'],
            'type_color': broker_info['color'],
            'net_b': f"{row['net_value']/1e9:,.1f}",
            'avg_buy': f"Rp {avg_buy:,.0f}" if avg_buy > 0 else "-"
        })

    # Style conditional based on broker type
    style_data_conditional = [
        {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
        {'if': {'filter_query': '{type} = Asing'}, 'backgroundColor': 'rgba(220, 53, 69, 0.2)'},
        {'if': {'filter_query': '{type} = BUMN/Pemerintah'}, 'backgroundColor': 'rgba(40, 167, 69, 0.2)'},
        {'if': {'filter_query': '{type} = Lokal'}, 'backgroundColor': 'rgba(111, 66, 193, 0.2)'},
    ]

    # Legend
    broker_legend = html.Div([
        html.Small("Legenda: ", className="text-muted me-2"),
        html.Span([
            html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['FOREIGN'], "fontSize": "10px"}),
            "Asing "
        ], className="me-2", style={"fontSize": "10px"}),
        html.Span([
            html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['BUMN'], "fontSize": "10px"}),
            "BUMN "
        ], className="me-2", style={"fontSize": "10px"}),
        html.Span([
            html.I(className="fas fa-square me-1", style={"color": BROKER_COLORS['LOCAL'], "fontSize": "10px"}),
            "Lokal "
        ], style={"fontSize": "10px"}),
    ], className="mb-2")

    return html.Div([
        broker_legend,
        dbc.Row([
            dbc.Col([
                html.H5("Top 10 Accumulators", className="text-success"),
                dash_table.DataTable(
                    data=top_acc_data,
                    columns=[
                        {'name': 'Broker', 'id': 'broker_code'},
                        {'name': 'Tipe', 'id': 'type'},
                        {'name': 'Net (B)', 'id': 'net_b'},
                        {'name': 'Avg Buy', 'id': 'avg_buy'}
                    ],
                    style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '5px'},
                    style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
                    style_data_conditional=style_data_conditional
                )
            ], width=6),
            dbc.Col([
                html.H5("Top 10 Distributors", className="text-danger"),
                dash_table.DataTable(
                    data=top_dist_data,
                    columns=[
                        {'name': 'Broker', 'id': 'broker_code'},
                        {'name': 'Tipe', 'id': 'type'},
                        {'name': 'Net (B)', 'id': 'net_b'},
                        {'name': 'Avg Buy', 'id': 'avg_buy'}
                    ],
                    style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '5px'},
                    style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
                    style_data_conditional=style_data_conditional
                )
            ], width=6),
        ])
    ])


def create_broker_history_chart(broker_code, stock_code='CDIA'):
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return html.Div("No data")

    broker_data = broker_df[broker_df['broker_code'] == broker_code].sort_values('date')
    if broker_data.empty:
        return html.Div(f"No data for {broker_code}")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['green' if v >= 0 else 'red' for v in broker_data['net_value']]
    fig.add_trace(go.Bar(x=broker_data['date'], y=broker_data['net_value'] / 1e9, marker_color=colors, name='Daily Net'), secondary_y=False)
    broker_data = broker_data.copy()
    broker_data['cumulative'] = broker_data['net_value'].cumsum()
    fig.add_trace(go.Scatter(x=broker_data['date'], y=broker_data['cumulative'] / 1e9, mode='lines', name='Cumulative', line=dict(color='yellow', width=2)), secondary_y=True)
    fig.update_layout(title=f'{broker_code} Net Flow', template='plotly_dark', height=400)
    fig.update_yaxes(title_text="Daily (B)", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative (B)", secondary_y=True)
    return dcc.Graph(figure=fig)


# ============================================================
# PAGE: BROKER POSITION ANALYSIS
# ============================================================

def create_position_action_card(stock_code, position_df, sr_levels, validation_result):
    """
    Create Position Action Card - WAJIB di paling atas
    Menampilkan rekomendasi: EXIT / REDUCE / HOLD / ADD
    """
    try:
        # Get phase analysis data
        summary = validation_result.get('summary', {})
        confidence = validation_result.get('confidence', {})
        overall_signal = summary.get('overall_signal', 'NETRAL')
        pass_rate = confidence.get('pass_rate', 0)
        passed = confidence.get('passed', 0)
        total = confidence.get('total', 6)

        # Calculate floating P/L stats
        holders = position_df[position_df['net_lot'] > 0] if not position_df.empty else pd.DataFrame()
        in_profit = len(holders[holders['floating_pnl_pct'] > 0]) if not holders.empty else 0
        in_loss = len(holders[holders['floating_pnl_pct'] < 0]) if not holders.empty else 0
        avg_pnl = holders['floating_pnl_pct'].mean() if not holders.empty else 0

        # Check support/resistance
        has_support = len(sr_levels.get('supports', [])) > 0
        has_resistance = len(sr_levels.get('resistances', [])) > 0

        # Determine Position Action
        if overall_signal == 'DISTRIBUSI':
            if in_loss > in_profit and avg_pnl < -5:
                action = "EXIT"
                action_icon = "[R]"
                action_color = "danger"
                action_reason = "Mayoritas broker dalam posisi rugi dan fase distribusi masih dominan."
                action_guidance = "Pertimbangkan keluar dari posisi untuk menghindari kerugian lebih lanjut."
            else:
                action = "REDUCE"
                action_icon = "[ ]"
                action_color = "warning"
                action_reason = "Fase distribusi terdeteksi namun sebagian broker masih dalam kondisi wajar."
                action_guidance = "Kurangi eksposur secara bertahap, jangan tambah posisi baru."
        elif overall_signal == 'AKUMULASI':
            if has_support and in_profit > in_loss:
                action = "ADD"
                action_icon = "[G]"
                action_color = "success"
                action_reason = "Fase akumulasi dengan support kuat dari cost basis broker."
                action_guidance = "Pertimbangkan menambah posisi saat pullback ke area support."
            else:
                action = "HOLD"
                action_icon = "[STOP]"
                action_color = "info"
                action_reason = "Fase akumulasi terdeteksi namun belum ada konfirmasi support kuat."
                action_guidance = "Pertahankan posisi, tunggu konfirmasi sebelum menambah."
        else:  # NETRAL
            action = "HOLD"
            action_icon = "[~]"
            action_color = "secondary"
            action_reason = "Belum ada sinyal yang cukup kuat untuk mengambil aksi."
            action_guidance = "Pertahankan posisi saat ini, pantau perkembangan broker flow."

        # Build invalidation checklist
        invalidation_checks = [
            {
                'label': 'Broker akumulator berhenti beli',
                'checked': overall_signal == 'DISTRIBUSI',
                'tooltip': 'Broker yang sebelumnya akumulasi sudah tidak aktif membeli'
            },
            {
                'label': 'Distribusi > 2 hari berturut',
                'checked': overall_signal == 'DISTRIBUSI' and pass_rate >= 60,
                'tooltip': 'Pola distribusi terjadi lebih dari 2 hari berturut-turut'
            },
            {
                'label': 'Breakdown support utama',
                'checked': not has_support and avg_pnl < -10,
                'tooltip': 'Harga menembus support dari cost basis broker'
            },
            {
                'label': 'Volume konfirmasi negatif',
                'checked': in_loss > in_profit * 2,
                'tooltip': 'Volume jual lebih dominan dari volume beli'
            }
        ]

        # Count how many invalidation checks are true
        invalid_count = sum(1 for c in invalidation_checks if c['checked'])
        is_invalid = invalid_count >= 2

        return dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-bullseye me-2 text-warning"),
                    html.Strong("Rekomendasi Posisi Saat Ini", className="text-warning"),
                ], className="d-flex align-items-center")
            ], className="bg-transparent border-warning"),
            dbc.CardBody([
                dbc.Row([
                    # Action Label (LEFT - Big)
                    dbc.Col([
                        html.Div([
                            html.Span(action_icon, style={"fontSize": "48px"}),
                            html.H2(action, className=f"text-{action_color} fw-bold mb-0 mt-2"),
                        ], className="text-center")
                    ], md=3, className="d-flex align-items-center justify-content-center border-end"),

                    # Details (RIGHT)
                    dbc.Col([
                        # Reason
                        html.P(action_reason, className="mb-2", style={"fontSize": "14px"}),

                        # Guidance
                        html.Div([
                            html.I(className="fas fa-lightbulb me-2 text-info"),
                            html.Span(action_guidance, style={"fontSize": "13px"})
                        ], className="mb-3 p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),

                        # Metrics Row
                        dbc.Row([
                            dbc.Col([
                                html.Small("Fase Pasar", className="text-muted d-block"),
                                html.Span(
                                    f"{'DISTRIBUTION' if overall_signal == 'DISTRIBUSI' else 'ACCUMULATION' if overall_signal == 'AKUMULASI' else 'NEUTRAL'}",
                                    className=f"badge bg-{'warning' if overall_signal == 'DISTRIBUSI' else 'info' if overall_signal == 'AKUMULASI' else 'secondary'}"
                                ),
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("Confidence", className="text-muted d-block"),
                                html.Strong(f"{pass_rate:.0f}%", className=f"text-{'success' if pass_rate >= 70 else 'warning' if pass_rate >= 50 else 'danger'}"),
                                html.Small(f" ({passed}/{total})", className="text-muted"),
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("Profit/Loss", className="text-muted d-block"),
                                html.Strong([
                                    html.Span(f"{in_profit}", className="text-success"),
                                    " / ",
                                    html.Span(f"{in_loss}", className="text-danger")
                                ]),
                            ], width=4, className="text-center"),
                        ], className="mb-3"),

                        # Invalidation Checklist
                        html.Div([
                            html.Small([
                                html.I(className="fas fa-ban me-1"),
                                html.Strong("Kapan Sinyal Ini Gugur?")
                            ], className="text-danger d-block mb-2"),
                            html.Div([
                                html.Div([
                                    html.Span("[OK]" if c['checked'] else "[ ]", className="me-2"),
                                    html.Small(c['label'], title=c['tooltip'], style={"cursor": "help"})
                                ], className="mb-1") for c in invalidation_checks
                            ]),
                            # Warning if invalid
                            html.Div([
                                html.I(className="fas fa-exclamation-triangle me-1"),
                                html.Small(f" {invalid_count}/4 kondisi terpenuhi - Sinyal mungkin tidak valid. Hindari tambah posisi.",
                                          className="text-warning")
                            ], className="mt-2") if is_invalid else None
                        ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"})
                    ], md=9)
                ])
            ], className="py-3")
        ], className="mb-4", style={"border": f"2px solid var(--bs-{action_color})", "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"})

    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("Rekomendasi Posisi"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-4")


def create_selling_pressure_interpretation(position_df, current_price):
    """
    Create interpretation box for Selling Pressure Map
    """
    try:
        if position_df.empty:
            return html.Div()

        holders = position_df[position_df['net_lot'] > 0].copy()
        if holders.empty:
            return html.Div()

        # Find the biggest selling pressure zone (where most loss brokers are)
        loss_brokers = holders[holders['floating_pnl_pct'] < 0]
        if loss_brokers.empty:
            return html.Div([
                html.Div([
                    html.I(className="fas fa-check-circle me-2 text-success"),
                    html.Strong("Interpretasi: ", className="text-success"),
                    "Tidak ada tekanan jual signifikan. Mayoritas broker dalam posisi profit."
                ], className="p-3 rounded", style={"backgroundColor": "rgba(40, 167, 69, 0.1)", "border": "1px solid #28a745"})
            ], className="mt-3")

        # Calculate pressure zones
        avg_loss_price = (loss_brokers['weighted_avg_buy'] * loss_brokers['net_lot']).sum() / loss_brokers['net_lot'].sum()
        total_loss_lot = loss_brokers['net_lot'].sum()

        # Price range for resistance
        min_loss_price = loss_brokers['weighted_avg_buy'].min()
        max_loss_price = loss_brokers['weighted_avg_buy'].max()

        return html.Div([
            html.Div([
                html.I(className="fas fa-search me-2 text-warning"),
                html.Strong("Interpretasi Selling Pressure", className="text-warning"),
            ], className="mb-2"),
            html.P([
                f"Tekanan jual terbesar berada di range ",
                html.Strong(f"Rp {min_loss_price:,.0f} - Rp {max_loss_price:,.0f}", className="text-danger"),
                f" dengan total ",
                html.Strong(f"{total_loss_lot:,.0f} lot", className="text-danger"),
                " berpotensi menjadi resistance aktif jika harga rebound."
            ], className="mb-2 small"),
            html.Div([
                html.I(className="fas fa-lightbulb me-1 text-info"),
                html.Small([
                    "Upside cenderung terbatas karena ",
                    html.Strong("rebound berpotensi dimanfaatkan broker untuk keluar", className="text-warning"),
                    ". Semakin banyak broker rugi di atas, semakin berat ceiling-nya."
                ])
            ], className="text-muted")
        ], className="mt-3 p-3 rounded", style={"backgroundColor": "rgba(255, 193, 7, 0.1)", "border": "1px solid #ffc107"})

    except Exception as e:
        return html.Div()


def create_position_page(stock_code='CDIA'):
    """Create broker position analysis page"""

    # Try to get IPO position data first
    position_df = calculate_broker_current_position(stock_code)
    data_source = 'IPO'

    # If no IPO data, fallback to daily broker summary data
    if position_df.empty:
        position_df = calculate_broker_position_from_daily(stock_code, days=90)
        data_source = 'DAILY'

    # If still empty, show no data message
    if position_df.empty:
        return html.Div([
            dbc.Alert([
                html.H5("Data Position Belum Tersedia", className="alert-heading"),
                html.P(f"Tidak ada data posisi broker untuk {stock_code}."),
                html.Hr(),
                html.P([
                    "Untuk menggunakan fitur ini, upload file Excel dengan data broker.",
                ], className="mb-0")
            ], color="warning"),
            dbc.Button("Upload Data", href="/upload", color="primary")
        ])

    # Get period info based on data source
    if data_source == 'IPO':
        ipo_df = get_ipo_position(stock_code)
        period_start = ipo_df['period_start'].iloc[0] if not ipo_df.empty and 'period_start' in ipo_df.columns else None
        period_end = ipo_df['period_end'].iloc[0] if not ipo_df.empty and 'period_end' in ipo_df.columns else None
        period_str = f"IPO: {period_start.strftime('%d %b %Y') if period_start else 'N/A'} - {period_end.strftime('%d %b %Y') if period_end else 'N/A'}"
    else:
        # Daily data - show date range from the data
        first_date = position_df['first_date'].min() if 'first_date' in position_df.columns else None
        last_date = position_df['last_date'].max() if 'last_date' in position_df.columns else None
        period_str = f"Daily Data (90 hari): {first_date.strftime('%d %b %Y') if first_date else 'N/A'} - {last_date.strftime('%d %b %Y') if last_date else 'N/A'}"

    # Current price
    current_price = position_df['current_price'].iloc[0] if 'current_price' in position_df.columns else 0

    # Get support/resistance
    sr_levels = get_support_resistance_from_positions(position_df)

    # Summary stats
    total_holders = len(position_df[position_df['net_lot'] > 0])
    total_net_lot = position_df[position_df['net_lot'] > 0]['net_lot'].sum()
    avg_floating_pnl = position_df[position_df['net_lot'] > 0]['floating_pnl_pct'].mean()

    # Add broker type for coloring
    position_df['broker_type'] = position_df['broker_code'].apply(get_broker_type)

    # Top holders and sellers
    top_holders = position_df[position_df['net_lot'] > 0].nlargest(10, 'net_lot').copy()
    top_sellers = position_df[position_df['net_lot'] < 0].nsmallest(10, 'net_lot').copy()

    # Floating profit vs loss breakdown
    in_profit = position_df[(position_df['net_lot'] > 0) & (position_df['floating_pnl_pct'] > 0)]
    in_loss = position_df[(position_df['net_lot'] > 0) & (position_df['floating_pnl_pct'] < 0)]

    # Get validation result for Position Action card
    validation_result = get_comprehensive_validation(stock_code, 30)

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-chart-pie me-2"),
                f"Position - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_dashboard_submenu_nav('position', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-2"),
        html.P([
            html.Small("Analisis posisi berdasarkan perilaku broker & cost basis ", className="text-muted"),
            html.Small(f"({period_str})", className="text-info")
        ], className="mb-3"),

        # [S] POSITION ACTION CARD - WAJIB DI PALING ATAS
        create_position_action_card(stock_code, position_df, sr_levels, validation_result),

        # Summary Cards with improved labels
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Holders", className="text-muted mb-1"),
                        html.H3(f"{total_holders}", className="mb-0 text-info"),
                        html.Small("Broker yang masih pegang saham", className="text-muted", style={"fontSize": "10px"})
                    ])
                ], color="dark", outline=True)
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Net Position", className="text-muted mb-1"),
                        html.H3(f"{total_net_lot:,.0f} lot", className="mb-0 text-primary"),
                        html.Small("Total saham yang dipegang", className="text-muted", style={"fontSize": "10px"})
                    ])
                ], color="dark", outline=True)
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Avg Floating P/L", className="text-muted mb-1"),
                        html.H3(
                            f"{avg_floating_pnl:+.1f}%",
                            className=f"mb-0 text-{'success' if avg_floating_pnl > 0 else 'danger'}"
                        ),
                        html.Small("Rata-rata untung/rugi broker", className="text-muted", style={"fontSize": "10px"})
                    ])
                ], color="dark", outline=True)
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Profit/Loss Ratio", className="text-muted mb-1"),
                        html.H3([
                            html.Span(f"{len(in_profit)}", className="text-success"),
                            " / ",
                            html.Span(f"{len(in_loss)}", className="text-danger")
                        ], className="mb-0"),
                        html.Small(
                            "Mayoritas masih rugi" if len(in_loss) > len(in_profit) else "Mayoritas sudah profit",
                            className=f"text-{'danger' if len(in_loss) > len(in_profit) else 'success'}",
                            style={"fontSize": "10px"}
                        )
                    ])
                ], color="dark", outline=True)
            ], md=3),
        ], className="mb-4"),

        # Main content - two columns
        dbc.Row([
            # Left column - Position Table
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-users me-2"),
                            "Top 10 Holders (Net Long)"
                        ], className="mb-0")
                    ]),
                    dbc.CardBody([
                        # HTML Table instead of DataTable for better styling control
                        html.Table([
                            html.Thead(html.Tr([
                                html.Th("Broker", style={"width": "80px"}),
                                html.Th("Type", style={"width": "100px"}),
                                html.Th("Net Lot", style={"width": "120px"}),
                                html.Th("Avg Buy", style={"width": "100px"}),
                                html.Th("Float P/L", style={"width": "80px"})
                            ])),
                            html.Tbody([
                                html.Tr([
                                    html.Td(colored_broker(row['broker_code'], with_badge=True)),
                                    html.Td(html.Span(
                                        row['broker_type'],
                                        className=f"broker-{row['broker_type'].lower()}"
                                    )),
                                    html.Td(f"{row['net_lot']:,.0f}"),
                                    html.Td(f"{row['weighted_avg_buy']:,.0f}"),
                                    html.Td(
                                        f"{row['floating_pnl_pct']:+.1f}",
                                        className="text-success" if row['floating_pnl_pct'] > 0 else "text-danger"
                                    )
                                ]) for _, row in top_holders.iterrows()
                            ]) if not top_holders.empty else html.Tbody([])
                        ], className="table table-sm table-dark table-hover", style={"fontSize": "12px"}),
                        # Legend
                        html.Div([
                            html.Span([html.I(className="fas fa-circle me-1", style={"color": "#dc3545", "fontSize": "8px"}), "Asing "], className="me-3", style={"fontSize": "11px"}),
                            html.Span([html.I(className="fas fa-circle me-1", style={"color": "#28a745", "fontSize": "8px"}), "BUMN "], className="me-3", style={"fontSize": "11px"}),
                            html.Span([html.I(className="fas fa-circle me-1", style={"color": "#6f42c1", "fontSize": "8px"}), "Lokal "], style={"fontSize": "11px"}),
                        ], className="mt-2 mb-2"),
                        html.Hr(),
                        html.Small([
                            html.Strong("Cara Baca: "),
                            "Broker dengan Net Lot positif = masih memegang saham. ",
                            "Float P/L menunjukkan profit/loss berdasarkan harga saat ini vs avg buy."
                        ], className="text-muted")
                    ])
                ], className="mb-4"),

                # Phase Analysis (consistent with Accumulation page)
                create_phase_analysis_card(stock_code, current_price),
            ], md=7),

            # Right column - Support/Resistance & Ownership
            dbc.Col([
                # Support/Resistance from Cost Basis
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-layer-group me-2"),
                            "Support/Resistance dari Cost Basis"
                        ], className="mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div([
                            html.H6("Resistance Levels", className="text-danger mb-2"),
                            html.Small("(Broker floating loss - potential sellers)", className="text-muted d-block mb-2"),
                            *([html.Div([
                                html.Span(f"Rp {r['price']:,.0f}", className="fw-bold"),
                                html.Span(" - "),
                                colored_broker(r['broker'], with_badge=True),
                                html.Span(f" ({r['lot']:,.0f} lot)", className="small"),
                                html.Span(f" {r['pnl']:+.1f}%", className="text-danger small ms-2"),
                            ], className="mb-1") for r in sr_levels.get('resistances', [])] if sr_levels.get('resistances') else [
                                html.Small("Tidak ada resistance dari cost basis", className="text-muted")
                            ]),
                        ], className="mb-4"),

                        html.Hr(),

                        html.Div([
                            html.Div([
                                html.I(className="fas fa-arrow-right me-2 text-warning"),
                                html.Strong(f"Current: Rp {current_price:,.0f}", className="text-warning")
                            ], className="mb-3 text-center py-2 rounded metric-box"),
                        ]),

                        html.Hr(),

                        html.Div([
                            html.H6("Support Levels", className="text-success mb-2"),
                            html.Small("(Broker floating profit - akan defend posisi)", className="text-muted d-block mb-2"),
                            *([html.Div([
                                html.Span(f"Rp {s['price']:,.0f}", className="fw-bold"),
                                html.Span(" - "),
                                colored_broker(s['broker'], with_badge=True),
                                html.Span(f" ({s['lot']:,.0f} lot)", className="small"),
                                html.Span(f" {s['pnl']:+.1f}%", className="text-success small ms-2"),
                            ], className="mb-1") for s in sr_levels.get('supports', [])] if sr_levels.get('supports') else [
                                html.Div([
                                    html.I(className="fas fa-exclamation-circle me-1 text-warning"),
                                    html.Small("Belum ada support kuat dari cost basis broker", className="text-warning d-block"),
                                    html.Small("Mayoritas broker masih rugi ^ cenderung menjual saat harga naik (resistance), bukan bertahan.",
                                              className="text-muted", style={"fontSize": "10px"})
                                ])
                            ]),
                        ]),

                        html.Hr(),
                        html.Small([
                            html.Strong("Cara Baca: "),
                            "Support = level harga di mana broker profit (akan defend). ",
                            "Resistance = level di mana broker loss (mungkin jual saat harga naik). ",
                            html.Br(),
                            html.I(className="fas fa-info-circle me-1 text-info"),
                            html.Span("Dalam fase distribusi, rebound sering tertahan karena broker memanfaatkan kenaikan untuk keluar.",
                                     style={"fontSize": "10px"})
                        ], className="text-muted")
                    ])
                ], className="mb-4"),

                # Ownership Distribution
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-chart-pie me-2"),
                            "Ownership Distribution"
                        ], className="mb-0")
                    ]),
                    dbc.CardBody([
                        create_ownership_chart(position_df)
                    ])
                ])
            ], md=5),
        ]),

        # Selling Pressure Map
        dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    "Selling Pressure Map"
                ], className="mb-0 text-warning")
            ]),
            dbc.CardBody([
                create_selling_pressure_chart(position_df, current_price),
                # [!] Interpretasi Selling Pressure - Actionable insight
                create_selling_pressure_interpretation(position_df, current_price),
                html.Hr(),
                # Legend for colors
                html.Div([
                    html.Span([
                        html.I(className="fas fa-square me-1", style={"color": "#00aa00"}),
                        "SUPPORT (Profit) "
                    ], className="me-4"),
                    html.Span([
                        html.I(className="fas fa-square me-1", style={"color": "#ff4444"}),
                        "RESISTANCE (Loss) "
                    ], className="me-4"),
                    html.Span([
                        html.I(className="fas fa-grip-lines-vertical me-1", style={"color": "yellow"}),
                        "Harga Sekarang"
                    ]),
                ], className="mb-3"),
                html.Hr(),
                html.Div([
                    html.H6("Cara Baca Chart:", className="text-info mb-2"),
                    html.Ul([
                        html.Li([
                            html.Strong("Data: "), "SEMUA broker yang masih memegang saham (net lot > 0)"
                        ]),
                        html.Li([
                            html.Strong("X-axis: "), "Harga rata-rata beli broker (dikelompokkan per range Rp 1.000)"
                        ]),
                        html.Li([
                            html.Strong("Y-axis: "), "Total lot yang dipegang oleh broker di range harga tersebut"
                        ]),
                        html.Li([
                            html.Strong("Bar Hijau: "), "Broker yang sudah PROFIT (avg buy < harga sekarang) ^ ",
                            html.Span("SUPPORT", className="text-success fw-bold"),
                            " - mereka tidak akan jual rugi"
                        ]),
                        html.Li([
                            html.Strong("Bar Merah: "), "Broker yang masih LOSS (avg buy > harga sekarang) ^ ",
                            html.Span("RESISTANCE", className="text-danger fw-bold"),
                            " - mereka akan jual saat harga naik ke level avg buy untuk cut loss/BEP"
                        ]),
                    ], className="small mb-2"),
                    html.Div([
                        html.Strong("Insight: ", className="text-warning"),
                        "Semakin banyak bar hijau (profit) ^ saham punya support kuat. ",
                        "Semakin banyak bar merah (loss) ^ ada selling pressure/resistance di atas."
                    ], className="small text-muted")
                ])
            ])
        ], className="mt-4")
    ])


def create_ownership_chart(position_df):
    """Create pie chart for ownership distribution by broker type"""
    if position_df.empty:
        return html.Div("No data", className="text-muted")

    # Filter only holders (positive net lot)
    holders = position_df[position_df['net_lot'] > 0].copy()

    if holders.empty:
        return html.Div("No holders data", className="text-muted")

    # Classify by broker type
    holders['broker_type'] = holders['broker_code'].apply(lambda x: get_broker_type(x))

    # Aggregate by type
    type_totals = holders.groupby('broker_type')['net_lot'].sum().reset_index()
    type_totals.columns = ['type', 'lot']

    # Map names
    type_names = {'FOREIGN': 'Asing', 'BUMN': 'BUMN/Pemerintah', 'LOCAL': 'Lokal'}
    type_colors = {'FOREIGN': '#dc3545', 'BUMN': '#28a745', 'LOCAL': '#6f42c1'}

    type_totals['name'] = type_totals['type'].map(type_names)
    type_totals['color'] = type_totals['type'].map(type_colors)

    fig = go.Figure(data=[go.Pie(
        labels=type_totals['name'],
        values=type_totals['lot'],
        hole=0.4,
        marker_colors=type_totals['color'].tolist(),
        textinfo='label+percent',
        textposition='outside'
    )])

    fig.update_layout(
        template='plotly_dark',
        height=250,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False
    )

    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def create_selling_pressure_chart(position_df, current_price):
    """Create bar chart showing selling pressure at different price levels"""
    if position_df.empty or current_price == 0:
        return html.Div("No data", className="text-muted")

    # Filter holders only
    holders = position_df[position_df['net_lot'] > 0].copy()

    if holders.empty:
        return html.Div("No holders data", className="text-muted")

    # Create price bins
    min_price = holders['weighted_avg_buy'].min()
    max_price = holders['weighted_avg_buy'].max()

    # Create bins
    price_range = max_price - min_price
    if price_range < 1000:
        bin_size = 100
    elif price_range < 5000:
        bin_size = 500
    else:
        bin_size = 1000

    bins = list(range(int(min_price // bin_size * bin_size), int(max_price + bin_size), bin_size))

    # Aggregate lots by price bin
    holders['price_bin'] = pd.cut(holders['weighted_avg_buy'], bins=bins, labels=bins[:-1])
    bin_totals = holders.groupby('price_bin')['net_lot'].sum().reset_index()
    bin_totals['price_bin'] = bin_totals['price_bin'].astype(float)

    # Color based on above/below current price
    colors = ['#ff4444' if p > current_price else '#00aa00' for p in bin_totals['price_bin']]

    fig = go.Figure(data=[go.Bar(
        x=bin_totals['price_bin'],
        y=bin_totals['net_lot'],
        marker_color=colors,
        text=[f"{v:,.0f}" for v in bin_totals['net_lot']],
        textposition='outside'
    )])

    # Add current price line
    fig.add_vline(x=current_price, line_dash="dash", line_color="yellow",
                  annotation_text=f"Current: {current_price:,.0f}",
                  annotation_position="top")

    fig.update_layout(
        template='plotly_dark',
        height=300,
        xaxis_title="Harga Rata-rata Beli Broker (Rupiah)",
        yaxis_title="Total Lot Dipegang di Range Harga Ini",
        margin=dict(l=50, r=20, t=30, b=50)
    )

    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================
# MAIN LAYOUT
# ============================================================

# Render navbar sekali di layout (tidak re-render setiap URL change)
def create_login_required_content():
    """Create content shown when login is required"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="fas fa-lock fa-4x text-warning mb-4"),
                            ], className="text-center"),
                            html.H3("Login Diperlukan", className="text-center mb-3"),
                            html.P([
                                "Anda harus login terlebih dahulu untuk mengakses halaman ini."
                            ], className="text-center text-muted mb-4"),
                            html.Div([
                                dcc.Link(
                                    dbc.Button([
                                        html.I(className="fas fa-sign-in-alt me-2"),
                                        "Login Sekarang"
                                    ], color="primary", size="lg", className="me-3"),
                                    href="/login"
                                ),
                                dcc.Link(
                                    dbc.Button([
                                        html.I(className="fas fa-user-plus me-2"),
                                        "Daftar Akun Baru"
                                    ], color="success", size="lg", outline=True),
                                    href="/signup"
                                ),
                            ], className="text-center mb-4"),
                            html.Hr(),
                            html.P([
                                html.I(className="fas fa-info-circle me-2 text-info"),
                                "Dengan mendaftar, Anda akan mendapat akses trial 7 hari gratis!"
                            ], className="text-center text-muted small mb-0")
                        ], className="py-5")
                    ], className="shadow-lg border-0")
                ], md=6, lg=5, className="mx-auto")
            ], className="min-vh-75 align-items-center", style={"minHeight": "60vh"})
        ], className="py-5")
    ])

def create_admin_required_content():
    """Create content shown when admin access is required"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="fas fa-user-shield fa-4x text-danger mb-4"),
                            ], className="text-center"),
                            html.H3("Akses Terbatas", className="text-center mb-3"),
                            html.P([
                                "Halaman ini hanya dapat diakses oleh Admin."
                            ], className="text-center text-muted mb-4"),
                            html.Div([
                                dcc.Link(
                                    dbc.Button([
                                        html.I(className="fas fa-home me-2"),
                                        "Kembali ke Home"
                                    ], color="primary", size="lg"),
                                    href="/"
                                ),
                            ], className="text-center mb-4"),
                            html.Hr(),
                            html.P([
                                html.I(className="fas fa-info-circle me-2 text-info"),
                                "Hubungi administrator jika Anda memerlukan akses ke halaman ini."
                            ], className="text-center text-muted small mb-0")
                        ], className="py-5")
                    ], className="shadow-lg border-0")
                ], md=6, lg=5, className="mx-auto")
            ], className="min-vh-75 align-items-center", style={"minHeight": "60vh"})
        ], className="py-5")
    ])

def create_trial_expired_content():
    """Create content shown when trial period has expired"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="fas fa-clock fa-4x text-warning mb-4"),
                            ], className="text-center"),
                            html.H3("Masa Trial Berakhir", className="text-center mb-3"),
                            html.P([
                                "Masa trial 7 hari Anda telah berakhir. ",
                                "Upgrade ke akun Subscribe untuk melanjutkan akses ke semua fitur."
                            ], className="text-center text-muted mb-4"),
                            html.Div([
                                dcc.Link(
                                    dbc.Button([
                                        html.I(className="fas fa-home me-2"),
                                        "Kembali ke Home"
                                    ], color="primary", size="lg", className="me-2"),
                                    href="/"
                                ),
                            ], className="text-center mb-4"),
                            html.Hr(),
                            html.P([
                                html.I(className="fas fa-envelope me-2 text-info"),
                                "Hubungi admin untuk upgrade akun: ",
                                html.A("herman.irawan1108@gmail.com", href="mailto:herman.irawan1108@gmail.com")
                            ], className="text-center text-muted small mb-0")
                        ], className="py-5")
                    ], className="shadow-lg border-0")
                ], md=6, lg=5, className="mx-auto")
            ], className="min-vh-75 align-items-center", style={"minHeight": "60vh"})
        ], className="py-5")
    ])

def create_maintenance_banner():
    """Create maintenance mode banner for regular users"""
    return dbc.Alert([
        html.Div([
            html.I(className="fas fa-tools me-2"),
            html.Strong("Maintenance Mode - "),
            "Sedang ada pembaruan data. Anda melihat data sebelum maintenance dimulai. ",
            "Data terbaru akan tersedia setelah maintenance selesai."
        ], className="d-flex align-items-center")
    ], color="warning", className="mb-0 rounded-0 text-center", dismissable=False)

def create_app_layout():
    """Create app layout - dropdown uses persistence for session storage"""
    return html.Div([
        # CSS is now loaded from assets/v10-styles.css automatically

        dcc.Location(id='url', refresh=False),  # No page refresh - use callbacks for navigation
        dcc.Store(id='theme-store', storage_type='local', data='dark'),  # Persist theme
        dcc.Store(id='admin-session', storage_type='session', data={'logged_in': False}),  # Admin session - persists until browser close
        dcc.Store(id='user-session', storage_type='session', data=None),  # User login session
        dcc.Store(id='superadmin-session', storage_type='local', data=None),  # Super admin persistent login

        # Hidden dummy components to prevent callback errors when page components don't exist
        html.Div([
            dbc.Button(id='upload-password-submit', n_clicks=0, style={'display': 'none'}),
            dbc.Input(id='upload-password-input', value='', style={'display': 'none'}),
            html.Div(id='upload-password-gate'),
            html.Div(id='upload-form-container'),
            html.Div(id='upload-password-error'),
        ], style={'display': 'none'}),

        create_navbar(),
        # Wrap page-content with Loading component for better UX
        dcc.Loading(
            id="page-loading",
            type="circle",
            fullscreen=False,
            children=dbc.Container(id='page-content', fluid=True),
            style={"minHeight": "400px"},
            color="#17a2b8"
        )
    ], id='main-container')

app.layout = create_app_layout()

# ============================================================
# CALLBACKS
# ============================================================

# Navbar toggle callback for mobile - auto-close on navigation
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks"),
     Input("url", "pathname")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, pathname, is_open):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # If URL changed (nav link clicked), close the menu
    if trigger_id == 'url':
        return False

    # If hamburger toggler clicked, toggle the menu
    if trigger_id == 'navbar-toggler' and n_clicks:
        return not is_open

    return is_open

# Theme toggle callback - switch between dark/light mode (lightweight version)
app.clientside_callback(
    """
    function(n_clicks, currentTheme) {
        if (!n_clicks) {
            // On initial load, apply saved theme
            if (currentTheme === 'light') {
                document.body.classList.add('light-mode');
                return ['light', 'fas fa-moon'];
            }
            return ['dark', 'fas fa-sun'];
        }

        // Toggle theme
        if (currentTheme === 'dark') {
            document.body.classList.add('light-mode');
            return ['light', 'fas fa-moon'];
        } else {
            document.body.classList.remove('light-mode');
            return ['dark', 'fas fa-sun'];
        }
    }
    """,
    [Output('theme-store', 'data'), Output('theme-icon', 'className')],
    [Input('theme-toggle', 'n_clicks')],
    [State('theme-store', 'data')]
)

# Client-side callback to filter stock cards on landing page
app.clientside_callback(
    """
    function(searchValue) {
        // Get all stock cards
        var cards = document.querySelectorAll('.stock-card');
        if (!cards || cards.length === 0) return window.dash_clientside.no_update;

        // If search is empty, show all cards
        var search = (searchValue || '').toUpperCase().trim();

        cards.forEach(function(card) {
            // Extract stock code from id (format: stock-card-XXXX)
            var cardId = card.id || '';
            var stockCode = cardId.replace('stock-card-', '').replace('-error', '');
            if (!search || (stockCode && stockCode.toUpperCase().includes(search))) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });

        return window.dash_clientside.no_update;
    }
    """,
    Output('landing-stock-search', 'className'),  # Dummy output
    [Input('landing-stock-search', 'value')],
    prevent_initial_call=True
)

@app.callback(
    Output('stock-selector', 'options'),
    [Input('url', 'pathname')],
    [State('user-session', 'data')],
    prevent_initial_call=False
)
def refresh_stock_dropdown(pathname, user_session):
    """Refresh stock dropdown options on every page load.
    During maintenance, regular users see frozen snapshot of stocks."""
    try:
        # Check if user is admin
        is_admin = False
        if user_session and isinstance(user_session, dict):
            member_type = user_session.get('member_type', '')
            is_admin = member_type in ['admin', 'superuser']

        stocks = get_available_stocks_for_user(is_admin)

        # Ensure we always return valid options
        if stocks and len(stocks) > 0:
            return [{'label': s, 'value': s} for s in stocks]
        else:
            # Fallback to default stock
            return [{'label': 'CDIA', 'value': 'CDIA'}]
    except Exception as e:
        print(f"Error in refresh_stock_dropdown: {e}")
        # Return fallback on error
        return [{'label': 'CDIA', 'value': 'CDIA'}]

# Clientside callback for faster dropdown sync with URL
app.clientside_callback(
    """
    function(search, pathname, currentValue, options) {
        // Parse stock from URL
        if (search) {
            const params = new URLSearchParams(search);
            const stockFromUrl = params.get('stock');
            if (stockFromUrl) {
                return stockFromUrl.toUpperCase();
            }
        }

        // No stock in URL - return current value or first option
        if (currentValue) {
            return currentValue;
        }

        // Default to first available stock
        if (options && options.length > 0) {
            return options[0].value;
        }

        return 'PANI';
    }
    """,
    Output('stock-selector', 'value'),
    [Input('url', 'search'), Input('url', 'pathname')],
    [State('stock-selector', 'value'), State('stock-selector', 'options')]
)

@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname'), Input('url', 'search'), Input('stock-selector', 'value')],
    [State('user-session', 'data'), State('superadmin-session', 'data')]
)
def display_page(pathname, search, selected_stock, user_session, superadmin_session):
    """Main routing callback - triggers on URL change OR stock selection change"""
    # Parse query string for token and stock
    token = None
    stock_from_url = None
    if search:
        from urllib.parse import parse_qs
        params = parse_qs(search.lstrip('?'))
        token = params.get('token', [None])[0]
        stock_from_url = params.get('stock', [None])[0]

    # Use stock from URL if provided, otherwise use dropdown selection
    if stock_from_url:
        selected_stock = stock_from_url
    elif not selected_stock:
        stocks = get_available_stocks()
        selected_stock = stocks[0] if stocks else 'PANI'

    # Clear cache for selected stock to ensure fresh data on stock change
    clear_stock_cache(selected_stock)

    # Check if user is logged in and get member type
    is_logged_in = False
    is_admin = False
    is_trial_expired = False
    member_type = None

    if user_session and user_session.get('email'):
        is_logged_in = True
        user_email = user_session.get('email')
        
        # Get fresh membership status from database (not from session)
        # This ensures admin changes to member_end take effect immediately
        db_status = get_user_membership_status(user_email)
        if db_status:
            member_type = db_status['member_type']
        else:
            member_type = user_session.get('member_type', 'trial')
        
        if member_type in ['admin', 'superuser']:
            is_admin = True  # superuser has same access as admin
        elif member_type in ['trial', 'subscribe']:
            # Check if trial/subscribe is expired - use database value for real-time check
            from datetime import datetime
            if db_status and db_status.get('member_end'):
                member_end = db_status['member_end']
                try:
                    if isinstance(member_end, datetime):
                        end_date = member_end
                    else:
                        end_date = datetime.fromisoformat(str(member_end).replace('Z', '+00:00'))
                    # Compare with timezone-naive datetime
                    end_date_naive = end_date.replace(tzinfo=None) if hasattr(end_date, 'tzinfo') and end_date.tzinfo else end_date
                    if datetime.now() > end_date_naive:
                        is_trial_expired = True
                except:
                    pass
    elif superadmin_session and superadmin_session.get('email'):
        is_logged_in = True
        is_admin = True  # Superadmin is always admin
        member_type = 'admin'

    # Public pages (no login required)
    public_pages = ['/', '/login', '/signup', '/verify']

    # Admin-only pages (only admin can access)
    admin_pages = ['/upload']

    # Protected pages require login
    if pathname not in public_pages and not is_logged_in:
        return create_login_required_content()

    # Trial expired - can only access landing page
    if is_trial_expired and pathname != '/' and pathname not in ['/login', '/signup', '/verify']:
        return create_trial_expired_content()

    # Admin pages require admin role
    if pathname in admin_pages and not is_admin:
        return create_admin_required_content()

    # Check maintenance mode - show banner for non-admin users
    show_maintenance_banner = False
    if not is_admin:
        try:
            maintenance_status = get_maintenance_mode()
            show_maintenance_banner = maintenance_status.get('is_on', False)
        except:
            pass

    # Helper to wrap page content with maintenance banner if needed
    def wrap_with_banner(page_content):
        if show_maintenance_banner:
            return html.Div([
                create_maintenance_banner(),
                page_content
            ])
        return page_content

    # Route to appropriate page
    if pathname == '/':
        return wrap_with_banner(create_landing_page(is_admin, is_logged_in, is_trial_expired))
    
    # Pages that require stock selection - check access during maintenance
    stock_pages = ['/dashboard', '/analysis', '/bandarmology', '/summary', '/position',
                   '/discussion', '/movement', '/sensitive', '/profile', '/fundamental',
                   '/support-resistance', '/accumulation']
    
    if pathname in stock_pages:
        # Check if user can access this stock during maintenance
        if not is_stock_accessible_for_user(selected_stock, is_admin):
            # Redirect to landing page with message
            return wrap_with_banner(html.Div([
                dbc.Alert([
                    html.I(className="fas fa-tools me-2"),
                    html.Strong("Maintenance Mode - "),
                    f"Data {selected_stock} tidak tersedia selama maintenance. ",
                    "Silakan pilih emiten lain atau tunggu maintenance selesai."
                ], color="warning", className="text-center"),
                html.Div([
                    dbc.Button([html.I(className="fas fa-home me-2"), "Kembali ke Home"], 
                              href="/", color="primary", size="lg")
                ], className="text-center mt-4")
            ]))
    
    if pathname == '/dashboard':
        return wrap_with_banner(create_dashboard_page(selected_stock))
    elif pathname == '/analysis':
        return wrap_with_banner(create_analysis_page(selected_stock))
    elif pathname == '/news':
        return wrap_with_banner(create_news_page(selected_stock))
    elif pathname == '/bandarmology':
        return wrap_with_banner(create_bandarmology_page(selected_stock))
    elif pathname == '/summary':
        return wrap_with_banner(create_summary_page(selected_stock))
    elif pathname == '/position':
        return wrap_with_banner(create_position_page(selected_stock))
    elif pathname == '/upload':
        return create_upload_page()  # No banner for admin pages
    elif pathname == '/discussion':
        return wrap_with_banner(create_discussion_page(selected_stock))
    elif pathname == '/movement':
        return wrap_with_banner(create_broker_movement_page(selected_stock))
    elif pathname == '/sensitive':
        return wrap_with_banner(create_sensitive_broker_page(selected_stock))
    elif pathname == '/profile':
        return wrap_with_banner(create_company_profile_page(selected_stock))
    elif pathname == '/fundamental':
        return wrap_with_banner(create_fundamental_page(selected_stock))
    elif pathname == '/support-resistance':
        return wrap_with_banner(create_support_resistance_page(selected_stock))
    elif pathname == '/accumulation':
        return wrap_with_banner(create_accumulation_page(selected_stock))
    elif pathname == '/signup':
        return create_signup_page()  # No banner for auth pages
    elif pathname == '/login':
        return create_login_page()  # No banner for auth pages
    elif pathname == '/verify':
        return create_verify_page(token)  # No banner for auth pages
    else:
        return wrap_with_banner(create_landing_page(is_admin, is_logged_in, is_trial_expired))

# Password validation callback for upload page - with session persistence
@app.callback(
    [Output('upload-password-gate', 'style'),
     Output('upload-form-container', 'style'),
     Output('upload-password-error', 'children'),
     Output('admin-session', 'data')],
    [Input('upload-password-submit', 'n_clicks'),
     Input('admin-session', 'data'),
     Input('user-session', 'data')],
    [State('upload-password-input', 'value')],
    prevent_initial_call=True
)
def validate_upload_password(n_clicks, session_data, user_session, password):
    ctx = dash.callback_context
    triggered = ctx.triggered[0]['prop_id'] if ctx.triggered else None

    # Check if user is logged in as admin/superuser - auto unlock upload
    if user_session and user_session.get('member_type') in ['admin', 'superuser']:
        return {'display': 'none'}, {'display': 'block'}, "", {'logged_in': True}

    # Check if already logged in from admin session (password)
    if session_data and session_data.get('logged_in'):
        return {'display': 'none'}, {'display': 'block'}, "", session_data

    # If triggered by password submit button
    if triggered == 'upload-password-submit.n_clicks' and n_clicks:
        if password == UPLOAD_PASSWORD:
            # Password correct - show upload form, hide password gate, save to session
            return {'display': 'none'}, {'display': 'block'}, "", {'logged_in': True}
        else:
            # Password incorrect
            return (
                {'display': 'block'},
                {'display': 'none'},
                dbc.Alert("Password salah! Silakan coba lagi.", color="danger", className="mt-2"),
                {'logged_in': False}
            )

    # Default - show password gate
    return {'display': 'block'}, {'display': 'none'}, "", session_data or {'logged_in': False}


# ============================================================
# MEMBER MANAGEMENT CALLBACKS
# ============================================================

# Update member stats
@app.callback(
    [Output('stat-trial-active', 'children'),
     Output('stat-trial-online', 'children'),
     Output('stat-subscribe-active', 'children'),
     Output('stat-subscribe-online', 'children'),
     Output('stat-expired-total', 'children'),
     Output('stat-total-members', 'children')],
    [Input('member-stats-interval', 'n_intervals'),
     Input('refresh-members-btn', 'n_clicks'),
     Input('add-member-btn', 'n_clicks')],
    prevent_initial_call=False
)
def update_member_stats(n_intervals, refresh_clicks, add_clicks):
    try:
        stats = get_member_stats()
        trial_active = stats.get('active_trial', 0) or 0
        subscribe_active = stats.get('active_subscribe', 0) or 0
        trial_online = stats.get('online_trial', 0) or 0
        subscribe_online = stats.get('online_subscribe', 0) or 0
        expired_trial = stats.get('expired_trial', 0) or 0
        expired_subscribe = stats.get('expired_subscribe', 0) or 0
        total = stats.get('total_members', 0) or 0

        return (
            f"{trial_active} aktif",
            f"[G] {trial_online} online" if trial_online > 0 else "[N] 0 online",
            f"{subscribe_active} aktif",
            f"[G] {subscribe_online} online" if subscribe_online > 0 else "[N] 0 online",
            f"{expired_trial + expired_subscribe}",
            f"{total}"
        )
    except Exception as e:
        return "0", "0 online", "0", "0 online", "0", "0"

# Add new member
@app.callback(
    Output('add-member-feedback', 'children'),
    [Input('add-member-btn', 'n_clicks')],
    [State('new-member-email', 'value'),
     State('new-member-name', 'value'),
     State('new-member-type', 'value')],
    prevent_initial_call=True
)
def add_new_member(n_clicks, email, name, member_type):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not email or not name:
        return dbc.Alert("Email dan nama wajib diisi!", color="warning")

    try:
        result = add_member(email, name, member_type)
        if result:
            days = 7 if member_type == 'trial' else 30
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Member {name} berhasil ditambahkan sebagai {member_type} ({days} hari)"
            ], color="success")
        else:
            return dbc.Alert("Gagal menambahkan member", color="danger")
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")

# Member list display
@app.callback(
    Output('member-list-container', 'children'),
    [Input('member-list-tabs', 'active_tab'),
     Input('refresh-members-btn', 'n_clicks'),
     Input('add-member-btn', 'n_clicks')],
    prevent_initial_call=False
)
def update_member_list(active_tab, refresh_clicks, add_clicks):
    member_type = 'trial' if active_tab == 'subtab-trial' else 'subscribe'

    try:
        members = get_members_by_type(member_type)

        if not members:
            return dbc.Alert(f"Belum ada member {member_type}", color="secondary")

        # Create table
        rows = []
        for m in members:
            days_remaining = m.get('days_remaining')
            is_online = m.get('is_online', False)
            is_active = m.get('is_active', False)
            end_date = m.get('end_date')

            # Status badge
            if not is_active or (days_remaining is not None and days_remaining <= 0):
                status_badge = dbc.Badge("Expired", color="danger")
            elif days_remaining is not None and days_remaining <= 3:
                status_badge = dbc.Badge(f"{int(days_remaining)}d left", color="warning")
            else:
                status_badge = dbc.Badge("Active", color="success")

            # Online indicator
            online_indicator = html.Span("[G]", title="Online") if is_online else html.Span("[N]", title="Offline")

            # Format dates
            start_str = m['start_date'].strftime("%d %b %Y") if m.get('start_date') else "-"
            end_str = end_date.strftime("%d %b %Y") if end_date else "-"

            rows.append(html.Tr([
                html.Td(online_indicator),
                html.Td(m['name']),
                html.Td(m['email']),
                html.Td(start_str),
                html.Td(end_str),
                html.Td([
                    status_badge,
                    html.Span(f" ({int(days_remaining)}d)" if days_remaining and days_remaining > 0 else "", className="small text-muted ms-1")
                ]),
                html.Td([
                    dbc.Button([html.I(className="fas fa-plus")], id={"type": "extend-member", "index": m['id']},
                              color="success", size="sm", className="me-1", title="Perpanjang 30 hari"),
                    dbc.Button([html.I(className="fas fa-ban")], id={"type": "deactivate-member", "index": m['id']},
                              color="danger", size="sm", title="Nonaktifkan"),
                ])
            ]))

        return dbc.Table([
            html.Thead(html.Tr([
                html.Th("", style={"width": "30px"}),
                html.Th("Nama"),
                html.Th("Email"),
                html.Th("Start"),
                html.Th("End"),
                html.Th("Status"),
                html.Th("Action", style={"width": "100px"}),
            ])),
            html.Tbody(rows)
        ], striped=True, hover=True, size="sm", className="mb-0")

    except Exception as e:
        return dbc.Alert(f"Error loading members: {str(e)}", color="danger")

# Member history chart
@app.callback(
    Output('member-history-chart', 'figure'),
    [Input('member-stats-interval', 'n_intervals'),
     Input('refresh-members-btn', 'n_clicks')],
    prevent_initial_call=False
)
def update_member_history_chart(n_intervals, refresh_clicks):
    try:
        import plotly.graph_objects as go
        from datetime import datetime, timedelta

        history = get_member_history_data()

        # Create empty figure if no data
        if not history:
            fig = go.Figure()
            fig.add_annotation(
                text="Belum ada data member",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=20, b=20),
            )
            return fig

        # Process data for chart
        import pandas as pd
        df = pd.DataFrame(history)

        fig = go.Figure()

        # Trial members
        trial_data = df[df['member_type'] == 'trial'] if 'member_type' in df.columns else pd.DataFrame()
        if not trial_data.empty:
            fig.add_trace(go.Bar(
                x=trial_data['join_date'],
                y=trial_data['count'],
                name='Trial',
                marker_color='#ffc107'
            ))

        # Subscribe members
        subscribe_data = df[df['member_type'] == 'subscribe'] if 'member_type' in df.columns else pd.DataFrame()
        if not subscribe_data.empty:
            fig.add_trace(go.Bar(
                x=subscribe_data['join_date'],
                y=subscribe_data['count'],
                name='Subscribe',
                marker_color='#28a745'
            ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=20, b=20),
            barmode='group',
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Tanggal Join",
            yaxis_title="Jumlah Member"
        )
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

# Member online chart (pie chart)
@app.callback(
    Output('member-online-chart', 'figure'),
    [Input('member-stats-interval', 'n_intervals'),
     Input('refresh-members-btn', 'n_clicks')],
    prevent_initial_call=False
)
def update_member_online_chart(n_intervals, refresh_clicks):
    try:
        import plotly.graph_objects as go

        stats = get_member_stats()
        trial_online = stats.get('online_trial', 0) or 0
        subscribe_online = stats.get('online_subscribe', 0) or 0
        trial_offline = max(0, (stats.get('active_trial', 0) or 0) - trial_online)
        subscribe_offline = max(0, (stats.get('active_subscribe', 0) or 0) - subscribe_online)

        fig = go.Figure()

        # Check if all values are 0
        total = trial_online + trial_offline + subscribe_online + subscribe_offline
        if total == 0:
            fig.add_annotation(
                text="Belum ada member aktif",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=20, b=20),
            )
            return fig

        # Create donut chart
        labels = ['Trial Online', 'Trial Offline', 'Subscribe Online', 'Subscribe Offline']
        values = [trial_online, trial_offline, subscribe_online, subscribe_offline]
        colors = ['#ffc107', '#6c757d', '#28a745', '#495057']

        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=colors,
            textinfo='value+label',
            textposition='outside'
        ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False,
            annotations=[dict(text='Online', x=0.5, y=0.5, font_size=14, showarrow=False)]
        )
        return fig
    except Exception as e:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

# Extend member subscription
@app.callback(
    Output('add-member-feedback', 'children', allow_duplicate=True),
    [Input({"type": "extend-member", "index": ALL}, "n_clicks")],
    prevent_initial_call=True
)
def extend_member_subscription(n_clicks_list):
    ctx = dash.callback_context
    if not ctx.triggered or not n_clicks_list or not any(n for n in n_clicks_list if n):
        raise dash.exceptions.PreventUpdate

    # Get the triggered button's member ID
    triggered = ctx.triggered[0]
    prop_id = triggered['prop_id']

    if prop_id == '.' or '.n_clicks' not in prop_id:
        raise dash.exceptions.PreventUpdate

    import json
    try:
        button_info = json.loads(prop_id.replace('.n_clicks', ''))
        member_id = button_info['index']

        result = extend_member(member_id, 30)
        if result:
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Member ID {member_id} diperpanjang 30 hari"
            ], color="success")
        return dbc.Alert("Gagal memperpanjang", color="danger")
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")

# Deactivate member
@app.callback(
    Output('add-member-feedback', 'children', allow_duplicate=True),
    [Input({"type": "deactivate-member", "index": ALL}, "n_clicks")],
    prevent_initial_call=True
)
def deactivate_member_callback(n_clicks_list):
    ctx = dash.callback_context
    if not ctx.triggered or not n_clicks_list or not any(n for n in n_clicks_list if n):
        raise dash.exceptions.PreventUpdate

    triggered = ctx.triggered[0]
    prop_id = triggered['prop_id']

    if prop_id == '.' or '.n_clicks' not in prop_id:
        raise dash.exceptions.PreventUpdate

    import json
    try:
        button_info = json.loads(prop_id.replace('.n_clicks', ''))
        member_id = button_info['index']

        result = deactivate_member(member_id)
        if result:
            return dbc.Alert([
                html.I(className="fas fa-ban me-2"),
                f"Member ID {member_id} dinonaktifkan"
            ], color="warning")
        return dbc.Alert("Gagal menonaktifkan", color="danger")
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")


# ============================================================
# ACCOUNT LIST MANAGEMENT CALLBACKS
# ============================================================

# Load account list
@app.callback(
    Output('account-list-container', 'children'),
    [Input('admin-tabs', 'active_tab'),
     Input('refresh-account-list-btn', 'n_clicks')],
    [State('user-session', 'data')],
    prevent_initial_call=False
)
def load_account_list(active_tab, refresh_clicks, user_session):
    """Load account list table for List Member tab"""
    if active_tab != 'tab-list-member':
        raise dash.exceptions.PreventUpdate

    # Check if current user is superuser (can't see passwords)
    is_superuser = False
    if user_session and user_session.get('member_type') == 'superuser':
        is_superuser = True

    try:
        accounts = get_all_accounts()

        if not accounts:
            return dbc.Alert("Belum ada akun member terdaftar.", color="secondary")

        # Build table
        table_header = html.Thead(html.Tr([
            html.Th("#", style={"width": "40px"}),
            html.Th("Email"),
            html.Th("Username"),
            html.Th("Password", style={"width": "100px"}),
            html.Th("Tipe", style={"width": "100px"}),
            html.Th("Expired", style={"width": "100px"}),
            html.Th("Status", style={"width": "80px"}),
            html.Th("Aksi", style={"width": "200px"}),
        ]))

        table_rows = []
        for idx, acc in enumerate(accounts, 1):
            # Type badge
            type_badge = {
                'admin': dbc.Badge("[i] Admin", color="warning", className="me-1"),
                'superuser': dbc.Badge("[E] Superuser", color="info", className="me-1"),
                'subscribe': dbc.Badge("[*] Subscribe", color="success", className="me-1"),
                'trial': dbc.Badge("[T] Trial", color="secondary", className="me-1"),
            }.get(acc['member_type'], dbc.Badge(acc['member_type'], color="light"))

            # Status badge
            status_badge = dbc.Badge("[OK] Aktif", color="success") if acc['is_verified'] else dbc.Badge("[X] Nonaktif", color="danger")

            # Password display - superuser can't see ANY passwords, admin can only see non-admin passwords
            if is_superuser:
                password_display = "********"  # Superuser can't see any passwords
            elif acc['member_type'] in ['admin', 'superuser']:
                password_display = "********"  # Hide admin/superuser passwords from everyone
            else:
                password_display = acc.get('plain_password') or "********"

            # Expired date with color indication
            from datetime import datetime
            member_end = acc.get('member_end')
            if member_end:
                expired_date = member_end.strftime('%Y-%m-%d')
                is_expired = datetime.now() > member_end
                expired_badge = dbc.Badge(expired_date, color="danger" if is_expired else "success",
                                         className="small")
            else:
                expired_badge = dbc.Badge("-", color="secondary")

            # Action buttons - Admin accounts cannot be edited or deleted
            if acc['member_type'] == 'admin':
                action_cell = html.Td([
                    html.Small("[Protected]", className="text-muted fst-italic")
                ], className="text-center")
            else:
                action_cell = html.Td([
                    # Extend buttons
                    dbc.Button(["+7d"], id={"type": "extend-account-7d", "index": acc['id']},
                              color="success", size="sm", className="me-1", title="Perpanjang 7 hari",
                              style={"fontSize": "10px", "padding": "2px 6px"}),
                    dbc.Button(["+30d"], id={"type": "extend-account-30d", "index": acc['id']},
                              color="warning", size="sm", className="me-1", title="Perpanjang 30 hari",
                              style={"fontSize": "10px", "padding": "2px 6px"}),
                    # Edit & Delete buttons
                    dbc.Button([html.I(className="fas fa-edit")], id={"type": "edit-account-btn", "index": acc['id']},
                              color="primary", size="sm", className="me-1", title="Edit"),
                    dbc.Button([html.I(className="fas fa-trash")], id={"type": "delete-account-btn", "index": acc['id']},
                              color="danger", size="sm", title="Hapus"),
                ])

            table_rows.append(html.Tr([
                html.Td(idx),
                html.Td(acc['email'], style={"fontSize": "12px"}),
                html.Td(acc['username']),
                html.Td(password_display, className="text-muted"),
                html.Td(type_badge),
                html.Td(expired_badge),
                html.Td(status_badge),
                action_cell,
            ]))

        table_body = html.Tbody(table_rows)
        return dbc.Table([table_header, table_body], bordered=True, hover=True, responsive=True,
                        className="table-sm", style={"fontSize": "13px"})

    except Exception as e:
        return dbc.Alert(f"Error loading accounts: {str(e)}", color="danger")


# Open edit modal
@app.callback(
    [Output('edit-account-modal', 'is_open'),
     Output('edit-account-id', 'data'),
     Output('edit-account-email', 'value'),
     Output('edit-account-username', 'value'),
     Output('edit-account-password', 'value'),
     Output('edit-account-type', 'value'),
     Output('edit-account-status', 'value')],
    [Input({"type": "edit-account-btn", "index": ALL}, "n_clicks"),
     Input('cancel-edit-account-btn', 'n_clicks')],
    [State('edit-account-modal', 'is_open')],
    prevent_initial_call=True
)
def open_edit_account_modal(edit_clicks, cancel_click, is_open):
    """Open edit modal and populate with account data"""
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered = ctx.triggered[0]
    prop_id = triggered['prop_id']

    # Cancel button
    if 'cancel-edit-account-btn' in prop_id:
        return False, None, "", "", "", "trial", "true"

    # Edit button clicked
    if 'edit-account-btn' in prop_id and any(c for c in (edit_clicks or []) if c):
        import json
        try:
            button_info = json.loads(prop_id.replace('.n_clicks', ''))
            account_id = button_info['index']

            account = get_account_by_id(account_id)
            if account:
                return (
                    True,  # Open modal
                    account_id,
                    account['email'],
                    account['username'],
                    "",  # Don't show password
                    account['member_type'],
                    "true" if account['is_verified'] else "false"
                )
        except Exception as e:
            print(f"Error opening edit modal: {e}")

    raise dash.exceptions.PreventUpdate


# Save account edit
@app.callback(
    [Output('edit-account-feedback', 'children'),
     Output('account-action-feedback', 'children', allow_duplicate=True)],
    [Input('save-edit-account-btn', 'n_clicks')],
    [State('edit-account-id', 'data'),
     State('edit-account-username', 'value'),
     State('edit-account-password', 'value'),
     State('edit-account-type', 'value'),
     State('edit-account-status', 'value')],
    prevent_initial_call=True
)
def save_account_edit(n_clicks, account_id, username, password, member_type, status):
    """Save edited account data"""
    if not n_clicks or not account_id:
        raise dash.exceptions.PreventUpdate

    try:
        is_verified = status == "true"
        result = update_account(
            account_id,
            username=username if username else None,
            password=password if password else None,
            member_type=member_type,
            is_verified=is_verified
        )

        if result:
            return (
                dbc.Alert("Akun berhasil diupdate!", color="success"),
                dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    "Akun berhasil diupdate. Refresh untuk melihat perubahan."
                ], color="success", dismissable=True)
            )
        return dbc.Alert("Tidak ada perubahan", color="warning"), dash.no_update
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger"), dash.no_update


# Open delete confirmation modal
@app.callback(
    [Output('delete-account-modal', 'is_open'),
     Output('delete-account-id', 'data'),
     Output('delete-confirm-text', 'children')],
    [Input({"type": "delete-account-btn", "index": ALL}, "n_clicks"),
     Input('cancel-delete-account-btn', 'n_clicks')],
    [State('delete-account-modal', 'is_open')],
    prevent_initial_call=True
)
def open_delete_modal(delete_clicks, cancel_click, is_open):
    """Open delete confirmation modal"""
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered = ctx.triggered[0]
    prop_id = triggered['prop_id']

    # Cancel button
    if 'cancel-delete-account-btn' in prop_id:
        return False, None, ""

    # Delete button clicked
    if 'delete-account-btn' in prop_id and any(c for c in (delete_clicks or []) if c):
        import json
        try:
            button_info = json.loads(prop_id.replace('.n_clicks', ''))
            account_id = button_info['index']

            account = get_account_by_id(account_id)
            if account:
                return (
                    True,  # Open modal
                    account_id,
                    f"Apakah Anda yakin ingin menghapus akun '{account['email']}' ({account['username']})?"
                )
        except Exception as e:
            print(f"Error opening delete modal: {e}")

    raise dash.exceptions.PreventUpdate


# Confirm delete account
@app.callback(
    [Output('delete-account-modal', 'is_open', allow_duplicate=True),
     Output('account-action-feedback', 'children')],
    [Input('confirm-delete-account-btn', 'n_clicks')],
    [State('delete-account-id', 'data')],
    prevent_initial_call=True
)
def confirm_delete_account(n_clicks, account_id):
    """Delete account after confirmation"""
    if not n_clicks or not account_id:
        raise dash.exceptions.PreventUpdate

    try:
        result = delete_account(account_id)
        if result:
            return (
                False,  # Close modal
                dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    "Akun berhasil dihapus. Refresh untuk melihat perubahan."
                ], color="success", dismissable=True)
            )
        return False, dbc.Alert("Gagal menghapus akun", color="danger")
    except Exception as e:
        return False, dbc.Alert(f"Error: {str(e)}", color="danger")


# Extend account membership (7 days or 30 days)
@app.callback(
    Output('account-action-feedback', 'children', allow_duplicate=True),
    [Input({"type": "extend-account-7d", "index": ALL}, "n_clicks"),
     Input({"type": "extend-account-30d", "index": ALL}, "n_clicks")],
    prevent_initial_call=True
)
def extend_account_membership(clicks_7d, clicks_30d):
    """Extend account membership by 7 or 30 days"""
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered = ctx.triggered[0]
    prop_id = triggered['prop_id']
    triggered_value = triggered.get('value')

    # Must have a click value (not None or 0)
    if not triggered_value:
        raise dash.exceptions.PreventUpdate

    # Check which button was clicked
    if 'extend-account-7d' in prop_id:
        days = 7
    elif 'extend-account-30d' in prop_id:
        days = 30
    else:
        raise dash.exceptions.PreventUpdate

    import json
    try:
        # Extract button info from prop_id
        button_id_str = prop_id.replace('.n_clicks', '')
        button_info = json.loads(button_id_str)
        account_id = button_info['index']

        # Get account info for feedback
        account = get_account_by_id(account_id)
        if not account:
            return dbc.Alert("Akun tidak ditemukan", color="danger", dismissable=True)

        # Extend membership
        result = extend_member(account_id, days)
        if result:
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Akun '{account['username']}' diperpanjang {days} hari. Refresh untuk melihat perubahan."
            ], color="success", dismissable=True)
        return dbc.Alert("Gagal memperpanjang akun", color="danger", dismissable=True)
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger", dismissable=True)


# ============================================================
# DATA MANAGEMENT CALLBACKS
# ============================================================

# Load stock data summary
@app.callback(
    Output('stock-data-summary-container', 'children'),
    [Input('admin-tabs', 'active_tab'),
     Input('refresh-data-mgmt-btn', 'n_clicks')],
    prevent_initial_call=False
)
def load_stock_data_summary(active_tab, refresh_clicks):
    """Load stock data summary table"""
    if active_tab != 'tab-data-mgmt':
        raise dash.exceptions.PreventUpdate

    try:
        data = get_stock_data_summary()

        if not data:
            return dbc.Alert("Belum ada data emiten.", color="secondary")

        # Build table
        table_header = html.Thead(html.Tr([
            html.Th("#"),
            html.Th("Kode"),
            html.Th("Row Range"),
            html.Th("Brokers", className="text-end"),
            html.Th("Data Dari"),
            html.Th("Data Sampai"),
            html.Th("Aksi"),
        ]))

        table_rows = []
        for idx, row in enumerate(data, 1):
            # Row range: from upload_history or default
            row_range = row.get('row_range') or "A-H, L-X"
            table_rows.append(html.Tr([
                html.Td(idx),
                html.Td(dbc.Badge(row['stock_code'], color="info", className="fs-6")),
                html.Td(dbc.Badge(row_range, color="secondary", className="font-monospace")),
                html.Td(row['brokers'], className="text-end"),
                html.Td(row['first_date'].strftime('%Y-%m-%d') if row['first_date'] else '-'),
                html.Td(row['last_date'].strftime('%Y-%m-%d') if row['last_date'] else '-'),
                html.Td(
                    dbc.Button([html.I(className="fas fa-trash")],
                              id={"type": "delete-stock-btn", "index": row['stock_code']},
                              color="danger", size="sm", title="Hapus Data")
                ),
            ]))

        table_body = html.Tbody(table_rows)
        return dbc.Table([table_header, table_body], bordered=True, hover=True,
                        responsive=True, className="table-sm")

    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")


# Load upload history
@app.callback(
    Output('upload-history-container', 'children'),
    [Input('admin-tabs', 'active_tab'),
     Input('refresh-data-mgmt-btn', 'n_clicks')],
    prevent_initial_call=False
)
def load_upload_history(active_tab, refresh_clicks):
    """Load upload history table"""
    if active_tab != 'tab-data-mgmt':
        raise dash.exceptions.PreventUpdate

    try:
        history = get_upload_history(5)

        if not history:
            return dbc.Alert("Belum ada riwayat upload.", color="secondary")

        # Build table
        table_header = html.Thead(html.Tr([
            html.Th("#"),
            html.Th("Kode"),
            html.Th("Diupload Oleh"),
            html.Th("Row Range"),
            html.Th("Brokers", className="text-end"),
            html.Th("Range Data"),
            html.Th("Waktu Upload"),
        ]))

        table_rows = []
        for idx, row in enumerate(history, 1):
            uploaded_at = row['uploaded_at']
            time_str = uploaded_at.strftime('%Y-%m-%d %H:%M') if uploaded_at else '-'

            date_range = '-'
            if row['date_range_start'] and row['date_range_end']:
                date_range = f"{row['date_range_start'].strftime('%m/%d')} - {row['date_range_end'].strftime('%m/%d')}"

            row_range = row.get('row_range') or "A-H, L-X"
            table_rows.append(html.Tr([
                html.Td(idx),
                html.Td(dbc.Badge(row['stock_code'], color="info")),
                html.Td(row['uploaded_by'] or '-', style={"fontSize": "12px"}),
                html.Td(dbc.Badge(row_range, color="secondary", className="font-monospace"), style={"fontSize": "11px"}),
                html.Td(row['brokers_count'] or '-', className="text-end"),
                html.Td(date_range, style={"fontSize": "11px"}),
                html.Td(time_str, style={"fontSize": "11px"}),
            ]))

        table_body = html.Tbody(table_rows)
        return dbc.Table([table_header, table_body], bordered=True, hover=True,
                        responsive=True, className="table-sm", style={"fontSize": "13px"})

    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")


# Load maintenance mode status
@app.callback(
    Output('maintenance-mode-container', 'children'),
    [Input('admin-tabs', 'active_tab'),
     Input('refresh-data-mgmt-btn', 'n_clicks')],
    prevent_initial_call=False
)
def load_maintenance_mode(active_tab, refresh_clicks):
    """Load maintenance mode status"""
    if active_tab != 'tab-data-mgmt':
        raise dash.exceptions.PreventUpdate

    try:
        status = get_maintenance_mode()
        is_on = status['is_on']
        updated_at = status['updated_at']
        updated_by = status['updated_by']

        # Status display
        if is_on:
            status_badge = dbc.Badge([html.I(className="fas fa-tools me-1"), "MAINTENANCE AKTIF"], color="warning", className="fs-6 py-2 px-3")
            action_btn = dbc.Button([html.I(className="fas fa-play me-2"), "Selesai Maintenance"], id="toggle-maintenance-btn", color="success", size="lg", className="ms-3")
            info_text = f"Diaktifkan oleh {updated_by or 'System'}" if updated_by else "Maintenance sedang berlangsung"
            if updated_at:
                info_text += f" pada {updated_at.strftime('%Y-%m-%d %H:%M')}"
        else:
            status_badge = dbc.Badge([html.I(className="fas fa-check-circle me-1"), "NORMAL"], color="success", className="fs-6 py-2 px-3")
            action_btn = dbc.Button([html.I(className="fas fa-pause me-2"), "Mulai Maintenance"], id="toggle-maintenance-btn", color="warning", size="lg", className="ms-3")
            info_text = "Sistem berjalan normal. User melihat data real-time."

        return html.Div([
            html.Div([
                status_badge,
                action_btn,
            ], className="d-flex align-items-center mb-3"),
            html.P(info_text, className="text-muted small mb-0"),
            dcc.Store(id="maintenance-current-state", data=is_on),
        ])

    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")


# Open delete stock modal
@app.callback(
    [Output('delete-stock-modal', 'is_open'),
     Output('delete-stock-code', 'data'),
     Output('delete-stock-confirm-text', 'children')],
    [Input({"type": "delete-stock-btn", "index": ALL}, "n_clicks"),
     Input('cancel-delete-stock-btn', 'n_clicks')],
    [State('delete-stock-modal', 'is_open')],
    prevent_initial_call=True
)
def open_delete_stock_modal(delete_clicks, cancel_click, is_open):
    """Open delete stock modal"""
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered = ctx.triggered[0]
    triggered_id = triggered['prop_id']
    triggered_value = triggered['value']

    # Important: Check that this is an actual click, not just button creation
    if triggered_value is None:
        raise dash.exceptions.PreventUpdate

    if 'cancel-delete-stock-btn' in triggered_id:
        return False, None, ""

    if 'delete-stock-btn' in triggered_id:
        # Also verify there was an actual click (value > 0)
        if not triggered_value or triggered_value < 1:
            raise dash.exceptions.PreventUpdate
        import json
        btn_id = json.loads(triggered_id.split('.')[0])
        stock_code = btn_id['index']
        return True, stock_code, f"Apakah Anda yakin ingin menghapus semua data untuk {stock_code}?"

    raise dash.exceptions.PreventUpdate


# Confirm delete stock
@app.callback(
    [Output('delete-stock-modal', 'is_open', allow_duplicate=True),
     Output('data-mgmt-feedback', 'children')],
    [Input('confirm-delete-stock-btn', 'n_clicks')],
    [State('delete-stock-code', 'data')],
    prevent_initial_call=True
)
def confirm_delete_stock(n_clicks, stock_code):
    """Delete stock data after confirmation"""
    if not n_clicks or not stock_code:
        raise dash.exceptions.PreventUpdate

    try:
        result = delete_stock_data(stock_code)
        if result:
            return (
                False,
                dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"Data {stock_code} berhasil dihapus. Refresh untuk melihat perubahan."
                ], color="success", dismissable=True)
            )
        return False, dbc.Alert(f"Gagal menghapus data {stock_code}", color="danger")
    except Exception as e:
        return False, dbc.Alert(f"Error: {str(e)}", color="danger")


# Handle maintenance mode toggle
@app.callback(
    Output('data-mgmt-feedback', 'children', allow_duplicate=True),
    [Input('toggle-maintenance-btn', 'n_clicks')],
    [State('maintenance-current-state', 'data'),
     State('user-session', 'data')],
    prevent_initial_call=True
)
def handle_maintenance_toggle(n_clicks, current_state, user_session):
    """Handle maintenance mode toggle"""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    try:
        # Get current user for audit
        updated_by = None
        if user_session:
            updated_by = user_session.get('username') or user_session.get('email')

        # Toggle the state
        new_state = not current_state
        result = set_maintenance_mode(new_state, updated_by)

        if result:
            if new_state:
                return dbc.Alert([
                    html.I(className="fas fa-tools me-2"),
                    "Maintenance Mode AKTIF. User biasa sekarang melihat data sebelum maintenance. Refresh untuk update tampilan."
                ], color="warning", dismissable=True)
            else:
                return dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    "Maintenance Mode SELESAI. User sekarang melihat data real-time. Refresh untuk update tampilan."
                ], color="success", dismissable=True)

        return dbc.Alert("Gagal mengubah status maintenance", color="danger")
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")


# ============================================================
# USER AUTHENTICATION CALLBACKS
# ============================================================

# Sign Up callback
@app.callback(
    Output('signup-feedback', 'children'),
    [Input('signup-submit', 'n_clicks')],
    [State('signup-email', 'value'),
     State('signup-username', 'value'),
     State('signup-password', 'value'),
     State('signup-confirm', 'value')],
    prevent_initial_call=True
)
def handle_signup(n_clicks, email, username, password, confirm):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    # Validate inputs
    if not all([email, username, password, confirm]):
        return dbc.Alert("Semua field harus diisi!", color="warning")

    if password != confirm:
        return dbc.Alert("Password dan konfirmasi tidak cocok!", color="danger")

    # Create user
    result = create_user(email, username, password)

    if result['success']:
        # Send verification email
        email_result = send_verification_email(result['email'], result['token'], username)

        if email_result['sent']:
            # Email actually sent via SMTP
            return dbc.Alert([
                html.Div([
                    html.I(className="fas fa-envelope fa-3x text-success mb-3"),
                ], className="text-center"),
                html.H5("Pendaftaran Berhasil!", className="text-center"),
                html.P([
                    "Email verifikasi telah dikirim ke ",
                    html.Strong(email),
                    ". Silakan cek inbox (dan folder spam) untuk memverifikasi akun Anda."
                ], className="text-center mb-0"),
                html.P("Link verifikasi berlaku selama 24 jam.", className="text-center text-muted small mt-2")
            ], color="success")
        else:
            # Email not configured - show verification link directly
            return dbc.Alert([
                html.Div([
                    html.I(className="fas fa-check-circle fa-3x text-success mb-3"),
                ], className="text-center"),
                html.H5("Pendaftaran Berhasil!", className="text-center"),
                html.P([
                    "Akun Anda berhasil dibuat. Silakan klik tombol di bawah untuk memverifikasi email:"
                ], className="text-center mb-2"),
                html.Div([
                    html.A(
                        dbc.Button([
                            html.I(className="fas fa-check-circle me-2"),
                            "Verifikasi Email Sekarang"
                        ], color="success", size="lg"),
                        href=email_result['url'],
                        target="_blank"
                    )
                ], className="text-center mb-3"),
                html.P([
                    "Atau copy link berikut:"
                ], className="text-center text-muted small mb-1"),
                html.Div([
                    html.Code(email_result['url'], style={"fontSize": "10px", "wordBreak": "break-all"})
                ], className="text-center p-2 bg-light rounded", style={"maxWidth": "100%", "overflow": "auto"})
            ], color="success")
    else:
        return dbc.Alert([
            html.I(className="fas fa-exclamation-circle me-2"),
            result['error']
        ], color="danger")


# Login callback - with super admin persistent login and resend verification
@app.callback(
    [Output('login-feedback', 'children'),
     Output('user-session', 'data'),
     Output('superadmin-session', 'data'),
     Output('url', 'pathname', allow_duplicate=True)],
    [Input('login-submit', 'n_clicks'),
     Input('resend-verification-btn', 'n_clicks')],
    [State('login-email', 'value'),
     State('login-password', 'value'),
     State('user-session', 'data'),
     State('superadmin-session', 'data')],
    prevent_initial_call=True
)
def handle_login_and_resend(login_clicks, resend_clicks, email, password, current_session, superadmin_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Handle resend verification
    if triggered_id == 'resend-verification-btn' and resend_clicks:
        if not email:
            return dbc.Alert("Masukkan email Anda terlebih dahulu!", color="warning"), dash.no_update, dash.no_update, dash.no_update

        result = resend_verification(email)

        if result['success']:
            return dbc.Alert([
                html.I(className="fas fa-envelope me-2"),
                result['message']
            ], color="success"), dash.no_update, dash.no_update, dash.no_update
        else:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                result['error']
            ], color="danger"), dash.no_update, dash.no_update, dash.no_update

    # Handle login
    if triggered_id == 'login-submit' and login_clicks:
        if not email or not password:
            return dbc.Alert("Email dan password harus diisi!", color="warning"), dash.no_update, dash.no_update, dash.no_update

        result = login_user(email, password)

        if result['success']:
            user = result['user']
            # Convert member_end to string for JSON serialization
            member_end_str = None
            if user.get('member_end'):
                member_end_str = user['member_end'].isoformat() if hasattr(user['member_end'], 'isoformat') else str(user['member_end'])

            session_data = {
                'user_id': user['id'],
                'email': user['email'],
                'username': user['username'],
                'member_type': user['member_type'],
                'member_end': member_end_str,
                'logged_in': True
            }

            # If admin, save to persistent local storage
            if user['member_type'] == 'admin':
                return (
                    dbc.Alert([
                        html.I(className="fas fa-crown me-2 text-warning"),
                        f"Login berhasil! Mengalihkan ke halaman utama..."
                    ], color="success"),
                    session_data,
                    session_data,  # Save to persistent local storage
                    '/'  # Redirect to landing page
                )
            else:
                return (
                    dbc.Alert([
                        html.I(className="fas fa-check-circle me-2"),
                        f"Login berhasil! Mengalihkan ke halaman utama..."
                    ], color="success"),
                    session_data,
                    dash.no_update,  # Don't save to persistent storage for regular users
                    '/'  # Redirect to landing page
                )
        else:
            return (
                dbc.Alert([
                    html.I(className="fas fa-exclamation-circle me-2"),
                    result['error']
                ], color="danger"),
                dash.no_update,
                dash.no_update,
                dash.no_update
            )

    raise dash.exceptions.PreventUpdate


# Auto-login callback for super admin (checks local storage on page load)
@app.callback(
    Output('user-session', 'data', allow_duplicate=True),
    [Input('url', 'pathname')],
    [State('superadmin-session', 'data')],
    prevent_initial_call=True
)
def auto_login_superadmin(pathname, superadmin_data):
    """Auto-login super admin from persistent local storage"""
    if superadmin_data and isinstance(superadmin_data, dict) and superadmin_data.get('logged_in') and superadmin_data.get('member_type') == 'admin':
        return superadmin_data
    raise dash.exceptions.PreventUpdate


# Show/hide login/logout buttons based on user session
@app.callback(
    [Output('auth-buttons-desktop', 'style'),
     Output('logout-section-desktop', 'style'),
     Output('user-display-desktop', 'children'),
     Output('auth-buttons-mobile', 'style'),
     Output('logout-section-mobile', 'style'),
     Output('user-display-mobile', 'children')],
    [Input('user-session', 'data')],
    prevent_initial_call=False
)
def toggle_auth_buttons(user_session):
    """Toggle visibility of login/logout buttons based on session"""
    if user_session and isinstance(user_session, dict) and user_session.get('logged_in'):
        username = user_session.get('username', 'User')
        member_type = user_session.get('member_type', '')
        badge = "[i] " if member_type == 'admin' else ""
        display_text = f"{badge}{username}"
        # Hide login buttons, show logout
        return (
            {"display": "none"},  # Hide auth-buttons-desktop
            {"display": "flex"},  # Show logout-section-desktop
            display_text,
            {"display": "none"},  # Hide auth-buttons-mobile
            {"display": "block"},  # Show logout-section-mobile
            display_text
        )
    else:
        # Show login buttons, hide logout
        return (
            {"display": "flex"},  # Show auth-buttons-desktop
            {"display": "none"},  # Hide logout-section-desktop
            "",
            {"display": "block"},  # Show auth-buttons-mobile
            {"display": "none"},  # Hide logout-section-mobile
            ""
        )


# Logout callback
@app.callback(
    [Output('user-session', 'data', allow_duplicate=True),
     Output('superadmin-session', 'data', allow_duplicate=True),
     Output('url', 'pathname', allow_duplicate=True)],
    [Input('logout-btn-desktop', 'n_clicks'),
     Input('logout-btn-mobile', 'n_clicks')],
    prevent_initial_call=True
)
def handle_logout(desktop_clicks, mobile_clicks):
    """Handle logout - clear all sessions"""
    if not desktop_clicks and not mobile_clicks:
        raise dash.exceptions.PreventUpdate

    # Clear sessions and redirect to home
    return None, None, "/"


@app.callback(Output('broker-select', 'options'), [Input('url', 'pathname'), Input('stock-selector', 'value')])
def update_broker_options(pathname, stock_code):
    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'
    broker_df = get_broker_data(stock_code)
    if broker_df.empty:
        return []
    top_brokers = broker_df.groupby('broker_code')['net_value'].sum().abs().nlargest(20).index.tolist()
    return [{'label': b, 'value': b} for b in top_brokers]

@app.callback(
    [Output("summary-cards", "children"), Output("price-chart-container", "children"),
     Output("flow-chart-container", "children"),
     Output("sentiment-container", "children"), Output("metrics-container", "children"),
     Output("last-refresh", "children")],
    [Input("refresh-btn", "n_clicks"), Input('stock-selector', 'value')],
    prevent_initial_call=False
)
def refresh_dashboard(n_clicks, stock_code):
    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'
    return (
        create_summary_cards(stock_code),
        create_price_chart(stock_code),
        create_broker_flow_chart(stock_code),
        # New sections replacing Top Brokers Summary
        create_quick_sentiment_summary(stock_code),
        create_key_metrics_compact(stock_code),
        f"Refresh: {datetime.now().strftime('%H:%M:%S')}"
    )

@app.callback(Output("broker-detail-container", "children"), [Input("broker-select", "value"), Input('stock-selector', 'value')])
def update_broker_detail(broker_code, stock_code):
    if not broker_code:
        return html.Div("Pilih broker untuk melihat pola beli/jual", className="text-muted")
    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'
    return create_broker_history_chart(broker_code, stock_code)

# Movement page refresh callback
@app.callback(
    [Output("movement-alert-container", "children"),
     Output("movement-watchlist-container", "children"),
     Output("movement-streak-container", "children"),
     Output("movement-last-refresh", "children")],
    [Input("movement-refresh-btn", "n_clicks"), Input('stock-selector', 'value')],
    prevent_initial_call=True
)
def refresh_movement_page(n_clicks, stock_code):
    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'
    return (
        create_broker_movement_alert(stock_code),
        create_broker_watchlist(stock_code),
        create_broker_streak_section(stock_code),
        f"Last refresh: {datetime.now().strftime('%H:%M:%S')}"
    )


# Streak chart dropdown callback - update chart when broker selection changes
@app.callback(
    Output("streak-chart-container", "children"),
    [Input("streak-broker-dropdown", "value")],
    [State('stock-selector', 'value')],
    prevent_initial_call=False  # Allow initial call to work properly
)
def update_streak_chart(selected_brokers, stock_code):
    print(f"[CALLBACK] update_streak_chart CALLED! brokers={selected_brokers}, stock={stock_code}", flush=True)

    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'

    if not selected_brokers or len(selected_brokers) == 0:
        return html.Div("Pilih minimal 1 broker untuk melihat grafik", className="text-muted text-center py-3")

    # Pass selected_brokers directly to chart function
    print(f"[CALLBACK] Calling create_broker_streak_chart with {len(selected_brokers)} brokers", flush=True)
    return create_broker_streak_chart(stock_code, list(selected_brokers))

# Sensitive Broker page refresh callback
@app.callback(
    [Output("sensitive-pattern-container", "children"),
     Output("broker-summary-container", "children"),
     Output("activity-1week", "children"),
     Output("activity-2weeks", "children"),
     Output("activity-3weeks", "children"),
     Output("activity-1month", "children"),
     Output("sensitive-last-refresh", "children")],
    [Input("sensitive-refresh-btn", "n_clicks"), Input('stock-selector', 'value')],
    prevent_initial_call=True
)
def refresh_sensitive_page(n_clicks, stock_code):
    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'

    # Get top 5 sensitive brokers
    broker_sens = calculate_broker_sensitivity_advanced(stock_code)
    top_5_codes = []
    if broker_sens and broker_sens.get('brokers'):
        top_5_codes = [b['broker_code'] for b in broker_sens['brokers'][:5]]

    return (
        create_broker_sensitivity_pattern(stock_code),
        create_broker_summary_card(stock_code, top_5_codes),
        create_broker_activity_table(stock_code, top_5_codes, 7),
        create_broker_activity_table(stock_code, top_5_codes, 14),
        create_broker_activity_table(stock_code, top_5_codes, 21),
        create_broker_activity_table(stock_code, top_5_codes, 30),
        f"Last refresh: {datetime.now().strftime('%H:%M:%S')}"
    )

# Upload callbacks
@app.callback(
    [Output('upload-status', 'children'), Output('available-stocks-list', 'children'), Output('import-log', 'children')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'), State('upload-stock-code', 'value')],
    prevent_initial_call=True
)
def handle_upload(contents, filename, stock_code):
    import tempfile
    import traceback

    stocks_list = create_stocks_list()

    if contents is None:
        return html.Div(), stocks_list, html.Div("No imports yet", className="text-muted")

    if not stock_code or len(stock_code) < 2:
        return dbc.Alert("Masukkan kode saham terlebih dahulu (min 2 karakter)", color="danger"), stocks_list, html.Div()

    stock_code = stock_code.upper().strip()

    try:
        print(f"[UPLOAD] Starting upload for {stock_code}, file: {filename}")

        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        print(f"[UPLOAD] Decoded file size: {len(decoded)} bytes")

        # Save to temp file (use system temp directory for cloud compatibility)
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f'upload_{stock_code}_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx')

        print(f"[UPLOAD] Saving to temp path: {temp_path}")

        with open(temp_path, 'wb') as f:
            f.write(decoded)

        print(f"[UPLOAD] File saved, parsing...")

        # Parse and import
        broker_df, price_df = read_excel_data(temp_path)

        print(f"[UPLOAD] Parsed - Price: {len(price_df)} rows, Broker: {len(broker_df)} rows")

        price_count = import_price_data(price_df, stock_code)
        print(f"[UPLOAD] Price imported: {price_count} records")

        broker_count = import_broker_data(broker_df, stock_code)
        print(f"[UPLOAD] Broker imported: {broker_count} records")

        # Import profile data if exists
        profile_data = read_profile_data(temp_path)
        profile_imported = False
        if profile_data:
            profile_count = import_profile_data(profile_data, stock_code)
            profile_imported = profile_count > 0
            print(f"[UPLOAD] Profile imported: {profile_imported}")

        # Import fundamental data if exists
        fund_data = read_fundamental_data(temp_path)
        fundamental_imported = False
        if fund_data:
            fund_count = import_fundamental_data(fund_data, stock_code)
            fundamental_imported = fund_count > 0
            print(f"[UPLOAD] Fundamental imported: {fundamental_imported}")

        # Clean up
        try:
            os.remove(temp_path)
        except:
            pass  # Ignore cleanup errors

        # Clear cache so new stock appears immediately
        clear_cache()
        clear_analysis_cache(stock_code)  # Clear analysis cache for this stock
        print(f"[UPLOAD] Cache cleared after import")

        # Build status message
        status_items = [
            f"Stock: {stock_code}", html.Br(),
            f"File: {filename}", html.Br(),
            f"Price records: {price_count}", html.Br(),
            f"Broker records: {broker_count}"
        ]
        if profile_imported:
            status_items.extend([html.Br(), "Company Profile: Imported"])
        if fundamental_imported:
            status_items.extend([html.Br(), "Fundamental Data: Imported"])

        status = dbc.Alert([
            html.H5("Import Berhasil!", className="alert-heading"),
            html.P(status_items)
        ], color="success")

        log_text = f"  - Price: {price_count} records, Broker: {broker_count} records"
        if profile_imported:
            log_text += ", Profile: Yes"
        if fundamental_imported:
            log_text += ", Fundamental: Yes"

        log = html.Div([
            html.P(f"[{datetime.now().strftime('%H:%M:%S')}] Imported {filename} for {stock_code}"),
            html.P(log_text, className="text-muted small")
        ])

        print(f"[UPLOAD] SUCCESS - {stock_code}: {price_count} price, {broker_count} broker records, profile: {profile_imported}")

        # Auto backup to GitHub after successful import
        try:
            from auto_backup import auto_backup_and_push
            backup_msg = f"Auto backup after import: {stock_code} ({price_count} price, {broker_count} broker)"
            auto_backup_and_push(backup_msg)
            print(f"[UPLOAD] Auto backup to GitHub completed")
        except Exception as backup_error:
            print(f"[UPLOAD] Auto backup failed (non-critical): {backup_error}")

        return status, create_stocks_list(), log  # Dropdown options refreshed by separate callback

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[UPLOAD] ERROR: {str(e)}")
        print(f"[UPLOAD] Traceback: {error_detail}")

        return dbc.Alert([
            html.H5("Error Import!", className="alert-heading"),
            html.P(f"Error: {str(e)}"),
            html.Details([
                html.Summary("Detail Error"),
                html.Pre(error_detail, style={'fontSize': '10px', 'maxHeight': '200px', 'overflow': 'auto'})
            ])
        ], color="danger"), stocks_list, html.Div(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}", className="text-danger")


def create_stocks_list():
    stocks = get_available_stocks()
    if not stocks:
        return html.Div("No stocks in database", className="text-muted")

    items = []
    for stock in stocks:
        price_df = get_price_data(stock)
        broker_df = get_broker_data(stock)

        if not price_df.empty:
            date_range = f"{price_df['date'].min().strftime('%d %b')} - {price_df['date'].max().strftime('%d %b %Y')}"
            items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong(stock, className="me-2"),
                        dbc.Badge(f"{len(price_df)} days", color="info", className="me-1"),
                        dbc.Badge(f"{len(broker_df)} broker records", color="secondary"),
                    ]),
                    html.Small(date_range, className="text-muted")
                ])
            )

    return dbc.ListGroup(items)


# ============================================================
# FORUM CALLBACKS
# ============================================================

# Toggle new thread form
@app.callback(
    Output("new-thread-form", "is_open"),
    [Input("new-thread-btn", "n_clicks")],
    [State("new-thread-form", "is_open")],
    prevent_initial_call=True
)
def toggle_new_thread_form(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

# Toggle admin section
@app.callback(
    Output("admin-section", "is_open"),
    [Input("toggle-admin-btn", "n_clicks")],
    [State("admin-section", "is_open")],
    prevent_initial_call=True
)
def toggle_admin_section(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


# Check for admin-like names and show warning
@app.callback(
    [Output("admin-name-warning", "children"),
     Output("admin-section", "is_open", allow_duplicate=True)],
    [Input("thread-author", "value")],
    [State("admin-section", "is_open")],
    prevent_initial_call=True
)
def check_admin_name(author, is_section_open):
    if not author:
        return "", is_section_open

    import re
    admin_name_pattern = re.compile(r'(admin|administrator|moderator|mod|pengelola|official)', re.IGNORECASE)

    if admin_name_pattern.search(author):
        warning = dbc.Alert([
            html.I(className="fas fa-shield-alt me-2"),
            "Nama mengandung kata 'admin/moderator'. ",
            html.Strong("Password admin wajib diisi!")
        ], color="warning", className="py-2 mb-0")
        return warning, True  # Auto-open admin section

    return "", is_section_open


# PDF upload status
@app.callback(
    Output("pdf-upload-status", "children"),
    [Input("thread-pdf-upload", "filename")],
    prevent_initial_call=True
)
def update_pdf_status(filename):
    if filename:
        return html.Span([
            html.I(className="fas fa-check-circle text-success me-1"),
            f"File terpilih: {filename}"
        ])
    return ""

# Expand/collapse thread content - using MATCH for reliability
@app.callback(
    [Output({"type": "thread-full", "index": MATCH}, "is_open"),
     Output({"type": "thread-preview", "index": MATCH}, "style"),
     Output({"type": "expand-content", "index": MATCH}, "children")],
    [Input({"type": "expand-content", "index": MATCH}, "n_clicks")],
    [State({"type": "thread-full", "index": MATCH}, "is_open")],
    prevent_initial_call=True
)
def toggle_thread_content(n_clicks, is_open):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    # Toggle the state
    if is_open:
        return False, {}, [html.I(className="fas fa-chevron-down me-1"), "Lihat selengkapnya"]
    else:
        return True, {"display": "none"}, [html.I(className="fas fa-chevron-up me-1"), "Sembunyikan"]

# Submit new thread
@app.callback(
    [Output("thread-submit-feedback", "children"),
     Output("admin-threads-container", "children"),
     Output("admin-section-wrapper", "style"),
     Output("community-threads-container", "children")],
    [Input("submit-thread-btn", "n_clicks")],
    [State("thread-author", "value"),
     State("thread-title", "value"),
     State("thread-content", "value"),
     State("stock-selector", "value"),  # Use main stock selector
     State("admin-password", "value"),
     State("admin-options", "value"),
     State("thread-pdf-upload", "contents"),
     State("thread-pdf-upload", "filename")],
    prevent_initial_call=True
)
def submit_new_thread(n_clicks, author, title, content, stock_code, admin_pwd, admin_opts, pdf_contents, pdf_filename):
    if not n_clicks:
        return "", dash.no_update, dash.no_update, dash.no_update

    try:
        # Validate inputs
        if not author or not title or not content:
            return dbc.Alert("Semua field harus diisi!", color="danger"), dash.no_update, dash.no_update, dash.no_update

        if len(title) < 5:
            return dbc.Alert("Judul terlalu pendek (min 5 karakter)", color="warning"), dash.no_update, dash.no_update, dash.no_update

        if len(content) < 20:
            return dbc.Alert("Isi thread terlalu pendek (min 20 karakter)", color="warning"), dash.no_update, dash.no_update, dash.no_update

        # Check for admin-like names - require password
        import re
        admin_name_pattern = re.compile(r'(admin|administrator|moderator|mod|pengelola|official)', re.IGNORECASE)
        if admin_name_pattern.search(author):
            if admin_pwd != ADMIN_PASSWORD:
                return dbc.Alert([
                    html.I(className="fas fa-shield-alt me-2"),
                    "Nama mengandung kata 'admin/moderator'. Masukkan password admin untuk menggunakan nama ini."
                ], color="warning"), dash.no_update, dash.no_update, dash.no_update

        # Check profanity
        title_check = check_profanity(title)
        content_check = check_profanity(content)

        # Level 1 - HARD BLOCK
        if title_check['level'] == 1 or content_check['level'] == 1:
            return dbc.Alert([
                html.I(className="fas fa-ban me-2"),
                "Kalimat mengandung kata tidak pantas. Forum ini untuk diskusi investasi, bukan provokasi."
            ], color="danger"), dash.no_update, dash.no_update, dash.no_update

        # Determine if admin
        is_admin = admin_pwd == ADMIN_PASSWORD
        admin_opts = admin_opts or []
        is_pinned = 'pinned' in admin_opts and is_admin
        is_frozen = 'frozen' in admin_opts and is_admin
        author_type = 'admin' if is_admin else 'user'

        # Level 2 - FLAG as provokatif
        flag = None
        collapsed = False
        initial_score = 0

        if title_check['level'] == 2 or content_check['level'] == 2:
            flag = 'provokatif'
            collapsed = True
            initial_score = -2

        # Process PDF if uploaded
        pdf_data = None
        pdf_name = None
        if pdf_contents and pdf_filename:
            if not pdf_filename.lower().endswith('.pdf'):
                return dbc.Alert("Hanya file PDF yang diperbolehkan!", color="danger"), dash.no_update, dash.no_update, dash.no_update
            try:
                content_type, content_string = pdf_contents.split(',')
                pdf_data = base64.b64decode(content_string)
                pdf_name = pdf_filename
                if len(pdf_data) > 5 * 1024 * 1024:
                    return dbc.Alert("Ukuran file PDF maksimal 5MB!", color="danger"), dash.no_update, dash.no_update, dash.no_update
            except Exception as pdf_err:
                return dbc.Alert(f"Error membaca file PDF: {str(pdf_err)}", color="danger"), dash.no_update, dash.no_update, dash.no_update

        # Insert to database
        insert_query = """
            INSERT INTO forum_threads
            (stock_code, title, content, author_name, author_type, is_pinned, is_frozen, flag, collapsed, score, pdf_data, pdf_filename)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        stock_val = stock_code if stock_code else None
        result = execute_query(insert_query, (
            stock_val, title, content, author, author_type,
            is_pinned, is_frozen, flag, collapsed, initial_score,
            pdf_data, pdf_name
        ))

        # Refresh threads
        threads = get_forum_threads(stock_val)
        admin_threads = [t for t in threads if t['is_pinned'] and t['author_type'] == 'admin']
        community_threads = [t for t in threads if not (t['is_pinned'] and t['author_type'] == 'admin')]

        feedback_msg = "Thread berhasil dibuat!"
        if pdf_name:
            feedback_msg += f" (PDF: {pdf_name})"
        if flag == 'provokatif':
            feedback_msg += " (Ditandai sebagai provokatif - score awal -2)"
        if is_pinned:
            feedback_msg += " (Dipinned sebagai Admin Insight)"

        admin_style = {} if admin_threads else {"display": "none"}

        return (
            dbc.Alert([html.I(className="fas fa-check me-2"), feedback_msg], color="success"),
            [create_thread_card(t) for t in admin_threads],
            admin_style,
            [create_thread_card(t) for t in community_threads] if community_threads else [
                dbc.Alert("Belum ada diskusi.", color="secondary")
            ]
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Submit thread error: {error_detail}")
        return dbc.Alert(f"Error: {str(e)}", color="danger"), dash.no_update, dash.no_update, dash.no_update


# ============================================================
# ADMIN: EDIT THREAD
# ============================================================

# Open edit modal and load thread data
@app.callback(
    [Output("edit-thread-modal", "is_open"),
     Output("edit-thread-title", "value"),
     Output("edit-thread-content", "value"),
     Output("selected-thread-id", "data"),
     Output("edit-feedback", "children")],
    [Input({"type": "edit-thread", "index": ALL}, "n_clicks"),
     Input("cancel-edit-btn", "n_clicks"),
     Input("save-edit-btn", "n_clicks")],
    [State("edit-thread-modal", "is_open"),
     State("edit-admin-password", "value"),
     State("edit-thread-title", "value"),
     State("edit-thread-content", "value"),
     State("selected-thread-id", "data"),
     State("stock-selector", "value")],
    prevent_initial_call=True
)
def handle_edit_thread(edit_clicks, cancel_click, save_click, is_open, password, title, content, thread_id, stock_code):
    ctx = dash.callback_context
    if not ctx.triggered:
        return is_open, "", "", None, ""

    trigger = ctx.triggered[0]['prop_id']

    # Cancel button
    if "cancel-edit-btn" in trigger:
        return False, "", "", None, ""

    # Save button
    if "save-edit-btn" in trigger:
        if password != ADMIN_PASSWORD:
            return True, title, content, thread_id, dbc.Alert("Password salah!", color="danger")
        if not title or not content:
            return True, title, content, thread_id, dbc.Alert("Judul dan isi tidak boleh kosong!", color="warning")

        try:
            query = "UPDATE forum_threads SET title = %s, content = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
            execute_query(query, (title, content, thread_id), fetch=False)
            return False, "", "", None, ""
        except Exception as e:
            return True, title, content, thread_id, dbc.Alert(f"Error: {str(e)}", color="danger")

    # Edit button clicked - open modal and load data
    if "edit-thread" in trigger:
        # Find which button was clicked
        for i, clicks in enumerate(edit_clicks):
            if clicks:
                # Get the thread ID from the pattern
                prop_id = ctx.triggered[0]['prop_id']
                import json
                button_id = json.loads(prop_id.split('.')[0])
                thread_id = button_id['index']

                # Load thread data
                query = "SELECT title, content FROM forum_threads WHERE id = %s"
                result = execute_query(query, (thread_id,), use_cache=False)
                if result:
                    return True, result[0]['title'], result[0]['content'], thread_id, ""
        return is_open, "", "", None, ""

    return is_open, "", "", None, ""


# ============================================================
# ADMIN: DELETE THREAD
# ============================================================

# Open delete modal
@app.callback(
    [Output("delete-thread-modal", "is_open"),
     Output("selected-thread-id", "data", allow_duplicate=True),
     Output("delete-feedback", "children")],
    [Input({"type": "delete-thread", "index": ALL}, "n_clicks"),
     Input("cancel-delete-btn", "n_clicks"),
     Input("confirm-delete-btn", "n_clicks")],
    [State("delete-thread-modal", "is_open"),
     State("delete-admin-password", "value"),
     State("selected-thread-id", "data"),
     State("stock-selector", "value")],
    prevent_initial_call=True
)
def handle_delete_thread(delete_clicks, cancel_click, confirm_click, is_open, password, thread_id, stock_code):
    ctx = dash.callback_context
    if not ctx.triggered:
        return is_open, thread_id, ""

    trigger = ctx.triggered[0]['prop_id']

    # Cancel button
    if "cancel-delete-btn" in trigger:
        return False, None, ""

    # Confirm delete button
    if "confirm-delete-btn" in trigger:
        if password != ADMIN_PASSWORD:
            return True, thread_id, dbc.Alert("Password salah!", color="danger")

        try:
            query = "DELETE FROM forum_threads WHERE id = %s"
            execute_query(query, (thread_id,), fetch=False)
            return False, None, ""
        except Exception as e:
            return True, thread_id, dbc.Alert(f"Error: {str(e)}", color="danger")

    # Delete button clicked - open modal
    if "delete-thread" in trigger:
        for i, clicks in enumerate(delete_clicks):
            if clicks:
                prop_id = ctx.triggered[0]['prop_id']
                import json
                button_id = json.loads(prop_id.split('.')[0])
                thread_id = button_id['index']
                return True, thread_id, ""
        return is_open, thread_id, ""

    return is_open, thread_id, ""


# Refresh threads after edit/delete
@app.callback(
    [Output("admin-threads-container", "children", allow_duplicate=True),
     Output("admin-section-wrapper", "style", allow_duplicate=True),
     Output("community-threads-container", "children", allow_duplicate=True)],
    [Input("edit-thread-modal", "is_open"),
     Input("delete-thread-modal", "is_open")],
    [State("stock-selector", "value")],
    prevent_initial_call=True
)
def refresh_threads_after_admin_action(edit_open, delete_open, stock_code):
    # Only refresh when modals are closed (action completed)
    if not edit_open and not delete_open:
        threads = get_forum_threads(stock_code)
        admin_threads = [t for t in threads if t['is_pinned'] and t['author_type'] == 'admin']
        community_threads = [t for t in threads if not (t['is_pinned'] and t['author_type'] == 'admin')]

        admin_style = {} if admin_threads else {"display": "none"}

        return (
            [create_thread_card(t) for t in admin_threads],
            admin_style,
            [create_thread_card(t) for t in community_threads] if community_threads else [
                dbc.Alert("Belum ada diskusi. Jadilah yang pertama!", color="secondary")
            ]
        )
    return dash.no_update, dash.no_update, dash.no_update


# ============================================================
# FORUM COMMENTS
# ============================================================

# Toggle comments visibility - using MATCH for reliability
@app.callback(
    Output({"type": "comments-collapse", "index": MATCH}, "is_open"),
    [Input({"type": "toggle-comments", "index": MATCH}, "n_clicks")],
    [State({"type": "comments-collapse", "index": MATCH}, "is_open")],
    prevent_initial_call=True
)
def toggle_comments(n_clicks, is_open):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return not is_open if is_open is not None else True


# Submit new comment - using MATCH for reliability
@app.callback(
    [Output({"type": "comments-list", "index": MATCH}, "children"),
     Output({"type": "comment-feedback", "index": MATCH}, "children"),
     Output({"type": "comment-author", "index": MATCH}, "value"),
     Output({"type": "comment-content", "index": MATCH}, "value")],
    [Input({"type": "submit-comment", "index": MATCH}, "n_clicks")],
    [State({"type": "comment-author", "index": MATCH}, "value"),
     State({"type": "comment-content", "index": MATCH}, "value"),
     State({"type": "submit-comment", "index": MATCH}, "id")],
    prevent_initial_call=True
)
def submit_comment(n_clicks, author, content, button_id):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    thread_id = button_id['index']

    # Validate inputs
    if not author or not content:
        return dash.no_update, dbc.Alert("Nama dan komentar harus diisi!", color="warning", className="py-1 px-2 mb-0 small"), dash.no_update, dash.no_update

    if len(content) < 3:
        return dash.no_update, dbc.Alert("Komentar terlalu pendek!", color="warning", className="py-1 px-2 mb-0 small"), dash.no_update, dash.no_update

    # Block admin-like names in comments
    import re
    admin_name_pattern = re.compile(r'(admin|administrator|moderator|mod|pengelola|official)', re.IGNORECASE)
    if admin_name_pattern.search(author):
        return dash.no_update, dbc.Alert("Nama 'admin/moderator' tidak diperbolehkan!", color="danger", className="py-1 px-2 mb-0 small"), dash.no_update, dash.no_update

    # Check profanity
    content_check = check_profanity(content)
    if content_check['level'] == 1:
        return dash.no_update, dbc.Alert("Komentar mengandung kata tidak pantas!", color="danger", className="py-1 px-2 mb-0 small"), dash.no_update, dash.no_update

    try:
        # Insert comment
        insert_query = """
            INSERT INTO forum_comments (thread_id, author_name, content)
            VALUES (%s, %s, %s)
        """
        execute_query(insert_query, (thread_id, author, content), fetch=False)

        # Update comment count
        update_query = "UPDATE forum_threads SET comment_count = comment_count + 1 WHERE id = %s"
        execute_query(update_query, (thread_id,), fetch=False)

        # Get updated comments list
        comments = get_thread_comments(thread_id)
        comments_children = [create_comment_card(c) for c in comments] if comments else [
            html.Small("Belum ada komentar.", className="text-muted")
        ]

        return (
            comments_children,
            dbc.Alert("Komentar berhasil ditambahkan!", color="success", className="py-1 px-2 mb-0 small"),
            "",  # Clear author
            ""   # Clear content
        )

    except Exception as e:
        return dash.no_update, dbc.Alert(f"Error: {str(e)}", color="danger", className="py-1 px-2 mb-0 small"), dash.no_update, dash.no_update


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == '__main__':
    print("Starting Stock Broker Analysis Dashboard...")
    print("Open http://localhost:8050 in your browser")
    app.run(debug=True, host='0.0.0.0', port=8050)
