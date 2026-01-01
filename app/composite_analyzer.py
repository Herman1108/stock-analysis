"""
Composite Stock Analysis Module
Comprehensive Bandarmology + Sensitivity Analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from functools import lru_cache
import hashlib
from database import execute_query
from analyzer import get_price_data, get_broker_data, calculate_optimal_lookback_days
from broker_config import (
    get_broker_type, get_broker_color, get_broker_info,
    classify_brokers, is_foreign_broker, FOREIGN_BROKER_CODES, BUMN_BROKER_CODES
)

# Simple cache for analysis results (expires after 5 minutes)
_analysis_cache = {}
_cache_timeout = 300  # 5 minutes

def _get_cache_key(stock_code: str) -> str:
    """Generate cache key based on stock code and latest data date"""
    try:
        price_df = get_price_data(stock_code)
        if not price_df.empty:
            latest_date = price_df['date'].max().strftime('%Y%m%d')
            return f"{stock_code}_{latest_date}"
    except:
        pass
    return f"{stock_code}_default"

def _is_cache_valid(cache_key: str) -> bool:
    """Check if cache is still valid"""
    if cache_key not in _analysis_cache:
        return False
    cached_time = _analysis_cache[cache_key].get('_cached_at', 0)
    return (datetime.now().timestamp() - cached_time) < _cache_timeout

def clear_analysis_cache(stock_code: str = None):
    """Clear analysis cache"""
    global _analysis_cache
    if stock_code:
        keys_to_remove = [k for k in _analysis_cache if k.startswith(stock_code)]
        for k in keys_to_remove:
            del _analysis_cache[k]
    else:
        _analysis_cache = {}


# ============================================================
# PRICE MOVEMENT TRACKING (Pergerakan Harga Multi-Periode)
# ============================================================

def calculate_price_movements(stock_code: str = 'CDIA') -> Dict:
    """
    Calculate price movements for multiple time periods.

    Periods:
    - 1D: 1 trading day
    - 1W: 5 trading days (1 week)
    - 2W: 10 trading days (2 weeks)
    - 3W: 15 trading days (3 weeks)
    - 1M: 22 trading days (1 month)

    Returns:
        Dict with price movements and percentage changes for each period
    """
    price_df = get_price_data(stock_code)

    if price_df.empty:
        return {'error': 'No price data'}

    # Sort by date descending (latest first)
    price_df = price_df.sort_values('date', ascending=False).reset_index(drop=True)

    # Convert Decimal to float
    for col in ['close_price', 'open_price', 'high_price', 'low_price', 'volume', 'value']:
        if col in price_df.columns:
            price_df[col] = price_df[col].astype(float)

    current_price = float(price_df.iloc[0]['close_price'])
    current_date = price_df.iloc[0]['date']

    # Define periods (trading days)
    periods = {
        '1D': 1,
        '1W': 5,
        '2W': 10,
        '3W': 15,
        '1M': 22,
    }

    movements = {
        'current_price': current_price,
        'current_date': current_date,
        'periods': {}
    }

    for period_name, days in periods.items():
        if len(price_df) > days:
            past_price = float(price_df.iloc[days]['close_price'])
            past_date = price_df.iloc[days]['date']
            change = current_price - past_price
            change_pct = (change / past_price) * 100 if past_price > 0 else 0

            movements['periods'][period_name] = {
                'past_price': past_price,
                'past_date': past_date,
                'change': change,
                'change_pct': change_pct,
                'direction': 'up' if change > 0 else ('down' if change < 0 else 'flat')
            }
        else:
            movements['periods'][period_name] = {
                'past_price': None,
                'past_date': None,
                'change': None,
                'change_pct': None,
                'direction': 'N/A'
            }

    return movements


def calculate_broker_flow_by_period(stock_code: str = 'CDIA', broker_codes: List[str] = None) -> Dict:
    """
    Calculate broker net flow for multiple time periods.

    Args:
        stock_code: Stock code
        broker_codes: List of broker codes to track (if None, tracks all)

    Returns:
        Dict with broker flows for each period
    """
    broker_df = get_broker_data(stock_code)

    if broker_df.empty:
        return {'error': 'No broker data'}

    # Convert Decimal to float
    for col in ['net_value', 'buy_value', 'sell_value', 'net_lot']:
        if col in broker_df.columns:
            broker_df[col] = broker_df[col].astype(float)

    # Get latest date
    latest_date = broker_df['date'].max()

    # Define periods (calendar days for query)
    periods = {
        '1D': 1,
        '1W': 7,
        '2W': 14,
        '3W': 21,
        '1M': 30,
    }

    result = {
        'latest_date': latest_date,
        'periods': {}
    }

    for period_name, days in periods.items():
        cutoff_date = latest_date - timedelta(days=days)
        period_df = broker_df[broker_df['date'] > cutoff_date]

        if period_df.empty:
            result['periods'][period_name] = {'total_net': 0, 'brokers': {}}
            continue

        # Filter by specific brokers if provided
        if broker_codes:
            period_df = period_df[period_df['broker_code'].isin(broker_codes)]

        # Aggregate by broker
        broker_agg = period_df.groupby('broker_code').agg({
            'net_value': 'sum',
            'buy_value': 'sum',
            'sell_value': 'sum',
        }).reset_index()

        # Add broker type
        broker_agg['broker_type'] = broker_agg['broker_code'].apply(get_broker_type)
        broker_agg['broker_color'] = broker_agg['broker_code'].apply(get_broker_color)

        result['periods'][period_name] = {
            'total_net': broker_agg['net_value'].sum(),
            'brokers': broker_agg.to_dict('records')
        }

    return result


def calculate_foreign_flow_by_period(stock_code: str = 'CDIA') -> Dict:
    """
    Calculate foreign broker net flow for multiple time periods.
    Uses dynamic classification from broker_config.

    Returns:
        Dict with foreign flow for each period
    """
    broker_df = get_broker_data(stock_code)

    if broker_df.empty:
        return {'error': 'No broker data'}

    # Convert Decimal to float
    for col in ['net_value', 'buy_value', 'sell_value', 'net_lot']:
        if col in broker_df.columns:
            broker_df[col] = broker_df[col].astype(float)

    # Add broker classification
    broker_df['broker_type'] = broker_df['broker_code'].apply(get_broker_type)

    # Filter foreign brokers
    foreign_df = broker_df[broker_df['broker_type'] == 'FOREIGN']

    if foreign_df.empty:
        return {
            'message': 'No foreign broker activity',
            'periods': {p: {'net_flow': 0, 'buy_value': 0, 'sell_value': 0, 'top_buyers': [], 'top_sellers': []}
                       for p in ['1D', '1W', '2W', '3W', '1M']}
        }

    latest_date = broker_df['date'].max()

    periods = {
        '1D': 1,
        '1W': 7,
        '2W': 14,
        '3W': 21,
        '1M': 30,
    }

    result = {
        'latest_date': latest_date,
        'periods': {}
    }

    for period_name, days in periods.items():
        cutoff_date = latest_date - timedelta(days=days)
        period_df = foreign_df[foreign_df['date'] > cutoff_date]

        if period_df.empty:
            result['periods'][period_name] = {
                'net_flow': 0,
                'buy_value': 0,
                'sell_value': 0,
                'top_buyers': [],
                'top_sellers': []
            }
            continue

        # Aggregate
        broker_agg = period_df.groupby('broker_code').agg({
            'net_value': 'sum',
            'buy_value': 'sum',
            'sell_value': 'sum',
        }).reset_index()

        # Top buyers and sellers
        top_buyers = broker_agg.nlargest(3, 'net_value')[['broker_code', 'net_value']].to_dict('records')
        top_sellers = broker_agg.nsmallest(3, 'net_value')[['broker_code', 'net_value']].to_dict('records')

        result['periods'][period_name] = {
            'net_flow': broker_agg['net_value'].sum(),
            'buy_value': broker_agg['buy_value'].sum(),
            'sell_value': broker_agg['sell_value'].sum(),
            'top_buyers': top_buyers,
            'top_sellers': top_sellers
        }

    return result


def calculate_sensitive_broker_flow_by_period(stock_code: str = 'CDIA', sensitive_brokers: List[str] = None) -> Dict:
    """
    Calculate sensitive broker net flow for multiple time periods.

    Args:
        stock_code: Stock code
        sensitive_brokers: List of sensitive broker codes (if None, will be calculated)

    Returns:
        Dict with sensitive broker flow for each period
    """
    # If no sensitive brokers provided, calculate them
    if sensitive_brokers is None:
        sens_analysis = calculate_broker_sensitivity_advanced(stock_code)
        if 'error' in sens_analysis:
            return {'error': sens_analysis['error']}

        # Get top 10 sensitive brokers
        sensitive_brokers = [b['broker'] for b in sens_analysis.get('sensitive_brokers', [])[:10]]

    if not sensitive_brokers:
        return {'error': 'No sensitive brokers found'}

    broker_df = get_broker_data(stock_code)

    if broker_df.empty:
        return {'error': 'No broker data'}

    # Convert Decimal to float
    for col in ['net_value', 'buy_value', 'sell_value', 'net_lot']:
        if col in broker_df.columns:
            broker_df[col] = broker_df[col].astype(float)

    # Filter sensitive brokers
    sens_df = broker_df[broker_df['broker_code'].isin(sensitive_brokers)]

    if sens_df.empty:
        return {'error': 'No sensitive broker activity'}

    latest_date = broker_df['date'].max()

    periods = {
        '1D': 1,
        '1W': 7,
        '2W': 14,
        '3W': 21,
        '1M': 30,
    }

    result = {
        'latest_date': latest_date,
        'sensitive_brokers': sensitive_brokers,
        'periods': {}
    }

    for period_name, days in periods.items():
        cutoff_date = latest_date - timedelta(days=days)
        period_df = sens_df[sens_df['date'] > cutoff_date]

        if period_df.empty:
            result['periods'][period_name] = {
                'net_flow': 0,
                'buy_value': 0,
                'sell_value': 0,
                'broker_details': []
            }
            continue

        # Aggregate by broker
        broker_agg = period_df.groupby('broker_code').agg({
            'net_value': 'sum',
            'buy_value': 'sum',
            'sell_value': 'sum',
        }).reset_index()

        # Add broker type info
        broker_agg['broker_type'] = broker_agg['broker_code'].apply(get_broker_type)
        broker_agg['broker_color'] = broker_agg['broker_code'].apply(get_broker_color)

        result['periods'][period_name] = {
            'net_flow': broker_agg['net_value'].sum(),
            'buy_value': broker_agg['buy_value'].sum(),
            'sell_value': broker_agg['sell_value'].sum(),
            'broker_details': broker_agg.sort_values('net_value', ascending=False).to_dict('records')
        }

    return result


def get_multi_period_summary(stock_code: str = 'CDIA') -> Dict:
    """
    Get comprehensive multi-period summary including:
    - Price movements
    - Foreign flow
    - Sensitive broker flow

    This is the main function to call for the dashboard.
    """
    # Get price movements
    price_movements = calculate_price_movements(stock_code)

    # Get foreign flow
    foreign_flow = calculate_foreign_flow_by_period(stock_code)

    # Get sensitive broker flow
    sensitive_flow = calculate_sensitive_broker_flow_by_period(stock_code)

    return {
        'price': price_movements,
        'foreign': foreign_flow,
        'sensitive': sensitive_flow,
        'periods': ['1D', '1W', '2W', '3W', '1M'],
        'period_labels': {
            '1D': '1 Hari',
            '1W': '1 Minggu',
            '2W': '2 Minggu',
            '3W': '3 Minggu',
            '1M': '1 Bulan'
        }
    }


# ============================================================
# BROKER AVG BUY ANALYSIS (Rata-rata harga beli per broker)
# ============================================================

def get_broker_avg_buy(stock_code: str = 'CDIA', days: int = 30) -> pd.DataFrame:
    """
    Hitung rata-rata harga beli (Avg Buy) per broker.

    Avg Buy menunjukkan harga rata-rata broker membeli saham.
    Jika harga sekarang < Avg Buy broker besar, artinya broker tersebut
    sedang floating loss dan mungkin akan averaging down atau cut loss.

    Args:
        stock_code: Kode saham
        days: Periode analisis (default 30 hari)

    Returns:
        DataFrame dengan kolom: broker_code, total_buy_value, total_buy_lot, avg_buy_price
    """
    query = """
        SELECT
            broker_code,
            SUM(buy_value) as total_buy_value,
            SUM(buy_lot) as total_buy_lot,
            CASE WHEN SUM(buy_lot) > 0
                THEN SUM(buy_value) / SUM(buy_lot) / 100
                ELSE 0
            END as avg_buy_price,
            SUM(sell_value) as total_sell_value,
            SUM(sell_lot) as total_sell_lot,
            CASE WHEN SUM(sell_lot) > 0
                THEN SUM(sell_value) / SUM(sell_lot) / 100
                ELSE 0
            END as avg_sell_price,
            SUM(net_value) as net_value,
            SUM(net_lot) as net_lot
        FROM broker_summary
        WHERE stock_code = %s
          AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY broker_code
        HAVING SUM(buy_lot) > 0
        ORDER BY SUM(buy_value) DESC
    """
    results = execute_query(query, (stock_code, days))

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # Convert Decimal columns to float
    numeric_cols = ['total_buy_value', 'total_buy_lot', 'avg_buy_price',
                    'total_sell_value', 'total_sell_lot', 'avg_sell_price',
                    'net_value', 'net_lot']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)

    return df


def analyze_avg_buy_position(stock_code: str = 'CDIA', current_price: float = None) -> Dict:
    """
    Analisis posisi Avg Buy broker relatif terhadap harga sekarang.

    Interpretasi:
    - Broker dengan Avg Buy > Current Price = Floating Profit (sudah untung)
    - Broker dengan Avg Buy < Current Price = Floating Loss (masih rugi)

    Jika banyak broker besar floating loss, potensi:
    - Averaging down (beli lagi di harga lebih murah)
    - Support kuat di area Avg Buy mereka

    Args:
        stock_code: Kode saham
        current_price: Harga sekarang (jika None, ambil dari database)
    """
    # Get current price if not provided
    if current_price is None:
        price_df = get_price_data(stock_code)
        if price_df.empty:
            return {'error': 'No price data'}
        current_price = float(price_df.sort_values('date').iloc[-1]['close_price'])
    else:
        current_price = float(current_price)

    # Get broker avg buy data
    broker_avg = get_broker_avg_buy(stock_code, days=60)

    if broker_avg.empty:
        return {'error': 'No broker data'}

    # Convert Decimal columns to float for calculations
    for col in ['avg_buy_price', 'avg_sell_price', 'total_buy_value', 'total_sell_value', 'net_value']:
        if col in broker_avg.columns:
            broker_avg[col] = broker_avg[col].astype(float)

    # Analyze position
    broker_avg['floating_pct'] = (current_price - broker_avg['avg_buy_price']) / broker_avg['avg_buy_price'] * 100
    broker_avg['position'] = broker_avg['floating_pct'].apply(
        lambda x: 'PROFIT' if x > 0 else ('LOSS' if x < 0 else 'BREAKEVEN')
    )

    # Summary statistics
    total_buy_value = broker_avg['total_buy_value'].sum()
    profit_brokers = broker_avg[broker_avg['position'] == 'PROFIT']
    loss_brokers = broker_avg[broker_avg['position'] == 'LOSS']

    profit_value = profit_brokers['total_buy_value'].sum() if not profit_brokers.empty else 0
    loss_value = loss_brokers['total_buy_value'].sum() if not loss_brokers.empty else 0

    # Determine support and resistance levels
    # Support = level BELOW current price where buyers might step in
    # Resistance/Interest Zone = level ABOVE current price where brokers have positions

    # If some brokers are in profit, their Avg Buy is below current price = TRUE SUPPORT
    support_levels = []
    resistance_levels = []

    if not profit_brokers.empty:
        # Brokers in profit have Avg Buy < current price = support levels
        big_profit_brokers = profit_brokers.nlargest(5, 'total_buy_value')
        support_levels = sorted(big_profit_brokers['avg_buy_price'].tolist(), reverse=True)  # highest to lowest

    if not loss_brokers.empty:
        # Brokers in loss have Avg Buy > current price = resistance/interest zone
        big_loss_brokers = loss_brokers.nlargest(5, 'total_buy_value')
        resistance_levels = sorted(big_loss_brokers['avg_buy_price'].tolist())  # lowest to highest

    # Calculate actual support (below current price)
    if support_levels:
        buy_safe_zone = max(support_levels)  # Closest support below
        support_explanation = f'Support dari Avg Buy broker profit: Rp {buy_safe_zone:,.0f}'
    else:
        # No brokers in profit, use estimated support (5-10% below current)
        buy_safe_zone = current_price * 0.95
        support_explanation = 'Belum ada support kuat (semua broker loss). Estimasi: -5% dari harga sekarang'

    # Interest zone (where big brokers bought, might defend)
    if resistance_levels:
        interest_zone = min(resistance_levels)  # Closest interest zone above
    else:
        interest_zone = None

    return {
        'current_price': current_price,
        'brokers': broker_avg.to_dict('records'),
        'summary': {
            'total_brokers': len(broker_avg),
            'profit_brokers': len(profit_brokers),
            'loss_brokers': len(loss_brokers),
            'profit_value_pct': profit_value / total_buy_value * 100 if total_buy_value > 0 else 0,
            'loss_value_pct': loss_value / total_buy_value * 100 if total_buy_value > 0 else 0,
        },
        'support_levels': support_levels,  # Below current price
        'resistance_levels': resistance_levels,  # Above current price (broker interest zone)
        'interest_zone': interest_zone,  # Closest level above where big brokers bought
        'interpretation': {
            'buy_safe_zone': buy_safe_zone,
            'explanation': support_explanation
        }
    }


# ============================================================
# BUY SIGNAL TRACKER (Deteksi kapan sinyal BUY dimulai)
# ============================================================

def track_buy_signal(stock_code: str = 'CDIA', lookback_days: int = 30) -> Dict:
    """
    Track kapan sinyal BUY dimulai dan harga saat itu.

    Fitur anti-FOMO:
    - Menunjukkan tanggal sinyal BUY pertama muncul
    - Harga saat sinyal muncul
    - Berapa persen harga sudah naik dari sinyal
    - Safe Zone: masih aman beli atau sudah terlalu mahal

    Returns:
        Dict dengan info sinyal BUY dan rekomendasi
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty:
        return {'has_signal': False, 'message': 'No price data'}

    price_df = price_df.sort_values('date').tail(lookback_days).reset_index(drop=True)

    # Convert Decimal to float for price columns
    for col in ['close_price', 'open_price', 'high_price', 'low_price', 'volume', 'value']:
        if col in price_df.columns:
            price_df[col] = price_df[col].astype(float)

    current_price = float(price_df.iloc[-1]['close_price'])
    current_date = price_df.iloc[-1]['date']

    # Cari trigger sinyal BUY berdasarkan kombinasi:
    # 1. Broker sensitif mulai akumulasi
    # 2. Foreign flow berubah positif
    # 3. Volume meningkat dengan frekuensi turun (smart money)

    signals = []

    for idx, row in price_df.iterrows():
        date = row['date']
        price = float(row['close_price'])

        # Check broker accumulation on this date
        broker_on_date = broker_df[broker_df['date'] == date] if not broker_df.empty else pd.DataFrame()

        signal_strength = 0
        signal_reasons = []

        # 1. Check net foreign (if available)
        if 'net_foreign' in row and row['net_foreign'] > 0:
            signal_strength += 1
            signal_reasons.append('Foreign Inflow')

        # 2. Check broker accumulation
        if not broker_on_date.empty:
            net_accum = float(broker_on_date['net_value'].sum())
            if net_accum > 0:
                signal_strength += 1
                signal_reasons.append('Net Accumulation')

            # Check top brokers accumulating
            top_accum = broker_on_date.nlargest(3, 'net_value')
            if not top_accum.empty and float(top_accum['net_value'].sum()) > 1e9:  # > 1B
                signal_strength += 1
                signal_reasons.append('Big Broker Buy')

        # 3. Check volume spike
        if idx > 0:
            prev_vol = price_df.iloc[max(0, idx-5):idx]['volume'].mean()
            if prev_vol > 0 and row['volume'] > prev_vol * 1.5:
                signal_strength += 1
                signal_reasons.append('Volume Spike')

        if signal_strength >= 2:
            signals.append({
                'date': date,
                'price': price,
                'strength': signal_strength,
                'reasons': signal_reasons
            })

    if not signals:
        return {
            'has_signal': False,
            'message': 'Belum ada sinyal BUY yang kuat dalam 30 hari terakhir',
            'recommendation': 'WAIT',
            'current_price': current_price
        }

    # Ambil sinyal pertama (paling awal)
    first_signal = signals[0]
    signal_price = float(first_signal['price'])
    signal_date = first_signal['date']

    # Hitung perubahan harga dari sinyal
    price_change_pct = float((current_price - signal_price) / signal_price * 100)

    # Tentukan zone berdasarkan arah pergerakan harga
    # CASE 1: Harga TURUN dari sinyal (price_change_pct < 0)
    # CASE 2: Harga NAIK dari sinyal (price_change_pct >= 0)

    if price_change_pct < -10:
        # Harga turun banyak dari sinyal = SIGNAL FAILED atau DEEP DISCOUNT
        zone = 'SIGNAL FAILED'
        zone_color = 'danger'
        zone_desc = f'Harga turun {abs(price_change_pct):.1f}% dari sinyal! Sinyal mungkin gagal. Review ulang sebelum beli.'
        recommendation = 'REVIEW'
    elif price_change_pct < -5:
        # Harga turun cukup banyak = DISCOUNTED tapi hati-hati
        zone = 'DISCOUNTED'
        zone_color = 'warning'
        zone_desc = f'Harga turun {abs(price_change_pct):.1f}% dari sinyal. Bisa jadi diskon atau sinyal mulai lemah.'
        recommendation = 'SCALE IN CAREFULLY'
    elif price_change_pct < 0:
        # Harga turun sedikit = BETTER ENTRY
        zone = 'BETTER ENTRY'
        zone_color = 'success'
        zone_desc = f'Harga turun {abs(price_change_pct):.1f}% dari sinyal. Entry lebih baik dari sinyal awal!'
        recommendation = 'BUY'
    elif price_change_pct <= 3:
        # Harga naik sedikit = SAFE
        zone = 'SAFE'
        zone_color = 'success'
        zone_desc = 'Masih aman untuk beli, harga dekat dengan sinyal awal'
        recommendation = 'BUY'
    elif price_change_pct <= 7:
        zone = 'MODERATE'
        zone_color = 'info'
        zone_desc = 'Masih bisa beli dengan cicilan, jangan all-in'
        recommendation = 'SCALE IN'
    elif price_change_pct <= 12:
        zone = 'CAUTION'
        zone_color = 'warning'
        zone_desc = 'Harga sudah naik cukup jauh, pertimbangkan wait pullback'
        recommendation = 'WAIT PULLBACK'
    else:
        zone = 'FOMO ALERT'
        zone_color = 'danger'
        zone_desc = f'Harga sudah naik {price_change_pct:.1f}% dari sinyal! Jangan FOMO!'
        recommendation = 'DO NOT CHASE'

    # Hitung target entry yang aman (relatif terhadap sinyal)
    safe_entry_price = signal_price * 1.05  # Max 5% di atas sinyal
    ideal_entry_price = signal_price * 1.02  # Ideal 2% di atas sinyal
    # Jika harga sekarang di bawah sinyal, current price sudah aman
    is_entry_safe = current_price <= safe_entry_price

    return {
        'has_signal': True,
        'signal_date': signal_date,
        'signal_price': signal_price,
        'signal_strength': first_signal['strength'],
        'signal_reasons': first_signal['reasons'],
        'current_price': current_price,
        'current_date': current_date,
        'price_change_pct': price_change_pct,
        'zone': zone,
        'zone_color': zone_color,
        'zone_desc': zone_desc,
        'recommendation': recommendation,
        'safe_entry': {
            'ideal_price': ideal_entry_price,
            'max_price': safe_entry_price,
            'is_safe': is_entry_safe
        },
        'all_signals': signals,
        'interpretation': {
            'summary': f"Sinyal BUY muncul pada {signal_date.strftime('%d %b %Y')} di harga Rp {signal_price:,.0f}",
            'current_status': f"Harga sekarang Rp {current_price:,.0f} ({price_change_pct:+.1f}% dari sinyal)",
            'action': zone_desc
        }
    }


# ============================================================
# A. BROKER SENSITIVITY ANALYSIS
# ============================================================

def calculate_broker_sensitivity_advanced(stock_code: str = 'CDIA', max_brokers: int = 40) -> Dict:
    """
    Advanced Broker Sensitivity Analysis (Optimized):
    - Lead Time: Berapa hari sebelum harga naik, broker X mulai akumulasi (T+1 s/d T+10)
    - Win Rate: % kejadian broker X akumulasi -> harga naik >= 10% dalam 10 hari
    - Sensitivity Score: Korelasi net buy dengan return T+1 s/d T+10

    Args:
        max_brokers: Limit analysis to top N brokers by activity (default 40)

    Parameter sesuai panduan:
    - Threshold Kenaikan Signifikan: >= 10%
    - Lead Time Analysis: T+1 sampai T+10 (fleksibel)
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or broker_df.empty:
        return {'brokers': [], 'summary': {}, 'top_5_brokers': [], 'total_analyzed': 0}

    price_df = price_df.sort_values('date').reset_index(drop=True)

    # Calculate forward returns (T+1 to T+10) - sesuai panduan
    for i in range(1, 11):
        price_df[f'return_t{i}'] = price_df['close_price'].shift(-i) / price_df['close_price'] - 1

    # Max forward return in 10 days
    return_cols = [f'return_t{i}' for i in range(1, 11)]
    price_df['max_return_10d'] = price_df[return_cols].max(axis=1)
    # Threshold >= 10% sesuai panduan
    price_df['significant_rise'] = price_df['max_return_10d'] >= 0.10

    # Pre-compute significant rise dates for faster lookup
    sig_rise_dates = set(price_df[price_df['significant_rise'] == True]['date'].tolist())

    # Limit to top brokers by total absolute net value (most active)
    broker_activity = broker_df.groupby('broker_code')['net_value'].apply(lambda x: x.abs().sum()).sort_values(ascending=False)
    top_brokers = broker_activity.head(max_brokers).index.tolist()

    broker_stats = {}

    for broker in top_brokers:
        broker_data = broker_df[broker_df['broker_code'] == broker].copy()
        broker_dates = set(broker_data['date'].tolist())

        # Fast merge using pre-sorted data
        merged = pd.merge(
            broker_data[['date', 'net_value', 'net_lot']],
            price_df[['date', 'close_price', 'max_return_10d', 'significant_rise'] + return_cols],
            on='date',
            how='inner'
        )

        if len(merged) < 10:
            continue

        accumulation_days = merged[merged['net_value'] > 0]
        if len(accumulation_days) < 5:
            continue

        # Win Rate: % akumulasi yang diikuti kenaikan >= 10% dalam 10 hari
        accum_then_rise = accumulation_days[accumulation_days['significant_rise'] == True]
        win_rate = len(accum_then_rise) / len(accumulation_days) * 100 if len(accumulation_days) > 0 else 0

        # Lead Time Analysis T+1 s/d T+10 (sample up to 20 rises for speed)
        lead_times = []
        sample_rises = list(sig_rise_dates)[:20]
        broker_accum_dates = set(broker_data[broker_data['net_value'] > 0]['date'].tolist())

        for rise_date in sample_rises:
            for lookback in range(1, 11):  # T+1 s/d T+10 sesuai panduan
                check_date = rise_date - timedelta(days=lookback)
                if check_date in broker_accum_dates:
                    lead_times.append(lookback)
                    break

        avg_lead_time = np.mean(lead_times) if lead_times else 5.0  # Default 5 days

        # Sensitivity Score: Correlation T+1, T+5, T+10 untuk coverage lebih baik
        corr_t1 = merged['net_value'].corr(merged['return_t1'])
        corr_t5 = merged['net_value'].corr(merged['return_t5'])
        corr_t10 = merged['net_value'].corr(merged['return_t10'])
        avg_correlation = np.nanmean([corr_t1, corr_t5, corr_t10])

        # Calculate total accumulation
        total_net = broker_data['net_value'].sum()

        # Composite Sensitivity Score (0-100)
        # Win Rate contributes 40%, Lead Time (inverse) 30%, Correlation 30%
        win_rate_score = min(win_rate, 100) * 0.4
        lead_time_score = max(0, (10 - avg_lead_time) / 10 * 100) * 0.3 if avg_lead_time > 0 else 0
        corr_score = max(0, avg_correlation * 100) * 0.3

        sensitivity_score = win_rate_score + lead_time_score + corr_score

        broker_stats[broker] = {
            'broker_code': broker,
            'win_rate': round(win_rate, 1),
            'avg_lead_time': round(avg_lead_time, 1),
            'correlation': round(avg_correlation * 100, 1),
            'sensitivity_score': round(sensitivity_score, 1),
            'total_net': total_net,
            'accum_days': len(accumulation_days),
            'successful_signals': len(accum_then_rise)
        }

    # Sort by sensitivity score
    sorted_brokers = sorted(broker_stats.values(), key=lambda x: x['sensitivity_score'], reverse=True)

    return {
        'brokers': sorted_brokers[:30],  # Top 30
        'total_analyzed': len(broker_stats),
        'avg_win_rate': np.mean([b['win_rate'] for b in sorted_brokers]) if sorted_brokers else 0,
        'top_5_brokers': [b['broker_code'] for b in sorted_brokers[:5]]
    }


# ============================================================
# B. FOREIGN FLOW MOMENTUM
# ============================================================

def calculate_foreign_flow_momentum(stock_code: str = 'CDIA', lookback: int = 20) -> Dict:
    """
    Foreign Flow Analysis dengan:
    - Flow Direction: N Foreign hari ini (+/-)
    - Flow Momentum: N Foreign hari ini - N Foreign kemarin (akselerasi)
    - Flow Consistency: Berapa hari berturut-turut positif/negatif
    - Flow vs Price: Korelasi N Foreign dengan perubahan harga

    Scoring: Foreign Score = (Direction × 1) + (Momentum × 2) + (Consistency × 3)
    """
    price_df = get_price_data(stock_code)

    if price_df.empty or 'net_foreign' not in price_df.columns:
        return {'score': 0, 'signal': 'NO_DATA'}

    df = price_df.sort_values('date').tail(lookback + 5).copy()

    if len(df) < 5:
        return {'score': 0, 'signal': 'INSUFFICIENT_DATA'}

    # Flow Direction (latest)
    latest_foreign = df['net_foreign'].iloc[-1]
    direction = 1 if latest_foreign > 0 else (-1 if latest_foreign < 0 else 0)

    # Flow Momentum (acceleration)
    if len(df) >= 2:
        prev_foreign = df['net_foreign'].iloc[-2]
        momentum = latest_foreign - prev_foreign
        momentum_score = 1 if momentum > 0 else (-1 if momentum < 0 else 0)
    else:
        momentum = 0
        momentum_score = 0

    # Flow Consistency (consecutive days)
    consistency = 0
    for i in range(len(df) - 1, -1, -1):
        if df['net_foreign'].iloc[i] > 0:
            if consistency >= 0:
                consistency += 1
            else:
                break
        elif df['net_foreign'].iloc[i] < 0:
            if consistency <= 0:
                consistency -= 1
            else:
                break

    consistency_score = min(abs(consistency), 10) * (1 if consistency > 0 else -1)

    # Flow vs Price Correlation
    df['price_change'] = df['close_price'].pct_change()
    correlation = df['net_foreign'].corr(df['price_change'])
    correlation = 0 if pd.isna(correlation) else correlation

    # Calculate Foreign Score
    # Normalized to 0-100 scale
    raw_score = (direction * 10) + (momentum_score * 20) + (consistency_score * 7)

    # Normalize to 0-100
    foreign_score = max(0, min(100, 50 + raw_score))

    # Recent stats
    recent_5 = df.tail(5)
    recent_10 = df.tail(10)

    total_5d = recent_5['net_foreign'].sum()
    total_10d = recent_10['net_foreign'].sum()
    avg_daily = df.tail(lookback)['net_foreign'].mean()

    # Signal determination
    if foreign_score >= 75:
        signal = 'STRONG_ACCUMULATION'
    elif foreign_score >= 60:
        signal = 'ACCUMULATION'
    elif foreign_score >= 40:
        signal = 'NEUTRAL'
    elif foreign_score >= 25:
        signal = 'DISTRIBUTION'
    else:
        signal = 'STRONG_DISTRIBUTION'

    return {
        'score': round(foreign_score, 1),
        'signal': signal,
        'direction': direction,
        'direction_label': 'INFLOW' if direction > 0 else ('OUTFLOW' if direction < 0 else 'FLAT'),
        'momentum': round(momentum / 1e9, 2),  # In billions
        'momentum_trend': 'ACCELERATING' if momentum_score > 0 else ('DECELERATING' if momentum_score < 0 else 'STABLE'),
        'consistency': consistency,
        'consistency_label': f"{abs(consistency)} hari {'inflow' if consistency > 0 else 'outflow'}",
        'correlation': round(correlation * 100, 1),
        'latest_foreign': round(latest_foreign / 1e9, 2),
        'total_5d': round(total_5d / 1e9, 2),
        'total_10d': round(total_10d / 1e9, 2),
        'avg_daily': round(avg_daily / 1e9, 2)
    }


# ============================================================
# C. SMART MONEY INDICATOR
# ============================================================

def calculate_smart_money_indicator(stock_code: str = 'CDIA', lookback: int = 20) -> Dict:
    """
    Smart Money Detection berdasarkan Volume-Frequency Analysis:

    Scoring:
    | Kondisi                         | Skor | Interpretasi            |
    |--------------------------------|------|-------------------------|
    | Volume ↑ 50%+, Freq ↓ atau flat | +3   | Strong accumulation     |
    | Volume ↑ 50%+, Freq ↑ <20%      | +2   | Moderate accumulation   |
    | Volume ↑, Freq ↑ proporsional   | +1   | Mixed (retail + bandar) |
    | Volume ↓, Freq ↓                | 0    | No signal               |
    | Volume ↑ 50%+, Freq ↑ 50%+      | -1   | Retail FOMO (hati-hati) |

    Additional:
    - Avg Transaction Size = Value / Freq
    - Lot per Transaction = Volume / Freq
    """
    price_df = get_price_data(stock_code)

    if price_df.empty:
        return {'score': 0, 'signal': 'NO_DATA'}

    df = price_df.sort_values('date').copy()

    # Calculate rolling averages
    df['vol_ma20'] = df['volume'].rolling(20, min_periods=5).mean()
    df['freq_ma20'] = df['frequency'].rolling(20, min_periods=5).mean() if 'frequency' in df.columns else df['vol_ma20']
    df['value_ma20'] = df['value'].rolling(20, min_periods=5).mean() if 'value' in df.columns else df['vol_ma20']

    # Get recent data
    recent = df.tail(lookback)
    latest = df.iloc[-1]

    if pd.isna(latest['vol_ma20']) or latest['vol_ma20'] == 0:
        return {'score': 50, 'signal': 'INSUFFICIENT_DATA'}

    # Calculate changes
    vol_change = (latest['volume'] - latest['vol_ma20']) / latest['vol_ma20'] * 100

    if 'frequency' in df.columns and not pd.isna(latest['freq_ma20']) and latest['freq_ma20'] > 0:
        freq_change = (latest['frequency'] - latest['freq_ma20']) / latest['freq_ma20'] * 100
        has_freq = True
    else:
        freq_change = 0
        has_freq = False

    # Daily scoring based on conditions
    daily_scores = []

    for idx in range(max(0, len(df) - lookback), len(df)):
        row = df.iloc[idx]
        if pd.isna(row['vol_ma20']) or row['vol_ma20'] == 0:
            continue

        v_change = (row['volume'] - row['vol_ma20']) / row['vol_ma20'] * 100

        if has_freq and not pd.isna(row['freq_ma20']) and row['freq_ma20'] > 0:
            f_change = (row['frequency'] - row['freq_ma20']) / row['freq_ma20'] * 100
        else:
            f_change = 0

        # Scoring logic
        if v_change >= 50 and f_change <= 0:
            score = 3  # Strong accumulation
        elif v_change >= 50 and f_change < 20:
            score = 2  # Moderate accumulation
        elif v_change > 0 and abs(v_change - f_change) < 20:
            score = 1  # Mixed
        elif v_change < 0 and f_change < 0:
            score = 0  # No signal
        elif v_change >= 50 and f_change >= 50:
            score = -1  # Retail FOMO
        else:
            score = 0

        daily_scores.append(score)

    # Calculate average score
    avg_score = np.mean(daily_scores) if daily_scores else 0

    # Normalize to 0-100
    # Score range is -1 to +3, map to 0-100
    smart_money_score = max(0, min(100, (avg_score + 1) / 4 * 100))

    # Calculate additional metrics
    if has_freq and latest['frequency'] > 0:
        avg_transaction_size = latest['value'] / latest['frequency'] if 'value' in df.columns else 0
        lot_per_transaction = latest['volume'] / latest['frequency']
    else:
        avg_transaction_size = 0
        lot_per_transaction = 0

    # Count signal days
    strong_accum_days = sum(1 for s in daily_scores if s == 3)
    moderate_accum_days = sum(1 for s in daily_scores if s == 2)
    retail_fomo_days = sum(1 for s in daily_scores if s == -1)

    # Determine signal
    if smart_money_score >= 75:
        signal = 'STRONG_ACCUMULATION'
    elif smart_money_score >= 60:
        signal = 'ACCUMULATION'
    elif smart_money_score >= 40:
        signal = 'MIXED'
    elif smart_money_score >= 25:
        signal = 'WEAK'
    else:
        signal = 'RETAIL_FOMO'

    return {
        'score': round(smart_money_score, 1),
        'signal': signal,
        'latest_vol_change': round(vol_change, 1),
        'latest_freq_change': round(freq_change, 1),
        'avg_transaction_size': round(avg_transaction_size / 1e6, 2),  # In millions
        'lot_per_transaction': round(lot_per_transaction, 0),
        'strong_accum_days': strong_accum_days,
        'moderate_accum_days': moderate_accum_days,
        'retail_fomo_days': retail_fomo_days,
        'total_days_analyzed': len(daily_scores)
    }


# ============================================================
# D. PRICE POSITION & PATTERN
# ============================================================

def calculate_price_position(stock_code: str = 'CDIA') -> Dict:
    """
    Price Position Analysis:
    - Close vs Avg
    - Price vs MA5
    - Price vs MA20
    - Distance from 20-day Low
    - Breakout Signal (Close > High5)
    """
    price_df = get_price_data(stock_code)

    if price_df.empty or len(price_df) < 20:
        return {'score': 50, 'signal': 'INSUFFICIENT_DATA'}

    df = price_df.sort_values('date').copy()

    # Calculate MAs
    df['ma5'] = df['close_price'].rolling(5).mean()
    df['ma20'] = df['close_price'].rolling(20).mean()
    df['high5'] = df['high_price'].rolling(5).max().shift(1)  # Previous 5-day high
    df['low20'] = df['low_price'].rolling(20).min()
    df['high20'] = df['high_price'].rolling(20).max()

    latest = df.iloc[-1]

    scores = {}

    # 1. Close vs Avg
    if 'avg_price' in df.columns and not pd.isna(latest.get('avg_price', None)) and latest['avg_price'] > 0:
        close_vs_avg = (latest['close_price'] - latest['avg_price']) / latest['avg_price'] * 100
        scores['close_vs_avg'] = {
            'value': round(close_vs_avg, 2),
            'bullish': close_vs_avg > 0,
            'score': min(100, max(0, 50 + close_vs_avg * 10))
        }
    else:
        scores['close_vs_avg'] = {'value': 0, 'bullish': None, 'score': 50}

    # 2. Price vs MA5
    if not pd.isna(latest['ma5']) and latest['ma5'] > 0:
        price_vs_ma5 = (latest['close_price'] - latest['ma5']) / latest['ma5'] * 100
        scores['price_vs_ma5'] = {
            'value': round(price_vs_ma5, 2),
            'bullish': latest['close_price'] > latest['ma5'],
            'score': min(100, max(0, 50 + price_vs_ma5 * 5))
        }
    else:
        scores['price_vs_ma5'] = {'value': 0, 'bullish': None, 'score': 50}

    # 3. Price vs MA20
    if not pd.isna(latest['ma20']) and latest['ma20'] > 0:
        price_vs_ma20 = (latest['close_price'] - latest['ma20']) / latest['ma20'] * 100
        scores['price_vs_ma20'] = {
            'value': round(price_vs_ma20, 2),
            'bullish': latest['close_price'] > latest['ma20'],
            'score': min(100, max(0, 50 + price_vs_ma20 * 3))
        }
    else:
        scores['price_vs_ma20'] = {'value': 0, 'bullish': None, 'score': 50}

    # 4. Distance from 20-day Low
    if not pd.isna(latest['low20']) and latest['low20'] > 0:
        dist_from_low = (latest['close_price'] - latest['low20']) / latest['low20'] * 100
        # Bullish if close to bottom (< 15%)
        scores['dist_from_low'] = {
            'value': round(dist_from_low, 2),
            'bullish': dist_from_low < 15,
            'near_bottom': dist_from_low < 15,
            'score': min(100, max(0, 100 - dist_from_low * 2)) if dist_from_low < 50 else 0
        }
    else:
        scores['dist_from_low'] = {'value': 0, 'bullish': None, 'score': 50}

    # 5. Breakout Signal
    if not pd.isna(latest['high5']):
        is_breakout = latest['close_price'] > latest['high5']
        breakout_pct = (latest['close_price'] - latest['high5']) / latest['high5'] * 100 if latest['high5'] > 0 else 0
        scores['breakout'] = {
            'value': round(breakout_pct, 2),
            'is_breakout': is_breakout,
            'bullish': is_breakout,
            'score': 100 if is_breakout else 30
        }
    else:
        scores['breakout'] = {'value': 0, 'is_breakout': False, 'bullish': False, 'score': 30}

    # Calculate overall Price Position Score
    valid_scores = [s['score'] for s in scores.values() if s['score'] is not None]
    overall_score = np.mean(valid_scores) if valid_scores else 50

    # Count bullish signals
    bullish_count = sum(1 for s in scores.values() if s.get('bullish') == True)
    total_signals = sum(1 for s in scores.values() if s.get('bullish') is not None)

    # Determine signal
    if overall_score >= 70:
        signal = 'BULLISH'
    elif overall_score >= 55:
        signal = 'MODERATELY_BULLISH'
    elif overall_score >= 45:
        signal = 'NEUTRAL'
    elif overall_score >= 30:
        signal = 'MODERATELY_BEARISH'
    else:
        signal = 'BEARISH'

    return {
        'score': round(overall_score, 1),
        'signal': signal,
        'bullish_signals': bullish_count,
        'total_signals': total_signals,
        'details': scores,
        'current_price': latest['close_price'],
        'ma5': round(latest['ma5'], 0) if not pd.isna(latest['ma5']) else None,
        'ma20': round(latest['ma20'], 0) if not pd.isna(latest['ma20']) else None
    }


# ============================================================
# E. ACCUMULATION PHASE DETECTION
# ============================================================

def detect_accumulation_phase(stock_code: str = 'CDIA', sensitivity_data: Dict = None) -> Dict:
    """
    Detect if stock is in accumulation phase:
    - Harga sideways (range < 10% dalam 10 hari)
    - Volume rata-rata naik vs 20 hari sebelumnya
    - Net Foreign cenderung positif
    - Broker sensitif mulai masuk
    - Belum breakout

    Args:
        sensitivity_data: Pre-computed broker sensitivity data (optional, to avoid duplicate calls)
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or len(price_df) < 30:
        return {'score': 50, 'phase': 'UNKNOWN', 'in_accumulation': False}

    df = price_df.sort_values('date').copy()

    # 1. Price Sideways Check (10 days)
    recent_10 = df.tail(10)
    price_range = (recent_10['high_price'].max() - recent_10['low_price'].min()) / recent_10['low_price'].min() * 100
    is_sideways = price_range < 10
    sideways_score = 100 if is_sideways else max(0, 100 - (price_range - 10) * 5)

    # 2. Volume Increase Check
    recent_vol_avg = df.tail(10)['volume'].mean()
    prev_vol_avg = df.tail(30).head(20)['volume'].mean()
    vol_increase = (recent_vol_avg - prev_vol_avg) / prev_vol_avg * 100 if prev_vol_avg > 0 else 0
    vol_increasing = vol_increase > 10
    vol_score = min(100, max(0, 50 + vol_increase))

    # 3. Net Foreign Tendency
    if 'net_foreign' in df.columns:
        recent_foreign = df.tail(10)['net_foreign'].sum()
        foreign_positive = recent_foreign > 0
        foreign_score = min(100, max(0, 50 + (recent_foreign / 1e9) * 5))
    else:
        foreign_positive = None
        foreign_score = 50

    # 4. Sensitive Brokers Check (use pre-computed if available)
    sensitivity = sensitivity_data if sensitivity_data else calculate_broker_sensitivity_advanced(stock_code)
    top_5_sensitive = sensitivity.get('top_5_brokers', [])

    # Check if top sensitive brokers are accumulating recently
    sensitive_accumulating = 0
    if not broker_df.empty and top_5_sensitive:
        recent_dates = sorted(broker_df['date'].unique())[-5:]
        recent_broker = broker_df[broker_df['date'].isin(recent_dates)]

        for broker in top_5_sensitive:
            broker_recent = recent_broker[recent_broker['broker_code'] == broker]
            if not broker_recent.empty and broker_recent['net_value'].sum() > 0:
                sensitive_accumulating += 1

    sensitive_active = sensitive_accumulating >= 2
    sensitive_score = sensitive_accumulating / 5 * 100 if top_5_sensitive else 50

    # 5. Not Breakout Yet
    df['high20'] = df['high_price'].rolling(20).max().shift(1)
    latest = df.iloc[-1]
    not_breakout = latest['close_price'] <= latest['high20'] if not pd.isna(latest['high20']) else True
    breakout_score = 80 if not_breakout else 20  # Higher score if NOT broken out (still in accumulation)

    # Calculate Overall Accumulation Score
    weights = {
        'sideways': 0.25,
        'volume': 0.20,
        'foreign': 0.20,
        'sensitive': 0.25,
        'not_breakout': 0.10
    }

    overall_score = (
        sideways_score * weights['sideways'] +
        vol_score * weights['volume'] +
        foreign_score * weights['foreign'] +
        sensitive_score * weights['sensitive'] +
        breakout_score * weights['not_breakout']
    )

    # Determine phase
    in_accumulation = overall_score >= 60 and is_sideways and not_breakout

    if in_accumulation:
        if overall_score >= 80:
            phase = 'STRONG_ACCUMULATION'
        else:
            phase = 'ACCUMULATION'
    elif overall_score >= 50 and is_sideways:
        phase = 'POTENTIAL_ACCUMULATION'
    elif not not_breakout:
        phase = 'BREAKOUT'
    elif overall_score < 40:
        phase = 'DISTRIBUTION'
    else:
        phase = 'UNCERTAIN'

    return {
        'score': round(overall_score, 1),
        'phase': phase,
        'in_accumulation': in_accumulation,
        'criteria': {
            'sideways': {
                'met': is_sideways,
                'range_pct': round(price_range, 1),
                'score': round(sideways_score, 1)
            },
            'volume_increasing': {
                'met': vol_increasing,
                'change_pct': round(vol_increase, 1),
                'score': round(vol_score, 1)
            },
            'foreign_positive': {
                'met': foreign_positive,
                'total_10d': round(recent_foreign / 1e9, 2) if 'net_foreign' in df.columns else 0,
                'score': round(foreign_score, 1)
            },
            'sensitive_brokers_active': {
                'met': sensitive_active,
                'count': sensitive_accumulating,
                'brokers': top_5_sensitive[:sensitive_accumulating] if sensitive_accumulating > 0 else [],
                'score': round(sensitive_score, 1)
            },
            'not_breakout': {
                'met': not_breakout,
                'score': round(breakout_score, 1)
            }
        }
    }


# ============================================================
# F. VOLUME ANALYSIS (RVOL & Volume-Price Trend)
# ============================================================

def calculate_volume_analysis(stock_code: str, lookback: int = 20) -> Dict:
    """
    Volume Analysis untuk mendeteksi aktivitas abnormal.

    Komponen (sesuai panduan):
    1. RVOL (Relative Volume) = Volume Hari Ini / Avg Volume 20 Hari
       - >= 2.0: Very High (skor 100)
       - >= 1.5: High (skor 80)
       - >= 1.2: Above Average (skor 60)
       - >= 0.8: Normal (skor 40)
       - < 0.8: Low (skor 20)

    2. Volume-Price Trend (VPT)
       - Volume naik + Harga naik = Bullish (skor +20)
       - Volume naik + Harga turun = Distribution (skor -10)
       - Volume turun + Harga naik = Weak rally (skor +5)
       - Volume turun + Harga turun = Consolidation (skor 0)

    3. Consecutive High Volume Days
       - 3+ hari RVOL > 1.2 = Strong interest

    Args:
        stock_code: Kode saham (dinamis, bisa untuk semua emiten)
        lookback: Periode analisis (default 20 hari)

    Returns:
        Dict dengan volume analysis metrics
    """
    price_df = get_price_data(stock_code)

    if price_df.empty or len(price_df) < lookback:
        return {
            'score': 50,
            'signal': 'INSUFFICIENT_DATA',
            'rvol': 1.0,
            'rvol_category': 'Normal',
            'vpt_signal': 'NEUTRAL',
            'consecutive_high_vol_days': 0
        }

    df = price_df.sort_values('date').copy()

    # Convert to float
    for col in ['volume', 'close_price', 'value']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    # Calculate rolling average volume (20 days)
    df['vol_ma20'] = df['volume'].rolling(20, min_periods=5).mean()

    # Calculate RVOL
    df['rvol'] = df['volume'] / df['vol_ma20']

    # Get latest data
    latest = df.iloc[-1]
    rvol = float(latest['rvol']) if not pd.isna(latest['rvol']) else 1.0

    # RVOL Score
    if rvol >= 2.0:
        rvol_score = 100
        rvol_category = 'Very High'
    elif rvol >= 1.5:
        rvol_score = 80
        rvol_category = 'High'
    elif rvol >= 1.2:
        rvol_score = 60
        rvol_category = 'Above Average'
    elif rvol >= 0.8:
        rvol_score = 40
        rvol_category = 'Normal'
    else:
        rvol_score = 20
        rvol_category = 'Low'

    # Volume-Price Trend (VPT)
    df['price_change'] = df['close_price'].pct_change()
    df['vol_change'] = df['volume'].pct_change()

    recent_5 = df.tail(5)
    vpt_scores = []

    for _, row in recent_5.iterrows():
        if pd.isna(row['price_change']) or pd.isna(row['vol_change']):
            continue

        vol_up = row['vol_change'] > 0
        price_up = row['price_change'] > 0

        if vol_up and price_up:
            vpt_scores.append(20)  # Bullish
        elif vol_up and not price_up:
            vpt_scores.append(-10)  # Distribution
        elif not vol_up and price_up:
            vpt_scores.append(5)  # Weak rally
        else:
            vpt_scores.append(0)  # Consolidation

    avg_vpt = np.mean(vpt_scores) if vpt_scores else 0

    # VPT Signal
    if avg_vpt >= 15:
        vpt_signal = 'STRONG_BULLISH'
    elif avg_vpt >= 5:
        vpt_signal = 'BULLISH'
    elif avg_vpt >= -5:
        vpt_signal = 'NEUTRAL'
    elif avg_vpt >= -10:
        vpt_signal = 'DISTRIBUTION'
    else:
        vpt_signal = 'STRONG_DISTRIBUTION'

    # Consecutive High Volume Days (RVOL > 1.2)
    consecutive_high_vol = 0
    for i in range(len(df) - 1, max(0, len(df) - 10) - 1, -1):
        if not pd.isna(df.iloc[i]['rvol']) and df.iloc[i]['rvol'] >= 1.2:
            consecutive_high_vol += 1
        else:
            break

    # Bonus for consecutive high volume
    consecutive_bonus = min(20, consecutive_high_vol * 5)

    # Calculate overall Volume Score (0-100)
    # RVOL contributes 60%, VPT contributes 30%, Consecutive bonus 10%
    volume_score = (rvol_score * 0.6) + (max(0, min(100, 50 + avg_vpt * 2)) * 0.3) + consecutive_bonus
    volume_score = max(0, min(100, volume_score))

    # Determine signal
    if volume_score >= 75:
        signal = 'HIGH_ACTIVITY'
    elif volume_score >= 60:
        signal = 'ABOVE_NORMAL'
    elif volume_score >= 40:
        signal = 'NORMAL'
    elif volume_score >= 25:
        signal = 'LOW_ACTIVITY'
    else:
        signal = 'VERY_LOW'

    return {
        'score': round(volume_score, 1),
        'signal': signal,
        'rvol': round(rvol, 2),
        'rvol_score': round(rvol_score, 1),
        'rvol_category': rvol_category,
        'vpt_signal': vpt_signal,
        'vpt_avg_score': round(avg_vpt, 1),
        'consecutive_high_vol_days': consecutive_high_vol,
        'latest_volume': float(latest['volume']),
        'avg_volume_20d': float(latest['vol_ma20']) if not pd.isna(latest['vol_ma20']) else 0,
        'interpretation': {
            'rvol': f"Volume {rvol:.1f}x dari rata-rata 20 hari ({rvol_category})",
            'vpt': f"Volume-Price Trend: {vpt_signal}",
            'consecutive': f"{consecutive_high_vol} hari berturut-turut volume tinggi" if consecutive_high_vol > 0 else "Tidak ada volume tinggi berturut-turut"
        }
    }


# ============================================================
# G. LAYER 1 BASIC FILTER (Syarat Minimum Entry)
# ============================================================

def check_layer1_filter(stock_code: str) -> Dict:
    """
    LAYER 1 Basic Filter - Syarat minimum sebelum analisis lanjutan.

    Kriteria (sesuai panduan):
    1. N Foreign positif >= 3 hari berturut-turut
    2. RVOL >= 1.2x (volume di atas rata-rata)
    3. N Foreign hari ini > 0 (masih inflow)

    Jika TIDAK LOLOS Layer 1:
    - Tampilkan warning
    - Skor maksimal dibatasi 60 (tidak bisa STRONG BUY)

    Args:
        stock_code: Kode saham (dinamis untuk semua emiten)

    Returns:
        Dict dengan status filter dan detail kriteria
    """
    price_df = get_price_data(stock_code)

    if price_df.empty:
        return {
            'passed': False,
            'criteria_met': 0,
            'total_criteria': 3,
            'message': 'Data tidak tersedia',
            'details': {}
        }

    df = price_df.sort_values('date').copy()

    # Convert to float
    for col in ['volume', 'close_price', 'net_foreign']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    criteria = {}
    criteria_met = 0

    # 1. N Foreign positif >= 3 hari berturut-turut
    consecutive_foreign_positive = 0
    if 'net_foreign' in df.columns:
        for i in range(len(df) - 1, max(0, len(df) - 10) - 1, -1):
            if df.iloc[i]['net_foreign'] > 0:
                consecutive_foreign_positive += 1
            else:
                break

    foreign_consecutive_ok = consecutive_foreign_positive >= 3
    criteria['foreign_consecutive'] = {
        'name': 'N Foreign >= 3 hari berturut',
        'passed': foreign_consecutive_ok,
        'value': consecutive_foreign_positive,
        'threshold': 3,
        'detail': f"{consecutive_foreign_positive} hari foreign inflow berturut-turut"
    }
    if foreign_consecutive_ok:
        criteria_met += 1

    # 2. RVOL >= 1.2x
    df['vol_ma20'] = df['volume'].rolling(20, min_periods=5).mean()
    latest = df.iloc[-1]
    rvol = float(latest['volume'] / latest['vol_ma20']) if not pd.isna(latest['vol_ma20']) and latest['vol_ma20'] > 0 else 0

    rvol_ok = rvol >= 1.2
    criteria['rvol'] = {
        'name': 'RVOL >= 1.2x',
        'passed': rvol_ok,
        'value': round(rvol, 2),
        'threshold': 1.2,
        'detail': f"RVOL = {rvol:.2f}x (threshold: 1.2x)"
    }
    if rvol_ok:
        criteria_met += 1

    # 3. N Foreign hari ini > 0
    latest_foreign = float(latest['net_foreign']) if 'net_foreign' in df.columns and not pd.isna(latest['net_foreign']) else 0

    foreign_today_ok = latest_foreign > 0
    criteria['foreign_today'] = {
        'name': 'N Foreign hari ini > 0',
        'passed': foreign_today_ok,
        'value': latest_foreign,
        'threshold': 0,
        'detail': f"N Foreign = Rp {latest_foreign/1e9:.2f} B" if latest_foreign != 0 else "N Foreign = 0"
    }
    if foreign_today_ok:
        criteria_met += 1

    # Overall pass/fail
    passed = criteria_met >= 2  # At least 2 of 3 criteria must pass
    all_passed = criteria_met == 3

    if all_passed:
        message = "LOLOS Layer 1 - Semua kriteria terpenuhi"
        status = 'FULL_PASS'
    elif passed:
        message = f"LOLOS Layer 1 (Partial) - {criteria_met}/3 kriteria terpenuhi"
        status = 'PARTIAL_PASS'
    else:
        message = f"TIDAK LOLOS Layer 1 - Hanya {criteria_met}/3 kriteria"
        status = 'FAILED'

    return {
        'passed': passed,
        'all_passed': all_passed,
        'status': status,
        'criteria_met': criteria_met,
        'total_criteria': 3,
        'message': message,
        'criteria': criteria,
        'max_score_cap': None if all_passed else (75 if passed else 60),
        'interpretation': {
            'summary': message,
            'action': 'Lanjut analisis komponen' if passed else 'Hati-hati! Fundamental lemah',
            'score_impact': 'Skor tidak dibatasi' if all_passed else f'Skor maksimal dibatasi {75 if passed else 60}'
        }
    }


# ============================================================
# H. COMPOSITE SCORE (Updated dengan 6 Komponen)
# ============================================================

def calculate_composite_score(stock_code: str) -> Dict:
    """
    Composite Score combining all indicators (Updated sesuai panduan).

    BOBOT KOMPONEN (Total 100%):
    | Komponen                  | Bobot |
    |---------------------------|-------|
    | A. Broker Sensitivity     | 20%   |
    | B. Foreign Flow Score     | 20%   |
    | C. Smart Money Indicator  | 15%   |
    | D. Price Position Score   | 15%   |
    | E. Accumulation Phase     | 15%   |
    | F. Volume Analysis        | 15%   |

    LAYER 1 BASIC FILTER (Syarat Minimum):
    - N Foreign >= 3 hari berturut
    - RVOL >= 1.2x
    - N Foreign hari ini > 0
    Jika tidak lolos, skor dibatasi maksimal 60-75.

    INTERPRETASI (Updated Thresholds):
    | Score  | Action                                |
    |--------|---------------------------------------|
    | >= 75  | Strong Buy - Semua sinyal align       |
    | 60-74  | Buy - Mayoritas sinyal positif        |
    | 45-59  | Watch - Sinyal mixed, pantau terus    |
    | < 45   | No Entry - Sinyal belum mendukung     |

    Args:
        stock_code: Kode saham (dinamis untuk semua emiten)
    """
    # Check Layer 1 Filter first
    layer1 = check_layer1_filter(stock_code)

    # Get all component scores
    sensitivity = calculate_broker_sensitivity_advanced(stock_code)
    foreign_flow = calculate_foreign_flow_momentum(stock_code)
    smart_money = calculate_smart_money_indicator(stock_code)
    price_position = calculate_price_position(stock_code)
    accumulation = detect_accumulation_phase(stock_code, sensitivity_data=sensitivity)
    volume_analysis = calculate_volume_analysis(stock_code)

    # Extract scores
    # A. Broker Sensitivity (from top brokers' win rate)
    if sensitivity['brokers']:
        top_5_avg_win = np.mean([b['win_rate'] for b in sensitivity['brokers'][:5]])
        sensitivity_score = min(100, top_5_avg_win * 1.2)  # Scale win rate
    else:
        sensitivity_score = 50

    # B-F. Other component scores
    foreign_score = foreign_flow.get('score', 50)
    smart_money_score = smart_money.get('score', 50)
    price_score = price_position.get('score', 50)
    accum_score = accumulation.get('score', 50)
    volume_score = volume_analysis.get('score', 50)

    # Apply weights (Updated: 20/20/15/15/15/15)
    weights = {
        'sensitivity': 0.20,    # A. Broker Sensitivity
        'foreign': 0.20,        # B. Foreign Flow
        'smart_money': 0.15,    # C. Smart Money
        'price': 0.15,          # D. Price Position
        'accumulation': 0.15,   # E. Accumulation Phase
        'volume': 0.15          # F. Volume Analysis
    }

    composite = (
        sensitivity_score * weights['sensitivity'] +
        foreign_score * weights['foreign'] +
        smart_money_score * weights['smart_money'] +
        price_score * weights['price'] +
        accum_score * weights['accumulation'] +
        volume_score * weights['volume']
    )

    # Apply Layer 1 cap if not fully passed
    original_composite = composite
    if layer1['max_score_cap'] is not None:
        composite = min(composite, layer1['max_score_cap'])

    # Determine action (Updated Thresholds: 75/60/45)
    if composite >= 75:
        action = 'STRONG_BUY'
        action_desc = 'Semua sinyal align - momentum kuat'
        color = 'success'
    elif composite >= 60:
        action = 'BUY'
        action_desc = 'Mayoritas sinyal positif'
        color = 'info'
    elif composite >= 45:
        action = 'WATCH'
        action_desc = 'Sinyal mixed - pantau terus'
        color = 'warning'
    else:
        action = 'NO_ENTRY'
        action_desc = 'Sinyal belum mendukung entry'
        color = 'danger'

    return {
        'composite_score': round(composite, 1),
        'original_score': round(original_composite, 1),
        'action': action,
        'action_desc': action_desc,
        'color': color,
        'layer1_filter': layer1,
        'score_capped': layer1['max_score_cap'] is not None and original_composite > layer1['max_score_cap'],
        'components': {
            'broker_sensitivity': {
                'score': round(sensitivity_score, 1),
                'weight': '20%',
                'signal': 'POSITIVE' if sensitivity_score >= 60 else ('NEUTRAL' if sensitivity_score >= 40 else 'NEGATIVE'),
                'detail': sensitivity
            },
            'foreign_flow': {
                'score': round(foreign_score, 1),
                'weight': '20%',
                'signal': foreign_flow.get('signal', 'NEUTRAL'),
                'detail': foreign_flow
            },
            'smart_money': {
                'score': round(smart_money_score, 1),
                'weight': '15%',
                'signal': smart_money.get('signal', 'NEUTRAL'),
                'detail': smart_money
            },
            'price_position': {
                'score': round(price_score, 1),
                'weight': '15%',
                'signal': price_position.get('signal', 'NEUTRAL'),
                'detail': price_position
            },
            'accumulation_phase': {
                'score': round(accum_score, 1),
                'weight': '15%',
                'signal': accumulation.get('phase', 'UNKNOWN'),
                'detail': accumulation
            },
            'volume_analysis': {
                'score': round(volume_score, 1),
                'weight': '15%',
                'signal': volume_analysis.get('signal', 'NEUTRAL'),
                'detail': volume_analysis
            }
        },
        'analysis_time': datetime.now().isoformat()
    }


# ============================================================
# G. ENHANCED ALERT SYSTEM
# ============================================================

def generate_alerts(stock_code: str = 'CDIA', sensitivity_data: Dict = None, composite_score: float = None) -> List[Dict]:
    """
    Generate alerts based on:
    1. Broker sensitif (top 5) mulai akumulasi setelah 3+ hari tidak aktif
    2. N Foreign berubah dari negatif ke positif 2 hari berturut
    3. Volume spike >100% dengan Freq naik <30%
    4. Breakout dari range 10 hari dengan volume tinggi
    5. Composite Score tinggi (>=70)

    Args:
        sensitivity_data: Pre-computed broker sensitivity data (optional)
        composite_score: Pre-computed composite score value (optional)
    """
    alerts = []

    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or broker_df.empty:
        return alerts

    df = price_df.sort_values('date').copy()

    # 1. Sensitive Broker Activation (use pre-computed if available)
    sensitivity = sensitivity_data if sensitivity_data else calculate_broker_sensitivity_advanced(stock_code)
    top_5 = sensitivity.get('top_5_brokers', [])

    for broker in top_5:
        broker_data = broker_df[broker_df['broker_code'] == broker].sort_values('date')
        if len(broker_data) >= 5:
            recent_5 = broker_data.tail(5)

            # Check if inactive for 3+ days then active
            inactive_days = 0
            for i in range(len(recent_5) - 2, -1, -1):
                if recent_5.iloc[i]['net_value'] <= 0:
                    inactive_days += 1
                else:
                    break

            latest_active = recent_5.iloc[-1]['net_value'] > 0
            prev_active = recent_5.iloc[-2]['net_value'] > 0 if len(recent_5) >= 2 else False

            if inactive_days >= 3 and latest_active:
                broker_info = next((b for b in sensitivity['brokers'] if b['broker_code'] == broker), {})
                alerts.append({
                    'type': 'SENSITIVE_BROKER_ACTIVATION',
                    'priority': 'HIGH',
                    'broker': broker,
                    'message': f"Broker sensitif {broker} kembali akumulasi setelah {inactive_days} hari tidak aktif",
                    'detail': f"Win Rate: {broker_info.get('win_rate', 0):.0f}%, Avg Lead: {broker_info.get('avg_lead_time', 0):.0f} hari"
                })

    # 2. Foreign Flow Reversal
    if 'net_foreign' in df.columns and len(df) >= 4:
        recent_4 = df.tail(4)
        day_minus_4 = recent_4.iloc[0]['net_foreign']
        day_minus_3 = recent_4.iloc[1]['net_foreign']
        day_minus_2 = recent_4.iloc[2]['net_foreign']
        day_minus_1 = recent_4.iloc[3]['net_foreign']

        # Was negative, now positive for 2 days
        if day_minus_4 < 0 and day_minus_3 < 0 and day_minus_2 > 0 and day_minus_1 > 0:
            alerts.append({
                'type': 'FOREIGN_FLOW_REVERSAL',
                'priority': 'MEDIUM',
                'message': f"Foreign flow berubah dari outflow ke inflow 2 hari berturut",
                'detail': f"Hari -2: +{day_minus_2/1e9:.1f}B, Hari -1: +{day_minus_1/1e9:.1f}B"
            })

    # 3. Volume Spike with Low Frequency Increase
    if len(df) >= 21:
        latest = df.iloc[-1]
        vol_avg_20 = df.tail(21).head(20)['volume'].mean()

        if vol_avg_20 > 0:
            vol_change = (latest['volume'] - vol_avg_20) / vol_avg_20 * 100

            if 'frequency' in df.columns:
                freq_avg_20 = df.tail(21).head(20)['frequency'].mean()
                freq_change = (latest['frequency'] - freq_avg_20) / freq_avg_20 * 100 if freq_avg_20 > 0 else 0
            else:
                freq_change = 0

            if vol_change > 100 and freq_change < 30:
                alerts.append({
                    'type': 'SMART_MONEY_VOLUME',
                    'priority': 'HIGH',
                    'message': f"Volume spike +{vol_change:.0f}% dengan frequency hanya +{freq_change:.0f}%",
                    'detail': "Indikasi transaksi besar (institusi/bandar)"
                })

    # 4. Breakout Signal
    if len(df) >= 11:
        latest = df.iloc[-1]
        high_10 = df.tail(11).head(10)['high_price'].max()
        vol_avg_10 = df.tail(11).head(10)['volume'].mean()

        if latest['close_price'] > high_10 and latest['volume'] > vol_avg_10 * 1.5:
            breakout_pct = (latest['close_price'] - high_10) / high_10 * 100
            alerts.append({
                'type': 'BREAKOUT',
                'priority': 'HIGH',
                'message': f"BREAKOUT! Harga menembus high 10 hari (+{breakout_pct:.1f}%)",
                'detail': f"Volume {latest['volume']/vol_avg_10:.1f}x average"
            })

    # 5. Composite Score High Alert (use pre-computed if available)
    if composite_score is not None and composite_score >= 70:
        action = 'STRONG_BUY' if composite_score >= 80 else 'BUY'
        alerts.append({
            'type': 'COMPOSITE_SCORE_HIGH',
            'priority': 'MEDIUM',
            'message': f"Composite Score tinggi: {composite_score:.0f}/100",
            'detail': f"Action: {action}"
        })

    # Sort by priority
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    alerts.sort(key=lambda x: priority_order.get(x['priority'], 99))

    return alerts


# ============================================================
# MAIN COMPREHENSIVE ANALYSIS (Optimized with caching)
# ============================================================

def get_comprehensive_analysis(stock_code: str, use_cache: bool = True) -> Dict:
    """
    Get complete comprehensive analysis for a stock (Updated dengan 6 komponen).
    Optimized with caching to avoid recalculation on every page load.

    Args:
        stock_code: Kode saham (dinamis untuk semua emiten)
        use_cache: If True, use cached results if available (default True)
    """
    global _analysis_cache

    # Check cache first
    cache_key = _get_cache_key(stock_code)
    if use_cache and _is_cache_valid(cache_key):
        cached = _analysis_cache[cache_key].copy()
        cached['from_cache'] = True
        cached['analysis_time'] = datetime.now().isoformat()
        return cached

    # Check Layer 1 Filter first
    layer1 = check_layer1_filter(stock_code)

    # Calculate each component once (pass pre-computed data to avoid duplicates)
    sensitivity = calculate_broker_sensitivity_advanced(stock_code)
    foreign_flow = calculate_foreign_flow_momentum(stock_code)
    smart_money = calculate_smart_money_indicator(stock_code)
    price_position = calculate_price_position(stock_code)
    accumulation = detect_accumulation_phase(stock_code, sensitivity_data=sensitivity)
    volume_analysis = calculate_volume_analysis(stock_code)

    # Calculate composite score using pre-computed values
    # A. Broker Sensitivity
    if sensitivity['brokers']:
        top_5_avg_win = np.mean([b['win_rate'] for b in sensitivity['brokers'][:5]])
        sensitivity_score = min(100, top_5_avg_win * 1.2)
    else:
        sensitivity_score = 50

    # B-F. Other component scores
    foreign_score = foreign_flow.get('score', 50)
    smart_money_score = smart_money.get('score', 50)
    price_score = price_position.get('score', 50)
    accum_score = accumulation.get('score', 50)
    volume_score = volume_analysis.get('score', 50)

    # Apply weights (Updated: 20/20/15/15/15/15)
    weights = {
        'sensitivity': 0.20,    # A. Broker Sensitivity
        'foreign': 0.20,        # B. Foreign Flow
        'smart_money': 0.15,    # C. Smart Money
        'price': 0.15,          # D. Price Position
        'accumulation': 0.15,   # E. Accumulation Phase
        'volume': 0.15          # F. Volume Analysis
    }

    composite_val = (
        sensitivity_score * weights['sensitivity'] +
        foreign_score * weights['foreign'] +
        smart_money_score * weights['smart_money'] +
        price_score * weights['price'] +
        accum_score * weights['accumulation'] +
        volume_score * weights['volume']
    )

    # Apply Layer 1 cap if not fully passed
    original_composite = composite_val
    if layer1['max_score_cap'] is not None:
        composite_val = min(composite_val, layer1['max_score_cap'])

    # Determine action (Updated Thresholds: 75/60/45)
    if composite_val >= 75:
        action = 'STRONG_BUY'
        action_desc = 'Semua sinyal align - momentum kuat'
        color = 'success'
    elif composite_val >= 60:
        action = 'BUY'
        action_desc = 'Mayoritas sinyal positif'
        color = 'info'
    elif composite_val >= 45:
        action = 'WATCH'
        action_desc = 'Sinyal mixed - pantau terus'
        color = 'warning'
    else:
        action = 'NO_ENTRY'
        action_desc = 'Sinyal belum mendukung entry'
        color = 'danger'

    composite = {
        'composite_score': round(composite_val, 1),
        'original_score': round(original_composite, 1),
        'action': action,
        'action_desc': action_desc,
        'color': color,
        'layer1_filter': layer1,
        'score_capped': layer1['max_score_cap'] is not None and original_composite > layer1['max_score_cap'],
        'components': {
            'broker_sensitivity': {
                'score': round(sensitivity_score, 1),
                'weight': '20%',
                'signal': 'POSITIVE' if sensitivity_score >= 60 else ('NEUTRAL' if sensitivity_score >= 40 else 'NEGATIVE'),
                'detail': sensitivity
            },
            'foreign_flow': {
                'score': round(foreign_score, 1),
                'weight': '20%',
                'signal': foreign_flow.get('signal', 'NEUTRAL'),
                'detail': foreign_flow
            },
            'smart_money': {
                'score': round(smart_money_score, 1),
                'weight': '15%',
                'signal': smart_money.get('signal', 'NEUTRAL'),
                'detail': smart_money
            },
            'price_position': {
                'score': round(price_score, 1),
                'weight': '15%',
                'signal': price_position.get('signal', 'NEUTRAL'),
                'detail': price_position
            },
            'accumulation_phase': {
                'score': round(accum_score, 1),
                'weight': '15%',
                'signal': accumulation.get('phase', 'UNKNOWN'),
                'detail': accumulation
            },
            'volume_analysis': {
                'score': round(volume_score, 1),
                'weight': '15%',
                'signal': volume_analysis.get('signal', 'NEUTRAL'),
                'detail': volume_analysis
            }
        },
        'analysis_time': datetime.now().isoformat()
    }

    # Generate alerts (uses pre-computed data to avoid duplicate calls)
    alerts = generate_alerts(stock_code, sensitivity_data=sensitivity, composite_score=composite_val)

    result = {
        'stock_code': stock_code,
        'analysis_time': datetime.now().isoformat(),
        'composite': composite,
        'layer1_filter': layer1,
        'broker_sensitivity': sensitivity,
        'foreign_flow': foreign_flow,
        'smart_money': smart_money,
        'price_position': price_position,
        'accumulation_phase': accumulation,
        'volume_analysis': volume_analysis,
        'alerts': alerts,
        'from_cache': False,
        '_cached_at': datetime.now().timestamp()
    }

    # Store in cache
    _analysis_cache[cache_key] = result

    return result


if __name__ == "__main__":
    import json
    result = get_comprehensive_analysis('CDIA')
    print(json.dumps(result, indent=2, default=str))
