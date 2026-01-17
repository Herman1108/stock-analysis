# -*- coding: utf-8 -*-
"""
STRONG S/R ANALYZER V7 - Density-Based
=======================================
Khusus untuk PANI, BREN, MBMA dengan formula V7.
Menggunakan metode density/activity-based dari data 1 tahun terakhir.

Metode:
1. Bagi harga ke zona per 500 Rp
2. Hitung aktivitas (jumlah candle yang menyentuh zona)
3. Cari PEAK = zona dengan aktivitas > tetangga
4. Filter = hanya peak dengan aktivitas > median
5. Support = peak terdekat di bawah harga
   Resistance = peak terdekat di atas harga
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Ensure app directory is in path for database import
app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from database import get_connection


def get_db_connection():
    """Wrapper for backward compatibility - uses shared database connection"""
    return get_connection().__enter__()


def get_stock_data(stock_code, conn):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT date, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM stock_daily WHERE stock_code = %s
        AND open_price IS NOT NULL AND close_price IS NOT NULL
        ORDER BY date ASC
    ''', (stock_code,))
    return cur.fetchall()


def filter_data_1year(data):
    """Filter data hanya 1 tahun terakhir"""
    if not data:
        return data

    last_date = data[-1]['date']
    if isinstance(last_date, str):
        last_date = datetime.strptime(last_date, '%Y-%m-%d').date()

    one_year_ago = last_date - timedelta(days=365)

    filtered = []
    for d in data:
        d_date = d['date']
        if isinstance(d_date, str):
            d_date = datetime.strptime(d_date, '%Y-%m-%d').date()
        if d_date >= one_year_ago:
            filtered.append(d)

    return filtered


def calculate_zone_activity(data, zone_size=500):
    """
    Hitung aktivitas per zona harga.
    Aktivitas = jumlah candle yang menyentuh zona tersebut.
    """
    zone_activity = defaultdict(int)

    for d in data:
        high = float(d['high'])
        low = float(d['low'])

        # Candle spans dari low ke high - hitung semua zona yang disentuh
        low_zone_idx = int(low / zone_size)
        high_zone_idx = int(high / zone_size)

        for z_idx in range(low_zone_idx, high_zone_idx + 1):
            zone_mid = z_idx * zone_size + zone_size / 2
            zone_activity[zone_mid] += 1

    return zone_activity


def find_peak_zones(zone_activity):
    """
    Cari zona dengan aktivitas puncak (lebih tinggi dari tetangga).
    Return list of (price, activity) sorted by activity descending.
    """
    prices = sorted(zone_activity.keys())
    activities = [zone_activity[p] for p in prices]

    if len(prices) < 3:
        return [(p, zone_activity[p]) for p in prices]

    # Calculate median for filtering
    median_activity = statistics.median(activities)

    # Find local maxima (peaks)
    peaks = []
    for i in range(1, len(prices) - 1):
        if activities[i] > activities[i-1] and activities[i] > activities[i+1]:
            if activities[i] > median_activity:  # Only strong peaks
                peaks.append((prices[i], activities[i]))

    # Also check edges if they're high
    if activities[0] > median_activity and activities[0] > activities[1]:
        peaks.append((prices[0], activities[0]))
    if activities[-1] > median_activity and activities[-1] > activities[-2]:
        peaks.append((prices[-1], activities[-1]))

    # Sort by activity descending
    peaks.sort(key=lambda x: -x[1])

    return peaks


def get_nearest_sr_density(peaks, current_price, zone_size=500):
    """
    Cari support dan resistance terdekat dari peaks.
    Support = peak terdekat di bawah current_price
    Resistance = peak terdekat di atas current_price
    """
    supports = [(p, a) for p, a in peaks if p < current_price]
    resistances = [(p, a) for p, a in peaks if p > current_price]

    # Sort by distance to current price
    supports.sort(key=lambda x: current_price - x[0])
    resistances.sort(key=lambda x: x[0] - current_price)

    support = None
    resistance = None

    if supports:
        support = {
            'price': supports[0][0],
            'activity': supports[0][1],
            'zone_low': supports[0][0] - zone_size/2,
            'zone_high': supports[0][0] + zone_size/2
        }

    if resistances:
        resistance = {
            'price': resistances[0][0],
            'activity': resistances[0][1],
            'zone_low': resistances[0][0] - zone_size/2,
            'zone_high': resistances[0][0] + zone_size/2
        }

    return support, resistance


def calculate_vr(data, level_price, lookback=30, tolerance_pct=3.0):
    """Hitung Volume Ratio di sekitar level (untuk phase detection)"""
    level_high = level_price * (1 + tolerance_pct/100)
    level_low = level_price * (1 - tolerance_pct/100)

    # Use last 'lookback' days
    recent_data = data[-lookback:] if len(data) > lookback else data

    vol_lower, vol_upper = 0, 0
    for d in recent_data:
        if float(d['low']) <= level_high and float(d['high']) >= level_low:
            avg = (float(d['high']) + float(d['low'])) / 2
            if avg <= level_price:
                vol_lower += float(d['volume'])
            else:
                vol_upper += float(d['volume'])

    return vol_lower / vol_upper if vol_upper > 0 else (999.0 if vol_lower > 0 else 1.0)


def get_phase(vr):
    """Tentukan phase berdasarkan VR"""
    if vr >= 4.0:
        return 'STRONG_ACCUMULATION'
    elif vr >= 2.0:
        return 'ACCUMULATION'
    elif vr >= 1.5:
        return 'WEAK_ACCUMULATION'
    elif vr <= 0.5:
        return 'STRONG_DISTRIBUTION'
    elif vr <= 0.8:
        return 'DISTRIBUTION'
    else:
        return 'NEUTRAL'


def get_strong_sr_analysis(stock_code):
    """
    Get Strong S/R analysis untuk PANI/BREN/MBMA menggunakan V7 Density-Based.

    Returns dict dengan:
    - support: harga support (zona density)
    - resistance: harga resistance (zona density)
    - stop_loss: support - 5%
    - target: resistance - 2%
    - phase, vr, dll
    """
    conn = get_db_connection()
    try:
        # Load all data
        all_data = get_stock_data(stock_code, conn)
        if not all_data or len(all_data) < 60:
            return {'error': 'Insufficient data'}

        # Filter 1 tahun untuk deteksi S/R
        data_1year = filter_data_1year(all_data)
        if len(data_1year) < 30:
            data_1year = all_data

        # Calculate zone activity (V7 Density Method)
        zone_size = 500
        zone_activity = calculate_zone_activity(data_1year, zone_size)

        # Find peak zones
        peaks = find_peak_zones(zone_activity)

        # Current price
        current_price = float(all_data[-1]['close'])
        today = all_data[-1]

        # Get nearest S/R from density peaks
        support, resistance = get_nearest_sr_density(peaks, current_price, zone_size)

        if not support:
            return {'error': 'No support zone found'}

        support_price = support['price']
        resistance_price = resistance['price'] if resistance else current_price * 1.15

        # Load formula dari database
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM stock_formula WHERE stock_code = %s', (stock_code,))
        formula = cur.fetchone()

        sl_pct = float(formula.get('stop_loss_pct', 5.0)) / 100 if formula else 0.05
        tp_pct = float(formula.get('take_profit_pct', 2.0)) / 100 if formula else 0.02

        # Calculate SL & Target
        stop_loss = support_price * (1 - sl_pct)
        target = resistance_price * (1 - tp_pct)

        # Calculate VR & Phase at support zone
        vr = calculate_vr(data_1year, support_price)
        phase = get_phase(vr)

        # Distance from support
        dist_from_support = (current_price - support_price) / current_price * 100
        dist_from_resistance = (resistance_price - current_price) / current_price * 100 if resistance else 0

        # Entry criteria
        valid_phases = ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']
        near_support = dist_from_support <= 5.0
        is_valid_phase = phase in valid_phases

        # Score calculation
        score = 0
        if near_support:
            score += 20
        if vr >= 4.0:
            score += 40
        elif vr >= 2.0:
            score += 30
        elif vr >= 1.5:
            score += 15
        if support['activity'] >= 50:
            score += 15
        elif support['activity'] >= 30:
            score += 10

        confirmed = near_support and is_valid_phase and score >= 30

        # Determine action and reason based on V7 analysis
        if confirmed:
            action = 'ENTRY'
            action_reason = f"Dekat support zone Rp {support_price:,.0f} ({support['activity']}x) dalam fase {phase}"
        elif near_support and not is_valid_phase:
            action = 'WAIT'
            action_reason = f"Dekat support tapi fase {phase} - tunggu akumulasi"
        elif is_valid_phase and not near_support:
            action = 'WAIT'
            action_reason = f"Fase {phase} tapi jarak {dist_from_support:.1f}% dari support - tunggu pullback"
        elif phase in ['DISTRIBUTION', 'STRONG_DISTRIBUTION']:
            action = 'AVOID'
            action_reason = f"Fase {phase} (VR: {vr:.2f}x) - hindari entry"
        else:
            action = 'WAIT'
            action_reason = f"V7: Support Rp {support_price:,.0f} | Resistance Rp {resistance_price:,.0f}"

        return {
            'stock_code': stock_code,
            'current_price': current_price,
            'date': today['date'],

            # Action & Reason
            'action': action,
            'action_reason': action_reason,

            # Strong S/R values (V7 Density)
            'support': support_price,
            'support_activity': support['activity'],
            'support_zone': f"{support['zone_low']:,.0f}-{support['zone_high']:,.0f}",
            'resistance': resistance_price,
            'resistance_activity': resistance['activity'] if resistance else 0,
            'resistance_zone': f"{resistance['zone_low']:,.0f}-{resistance['zone_high']:,.0f}" if resistance else "N/A",

            # Calculated values
            'stop_loss': stop_loss,
            'target': target,

            # Phase info
            'vr': vr,
            'phase': phase,

            # Distances
            'dist_from_support': dist_from_support,
            'dist_from_resistance': dist_from_resistance,

            # Entry signal
            'score': score,
            'confirmed': confirmed,
            'near_support': near_support,
            'is_valid_phase': is_valid_phase,

            # Formula info
            'formula_info': {
                'type': 'STRONG_SR',
                'version': 'V7_DENSITY',
                'sl_pct': sl_pct * 100,
                'tp_pct': tp_pct * 100,
                'sl_formula': f"Support ({support_price:,.0f}) - {sl_pct*100:.0f}%",
                'tp_formula': f"Resistance ({resistance_price:,.0f}) - {tp_pct*100:.0f}%"
            },

            # All peaks for reference
            'all_peaks': peaks[:10]
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e)}
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    for stock in ['PANI', 'BREN', 'MBMA']:
        print('='*60)
        print(f'V7 STRONG S/R ANALYSIS (Density-Based): {stock}')
        print('='*60)

        result = get_strong_sr_analysis(stock)

        if result.get('error'):
            print(f'Error: {result["error"]}')
            continue

        print(f"""
Current Price : Rp {result['current_price']:,.0f}

=== SUPPORT ===
  Zone    : {result['support_zone']}
  Center  : Rp {result['support']:,.0f}
  Activity: {result['support_activity']}x candles

=== RESISTANCE ===
  Zone    : {result['resistance_zone']}
  Center  : Rp {result['resistance']:,.0f}
  Activity: {result['resistance_activity']}x candles

=== TRADING LEVELS ===
  Stop Loss : Rp {result['stop_loss']:,.0f} (Support - {result['formula_info']['sl_pct']:.0f}%)
  Target    : Rp {result['target']:,.0f} (Resistance - {result['formula_info']['tp_pct']:.0f}%)

=== PHASE ANALYSIS ===
  Phase : {result['phase']}
  VR    : {result['vr']:.2f}x
  Score : {result['score']}

=== SIGNAL ===
  Action: {result['action']}
  Reason: {result['action_reason']}
""")
