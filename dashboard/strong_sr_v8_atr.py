# -*- coding: utf-8 -*-
"""
STRONG S/R ANALYZER V8 - ATR-Quality Based
==========================================
Formula untuk PTRO, CBDK, BREN, BRPT, CDIA dengan metode ATR-Quality.

Metode V8 (berbeda dari V7 Density):
1. ATR(14) untuk toleransi zona dinamis
2. Pivot detection (fractal 3 kiri 3 kanan)
3. Clustering level ke "bucket" berdasarkan tolerance
4. Strength Score = Touches * (0.7 + 0.6*Quality) * LN(1+AvgVol)
5. Filter: Touches >= 3, Quality >= 0.5

Backtest Result (2025-01-02 s/d sekarang):
- Win Rate: 55.6%
- Total PnL: +62.69%
- Lebih baik dari V7 (Win Rate 28.6%, PnL -25.90%)
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from collections import defaultdict
import math
import statistics

def get_db_connection():
    """Get database connection - uses DATABASE_URL for Railway, localhost for local dev"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host='localhost',
            database='stock_analysis',
            user='postgres',
            password='postgres'
        )


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


def get_custom_sr_zones(stock_code, conn):
    """Get custom S/R zones from database if available"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT zone_type, level_low, level_high, priority
        FROM stock_sr_zones
        WHERE stock_code = %s
        ORDER BY priority ASC
    ''', (stock_code,))
    rows = cur.fetchall()

    if not rows:
        return None, None

    supports = []
    resistances = []

    for row in rows:
        zone = {
            'level': (float(row['level_low']) + float(row['level_high'])) / 2,  # midpoint
            'level_low': float(row['level_low']),
            'level_high': float(row['level_high']),
            'touches': 99,  # high value for manual zones
            'bounces': 99,  # high value for manual zones
            'quality': 1.0,  # 100% quality for manual zones
            'score': 100 - row['priority'],  # priority 1 = score 99, priority 2 = score 98, etc
            'avg_volume': 0,
            'is_manual': True
        }

        if row['zone_type'].lower() == 'support':
            supports.append(zone)
        else:
            resistances.append(zone)

    return supports, resistances


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


# ================== ATR CALCULATION ==================

def calculate_true_range(data):
    """
    Hitung True Range untuk setiap candle.
    TR = MAX(High-Low, ABS(High-PrevClose), ABS(Low-PrevClose))
    """
    tr_list = []
    for i, d in enumerate(data):
        high = float(d['high'])
        low = float(d['low'])

        if i == 0:
            tr = high - low
        else:
            prev_close = float(data[i-1]['close'])
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
        tr_list.append(tr)
    return tr_list


def calculate_atr(tr_list, period=14):
    """Hitung ATR(14) - rolling average dari True Range"""
    atr_list = []
    for i in range(len(tr_list)):
        if i < period - 1:
            atr_list.append(None)
        else:
            atr = sum(tr_list[i-period+1:i+1]) / period
            atr_list.append(atr)
    return atr_list


def calculate_tolerance(data, atr_list):
    """
    Toleransi zona SR dinamis:
    = MAX(0.6 * MEDIAN(ATR14), 0.005 * Close_terakhir)
    """
    valid_atr = [a for a in atr_list if a is not None]
    if not valid_atr:
        return float(data[-1]['close']) * 0.005

    median_atr = statistics.median(valid_atr)
    current_close = float(data[-1]['close'])

    tol_price = max(0.6 * median_atr, 0.005 * current_close)
    return tol_price


# ================== PIVOT DETECTION ==================

def detect_pivots(data, left_bars=3, right_bars=3):
    """
    Detect pivot highs dan lows (fractal).
    Pivot low: Low = MIN dari 7 candle (3 kiri + current + 3 kanan)
    Pivot high: High = MAX dari 7 candle
    """
    pivot_lows = []
    pivot_highs = []

    for i in range(left_bars, len(data) - right_bars):
        current_low = float(data[i]['low'])
        current_high = float(data[i]['high'])

        # Check pivot low
        window_lows = [float(data[j]['low']) for j in range(i - left_bars, i + right_bars + 1)]
        if current_low == min(window_lows):
            pivot_lows.append({
                'index': i,
                'date': data[i]['date'],
                'price': current_low,
                'type': 'SUPPORT'
            })

        # Check pivot high
        window_highs = [float(data[j]['high']) for j in range(i - left_bars, i + right_bars + 1)]
        if current_high == max(window_highs):
            pivot_highs.append({
                'index': i,
                'date': data[i]['date'],
                'price': current_high,
                'type': 'RESISTANCE'
            })

    return pivot_lows, pivot_highs


# ================== CLUSTERING & SCORING ==================

def cluster_levels(pivots, tol_price):
    """
    Cluster pivot levels ke "bucket" berdasarkan toleransi.
    Bucket level = ROUND(pivot_price / tol_price) * tol_price
    """
    buckets = defaultdict(list)

    for pivot in pivots:
        bucket_level = round(pivot['price'] / tol_price) * tol_price
        buckets[bucket_level].append(pivot)

    return buckets


def calculate_strength_score(data, level, tol_price, level_type='SUPPORT'):
    """
    Hitung Strength Score untuk setiap level:
    - Touches: jumlah hari yang menyentuh zona
    - Bounce: jumlah hari yang memantul (close > level untuk support)
    - Quality = Bounce / Touches
    - AvgVol: rata-rata volume saat touch
    - Score = Touches * (0.7 + 0.6*Quality) * LN(1+AvgVol)
    """
    touches = 0
    bounces = 0
    touch_volumes = []

    level_high = level + tol_price
    level_low = level - tol_price

    for d in data:
        low = float(d['low'])
        high = float(d['high'])
        close = float(d['close'])
        volume = float(d['volume'])

        if level_type == 'SUPPORT':
            # Touch support: Low masuk band
            if low >= level_low and low <= level_high:
                touches += 1
                touch_volumes.append(volume)
                # Bounce: close di atas level
                if close > level:
                    bounces += 1
        else:  # RESISTANCE
            # Touch resistance: High masuk band
            if high >= level_low and high <= level_high:
                touches += 1
                touch_volumes.append(volume)
                # Bounce: close di bawah level
                if close < level:
                    bounces += 1

    if touches == 0:
        return {
            'level': level,
            'touches': 0,
            'bounces': 0,
            'quality': 0,
            'avg_vol': 0,
            'score': 0
        }

    quality = bounces / touches
    avg_vol = sum(touch_volumes) / len(touch_volumes) if touch_volumes else 0

    # Score formula: Touches * (0.7 + 0.6*Quality) * LN(1+AvgVol)
    # Normalize volume untuk LN calculation
    vol_factor = math.log(1 + avg_vol / 1000000)  # Normalize to millions
    score = touches * (0.7 + 0.6 * quality) * vol_factor

    return {
        'level': level,
        'touches': touches,
        'bounces': bounces,
        'quality': quality,
        'avg_vol': avg_vol,
        'score': score
    }


def get_strong_levels(data, tol_price):
    """
    Get semua strong levels dengan ATR-Quality method.
    Filter: Touches >= 3, Quality >= 0.5
    """
    # Detect pivots
    pivot_lows, pivot_highs = detect_pivots(data)

    # Cluster ke buckets
    support_buckets = cluster_levels(pivot_lows, tol_price)
    resistance_buckets = cluster_levels(pivot_highs, tol_price)

    # Calculate scores untuk setiap bucket
    support_levels = []
    for level, pivots in support_buckets.items():
        score_data = calculate_strength_score(data, level, tol_price, 'SUPPORT')
        score_data['type'] = 'SUPPORT'
        score_data['pivot_count'] = len(pivots)
        support_levels.append(score_data)

    resistance_levels = []
    for level, pivots in resistance_buckets.items():
        score_data = calculate_strength_score(data, level, tol_price, 'RESISTANCE')
        score_data['type'] = 'RESISTANCE'
        score_data['pivot_count'] = len(pivots)
        resistance_levels.append(score_data)

    # Filter: Touches >= 3, Quality >= 0.5
    strong_supports = [s for s in support_levels if s['touches'] >= 3 and s['quality'] >= 0.5]
    strong_resistances = [r for r in resistance_levels if r['touches'] >= 3 and r['quality'] >= 0.5]

    # Sort by score descending
    strong_supports.sort(key=lambda x: -x['score'])
    strong_resistances.sort(key=lambda x: -x['score'])

    return strong_supports, strong_resistances


def get_nearest_sr(strong_supports, strong_resistances, current_price, min_distance_pct=5.0, max_support_distance_pct=30.0):
    """
    Get support dan resistance dari strong levels.

    Untuk CUSTOM zones (is_manual=True): gunakan NEAREST (terdekat)
    Untuk AUTO-detected: gunakan STRONGEST (score tertinggi)

    Support: di bawah harga, dalam jarak maksimal max_support_distance_pct%
    Resistance: dengan jarak minimal min_distance_pct%
    """
    # Check if using custom zones
    is_custom = strong_supports and strong_supports[0].get('is_manual', False)

    # ===== SUPPORT =====
    min_support_level = current_price * (1 - max_support_distance_pct / 100)

    # Filter support: di bawah harga DAN dalam jarak maksimal
    valid_supports = [s for s in strong_supports if min_support_level <= s['level'] < current_price]

    # Jika tidak ada support dalam jarak, gunakan semua di bawah harga
    if not valid_supports:
        valid_supports = [s for s in strong_supports if s['level'] < current_price]

    if is_custom:
        # Custom zones: sort by NEAREST (closest to current price)
        valid_supports.sort(key=lambda x: current_price - x['level'])
    else:
        # Auto-detected: sort by SCORE descending (strongest first)
        valid_supports.sort(key=lambda x: -x['score'])

    # ===== RESISTANCE =====
    min_resistance_level = current_price * (1 + min_distance_pct / 100)

    # Filter resistance yang jaraknya >= min_distance_pct%
    valid_resistances = [r for r in strong_resistances if r['level'] >= min_resistance_level]

    # Jika tidak ada resistance dengan jarak cukup, gunakan semua yang di atas harga
    if not valid_resistances:
        valid_resistances = [r for r in strong_resistances if r['level'] > current_price]

    if is_custom:
        # Custom zones: sort by NEAREST (closest to current price)
        valid_resistances.sort(key=lambda x: x['level'] - current_price)
    else:
        # Auto-detected: sort by SCORE descending (strongest first)
        valid_resistances.sort(key=lambda x: -x['score'])

    support = valid_supports[0] if valid_supports else None
    resistance = valid_resistances[0] if valid_resistances else None

    return support, resistance


# ================== PHASE DETECTION ==================

def calculate_vr(data, level_price, lookback=30, tolerance_pct=3.0):
    """Hitung Volume Ratio di sekitar level (untuk phase detection)"""
    level_high = level_price * (1 + tolerance_pct/100)
    level_low = level_price * (1 - tolerance_pct/100)

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


# ================== MAIN ANALYSIS ==================

def get_strong_sr_analysis(stock_code):
    """
    Get S/R analysis menggunakan V10 RETEST+BREAKOUT method.

    Returns dict dengan:
    - support: harga support (zone_low)
    - resistance: harga resistance
    - stop_loss: zone_low - 5%
    - target: resistance - 2%
    - phase, vr, quality, dll
    - v10_position: posisi terbuka jika ada
    - v10_criteria: kriteria V10 yang terpenuhi
    """
    conn = get_db_connection()
    try:
        all_data = get_stock_data(stock_code, conn)
        if not all_data or len(all_data) < 60:
            return {'error': 'Insufficient data'}

        # Filter 1 tahun
        data_1year = filter_data_1year(all_data)
        if len(data_1year) < 30:
            data_1year = all_data

        # Calculate ATR
        tr_list = calculate_true_range(data_1year)
        atr_list = calculate_atr(tr_list)

        # Calculate tolerance
        tol_price = calculate_tolerance(data_1year, atr_list)

        # Check for custom S/R zones first
        custom_supports, custom_resistances = get_custom_sr_zones(stock_code, conn)

        if custom_supports and custom_resistances:
            # Use custom zones
            strong_supports = custom_supports
            strong_resistances = custom_resistances
            using_custom = True
        else:
            # Use auto-detected levels
            strong_supports, strong_resistances = get_strong_levels(data_1year, tol_price)
            using_custom = False

        # Current price
        current_price = float(all_data[-1]['close'])
        today = all_data[-1]

        # Get nearest S/R
        support, resistance = get_nearest_sr(strong_supports, strong_resistances, current_price)

        if not support:
            return {'error': 'No strong support found (Quality < 50% atau Touches < 3)'}

        support_price = support['level']
        support_zone_low = support.get('level_low', support_price * 0.97)
        support_zone_high = support.get('level_high', support_price * 1.03)
        resistance_price = resistance['level'] if resistance else current_price * 1.15

        # Load formula dari database
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM stock_formula WHERE stock_code = %s', (stock_code,))
        formula = cur.fetchone()

        sl_pct = float(formula.get('stop_loss_pct', 5.0)) / 100 if formula else 0.05
        tp_pct = float(formula.get('take_profit_pct', 2.0)) / 100 if formula else 0.02

        # V10: SL dari zone_low (bukan level)
        stop_loss = support_zone_low * (1 - sl_pct)
        target = resistance_price * (1 - tp_pct)

        # Calculate VR & Phase
        vr = calculate_vr(data_1year, support_price)
        phase = get_phase(vr)

        # Distance from support
        dist_from_support = (current_price - support_price) / current_price * 100
        dist_from_resistance = (resistance_price - current_price) / current_price * 100 if resistance else 0

        # ========== V10 LOGIC ==========
        # Check for open V10 position
        v10_result = backtest_v10(stock_code, '2025-01-02')
        v10_trades = v10_result.get('trades', [])
        open_positions = [t for t in v10_trades if t.get('result') == 'OPEN']

        v10_position = None
        v10_criteria = None
        action = 'WAIT'
        action_reason = ''

        if open_positions:
            # Ada posisi terbuka V10
            pos = open_positions[0]
            entry_price = pos['entry_price']
            current_pnl = (current_price - entry_price) / entry_price * 100

            v10_position = {
                'type': pos['type'],
                'entry_date': str(pos['entry_date'])[:10],
                'entry_price': entry_price,
                'current_price': current_price,
                'current_pnl': current_pnl,
                'stop_loss': pos['stop_loss'],
                'target': pos['target'],
                'phase': pos['phase'],
                'confirm_reason': pos.get('confirm_reason', '')
            }

            # Update SL dan target dari V10 position
            stop_loss = pos['stop_loss']
            target = pos['target']

            # Kriteria V10 yang terpenuhi
            trade_type = pos['type']
            if 'RETEST' in trade_type:
                v10_criteria = {
                    'high_touch_resistance': True,
                    'high_touch_resistance_desc': f"HIGH menyentuh Resistance {resistance_price:,.0f}",
                    'low_touch_support': True,
                    'low_touch_support_desc': f"LOW menyentuh Support {support_zone_low:,.0f}-{support_zone_high:,.0f}",
                    'in_range_35pct': True,
                    'in_range_35pct_desc': f"Close dalam range 35% (max {support_zone_high * 1.35:,.0f})",
                    'hold_above_support': True,
                    'hold_above_support_desc': f"HOLD di atas support (>= {support_zone_low:,.0f})",
                    'confirmation': pos.get('confirm_reason', 'CLOSE_STRENGTH'),
                    'confirmation_desc': f"Konfirmasi: {pos.get('confirm_reason', 'CLOSE_STRENGTH')}"
                }
            elif 'BREAKOUT' in trade_type:
                v10_criteria = {
                    'breakout_above_resistance': True,
                    'breakout_above_resistance_desc': f"Close > Resistance {support_zone_high:,.0f}",
                    'hold_3_days': True,
                    'hold_3_days_desc': "Hold di atas zona 3 hari berturut-turut",
                    'confirmation': 'BREAKOUT_' + ('HOLD' if 'HOLD' in trade_type else 'PULLBACK'),
                    'confirmation_desc': f"Konfirmasi: {trade_type}"
                }

            action = 'ALREADY_ENTRY'
            action_reason = f"V10 {pos['type']} Entry {pos['entry_date']} @ Rp {entry_price:,.0f} | PnL: {current_pnl:+.2f}%"

        else:
            # Tidak ada posisi terbuka - cek kondisi saat ini
            valid_phases = ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']
            near_support = dist_from_support <= 5.0
            is_valid_phase = phase in valid_phases
            is_quality_ok = support['quality'] >= 0.5
            is_touches_ok = support['touches'] >= 3

            # V10 criteria check for potential entry
            in_range_35 = current_price <= support_zone_high * 1.35
            is_reclaim = current_price > support_zone_high

            if phase in ['DISTRIBUTION', 'STRONG_DISTRIBUTION']:
                if is_reclaim and in_range_35:
                    action = 'WATCH'
                    action_reason = f"Fase {phase} tapi RECLAIM (close > {support_zone_high:,.0f}) - monitoring V10 RETEST"
                else:
                    action = 'AVOID'
                    action_reason = f"Fase {phase} (VR: {vr:.2f}x) - hindari entry"
            elif near_support and is_valid_phase:
                action = 'ENTRY'
                action_reason = f"V10: Support {support_zone_low:,.0f}-{support_zone_high:,.0f} | Fase {phase}"
            elif near_support:
                action = 'WAIT'
                action_reason = f"Dekat support tapi fase {phase} - tunggu konfirmasi V10"
            else:
                action = 'WAIT'
                action_reason = f"V10: Monitoring support {support_zone_low:,.0f}-{support_zone_high:,.0f}"

        return {
            'stock_code': stock_code,
            'current_price': current_price,
            'date': today['date'],

            # Action & Reason
            'action': action,
            'action_reason': action_reason,

            # Method info
            'method': 'V10_RETEST_BREAKOUT',
            'tolerance': tol_price,
            'atr14': atr_list[-1] if atr_list[-1] else 0,

            # Support info (V10: menggunakan zone)
            'support': support_price,
            'support_zone_low': support_zone_low,
            'support_zone_high': support_zone_high,
            'support_touches': support['touches'],
            'support_bounces': support['bounces'],
            'support_quality': support['quality'],
            'support_score': support['score'],
            'support_zone': f"{support_zone_low:,.0f}-{support_zone_high:,.0f}",

            # Resistance info
            'resistance': resistance_price,
            'resistance_touches': resistance['touches'] if resistance else 0,
            'resistance_bounces': resistance['bounces'] if resistance else 0,
            'resistance_quality': resistance['quality'] if resistance else 0,
            'resistance_score': resistance['score'] if resistance else 0,
            'resistance_zone': f"{resistance_price - tol_price:,.0f}-{resistance_price + tol_price:,.0f}" if resistance else "N/A",

            # Trading levels (V10: SL dari zone_low)
            'stop_loss': stop_loss,
            'target': target,

            # Phase
            'vr': vr,
            'phase': phase,

            # Distances
            'dist_from_support': dist_from_support,
            'dist_from_resistance': dist_from_resistance,

            # V10 Position & Criteria
            'v10_position': v10_position,
            'v10_criteria': v10_criteria,

            # V10 Performance
            'v10_performance': {
                'total_trades': v10_result.get('total_trades', 0),
                'wins': v10_result.get('wins', 0),
                'losses': v10_result.get('losses', 0),
                'win_rate': v10_result.get('win_rate', 0),
                'total_pnl': v10_result.get('total_pnl', 0),
                'avg_pnl': v10_result.get('avg_pnl', 0),
                'open_trades': len(open_positions)
            },

            # V10 Trade History
            'v10_trades': v10_trades,

            # Formula info
            'formula_info': {
                'type': 'STRONG_SR',
                'version': 'V10_RETEST_BREAKOUT',
                'sl_pct': sl_pct * 100,
                'tp_pct': tp_pct * 100,
                'sl_formula': f"Zone Low ({support_zone_low:,.0f}) - {sl_pct*100:.0f}%",
                'tp_formula': f"Resistance ({resistance_price:,.0f}) - {tp_pct*100:.0f}%"
            },

            # All levels for reference
            'all_supports': strong_supports[:5],
            'all_resistances': strong_resistances[:5]
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e)}
    finally:
        conn.close()


# ================== BACKTEST ==================

def backtest_v8(stock_code, start_date='2025-01-02'):
    """
    Backtest V8 ATR-Quality method untuk stock tertentu.
    """
    conn = get_db_connection()
    try:
        all_data = get_stock_data(stock_code, conn)
        if not all_data:
            return {'error': 'No data', 'trades': []}

        # Get formula
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM stock_formula WHERE stock_code = %s', (stock_code,))
        formula = cur.fetchone()

        sl_pct = float(formula.get('stop_loss_pct', 5.0)) / 100 if formula else 0.05
        tp_pct = float(formula.get('take_profit_pct', 2.0)) / 100 if formula else 0.02
        valid_phases = ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']

        # Filter 1 tahun untuk S/R detection
        data_1year = filter_data_1year(all_data)
        if len(data_1year) < 30:
            data_1year = all_data

        # Calculate ATR & tolerance
        tr_list = calculate_true_range(data_1year)
        atr_list = calculate_atr(tr_list)
        tol_price = calculate_tolerance(data_1year, atr_list)

        # Check for custom S/R zones first
        custom_supports, custom_resistances = get_custom_sr_zones(stock_code, conn)

        if custom_supports and custom_resistances:
            # Use custom zones
            strong_supports = custom_supports
            strong_resistances = custom_resistances
        else:
            # Use auto-detected levels
            strong_supports, strong_resistances = get_strong_levels(data_1year, tol_price)

        trades = []
        position = None

        # Find start index
        start_idx = 60
        for i, d in enumerate(all_data):
            if str(d['date']) >= start_date and i >= 60:
                start_idx = i
                break

        for i in range(start_idx, len(all_data)):
            price = float(all_data[i]['close'])

            # Get nearest S/R
            support, resistance = get_nearest_sr(strong_supports, strong_resistances, price)

            if position is None:
                if support:
                    dist = (price - support['level']) / price * 100
                    if dist <= 5.0:  # Within 5% of support
                        vr = calculate_vr(all_data[:i+1], support['level'])
                        phase = get_phase(vr)

                        if phase in valid_phases:
                            # Quality check
                            if support['quality'] >= 0.5 and support['touches'] >= 3:
                                if i + 1 < len(all_data):
                                    next_day = all_data[i + 1]
                                    entry_price = float(next_day['open'])
                                    sl = support['level'] * (1 - sl_pct)
                                    tp = resistance['level'] * (1 - tp_pct) if resistance else entry_price * 1.15

                                    # PENTING: Jangan entry jika entry_price >= target (tidak ada upside)
                                    if entry_price >= tp:
                                        continue  # Skip entry, tidak ada potensi profit

                                    position = {
                                        'signal_date': all_data[i]['date'],
                                        'entry_date': next_day['date'],
                                        'entry_price': entry_price,
                                        'support': support['level'],
                                        'support_quality': support['quality'],
                                        'support_touches': support['touches'],
                                        'resistance': resistance['level'] if resistance else None,
                                        'stop_loss': sl,
                                        'target': tp,
                                        'phase': phase,
                                        'vr': vr
                                    }
            else:
                # Check exit
                exit_reason = None

                if price <= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                elif price >= position['target']:
                    exit_reason = 'TARGET'

                if exit_reason:
                    pnl = (price - position['entry_price']) / position['entry_price'] * 100
                    trades.append({
                        **position,
                        'exit_date': all_data[i]['date'],
                        'exit_price': price,
                        'exit_reason': exit_reason,
                        'pnl': pnl,
                        'result': 'WIN' if pnl > 0 else 'LOSS',
                        'days_held': (all_data[i]['date'] - position['entry_date']).days
                    })
                    position = None

        # If still in position
        if position:
            last = all_data[-1]
            pnl = (float(last['close']) - position['entry_price']) / position['entry_price'] * 100
            trades.append({
                **position,
                'exit_date': last['date'],
                'exit_price': float(last['close']),
                'exit_reason': 'OPEN',
                'pnl': pnl,
                'result': 'OPEN',
                'days_held': (last['date'] - position['entry_date']).days
            })

        # Summary
        closed = [t for t in trades if t['exit_reason'] != 'OPEN']
        wins = [t for t in closed if t['pnl'] > 0]

        return {
            'method': 'V8_ATR_QUALITY',
            'stock_code': stock_code,
            'tolerance': tol_price,
            'total_trades': len(trades),
            'closed_trades': len(closed),
            'open_trades': len(trades) - len(closed),
            'wins': len(wins),
            'losses': len(closed) - len(wins),
            'win_rate': len(wins) / len(closed) * 100 if closed else 0,
            'total_pnl': sum(t['pnl'] for t in closed),
            'avg_pnl': sum(t['pnl'] for t in closed) / len(closed) if closed else 0,
            'trades': trades
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'trades': []}
    finally:
        conn.close()


def backtest_v9(stock_code, start_date='2025-01-02'):
    """
    Backtest V9 - Retest Pattern (khusus untuk stock dengan custom S/R zones)

    Syarat Entry:
    1. Harga harus menyentuh/mencapai resistance dulu (within 3% of resistance zone)
    2. Kemudian turun kembali ke support
    3. Di support harus memenuhi kriteria V8:
       - Within 5% of support
       - Phase: ACCUMULATION
       - Quality >= 50%
       - Touches >= 3
    """
    conn = get_db_connection()
    try:
        all_data = get_stock_data(stock_code, conn)
        if not all_data:
            return {'error': 'No data', 'trades': []}

        # Get formula
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM stock_formula WHERE stock_code = %s', (stock_code,))
        formula = cur.fetchone()

        sl_pct = float(formula.get('stop_loss_pct', 5.0)) / 100 if formula else 0.05
        tp_pct = float(formula.get('take_profit_pct', 2.0)) / 100 if formula else 0.02
        valid_phases = ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']

        # V9 REQUIRES custom zones
        custom_supports, custom_resistances = get_custom_sr_zones(stock_code, conn)

        if not custom_supports or not custom_resistances:
            return {'error': 'V9 requires custom S/R zones', 'trades': []}

        strong_supports = custom_supports
        strong_resistances = custom_resistances

        trades = []
        position = None
        touched_resistance = None  # Track which resistance was touched
        touched_resistance_date = None

        # Find start index
        start_idx = 60
        for i, d in enumerate(all_data):
            if str(d['date']) >= start_date and i >= 60:
                start_idx = i
                break

        for i in range(start_idx, len(all_data)):
            price = float(all_data[i]['close'])
            high = float(all_data[i]['high'])

            # Get nearest S/R based on current price
            support, resistance = get_nearest_sr(strong_supports, strong_resistances, price)

            # ===== STEP 1: Check if price touches resistance =====
            # Update to HIGHEST resistance touched (not just first)
            if resistance and position is None:
                resistance_zone_low = resistance.get('level_low', resistance['level'] * 0.97)
                if high >= resistance_zone_low:
                    # Only update if this resistance is HIGHER than previous
                    if touched_resistance is None or resistance['level'] > touched_resistance['level']:
                        touched_resistance = resistance
                        touched_resistance_date = all_data[i]['date']

            # ===== STEP 2: Entry at support ONLY if resistance was touched =====
            if position is None and touched_resistance is not None:
                if support:
                    dist = (price - support['level']) / price * 100
                    if 0 <= dist <= 5.0:  # Within 5% of support
                        vr = calculate_vr(all_data[:i+1], support['level'])
                        phase = get_phase(vr)

                        # V8 criteria: Phase + Quality + Touches
                        if phase in valid_phases and support['quality'] >= 0.5 and support['touches'] >= 3:
                            if i + 1 < len(all_data):
                                next_day = all_data[i + 1]
                                entry_price = float(next_day['open'])
                                sup_zone_low = support.get('level_low', support['level'] * 0.97)
                                sl = sup_zone_low * (1 - sl_pct)  # 5% di bawah zona support
                                tp = touched_resistance['level'] * (1 - tp_pct)

                                # Skip if no upside
                                if entry_price >= tp:
                                    continue

                                position = {
                                    'signal_date': all_data[i]['date'],
                                    'entry_date': next_day['date'],
                                    'entry_price': entry_price,
                                    'support': support['level'],
                                    'support_quality': support['quality'],
                                    'support_touches': support['touches'],
                                    'resistance': touched_resistance['level'],
                                    'resistance_touched_date': touched_resistance_date,
                                    'stop_loss': sl,
                                    'target': tp,
                                    'phase': phase,
                                    'vr': vr
                                }
                                # Reset touched_resistance after entry
                                touched_resistance = None
                                touched_resistance_date = None

            # ===== STEP 3: Check exit conditions =====
            elif position is not None:
                exit_reason = None
                exit_price = None
                low = float(all_data[i]['low'])

                # SL: cek dengan LOW, TP: cek dengan HIGH
                if low <= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = position['stop_loss']
                elif high >= position['target']:
                    exit_reason = 'TARGET'
                    exit_price = position['target']

                if exit_reason:
                    pnl = (exit_price - position['entry_price']) / position['entry_price'] * 100
                    trades.append({
                        **position,
                        'exit_date': all_data[i]['date'],
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl': pnl,
                        'result': 'WIN' if pnl > 0 else 'LOSS',
                        'days_held': (all_data[i]['date'] - position['entry_date']).days
                    })
                    position = None

        # If still in position
        if position:
            last = all_data[-1]
            pnl = (float(last['close']) - position['entry_price']) / position['entry_price'] * 100
            trades.append({
                **position,
                'exit_date': last['date'],
                'exit_price': float(last['close']),
                'exit_reason': 'OPEN',
                'pnl': pnl,
                'result': 'OPEN',
                'days_held': (last['date'] - position['entry_date']).days
            })

        # Summary
        closed = [t for t in trades if t['exit_reason'] != 'OPEN']
        wins = [t for t in closed if t['pnl'] > 0]

        return {
            'method': 'V9_RETEST_PATTERN',
            'stock_code': stock_code,
            'total_trades': len(trades),
            'closed_trades': len(closed),
            'open_trades': len(trades) - len(closed),
            'wins': len(wins),
            'losses': len(closed) - len(wins),
            'win_rate': len(wins) / len(closed) * 100 if closed else 0,
            'total_pnl': sum(t['pnl'] for t in closed),
            'avg_pnl': sum(t['pnl'] for t in closed) / len(closed) if closed else 0,
            'trades': trades
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'trades': []}
    finally:
        conn.close()


def backtest_v10(stock_code, start_date='2025-01-02'):
    """
    Backtest V10 - RETEST + BREAKOUT (dengan/tanpa pullback)

    RETEST:
    1. HIGH menyentuh zona resistance
    2. Tidak menembus, kembali ke bawah
    3. LOW menyentuh zona support di bawahnya → aktifkan V8
    4. SL: 5% di bawah zona support

    BREAKOUT tanpa Pullback:
    1. Close di ATAS zona resistance (dari bawah)
    2. Besoknya close juga di ATAS zona resistance (2 hari berturut)
    3. Aktifkan V8
    4. SL: 5% di bawah zona breakout

    BREAKOUT dengan Pullback:
    1. Close di ATAS zona resistance (dari bawah)
    2. Besoknya close DALAM zona (pullback) → V8 tidak aktif
    3. Menembus lagi ke atas + besoknya tutup di atas → aktifkan V8
    4. SL: 5% di bawah zona breakout
    """
    conn = get_db_connection()
    try:
        all_data = get_stock_data(stock_code, conn)
        if not all_data:
            return {'error': 'No data', 'trades': []}

        # Get formula
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM stock_formula WHERE stock_code = %s', (stock_code,))
        formula = cur.fetchone()

        sl_pct = float(formula.get('stop_loss_pct', 5.0)) / 100 if formula else 0.05
        tp_pct = float(formula.get('take_profit_pct', 2.0)) / 100 if formula else 0.02
        valid_phases = ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']

        # V10 REQUIRES custom zones
        custom_supports, custom_resistances = get_custom_sr_zones(stock_code, conn)

        if not custom_supports or not custom_resistances:
            return {'error': 'V10 requires custom S/R zones', 'trades': []}

        strong_supports = custom_supports
        strong_resistances = custom_resistances

        trades = []
        position = None

        # RETEST tracking: HIGH menyentuh resistance → siap di support bawahnya
        retest_tracking = {}  # {res_level: {'date': date, 'support_target': zone}}

        # BREAKOUT tracking
        # State: None, 'first_close_above', 'pullback', 'second_close_above'
        breakout_tracking = {}  # {zone_level: {'state': str, 'first_date': date, 'zone': zone}}

        # Find start index
        start_idx = 60
        for i, d in enumerate(all_data):
            if str(d['date']) >= start_date and i >= 60:
                start_idx = i
                break

        for i in range(start_idx, len(all_data)):
            d = all_data[i]
            price = float(d['close'])
            high = float(d['high'])
            low = float(d['low'])
            date_str = str(d['date'])[:10]

            # Get previous day close for breakout check
            prev_close = float(all_data[i-1]['close']) if i > 0 else price

            # ===== EXIT CHECK =====
            if position is not None:
                exit_reason = None
                exit_price = None

                # SL: cek dengan LOW, TP: cek dengan HIGH
                if low <= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = position['stop_loss']
                elif high >= position['target']:
                    exit_reason = 'TARGET'
                    exit_price = position['target']

                if exit_reason:
                    pnl = (exit_price - position['entry_price']) / position['entry_price'] * 100
                    trades.append({
                        **position,
                        'exit_date': d['date'],
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl': pnl,
                        'result': 'WIN' if pnl > 0 else 'LOSS',
                        'days_held': (d['date'] - position['entry_date']).days
                    })
                    position = None
                    retest_tracking = {}
                    breakout_tracking = {}
                    continue

            # ===== RETEST TRACKING =====
            # HIGH menyentuh resistance → siap V8 di support bawahnya
            if position is None:
                for res_zone in strong_resistances:
                    res_zone_low = res_zone.get('level_low', res_zone['level'] * 0.97)
                    res_zone_high = res_zone.get('level_high', res_zone['level'] * 1.03)
                    zone_key = res_zone['level']

                    # HIGH menyentuh zona resistance
                    if high >= res_zone_low and price <= res_zone_high:
                        # Find support di bawah resistance ini
                        lower_supports = [s for s in strong_supports if s['level'] < res_zone['level']]
                        if lower_supports:
                            target_support = max(lower_supports, key=lambda x: x['level'])
                            retest_tracking[zone_key] = {
                                'touched_date': d['date'],
                                'resistance': res_zone,
                                'support_target': target_support
                            }

            # ===== BREAKOUT TRACKING =====
            if position is None:
                for res_zone in strong_resistances:
                    res_zone_low = res_zone.get('level_low', res_zone['level'] * 0.97)
                    res_zone_high = res_zone.get('level_high', res_zone['level'] * 1.03)
                    zone_key = res_zone['level']

                    # Check if close is above zone
                    is_above = price > res_zone_high
                    was_below_or_in = prev_close <= res_zone_high

                    if is_above:
                        if zone_key not in breakout_tracking:
                            # First close above zone - ONLY if previously below/in zone
                            if was_below_or_in:
                                breakout_tracking[zone_key] = {
                                    'state': 'first_above',
                                    'first_date': d['date'],
                                    'zone': res_zone,
                                    'consecutive': 1
                                }
                        else:
                            tracking = breakout_tracking[zone_key]
                            if tracking['state'] == 'first_above':
                                # Second day above (konfirmasi hari ke-1)
                                tracking['state'] = 'second_above'
                                tracking['consecutive'] = 2
                            elif tracking['state'] == 'second_above':
                                # Third day above = BREAKOUT tanpa pullback (3 hari berturut)
                                tracking['state'] = 'confirmed_no_pullback'
                                tracking['consecutive'] = 3
                            elif tracking['state'] == 'pullback':
                                # First day above after pullback
                                tracking['state'] = 'first_above_after_pullback'
                                tracking['consecutive'] = 1
                            elif tracking['state'] == 'first_above_after_pullback':
                                # Second day above after pullback (konfirmasi hari ke-1)
                                tracking['state'] = 'second_above_after_pullback'
                                tracking['consecutive'] = 2
                            elif tracking['state'] == 'second_above_after_pullback':
                                # Third day above after pullback = BREAKOUT dengan pullback (3 hari)
                                tracking['state'] = 'confirmed_with_pullback'
                                tracking['consecutive'] = 3
                    else:
                        # Close inside or below zone
                        if zone_key in breakout_tracking:
                            tracking = breakout_tracking[zone_key]
                            if tracking['state'] in ['first_above', 'second_above']:
                                # Pullback after breakout (belum konfirmasi 2 hari)
                                tracking['state'] = 'pullback'
                                tracking['consecutive'] = 0
                            elif tracking['state'] in ['first_above_after_pullback', 'second_above_after_pullback']:
                                # Pullback again - reset to pullback state
                                tracking['state'] = 'pullback'
                                tracking['consecutive'] = 0
                            elif tracking['state'] in ['confirmed_no_pullback', 'confirmed_with_pullback']:
                                # Already confirmed but price fell back - remove tracking
                                del breakout_tracking[zone_key]

            # ===== ENTRY CONDITIONS =====
            if position is None:

                # --- BREAKOUT CHECK ---
                for zone_key, tracking in list(breakout_tracking.items()):
                    if tracking['state'] in ['confirmed_no_pullback', 'confirmed_with_pullback']:
                        res_zone = tracking['zone']
                        res_zone_low = res_zone.get('level_low', res_zone['level'] * 0.97)

                        breakout_type = 'HOLD' if tracking['state'] == 'confirmed_no_pullback' else 'PULLBACK'

                        # V8 criteria
                        vr = calculate_vr(all_data[:i+1], res_zone['level'])
                        phase = get_phase(vr)

                        if phase in valid_phases:
                            if i + 1 < len(all_data):
                                next_day = all_data[i + 1]
                                entry_price = float(next_day['open'])

                                # Find next higher resistance for target
                                higher_res = [r for r in strong_resistances if r['level'] > res_zone['level']]
                                if higher_res:
                                    target_res = min(higher_res, key=lambda x: x['level'])
                                    tp = target_res['level'] * (1 - tp_pct)
                                else:
                                    tp = entry_price * 1.15

                                sl = res_zone_low * (1 - sl_pct)  # 5% di bawah zona

                                if entry_price < tp:
                                    position = {
                                        'type': f'BREAKOUT_{breakout_type}',
                                        'signal_date': d['date'],
                                        'entry_date': next_day['date'],
                                        'entry_price': entry_price,
                                        'support': res_zone['level'],
                                        'support_quality': res_zone.get('quality', 1.0),
                                        'support_touches': res_zone.get('touches', 99),
                                        'resistance': target_res['level'] if higher_res else entry_price * 1.15,
                                        'breakout_zone': res_zone['level'],
                                        'first_breakout_date': tracking['first_date'],
                                        'stop_loss': sl,
                                        'target': tp,
                                        'phase': phase,
                                        'vr': vr
                                    }
                                    retest_tracking = {}
                                    breakout_tracking = {}
                                    break

                if position is not None:
                    continue

                # --- RETEST CHECK (V10) ---
                # LOW menyentuh zona support atas -> jalankan V8 formula
                # Entry jika RECLAIM (close > zona atas) ATAU Phase ACCUMULATION

                for res_key, retest in list(retest_tracking.items()):
                    support_zone = retest['support_target']
                    sup_zone_low = support_zone.get('level_low', support_zone['level'] * 0.97)
                    sup_zone_high = support_zone.get('level_high', support_zone['level'] * 1.03)

                    # Batas 35% di atas zona support
                    max_confirm_price = sup_zone_high * 1.35

                    # Step 1: LOW menyentuh zona support atas (pertama kali)
                    if not retest.get('touched_support', False):
                        if low <= sup_zone_high:
                            retest['touched_support'] = True
                            retest['touched_support_idx'] = i
                            retest['touched_support_date'] = d['date']

                    # Step 2: Jika sudah touched, jalankan V8 formula
                    if retest.get('touched_support', False):
                        # Cek hold - jika breakdown, invalidate
                        is_holding = price >= sup_zone_low
                        if not is_holding:
                            del retest_tracking[res_key]
                            break

                        # Cek apakah HIGH menyentuh resistance lagi
                        res_zone = retest['resistance']
                        res_zone_low_val = res_zone.get('level_low', res_zone['level'] * 0.97)
                        high_touched_res = high >= res_zone_low_val

                        in_confirm_range = price <= max_confirm_price

                        # Jika HIGH touch resistance sementara di luar range -> invalidate
                        if high_touched_res and not in_confirm_range:
                            del retest_tracking[res_key]
                            break

                        # Jika dalam range 35%, jalankan V8 formula
                        if in_confirm_range:
                            # V8 Formula: cek phase
                            vr = calculate_vr(all_data[:i+1], support_zone['level'])
                            phase = get_phase(vr)

                            # Kondisi entry: CLOSE_STRENGTH (close dekat high >70%)
                            candle_range = high - low if high > low else 1
                            close_strength = (price - low) / candle_range
                            is_close_strength = close_strength > 0.7

                            # Entry jika CLOSE_STRENGTH terpenuhi
                            if is_close_strength:
                                confirm_reason = f'CLOSE_STRENGTH_{close_strength:.0%}'

                                if i + 1 < len(all_data):
                                    next_day = all_data[i + 1]
                                    entry_price = float(next_day['open'])
                                    sl = sup_zone_low * (1 - sl_pct)
                                    tp = retest['resistance']['level'] * (1 - tp_pct)

                                    if entry_price < tp:
                                        position = {
                                            'type': f'RETEST_{confirm_reason}',
                                            'signal_date': d['date'],
                                            'entry_date': next_day['date'],
                                            'entry_price': entry_price,
                                            'support': support_zone['level'],
                                            'support_zone_low': sup_zone_low,
                                            'support_zone_high': sup_zone_high,
                                            'support_quality': support_zone.get('quality', 1.0),
                                            'support_touches': support_zone.get('touches', 99),
                                            'resistance': retest['resistance']['level'],
                                            'resistance_touched_date': retest['touched_date'],
                                            'stop_loss': sl,
                                            'target': tp,
                                            'phase': phase,
                                            'vr': vr,
                                            'confirm_reason': confirm_reason
                                        }
                                        retest_tracking = {}
                                        breakout_tracking = {}
                                        break
                        # Else: masih di luar range 35%, tunggu

        # If still in position
        if position:
            last = all_data[-1]
            pnl = (float(last['close']) - position['entry_price']) / position['entry_price'] * 100
            trades.append({
                **position,
                'exit_date': last['date'],
                'exit_price': float(last['close']),
                'exit_reason': 'OPEN',
                'pnl': pnl,
                'result': 'OPEN',
                'days_held': (last['date'] - position['entry_date']).days
            })

        # Summary
        closed = [t for t in trades if t['exit_reason'] != 'OPEN']
        wins = [t for t in closed if t['pnl'] > 0]

        return {
            'method': 'V10_RETEST_BREAKOUT',
            'stock_code': stock_code,
            'total_trades': len(trades),
            'closed_trades': len(closed),
            'open_trades': len(trades) - len(closed),
            'wins': len(wins),
            'losses': len(closed) - len(wins),
            'win_rate': len(wins) / len(closed) * 100 if closed else 0,
            'total_pnl': sum(t['pnl'] for t in closed),
            'avg_pnl': sum(t['pnl'] for t in closed) / len(closed) if closed else 0,
            'trades': trades
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'trades': []}
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("="*70)
    print("FORMULA V8: ATR-QUALITY BASED S/R ANALYZER")
    print("="*70)
    print("""
Perbedaan V7 vs V8:
- V7: Fixed zone 500 Rp, filter by activity > median
- V8: Dynamic zone by ATR(14), filter by quality >= 50%, touches >= 3

Backtest Result (2025-01-02 s/d sekarang):
- V7: Win Rate 28.6%, Total PnL -25.90%
- V8: Win Rate 55.6%, Total PnL +62.69%
""")

    for stock in ['PTRO', 'CBDK', 'BREN', 'BRPT', 'CDIA']:
        print('='*70)
        print(f'V8 ATR-QUALITY ANALYSIS: {stock}')
        print('='*70)

        result = get_strong_sr_analysis(stock)

        if result.get('error'):
            print(f'Error: {result["error"]}')
            continue

        print(f"""
Current Price : Rp {result['current_price']:,.0f}
ATR(14)       : Rp {result['atr14']:,.0f}
Tolerance     : Rp {result['tolerance']:,.0f}

=== SUPPORT ===
  Level   : Rp {result['support']:,.0f}
  Zone    : {result['support_zone']}
  Touches : {result['support_touches']}x
  Bounces : {result['support_bounces']}x
  Quality : {result['support_quality']:.1%}
  Score   : {result['support_score']:.2f}

=== RESISTANCE ===
  Level   : Rp {result['resistance']:,.0f}
  Zone    : {result['resistance_zone']}
  Touches : {result['resistance_touches']}x
  Bounces : {result['resistance_bounces']}x
  Quality : {result['resistance_quality']:.1%}
  Score   : {result['resistance_score']:.2f}

=== TRADING LEVELS ===
  Stop Loss : Rp {result['stop_loss']:,.0f} (Support - {result['formula_info']['sl_pct']:.0f}%)
  Target    : Rp {result['target']:,.0f} (Resistance - {result['formula_info']['tp_pct']:.0f}%)

=== PHASE ANALYSIS ===
  Phase : {result['phase']}
  VR    : {result['vr']:.2f}x

=== SIGNAL ===
  Action: {result['action']}
  Reason: {result['action_reason']}
""")
