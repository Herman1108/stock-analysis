# -*- coding: utf-8 -*-
"""
ADAPTIVE SIDEWAYS DETECTOR
==========================
Menentukan threshold sideways berdasarkan karakteristik historis saham.

3 Metode:
1. ATR-Based: Bandingkan range dengan Average True Range
2. Percentile-Based: Range di bawah percentile tertentu dari history
3. Standard Deviation: Range dalam X std dev dari mean
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import statistics

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

# Ensure app directory is in path for database import
app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from database import get_connection

# Module-level connection removed - use get_connection() context manager instead
conn = None
cur = None


def load_stock_data(stock_code):
    """Load data saham"""
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('''
            SELECT date, high_price as high, low_price as low,
                   close_price as close, volume
            FROM stock_daily
            WHERE stock_code = %s
            ORDER BY date ASC
        ''', (stock_code,))
        all_data = cur.fetchall()

    data_list = []
    for i, row in enumerate(all_data):
        prev_close = all_data[i-1]['close'] if i > 0 else row['close']
        change = ((row['close'] - prev_close) / prev_close * 100) if prev_close else 0

        # True Range untuk ATR
        if i > 0:
            tr = max(
                float(row['high']) - float(row['low']),
                abs(float(row['high']) - float(all_data[i-1]['close'])),
                abs(float(row['low']) - float(all_data[i-1]['close']))
            )
        else:
            tr = float(row['high']) - float(row['low'])

        data_list.append({
            'date': row['date'],
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']),
            'change': change,
            'true_range': tr
        })

    return data_list


# ============================================================
# METODE 1: ATR-BASED
# ============================================================
def calculate_atr(data, period=14):
    """Hitung Average True Range"""
    if len(data) < period:
        return None

    tr_values = [d['true_range'] for d in data[-period:]]
    return sum(tr_values) / len(tr_values)


def atr_based_sideways(data, lookback_window=10, atr_period=14, atr_multiplier=1.5):
    """
    Sideways jika range dalam window < ATR × multiplier

    Logika:
    - ATR = volatilitas "normal" harian
    - Range window = pergerakan dalam N hari
    - Jika range window < ATR × N × factor, maka sideways

    Parameter:
    - lookback_window: periode untuk cek sideways (default 10 hari)
    - atr_period: periode untuk hitung ATR (default 14 hari)
    - atr_multiplier: berapa kali ATR dianggap sideways (default 1.5)
    """
    if len(data) < max(lookback_window, atr_period) + 5:
        return None

    # Hitung ATR dari data sebelum window
    pre_window_data = data[:-lookback_window]
    atr = calculate_atr(pre_window_data, atr_period)

    if not atr or atr == 0:
        return None

    # Hitung range dalam window
    window = data[-lookback_window:]
    window_high = max(d['high'] for d in window)
    window_low = min(d['low'] for d in window)
    window_range = window_high - window_low

    avg_price = sum(d['close'] for d in window) / len(window)

    # Expected range jika trending = ATR × lookback × factor
    # Untuk sideways, actual range harus lebih kecil
    expected_trending_range = atr * lookback_window * 0.3  # Factor 0.3 karena tidak pure trending

    # Threshold = ATR × multiplier
    threshold = atr * atr_multiplier * (lookback_window ** 0.5)  # Square root untuk normalisasi

    is_sideways = window_range < threshold

    return {
        'method': 'ATR-Based',
        'is_sideways': is_sideways,
        'atr': atr,
        'atr_pct': atr / avg_price * 100,
        'window_range': window_range,
        'window_range_pct': window_range / avg_price * 100,
        'threshold': threshold,
        'threshold_pct': threshold / avg_price * 100,
        'high': window_high,
        'low': window_low,
        'days': lookback_window
    }


# ============================================================
# METODE 2: PERCENTILE-BASED
# ============================================================
def calculate_historical_ranges(data, window_size=10, history_periods=50):
    """Hitung range historis untuk berbagai window"""
    ranges = []

    start_idx = max(0, len(data) - history_periods - window_size)
    end_idx = len(data) - window_size

    for i in range(start_idx, end_idx):
        window = data[i:i+window_size]
        high = max(d['high'] for d in window)
        low = min(d['low'] for d in window)
        avg = sum(d['close'] for d in window) / len(window)
        range_pct = (high - low) / avg * 100
        ranges.append(range_pct)

    return ranges


def percentile_based_sideways(data, lookback_window=10, history_periods=50, percentile=30):
    """
    Sideways jika range dalam window < percentile tertentu dari history

    Logika:
    - Hitung range% untuk semua window historis
    - Jika current range < percentile ke-30, maka sideways
    - Ini adaptif karena berdasarkan karakteristik saham itu sendiri

    Parameter:
    - lookback_window: periode untuk cek sideways
    - history_periods: berapa banyak periode historis untuk referensi
    - percentile: di bawah percentile berapa dianggap sideways (default 30)
    """
    if len(data) < history_periods + lookback_window:
        return None

    # Hitung historical ranges
    hist_ranges = calculate_historical_ranges(data[:-lookback_window], lookback_window, history_periods)

    if len(hist_ranges) < 10:
        return None

    # Hitung percentile threshold
    sorted_ranges = sorted(hist_ranges)
    idx = int(len(sorted_ranges) * percentile / 100)
    threshold_pct = sorted_ranges[idx]

    # Hitung current range
    window = data[-lookback_window:]
    window_high = max(d['high'] for d in window)
    window_low = min(d['low'] for d in window)
    avg_price = sum(d['close'] for d in window) / len(window)
    current_range_pct = (window_high - window_low) / avg_price * 100

    is_sideways = current_range_pct < threshold_pct

    return {
        'method': 'Percentile-Based',
        'is_sideways': is_sideways,
        'current_range_pct': current_range_pct,
        'threshold_pct': threshold_pct,
        'percentile': percentile,
        'hist_min': min(hist_ranges),
        'hist_max': max(hist_ranges),
        'hist_mean': statistics.mean(hist_ranges),
        'hist_median': statistics.median(hist_ranges),
        'high': window_high,
        'low': window_low,
        'days': lookback_window
    }


# ============================================================
# METODE 3: STANDARD DEVIATION BASED
# ============================================================
def stdev_based_sideways(data, lookback_window=10, history_periods=50, num_stdev=1.0):
    """
    Sideways jika range < (mean - num_stdev × stdev) dari historical ranges

    Logika:
    - Hitung mean dan stdev dari historical ranges
    - Sideways = range di bawah (mean - 1 stdev)
    - Semakin volatile saham, semakin tinggi threshold

    Parameter:
    - lookback_window: periode untuk cek sideways
    - history_periods: berapa banyak periode historis
    - num_stdev: berapa stdev di bawah mean (default 1.0)
    """
    if len(data) < history_periods + lookback_window:
        return None

    # Hitung historical ranges
    hist_ranges = calculate_historical_ranges(data[:-lookback_window], lookback_window, history_periods)

    if len(hist_ranges) < 10:
        return None

    # Hitung mean dan stdev
    mean_range = statistics.mean(hist_ranges)
    stdev_range = statistics.stdev(hist_ranges) if len(hist_ranges) > 1 else 0

    # Threshold = mean - num_stdev × stdev
    threshold_pct = mean_range - (num_stdev * stdev_range)
    threshold_pct = max(threshold_pct, 0)  # Tidak boleh negatif

    # Hitung current range
    window = data[-lookback_window:]
    window_high = max(d['high'] for d in window)
    window_low = min(d['low'] for d in window)
    avg_price = sum(d['close'] for d in window) / len(window)
    current_range_pct = (window_high - window_low) / avg_price * 100

    is_sideways = current_range_pct < threshold_pct

    return {
        'method': 'StdDev-Based',
        'is_sideways': is_sideways,
        'current_range_pct': current_range_pct,
        'threshold_pct': threshold_pct,
        'mean_range': mean_range,
        'stdev_range': stdev_range,
        'num_stdev': num_stdev,
        'high': window_high,
        'low': window_low,
        'days': lookback_window
    }


# ============================================================
# COMBINED ADAPTIVE METHOD
# ============================================================
def adaptive_sideways_detection(data, lookback_window=10):
    """
    Kombinasi ketiga metode untuk deteksi sideways yang lebih robust

    Returns sideways jika minimal 2 dari 3 metode setuju
    """
    results = {}

    # Metode 1: ATR
    atr_result = atr_based_sideways(data, lookback_window)
    if atr_result:
        results['atr'] = atr_result

    # Metode 2: Percentile
    pct_result = percentile_based_sideways(data, lookback_window)
    if pct_result:
        results['percentile'] = pct_result

    # Metode 3: StdDev
    std_result = stdev_based_sideways(data, lookback_window)
    if std_result:
        results['stdev'] = std_result

    if not results:
        return None

    # Voting
    votes = sum(1 for r in results.values() if r['is_sideways'])
    is_sideways = votes >= 2  # Majority voting

    # Get range info from any result
    sample = list(results.values())[0]

    return {
        'method': 'Adaptive (Combined)',
        'is_sideways': is_sideways,
        'votes': votes,
        'total_methods': len(results),
        'results': results,
        'high': sample['high'],
        'low': sample['low'],
        'days': lookback_window
    }


# ============================================================
# ANALISIS UNTUK BEBERAPA SAHAM
# ============================================================
def analyze_stock_volatility(stock_code):
    """Analisis karakteristik volatilitas saham"""
    data = load_stock_data(stock_code)

    if len(data) < 100:
        print(f"Data tidak cukup untuk {stock_code}")
        return

    print(f"\n{'='*90}")
    print(f"ANALISIS VOLATILITAS: {stock_code}")
    print(f"{'='*90}")
    print(f"Periode: {data[0]['date']} - {data[-1]['date']} ({len(data)} hari)")

    # Hitung ATR
    atr = calculate_atr(data, 14)
    avg_price = sum(d['close'] for d in data[-30:]) / 30
    atr_pct = atr / avg_price * 100 if atr else 0

    print(f"\n1. ATR (14 hari):")
    print(f"   ATR: {atr:,.2f}")
    print(f"   ATR %: {atr_pct:.2f}%")
    print(f"   Interpretasi: Volatilitas harian rata-rata {atr_pct:.2f}%")

    # Hitung historical range distribution
    ranges_5d = calculate_historical_ranges(data, 5, 100)
    ranges_10d = calculate_historical_ranges(data, 10, 100)
    ranges_15d = calculate_historical_ranges(data, 15, 100)

    print(f"\n2. Distribusi Range Historis:")
    print(f"   {'Window':<10} {'Min':>8} {'P25':>8} {'Median':>8} {'P75':>8} {'Max':>8}")
    print(f"   {'-'*50}")

    for label, ranges in [('5 hari', ranges_5d), ('10 hari', ranges_10d), ('15 hari', ranges_15d)]:
        if ranges:
            sorted_r = sorted(ranges)
            p25 = sorted_r[int(len(sorted_r) * 0.25)]
            p50 = sorted_r[int(len(sorted_r) * 0.50)]
            p75 = sorted_r[int(len(sorted_r) * 0.75)]
            print(f"   {label:<10} {min(ranges):>7.1f}% {p25:>7.1f}% {p50:>7.1f}% {p75:>7.1f}% {max(ranges):>7.1f}%")

    # Recommended threshold
    if ranges_10d:
        sorted_r = sorted(ranges_10d)
        recommended = sorted_r[int(len(sorted_r) * 0.30)]
        print(f"\n3. RECOMMENDED SIDEWAYS THRESHOLD (Percentile 30):")
        print(f"   Range < {recommended:.1f}% dalam 10 hari = SIDEWAYS")

    # Current status
    print(f"\n4. STATUS SAAT INI:")
    for method_name, detector in [
        ('ATR-Based', lambda: atr_based_sideways(data, 10)),
        ('Percentile', lambda: percentile_based_sideways(data, 10)),
        ('StdDev', lambda: stdev_based_sideways(data, 10)),
        ('Adaptive', lambda: adaptive_sideways_detection(data, 10))
    ]:
        result = detector()
        if result:
            status = "SIDEWAYS" if result['is_sideways'] else "TRENDING"
            if 'threshold_pct' in result:
                print(f"   {method_name:<12}: {status:<10} (range: {result.get('current_range_pct', result.get('window_range_pct', 0)):.1f}% vs threshold: {result['threshold_pct']:.1f}%)")
            elif 'votes' in result:
                print(f"   {method_name:<12}: {status:<10} (votes: {result['votes']}/{result['total_methods']})")
            else:
                print(f"   {method_name:<12}: {status:<10}")

    return data


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    # Analisis beberapa saham
    stocks = ['NCKL', 'PANI', 'BBCA', 'TLKM']

    print("="*90)
    print("ADAPTIVE SIDEWAYS DETECTOR")
    print("="*90)
    print("\nMenentukan threshold sideways berdasarkan karakteristik masing-masing saham")
    print("\n3 Metode yang digunakan:")
    print("  1. ATR-Based: Bandingkan range dengan Average True Range")
    print("  2. Percentile: Range < percentile 30 dari history")
    print("  3. StdDev: Range < (mean - 1 stdev) dari history")

    for stock in stocks:
        try:
            analyze_stock_volatility(stock)
        except Exception as e:
            print(f"\nError untuk {stock}: {e}")

    conn.close()
