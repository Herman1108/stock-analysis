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
    classify_brokers, BROKER_COLORS, BROKER_TYPE_NAMES
)
from parser import read_excel_data, import_price_data, import_broker_data

# Initialize Dash app with Font Awesome for help icons
FA_CSS = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, FA_CSS],
    suppress_callback_exceptions=True,
    compress=True,  # Enable response compression
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"http-equiv": "X-UA-Compatible", "content": "IE=edge"}
    ]
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
    """Get list of stocks available in database"""
    query = "SELECT DISTINCT stock_code FROM stock_daily ORDER BY stock_code"
    results = execute_query(query)
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
               SUM(sell_lot) as daily_sell_lot
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

        # Weighted average buy price
        total_buy_value = ipo_buy_value + daily_buy_value
        weighted_avg_buy = total_buy_value / total_buy_lot if total_buy_lot > 0 else ipo_avg_buy

        # Use IPO avg if weighted is unreasonable
        if weighted_avg_buy > ipo_avg_buy * 100 or weighted_avg_buy < 1:
            weighted_avg_buy = ipo_avg_buy

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
                daily_buy_value = float(daily_row['daily_buy_value']) if pd.notna(daily_row['daily_buy_value']) else 0
                net_lot = daily_buy_lot - daily_sell_lot
                weighted_avg_buy = daily_buy_value / daily_buy_lot if daily_buy_lot > 0 else 0

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
            dbc.NavbarBrand("Stock Broker Analysis", href="/", className="ms-2"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Home", href="/", id="nav-home")),
                dbc.NavItem(dbc.NavLink("Dashboard", href="/dashboard", id="nav-dashboard")),
                dbc.NavItem(dbc.NavLink("Analysis", href="/analysis", id="nav-analysis")),
                dbc.NavItem(dbc.NavLink("Broker Ranking", href="/ranking", id="nav-ranking")),
                dbc.NavItem(dbc.NavLink("Alerts", href="/alerts", id="nav-alerts")),
                dbc.NavItem(dbc.NavLink("Position", href="/position", id="nav-position")),
                dbc.NavItem(dbc.NavLink("Upload Data", href="/upload", id="nav-upload")),
            ], className="me-auto", navbar=True),
            # Stock Selector
            html.Div([
                html.Span("Emiten: ", className="text-light me-2"),
                dcc.Dropdown(
                    id='stock-selector',
                    options=[{'label': s, 'value': s} for s in stocks],
                    value=stocks[0] if stocks else 'CDIA',
                    style={'width': '120px', 'color': 'black'},
                    clearable=False
                )
            ], className="d-flex align-items-center")
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-4"
    )


# ============================================================
# PAGE: LANDING / HOME
# ============================================================

def create_landing_page():
    """Create landing page with stock selection and overview"""
    stocks = get_available_stocks()

    if not stocks:
        return html.Div([
            dbc.Alert("Tidak ada data saham. Silakan upload data terlebih dahulu.", color="warning"),
            dbc.Button("Upload Data", href="/upload", color="primary")
        ])

    # Build stock cards with summary
    stock_cards = []
    for stock_code in stocks:
        try:
            # Get basic data first (more reliable)
            broker_df = get_broker_data(stock_code)
            price_df = get_price_data(stock_code)

            # Safe access to price data
            last_price = 0
            price_change = 0
            if not price_df.empty:
                if 'close' in price_df.columns and len(price_df) > 0:
                    last_price = price_df['close'].iloc[-1]
                if 'change' in price_df.columns and len(price_df) > 0:
                    price_change = price_df['change'].iloc[-1] if pd.notna(price_df['change'].iloc[-1]) else 0

            # Date range
            if not broker_df.empty:
                date_range = f"{broker_df['date'].min().strftime('%d %b')} - {broker_df['date'].max().strftime('%d %b %Y')}"
                trading_days = broker_df['date'].nunique()
            else:
                date_range = "No data"
                trading_days = 0

            # Top accumulator
            if not broker_df.empty:
                broker_totals = broker_df.groupby('broker_code')['net_value'].sum()
                top_acc = broker_totals.idxmax() if len(broker_totals) > 0 else "-"
            else:
                top_acc = "-"

            # Foreign flow (simple calculation from broker data)
            foreign_net = 0
            foreign_trend = "Netral"
            foreign_color = "secondary"
            if not broker_df.empty:
                # Get last 5 days foreign flow
                foreign_brokers = ['ML', 'CS', 'YU', 'RX', 'CG', 'BK', 'KZ', 'FS', 'AK', 'DB', 'UB', 'MS', 'JP', 'GS', 'MG']
                recent_dates = broker_df['date'].drop_duplicates().nlargest(5)
                recent_df = broker_df[broker_df['date'].isin(recent_dates)]
                foreign_df = recent_df[recent_df['broker_code'].isin(foreign_brokers)]
                if not foreign_df.empty:
                    foreign_net = foreign_df['net_value'].sum()
                    foreign_trend = "Inflow" if foreign_net > 0 else "Outflow" if foreign_net < 0 else "Netral"
                    foreign_color = "success" if foreign_net > 0 else "danger" if foreign_net < 0 else "secondary"

            # Try to get composite score (optional - fallback if fails)
            score = 50  # Default
            action = "HOLD"
            color = "secondary"
            try:
                analysis = get_comprehensive_analysis(stock_code)
                if analysis and 'composite' in analysis:
                    composite = analysis.get('composite', {})
                    score = composite.get('composite_score', 50)
                    action = composite.get('action', 'HOLD')
                    color = composite.get('color', 'secondary')
            except:
                pass  # Use defaults

            # Create card
            card = dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H3(stock_code, className="mb-0 d-inline"),
                            dbc.Badge(action, color=color, className="ms-2 fs-6")
                        ])
                    ], className="bg-dark"),
                    dbc.CardBody([
                        # Composite Score
                        html.Div([
                            html.Div([
                                html.Span("Composite Score", className="text-muted small"),
                                html.H2(f"{score:.0f}", className=f"mb-0 text-{color}")
                            ], className="text-center mb-3"),
                        ]),

                        html.Hr(className="my-2"),

                        # Key Metrics Grid
                        dbc.Row([
                            dbc.Col([
                                html.Small("Harga", className="text-muted d-block"),
                                html.Strong(f"Rp {last_price:,.0f}")
                            ], width=6),
                            dbc.Col([
                                html.Small("Change", className="text-muted d-block"),
                                html.Strong(
                                    f"{price_change:+.1f}%",
                                    className=f"text-{'success' if price_change > 0 else 'danger' if price_change < 0 else 'muted'}"
                                )
                            ], width=6),
                        ], className="mb-2"),

                        dbc.Row([
                            dbc.Col([
                                html.Small("Foreign Flow", className="text-muted d-block"),
                                dbc.Badge(foreign_trend, color=foreign_color, className="mt-1")
                            ], width=6),
                            dbc.Col([
                                html.Small("Top Broker", className="text-muted d-block"),
                                html.Strong(top_acc)
                            ], width=6),
                        ], className="mb-2"),

                        html.Hr(className="my-2"),

                        # Data Info
                        html.Div([
                            html.Small([
                                html.I(className="fas fa-calendar me-1"),
                                f"{trading_days} trading days"
                            ], className="text-muted d-block"),
                            html.Small([
                                html.I(className="fas fa-clock me-1"),
                                date_range
                            ], className="text-muted"),
                        ], className="mb-3"),

                        # Action Buttons
                        html.Div([
                            dbc.Button([
                                html.I(className="fas fa-chart-line me-1"),
                                "Dashboard"
                            ], href=f"/dashboard?stock={stock_code}", color="primary", size="sm", className="me-1"),
                            dbc.Button([
                                html.I(className="fas fa-search me-1"),
                                "Analysis"
                            ], href=f"/analysis?stock={stock_code}", color="outline-info", size="sm"),
                        ], className="d-flex justify-content-center")
                    ])
                ], className="h-100 shadow-sm", color="dark", outline=True)
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
                    "Analisis mendalam pergerakan broker, akumulasi/distribusi, dan sinyal trading untuk saham pilihan Anda",
                    className="lead text-center text-muted mb-4"
                ),
                html.Hr(className="my-4"),
            ], className="py-4")
        ]),

        # Stock Selection
        dbc.Container([
            html.H4([
                html.I(className="fas fa-list-alt me-2"),
                f"Pilih Emiten ({len(stocks)} tersedia)"
            ], className="mb-4"),

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
                ], md=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5([html.I(className="fas fa-trophy me-2"), "Broker Ranking"], className="mb-2"),
                            html.P("Lihat peringkat broker akumulator & distributor", className="text-muted small mb-2"),
                            dbc.Button("Ranking", href="/ranking", color="outline-light", size="sm")
                        ])
                    ], color="info")
                ], md=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5([html.I(className="fas fa-bell me-2"), "Alerts"], className="mb-2"),
                            html.P("Monitor sinyal akumulasi dan pergerakan broker", className="text-muted small mb-2"),
                            dbc.Button("Alerts", href="/alerts", color="outline-light", size="sm")
                        ])
                    ], color="warning")
                ], md=4),
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
                                            'backgroundColor': '#2a2a2a',
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
# HELPER: BUY SIGNAL TRACKER CARD
# ============================================================

def create_buy_signal_card(buy_signal):
    """
    Create Buy Signal Tracker card - Anti FOMO feature
    Menunjukkan kapan sinyal BUY dimulai dan apakah masih aman untuk beli
    """
    if not buy_signal.get('has_signal'):
        return dbc.Card([
            dbc.CardHeader([
                html.H5([
                    "Buy Signal Tracker ",
                    dbc.Badge("NO SIGNAL", color="secondary")
                ], className="mb-0")
            ]),
            dbc.CardBody([
                html.P(buy_signal.get('message', 'Belum ada sinyal BUY'), className="text-muted"),
                html.Small([
                    html.Strong("Apa itu Buy Signal? "),
                    "Sistem mendeteksi kapan ada kombinasi indikator bagus: broker besar beli, ",
                    "foreign inflow, atau volume spike. Sinyal ini menandai titik awal potensi kenaikan."
                ], className="text-muted")
            ])
        ], className="mb-4", color="dark")

    zone_color = buy_signal.get('zone_color', 'secondary')

    return dbc.Card([
        dbc.CardHeader([
            html.H5([
                "Buy Signal Tracker ",
                dbc.Badge(buy_signal['zone'], color=zone_color, className="ms-2")
            ], className="mb-0 d-inline"),
            html.Small(" - Fitur Anti-FOMO", className="text-muted ms-2")
        ]),
        dbc.CardBody([
            dbc.Row([
                # Signal Info
                dbc.Col([
                    html.Div([
                        html.P([
                            html.Strong("Sinyal BUY Dimulai: "),
                            html.Span(
                                buy_signal['signal_date'].strftime('%d %b %Y'),
                                className="text-info"
                            )
                        ], className="mb-1"),
                        html.P([
                            html.Strong("Harga Saat Sinyal: "),
                            html.Span(
                                f"Rp {buy_signal['signal_price']:,.0f}",
                                className="text-info"
                            )
                        ], className="mb-1"),
                        html.P([
                            html.Strong("Harga Sekarang: "),
                            html.Span(
                                f"Rp {buy_signal['current_price']:,.0f}",
                                className=f"text-{zone_color}"
                            ),
                            html.Span(
                                f" ({buy_signal['price_change_pct']:+.1f}%)",
                                className=f"text-{zone_color}"
                            )
                        ], className="mb-1"),
                    ])
                ], width=4),

                # Safe Entry Zone
                dbc.Col([
                    html.Div([
                        html.H6("Safe Entry Zone", className="text-info"),
                        html.P([
                            html.Strong("Harga Ideal: "),
                            f"< Rp {buy_signal['safe_entry']['ideal_price']:,.0f}"
                        ], className="mb-1 small"),
                        html.P([
                            html.Strong("Harga Maksimal: "),
                            f"< Rp {buy_signal['safe_entry']['max_price']:,.0f}"
                        ], className="mb-1 small"),
                        html.P([
                            html.Strong("Status: "),
                            html.Span(
                                "AMAN" if buy_signal['safe_entry']['is_safe'] else "MAHAL",
                                className=f"text-{'success' if buy_signal['safe_entry']['is_safe'] else 'danger'} fw-bold"
                            )
                        ], className="mb-0 small"),
                    ])
                ], width=4),

                # Recommendation
                dbc.Col([
                    html.Div([
                        html.H4([
                            dbc.Badge(
                                buy_signal['recommendation'],
                                color=zone_color,
                                className="fs-5"
                            )
                        ], className="mb-2"),
                        html.P(buy_signal['zone_desc'], className="small text-muted mb-0"),
                    ], className="text-center")
                ], width=4),
            ]),
            html.Hr(),
            html.Small([
                html.Strong("Trigger Sinyal: "),
                ", ".join(buy_signal.get('signal_reasons', []))
            ], className="text-muted d-block"),
            html.Small([
                html.Strong("Penjelasan Zone: "),
                html.Br(),
                "• BETTER ENTRY: Harga turun <5% dari sinyal → kesempatan entry lebih baik",
                html.Br(),
                "• DISCOUNTED: Harga turun 5-10% → hati-hati, sinyal mungkin melemah",
                html.Br(),
                "• SIGNAL FAILED: Harga turun >10% → review ulang, sinyal mungkin gagal",
                html.Br(),
                "• SAFE/MODERATE: Harga naik <7% dari sinyal → masih aman",
                html.Br(),
                "• CAUTION/FOMO: Harga naik >7% dari sinyal → risiko tinggi, tunggu pullback"
            ], className="text-muted d-block mt-1")
        ])
    ], className="mb-4", color="dark", outline=True)


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
                ], className="border rounded p-2", style={"backgroundColor": "#2d2d2d"})
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
    ], className="mb-4", color="dark", outline=True)


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
    interpretation = avg_buy_analysis.get('interpretation', {})
    brokers = avg_buy_analysis.get('brokers', [])[:10]  # Top 10

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
            ], className="mb-2"),

            # Top 10 Brokers Avg Buy Table
            html.H6("Top 10 Broker by Buy Value (60 hari)", className="mb-2"),
            dash_table.DataTable(
                data=[{
                    'Broker': b['broker_code'],
                    'Tipe': get_broker_info(b['broker_code'])['type_name'],
                    'Avg Buy': f"Rp {b['avg_buy_price']:,.0f}",
                    'Buy Value': f"{b['total_buy_value']/1e9:.1f}B",
                    'Net': f"{b['net_value']/1e9:+.1f}B",
                    'Floating': f"{b.get('floating_pct', 0):+.1f}%",
                    'Status': b.get('position', '-')
                } for b in brokers],
                columns=[
                    {'name': 'Broker', 'id': 'Broker'},
                    {'name': 'Tipe', 'id': 'Tipe'},
                    {'name': 'Avg Buy', 'id': 'Avg Buy'},
                    {'name': 'Buy Value', 'id': 'Buy Value'},
                    {'name': 'Net', 'id': 'Net'},
                    {'name': 'Floating', 'id': 'Floating'},
                    {'name': 'Status', 'id': 'Status'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={
                    'textAlign': 'left',
                    'backgroundColor': '#303030',
                    'color': 'white',
                    'padding': '5px',
                    'fontSize': '12px'
                },
                style_header={
                    'backgroundColor': '#404040',
                    'fontWeight': 'bold'
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
                    {'if': {'filter_query': '{Status} = PROFIT'}, 'color': '#28a745'},
                    {'if': {'filter_query': '{Status} = LOSS'}, 'color': '#dc3545'},
                    {'if': {'filter_query': '{Tipe} = Asing'}, 'backgroundColor': 'rgba(220, 53, 69, 0.2)'},
                    {'if': {'filter_query': '{Tipe} = BUMN/Pemerintah'}, 'backgroundColor': 'rgba(40, 167, 69, 0.2)'},
                    {'if': {'filter_query': '{Tipe} = Lokal'}, 'backgroundColor': 'rgba(111, 66, 193, 0.2)'},
                ],
                page_size=5
            ),

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
        'Broker Position': '#6f42c1'  # purple
    }

    def create_level_badge(level_data):
        """Create badge for a support/resistance level"""
        source = level_data.get('source', '')
        color = source_colors.get(source, '#6c757d')
        return html.Div([
            html.Span(
                f"Rp {level_data['level']:,.0f}",
                className="fw-bold me-2"
            ),
            dbc.Badge(
                source,
                style={"backgroundColor": color, "fontSize": "10px"},
                className="me-2"
            ),
            html.Small(
                level_data.get('description', ''),
                className="text-muted"
            )
        ], className="mb-2 p-2 rounded", style={"backgroundColor": "#383838"})

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
            dbc.Alert([
                html.Strong("Risk/Reward Ratio: "),
                html.Span(
                    f"{interpretation.get('risk_reward', 0):.2f}x",
                    className="fw-bold text-warning"
                ),
                html.Small(
                    " (Potential gain vs potential loss dari level saat ini)",
                    className="text-muted ms-2"
                )
            ], color="dark", className="mb-3"),

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
    ], className="mb-4", color="dark", outline=True)


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
                # Top row: 3 metric cards
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Small("Foreign Flow", className="text-muted"),
                            html.H4([
                                f"{foreign_today:+.1f}B ",
                                html.Span("🟢" if foreign_today > 0 else "🔴", style={"fontSize": "16px"})
                            ], className="mb-0"),
                            html.Small(f"vs {foreign_yesterday:+.1f}B yesterday", className="text-muted")
                        ], className="text-center p-2 rounded", style={"backgroundColor": "#383838"})
                    ], width=4),
                    dbc.Col([
                        html.Div([
                            html.Small("Accum Ratio", className="text-muted"),
                            html.H4([
                                f"{accum_ratio:.0f}% Buy",
                            ], className=f"mb-0 text-{'success' if accum_ratio > 55 else ('danger' if accum_ratio < 45 else 'warning')}"),
                            html.Small(f"{100-accum_ratio:.0f}% Sell", className="text-muted")
                        ], className="text-center p-2 rounded", style={"backgroundColor": "#383838"})
                    ], width=4),
                    dbc.Col([
                        html.Div([
                            html.Small("Foreign Streak", className="text-muted"),
                            html.H4([
                                f"{foreign_streak} days ",
                                html.Span(foreign_signal[:3] if foreign_signal else "NEU",
                                         className=f"badge bg-{'success' if 'INFLOW' in foreign_signal else ('danger' if 'OUTFLOW' in foreign_signal else 'secondary')}")
                            ], className="mb-0"),
                            html.Small("consecutive", className="text-muted")
                        ], className="text-center p-2 rounded", style={"backgroundColor": "#383838"})
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
                ], className="p-2 rounded", style={"backgroundColor": "#2a2a2a"})
            ])
        ], className="mb-3", color="dark", outline=True)
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("📊 Market Sentiment"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3", color="dark")


def create_key_metrics_compact(stock_code='CDIA'):
    """
    Section 2: Key Metrics Compact
    - 6 metric cards in compact view
    """
    try:
        full_analysis = get_comprehensive_analysis(stock_code)
        broker_sens = full_analysis.get('broker_sensitivity', {})
        foreign_flow = full_analysis.get('foreign_flow', {})
        smart_money = full_analysis.get('smart_money', {})
        accum_phase = full_analysis.get('accumulation_phase', {})
        volume_analysis = full_analysis.get('volume_analysis', {})
        sr_analysis = analyze_support_resistance(stock_code)

        def metric_card(title, value, subtitle, color="info"):
            return html.Div([
                html.Small(title, className="text-muted", style={"fontSize": "10px"}),
                html.H5(value, className=f"text-{color} mb-0"),
                html.Small(subtitle, className="text-muted", style={"fontSize": "9px"})
            ], className="text-center p-2 rounded", style={"backgroundColor": "#383838"})

        # Get values
        sens_score = broker_sens.get('avg_win_rate', 0) if broker_sens else 0
        top_brokers = broker_sens.get('top_5_brokers', [])[:2] if broker_sens else []

        foreign_score = foreign_flow.get('score', 0)
        foreign_signal = foreign_flow.get('signal', 'NEUTRAL')

        smart_score = smart_money.get('score', 0)
        smart_detected = smart_money.get('detection', 'NO')

        accum_in = accum_phase.get('in_accumulation', False)
        accum_range = accum_phase.get('range_pct', 0)

        rvol = volume_analysis.get('rvol', 1.0)
        vpt_signal = volume_analysis.get('vpt_signal', 'NEUTRAL')

        key_support = sr_analysis.get('key_support', 0) if sr_analysis else 0
        key_resistance = sr_analysis.get('key_resistance', 0) if sr_analysis else 0
        current_price = sr_analysis.get('current_price', 0) if sr_analysis else 0

        support_pct = ((current_price - key_support) / current_price * 100) if current_price > 0 and key_support > 0 else 0
        resist_pct = ((key_resistance - current_price) / current_price * 100) if current_price > 0 and key_resistance > 0 else 0

        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-tachometer-alt me-2"),
                html.Span("Key Metrics at Glance", className="fw-bold")
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        metric_card(
                            "Broker Sensitivity",
                            f"{sens_score:.0f}%",
                            f"Top: {', '.join(top_brokers)}" if top_brokers else "N/A",
                            "info" if sens_score > 50 else "warning"
                        )
                    ], width=4),
                    dbc.Col([
                        metric_card(
                            "Foreign Flow",
                            f"{foreign_score:.0f}",
                            foreign_signal[:10] if foreign_signal else "N/A",
                            "success" if foreign_score > 0 else ("danger" if foreign_score < 0 else "secondary")
                        )
                    ], width=4),
                    dbc.Col([
                        metric_card(
                            "Volume",
                            f"RVOL {rvol:.1f}x",
                            vpt_signal[:10] if vpt_signal else "N/A",
                            "success" if rvol > 1.2 else ("warning" if rvol > 0.8 else "danger")
                        )
                    ], width=4),
                ], className="mb-2"),
                dbc.Row([
                    dbc.Col([
                        metric_card(
                            "Smart Money",
                            f"{smart_score:.0f}",
                            f"Detected: {smart_detected[:3]}" if smart_detected else "N/A",
                            "success" if smart_score > 60 else "secondary"
                        )
                    ], width=4),
                    dbc.Col([
                        metric_card(
                            "Accum Phase",
                            "IN ✅" if accum_in else "OUT",
                            f"Range: {accum_range:.1f}%",
                            "success" if accum_in else "secondary"
                        )
                    ], width=4),
                    dbc.Col([
                        metric_card(
                            "S/R Levels",
                            f"S: -{support_pct:.1f}%",
                            f"R: +{resist_pct:.1f}%",
                            "info"
                        )
                    ], width=4),
                ]),

                html.Hr(className="my-2"),

                # Penjelasan Section
                html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        html.Strong("Cara Baca 6 Indikator: ")
                    ], className="text-info"),
                    html.Br(),
                    html.Small([
                        html.Strong("• Broker Sensitivity: "), "Win rate broker 'pintar' memprediksi kenaikan. >50% = bagus",
                        html.Br(),
                        html.Strong("• Foreign Flow: "), "Skor momentum asing. Positif = asing aktif beli, Negatif = jual",
                        html.Br(),
                        html.Strong("• Volume (RVOL): "), "Relative Volume vs rata-rata. >1.2x = volume tinggi (ada interest)",
                        html.Br(),
                        html.Strong("• Smart Money: "), "Deteksi pembelian besar tersembunyi. >60 = terdeteksi akumulasi",
                        html.Br(),
                        html.Strong("• Accum Phase: "), "IN = sedang fase akumulasi (sideways, range sempit). Ideal untuk beli",
                        html.Br(),
                        html.Strong("• S/R Levels: "), "Support (-%) = jarak ke bawah, Resistance (+%) = jarak ke atas"
                    ], className="text-muted", style={"fontSize": "10px"})
                ], className="p-2 rounded", style={"backgroundColor": "#2a2a2a"})
            ])
        ], className="mb-3", color="dark", outline=True)
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("🎯 Key Metrics"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3", color="dark")


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

        # Build accumulation list
        accum_items = [html.Div([
            html.Span(f"{m['broker']} ", className="fw-bold"),
            html.Small(f"+{m['today']/1e9:.1f}B", className="text-success")
        ], style={"fontSize": "11px"}) for m in new_accum] if new_accum else [html.Small("None today", className="text-muted")]

        # Build distribution list
        dist_items = [html.Div([
            html.Span(f"{m['broker']} ", className="fw-bold"),
            html.Small(f"{m['today']/1e9:.1f}B", className="text-danger")
        ], style={"fontSize": "11px"}) for m in new_dist] if new_dist else [html.Small("None today", className="text-muted")]

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
                            html.Small("🟢 New Accumulation", className="text-success fw-bold"),
                            *accum_items
                        ], className="p-2 rounded", style={"backgroundColor": "#2d3a2d"})
                    ], width=6),
                    # New Distribution Warning
                    dbc.Col([
                        html.Div([
                            html.Small("🔴 New Distribution", className="text-danger fw-bold"),
                            *dist_items
                        ], className="p-2 rounded", style={"backgroundColor": "#3a2d2d"})
                    ], width=6),
                ], className="mb-3"),

                # Biggest Movement Table
                html.Small("Biggest Movement Today vs Yesterday", className="text-muted fw-bold mb-2 d-block"),
                dash_table.DataTable(
                    data=[{
                        'Broker': m['broker'],
                        'Type': m['type'][:6],
                        'Today': f"{m['today']/1e9:+.1f}B",
                        'Yesterday': f"{m['yesterday']/1e9:+.1f}B",
                        'Change': f"{m['change']/1e9:+.1f}B"
                    } for m in top_movements],
                    columns=[
                        {'name': 'Broker', 'id': 'Broker'},
                        {'name': 'Type', 'id': 'Type'},
                        {'name': 'Today', 'id': 'Today'},
                        {'name': 'Yest', 'id': 'Yesterday'},
                        {'name': 'Change', 'id': 'Change'}
                    ],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '4px', 'fontSize': '11px'},
                    style_header={'backgroundColor': '#404040', 'fontWeight': 'bold', 'fontSize': '10px'},
                    style_data_conditional=[
                        {'if': {'filter_query': '{Change} contains "+"'}, 'color': '#28a745'},
                        {'if': {'filter_query': '{Change} contains "-"'}, 'color': '#dc3545'},
                    ]
                ),

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
                ], className="p-2 rounded", style={"backgroundColor": "#2a2a2a"})
            ])
        ], className="mb-3", color="dark", outline=True)
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("🔔 Broker Movement"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3", color="dark")


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
                # Historical Pattern Table
                html.Small("Historical Performance", className="text-muted fw-bold mb-2 d-block"),
                dash_table.DataTable(
                    data=[{
                        'Rank': f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else str(i+1)}",
                        'Broker': b['broker'],
                        'Win Rate': f"{b['win_rate']:.0f}%",
                        'Lead Time': f"{b['lead_time']:.0f}d",
                        'Signals': b['signals'],
                        'Avg Buy': f"Rp {b['avg_buy']:,.0f}" if b['avg_buy'] > 0 else "-"
                    } for i, b in enumerate(broker_status)],
                    columns=[
                        {'name': '', 'id': 'Rank'},
                        {'name': 'Broker', 'id': 'Broker'},
                        {'name': 'Win%', 'id': 'Win Rate'},
                        {'name': 'Lead', 'id': 'Lead Time'},
                        {'name': 'Sigs', 'id': 'Signals'},
                        {'name': 'Avg Buy', 'id': 'Avg Buy'}
                    ],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '4px', 'fontSize': '11px'},
                    style_header={'backgroundColor': '#404040', 'fontWeight': 'bold', 'fontSize': '10px'},
                ),

                html.Hr(className="my-2"),

                # Current Status
                html.Small("Current Status - Are they accumulating now?", className="text-muted fw-bold mb-2 d-block"),
                dash_table.DataTable(
                    data=[{
                        'Broker': b['broker'],
                        'Status': f"{'🟢 ACCUM' if b['status']=='ACCUM' else '🔴 DIST' if b['status']=='DIST' else '⚪ NEUTRAL'}",
                        'Streak': f"{b['streak']}d" if b['streak'] > 0 else "-",
                        'Today': f"{b['today_net']/1e9:+.1f}B",
                        'Lot': f"{b['total_lot']/1e6:.1f}M" if b['total_lot'] > 0 else "-"
                    } for b in broker_status],
                    columns=[
                        {'name': 'Broker', 'id': 'Broker'},
                        {'name': 'Status', 'id': 'Status'},
                        {'name': 'Streak', 'id': 'Streak'},
                        {'name': 'Today', 'id': 'Today'},
                        {'name': 'Tot Lot', 'id': 'Lot'}
                    ],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '4px', 'fontSize': '11px'},
                    style_header={'backgroundColor': '#404040', 'fontWeight': 'bold', 'fontSize': '10px'},
                ),

                # Insight box
                html.Div([
                    html.Small("💡 Insight: ", className="fw-bold"),
                    html.Small(
                        f"{len(accum_brokers)} broker sensitif sedang akumulasi: {', '.join([b['broker'] for b in accum_brokers])}"
                        if accum_brokers else "Belum ada broker sensitif yang mulai akumulasi",
                        className="text-success" if accum_brokers else "text-muted"
                    )
                ], className="mt-2 p-2 rounded", style={"backgroundColor": "#2d3a2d" if accum_brokers else "#383838"}),

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
                ], className="p-2 rounded", style={"backgroundColor": "#2a2a2a"})
            ])
        ], className="mb-3", color="dark", outline=True)
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("🎯 Broker Sensitivity Pattern"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3", color="dark")


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

        # Build list items
        accum_items = [html.Div([
            html.Span(f"{b['broker']} ", className="fw-bold"),
            html.Span(f"{b['accum_streak']}d ", className="badge bg-success me-1"),
            html.Small(f"{b['total_net']/1e9:+.1f}B", className="text-muted")
        ], style={"fontSize": "11px"}) for b in accum_watch] if accum_watch else [html.Small("No streak", className="text-muted")]

        dist_items = [html.Div([
            html.Span(f"{b['broker']} ", className="fw-bold"),
            html.Span(f"{b['dist_streak']}d ", className="badge bg-danger me-1"),
            html.Small(f"{b['total_net']/1e9:.1f}B", className="text-muted")
        ], style={"fontSize": "11px"}) for b in dist_watch] if dist_watch else [html.Small("No warning", className="text-muted")]

        float_items = [html.Div([
            html.Span(f"{b['broker']} ", className="fw-bold"),
            html.Small(f"{b['floating_pct']:.1f}% ", className="text-danger"),
            html.Small(f"@{b['avg_buy']:,.0f}", className="text-muted")
        ], style={"fontSize": "11px"}) for b in float_loss] if float_loss else [html.Small("No significant loss", className="text-muted")]

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
                        ], className="p-2 rounded h-100", style={"backgroundColor": "#2d3a2d"})
                    ], width=4),

                    # Distribution Warning
                    dbc.Col([
                        html.Div([
                            html.Small("⚠️ Distribution Warning", className="text-danger fw-bold mb-2 d-block"),
                            *dist_items
                        ], className="p-2 rounded h-100", style={"backgroundColor": "#3a2d2d"})
                    ], width=4),

                    # Floating Loss
                    dbc.Col([
                        html.Div([
                            html.Small("💸 Floating Loss", className="text-warning fw-bold mb-2 d-block"),
                            *float_items
                        ], className="p-2 rounded h-100", style={"backgroundColor": "#3a3a2d"})
                    ], width=4),
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
                ], className="p-2 rounded", style={"backgroundColor": "#2a2a2a"})
            ])
        ], className="mb-3", color="dark", outline=True)
    except Exception as e:
        return dbc.Card([
            dbc.CardHeader("👁️ Broker Watchlist"),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3", color="dark")


# ============================================================
# PAGE: COMPREHENSIVE ANALYSIS (Merged Bandarmology + Summary)
# ============================================================

def create_analysis_page(stock_code='CDIA'):
    """Create comprehensive analysis page with composite scoring"""
    try:
        # Use get_comprehensive_analysis to get all data in one call (optimized)
        full_analysis = get_comprehensive_analysis(stock_code)
        composite = full_analysis['composite']
        broker_sens = full_analysis['broker_sensitivity']
        foreign_flow = full_analysis['foreign_flow']
        smart_money = full_analysis['smart_money']
        price_pos = full_analysis['price_position']
        accum_phase = full_analysis['accumulation_phase']
        volume_analysis = full_analysis.get('volume_analysis', {})
        layer1 = full_analysis.get('layer1_filter', {})
        alerts = full_analysis['alerts']

        # Get Buy Signal Tracker
        buy_signal = track_buy_signal(stock_code)

        # Get Avg Buy Analysis
        avg_buy_analysis = analyze_avg_buy_position(stock_code)

        # Get Support/Resistance Analysis (Multi-Method)
        sr_analysis = analyze_support_resistance(stock_code)

    except Exception as e:
        return html.Div([
            dbc.Alert(f"Error loading analysis for {stock_code}: {str(e)}", color="danger"),
            html.P("Pastikan data sudah diupload dengan benar")
        ])

    # Color mapping for scores
    def score_color(score):
        if score >= 70: return 'success'
        if score >= 50: return 'info'
        if score >= 30: return 'warning'
        return 'danger'

    return html.Div([
        html.H4(f"Comprehensive Analysis - {stock_code}", className="mb-4"),

        # ========== COMPOSITE SCORE HERO CARD ==========
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.H1(
                                f"{composite['composite_score']:.0f}",
                                className=f"display-1 text-{composite['color']} mb-0"
                            ),
                            html.P("/100", className="text-muted h4")
                        ], className="text-center")
                    ], width=3, className="border-end"),
                    dbc.Col([
                        html.Div([
                            html.H2([
                                dbc.Badge(
                                    composite['action'],
                                    color=composite['color'],
                                    className="fs-3 me-2"
                                )
                            ], className="mb-2"),
                            html.P(composite['action_desc'], className="text-muted mb-3"),
                            html.Hr(),
                            html.Div([
                                html.Strong("Interpretasi Score:"),
                                html.Ul([
                                    html.Li("80-100: STRONG BUY - Semua sinyal align"),
                                    html.Li("60-79: BUY - Mayoritas sinyal positif"),
                                    html.Li("40-59: HOLD - Sinyal mixed, wait & see"),
                                    html.Li("20-39: CAUTION - Lebih banyak sinyal negatif"),
                                    html.Li("0-19: AVOID - Distribusi/downtrend"),
                                ], className="small mb-0")
                            ])
                        ])
                    ], width=9)
                ])
            ])
        ], className="mb-4", color="dark"),

        # ========== BUY SIGNAL TRACKER (Anti-FOMO) ==========
        create_buy_signal_card(buy_signal),

        # ========== MULTI-PERIOD SUMMARY ==========
        create_multi_period_card(stock_code),

        # ========== AVG BUY ANALYSIS ==========
        create_avg_buy_card(avg_buy_analysis, stock_code, sr_analysis),

        # ========== SUPPORT/RESISTANCE LEVELS (Multi-Method) ==========
        create_sr_levels_card(sr_analysis, stock_code),

        # ========== COMPONENT SCORES ROW (with tooltips) ==========
        # ========== LAYER 1 BASIC FILTER ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-filter me-2"),
                    "Layer 1 Basic Filter",
                    dbc.Badge(
                        layer1['status'] if 'layer1' in dir() and layer1 else "N/A",
                        color="success" if layer1.get('all_passed') else ("warning" if layer1.get('passed') else "danger"),
                        className="ms-2"
                    ) if 'layer1' in dir() and layer1 else None
                ], className="mb-0"),
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.I(className=f"fas fa-{'check-circle text-success' if layer1['criteria']['foreign_consecutive']['passed'] else 'times-circle text-danger'} me-2"),
                            html.Strong("N Foreign >= 3 hari: "),
                            html.Span(f"{layer1['criteria']['foreign_consecutive']['value']} hari"),
                        ], className="mb-2") if 'layer1' in dir() and layer1 and 'criteria' in layer1 else None,
                        html.Div([
                            html.I(className=f"fas fa-{'check-circle text-success' if layer1['criteria']['rvol']['passed'] else 'times-circle text-danger'} me-2"),
                            html.Strong("RVOL >= 1.2x: "),
                            html.Span(f"{layer1['criteria']['rvol']['value']:.2f}x"),
                        ], className="mb-2") if 'layer1' in dir() and layer1 and 'criteria' in layer1 else None,
                        html.Div([
                            html.I(className=f"fas fa-{'check-circle text-success' if layer1['criteria']['foreign_today']['passed'] else 'times-circle text-danger'} me-2"),
                            html.Strong("N Foreign hari ini > 0: "),
                            html.Span(f"Rp {layer1['criteria']['foreign_today']['value']/1e9:.2f} B"),
                        ]) if 'layer1' in dir() and layer1 and 'criteria' in layer1 else None,
                    ], width=6),
                    dbc.Col([
                        html.Div([
                            html.H4(f"{layer1['criteria_met']}/3", className=f"text-{'success' if layer1['all_passed'] else ('warning' if layer1['passed'] else 'danger')}"),
                            html.P(layer1['message'], className="text-muted small mb-1"),
                            html.P([
                                html.I(className="fas fa-info-circle me-1"),
                                layer1['interpretation']['score_impact']
                            ], className="small text-warning") if layer1.get('max_score_cap') else None,
                        ])
                    ], width=6, className="text-end"),
                ])
            ])
        ], color="dark", outline=True, className="mb-3") if 'layer1' in dir() and layer1 else None,

        # ========== COMPONENT SCORES ROW 1 (A-C) ==========
        dbc.Row([
            # A. Broker Sensitivity
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("A. Broker Sensitivity", className="fw-bold"),
                        html.I(className="fas fa-question-circle text-info ms-1", id="help-broker-sens", style={"fontSize": "11px", "cursor": "pointer"}),
                        dbc.Tooltip(METRIC_EXPLANATIONS['broker_sensitivity']['short'], target="help-broker-sens", placement="top"),
                        dbc.Badge("20%", color="secondary", className="ms-2 float-end")
                    ]),
                    dbc.CardBody([
                        html.H2(f"{composite['components']['broker_sensitivity']['score']:.0f}",
                               className=f"text-{score_color(composite['components']['broker_sensitivity']['score'])}"),
                        html.P(composite['components']['broker_sensitivity']['signal'], className="text-muted small"),
                        html.Small([f"Top 5: {', '.join(broker_sens.get('top_5_brokers', [])[:3])}"], className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=4),

            # B. Foreign Flow
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("B. Foreign Flow", className="fw-bold"),
                        html.I(className="fas fa-question-circle text-info ms-1", id="help-foreign-flow", style={"fontSize": "11px", "cursor": "pointer"}),
                        dbc.Tooltip(METRIC_EXPLANATIONS['foreign_flow']['short'], target="help-foreign-flow", placement="top"),
                        dbc.Badge("20%", color="secondary", className="ms-2 float-end")
                    ]),
                    dbc.CardBody([
                        html.H2(f"{foreign_flow['score']:.0f}", className=f"text-{score_color(foreign_flow['score'])}"),
                        html.P(foreign_flow['signal'].replace('_', ' '), className="text-muted small"),
                        html.Small([f"{foreign_flow['direction_label']} | {foreign_flow['consistency_label']}"], className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=4),

            # C. Smart Money
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("C. Smart Money", className="fw-bold"),
                        html.I(className="fas fa-question-circle text-info ms-1", id="help-smart-money", style={"fontSize": "11px", "cursor": "pointer"}),
                        dbc.Tooltip(METRIC_EXPLANATIONS['smart_money']['short'], target="help-smart-money", placement="top"),
                        dbc.Badge("15%", color="secondary", className="ms-2 float-end")
                    ]),
                    dbc.CardBody([
                        html.H2(f"{smart_money['score']:.0f}", className=f"text-{score_color(smart_money['score'])}"),
                        html.P(smart_money['signal'].replace('_', ' '), className="text-muted small"),
                        html.Small([f"Strong: {smart_money['strong_accum_days']}d | Moderate: {smart_money['moderate_accum_days']}d"], className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=4),
        ], className="mb-3"),

        # ========== COMPONENT SCORES ROW 2 (D-F) ==========
        dbc.Row([
            # D. Price Position
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("D. Price Position", className="fw-bold"),
                        html.I(className="fas fa-question-circle text-info ms-1", id="help-price-pos", style={"fontSize": "11px", "cursor": "pointer"}),
                        dbc.Tooltip(METRIC_EXPLANATIONS['price_position']['short'], target="help-price-pos", placement="top"),
                        dbc.Badge("15%", color="secondary", className="ms-2 float-end")
                    ]),
                    dbc.CardBody([
                        html.H2(f"{price_pos['score']:.0f}", className=f"text-{score_color(price_pos['score'])}"),
                        html.P(price_pos['signal'].replace('_', ' '), className="text-muted small"),
                        html.Small([f"Bullish: {price_pos['bullish_signals']}/{price_pos['total_signals']} signals"], className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=4),

            # E. Accumulation Phase
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("E. Accumulation", className="fw-bold"),
                        html.I(className="fas fa-question-circle text-info ms-1", id="help-accum", style={"fontSize": "11px", "cursor": "pointer"}),
                        dbc.Tooltip(METRIC_EXPLANATIONS['accumulation_phase']['short'], target="help-accum", placement="top"),
                        dbc.Badge("15%", color="secondary", className="ms-2 float-end")
                    ]),
                    dbc.CardBody([
                        html.H2(f"{accum_phase['score']:.0f}", className=f"text-{score_color(accum_phase['score'])}"),
                        html.P(accum_phase['phase'].replace('_', ' '), className="text-muted small"),
                        html.Small(["In Accum" if accum_phase['in_accumulation'] else "Not in Accum"],
                                   className=f"text-{'success' if accum_phase['in_accumulation'] else 'muted'}")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=4),

            # F. Volume Analysis
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("F. Volume Analysis", className="fw-bold"),
                        html.I(className="fas fa-question-circle text-info ms-1", id="help-volume", style={"fontSize": "11px", "cursor": "pointer"}),
                        dbc.Tooltip("Analisis volume relatif (RVOL) dan tren volume-harga", target="help-volume", placement="top"),
                        dbc.Badge("15%", color="secondary", className="ms-2 float-end")
                    ]),
                    dbc.CardBody([
                        html.H2(f"{volume_analysis['score']:.0f}" if 'volume_analysis' in dir() and volume_analysis else "N/A",
                               className=f"text-{score_color(volume_analysis['score'])}" if 'volume_analysis' in dir() and volume_analysis else "text-muted"),
                        html.P(volume_analysis['signal'].replace('_', ' ') if 'volume_analysis' in dir() and volume_analysis else "N/A", className="text-muted small"),
                        html.Small([f"RVOL: {volume_analysis['rvol']:.1f}x | {volume_analysis['rvol_category']}"] if 'volume_analysis' in dir() and volume_analysis else ["N/A"],
                                   className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=4),
        ], className="mb-4"),

        # ========== PANDUAN CARA MEMBACA KOMPONEN ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-book-open me-2"),
                    "Panduan Cara Membaca Komponen Score"
                ], className="mb-0"),
            ]),
            dbc.CardBody([
                # Layer 1 Filter Explanation
                dbc.Alert([
                    html.H6([html.I(className="fas fa-filter me-2"), "Layer 1 Basic Filter"], className="alert-heading"),
                    html.P([
                        "Syarat minimum sebelum entry. ", html.Strong("Jika tidak lolos, skor dibatasi maksimal 60-75."), html.Br(),
                        "• N Foreign >= 3 hari berturut (konsistensi foreign inflow)", html.Br(),
                        "• RVOL >= 1.2x (volume di atas rata-rata 20 hari)", html.Br(),
                        "• N Foreign hari ini > 0 (masih ada foreign inflow)"
                    ], className="small mb-0")
                ], color="info", className="mb-3"),

                dbc.Row([
                    # Column 1: A-B
                    dbc.Col([
                        html.Div([
                            html.H6("A. Broker Sensitivity (20%)", className="text-info"),
                            html.P([
                                html.Strong("Apa: "), "Mengukur apakah broker-broker 'pintar' sedang akumulasi.", html.Br(),
                                html.Strong("Cara Baca: "), html.Br(),
                                "• Score >60 = Broker sensitif aktif akumulasi", html.Br(),
                                "• Score 40-60 = Mixed, beberapa akumulasi", html.Br(),
                                "• Score <40 = Belum ada akumulasi signifikan", html.Br(),
                                html.Strong("Top 5: "), "Broker dengan track record terbaik prediksi harga naik"
                            ], className="small text-muted mb-3"),

                            html.H6("B. Foreign Flow (20%)", className="text-info"),
                            html.P([
                                html.Strong("Apa: "), "Aliran dana asing (foreign) masuk/keluar.", html.Br(),
                                html.Strong("Cara Baca: "), html.Br(),
                                "• INFLOW = Dana asing masuk (bullish)", html.Br(),
                                "• OUTFLOW = Dana asing keluar (bearish)", html.Br(),
                                "• Perhatikan konsistensi (berapa hari berturut-turut)", html.Br(),
                                html.Strong("Tip: "), "Foreign inflow + broker sensitif akumulasi = sinyal kuat"
                            ], className="small text-muted"),
                        ], className="border-end pe-3")
                    ], width=4),

                    # Column 2: C-D
                    dbc.Col([
                        html.Div([
                            html.H6("C. Smart Money (15%)", className="text-info"),
                            html.P([
                                html.Strong("Apa: "), "Deteksi akumulasi 'diam-diam' oleh bandar.", html.Br(),
                                html.Strong("Cara Baca: "), html.Br(),
                                "• Strong: Volume naik, tapi frekuensi turun (bandar beli besar)", html.Br(),
                                "• Moderate: Volume naik sedikit, frekuensi stabil", html.Br(),
                                "• Weak: Volume dan frekuensi naik sama (retail ikut-ikutan)", html.Br(),
                                html.Strong("Formula: "), "Strong=+3, Moderate=+2, Mixed=+1, Retail FOMO=-1"
                            ], className="small text-muted mb-3"),

                            html.H6("D. Price Position (15%)", className="text-info"),
                            html.P([
                                html.Strong("Apa: "), "Posisi harga secara teknikal.", html.Br(),
                                html.Strong("Cara Baca: "), html.Br(),
                                "• Bullish signals = Harga di atas MA, breakout, dll", html.Br(),
                                "• Bearish signals = Harga di bawah MA, breakdown", html.Br(),
                                html.Strong("Bullish x/y: "), "x = jumlah sinyal bullish, y = total sinyal"
                            ], className="small text-muted"),
                        ], className="border-end pe-3")
                    ], width=4),

                    # Column 3: E-F + Summary
                    dbc.Col([
                        html.Div([
                            html.H6("E. Accumulation Phase (15%)", className="text-info"),
                            html.P([
                                html.Strong("Apa: "), "Apakah saham dalam fase akumulasi.", html.Br(),
                                html.Strong("Cara Baca: "), html.Br(),
                                "• ACCUMULATION = Fase ideal untuk beli", html.Br(),
                                "• DISTRIBUTION = Fase jual/hindari", html.Br(),
                                html.Strong("In Accum: "), "Memenuhi kriteria fase akumulasi"
                            ], className="small text-muted mb-3"),

                            html.H6("F. Volume Analysis (15%)", className="text-info"),
                            html.P([
                                html.Strong("Apa: "), "Analisis volume relatif dan tren volume-harga.", html.Br(),
                                html.Strong("RVOL: "), "Volume hari ini / Avg 20 hari", html.Br(),
                                "• >= 2.0x = Very High (aktivitas sangat tinggi)", html.Br(),
                                "• >= 1.5x = High | >= 1.2x = Above Average", html.Br(),
                                "• < 0.8x = Low (aktivitas rendah)", html.Br(),
                                html.Strong("VPT: "), "Volume naik + Harga naik = Bullish"
                            ], className="small text-muted mb-3"),

                            html.H6("Interpretasi Total Score", className="text-warning"),
                            html.P([
                                html.Span(">= 75: ", className="text-success fw-bold"), "STRONG BUY - Semua sinyal align", html.Br(),
                                html.Span("60-74: ", className="text-info"), "BUY - Mayoritas sinyal positif", html.Br(),
                                html.Span("45-59: ", className="text-warning"), "WATCH - Sinyal mixed, pantau", html.Br(),
                                html.Span("< 45: ", className="text-danger fw-bold"), "NO ENTRY - Belum mendukung"
                            ], className="small"),
                        ])
                    ], width=4),
                ])
            ])
        ], className="mb-4", color="dark", outline=True),

        # ========== ALERTS SECTION ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5("Active Alerts", className="mb-0 d-inline"),
                dbc.Badge(f"{len(alerts)}", color="warning" if alerts else "secondary", className="ms-2")
            ]),
            dbc.CardBody([
                create_enhanced_alerts_list(alerts) if alerts else dbc.Alert("Tidak ada alert aktif", color="secondary")
            ])
        ], className="mb-4"),

        # ========== BROKER SENSITIVITY RANKING ==========
        dbc.Card([
            dbc.CardHeader([
                html.H5("Broker Sensitivity Ranking", className="mb-0 d-inline"),
                html.Small(" (Lead Time, Win Rate, Sensitivity Score)", className="text-muted ms-2")
            ]),
            dbc.CardBody([
                create_broker_sensitivity_table(broker_sens) if broker_sens.get('brokers') else "No data"
            ])
        ], className="mb-4"),

        # ========== DETAIL SECTIONS ==========
        dbc.Row([
            # Foreign Flow Detail
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H6("Foreign Flow Detail", className="mb-0")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([html.Strong("Direction:"), html.Br(), html.Span(foreign_flow['direction_label'])]),
                            dbc.Col([html.Strong("Momentum:"), html.Br(), html.Span(f"{foreign_flow['momentum']}B", className=f"text-{score_color(50 + foreign_flow['momentum']*10)}")]),
                            dbc.Col([html.Strong("Consistency:"), html.Br(), html.Span(foreign_flow['consistency_label'])]),
                        ], className="mb-2"),
                        html.Hr(),
                        dbc.Row([
                            dbc.Col([html.Strong("Latest:"), f" {foreign_flow['latest_foreign']}B"]),
                            dbc.Col([html.Strong("5D Total:"), f" {foreign_flow['total_5d']}B"]),
                            dbc.Col([html.Strong("10D Total:"), f" {foreign_flow['total_10d']}B"]),
                        ]),
                        html.Small(f"Flow vs Price Correlation: {foreign_flow['correlation']}%", className="text-muted d-block mt-2"),
                        html.Hr(),
                        html.Small([
                            html.Strong("Cara Baca: ", className="text-info"), html.Br(),
                            "• ", html.Strong("Direction"), ": INFLOW (asing beli) / OUTFLOW (asing jual)", html.Br(),
                            "• ", html.Strong("Momentum"), ": Perubahan net flow dari kemarin (+ atau -)", html.Br(),
                            "• ", html.Strong("Consistency"), ": Berapa hari berturut-turut inflow/outflow", html.Br(),
                            "• ", html.Strong("Latest/5D/10D"), ": Net flow hari ini / 5 hari / 10 hari", html.Br(),
                            "• ", html.Strong("Correlation"), ": Seberapa kuat hubungan foreign flow dengan harga"
                        ], className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=6),

            # Price Position Detail
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H6("Price Position Detail", className="mb-0")),
                    dbc.CardBody([
                        create_price_position_detail(price_pos),
                        html.Hr(),
                        html.Small([
                            html.Strong("Cara Baca: ", className="text-info"), html.Br(),
                            "• ", html.Strong("Close Vs Avg"), ": Posisi harga vs rata-rata → + = uptrend", html.Br(),
                            "• ", html.Strong("Price Vs MA5/MA20"), ": Harga vs Moving Average → + = bullish", html.Br(),
                            "• ", html.Strong("Dist From Low"), ": Jarak dari harga terendah → tinggi = sudah naik", html.Br(),
                            "• ", html.Strong("Breakout"), ": Kekuatan breakout dari range sebelumnya", html.Br(),
                            "• ", html.Strong("Bullish"), ": ✓ = sinyal bullish, ✗ = bearish, - = netral"
                        ], className="text-muted")
                    ])
                ], color="dark", outline=True, className="h-100")
            ], width=6),
        ], className="mb-4"),

        # ========== ACCUMULATION PHASE CRITERIA ==========
        dbc.Card([
            dbc.CardHeader(html.H5("Accumulation Phase Criteria", className="mb-0")),
            dbc.CardBody([
                create_accumulation_criteria_table(accum_phase['criteria']),
                html.Hr(),
                html.Div([
                    html.H6("Cara Membaca Kriteria Akumulasi:", className="text-info mb-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.Strong("1. Sideways"), html.Br(),
                                "Range harga sempit (<10%). Ideal untuk akumulasi.", html.Br(),
                                html.Span("✓", className="text-success"), " = Range <10%  ",
                                html.Span("✗", className="text-danger"), " = Range >10%"
                            ], className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.Small([
                                html.Strong("2. Volume Increasing"), html.Br(),
                                "Volume naik = ada aktivitas beli.", html.Br(),
                                html.Span("✓", className="text-success"), " = Vol naik  ",
                                html.Span("✗", className="text-danger"), " = Vol turun"
                            ], className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.Small([
                                html.Strong("3. Foreign Positive"), html.Br(),
                                "Asing net buy dalam 10 hari.", html.Br(),
                                html.Span("✓", className="text-success"), " = Net buy  ",
                                html.Span("✗", className="text-danger"), " = Net sell"
                            ], className="text-muted")
                        ], width=4),
                    ], className="mb-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.Strong("4. Sensitive Brokers Active"), html.Br(),
                                "Broker sensitif sedang akumulasi.", html.Br(),
                                html.Span("✓", className="text-success"), " = >2 broker aktif  ",
                                html.Span("✗", className="text-danger"), " = <2 broker"
                            ], className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.Small([
                                html.Strong("5. Not Breakout"), html.Br(),
                                "Belum breakout = masih bisa entry.", html.Br(),
                                html.Span("✓", className="text-success"), " = Belum breakout  ",
                                html.Span("✗", className="text-danger"), " = Sudah breakout"
                            ], className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.Small([
                                html.Strong("Ideal Akumulasi:"), html.Br(),
                                "Minimal 3-4 kriteria terpenuhi (✓)", html.Br(),
                                html.Span("Score tinggi = lebih baik", className="text-success")
                            ], className="text-muted")
                        ], width=4),
                    ]),
                ])
            ])
        ], className="mb-4"),

        # ========== VOLUME ANALYSIS DETAIL ==========
        dbc.Card([
            dbc.CardHeader(html.H5([
                html.I(className="fas fa-chart-bar me-2"),
                "Volume Analysis Detail"
            ], className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Strong("RVOL (Relative Volume)"),
                        html.H3(f"{volume_analysis.get('rvol', 1.0):.2f}x" if volume_analysis else "N/A",
                               className=f"text-{'success' if volume_analysis.get('rvol', 0) >= 1.5 else ('info' if volume_analysis.get('rvol', 0) >= 1.2 else 'muted')}"),
                        html.Small(volume_analysis.get('rvol_category', 'N/A'), className="text-muted")
                    ], width=3),
                    dbc.Col([
                        html.Strong("Volume-Price Trend"),
                        html.H4(volume_analysis.get('vpt_signal', 'N/A').replace('_', ' ') if volume_analysis else "N/A",
                               className=f"text-{'success' if 'BULLISH' in volume_analysis.get('vpt_signal', '') else ('danger' if 'DISTRIBUTION' in volume_analysis.get('vpt_signal', '') else 'muted')}" if volume_analysis else "text-muted"),
                        html.Small(f"VPT Score: {volume_analysis.get('vpt_avg_score', 0)}" if volume_analysis else "", className="text-muted")
                    ], width=3),
                    dbc.Col([
                        html.Strong("Consecutive High Vol"),
                        html.H3(f"{volume_analysis.get('consecutive_high_vol_days', 0)} hari" if volume_analysis else "N/A",
                               className=f"text-{'success' if volume_analysis.get('consecutive_high_vol_days', 0) >= 3 else 'muted'}" if volume_analysis else "text-muted"),
                        html.Small("RVOL > 1.2x berturut-turut", className="text-muted")
                    ], width=3),
                    dbc.Col([
                        html.Strong("Overall Score"),
                        html.H3(f"{volume_analysis.get('score', 50):.0f}" if volume_analysis else "N/A",
                               className=f"text-{score_color(volume_analysis.get('score', 50))}" if volume_analysis else "text-muted"),
                        html.Small(volume_analysis.get('signal', 'N/A').replace('_', ' ') if volume_analysis else "N/A", className="text-muted")
                    ], width=3),
                ]),
                html.Hr(),
                dbc.Row([
                    dbc.Col([
                        html.Strong("Volume Hari Ini: "),
                        html.Span(f"{volume_analysis.get('latest_volume', 0)/1e6:.1f}M lots" if volume_analysis else "N/A")
                    ], width=4),
                    dbc.Col([
                        html.Strong("Avg Volume 20D: "),
                        html.Span(f"{volume_analysis.get('avg_volume_20d', 0)/1e6:.1f}M lots" if volume_analysis else "N/A")
                    ], width=4),
                    dbc.Col([
                        html.Strong("Signal: "),
                        dbc.Badge(volume_analysis.get('signal', 'N/A').replace('_', ' ') if volume_analysis else "N/A",
                                 color="success" if volume_analysis.get('signal', '') in ['HIGH_ACTIVITY', 'ABOVE_NORMAL'] else "secondary")
                    ], width=4),
                ]),
                html.Hr(),
                html.Div([
                    html.H6("Cara Membaca Volume Analysis:", className="text-info mb-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.Strong("RVOL (Relative Volume)"), html.Br(),
                                "Volume hari ini / Avg 20 hari", html.Br(),
                                "• >= 2.0x = Very High (aktivitas tinggi)", html.Br(),
                                "• >= 1.5x = High (di atas normal)", html.Br(),
                                "• >= 1.2x = Above Average", html.Br(),
                                "• < 0.8x = Low (aktivitas rendah)"
                            ], className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.Small([
                                html.Strong("Volume-Price Trend (VPT)"), html.Br(),
                                "Kombinasi volume dan arah harga", html.Br(),
                                "• Vol ↑ + Price ↑ = BULLISH (+)", html.Br(),
                                "• Vol ↑ + Price ↓ = DISTRIBUTION (-)", html.Br(),
                                "• Vol ↓ + Price ↑ = WEAK RALLY", html.Br(),
                                "• Vol ↓ + Price ↓ = CONSOLIDATION"
                            ], className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.Small([
                                html.Strong("Interpretasi"), html.Br(),
                                "RVOL tinggi + VPT Bullish = Strong Buy", html.Br(),
                                "RVOL tinggi + VPT Distribution = Waspada", html.Br(),
                                "RVOL rendah = Kurang menarik", html.Br(),
                                html.Span("Consecutive High Vol >= 3 hari = Strong interest!", className="text-success")
                            ], className="text-muted")
                        ], width=4),
                    ]),
                ])
            ])
        ], className="mb-4", color="dark", outline=True) if volume_analysis else None,

        # ========== SMART MONEY SCORING REFERENCE ==========
        dbc.Card([
            dbc.CardHeader(html.H5("Scoring Reference", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6("Smart Money Scoring", className="text-info"),
                        html.Table([
                            html.Thead(html.Tr([
                                html.Th("Kondisi"),
                                html.Th("Skor"),
                                html.Th("Interpretasi")
                            ])),
                            html.Tbody([
                                html.Tr([html.Td("Vol +50%, Freq turun"), html.Td("+3"), html.Td("Strong Accumulation", className="text-success")]),
                                html.Tr([html.Td("Vol +50%, Freq <+20%"), html.Td("+2"), html.Td("Moderate Accumulation")]),
                                html.Tr([html.Td("Vol naik = Freq naik"), html.Td("+1"), html.Td("Mixed (retail+bandar)")]),
                                html.Tr([html.Td("Vol turun, Freq turun"), html.Td("0"), html.Td("No Signal")]),
                                html.Tr([html.Td("Vol +50%, Freq +50%"), html.Td("-1"), html.Td("Retail FOMO", className="text-danger")]),
                            ])
                        ], className="table table-sm table-dark")
                    ], width=6),
                    dbc.Col([
                        html.H6("Foreign Flow Scoring", className="text-info"),
                        html.P("Formula: (Direction x 10) + (Momentum x 20) + (Consistency x 7)"),
                        html.Ul([
                            html.Li("Direction: +1 (inflow), -1 (outflow), 0 (flat)"),
                            html.Li("Momentum: perubahan dari kemarin (+/- 1)"),
                            html.Li("Consistency: hari berturut-turut (max 10)"),
                        ], className="small"),
                        html.Hr(),
                        html.H6("Composite Score Weights", className="text-info"),
                        html.Ul([
                            html.Li("Broker Sensitivity: 25%"),
                            html.Li("Foreign Flow: 25%"),
                            html.Li("Smart Money: 20%"),
                            html.Li("Price Position: 15%"),
                            html.Li("Accumulation Phase: 15%"),
                        ], className="small")
                    ], width=6)
                ])
            ])
        ])
    ])


def create_enhanced_alerts_list(alerts):
    """Create enhanced alerts list with priority indicators and broker type info"""
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
            broker_color = get_broker_color(broker_code)

            # Map broker type to label
            type_labels = {
                'FOREIGN': ('ASING', 'danger'),
                'BUMN': ('BUMN', 'success'),
                'LOCAL': ('LOKAL', 'secondary')
            }
            type_label, type_badge_color = type_labels.get(broker_type, ('LOKAL', 'secondary'))

            broker_badge = html.Span([
                html.Span(
                    broker_code,
                    className="badge me-1",
                    style={
                        'backgroundColor': broker_color,
                        'color': 'white',
                        'fontSize': '0.8rem'
                    }
                ),
                dbc.Badge(type_label, color=type_badge_color, className="me-2", style={'fontSize': '0.65rem'})
            ])

        alert_items.append(
            dbc.Alert([
                dbc.Row([
                    dbc.Col([
                        dbc.Badge(alert.get('priority', 'N/A'), color=priority_color, className="me-2"),
                        dbc.Badge(alert.get('type', '').replace('_', ' '), color="light", text_color="dark", className="me-2"),
                        broker_badge if broker_badge else None,
                    ], width=4),
                    dbc.Col([
                        html.Strong(alert.get('message', '')),
                        html.Br(),
                        html.Small(alert.get('detail', ''), className="text-muted")
                    ], width=8)
                ])
            ], color=priority_color, className="mb-2 py-2")
        )

    return html.Div(alert_items)


def create_broker_sensitivity_table(data):
    """Create broker sensitivity ranking table with Lead Time, Win Rate, and Broker Type"""
    if not data or not data.get('brokers'):
        return html.Div("No sensitivity data available")

    brokers = data['brokers'][:20]  # Top 20
    lookback_days = data.get('lookback_days', 60)  # Get lookback period

    # Add broker type info
    table_data = []
    for i, b in enumerate(brokers):
        broker_info = get_broker_info(b['broker_code'])
        table_data.append({
            'Rank': i + 1,
            'Broker': b['broker_code'],
            'Tipe': broker_info['type_name'],
            'Win Rate': f"{b['win_rate']:.0f}%",
            'Lead Time': f"{b['avg_lead_time']:.1f}d",
            'Correlation': f"{b['correlation']:.0f}%",
            'Score': f"{b['sensitivity_score']:.0f}",
            'Accum Days': b['accum_days'],
            'Signals': b['successful_signals']
        })

    # Style conditional based on broker type
    style_data_conditional = [
        {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
        {'if': {'filter_query': '{Score} >= 40'}, 'backgroundColor': '#1a472a'},
        {'if': {'filter_query': '{Tipe} = Asing'}, 'backgroundColor': 'rgba(220, 53, 69, 0.2)'},
        {'if': {'filter_query': '{Tipe} = BUMN/Pemerintah'}, 'backgroundColor': 'rgba(40, 167, 69, 0.2)'},
        {'if': {'filter_query': '{Tipe} = Lokal'}, 'backgroundColor': 'rgba(111, 66, 193, 0.2)'},
    ]

    table = dash_table.DataTable(
        data=table_data,
        columns=[
            {'name': '#', 'id': 'Rank'},
            {'name': 'Broker', 'id': 'Broker'},
            {'name': 'Tipe', 'id': 'Tipe'},
            {'name': 'Win Rate', 'id': 'Win Rate'},
            {'name': 'Lead Time', 'id': 'Lead Time'},
            {'name': 'Correlation', 'id': 'Correlation'},
            {'name': 'Score', 'id': 'Score'},
            {'name': 'Accum Days', 'id': 'Accum Days'},
            {'name': 'Signals', 'id': 'Signals'}
        ],
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'backgroundColor': '#303030',
            'color': 'white',
            'padding': '8px',
            'minWidth': '70px',
            'fontSize': '12px'
        },
        style_header={
            'backgroundColor': '#404040',
            'fontWeight': 'bold'
        },
        style_data_conditional=style_data_conditional,
        sort_action='native',
        page_size=10
    )

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

def create_dashboard_page(stock_code='CDIA'):
    return html.Div([
        # Header with stock info
        dbc.Row([
            dbc.Col([
                html.H4(f"Dashboard - {stock_code}", className="mb-0"),
            ], width=6),
            dbc.Col([
                dbc.Button("Refresh Data", id="refresh-btn", color="primary", size="sm"),
                html.Span(id="last-refresh", className="ms-3 text-muted small")
            ], width=6, className="text-end")
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

        # Row 1: Quick Sentiment + Key Metrics
        dbc.Row([
            dbc.Col([
                html.Div(id="sentiment-container")
            ], width=6),
            dbc.Col([
                html.Div(id="metrics-container")
            ], width=6),
        ], className="mb-3"),

        # Row 2: Broker Movement Alert
        html.Div(id="movement-container"),

        # Row 3: Broker Sensitivity Pattern
        html.Div(id="sensitivity-container"),

        # Row 4: Broker Watchlist
        html.Div(id="watchlist-container"),

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

# ============================================================
# PAGE: BROKER RANKING (Dynamic)
# ============================================================

def create_ranking_page(stock_code='CDIA'):
    broker_df = get_broker_data(stock_code)

    if broker_df.empty:
        return html.Div([
            dbc.Alert(f"Tidak ada data broker untuk {stock_code}", color="warning"),
            html.P("Silakan upload data terlebih dahulu di menu Upload Data")
        ])

    # Overall ranking
    overall = broker_df.groupby('broker_code').agg({
        'buy_value': 'sum',
        'sell_value': 'sum',
        'net_value': 'sum',
        'buy_lot': 'sum',
        'sell_lot': 'sum',
        'net_lot': 'sum',
        'date': 'count'
    }).reset_index()
    overall.columns = ['Broker', 'Total Buy', 'Total Sell', 'Net Value',
                       'Buy Lot', 'Sell Lot', 'Net Lot', 'Days Active']
    overall = overall.sort_values('Net Value', ascending=False)

    # Get Avg Buy data
    avg_buy_df = get_broker_avg_buy(stock_code, days=60)
    avg_buy_dict = {}
    if not avg_buy_df.empty:
        avg_buy_dict = dict(zip(avg_buy_df['broker_code'], avg_buy_df['avg_buy_price']))

    overall['Net (B)'] = overall['Net Value'].apply(lambda x: f"{x/1e9:,.1f}")
    overall['Buy (B)'] = overall['Total Buy'].apply(lambda x: f"{x/1e9:,.1f}")
    overall['Sell (B)'] = overall['Total Sell'].apply(lambda x: f"{x/1e9:,.1f}")
    overall['Avg Buy'] = overall['Broker'].apply(lambda x: f"Rp {avg_buy_dict.get(x, 0):,.0f}" if avg_buy_dict.get(x, 0) > 0 else "-")
    # Add broker type classification
    overall['Tipe'] = overall['Broker'].apply(lambda x: get_broker_info(x)['type_name'])

    accumulators = overall[overall['Net Value'] > 0].head(20)
    distributors = overall[overall['Net Value'] < 0].head(20)

    # Style conditional based on broker type
    style_data_conditional = [
        {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
        {'if': {'filter_query': '{Tipe} = Asing'}, 'backgroundColor': 'rgba(220, 53, 69, 0.2)'},
        {'if': {'filter_query': '{Tipe} = BUMN/Pemerintah'}, 'backgroundColor': 'rgba(40, 167, 69, 0.2)'},
        {'if': {'filter_query': '{Tipe} = Lokal'}, 'backgroundColor': 'rgba(111, 66, 193, 0.2)'},
    ]

    # Legend
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
    ], className="mb-3")

    # Get date range
    date_range = f"{broker_df['date'].min().strftime('%d %b %Y')} - {broker_df['date'].max().strftime('%d %b %Y')}"

    return html.Div([
        html.H4(f"Broker Ranking - {stock_code}", className="mb-2"),
        html.P(f"Period: {date_range}", className="text-muted mb-2"),
        broker_legend,

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Top 20 Accumulators", className="text-success mb-0")),
                    dbc.CardBody([
                        dash_table.DataTable(
                            data=accumulators[['Broker', 'Tipe', 'Net (B)', 'Buy (B)', 'Avg Buy', 'Days Active']].to_dict('records'),
                            columns=[
                                {'name': 'Broker', 'id': 'Broker'},
                                {'name': 'Tipe', 'id': 'Tipe'},
                                {'name': 'Net (B)', 'id': 'Net (B)'},
                                {'name': 'Buy (B)', 'id': 'Buy (B)'},
                                {'name': 'Avg Buy', 'id': 'Avg Buy'},
                                {'name': 'Days', 'id': 'Days Active'},
                            ],
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '8px', 'fontSize': '12px'},
                            style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
                            style_data_conditional=style_data_conditional,
                            page_size=20
                        )
                    ])
                ], className="h-100")
            ], width=6),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Top 20 Distributors", className="text-danger mb-0")),
                    dbc.CardBody([
                        dash_table.DataTable(
                            data=distributors[['Broker', 'Tipe', 'Net (B)', 'Buy (B)', 'Avg Buy', 'Days Active']].to_dict('records'),
                            columns=[
                                {'name': 'Broker', 'id': 'Broker'},
                                {'name': 'Tipe', 'id': 'Tipe'},
                                {'name': 'Net (B)', 'id': 'Net (B)'},
                                {'name': 'Buy (B)', 'id': 'Buy (B)'},
                                {'name': 'Avg Buy', 'id': 'Avg Buy'},
                                {'name': 'Days', 'id': 'Days Active'},
                            ],
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'left', 'backgroundColor': '#303030', 'color': 'white', 'padding': '8px', 'fontSize': '12px'},
                            style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
                            style_data_conditional=style_data_conditional,
                            page_size=20
                        )
                    ])
                ], className="h-100")
            ], width=6),
        ], className="mb-4"),

        # Distribution Chart
        dbc.Card([
            dbc.CardHeader("Broker Net Flow Distribution"),
            dbc.CardBody([
                dcc.Graph(figure=create_broker_distribution_chart(overall), config={'displayModeBar': False})
            ])
        ])
    ])


def create_broker_distribution_chart(df):
    top_acc = df[df['Net Value'] > 0].head(15)
    top_dist = df[df['Net Value'] < 0].head(15)
    combined = pd.concat([top_acc, top_dist]).sort_values('Net Value', ascending=True)
    colors = ['#dc3545' if x < 0 else '#28a745' for x in combined['Net Value']]

    fig = go.Figure(go.Bar(
        x=combined['Net Value'] / 1e9,
        y=combined['Broker'],
        orientation='h',
        marker_color=colors,
        text=[f"{x/1e9:,.0f}B" for x in combined['Net Value']],
        textposition='outside'
    ))
    fig.update_layout(template='plotly_dark', height=600, xaxis_title='Net Value (Billion Rp)', showlegend=False)
    return fig

# ============================================================
# PAGE: ALERTS (Dynamic)
# ============================================================

def create_alerts_page(stock_code='CDIA'):
    broker_df = get_broker_data(stock_code)

    if broker_df.empty:
        return html.Div([
            dbc.Alert(f"Tidak ada data untuk {stock_code}", color="warning")
        ])

    alerts = check_accumulation_alerts(broker_df, stock_code)
    broker_analysis = analyze_broker_accumulation(broker_df, stock_code)

    return html.Div([
        html.H4(f"Accumulation Alerts - {stock_code}", className="mb-4"),

        # Broker Type Legend
        dbc.Card([
            dbc.CardBody([
                html.Span("Legenda Warna Broker: ", className="fw-bold me-3"),
                html.Span([
                    html.Span("ASING", className="badge me-1", style={'backgroundColor': '#dc3545', 'color': 'white'}),
                    html.Small("(Foreign)", className="text-muted me-3"),
                ]),
                html.Span([
                    html.Span("BUMN", className="badge me-1", style={'backgroundColor': '#28a745', 'color': 'white'}),
                    html.Small("(Government)", className="text-muted me-3"),
                ]),
                html.Span([
                    html.Span("LOKAL", className="badge me-1", style={'backgroundColor': '#6f42c1', 'color': 'white'}),
                    html.Small("(Local)", className="text-muted"),
                ]),
            ], className="py-2")
        ], className="mb-3", color="dark", outline=True),

        dbc.Card([
            dbc.CardHeader([
                html.H5("Active Accumulation Signals", className="mb-0"),
                dbc.Badge(f"{len(alerts)} Active", color="warning", className="ms-2")
            ]),
            dbc.CardBody([
                create_alerts_list(alerts) if alerts else dbc.Alert("No active alerts", color="secondary")
            ])
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader("Broker Accumulation Patterns"),
            dbc.CardBody([
                create_accumulation_table(broker_analysis, stock_code) if not broker_analysis.empty else "No data"
            ])
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader("Recent 7-Day Activity Heatmap"),
            dbc.CardBody([
                create_recent_activity_chart(broker_df)
            ])
        ])
    ])


def create_alerts_list(alerts):
    alert_items = []
    for alert in alerts:
        color = "warning" if alert['streak_days'] >= 5 else "info"
        broker_code = alert['broker_code']

        # Get broker type and color
        broker_type = get_broker_type(broker_code)
        broker_color = get_broker_color(broker_code)

        # Map broker type to label
        type_labels = {
            'FOREIGN': ('ASING', 'danger'),
            'BUMN': ('BUMN', 'success'),
            'LOCAL': ('LOKAL', 'secondary')
        }
        type_label, type_badge_color = type_labels.get(broker_type, ('LOKAL', 'secondary'))

        alert_items.append(
            dbc.Alert([
                dbc.Row([
                    dbc.Col([
                        html.H5([
                            html.Span(
                                broker_code,
                                className="badge me-2",
                                style={
                                    'backgroundColor': broker_color,
                                    'color': 'white',
                                    'fontSize': '0.9rem',
                                    'padding': '5px 10px',
                                    'borderRadius': '4px'
                                }
                            ),
                            dbc.Badge(type_label, color=type_badge_color, className="me-2", style={'fontSize': '0.7rem'}),
                            f"Akumulasi {alert['streak_days']} hari berturut-turut"
                        ]),
                        html.P([html.Strong("Total Net: "), f"Rp {alert['total_net_value']/1e9:.1f} Miliar"], className="mb-0")
                    ], width=9),
                    dbc.Col([
                        html.Div([
                            html.Span(f"{alert['streak_days']}", style={'fontSize': '2rem', 'fontWeight': 'bold'}),
                            html.Br(),
                            html.Small("days")
                        ], className="text-center")
                    ], width=3)
                ])
            ], color=color, className="mb-2")
        )
    return html.Div(alert_items)


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

    return dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader(f"{stock_code} Price"),
            dbc.CardBody([
                html.H3(f"Rp {latest_price:,.0f}"),
                html.P(f"{price_change:+.2f}%", className="text-success" if price_change >= 0 else "text-danger")
            ])
        ], color="dark", outline=True), width=3),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Market Phase"),
            dbc.CardBody([
                html.H3(phase['phase'].upper()),
                html.P(f"Range: {phase['details'].get('range_percent', 0):.1f}%")
            ])
        ], color="dark", outline=True), width=3),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Top Accumulator Today"),
            dbc.CardBody([html.H3(top_acc_name), html.P(f"Net: Rp {top_acc_val:.1f}B")])
        ], color="dark", outline=True), width=3),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Active Alerts"),
            dbc.CardBody([html.H3(f"{len(alerts)}"), html.P("Accumulation signals")])
        ], color="warning" if alerts else "dark", outline=True), width=3),
    ], className="mb-4")


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
    return dcc.Graph(figure=fig)


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

    # Get position data
    position_df = calculate_broker_current_position(stock_code)

    if position_df.empty:
        return html.Div([
            dbc.Alert([
                html.H5("Data IPO Position Belum Tersedia", className="alert-heading"),
                html.P(f"Tidak ada data posisi broker dari IPO untuk {stock_code}."),
                html.Hr(),
                html.P([
                    "Untuk menggunakan fitur ini, upload file Excel dengan data IPO di kolom Z-AH.",
                    html.Br(),
                    "Format: buy, buy_val, buy_lot, buy_avg, sell, sell_val, sell_lot, sell_avg"
                ], className="mb-0")
            ], color="warning"),
            dbc.Button("Upload Data", href="/upload", color="primary")
        ])

    # Get IPO period info
    ipo_df = get_ipo_position(stock_code)
    period_start = ipo_df['period_start'].iloc[0] if not ipo_df.empty and 'period_start' in ipo_df.columns else None
    period_end = ipo_df['period_end'].iloc[0] if not ipo_df.empty and 'period_end' in ipo_df.columns else None
    period_str = f"{period_start.strftime('%d %b %Y') if period_start else 'N/A'} - {period_end.strftime('%d %b %Y') if period_end else 'N/A'}"

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
        html.H4([
            html.I(className="fas fa-warehouse me-2"),
            f"Broker Position Analysis - {stock_code}"
        ], className="mb-2"),
        html.P([
            f"Data IPO: {period_str} | ",
            f"Current Price: Rp {current_price:,.0f}"
        ], className="text-muted mb-4"),

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
                        dash_table.DataTable(
                            data=top_holders[[
                                'broker_code', 'broker_type', 'net_lot', 'ipo_avg_buy', 'floating_pnl_pct'
                            ]].to_dict('records') if not top_holders.empty else [],
                            columns=[
                                {'name': 'Broker', 'id': 'broker_code'},
                                {'name': 'Type', 'id': 'broker_type'},
                                {'name': 'Net Lot', 'id': 'net_lot', 'type': 'numeric',
                                 'format': {'specifier': ',.0f'}},
                                {'name': 'Avg Buy', 'id': 'ipo_avg_buy', 'type': 'numeric',
                                 'format': {'specifier': ',.0f'}},
                                {'name': 'Float P/L', 'id': 'floating_pnl_pct', 'type': 'numeric',
                                 'format': {'specifier': '+.1f'}},
                            ],
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'center', 'padding': '8px',
                                       'backgroundColor': '#303030', 'color': 'white'},
                            style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
                            style_data_conditional=[
                                {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
                                # Broker type colors
                                {'if': {'filter_query': '{broker_type} = FOREIGN', 'column_id': 'broker_code'},
                                 'color': '#dc3545', 'fontWeight': 'bold'},
                                {'if': {'filter_query': '{broker_type} = FOREIGN', 'column_id': 'broker_type'},
                                 'backgroundColor': '#dc3545', 'color': 'white'},
                                {'if': {'filter_query': '{broker_type} = BUMN', 'column_id': 'broker_code'},
                                 'color': '#28a745', 'fontWeight': 'bold'},
                                {'if': {'filter_query': '{broker_type} = BUMN', 'column_id': 'broker_type'},
                                 'backgroundColor': '#28a745', 'color': 'white'},
                                {'if': {'filter_query': '{broker_type} = LOCAL', 'column_id': 'broker_code'},
                                 'color': '#6f42c1', 'fontWeight': 'bold'},
                                {'if': {'filter_query': '{broker_type} = LOCAL', 'column_id': 'broker_type'},
                                 'backgroundColor': '#6f42c1', 'color': 'white'},
                                # Float P/L colors
                                {'if': {'filter_query': '{floating_pnl_pct} > 0', 'column_id': 'floating_pnl_pct'},
                                 'color': '#00ff00'},
                                {'if': {'filter_query': '{floating_pnl_pct} < 0', 'column_id': 'floating_pnl_pct'},
                                 'color': '#ff4444'},
                            ],
                            page_size=10,
                        ),
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

                # Net Sellers
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-sign-out-alt me-2"),
                            "Top 10 Net Sellers"
                        ], className="mb-0 text-danger")
                    ]),
                    dbc.CardBody([
                        dash_table.DataTable(
                            data=top_sellers[[
                                'broker_code', 'broker_type', 'net_lot', 'total_sell_lot'
                            ]].to_dict('records') if not top_sellers.empty else [],
                            columns=[
                                {'name': 'Broker', 'id': 'broker_code'},
                                {'name': 'Type', 'id': 'broker_type'},
                                {'name': 'Net Lot', 'id': 'net_lot', 'type': 'numeric',
                                 'format': {'specifier': ',.0f'}},
                                {'name': 'Total Sell', 'id': 'total_sell_lot', 'type': 'numeric',
                                 'format': {'specifier': ',.0f'}},
                            ],
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'center', 'padding': '8px',
                                       'backgroundColor': '#303030', 'color': 'white'},
                            style_header={'backgroundColor': '#404040', 'fontWeight': 'bold'},
                            style_data_conditional=[
                                {'if': {'row_index': 'odd'}, 'backgroundColor': '#383838'},
                                # Broker type colors
                                {'if': {'filter_query': '{broker_type} = FOREIGN', 'column_id': 'broker_code'},
                                 'color': '#dc3545', 'fontWeight': 'bold'},
                                {'if': {'filter_query': '{broker_type} = FOREIGN', 'column_id': 'broker_type'},
                                 'backgroundColor': '#dc3545', 'color': 'white'},
                                {'if': {'filter_query': '{broker_type} = BUMN', 'column_id': 'broker_code'},
                                 'color': '#28a745', 'fontWeight': 'bold'},
                                {'if': {'filter_query': '{broker_type} = BUMN', 'column_id': 'broker_type'},
                                 'backgroundColor': '#28a745', 'color': 'white'},
                                {'if': {'filter_query': '{broker_type} = LOCAL', 'column_id': 'broker_code'},
                                 'color': '#6f42c1', 'fontWeight': 'bold'},
                                {'if': {'filter_query': '{broker_type} = LOCAL', 'column_id': 'broker_type'},
                                 'backgroundColor': '#6f42c1', 'color': 'white'},
                                # Net lot always red for sellers
                                {'if': {'column_id': 'net_lot'}, 'color': '#ff4444'},
                            ],
                            page_size=10,
                        ),
                        # Legend
                        html.Div([
                            html.Span([html.I(className="fas fa-circle me-1", style={"color": "#dc3545", "fontSize": "8px"}), "Asing "], className="me-3", style={"fontSize": "11px"}),
                            html.Span([html.I(className="fas fa-circle me-1", style={"color": "#28a745", "fontSize": "8px"}), "BUMN "], className="me-3", style={"fontSize": "11px"}),
                            html.Span([html.I(className="fas fa-circle me-1", style={"color": "#6f42c1", "fontSize": "8px"}), "Lokal "], style={"fontSize": "11px"}),
                        ], className="mt-2 mb-2"),
                        html.Hr(),
                        html.Small([
                            html.Strong("Cara Baca: "),
                            "Broker dengan Net Lot negatif = sudah menjual lebih banyak dari yang dibeli. ",
                            "Ini menunjukkan broker yang sudah keluar dari saham."
                        ], className="text-muted")
                    ])
                ])
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
                                html.Span(f" - {r['broker']}", className="text-muted"),
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
                            ], className="mb-3 text-center py-2", style={'backgroundColor': '#404040', 'borderRadius': '5px'}),
                        ]),

                        html.Hr(),

                        html.Div([
                            html.H6("Support Levels", className="text-success mb-2"),
                            html.Small("(Broker floating profit - will defend)", className="text-muted d-block mb-2"),
                            *([html.Div([
                                html.Span(f"Rp {s['price']:,.0f}", className="fw-bold"),
                                html.Span(f" - {s['broker']}", className="text-muted"),
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
                html.Small([
                    html.Strong("Cara Baca: "),
                    "Chart menunjukkan total lot yang dipegang di setiap range harga avg buy. ",
                    "Broker dengan avg buy di atas harga saat ini (floating loss) berpotensi menjual ",
                    "saat harga naik ke level avg buy mereka - ini menciptakan resistance."
                ], className="text-muted")
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
        xaxis_title="Avg Buy Price",
        yaxis_title="Total Lot",
        margin=dict(l=50, r=20, t=30, b=50)
    )

    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================
# MAIN LAYOUT
# ============================================================

# Render navbar sekali di layout (tidak re-render setiap URL change)
app.layout = html.Div([
    dcc.Store(id='selected-stock', data='CDIA', storage_type='session'),  # Persist across page navigation
    dcc.Location(id='url', refresh=False),
    create_navbar(),  # Navbar statis, tidak re-render
    dbc.Container(id='page-content', fluid=True)
])

# ============================================================
# CALLBACKS
# ============================================================

# Sync dropdown value dengan store (untuk saat page reload/initial load)
@app.callback(
    Output('stock-selector', 'value'),
    Input('selected-stock', 'data'),
    prevent_initial_call=True
)
def sync_dropdown_with_store(stored_value):
    """Sync dropdown dengan store untuk maintain selection"""
    return stored_value if stored_value else 'CDIA'

@app.callback(Output('selected-stock', 'data'), Input('stock-selector', 'value'))
def update_selected_stock(value):
    return value if value else 'CDIA'

@app.callback(
    [Output('page-content', 'children'), Output('selected-stock', 'data', allow_duplicate=True)],
    [Input('url', 'pathname'), Input('url', 'search')],
    [State('selected-stock', 'data')],
    prevent_initial_call='initial_duplicate'
)
def display_page(pathname, search, stored_stock):
    from urllib.parse import parse_qs

    # Parse query parameter ?stock=XXX
    stock_from_url = None
    if search:
        params = parse_qs(search.lstrip('?'))
        stock_from_url = params.get('stock', [None])[0]

    # Use URL param if provided, otherwise use stored value
    stock_code = stock_from_url or stored_stock or 'CDIA'

    # Route to appropriate page
    if pathname == '/':
        content = create_landing_page()
    elif pathname == '/dashboard':
        content = create_dashboard_page(stock_code)
    elif pathname == '/analysis':
        content = create_analysis_page(stock_code)
    elif pathname == '/bandarmology':
        content = create_bandarmology_page(stock_code)  # Legacy
    elif pathname == '/summary':
        content = create_summary_page(stock_code)  # Legacy
    elif pathname == '/ranking':
        content = create_ranking_page(stock_code)
    elif pathname == '/alerts':
        content = create_alerts_page(stock_code)
    elif pathname == '/position':
        content = create_position_page(stock_code)
    elif pathname == '/upload':
        content = create_upload_page()
    else:
        content = create_landing_page()

    # Return content and update store if stock from URL
    return content, stock_code

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

@app.callback(Output('broker-select', 'options'), [Input('url', 'pathname'), Input('selected-stock', 'data')])
def update_broker_options(pathname, stock_code):
    broker_df = get_broker_data(stock_code or 'CDIA')
    if broker_df.empty:
        return []
    top_brokers = broker_df.groupby('broker_code')['net_value'].sum().abs().nlargest(20).index.tolist()
    return [{'label': b, 'value': b} for b in top_brokers]

@app.callback(
    [Output("summary-cards", "children"), Output("price-chart-container", "children"),
     Output("flow-chart-container", "children"),
     Output("sentiment-container", "children"), Output("metrics-container", "children"),
     Output("movement-container", "children"), Output("sensitivity-container", "children"),
     Output("watchlist-container", "children"),
     Output("last-refresh", "children")],
    [Input("refresh-btn", "n_clicks"), Input('selected-stock', 'data')],
    prevent_initial_call=False
)
def refresh_dashboard(n_clicks, stock_code):
    stock_code = stock_code or 'CDIA'
    return (
        create_summary_cards(stock_code),
        create_price_chart(stock_code),
        create_broker_flow_chart(stock_code),
        # New sections replacing Top Brokers Summary
        create_quick_sentiment_summary(stock_code),
        create_key_metrics_compact(stock_code),
        create_broker_movement_alert(stock_code),
        create_broker_sensitivity_pattern(stock_code),
        create_broker_watchlist(stock_code),
        f"Refresh: {datetime.now().strftime('%H:%M:%S')}"
    )

@app.callback(Output("broker-detail-container", "children"), [Input("broker-select", "value"), Input('selected-stock', 'data')])
def update_broker_detail(broker_code, stock_code):
    if not broker_code:
        return html.Div("Select a broker")
    return create_broker_history_chart(broker_code, stock_code or 'CDIA')

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

        # Clean up
        try:
            os.remove(temp_path)
        except:
            pass  # Ignore cleanup errors

        status = dbc.Alert([
            html.H5("Import Berhasil!", className="alert-heading"),
            html.P([
                f"Stock: {stock_code}", html.Br(),
                f"File: {filename}", html.Br(),
                f"Price records: {price_count}", html.Br(),
                f"Broker records: {broker_count}"
            ])
        ], color="success")

        log = html.Div([
            html.P(f"[{datetime.now().strftime('%H:%M:%S')}] Imported {filename} for {stock_code}"),
            html.P(f"  - Price: {price_count} records, Broker: {broker_count} records", className="text-muted small")
        ])

        print(f"[UPLOAD] SUCCESS - {stock_code}: {price_count} price, {broker_count} broker records")

        return status, create_stocks_list(), log

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
# RUN SERVER
# ============================================================

if __name__ == '__main__':
    print("Starting Stock Broker Analysis Dashboard...")
    print("Open http://localhost:8050 in your browser")
    app.run(debug=True, host='0.0.0.0', port=8050)
