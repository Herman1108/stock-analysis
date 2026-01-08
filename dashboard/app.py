"""
Stock Analysis Dashboard - Multi-Emiten Support
Dynamic analysis with file upload capability
"""
import sys
import os
import base64
import io

# Add app directory to path
app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
sys.path.insert(0, app_dir)

import dash
from dash import dcc, html, dash_table, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from database import execute_query, get_cursor, clear_cache, get_cache_stats, preload_stock_data
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
    'persistence': 'Konsistensi broker dalam membeli/menjual berturut-turut. ≥5 hari = niat serius.',
    'elasticity': 'Hubungan antara perubahan volume dan perubahan harga. Volume↑ + Harga stabil = absorpsi.',
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
        status_icon = "✓" if passed else "✗"
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
                    html.Li([html.Strong("≥70: ", style={"color": "#28a745"}), "STRONG ACCUMULATION - Consider Entry"]),
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
• Broker Sensitivity (20%) - Apakah broker "pintar" sedang akumulasi?
• Foreign Flow (20%) - Apakah investor asing masuk atau keluar?
• Smart Money (15%) - Apakah ada tanda pembelian besar tersembunyi?
• Price Position (15%) - Posisi harga terhadap rata-rata pergerakan
• Accumulation (15%) - Apakah sedang dalam fase akumulasi?
• Volume Analysis (15%) - Apakah volume di atas rata-rata?

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
• Win Rate = % kejadian broker akumulasi → harga naik ≥10%
• Lead Time = Berapa hari sebelum naik, broker mulai beli
• Score = Gabungan dari Win Rate, Lead Time, dan Korelasi

Contoh: Jika broker MS punya Win Rate 70% dan Lead Time 3 hari,
artinya ketika MS beli, 70% kemungkinan harga naik ≥10% dalam 10 hari,
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
• INFLOW = Asing beli lebih banyak (positif untuk harga)
• OUTFLOW = Asing jual lebih banyak (negatif untuk harga)
• Consistency = Berapa hari berturut-turut inflow/outflow
• Momentum = Perubahan dibanding kemarin (akselerasi)

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
• Volume naik TAPI frekuensi rendah = transaksi besar, sedikit pelaku
• Volume naik DAN frekuensi naik = banyak retail ikut-ikutan (FOMO)

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

• Close vs Avg = Harga penutupan vs rata-rata hari ini
• Price vs MA5 = Harga vs rata-rata 5 hari
• Price vs MA20 = Harga vs rata-rata 20 hari
• Distance from Low = Jarak dari titik terendah 20 hari
• Breakout = Apakah tembus level tertinggi 5 hari?

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
• Harga sideways (bergerak dalam range kecil, <10%)
• Volume mulai meningkat
• Foreign flow cenderung positif
• Broker sensitif mulai masuk
• Belum breakout

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
• >= 2.0x = Very High (aktivitas sangat tinggi, perhatian besar)
• >= 1.5x = High (aktivitas tinggi)
• >= 1.2x = Above Average (di atas rata-rata)
• >= 0.8x = Normal
• < 0.8x = Low (aktivitas rendah, kurang menarik)

Volume-Price Trend (VPT):
• Volume naik + Harga naik = BULLISH (akumulasi kuat)
• Volume naik + Harga turun = DISTRIBUTION (distribusi/jual)
• Volume turun + Harga naik = WEAK RALLY (kenaikan lemah)
• Volume turun + Harga turun = CONSOLIDATION

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
• Tanggal Sinyal = Kapan sinyal beli pertama terdeteksi
• Harga Saat Sinyal = Harga saat sinyal muncul
• Harga Sekarang = Harga terkini
• Perubahan = Berapa persen harga sudah naik/turun dari sinyal

ZONE:
• SAFE (hijau) = Masih aman beli, harga dekat dengan sinyal (<3%)
• MODERATE (biru) = Boleh beli cicil, jangan all-in (3-7%)
• CAUTION (kuning) = Tunggu pullback lebih baik (7-12%)
• FOMO ALERT (merah) = Sudah terlambat, jangan kejar (>12%)
'''
    },
    'avg_buy': {
        'title': 'Avg Buy Broker',
        'short': 'Rata-rata harga beli broker untuk menentukan support level.',
        'detail': '''
Avg Buy menunjukkan rata-rata harga beli setiap broker.

Kenapa penting?
• Broker dengan Avg Buy > Harga Sekarang = Sedang RUGI (floating loss)
• Broker yang rugi cenderung akan DEFEND posisi mereka
• Area Avg Buy broker besar = SUPPORT LEVEL potensial

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
Broker akumulasi → Harga naik ≥10% dalam 10 hari berikutnya

Contoh: Win Rate 60% berarti:
Dari 10 kali broker ini akumulasi, 6 kali harga naik ≥10%.

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
    stocks = get_available_stocks()
    return dbc.Navbar(
        dbc.Container([
            # Brand + Stock Selector + Theme Toggle (always visible)
            html.Div([
                dbc.NavbarBrand("HermanStock", href="/", className="me-2", style={"fontSize": "1rem"}),
                # Stock Selector - searchable dropdown for 30+ stocks
                dcc.Dropdown(
                    id='stock-selector',
                    options=[{'label': s, 'value': s} for s in stocks],
                    value=stocks[0] if stocks else 'PANI',
                    style={'width': '120px', 'minWidth': '120px'},
                    clearable=False,
                    searchable=True,  # Enable search/filter
                    placeholder="Cari emiten...",
                    persistence=True,
                    persistence_type='session',
                    className="stock-dropdown"
                ),
                # Theme toggle button (sun/moon icon)
                dbc.Button(
                    html.I(className="fas fa-sun", id="theme-icon"),
                    id="theme-toggle",
                    color="link",
                    size="sm",
                    className="ms-2 text-warning",
                    title="Toggle Light/Dark Mode"
                ),
            ], className="d-flex align-items-center"),

            # Hamburger toggle button for mobile only - orange color
            dbc.Button(
                html.I(className="fas fa-bars"),
                id="navbar-toggler",
                color="warning",
                size="sm",
                className="d-lg-none ms-2",
                n_clicks=0,
                style={"border": "none"}
            ),

            # Desktop nav items - always visible on large screens
            dbc.Nav([
                dbc.NavItem(dcc.Link(dbc.Button("Home", color="warning", size="sm", className="fw-bold text-white me-1"), href="/")),
                dbc.NavItem(dcc.Link(dbc.Button("Dashboard", color="warning", size="sm", className="fw-bold text-white me-1"), href="/dashboard")),
                dbc.NavItem(dcc.Link(dbc.Button("Analysis", color="warning", size="sm", className="fw-bold text-white me-1"), href="/analysis")),
                dbc.NavItem(dcc.Link(dbc.Button("Upload", color="warning", size="sm", className="fw-bold text-white me-1"), href="/upload")),
            ], className="ms-auto d-none d-lg-flex", navbar=True),

            # Mobile dropdown menu - only visible when hamburger clicked
            dbc.Collapse(
                dbc.Nav([
                    dbc.NavItem(dcc.Link(dbc.Button("Home", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Dashboard", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/dashboard", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Analysis", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/analysis", refresh=True)),
                    dbc.NavItem(dcc.Link(dbc.Button("Upload", color="warning", size="sm", className="fw-bold text-white mb-1 w-100"), href="/upload", refresh=True)),
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

def create_landing_page():
    """Create landing page with stock selection and overview using unified analysis data from 3 submenus"""
    stocks = get_available_stocks()

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
            action_icon = decision.get('icon', '⏳')

            # Overall signal from accumulation
            overall_signal = summary.get('overall_signal', 'NETRAL')
            signal_color = "success" if overall_signal == 'AKUMULASI' else "danger" if overall_signal == 'DISTRIBUSI' else "secondary"

            # Create card with unified analysis
            card = dbc.Col([
                dbc.Card([
                    # Header with Decision Action
                    dbc.CardHeader([
                        html.Div([
                            html.H3(stock_code, className="mb-0 d-inline fw-bold"),
                            dbc.Badge([
                                html.Span(action_icon, className="me-1"),
                                action
                            ], color=action_color, className="ms-2 fs-6 px-3 py-2")
                        ], className="d-flex align-items-center justify-content-between")
                    ], className="bg-dark", style={"borderBottom": f"3px solid var(--bs-{action_color})"}),

                    dbc.CardBody([
                        # Price & Change Row
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("Harga Saat Ini", className="text-muted d-block"),
                                    html.H4(f"Rp {current_price:,.0f}", className="mb-0 text-warning"),
                                ], className="text-center")
                            ], width=6),
                            dbc.Col([
                                html.Div([
                                    html.Small("Perubahan", className="text-muted d-block"),
                                    html.H4(
                                        f"{price_change:+.1f}%",
                                        className=f"mb-0 text-{'success' if price_change > 0 else 'danger' if price_change < 0 else 'muted'}"
                                    ),
                                ], className="text-center")
                            ], width=6),
                        ], className="mb-3"),

                        # Markup Trigger Alert (if detected)
                        html.Div([
                            dbc.Badge([
                                html.Span("🔥", className="me-1"),
                                "MARKUP TRIGGER!"
                            ], color="warning", className="w-100 py-2 mb-2")
                        ]) if markup_trigger.get('markup_triggered') else html.Div(),

                        html.Hr(className="my-2"),

                        # 3 Submenu Summary Row
                        html.H6("Ringkasan 3 Analisis", className="text-muted small mb-2 text-center"),
                        dbc.Row([
                            # Fundamental
                            dbc.Col([
                                html.Div([
                                    html.Small("Fundamental", className="text-success d-block"),
                                    html.Div([
                                        html.Span(f"PER {fundamental.get('per', 0):.1f}x" if fundamental.get('has_data') else "N/A",
                                                  className="small"),
                                    ]),
                                    dbc.Badge(fundamental.get('valuation', 'N/A'),
                                              color=fundamental.get('valuation_color', 'secondary'),
                                              className="mt-1", style={"fontSize": "10px"})
                                ], className="text-center")
                            ], width=4),

                            # Support & Resistance
                            dbc.Col([
                                html.Div([
                                    html.Small("Posisi Harga", className="text-info d-block"),
                                    html.Div([
                                        html.Span(
                                            "Dekat Support" if sr.get('position') == 'NEAR_SUPPORT'
                                            else "Dekat Resist" if sr.get('position') == 'NEAR_RESISTANCE'
                                            else "Di Tengah" if sr.get('has_data') else "N/A",
                                            className="small"
                                        ),
                                    ]),
                                    dbc.Badge(
                                        f"{sr.get('dist_from_support', 0):.0f}% dari support" if sr.get('has_data') else "N/A",
                                        color="success" if sr.get('position') == 'NEAR_SUPPORT' else "danger" if sr.get('position') == 'NEAR_RESISTANCE' else "secondary",
                                        className="mt-1", style={"fontSize": "10px"}
                                    )
                                ], className="text-center")
                            ], width=4),

                            # Accumulation / Momentum Engine
                            dbc.Col([
                                html.Div([
                                    # Show which engine detected signal
                                    html.Small(
                                        "⚡ Momentum" if impulse_signal.get('impulse_detected') 
                                        else "📊 Akumulasi",
                                        className=f"{'text-danger' if impulse_signal.get('impulse_detected') else 'text-warning'} d-block fw-bold"
                                    ),
                                    dbc.Badge(
                                        impulse_signal.get('strength', 'IMPULSE') if impulse_signal.get('impulse_detected')
                                        else overall_signal,
                                        color="danger" if impulse_signal.get('impulse_detected') else signal_color,
                                        className="mb-1"
                                    ),
                                    html.Div([
                                        html.Span(
                                            f"Vol {impulse_signal.get('metrics', {}).get('volume_ratio', 0):.1f}x" if impulse_signal.get('impulse_detected')
                                            else f"{confidence.get('passed', 0)}/6 Valid",
                                            className="small text-muted"
                                        ),
                                    ]),
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-3"),

                        html.Hr(className="my-2"),

                        # Entry Zone & Invalidation
                        html.Div([
                            dbc.Row([
                                dbc.Col([
                                    html.Small("Entry Zone", className="text-success d-block"),
                                    html.Strong(f"{entry_zone.get('low', 0):,.0f}-{entry_zone.get('high', 0):,.0f}" if entry_zone else "N/A", className="small")
                                ], width=6, className="text-center"),
                                dbc.Col([
                                    html.Small("Invalidation", className="text-danger d-block"),
                                    html.Strong(f"< {invalidation:,.0f}" if invalidation else "N/A", className="small")
                                ], width=6, className="text-center"),
                            ])
                        ], className="mb-3 p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),

                        # Decision Reason
                        html.Div([
                            html.Small([
                                html.I(className=f"fas fa-{'bolt text-danger' if action in ['MASUK_MOMENTUM', 'PANTAU_BREAKOUT'] else 'check-circle text-success' if action in ['ENTRY', 'ADD'] else 'exclamation-circle text-warning' if action in ['WAIT', 'TUNGGU', 'SIAGA'] else 'times-circle text-danger'} me-2"),
                                decision.get('description', '')[:60] + "..." if len(decision.get('description', '')) > 60 else decision.get('description', '')
                            ], className="text-muted")
                        ], className="mb-3"),

                        # Action Buttons
                        html.Div([
                            dbc.Button([
                                html.I(className="fas fa-chart-pie me-1"),
                                "Analysis"
                            ], href=f"/analysis?stock={stock_code}", color=action_color, size="sm", className="me-1 flex-grow-1"),
                            dbc.Button([
                                html.I(className="fas fa-chart-line me-1"),
                                "Dashboard"
                            ], href=f"/dashboard?stock={stock_code}", color="outline-light", size="sm", className="flex-grow-1"),
                        ], className="d-flex")
                    ])
                ], className="h-100 shadow", color="dark", outline=True,
                   style={"borderColor": f"var(--bs-{action_color})", "borderWidth": "2px"})
            ], md=6, lg=4, className="mb-4")

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
            ], md=6, lg=4, className="mb-4")
            stock_cards.append(card)

    return html.Div([
        # Hero Section
        dbc.Container([
            html.Div([
                html.H1([
                    html.I(className="fas fa-chart-bar me-3"),
                    "Stock Broker Analysis"
                ], className="display-5 text-center mb-3"),
                html.P(
                    "Analisis terintegrasi: Fundamental, Support/Resistance, dan Akumulasi untuk keputusan trading optimal",
                    className="lead text-center text-muted mb-4"
                ),
                html.Hr(className="my-4"),
            ], className="py-4")
        ]),

        # Stock Selection
        dbc.Container([
            html.Div([
                html.H4([
                    html.I(className="fas fa-list-alt me-2"),
                    f"Pilih Emiten ({len(stocks)} tersedia)"
                ], className="mb-0 d-inline-block me-3"),
                # Legend
                html.Div([
                    dbc.Badge("🟢 ENTRY/ADD", color="success", className="me-1 small"),
                    dbc.Badge("🟡 WAIT/HOLD", color="warning", className="me-1 small"),
                    dbc.Badge("🔴 EXIT", color="danger", className="small"),
                ], className="d-inline-block")
            ], className="mb-4 d-flex align-items-center flex-wrap"),

            dbc.Row(stock_cards),

            # Quick Links
            html.Hr(className="my-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5([html.I(className="fas fa-upload me-2"), "Upload Data"], className="mb-2"),
                            html.P("Import data broker summary dari file Excel", className="text-muted small mb-2"),
                            dbc.Button("Upload", href="/upload", color="outline-light", size="sm")
                        ])
                    ], color="secondary")
                ], md=12),
            ], className="mb-4")
        ], fluid=True)
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
            icon = "●"
            title = f"{date_str}: BUY Dominan (Buy:{buy_lot:,.0f} vs Sell:{sell_lot:,.0f})"
        elif day['status'] == 'SELL':
            icon_class = "text-danger"
            icon = "●"
            title = f"{date_str}: SELL Dominan (Buy:{buy_lot:,.0f} vs Sell:{sell_lot:,.0f})"
        else:
            icon_class = "text-secondary"
            icon = "○"
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

    # === 14. WHAT THIS MEANS ===
    if overall_signal == 'AKUMULASI' and conf_level in ['HIGH', 'VERY_HIGH']:
        what_means = "Pola ini menunjukkan akumulasi terstruktur, namun belum menentukan arah pergerakan harga berikutnya."
    elif overall_signal == 'DISTRIBUSI':
        what_means = "Terdeteksi penjualan bertahap oleh pelaku besar. Berhati-hati dengan posisi beli baru."
    else:
        what_means = "Pola belum terbentuk jelas. Pantau terus untuk konfirmasi arah selanjutnya."

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
                html.Span(risk.get('icon', '⚠️'), className="me-2"),
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
                        "Timeline menunjukkan kapan sinyal berubah (Akumulasi ↔ Distribusi ↔ Netral) dan tingkat kekuatannya (Weak/Moderate/Strong)."
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
                            html.Span("🔥", style={"fontSize": "28px"}),
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
                                html.Span(decision_rule.get('icon', '⏳'), style={"fontSize": "40px"}),
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
                            html.Span("⏳", className="me-1"), html.Span("WAIT", className="text-secondary fw-bold me-2"), html.Span("= Observasi ", className="text-muted me-3"),
                            html.Span("🟢", className="me-1"), html.Span("ENTRY", className="text-success fw-bold me-2"), html.Span("= Masuk bertahap ", className="text-muted me-3"),
                            html.Span("➕", className="me-1"), html.Span("ADD", className="text-primary fw-bold me-2"), html.Span("= Tambah posisi ", className="text-muted me-3"),
                            html.Span("✋", className="me-1"), html.Span("HOLD", className="text-info fw-bold me-2"), html.Span("= Tahan/kelola ", className="text-muted me-3"),
                            html.Span("🚨", className="me-1"), html.Span("EXIT", className="text-danger fw-bold me-2"), html.Span("= Kurangi/keluar", className="text-muted"),
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
                                html.Th("Volume Δ", className="text-center", style={"width": "20%"}),
                                html.Th("Price Δ", className="text-center", style={"width": "20%"}),
                                html.Th("Range", className="text-center", style={"width": "20%"}),
                                html.Th("Absorption?", className="text-center", style={"width": "20%"}),
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
                                    dbc.Badge("Ya", color="success") if vol_price_multi.get('horizons', {}).get('1d', {}).get('is_absorption') else
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
                                    dbc.Badge("Ya", color="success") if vol_price_multi.get('horizons', {}).get('5d', {}).get('is_absorption') else
                                    dbc.Badge("Tidak", color="secondary"),
                                    className="text-center"
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
                                    dbc.Badge("Ya", color="success") if vol_price_multi.get('horizons', {}).get('10d', {}).get('is_absorption') else
                                    dbc.Badge("Tidak", color="secondary"),
                                    className="text-center"
                                ),
                            ], style={"backgroundColor": "rgba(40,167,69,0.1)" if vol_price_multi.get('structural_absorption') else "transparent"}),
                        ])
                    ], className="table table-sm table-dark", style={"fontSize": "12px"}),

                    # Legend
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Volume Δ = perubahan volume vs periode sebelumnya | ",
                        "Price Δ = perubahan harga close-to-close | ",
                        "Range = high-low sebagai % dari mid price"
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
                            html.Span("●", className="text-success me-1"), html.Small("Buy Dominan (>55%)", className="text-muted me-3"),
                            html.Span("●", className="text-danger me-1"), html.Small("Sell Dominan (<45%)", className="text-muted me-3"),
                            html.Span("○", className="text-secondary me-1"), html.Small("Seimbang", className="text-muted"),
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

            # === 14. WHAT THIS MEANS ===
            dbc.Card([
                dbc.CardHeader([
                    html.H6([html.I(className="fas fa-graduation-cap me-2"), "What This Means (Edukasi)"], className="mb-0 text-info d-inline"),
                    html.Small(" - Kesimpulan dalam bahasa sederhana", className="text-muted ms-2")
                ]),
                dbc.CardBody([
                    html.Small("Penjelasan pola yang terdeteksi tanpa rekomendasi beli/jual:", className="text-muted d-block mb-2"),
                    html.P(what_means, className="mb-0 fst-italic")
                ])
            ], className="mb-3", color="dark", outline=True),

            # === 15. HIDDEN/EXPANDABLE SECTION ===
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
                    "• BETTER ENTRY: Harga turun <5% dari sinyal → kesempatan entry lebih baik", html.Br(),
                    "• DISCOUNTED: Harga turun 5-10% → hati-hati, sinyal mungkin melemah", html.Br(),
                    "• SIGNAL FAILED: Harga turun >10% → review ulang, sinyal mungkin gagal", html.Br(),
                    "• SAFE/MODERATE: Harga naik <7% dari sinyal → masih aman", html.Br(),
                    "• CAUTION/FOMO: Harga naik >7% dari sinyal → risiko tinggi, tunggu pullback", html.Br(),
                    "• PHASE ENDED: Harga pernah naik >10% lalu turun ke <5% → fase akumulasi selesai, tunggu sinyal baru",
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
    interest_zone = avg_buy_analysis.get('interest_zone', None)

    # Use multi-method S/R analysis if available
    if sr_analysis and 'key_support' in sr_analysis:
        support_price = sr_analysis['key_support']
        support_display = f"Rp {support_price:,.0f}"
        support_class = "text-success"
        support_pct = sr_analysis.get('interpretation', {}).get('support_distance_pct', 0)
        support_note = f"(-{abs(support_pct):.1f}% dari harga sekarang)"
    else:
        # Fallback: estimasi -5%
        estimated_support = current_price * 0.95
        support_display = f"~Rp {estimated_support:,.0f}"
        support_class = "text-warning"
        support_note = "(estimasi -5%)"

    # Determine interest zone display (where loss brokers bought)
    if interest_zone and interest_zone > current_price:
        interest_display = f"Rp {interest_zone:,.0f}"
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
                            "Support Level ",
                            html.I(className="fas fa-arrow-down", style={"fontSize": "10px"})
                        ], className="text-muted small"),
                        html.H4(support_display, className=f"{support_class} mb-0"),
                        html.Small(support_note, className="text-muted", style={"fontSize": "10px"})
                    ], className="text-center")
                ], width=3),
            ], className="mb-2"),

            # Second row: Interest Zone (if exists)
            dbc.Row([
                dbc.Col(width=9),
                dbc.Col([
                    html.Div([
                        html.H6([
                            "Interest Zone ",
                            html.I(className="fas fa-arrow-up", style={"fontSize": "10px"})
                        ], className="text-muted small"),
                        html.H4(interest_display, className="text-danger mb-0") if interest_zone else html.H4("-", className="text-muted mb-0"),
                        html.Small(interest_note, className="text-muted", style={"fontSize": "10px"}) if interest_note else None
                    ], className="text-center")
                ], width=3),
            ], className="mb-3") if interest_zone else None,

            html.Hr(),

            # Interpretation
            html.Small([
                html.Strong("Cara Baca: "),
                html.Br(),
                html.Span("• Support Level", className="text-success"), " = Avg Buy broker PROFIT (di bawah harga sekarang)",
                html.Br(),
                html.Span("• Interest Zone", className="text-danger"), " = Avg Buy broker LOSS (di atas harga sekarang)",
                html.Br(),
                "• Broker PROFIT sudah untung → mungkin hold/jual",
                html.Br(),
                "• Broker LOSS floating rugi → mungkin averaging down atau defend di area Avg Buy mereka",
                html.Br(),
                html.Strong("Tips: "), "Interest Zone adalah area dimana broker besar membeli. Jika harga naik ke sana, ada tekanan jual."
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

    # Add Support lines (green)
    support_colors = ['#00E676', '#00C853', '#00A844', '#008B35', '#006D27']
    for i, sup in enumerate(supports[:5]):
        level = sup['level']
        color = support_colors[min(i, len(support_colors)-1)]
        confirmations = sup.get('confirmations', 1)
        line_width = 1 + confirmations  # Thicker for multi-confirmed

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

    # Add Resistance lines (red)
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
            strength_stars = "★★★"
        elif strength >= 50:
            strength_stars = "★★"
        elif strength >= 20:
            strength_stars = "★"

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
                html.Span("• Volume Profile", style={"color": source_colors['Volume Profile']}),
                " = Area dengan transaksi terbesar (banyak buyer/seller tertarik)",
                html.Br(),
                html.Span("• Price Bounce", style={"color": source_colors['Price Bounce']}),
                " = Level harga yang sering memantul (historically proven)",
                html.Br(),
                html.Span("• Broker Position", style={"color": source_colors['Broker Position']}),
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
                "• ", html.Span("Avg Buy", className="text-info"), " = Rata-rata harga beli broker dalam 60 hari",
                html.Br(),
                "• ", html.Span("Floating +%", className="text-success"), " = Broker sedang profit",
                html.Br(),
                "• ", html.Span("Floating -%", className="text-danger"), " = Broker sedang loss (mungkin defend/averaging)",
                html.Br(),
                "• Net positif = akumulasi, Net negatif = distribusi",
                html.Br(),
                "• ", html.Span("Background Orange", style={"backgroundColor": "#FF8C00", "color": "#000", "padding": "1px 4px", "borderRadius": "3px"}), " = Broker Sensitive (pola akumulasi akurat)"
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

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-layer-group me-2"),
                f"Support & Resistance - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_submenu_nav('support-resistance', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # ========== S/R CHART WITH VOLUME ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-chart-area me-2"),
                    "Price Chart with S/R Levels"
                ], className="mb-0"),
            ]),
            dbc.CardBody([
                create_sr_chart(stock_code, sr_analysis, days=60)
            ], className="p-2")
        ], className="mb-4", color="dark"),

        # ========== SUPPORT/RESISTANCE LEVELS (Multi-Method) ==========
        create_sr_levels_card(sr_analysis, stock_code),

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
                dbc.CardHeader("📊 Market Sentiment"),
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

        # Foreign flow
        foreign_today = foreign_flow.get('latest_value', 0) / 1e9
        foreign_yesterday = foreign_flow.get('prev_value', 0) / 1e9
        foreign_signal = foreign_flow.get('signal', 'NEUTRAL')
        foreign_streak = foreign_flow.get('streak_days', 0)

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

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-pie me-2"),
                html.Span("Market Sentiment Today", className="fw-bold")
            ]),
            dbc.CardBody([
                # Top row: 3 metric cards with tooltips
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Small([
                                html.Span("Foreign Flow", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                                         title=TERM_DEFINITIONS.get('foreign_flow', '')),
                                html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                            ], className="text-muted"),
                            html.H4([
                                f"{foreign_today:+.1f}B ",
                                html.Span("🟢" if foreign_today > 0 else "🔴", style={"fontSize": "16px"})
                            ], className="mb-0"),
                            html.Small(f"vs {foreign_yesterday:+.1f}B yesterday", className="text-muted")
                        ], className="text-center p-2 rounded metric-box")
                    ], width=4),
                    dbc.Col([
                        html.Div([
                            html.Small([
                                html.Span("Accum Ratio", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                                         title=TERM_DEFINITIONS.get('accum_ratio', '')),
                                html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                            ], className="text-muted"),
                            html.H4([
                                f"{accum_ratio:.0f}% Buy",
                            ], className=f"mb-0 text-{'success' if accum_ratio > 55 else ('danger' if accum_ratio < 45 else 'warning')}"),
                            html.Small(f"{100-accum_ratio:.0f}% Sell", className="text-muted")
                        ], className="text-center p-2 rounded metric-box")
                    ], width=4),
                    dbc.Col([
                        html.Div([
                            html.Small([
                                html.Span("Foreign Streak", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                                         title=TERM_DEFINITIONS.get('foreign_streak', '')),
                                html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                            ], className="text-muted"),
                            html.H4([
                                f"{foreign_streak} days ",
                                html.Span(foreign_signal[:3] if foreign_signal else "NEU",
                                         className=f"badge bg-{'success' if 'INFLOW' in foreign_signal else ('danger' if 'OUTFLOW' in foreign_signal else 'secondary')}")
                            ], className="mb-0"),
                            html.Small("consecutive", className="text-muted")
                        ], className="text-center p-2 rounded metric-box")
                    ], width=4),
                ], className="mb-3"),

                # Weekly trend mini chart
                html.Div([
                    html.Small("Weekly Trend: ", className="text-muted me-2"),
                    *[html.Span([
                        html.Span(f"{d['net']:+.1f}B ",
                                 className=f"text-{'success' if d['net'] > 0 else 'danger'} me-2",
                                 style={"fontSize": "11px"})
                    ]) for d in weekly_data],
                    html.Span(f"Total: {weekly_total:+.1f}B",
                             className=f"fw-bold text-{'success' if weekly_total > 0 else 'danger'}")
                ], className="mb-2", style={"fontSize": "11px"}),

                # By broker type
                html.Div([
                    html.Small("By Type: ", className="text-muted me-2"),
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

                html.Hr(className="my-2"),

                # Penjelasan Section
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Cara Baca: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("• Foreign Flow: "), "Net beli/jual investor asing hari ini. ",
                        html.Span("Positif (+) = asing masuk (bullish), ", className="text-success"),
                        html.Span("Negatif (-) = asing keluar (bearish)", className="text-danger"),
                        html.Br(),
                        html.Strong("• Accum Ratio: "), "Perbandingan total pembelian vs penjualan semua broker. ",
                        ">55% Buy = sentiment beli kuat, <45% = sentiment jual",
                        html.Br(),
                        html.Strong("• Foreign Streak: "), "Berapa hari berturut-turut asing konsisten beli/jual. ",
                        "Streak panjang = trend kuat",
                        html.Br(),
                        html.Strong("• Weekly Trend: "), "Net flow 5 hari terakhir. Lihat apakah trend naik/turun",
                        html.Br(),
                        html.Strong("• By Type: "), "Siapa yang mendominasi? Asing biasanya punya riset lebih dalam"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box")
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("📊 Market Sentiment"),
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

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-bullseye me-2 text-warning"),
                html.Span("Signal Drivers", className="fw-bold text-warning"),
                html.Small(" - Penggerak Keputusan", className="text-muted ms-2")
            ], className="bg-transparent"),
            dbc.CardBody([
                # === PRIMARY SIGNAL DRIVERS ===
                html.Div([
                    html.Small([
                        html.I(className="fas fa-star me-1 text-warning"),
                        "PRIMARY - Langsung Mempengaruhi Keputusan"
                    ], className="text-warning fw-bold", style={"fontSize": "10px"})
                ], className="mb-2"),

                dbc.Row([
                    dbc.Col([
                        primary_metric_card(
                            "Market Phase",
                            market_phase,
                            phase_desc,
                            phase_color,
                            tooltip_key="market_phase",
                            icon="fa-chart-line"
                        )
                    ], md=4, className="mb-2"),
                    dbc.Col([
                        primary_metric_card(
                            "Accum Phase",
                            "AKTIF" if accum_in else "TIDAK",
                            f"Range {accum_range:.1f}% | {accum_days} hari",
                            "success" if accum_in else "secondary",
                            tooltip_key="accum_phase",
                            icon="fa-compress-arrows-alt"
                        )
                    ], md=4, className="mb-2"),
                    dbc.Col([
                        primary_metric_card(
                            "Smart Money",
                            f"{smart_score:.0f}",
                            f"{'Terdeteksi' if smart_detected == 'YES' else 'Tidak ada'} akumulasi besar",
                            "success" if smart_score > 60 else ("warning" if smart_score > 40 else "secondary"),
                            tooltip_key="smart_money",
                            icon="fa-user-tie"
                        )
                    ], md=4, className="mb-2"),
                ], className="mb-3"),

                # === SECONDARY SUPPORTING METRICS ===
                html.Div([
                    html.Small([
                        html.I(className="fas fa-layer-group me-1 text-info"),
                        "SUPPORTING - Konteks & Konfirmasi"
                    ], className="text-info", style={"fontSize": "10px"})
                ], className="mb-2"),

                dbc.Row([
                    dbc.Col([
                        secondary_metric_card(
                            "Broker Sens.",
                            f"{sens_score:.0f}%",
                            html.Span(["Top: ", colored_broker(top_brokers[0], with_badge=True)] if top_brokers else "N/A"),
                            "info" if sens_score > 50 else "secondary",
                            tooltip_key="broker_sensitivity"
                        )
                    ], width=3),
                    dbc.Col([
                        secondary_metric_card(
                            "Foreign",
                            f"{foreign_score:+.0f}",
                            foreign_signal[:8] if foreign_signal else "N/A",
                            "success" if foreign_score > 0 else ("danger" if foreign_score < 0 else "secondary"),
                            tooltip_key="foreign_flow"
                        )
                    ], width=3),
                    dbc.Col([
                        secondary_metric_card(
                            "RVOL",
                            f"{rvol:.1f}x",
                            "Vol tinggi" if rvol > 1.2 else ("Normal" if rvol > 0.8 else "Vol rendah"),
                            "success" if rvol > 1.2 else ("warning" if rvol > 0.8 else "secondary"),
                            tooltip_key="rvol"
                        )
                    ], width=3),
                    dbc.Col([
                        secondary_metric_card(
                            "S/R",
                            f"-{support_pct:.0f}%",
                            f"+{resist_pct:.0f}% ke R",
                            "info"
                        )
                    ], width=3),
                ]),

                html.Hr(className="my-2"),

                # Quick Guide
                html.Div([
                    html.Small([
                        html.I(className="fas fa-lightbulb me-1 text-warning"),
                        html.Strong("Quick Guide: "),
                        "PRIMARY menentukan aksi (beli/jual/tunggu). ",
                        "SUPPORTING mengkonfirmasi dan memberikan konteks. ",
                        "Jika PRIMARY bullish tapi SUPPORTING bearish, tunggu konfirmasi."
                    ], className="text-muted", style={"fontSize": "9px"})
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,193,7,0.1)"})
            ])
        ], className="mb-3", style={"border": "1px solid var(--bs-warning)"})
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("🎯 Key Metrics"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def create_broker_movement_alert(stock_code='CDIA'):
    """
    Section 3: Broker Movement Alert
    - New accumulation signals
    - New distribution warnings
    - Biggest movement today vs yesterday
    """
    try:
        broker_df = get_broker_data(stock_code)

        if broker_df.empty:
            return dbc.Card([
                dbc.CardHeader("🔔 Broker Movement Alert"),
                dbc.CardBody(html.P("No data available", className="text-muted"))
            ], className="mb-3", color="dark")

        # Get last 2 days
        dates_sorted = sorted(broker_df['date'].unique(), reverse=True)
        if len(dates_sorted) < 2:
            return dbc.Card([
                dbc.CardHeader("🔔 Broker Movement Alert"),
                dbc.CardBody(html.P("Need at least 2 days of data", className="text-muted"))
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

        # Build accumulation items - horizontal with better spacing
        accum_items = [html.Span([
            colored_broker(m['broker'], with_badge=True),
            html.Span(f" +{m['today']/1e9:.1f}B", className="text-success fw-bold", style={"marginLeft": "4px"})
        ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "20px", "marginBottom": "4px"}) for m in new_accum] if new_accum else [html.Small("None today", className="text-muted")]

        # Build distribution items - horizontal with better spacing
        dist_items = [html.Span([
            colored_broker(m['broker'], with_badge=True),
            html.Span(f" {m['today']/1e9:.1f}B", className="text-danger fw-bold", style={"marginLeft": "4px"})
        ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "20px", "marginBottom": "4px"}) for m in new_dist] if new_dist else [html.Small("None today", className="text-muted")]

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-bell me-2"),
                html.Span("Broker Movement Alert", className="fw-bold")
            ]),
            dbc.CardBody([
                dbc.Row([
                    # New Accumulation Signal
                    dbc.Col([
                        html.Div([
                            html.Span([
                                html.I(className="fas fa-arrow-up text-success me-1"),
                                html.Span("New Accumulation", className="text-success fw-bold")
                            ]),
                            html.Span(" : ", className="text-muted mx-2"),
                            *accum_items
                        ], className="p-2 rounded alert-box-success d-flex flex-wrap align-items-center")
                    ], width=12, lg=6, className="mb-2 mb-lg-0"),
                    # New Distribution Warning
                    dbc.Col([
                        html.Div([
                            html.Span([
                                html.I(className="fas fa-arrow-down text-danger me-1"),
                                html.Span("New Distribution", className="text-danger fw-bold")
                            ]),
                            html.Span(" : ", className="text-muted mx-2"),
                            *dist_items
                        ], className="p-2 rounded alert-box-danger d-flex flex-wrap align-items-center")
                    ], width=12, lg=6),
                ], className="mb-3"),

                # Biggest Movement Table - dengan warna broker berdasarkan tipe
                html.Small("Biggest Movement Today vs Yesterday", className="text-muted fw-bold mb-2 d-block"),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Broker", className="table-header"),
                        html.Th("Tipe", className="table-header"),
                        html.Th("Today", className="table-header"),
                        html.Th("Yest", className="table-header"),
                        html.Th("Change", className="table-header"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(colored_broker(m['broker'], with_badge=True), className="table-cell"),
                            html.Td(html.Span(m['type'][:6], className=f"broker-{get_broker_type(m['broker']).lower()}"), className="table-cell"),
                            html.Td(f"{m['today']/1e9:+.1f}B", className="table-cell"),
                            html.Td(f"{m['yesterday']/1e9:+.1f}B", className="table-cell"),
                            html.Td(html.Span(f"{m['change']/1e9:+.1f}B", className="text-success" if m['change'] > 0 else "text-danger"), className="table-cell"),
                        ]) for m in top_movements
                    ])
                ], className="table table-sm", style={'width': '100%'}),

                html.Hr(className="my-2"),

                # Penjelasan Section
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Cara Baca: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("• New Accumulation: "), "Broker yang kemarin jual/netral, HARI INI mulai beli besar (>1B). ",
                        html.Span("Sinyal awal bullish!", className="text-success"),
                        html.Br(),
                        html.Strong("• New Distribution: "), "Broker yang kemarin beli/netral, HARI INI mulai jual besar. ",
                        html.Span("Sinyal awal bearish!", className="text-danger"),
                        html.Br(),
                        html.Strong("• Biggest Movement: "), "Broker dengan perubahan TERBESAR dari kemarin ke hari ini.",
                        html.Br(),
                        html.Strong("• Today vs Yest: "), "Bandingkan net hari ini vs kemarin untuk lihat perubahan perilaku",
                        html.Br(),
                        html.Strong("💡 Tip: "), "Perhatikan jika broker asing/sensitif muncul di New Accumulation!"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box")
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("🔔 Broker Movement"),
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
                dbc.CardHeader("🎯 Top 5 Broker Sensitivity Pattern"),
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
                html.Small(" - Pola akumulasi sampai harga naik ≥10%", className="text-muted ms-2")
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
                            html.Td('🟢 ACCUM' if b['status']=='ACCUM' else '🔴 DIST' if b['status']=='DIST' else '⚪ NEUTRAL', className="table-cell"),
                            html.Td(f"{b['streak']}d" if b['streak'] > 0 else "-", className="table-cell"),
                            html.Td(f"{b['today_net']/1e9:+.1f}B", className="table-cell"),
                            html.Td(f"{b['total_lot']/1e6:.1f}M" if b['total_lot'] > 0 else "-", className="table-cell"),
                        ]) for b in broker_status
                    ])
                ], className="table table-sm", style={'width': '100%'}),

                # Insight box
                html.Div([
                    html.Small("💡 Insight: ", className="fw-bold"),
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
                        html.Strong("• Win%: "), "Persentase kejadian broker ini akumulasi → harga naik ≥10% dalam 10 hari. ",
                        html.Span("Makin tinggi makin bagus!", className="text-success"),
                        html.Br(),
                        html.Strong("• Lead: "), "Rata-rata berapa hari SEBELUM harga naik, broker ini mulai akumulasi. ",
                        "Lead 3d = beli 3 hari sebelum harga naik",
                        html.Br(),
                        html.Strong("• Sigs: "), "Jumlah sinyal berhasil (akumulasi → harga naik ≥10%)",
                        html.Br(),
                        html.Strong("• Avg Buy: "), "Harga rata-rata pembelian broker ini (60 hari)",
                        html.Br(), html.Br(),
                        html.Strong("TABEL CURRENT STATUS:"),
                        html.Br(),
                        html.Strong("• Status: "), "ACCUM = sedang akumulasi ≥2 hari, DIST = sedang distribusi, NEUTRAL = tidak ada pola",
                        html.Br(),
                        html.Strong("• Streak: "), "Berapa hari berturut-turut akumulasi",
                        html.Br(),
                        html.Strong("• Tot Lot: "), "Total lot yang dibeli selama streak",
                        html.Br(), html.Br(),
                        html.Strong("💡 Strategi: "), "Jika broker dengan Win% tinggi dan Lead Time pendek mulai akumulasi, ",
                        html.Span("pertimbangkan untuk ikut beli!", className="text-warning")
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box")
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("🎯 Broker Sensitivity Pattern"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


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
                dbc.CardHeader("👁️ Broker Watchlist"),
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
                            html.Small("🔥 Accumulation Streak", className="text-success fw-bold mb-2 d-block"),
                            *accum_items
                        ], className="p-2 rounded h-100 alert-box-success")
                    ], xs=12, md=4, className="mb-2 mb-md-0"),

                    # Distribution Warning
                    dbc.Col([
                        html.Div([
                            html.Small("⚠️ Distribution Warning", className="text-danger fw-bold mb-2 d-block"),
                            *dist_items
                        ], className="p-2 rounded h-100 alert-box-danger")
                    ], xs=12, md=4, className="mb-2 mb-md-0"),

                    # Floating Loss
                    dbc.Col([
                        html.Div([
                            html.Small("💸 Floating Loss", className="text-warning fw-bold mb-2 d-block"),
                            *float_items
                        ], className="p-2 rounded h-100 alert-box-warning")
                    ], xs=12, md=4),
                ]),

                html.Hr(className="my-2"),

                # Penjelasan Section
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Cara Baca: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("🔥 ACCUMULATION STREAK:"),
                        html.Br(),
                        "Broker yang BELI berturut-turut ≥2 hari. Badge menunjukkan jumlah hari streak.",
                        html.Br(),
                        html.Span("Streak panjang + Net besar = broker punya conviction kuat. Ikuti mereka!", className="text-success"),
                        html.Br(), html.Br(),
                        html.Strong("⚠️ DISTRIBUTION WARNING:"),
                        html.Br(),
                        "Broker yang JUAL berturut-turut ≥2 hari. ",
                        html.Span("Hati-hati jika broker besar/sensitif muncul di sini!", className="text-danger"),
                        html.Br(), html.Br(),
                        html.Strong("💸 FLOATING LOSS:"),
                        html.Br(),
                        "Broker yang Avg Buy-nya >5% di atas harga sekarang (floating rugi).",
                        html.Br(),
                        "Implikasi: Mungkin mereka akan DEFEND di level Avg Buy atau CUT LOSS.",
                        html.Br(),
                        "• Defend = support sementara di Avg Buy mereka",
                        html.Br(),
                        "• Cut Loss = tekanan jual tambahan",
                        html.Br(), html.Br(),
                        html.Strong("💡 Strategi: "),
                        html.Br(),
                        "• Ikuti broker dengan Accum Streak panjang",
                        html.Br(),
                        "• Hindari/jual jika banyak Dist Warning dari broker besar",
                        html.Br(),
                        "• Perhatikan level Avg Buy broker Float Loss sebagai potensi support/resistance"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box")
            ])
        ], className="mb-3")
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("👁️ Broker Watchlist"),
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
    result = execute_query(query, (stock_code,))
    if result and len(result) > 0:
        row = result[0]
        # Parse directors/commissioners - could be string or already parsed
        directors = row['directors']
        if isinstance(directors, str):
            directors = json.loads(directors) if directors else []
        commissioners = row['commissioners']
        if isinstance(commissioners, str):
            commissioners = json.loads(commissioners) if commissioners else []
        shareholder_history = row['shareholder_history']
        if isinstance(shareholder_history, str):
            shareholder_history = json.loads(shareholder_history) if shareholder_history else []

        return {
            'stock_code': row['stock_code'],
            'company_name': row['company_name'],
            'listing_board': row['listing_board'],
            'sector': row['sector'],
            'subsector': row['subsector'],
            'industry': row['industry'],
            'business_activity': row['business_activity'],
            'listing_date': row['listing_date'],
            'effective_date': row['effective_date'],
            'nominal_value': float(row['nominal_value']) if row['nominal_value'] else None,
            'ipo_price': float(row['ipo_price']) if row['ipo_price'] else None,
            'ipo_shares': row['ipo_shares'],
            'ipo_amount': float(row['ipo_amount']) if row['ipo_amount'] else None,
            'underwriter': row['underwriter'],
            'share_registrar': row['share_registrar'],
            'company_background': row['company_background'],
            'major_shareholder': row['major_shareholder'],
            'major_shareholder_pct': float(row['major_shareholder_pct']) if row['major_shareholder_pct'] else 0,
            'public_pct': float(row['public_pct']) if row['public_pct'] else 0,
            'total_shares': row['total_shares'],
            'president_director': row['president_director'],
            'president_commissioner': row['president_commissioner'],
            'directors': directors,
            'commissioners': commissioners,
            'shareholder_history': shareholder_history,
        }
    return {}


# ============================================================
# PAGE: ACCUMULATION (New Sub-menu from Analysis)
# ============================================================

def create_accumulation_page(stock_code='CDIA'):
    """Create Accumulation analysis page - Active Alerts, Accumulation Phase, Broker Sensitivity & Volume Analysis"""
    try:
        # Get required data
        composite = get_comprehensive_analysis(stock_code)
        alerts = generate_alerts(stock_code)
        accum_phase = composite.get('accumulation_phase', {})
        broker_sens = calculate_broker_sensitivity_advanced(stock_code)
        foreign_flow = composite.get('foreign_flow', {})
        price_pos = composite.get('price_position', {})
        volume_analysis = composite.get('volume_analysis', {})

        # Score color helper
        def score_color(score):
            if score >= 70: return 'success'
            if score >= 50: return 'info'
            if score >= 30: return 'warning'
            return 'danger'

    except Exception as e:
        return html.Div([
            dbc.Alert(f"Error loading Accumulation analysis for {stock_code}: {str(e)}", color="danger"),
            html.P("Pastikan data sudah diupload dengan benar")
        ])

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-cubes me-2"),
                f"Accumulation Analysis - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_submenu_nav('accumulation', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # ========== ACTIVE ALERTS ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5("Active Alerts", className="mb-0 d-inline"),
                dbc.Badge(f"{len(alerts)}", color="warning" if alerts else "secondary", className="ms-2")
            ]),
            dbc.CardBody([
                create_enhanced_alerts_list(alerts) if alerts else dbc.Alert("Tidak ada alert aktif", color="secondary")
            ])
        ], className="mb-4"),

        # ========== NEW SIGNAL VALIDATION CARD (15 Elements) ==========
        create_validation_card(stock_code),

    ])


def create_company_profile_page(stock_code='CDIA'):
    """Create Company Profile page with attractive, colorful design"""
    profile = get_stock_profile(stock_code)

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
                            html.Div([
                                html.Small(d.get('position', ''), className="text-muted", style={'fontSize': '0.75rem'}),
                                html.P(d.get('name', ''), className="mb-2 fw-bold", style={'fontSize': '0.9rem'})
                            ], className="mb-1")
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
                            html.Div([
                                html.Small(c.get('position', ''), className="text-muted", style={'fontSize': '0.75rem'}),
                                html.P(c.get('name', ''), className="mb-2 fw-bold", style={'fontSize': '0.9rem'})
                            ], className="mb-1")
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
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # Broker Movement Alert Container
        html.Div(id="movement-alert-container", children=create_broker_movement_alert(stock_code)),

        # Broker Watchlist Container
        html.Div(id="movement-watchlist-container", children=create_broker_watchlist(stock_code)),

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
            status_icon = "🟢"
        elif negative_days > positive_days and total_net < 0:
            status = "DISTRIBUSI"
            status_color = "text-danger"
            status_icon = "🔴"
        else:
            status = "NETRAL"
            status_color = "text-warning"
            status_icon = "🟡"

        # Progress indicator - how far into accumulation pattern
        if streak >= accum_window:
            progress = "✅ READY"
            progress_color = "text-success fw-bold"
        elif streak >= accum_window * 0.5:
            progress = f"⏳ {streak}/{accum_window}d"
            progress_color = "text-info"
        elif streak > 0:
            progress = f"🔄 {streak}/{accum_window}d"
            progress_color = "text-muted"
        else:
            progress = "⏸️ -"
            progress_color = "text-muted"

        # Day detail (show last N days activity)
        day_indicators = []
        recent_days = period_df_sorted.head(min(accum_window, 5))  # Show up to 5 days
        for i, (_, row) in enumerate(recent_days.iterrows()):
            day_label = f"D{i+1}"
            if row['net_value'] > 0:
                day_indicators.append(html.Span(f"✓", className="text-success me-1", style={"fontSize": "11px"}, title=f"{day_label}: +{row['net_value']/1e9:.1f}B"))
            else:
                day_indicators.append(html.Span(f"✗", className="text-danger me-1", style={"fontSize": "11px"}, title=f"{day_label}: {row['net_value']/1e9:.1f}B"))

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

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-crosshairs me-2"),
                f"Sensitive Broker - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_dashboard_submenu_nav('sensitive', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # Broker Sensitivity Pattern Container
        html.Div(id="sensitive-pattern-container", children=create_broker_sensitivity_pattern(stock_code)),

        # Summary Card - Accumulation/Distribution/Neutral
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-balance-scale me-2"),
                html.Span("📈 Summary Status Broker Sensitif", className="fw-bold"),
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
                        html.Strong("• Window: "), "Jumlah hari akumulasi rata-rata broker sebelum harga naik ≥10% (dari data historis)",
                        html.Br(),
                        html.Strong("• Win%: "), "Persentase keberhasilan sinyal akumulasi broker ini",
                        html.Br(),
                        html.Strong("• Hari Terakhir: "), "✓ = net buy, ✗ = net sell (D1=hari ini, D2=kemarin, dst)",
                        html.Br(),
                        html.Strong("• Progress: "), "✅ READY = akumulasi sudah cukup, ⏳ = sedang proses, 🔄 = baru mulai",
                        html.Br(),
                        html.Strong("💡 Signal: "), "Broker dengan status AKUMULASI dan Progress READY = potensi harga naik dalam beberapa hari!"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded info-box mt-2")
            ])
        ], className="mb-3"),

        # Broker Activity Over Time Periods
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-line me-2"),
                html.Span("📊 Aktivitas Top 5 Broker Sensitif", className="fw-bold"),
                html.Small(" - Perbandingan periode waktu", className="text-muted ms-2")
            ]),
            dbc.CardBody([
                dbc.Row([
                    # 1 Week
                    dbc.Col([
                        html.Div([
                            html.H6("📅 1 Minggu Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-1week", children=create_broker_activity_table(stock_code, top_5_codes, 7))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),

                    # 2 Weeks
                    dbc.Col([
                        html.Div([
                            html.H6("📅 2 Minggu Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-2weeks", children=create_broker_activity_table(stock_code, top_5_codes, 14))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),

                    # 3 Weeks
                    dbc.Col([
                        html.Div([
                            html.H6("📅 3 Minggu Terakhir", className="text-info fw-bold mb-2"),
                            html.Div(id="activity-3weeks", children=create_broker_activity_table(stock_code, top_5_codes, 21))
                        ], className="p-2 rounded metric-box")
                    ], md=6, lg=3, className="mb-3"),

                    # 1 Month
                    dbc.Col([
                        html.Div([
                            html.H6("📅 1 Bulan Terakhir", className="text-info fw-bold mb-2"),
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
                        html.Strong("• Action: "), "BUY = net positif (lebih banyak beli), SELL = net negatif",
                        html.Br(),
                        html.Strong("• Net Val: "), "Total nilai bersih (beli - jual) dalam miliar rupiah",
                        html.Br(),
                        html.Strong("• Net Lot: "), "Total lot bersih dalam juta lot",
                        html.Br(),
                        html.Strong("💡 Tip: "), "Bandingkan aktivitas antar periode. Jika broker konsisten BUY di semua periode, kemungkinan sedang akumulasi besar!"
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
    result = execute_query(query, (stock_code,))
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
        insight_text = f"⚡ {stock_code} IMPULSE BREAKOUT ({imp_strength})! Volume {vol_ratio:.1f}x rata-rata. Momentum tinggi, risiko tinggi."
        insight_color = "danger"
    elif impulse_signal.get('near_impulse'):
        conds_met = impulse_signal.get('trigger_conditions', {}).get('conditions_met', 0)
        insight_text = f"👁️ {stock_code} hampir memenuhi kriteria impulse ({conds_met}/3). Pantau volume dan breakout."
        insight_color = "info"
    elif overall_signal == 'AKUMULASI' and conf_level in ['HIGH', 'VERY_HIGH']:
        insight_text = f"🟢 {stock_code} menunjukkan pola akumulasi kuat ({pass_rate:.0f}% validasi lolos). Perhatikan zona entry."
        insight_color = "success"
    elif overall_signal == 'AKUMULASI':
        insight_text = f"🟡 {stock_code} menunjukkan sinyal akumulasi awal. Pantau konsistensi broker flow."
        insight_color = "info"
    elif overall_signal == 'DISTRIBUSI' and conf_level in ['HIGH', 'VERY_HIGH']:
        insight_text = f"🔴 {stock_code} dalam fase distribusi kuat ({pass_rate:.0f}% validasi). Hati-hati posisi beli baru."
        insight_color = "danger"
    elif overall_signal == 'DISTRIBUSI':
        insight_text = f"🟠 {stock_code} menunjukkan sinyal distribusi. Pertimbangkan pengurangan posisi."
        insight_color = "warning"
    else:
        insight_text = f"⏳ {stock_code} dalam fase netral. Tidak ada sinyal kuat - observasi dulu."
        insight_color = "secondary"

    # ========== BUILD THE PAGE ==========
    return html.Div([
        # === ONE-LINE INSIGHT BAR (TOP HEADLINE) ===
        dbc.Alert([
            html.Div([
                html.I(className="fas fa-lightbulb me-2 text-warning"),
                html.Strong("Quick Insight: ", className="me-1"),
                html.Span(insight_text),
            ], className="d-flex align-items-center flex-wrap")
        ], color=insight_color, className="mb-3 py-2", style={
            "borderLeft": f"4px solid var(--bs-{insight_color})",
            "backgroundColor": f"rgba(var(--bs-{insight_color}-rgb), 0.1)"
        }),

        # === PAGE HEADER WITH SUBMENU NAVIGATION ===
        html.Div([
            html.H4([
                html.I(className="fas fa-chart-pie me-2"),
                f"Analysis Dashboard - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            dcc.Link(dbc.Button([html.I(className="fas fa-chart-line me-2"), "Fundamental"], color="success", size="sm", className="me-2"), href="/fundamental"),
            dcc.Link(dbc.Button([html.I(className="fas fa-layer-group me-2"), "Support & Resistance"], color="info", size="sm", className="me-2"), href="/support-resistance"),
            dcc.Link(dbc.Button([html.I(className="fas fa-cubes me-2"), "Accumulation"], color="warning", size="sm"), href="/accumulation"),
        ], className="d-flex align-items-center flex-wrap mb-4"),

        # === 1. DECISION HERO CARD (PALING PENTING) ===
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Decision Icon & Action
                    dbc.Col([
                        html.Div([
                            html.Span(decision.get('icon', '⏳'), style={"fontSize": "80px"}),
                            html.H1(decision.get('action', 'WAIT'), className=f"text-{decision.get('color', 'secondary')} fw-bold mb-0"),
                            html.P(decision.get('description', ''), className="text-muted")
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
                            html.P(decision.get('reason', ''), className="mb-3"),
                        ]),

                        # Key Points & Warnings
                        dbc.Row([
                            dbc.Col([
                                html.H6([html.I(className="fas fa-check-circle text-success me-2"), "Key Points"], className="mb-2"),
                                html.Div([
                                    html.Div([
                                        html.Span(kp.get('icon', ''), className="me-2"),
                                        html.Span(kp.get('text', ''), className=f"text-{kp.get('color', 'muted')} small")
                                    ], className="mb-1") for kp in key_points[:4]
                                ]) if key_points else html.Small("Tidak ada key points", className="text-muted")
                            ], md=6),
                            dbc.Col([
                                html.H6([html.I(className="fas fa-exclamation-triangle text-warning me-2"), "Warnings"], className="mb-2"),
                                html.Div([
                                    html.Div([
                                        html.Span(w.get('icon', ''), className="me-2"),
                                        html.Span(w.get('text', ''), className=f"text-{w.get('color', 'muted')} small")
                                    ], className="mb-1") for w in warnings[:4]
                                ]) if warnings else html.Small("Tidak ada warning", className="text-muted")
                            ], md=6),
                        ])
                    ], md=9)
                ])
            ])
        ], className="mb-4", style={"border": f"3px solid var(--bs-{decision.get('color', 'secondary')})", "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"}),

        # === IMPULSE/MOMENTUM ALERT (tertinggi prioritas) ===
        dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("⚡", style={"fontSize": "32px"}),
                        html.Strong(f" MOMENTUM {impulse_signal.get('strength', '')} DETECTED", className="text-danger fs-5 ms-2"),
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
                        html.Small("Trigger Conditions", className="text-muted d-block"),
                        html.Div([
                            dbc.Badge("✓ Vol 2x" if impulse_signal.get('metrics', {}).get('is_volume_spike') else "○ Vol 2x",
                                      color="success" if impulse_signal.get('metrics', {}).get('is_volume_spike') else "secondary", className="me-1"),
                            dbc.Badge("✓ Breakout" if impulse_signal.get('metrics', {}).get('is_breakout') else "○ Breakout",
                                      color="success" if impulse_signal.get('metrics', {}).get('is_breakout') else "secondary", className="me-1"),
                            dbc.Badge(f"✓ CPR {impulse_signal.get('metrics', {}).get('today_cpr_pct', 0):.0f}%" if impulse_signal.get('metrics', {}).get('is_cpr_bullish') else f"○ CPR {impulse_signal.get('metrics', {}).get('today_cpr_pct', 0):.0f}%",
                                      color="success" if impulse_signal.get('metrics', {}).get('is_cpr_bullish') else "secondary"),
                        ])
                    ]),
                ], md=4, className="text-end"),
            ]),
        ], color="danger", className="mb-3", style={"backgroundColor": "rgba(220,53,69,0.15)", "border": "2px solid #dc3545"})
        if impulse_signal.get('impulse_detected') else html.Div(),

        # === NEAR IMPULSE ALERT (hampir impulse) ===
        dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("👁️", style={"fontSize": "28px"}),
                        html.Strong(f" HAMPIR IMPULSE ({impulse_signal.get('trigger_conditions', {}).get('conditions_met', 0)}/3 kondisi)", className="text-info fs-6 ms-2"),
                    ], className="d-flex align-items-center"),
                    html.P("Satu atau dua kondisi belum terpenuhi. Pantau volume dan price action besok.", className="mb-0 small"),
                ], md=12),
            ]),
        ], color="info", className="mb-3", style={"backgroundColor": "rgba(23,162,184,0.15)", "border": "1px solid #17a2b8"})
        if impulse_signal.get('near_impulse') and not impulse_signal.get('impulse_detected') else html.Div(),

        # === MARKUP TRIGGER ALERT (setelah akumulasi) ===
        dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("🔥", style={"fontSize": "28px"}),
                        html.Strong(" MARKUP TRIGGER DETECTED", className="text-warning fs-5 ms-2"),
                    ], className="d-flex align-items-center"),
                    html.P([
                        "Harga breakout ", html.Strong(f"+{markup_trigger.get('breakout_pct', 0):.1f}%"),
                        " dari resistance terdekat setelah akumulasi terdeteksi sebelumnya."
                    ], className="mb-0 small"),
                ], md=9),
                dbc.Col([
                    html.Div([
                        html.Small("Volume Spike", className="text-muted d-block"),
                        dbc.Badge(f"+{markup_trigger.get('volume_spike_pct', 0):.0f}%" if markup_trigger.get('volume_spike') else "Normal",
                                  color="success" if markup_trigger.get('volume_spike') else "secondary"),
                    ]),
                ], md=3, className="text-end"),
            ]),
        ], color="warning", className="mb-3", style={"backgroundColor": "rgba(255,193,7,0.15)", "border": "2px solid #ffc107"})
        if markup_trigger.get('markup_triggered') and not impulse_signal.get('impulse_detected') else html.Div(),

        # === EDUCATIONAL CARD - "Apa Artinya Ini?" ===
        dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-graduation-cap me-2 text-info"),
                    html.Strong("Apa Artinya Ini?", className="text-info"),
                ], className="d-flex align-items-center")
            ], className="bg-transparent border-info"),
            dbc.CardBody([
                # Dynamic educational content based on signal type
                html.Div([
                    # For Impulse/Momentum signal
                    html.Div([
                        html.P([
                            html.Strong("⚡ Sinyal Momentum/Impulse", className="text-danger d-block mb-2"),
                            html.Span(impulse_signal.get('educational', 'Tidak ada data'), className="text-light"),
                        ], className="mb-3"),
                        html.Div([
                            html.Small("Perbedaan dengan Akumulasi:", className="text-warning d-block mb-2"),
                            dbc.Row([
                                dbc.Col([
                                    html.Div([
                                        html.Small("📊 Akumulasi", className="text-success d-block"),
                                        html.Small("• Lambat, tersembunyi", className="text-muted d-block"),
                                        html.Small("• Volume stabil", className="text-muted d-block"),
                                        html.Small("• CPR rendah/sedang", className="text-muted d-block"),
                                        html.Small("• Risiko lebih rendah", className="text-muted d-block"),
                                    ])
                                ], width=6),
                                dbc.Col([
                                    html.Div([
                                        html.Small("⚡ Momentum", className="text-danger d-block"),
                                        html.Small("• Cepat, agresif", className="text-muted d-block"),
                                        html.Small("• Volume spike >2x", className="text-muted d-block"),
                                        html.Small("• CPR tinggi >55%", className="text-muted d-block"),
                                        html.Small("• Risiko tinggi", className="text-muted d-block"),
                                    ])
                                ], width=6),
                            ])
                        ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),
                    ]) if impulse_signal.get('impulse_detected') or impulse_signal.get('near_impulse') else html.Div(),

                    # For Markup Trigger signal
                    html.Div([
                        html.P([
                            html.Strong("🔥 Sinyal Markup Trigger", className="text-warning d-block mb-2"),
                            "Harga mulai bergerak naik setelah periode akumulasi. ",
                            "Ini adalah transisi dari fase pengumpulan ke fase markup. ",
                            "Volume dan momentum mendukung pergerakan ini."
                        ], className="mb-2"),
                        html.Small([
                            html.I(className="fas fa-lightbulb me-1 text-warning"),
                            "Tips: Jangan kejar harga yang sudah breakout. Tunggu pullback ke zona entry atau kelola posisi yang sudah ada."
                        ], className="text-muted")
                    ]) if markup_trigger.get('markup_triggered') and not impulse_signal.get('impulse_detected') and not impulse_signal.get('near_impulse') else html.Div(),

                    # For Accumulation signal
                    html.Div([
                        html.P([
                            html.Strong("📊 Sinyal Akumulasi", className="text-success d-block mb-2"),
                            summary.get('what_means', 'Ada pihak yang mengumpulkan saham secara bertahap. Pola ini biasanya muncul sebelum kenaikan, namun timing tidak bisa diprediksi.')
                        ], className="mb-2"),
                        html.Small([
                            html.I(className="fas fa-lightbulb me-1 text-warning"),
                            "Tips: Masuk bertahap di zona entry. Jangan all-in. Siapkan stop loss di bawah invalidation level."
                        ], className="text-muted")
                    ]) if overall_signal == 'AKUMULASI' and not impulse_signal.get('impulse_detected') and not impulse_signal.get('near_impulse') and not markup_trigger.get('markup_triggered') else html.Div(),

                    # For Distribution signal
                    html.Div([
                        html.P([
                            html.Strong("🔴 Sinyal Distribusi", className="text-danger d-block mb-2"),
                            "Terdeteksi penjualan bertahap oleh pelaku besar. ",
                            "Berhati-hati dengan posisi beli baru."
                        ], className="mb-2"),
                        html.Small([
                            html.I(className="fas fa-exclamation-triangle me-1 text-danger"),
                            "Warning: Hindari entry baru. Jika sudah punya posisi, pertimbangkan untuk mengurangi atau memasang stop loss ketat."
                        ], className="text-muted")
                    ]) if overall_signal == 'DISTRIBUSI' and not impulse_signal.get('impulse_detected') and not impulse_signal.get('near_impulse') else html.Div(),

                    # For Neutral signal
                    html.Div([
                        html.P([
                            html.Strong("⏳ Kondisi Netral", className="text-secondary d-block mb-2"),
                            "Pola belum terbentuk jelas. Tidak ada sinyal kuat dari akumulasi maupun distribusi. ",
                            "Pantau perkembangan untuk konfirmasi arah selanjutnya."
                        ], className="mb-2"),
                        html.Small([
                            html.I(className="fas fa-clock me-1 text-info"),
                            "Tips: Sabar menunggu sinyal yang lebih jelas. Pasar tidak selalu memberikan peluang setiap saat."
                        ], className="text-muted")
                    ]) if overall_signal == 'NETRAL' and not impulse_signal.get('impulse_detected') and not impulse_signal.get('near_impulse') and not markup_trigger.get('markup_triggered') else html.Div(),
                ])
            ], className="py-2")
        ], color="dark", outline=True, className="mb-4", style={"borderColor": "var(--bs-info)"}),

        # === 2. QUICK SUMMARY FROM 3 SUBMENUS (Cards) ===
        dbc.Row([
            # FUNDAMENTAL CARD
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-chart-line me-2 text-success"), "Fundamental"], className="mb-0 d-inline"),
                        dcc.Link(html.Small("Detail →", className="float-end text-info"), href="/fundamental")
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

            # SUPPORT & RESISTANCE CARD
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-layer-group me-2 text-info"), "Support & Resistance"], className="mb-0 d-inline"),
                        dcc.Link(html.Small("Detail →", className="float-end text-info"), href="/support-resistance")
                    ]),
                    dbc.CardBody([
                        # Price Level Gauge
                        html.Div([
                            # Visual gauge
                            html.Div([
                                html.Div([
                                    html.Span(f"Rp {sr.get('support_20d', 0):,.0f}", className="small text-success"),
                                    html.Span(" Support", className="small text-muted", style={'cursor': 'help'}, title=TERM_DEFINITIONS['support'])
                                ], className="text-start", style={"width": "33%"}),
                                html.Div([
                                    html.Span(f"Rp {current_price:,.0f}", className="small text-warning fw-bold"),
                                ], className="text-center", style={"width": "34%"}),
                                html.Div([
                                    html.Span("Resistance ", className="small text-muted", style={'cursor': 'help'}, title=TERM_DEFINITIONS['resistance']),
                                    html.Span(f"Rp {sr.get('resistance_20d', 0):,.0f}", className="small text-danger")
                                ], className="text-end", style={"width": "33%"}),
                            ], className="d-flex justify-content-between mb-1") if sr.get('has_data') else None,

                            # Progress bar showing position
                            html.Div([
                                dbc.Progress([
                                    dbc.Progress(value=min(100, max(0, sr.get('dist_from_support', 50))), color="success", bar=True),
                                ], style={"height": "8px"})
                            ], className="mb-2") if sr.get('has_data') else None,

                            html.Div([
                                html.Small(f"Jarak ke Support: {sr.get('dist_from_support', 0):.1f}%", className="text-muted me-3"),
                                html.Small(f"Jarak ke Resistance: {sr.get('dist_from_resistance', 0):.1f}%", className="text-muted"),
                            ], className="text-center") if sr.get('has_data') else html.Small("Data tidak tersedia", className="text-muted"),
                        ]),
                        html.Hr(className="my-2"),
                        html.Div([
                            html.Small("Posisi: ", className="text-muted"),
                            dbc.Badge(
                                "Dekat Support" if sr.get('position') == 'NEAR_SUPPORT' else "Dekat Resistance" if sr.get('position') == 'NEAR_RESISTANCE' else "Di Tengah",
                                color="success" if sr.get('position') == 'NEAR_SUPPORT' else "danger" if sr.get('position') == 'NEAR_RESISTANCE' else "secondary"
                            )
                        ], className="text-center")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], md=4),

            # ACCUMULATION CARD
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([
                            html.I(className="fas fa-cubes me-2 text-warning"),
                            html.Span("Accumulation", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS['accumulation'])
                        ], className="mb-0 d-inline"),
                        dcc.Link(html.Small("Detail →", className="float-end text-info"), href="/accumulation")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("Sinyal", className="text-muted d-block"),
                                    dbc.Badge(
                                        summary.get('overall_signal', 'NETRAL'),
                                        color="success" if summary.get('overall_signal') == 'AKUMULASI' else "danger" if summary.get('overall_signal') == 'DISTRIBUSI' else "secondary",
                                        title=TERM_DEFINITIONS['accumulation'] if summary.get('overall_signal') == 'AKUMULASI' else TERM_DEFINITIONS['distribution'] if summary.get('overall_signal') == 'DISTRIBUSI' else '',
                                        style={'cursor': 'help'}
                                    ),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small([
                                        html.Span("Validasi", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS['confidence']),
                                        html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                                    ], className="text-muted d-block"),
                                    html.H4(f"{confidence.get('passed', 0)}/6", className=f"mb-0 text-{'success' if confidence.get('pass_rate', 0) >= 60 else 'warning' if confidence.get('pass_rate', 0) >= 40 else 'danger'}"),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small([
                                        html.Span("CPR", style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'}, title=TERM_DEFINITIONS['cpr']),
                                        html.I(className="fas fa-info-circle ms-1", style={'fontSize': '8px', 'opacity': '0.6'})
                                    ], className="text-muted d-block"),
                                    html.H4(f"{validations.get('cpr', {}).get('avg_cpr', 0)*100:.0f}%", className="mb-0 text-info"),
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-2"),
                        html.Hr(className="my-2"),
                        html.Div([
                            html.Small([
                                html.Span("Confidence: ", style={'cursor': 'help'}, title=TERM_DEFINITIONS['confidence'])
                            ], className="text-muted"),
                            dbc.Badge(confidence.get('level', 'N/A'), color="success" if confidence.get('level') in ['HIGH', 'VERY_HIGH'] else "warning" if confidence.get('level') == 'MEDIUM' else "secondary")
                        ], className="text-center")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], md=4),
        ], className="mb-4"),

        # === 3. KEY PRICE LEVELS (Entry Zone, Support, Invalidation) ===
        dbc.Card([
            dbc.CardHeader([
                html.H5([html.I(className="fas fa-map-marker-alt me-2"), "Level Harga Kunci"], className="mb-0"),
            ]),
            dbc.CardBody([
                dbc.Row([
                    # Entry Zone
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.I(className="fas fa-sign-in-alt text-success me-2", style={"fontSize": "24px"}),
                                html.H6("ZONA ENTRY", className="text-success mb-0 d-inline"),
                            ], className="mb-2"),
                            html.H4([
                                f"Rp {unified.get('entry_zone', {}).get('low', 0):,.0f}",
                                html.Span(" - ", className="text-muted"),
                                f"Rp {unified.get('entry_zone', {}).get('high', 0):,.0f}"
                            ] if unified.get('entry_zone') else "N/A", className="text-success"),
                            html.Small("Area ideal untuk entry (lower 40% range)", className="text-muted")
                        ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(40,167,69,0.1)"})
                    ], md=4),

                    # Support Level
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.I(className="fas fa-shield-alt text-info me-2", style={"fontSize": "24px"}),
                                html.H6("SUPPORT", className="text-info mb-0 d-inline"),
                            ], className="mb-2"),
                            html.H4(f"Rp {unified.get('support_level', 0):,.0f}" if unified.get('support_level') else "N/A", className="text-info"),
                            html.Small("Level support terdekat (low 10 hari)", className="text-muted")
                        ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(23,162,184,0.1)"})
                    ], md=4),

                    # Invalidation
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.I(className="fas fa-exclamation-triangle text-danger me-2", style={"fontSize": "24px"}),
                                html.H6("INVALIDATION", className="text-danger mb-0 d-inline"),
                            ], className="mb-2"),
                            html.H4(f"Rp {unified.get('invalidation', 0):,.0f}" if unified.get('invalidation') else "N/A", className="text-danger"),
                            html.Small("Tutup posisi jika tembus level ini", className="text-muted")
                        ], className="text-center p-3 rounded", style={"backgroundColor": "rgba(220,53,69,0.1)"})
                    ], md=4),
                ])
            ])
        ], className="mb-4", color="dark", outline=True),

        # === 4. SIGNAL TIMELINE (dari Accumulation) ===
        dbc.Card([
            dbc.CardHeader([
                html.H5([html.I(className="fas fa-history me-2"), "Riwayat Sinyal (30 Hari Terakhir)"], className="mb-0"),
            ]),
            dbc.CardBody([
                html.Div([
                    html.Div([
                        html.Div([
                            html.Span(str(h.get('date', ''))[:10], className="fw-bold small", style={"width": "85px", "display": "inline-block"}),
                            dbc.Badge(
                                f"{h.get('signal', 'N/A')}" + (f" ({h.get('strength', '')})" if h.get('strength') else ""),
                                color="success" if h.get('signal') == 'ACCUMULATION' else "danger" if h.get('signal') == 'DISTRIBUTION' else "secondary",
                                className="me-2", style={"width": "140px", "textAlign": "center"}
                            ),
                            html.Span(f"Rp {h.get('price', 0):,.0f}", className="text-warning me-3 small", style={"width": "90px", "display": "inline-block"}),
                            html.Span(f"CPR: {h.get('cpr', 0):.0f}%", className="text-muted small me-2", style={"width": "70px", "display": "inline-block"}),
                            html.Span(f"Net: {h.get('net_lot', 0):+,.0f}", className=f"small text-{'success' if h.get('net_lot', 0) > 0 else 'danger' if h.get('net_lot', 0) < 0 else 'muted'}", style={"width": "100px", "display": "inline-block"}),
                        ], className="d-flex align-items-center py-1 px-2 rounded mb-1",
                           style={"backgroundColor": "rgba(40,167,69,0.1)" if h.get('signal') == 'ACCUMULATION' else "rgba(220,53,69,0.1)" if h.get('signal') == 'DISTRIBUTION' else "rgba(255,255,255,0.03)"})
                        for h in (detection.get('signal_history', []) if detection else [])[-10:]
                    ]) if detection and detection.get('signal_history') else html.Small("Tidak ada riwayat sinyal", className="text-muted"),
                ], style={"maxHeight": "200px", "overflowY": "auto"})
            ])
        ], className="mb-4", color="dark", outline=True),

        # === 5. VOLUME VS PRICE (Multi-Horizon Summary) ===
        dbc.Card([
            dbc.CardHeader([
                html.H5([html.I(className="fas fa-balance-scale me-2"), "Volume vs Price Analysis"], className="mb-0 d-inline"),
                dbc.Badge(
                    vol_price_multi.get('significance', 'NONE'),
                    color="success" if vol_price_multi.get('significance') == 'SIGNIFICANT' else
                          "info" if vol_price_multi.get('significance') == 'MODERATE' else
                          "warning" if vol_price_multi.get('significance') == 'EARLY' else "secondary",
                    className="ms-2"
                ),
            ]),
            dbc.CardBody([
                # Formula Explanation
                html.Div([
                    html.H6([html.I(className="fas fa-flask me-2"), "Formula Analisis:"], className="text-info mb-2"),
                    html.Div([
                        html.Code("ABSORPTION = (Volume↑ > 10%) AND (Price_Range < 8%)", className="d-block mb-1"),
                        html.Code("SIGNIFICANT = Core(5d) + Micro(1d) Absorption", className="d-block mb-1"),
                        html.Code("MODERATE = Core(5d) Absorption only", className="d-block mb-1"),
                        html.Code("EARLY = Micro(1d) Absorption only (belum terkonfirmasi)", className="d-block"),
                    ], className="p-2 rounded small", style={"backgroundColor": "rgba(255,255,255,0.05)", "fontFamily": "monospace"})
                ], className="mb-3"),

                # Horizon Summary Table
                html.Table([
                    html.Thead([
                        html.Tr([
                            html.Th("Horizon", className="text-center"),
                            html.Th("Vol Δ", className="text-center"),
                            html.Th("Price Δ", className="text-center"),
                            html.Th("Range", className="text-center"),
                            html.Th("Status", className="text-center"),
                        ])
                    ]),
                    html.Tbody([
                        html.Tr([
                            html.Td("1 Hari (Micro)", className="text-center"),
                            html.Td(f"{vol_price_multi.get('horizons', {}).get('1d', {}).get('volume_change_pct', 0):+.0f}%" if vol_price_multi.get('horizons', {}).get('1d') else "-",
                                   className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('1d', {}).get('volume_change_pct', 0) > 0 else 'danger'}"),
                            html.Td(f"{vol_price_multi.get('horizons', {}).get('1d', {}).get('price_change_pct', 0):+.1f}%" if vol_price_multi.get('horizons', {}).get('1d') else "-", className="text-center"),
                            html.Td(f"{vol_price_multi.get('horizons', {}).get('1d', {}).get('price_range_pct', 0):.1f}%" if vol_price_multi.get('horizons', {}).get('1d') else "-", className="text-center"),
                            html.Td(dbc.Badge("Absorption" if vol_price_multi.get('micro_absorption') else "-", color="success" if vol_price_multi.get('micro_absorption') else "secondary"), className="text-center"),
                        ]),
                        html.Tr([
                            html.Td(html.Strong("5 Hari (Core)", className="text-warning"), className="text-center"),
                            html.Td(html.Strong(f"{vol_price_multi.get('horizons', {}).get('5d', {}).get('volume_change_pct', 0):+.0f}%" if vol_price_multi.get('horizons', {}).get('5d') else "-"),
                                   className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('5d', {}).get('volume_change_pct', 0) > 0 else 'danger'}"),
                            html.Td(html.Strong(f"{vol_price_multi.get('horizons', {}).get('5d', {}).get('price_change_pct', 0):+.1f}%" if vol_price_multi.get('horizons', {}).get('5d') else "-"), className="text-center"),
                            html.Td(html.Strong(f"{vol_price_multi.get('horizons', {}).get('5d', {}).get('price_range_pct', 0):.1f}%" if vol_price_multi.get('horizons', {}).get('5d') else "-"), className="text-center"),
                            html.Td(dbc.Badge("Absorption" if vol_price_multi.get('core_absorption') else "-", color="success" if vol_price_multi.get('core_absorption') else "secondary"), className="text-center"),
                        ], style={"backgroundColor": "rgba(255,193,7,0.1)"}),
                        html.Tr([
                            html.Td("10 Hari (Structural)", className="text-center"),
                            html.Td(f"{vol_price_multi.get('horizons', {}).get('10d', {}).get('volume_change_pct', 0):+.0f}%" if vol_price_multi.get('horizons', {}).get('10d') else "-",
                                   className=f"text-center text-{'success' if vol_price_multi.get('horizons', {}).get('10d', {}).get('volume_change_pct', 0) > 0 else 'danger'}"),
                            html.Td(f"{vol_price_multi.get('horizons', {}).get('10d', {}).get('price_change_pct', 0):+.1f}%" if vol_price_multi.get('horizons', {}).get('10d') else "-", className="text-center"),
                            html.Td(f"{vol_price_multi.get('horizons', {}).get('10d', {}).get('price_range_pct', 0):.1f}%" if vol_price_multi.get('horizons', {}).get('10d') else "-", className="text-center"),
                            html.Td(dbc.Badge("Absorption" if vol_price_multi.get('structural_absorption') else "-", color="success" if vol_price_multi.get('structural_absorption') else "secondary"), className="text-center"),
                        ]),
                    ])
                ], className="table table-sm table-dark mb-3", style={"fontSize": "12px"}),

                # Conclusion
                html.Div([
                    html.Strong([html.I(className="fas fa-clipboard-check me-2"), "Kesimpulan: "], className="text-info"),
                    html.Span(
                        vol_price_multi.get('conclusion', 'Data tidak tersedia'),
                        className="fw-bold " + (
                            "text-success" if vol_price_multi.get('significance') in ['SIGNIFICANT', 'MODERATE'] else
                            "text-warning" if vol_price_multi.get('significance') == 'EARLY' else
                            "text-muted"
                        )
                    )
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),

                # Explanation
                html.Hr(className="my-3"),
                html.Small([
                    html.I(className="fas fa-info-circle me-1"),
                    "Volume dinilai signifikan jika peningkatan bertahan minimal 3-5 hari tanpa pelebaran range harga. ",
                    "Lonjakan volume 1 hari belum tentu akumulasi - sistem mencari konsistensi."
                ], className="text-muted fst-italic")
            ])
        ], className="mb-4", color="dark", outline=True),

        # === 6. DECISION GUIDE (Panduan Keputusan) ===
        dbc.Card([
            dbc.CardHeader([
                html.H5([html.I(className="fas fa-compass me-2"), "Panduan Keputusan Trading"], className="mb-0"),
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.H6([html.Span("⏳", className="me-2"), "WAIT"], className="text-secondary"),
                            html.P("Pasar belum jelas, observasi dulu. Validasi <4/6, range >20%, atau CPR netral.", className="small text-muted mb-0")
                        ], className="p-2 rounded mb-2", style={"backgroundColor": "rgba(108,117,125,0.1)"})
                    ], md=6),
                    dbc.Col([
                        html.Div([
                            html.H6([html.Span("🟢", className="me-2"), "ENTRY"], className="text-success"),
                            html.P("Akumulasi terdeteksi, masuk bertahap 30-50%. Harga di zona entry ideal.", className="small text-muted mb-0")
                        ], className="p-2 rounded mb-2", style={"backgroundColor": "rgba(40,167,69,0.1)"})
                    ], md=6),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.H6([html.Span("➕", className="me-2"), "ADD"], className="text-primary"),
                            html.P("Akumulasi terkonfirmasi kuat (≥5/6 validasi). Layak tambah posisi saat pullback.", className="small text-muted mb-0")
                        ], className="p-2 rounded mb-2", style={"backgroundColor": "rgba(0,123,255,0.1)"})
                    ], md=6),
                    dbc.Col([
                        html.Div([
                            html.H6([html.Span("✋", className="me-2"), "HOLD"], className="text-info"),
                            html.P("Markup sudah berjalan atau konsolidasi. Jangan kejar, kelola posisi yang ada.", className="small text-muted mb-0")
                        ], className="p-2 rounded mb-2", style={"backgroundColor": "rgba(23,162,184,0.1)"})
                    ], md=6),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.H6([html.Span("🚨", className="me-2"), "EXIT"], className="text-danger"),
                            html.P("Distribusi terdeteksi atau breakdown support. Pertimbangkan keluar/kurangi posisi.", className="small text-muted mb-0")
                        ], className="p-2 rounded", style={"backgroundColor": "rgba(220,53,69,0.1)"})
                    ], md=12),
                ]),
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

def create_one_line_insight(stock_code: str) -> html.Div:
    """
    Generate a one-line insight bar for quick market context.
    This appears at the top of dashboard for immediate understanding.
    """
    try:
        # Get unified analysis for insight
        unified = get_unified_analysis_summary(stock_code)
        accum = unified.get('accumulation', {})
        decision = unified.get('decision', {})
        sr = unified.get('support_resistance', {})

        summary = accum.get('summary', {})
        confidence = accum.get('confidence', {})
        overall_signal = summary.get('overall_signal', 'NETRAL')
        conf_level = confidence.get('level', 'LOW')
        pass_rate = confidence.get('pass_rate', 0)

        current_price = sr.get('current_price', 0)
        action = decision.get('action', 'WAIT')

        # Generate contextual insight
        if overall_signal == 'AKUMULASI' and conf_level in ['HIGH', 'VERY_HIGH']:
            insight = f"🟢 {stock_code} menunjukkan pola akumulasi kuat ({pass_rate:.0f}% validasi lolos). Perhatikan zona entry."
            color = "success"
            icon = "fas fa-arrow-trend-up"
        elif overall_signal == 'AKUMULASI':
            insight = f"🟡 {stock_code} menunjukkan sinyal akumulasi awal. Pantau konsistensi broker flow."
            color = "info"
            icon = "fas fa-chart-line"
        elif overall_signal == 'DISTRIBUSI' and conf_level in ['HIGH', 'VERY_HIGH']:
            insight = f"🔴 {stock_code} dalam fase distribusi kuat ({pass_rate:.0f}% validasi). Hati-hati posisi beli baru."
            color = "danger"
            icon = "fas fa-arrow-trend-down"
        elif overall_signal == 'DISTRIBUSI':
            insight = f"🟠 {stock_code} menunjukkan sinyal distribusi. Pertimbangkan pengurangan posisi."
            color = "warning"
            icon = "fas fa-exclamation-triangle"
        else:
            insight = f"⏳ {stock_code} dalam fase netral. Tidak ada sinyal kuat - observasi dulu."
            color = "secondary"
            icon = "fas fa-clock"

        # Add action hint
        action_hints = {
            'ENTRY': " → Peluang entry di zona support.",
            'ADD': " → Layak tambah posisi.",
            'HOLD': " → Tahan posisi yang ada.",
            'EXIT': " → Pertimbangkan profit taking.",
            'WAIT': " → Tunggu konfirmasi lebih lanjut."
        }
        insight += action_hints.get(action, "")

    except Exception as e:
        insight = f"📊 Sistem sedang menganalisis {stock_code}. Silakan tunggu..."
        color = "secondary"
        icon = "fas fa-spinner fa-spin"

    return html.Div([
        dbc.Alert([
            html.Div([
                html.I(className=f"{icon} me-2"),
                html.Strong("Insight: ", className="me-1"),
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
    except:
        unified_data = {}
        validation_result = {}

    return html.Div([
        # === ONE-LINE INSIGHT BAR (NEW) ===
        create_one_line_insight(stock_code),

        # === DECISION PANEL - "APA YANG HARUS DILAKUKAN HARI INI?" ===
        create_decision_panel(stock_code, unified_data),

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

        # Broker Detail
        dbc.Card([
            dbc.CardHeader([
                "Broker Detail - ",
                dcc.Dropdown(
                    id='broker-select',
                    options=[],
                    value=None,
                    style={'width': '150px', 'display': 'inline-block', 'color': 'black'},
                    clearable=False
                )
            ]),
            dbc.CardBody(id="broker-detail-container")
        ], className="mb-4"),
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
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty:
        return dbc.Alert(f"No price data for {stock_code}", color="warning")

    latest_price = price_df['close_price'].iloc[-1] if not price_df.empty else 0
    prev_price = price_df['close_price'].iloc[-2] if len(price_df) > 1 else latest_price
    price_change = ((latest_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

    phase = find_current_market_phase(price_df)
    alerts = check_accumulation_alerts(broker_df, stock_code) if not broker_df.empty else []

    latest_date = broker_df['date'].max() if not broker_df.empty else None
    top_acc = get_top_accumulators(broker_df, latest_date, 1) if not broker_df.empty else pd.DataFrame()
    top_acc_name = top_acc['broker_code'].iloc[0] if not top_acc.empty else '-'
    top_acc_val = top_acc['net_value'].iloc[0] / 1e9 if not top_acc.empty else 0

    # Responsive card style: smaller font on mobile
    card_header_style = {"fontSize": "12px", "padding": "8px"}
    card_body_style = {"padding": "10px"}
    value_class = "h5 mb-1"  # Smaller than h3 for mobile-friendly
    subtitle_class = "small mb-0 text-muted"

    return dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader(f"{stock_code} Price", style=card_header_style),
            dbc.CardBody([
                html.Div(f"Rp {latest_price:,.0f}", className=value_class),
                html.P(f"{price_change:+.2f}%", className=f"{subtitle_class} text-{'success' if price_change >= 0 else 'danger'}")
            ], style=card_body_style)
        ], color="dark", outline=True), xs=6, md=3, className="mb-2"),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Market Phase", style=card_header_style),
            dbc.CardBody([
                html.Div(phase['phase'].upper(), className=value_class),
                html.P(f"Range: {phase['details'].get('range_percent', 0):.1f}%", className=subtitle_class)
            ], style=card_body_style)
        ], color="dark", outline=True), xs=6, md=3, className="mb-2"),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Top Accumulator", style=card_header_style),
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
        dbc.Col(dbc.Card([
            dbc.CardHeader("Active Alerts", style=card_header_style),
            dbc.CardBody([
                html.Div(f"{len(alerts)}", className=value_class),
                html.P("Accumulation signals", className=subtitle_class)
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

    return html.Div([
        # Page Header with submenu navigation
        html.Div([
            html.H4([
                html.I(className="fas fa-chart-pie me-2"),
                f"Position - {stock_code}"
            ], className="mb-0 d-inline-block me-3"),
            create_dashboard_submenu_nav('position', stock_code),
        ], className="d-flex align-items-center flex-wrap mb-2"),
        html.P(period_str, className="text-muted mb-4"),

        # Summary Cards
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Holders", className="text-muted mb-1"),
                        html.H3(f"{total_holders}", className="mb-0 text-info")
                    ])
                ], color="dark", outline=True)
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Net Position", className="text-muted mb-1"),
                        html.H3(f"{total_net_lot:,.0f} lot", className="mb-0 text-primary")
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
                        )
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
                        ], className="mb-0")
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
                            html.Small("(Broker floating profit - will defend)", className="text-muted d-block mb-2"),
                            *([html.Div([
                                html.Span(f"Rp {s['price']:,.0f}", className="fw-bold"),
                                html.Span(" - "),
                                colored_broker(s['broker'], with_badge=True),
                                html.Span(f" ({s['lot']:,.0f} lot)", className="small"),
                                html.Span(f" {s['pnl']:+.1f}%", className="text-success small ms-2"),
                            ], className="mb-1") for s in sr_levels.get('supports', [])] if sr_levels.get('supports') else [
                                html.Small("Tidak ada support dari cost basis", className="text-muted")
                            ]),
                        ]),

                        html.Hr(),
                        html.Small([
                            html.Strong("Cara Baca: "),
                            "Support = level harga di mana broker profit (akan defend). ",
                            "Resistance = level di mana broker loss (mungkin jual saat harga naik)."
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
                            html.Strong("Bar Hijau: "), "Broker yang sudah PROFIT (avg buy < harga sekarang) → ",
                            html.Span("SUPPORT", className="text-success fw-bold"),
                            " - mereka tidak akan jual rugi"
                        ]),
                        html.Li([
                            html.Strong("Bar Merah: "), "Broker yang masih LOSS (avg buy > harga sekarang) → ",
                            html.Span("RESISTANCE", className="text-danger fw-bold"),
                            " - mereka akan jual saat harga naik ke level avg buy untuk cut loss/BEP"
                        ]),
                    ], className="small mb-2"),
                    html.Div([
                        html.Strong("Insight: ", className="text-warning"),
                        "Semakin banyak bar hijau (profit) → saham punya support kuat. ",
                        "Semakin banyak bar merah (loss) → ada selling pressure/resistance di atas."
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
def create_app_layout():
    """Create app layout - dropdown uses persistence for session storage"""
    return html.Div([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='theme-store', storage_type='local', data='dark'),  # Persist theme
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

@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname'), Input('stock-selector', 'value')]
)
def display_page(pathname, selected_stock):
    """Main routing callback - triggers on URL change OR stock selection change"""
    # Get default stock if none selected
    if not selected_stock:
        stocks = get_available_stocks()
        selected_stock = stocks[0] if stocks else 'PANI'

    # Route to appropriate page
    if pathname == '/':
        return create_landing_page()
    elif pathname == '/dashboard':
        return create_dashboard_page(selected_stock)
    elif pathname == '/analysis':
        return create_analysis_page(selected_stock)
    elif pathname == '/bandarmology':
        return create_bandarmology_page(selected_stock)
    elif pathname == '/summary':
        return create_summary_page(selected_stock)
    elif pathname == '/position':
        return create_position_page(selected_stock)
    elif pathname == '/upload':
        return create_upload_page()
    elif pathname == '/movement':
        return create_broker_movement_page(selected_stock)
    elif pathname == '/sensitive':
        return create_sensitive_broker_page(selected_stock)
    elif pathname == '/profile':
        return create_company_profile_page(selected_stock)
    elif pathname == '/fundamental':
        return create_fundamental_page(selected_stock)
    elif pathname == '/support-resistance':
        return create_support_resistance_page(selected_stock)
    elif pathname == '/accumulation':
        return create_accumulation_page(selected_stock)
    else:
        return create_landing_page()

# Password validation callback for upload page
@app.callback(
    [Output('upload-password-gate', 'style'),
     Output('upload-form-container', 'style'),
     Output('upload-password-error', 'children')],
    [Input('upload-password-submit', 'n_clicks')],
    [State('upload-password-input', 'value')],
    prevent_initial_call=True
)
def validate_upload_password(n_clicks, password):
    if not n_clicks:
        return {'display': 'block'}, {'display': 'none'}, ""

    if password == UPLOAD_PASSWORD:
        # Password correct - show upload form, hide password gate
        return {'display': 'none'}, {'display': 'block'}, ""
    else:
        # Password incorrect
        return (
            {'display': 'block'},
            {'display': 'none'},
            dbc.Alert("Password salah! Silakan coba lagi.", color="danger", className="mt-2")
        )

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
        return html.Div("Select a broker")
    if not stock_code:
        stocks = get_available_stocks()
        stock_code = stocks[0] if stocks else 'PANI'
    return create_broker_history_chart(broker_code, stock_code)

# Movement page refresh callback
@app.callback(
    [Output("movement-alert-container", "children"),
     Output("movement-watchlist-container", "children"),
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
        f"Last refresh: {datetime.now().strftime('%H:%M:%S')}"
    )

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
    [Output('upload-status', 'children'), Output('available-stocks-list', 'children'), Output('import-log', 'children'), Output('stock-selector', 'options'), Output('stock-selector', 'value')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'), State('upload-stock-code', 'value'), State('stock-selector', 'value')],
    prevent_initial_call=True
)
def handle_upload(contents, filename, stock_code, current_stock):
    import tempfile
    import traceback

    stocks_list = create_stocks_list()

    # Get current stock options for dropdown
    def get_stock_options():
        stocks = get_available_stocks()
        return [{'label': s, 'value': s} for s in stocks]

    if contents is None:
        return html.Div(), stocks_list, html.Div("No imports yet", className="text-muted"), get_stock_options(), current_stock

    if not stock_code or len(stock_code) < 2:
        return dbc.Alert("Masukkan kode saham terlebih dahulu (min 2 karakter)", color="danger"), stocks_list, html.Div(), get_stock_options(), current_stock

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

        return status, create_stocks_list(), log, get_stock_options(), stock_code  # Set dropdown to newly uploaded stock

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
        ], color="danger"), stocks_list, html.Div(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}", className="text-danger"), get_stock_options(), current_stock


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
# RUN SERVER
# ============================================================

if __name__ == '__main__':
    print("Starting Stock Broker Analysis Dashboard...")
    print("Open http://localhost:8050 in your browser")
    app.run(debug=True, host='0.0.0.0', port=8050)
