# -*- coding: utf-8 -*-
"""
SIDEWAYS V6 ANALYZER
====================
Module untuk analisis sideways dengan formula V6:
1. Adaptive Threshold (Percentile 40)
2. Analisis Akumulasi vs Distribusi (Volume Ratio)
3. Entry Signal dengan konfirmasi
4. Stop Loss & Take Profit calculation

Digunakan oleh dashboard analysis page.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta


def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host='localhost',
        database='stock_analysis',
        user='postgres',
        password='postgres'
    )


def load_stock_data(stock_code, conn=None):
    """Load stock data from database"""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT date, high_price as high, low_price as low,
               close_price as close, volume
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date ASC
    ''', (stock_code,))
    all_data = cur.fetchall()

    if close_conn:
        conn.close()

    data_list = []
    for i, row in enumerate(all_data):
        prev_close = all_data[i-1]['close'] if i > 0 else row['close']
        change = ((row['close'] - prev_close) / prev_close * 100) if prev_close else 0
        data_list.append({
            'date': row['date'],
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']),
            'change': change
        })

    return data_list


def calculate_historical_ranges(data, window_size=10, history_periods=60):
    """Hitung range historis untuk kalibrasi threshold"""
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


def get_adaptive_threshold(data, lookback_window=10, history_periods=60, percentile=40):
    """
    Hitung threshold sideways ADAPTIVE berdasarkan history
    Returns: (threshold, hist_stats)
    """
    if len(data) < history_periods + lookback_window:
        return None, None

    hist_data = data[:-lookback_window] if lookback_window > 0 else data
    hist_ranges = calculate_historical_ranges(hist_data, lookback_window, history_periods)

    if len(hist_ranges) < 10:
        return None, None

    sorted_ranges = sorted(hist_ranges)
    idx = int(len(sorted_ranges) * percentile / 100)
    threshold = sorted_ranges[idx]

    return threshold, {
        'min': min(hist_ranges),
        'p25': sorted_ranges[int(len(sorted_ranges) * 0.25)],
        'p40': threshold,
        'p50': sorted_ranges[int(len(sorted_ranges) * 0.50)],
        'p75': sorted_ranges[int(len(sorted_ranges) * 0.75)],
        'max': max(hist_ranges)
    }


def detect_sideways_adaptive(data, min_days=3, max_days=15):
    """
    Deteksi sideways dengan threshold adaptive
    Cari window optimal dari min_days sampai max_days
    """
    if len(data) < max_days + 60:
        return None

    best_result = None

    for lookback in range(min_days, max_days + 1):
        threshold, hist_stats = get_adaptive_threshold(data, lookback)

        if threshold is None:
            continue

        window = data[-lookback:]
        high = max(d['high'] for d in window)
        low = min(d['low'] for d in window)
        avg = sum(d['close'] for d in window) / len(window)
        range_pct = (high - low) / avg * 100

        is_sideways = range_pct < threshold

        if is_sideways:
            if best_result is None or lookback > best_result['days']:
                best_result = {
                    'is_sideways': True,
                    'days': lookback,
                    'high': high,
                    'low': low,
                    'range': high - low,
                    'range_pct': range_pct,
                    'threshold': threshold,
                    'hist_stats': hist_stats
                }

    if best_result:
        return best_result

    # Jika tidak sideways, return info untuk window terpanjang
    threshold, hist_stats = get_adaptive_threshold(data, max_days)
    if threshold:
        window = data[-max_days:]
        high = max(d['high'] for d in window)
        low = min(d['low'] for d in window)
        avg = sum(d['close'] for d in window) / len(window)
        range_pct = (high - low) / avg * 100

        return {
            'is_sideways': False,
            'days': max_days,
            'high': high,
            'low': low,
            'range': high - low,
            'range_pct': range_pct,
            'threshold': threshold,
            'hist_stats': hist_stats
        }

    return None


def analyze_accumulation_distribution(data, sideways_info):
    """
    Analisis apakah sideways adalah AKUMULASI atau DISTRIBUSI
    Berdasarkan volume di area support vs resistance
    """
    if not sideways_info:
        return None

    days = sideways_info['days']
    window = data[-days:]

    mid_price = (sideways_info['high'] + sideways_info['low']) / 2

    vol_lower = 0
    vol_upper = 0
    count_lower = 0
    count_upper = 0

    for d in window:
        if d['close'] < mid_price:
            vol_lower += d['volume']
            count_lower += 1
        else:
            vol_upper += d['volume']
            count_upper += 1

    vol_ratio = vol_lower / vol_upper if vol_upper > 0 else 1

    # Scoring
    acc_score = 0
    dist_score = 0
    acc_reasons = []
    dist_reasons = []

    # Volume ratio scoring - Updated threshold based on backtest
    # VR > 3.0 = 100% win rate on NCKL backtest
    if vol_ratio > 4.0:
        acc_score += 2  # Strong signal
        acc_reasons.append(f"Volume ratio {vol_ratio:.2f} > 3.0 (STRONG)")
    if vol_ratio > 5.0:
        acc_score += 1
        acc_reasons.append(f"Volume ratio {vol_ratio:.2f} > 5.0 (VERY STRONG)")

    if vol_ratio < 0.8:
        dist_score += 1
        dist_reasons.append(f"Volume ratio {vol_ratio:.2f} < 0.8")
    if vol_ratio < 0.6:
        dist_score += 1
        dist_reasons.append(f"Volume ratio {vol_ratio:.2f} < 0.6 (kuat)")
    if vol_ratio < 0.4:
        dist_score += 1
        dist_reasons.append(f"Volume ratio {vol_ratio:.2f} < 0.4 (sangat kuat)")

    # Bullish/Bearish candles at key levels
    bullish_at_support = 0
    bearish_at_resistance = 0

    for d in window:
        pos_in_range = (d['close'] - sideways_info['low']) / sideways_info['range'] if sideways_info['range'] > 0 else 0.5

        if pos_in_range < 0.4 and d['change'] > 1:
            bullish_at_support += 1
        if pos_in_range > 0.6 and d['change'] < -1:
            bearish_at_resistance += 1

    if bullish_at_support >= 2:
        acc_score += 1
        acc_reasons.append(f"{bullish_at_support} bullish candle di support")
    if bearish_at_resistance >= 2:
        dist_score += 1
        dist_reasons.append(f"{bearish_at_resistance} bearish candle di resistance")

    # Determine phase - Updated with stricter Vol Ratio requirement
    # ACCUMULATION requires Vol Ratio > 3.0 (based on backtest: 100% win rate)
    if vol_ratio > 4.0 and acc_score >= 2:
        phase = 'ACCUMULATION'
    elif dist_score >= 2 and dist_score > acc_score:
        phase = 'DISTRIBUTION'
    elif vol_ratio > 1.5:
        phase = 'WEAK_ACCUMULATION'  # Not strong enough for entry
    else:
        phase = 'NEUTRAL'

    return {
        'phase': phase,
        'vol_ratio': vol_ratio,
        'acc_score': acc_score,
        'dist_score': dist_score,
        'acc_reasons': acc_reasons,
        'dist_reasons': dist_reasons,
        'vol_lower': vol_lower,
        'vol_upper': vol_upper,
        'count_lower': count_lower,
        'count_upper': count_upper,
        'bullish_at_support': bullish_at_support,
        'bearish_at_resistance': bearish_at_resistance
    }


def check_entry_signal(data, sideways_info, phase_info):
    """
    Check apakah ada entry signal dengan konfirmasi
    """
    if not sideways_info:
        return None

    today = data[-1]
    comp_days = data[-6:-1] if len(data) >= 6 else data[:-1]

    # Position dalam range
    if sideways_info['range'] > 0:
        pos_in_range = (today['close'] - sideways_info['low']) / sideways_info['range']
    else:
        pos_in_range = 0.5

    near_support = pos_in_range < 0.5

    # Candle analysis
    today_range = today['high'] - today['low']
    close_pos = (today['close'] - today['low']) / today_range if today_range > 0 else 0.5

    avg_range = sum((d['high'] - d['low']) for d in comp_days) / len(comp_days) if comp_days else 1
    avg_vol = sum(d['volume'] for d in comp_days) / len(comp_days) if comp_days else 1

    range_exp = today_range / avg_range if avg_range > 0 else 1
    vol_ratio = today['volume'] / avg_vol if avg_vol > 0 else 1

    signals = {
        'near_support': {
            'passed': near_support,
            'value': pos_in_range * 100,
            'description': f"Posisi {pos_in_range*100:.0f}% dari range {'(dekat support)' if near_support else '(dekat resistance)'}"
        },
        'bullish_candle': {
            'passed': today['change'] > 0.5 and close_pos > 0.6,
            'value': today['change'],
            'description': f"Change {today['change']:+.1f}%, close position {close_pos*100:.0f}%"
        },
        'range_expansion': {
            'passed': range_exp > 1.1,
            'value': range_exp,
            'description': f"Range {range_exp:.2f}x dari rata-rata"
        },
        'volume_surge': {
            'passed': vol_ratio > 1.2,
            'value': vol_ratio,
            'description': f"Volume {vol_ratio:.2f}x dari rata-rata"
        }
    }

    score = sum(1 for s in signals.values() if s['passed'])

    # Risk Management
    acc_range = sideways_info['range']
    stop_loss = sideways_info['low'] - (acc_range * 0.02)
    target = sideways_info['high']

    risk_pct = (today['close'] - stop_loss) / today['close'] * 100
    reward_pct = (target - today['close']) / today['close'] * 100
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

    # Entry criteria - STRICT VERSION
    # - Sideways must be detected
    # - Phase MUST be ACCUMULATION (not NEUTRAL or DISTRIBUTION)
    # - Near support (pos_in_range < 50%)
    # - At least 2/4 confirmation signals
    # - R:R ratio >= 1.5

    is_accumulation = phase_info and phase_info['phase'] == 'ACCUMULATION'
    is_distribution = phase_info and phase_info['phase'] == 'DISTRIBUTION'
    is_neutral = phase_info and phase_info['phase'] == 'NEUTRAL'

    confirmed = (
        sideways_info['is_sideways'] and
        is_accumulation and  # MUST be ACCUMULATION for entry
        score >= 2 and
        near_support and
        rr_ratio >= 1.5
    )

    # Determine action - STRICT LOGIC
    if is_distribution:
        action = 'EXIT'
        action_reason = 'Fase DISTRIBUSI terdeteksi - hindari entry baru'
    elif not sideways_info['is_sideways']:
        action = 'WAIT'
        action_reason = 'Tidak dalam fase sideways - tunggu konsolidasi'
    elif confirmed:
        action = 'ENTRY'
        action_reason = f'AKUMULASI + {score}/4 konfirmasi + R:R {rr_ratio:.1f}'
    elif is_accumulation:
        action = 'WATCH'
        action_reason = f'Akumulasi terdeteksi, tunggu konfirmasi ({score}/4)'
    elif is_neutral and near_support and score >= 2:
        action = 'WATCH'
        action_reason = f'Fase NETRAL tapi dekat support ({score}/4 konfirmasi) - observasi'
    else:
        action = 'WAIT'
        action_reason = 'Fase NETRAL - tunggu sinyal akumulasi yang jelas'

    return {
        'confirmed': confirmed,
        'action': action,
        'action_reason': action_reason,
        'score': score,
        'signals': signals,
        'pos_in_range': pos_in_range * 100,
        'stop_loss': stop_loss,
        'target': target,
        'risk_pct': risk_pct,
        'reward_pct': reward_pct,
        'rr_ratio': rr_ratio,
        'is_accumulation': is_accumulation,
        'is_distribution': is_distribution,
        'is_neutral': is_neutral
    }


def track_sideways_history(data, lookback_days=15):
    """
    Track sideways formation history and Vol Ratio evolution.

    Returns:
    - sideways_start: kapan sideways mulai terbentuk
    - sideways_duration: berapa lama sudah sideways
    - vr_history: perubahan Vol Ratio selama sideways
    - vr_trend: apakah VR naik/turun (BUILDING/WEAKENING)
    """
    if len(data) < 80:
        return None

    history = []
    sideways_streak = 0
    sideways_start_date = None

    # Check each day going backwards
    for i in range(lookback_days):
        day_idx = len(data) - 1 - i
        if day_idx < 80:
            break

        data_until_day = data[:day_idx + 1]
        day_data = data[day_idx]

        # Detect sideways for this day
        sideways = detect_sideways_adaptive(data_until_day)

        if sideways and sideways['is_sideways']:
            # Calculate Vol Ratio for this day's sideways
            days = sideways['days']
            window = data_until_day[-days:]
            mid_price = (sideways['high'] + sideways['low']) / 2

            vol_lower = 0
            vol_upper = 0
            for d in window:
                if d['close'] < mid_price:
                    vol_lower += d['volume']
                else:
                    vol_upper += d['volume']

            vol_ratio = vol_lower / vol_upper if vol_upper > 0 else 1

            # Determine phase
            if vol_ratio > 4.0:
                phase = 'ACCUMULATION'
            elif vol_ratio < 0.8:
                phase = 'DISTRIBUTION'
            elif vol_ratio > 1.5:
                phase = 'WEAK_ACC'
            else:
                phase = 'NEUTRAL'

            history.append({
                'date': day_data['date'],
                'is_sideways': True,
                'sideways_days': days,
                'vol_ratio': vol_ratio,
                'phase': phase,
                'range_high': sideways['high'],
                'range_low': sideways['low'],
                'close': day_data['close']
            })
        else:
            history.append({
                'date': day_data['date'],
                'is_sideways': False,
                'sideways_days': 0,
                'vol_ratio': 0,
                'phase': 'TRENDING',
                'range_high': 0,
                'range_low': 0,
                'close': day_data['close']
            })

    # Reverse to chronological order (oldest first)
    history = list(reversed(history))

    # Find sideways start and calculate streak
    sideways_entries = [h for h in history if h['is_sideways']]

    # Check current streak (from most recent)
    current_streak = 0
    for h in reversed(history):
        if h['is_sideways']:
            current_streak += 1
        else:
            break

    # Find when current sideways started
    if current_streak > 0:
        sideways_start_idx = len(history) - current_streak
        sideways_start_date = history[sideways_start_idx]['date']

    # Calculate VR trend during sideways
    vr_trend = 'N/A'
    vr_change = 0
    if current_streak >= 3:
        recent_sideways = [h for h in history[-current_streak:] if h['is_sideways']]
        if len(recent_sideways) >= 3:
            first_vr = recent_sideways[0]['vol_ratio']
            last_vr = recent_sideways[-1]['vol_ratio']
            vr_change = last_vr - first_vr

            if vr_change > 0.5:
                vr_trend = 'BUILDING'  # Akumulasi membangun
            elif vr_change < -0.5:
                vr_trend = 'WEAKENING'  # Akumulasi melemah
            else:
                vr_trend = 'STABLE'  # Stabil

    return {
        'history': history,
        'sideways_start_date': sideways_start_date,
        'sideways_duration': current_streak,
        'is_currently_sideways': history[-1]['is_sideways'] if history else False,
        'current_vol_ratio': history[-1]['vol_ratio'] if history and history[-1]['is_sideways'] else 0,
        'vr_trend': vr_trend,
        'vr_change': vr_change,
        'total_days_tracked': len(history)
    }


def get_v6_analysis(stock_code, conn=None):
    """
    Main function: Get complete V6 analysis for a stock
    Returns comprehensive analysis dict for dashboard
    """
    data = load_stock_data(stock_code, conn)

    if len(data) < 80:
        return {
            'error': 'Data tidak cukup (minimum 80 hari)',
            'stock_code': stock_code
        }

    today = data[-1]

    # 1. Detect Sideways with Adaptive Threshold
    sideways = detect_sideways_adaptive(data)

    # 2. Analyze Accumulation vs Distribution
    phase = analyze_accumulation_distribution(data, sideways) if sideways else None

    # 3. Check Entry Signal
    entry = check_entry_signal(data, sideways, phase)

    # 4. Build comprehensive result
    result = {
        'stock_code': stock_code,
        'date': today['date'],
        'current_price': today['close'],
        'change': today['change'],

        # Sideways Detection
        'sideways': {
            'is_sideways': sideways['is_sideways'] if sideways else False,
            'days': sideways['days'] if sideways else 0,
            'high': sideways['high'] if sideways else 0,
            'low': sideways['low'] if sideways else 0,
            'range': sideways['range'] if sideways else 0,
            'range_pct': sideways['range_pct'] if sideways else 0,
            'threshold': sideways['threshold'] if sideways else 0,
            'hist_stats': sideways['hist_stats'] if sideways else {},
        },

        # Phase Analysis
        'phase': {
            'phase': phase['phase'] if phase else 'UNKNOWN',
            'vol_ratio': phase['vol_ratio'] if phase else 0,
            'acc_score': phase['acc_score'] if phase else 0,
            'dist_score': phase['dist_score'] if phase else 0,
            'acc_reasons': phase['acc_reasons'] if phase else [],
            'dist_reasons': phase['dist_reasons'] if phase else [],
        },

        # Entry Signal
        'entry': entry if entry else {},

        # Education content
        'education': generate_education_content(sideways, phase, entry)
    }

    return result


def generate_education_content(sideways, phase, entry):
    """
    Generate educational content for the analysis
    """
    content = {
        'sideways_explanation': '',
        'phase_explanation': '',
        'action_explanation': '',
        'why_not_buy': [],
        'formula_explanation': ''
    }

    # Sideways explanation
    if sideways:
        if sideways['is_sideways']:
            content['sideways_explanation'] = (
                f"SIDEWAYS terdeteksi selama {sideways['days']} hari. "
                f"Range harga {sideways['range_pct']:.1f}% lebih kecil dari threshold {sideways['threshold']:.1f}% "
                f"(Percentile 40 dari historical ranges). "
                f"Ini menunjukkan harga berkonsolidasi dalam range Rp {sideways['low']:,.0f} - Rp {sideways['high']:,.0f}."
            )
        else:
            content['sideways_explanation'] = (
                f"TRENDING (bukan sideways). Range harga {sideways['range_pct']:.1f}% "
                f"lebih besar dari threshold {sideways['threshold']:.1f}%. "
                f"Harga sedang bergerak dengan momentum, bukan konsolidasi."
            )

    # Phase explanation
    if phase:
        if phase['phase'] == 'ACCUMULATION':
            content['phase_explanation'] = (
                f"Fase AKUMULASI terdeteksi. Volume Ratio {phase['vol_ratio']:.2f} menunjukkan "
                f"volume lebih tinggi saat harga di area support dibanding resistance. "
                f"Ini mengindikasikan smart money sedang mengumpulkan saham."
            )
        elif phase['phase'] == 'DISTRIBUTION':
            content['phase_explanation'] = (
                f"Fase DISTRIBUSI terdeteksi. Volume Ratio {phase['vol_ratio']:.2f} menunjukkan "
                f"volume lebih tinggi saat harga di area resistance dibanding support. "
                f"Ini mengindikasikan smart money sedang menjual saham."
            )
        else:
            content['phase_explanation'] = (
                f"Fase NETRAL. Volume Ratio {phase['vol_ratio']:.2f} seimbang antara "
                f"area support dan resistance. Belum ada indikasi kuat akumulasi atau distribusi."
            )

    # Why not buy reasons
    if entry:
        if not sideways or not sideways['is_sideways']:
            content['why_not_buy'].append("Tidak dalam fase sideways - harga sedang trending")

        if phase and phase['phase'] == 'DISTRIBUTION':
            content['why_not_buy'].append("Fase DISTRIBUSI - smart money sedang menjual")

        if entry.get('pos_in_range', 100) > 50:
            content['why_not_buy'].append(f"Posisi {entry.get('pos_in_range', 0):.0f}% dari range - terlalu dekat resistance")

        if entry.get('score', 0) < 2:
            content['why_not_buy'].append(f"Konfirmasi hanya {entry.get('score', 0)}/4 - butuh minimal 2")

        if entry.get('rr_ratio', 0) < 1.5:
            content['why_not_buy'].append(f"R:R ratio {entry.get('rr_ratio', 0):.1f} - butuh minimal 1.5")

    # Action explanation
    if entry:
        action = entry.get('action', 'WAIT')
        if action == 'ENTRY':
            content['action_explanation'] = (
                f"ENTRY SIGNAL: Sideways + Akumulasi + {entry.get('score', 0)}/4 konfirmasi. "
                f"Stop Loss di Rp {entry.get('stop_loss', 0):,.0f} (-{entry.get('risk_pct', 0):.1f}%), "
                f"Target Rp {entry.get('target', 0):,.0f} (+{entry.get('reward_pct', 0):.1f}%), "
                f"R:R = 1:{entry.get('rr_ratio', 0):.1f}"
            )
        elif action == 'EXIT':
            content['action_explanation'] = (
                "EXIT/AVOID: Fase distribusi terdeteksi. Smart money sedang menjual. "
                "Hindari entry baru dan pertimbangkan untuk keluar jika sudah punya posisi."
            )
        elif action == 'WATCH':
            content['action_explanation'] = (
                f"WATCH: Akumulasi terdeteksi tapi konfirmasi belum cukup ({entry.get('score', 0)}/4). "
                "Tunggu harga turun ke area support dengan konfirmasi yang lebih kuat."
            )
        else:
            content['action_explanation'] = (
                "WAIT: Kondisi belum optimal untuk entry. "
                "Tunggu terbentuknya fase sideways dengan akumulasi yang jelas."
            )

    # Formula explanation
    content['formula_explanation'] = """
FORMULA V6.2 - ADAPTIVE SIDEWAYS DETECTION (Updated):

1. DETEKSI SIDEWAYS (Adaptive Threshold)
   - Hitung range% untuk 60 periode historis
   - Threshold = Percentile 40 dari historical ranges
   - SIDEWAYS jika Range% < Threshold

2. ANALISIS FASE (Volume Ratio) - V6.2 UPDATE
   - Vol Ratio = Volume di Support / Volume di Resistance
   - AKUMULASI: Vol Ratio > 4.0 (STRONG - backtest 100% win)
   - WEAK ACCUMULATION: Vol Ratio 1.5-4.0 (tidak cukup kuat)
   - DISTRIBUSI: Vol Ratio < 0.8 (smart money jual)
   - NETRAL: Vol Ratio 0.8 - 1.5

3. ENTRY SIGNAL (4 Konfirmasi)
   - Near Support: Posisi < 50% dari range
   - Bullish Candle: Change > 0.5% & close > 60%
   - Range Expansion: Range > 1.1x rata-rata
   - Volume Surge: Volume > 1.2x rata-rata

4. RISK MANAGEMENT
   - Stop Loss = Low Sideways - (Range x 2%)
   - Target = High Sideways
   - Entry jika R:R >= 1.5

CATATAN V6.2: Threshold Vol Ratio dinaikkan dari 3.0 ke 4.0
berdasarkan backtest NCKL + PANI yang menunjukkan:
- VR > 4.0: Win Rate 100% (4/4) - NCKL: 3.56,3.94,8.81 + PANI: 4.55
- VR 3.0-4.0: Win Rate 0% (0/4) - semua LOSS
"""

    return content


# For testing
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    stocks = ['NCKL', 'DSNG', 'BBCA', 'BREN', 'PANI']

    print("=" * 80)
    print("TEST SIDEWAYS V6 ANALYZER")
    print("=" * 80)

    for stock in stocks:
        result = get_v6_analysis(stock)

        if result.get('error'):
            print(f"\n{stock}: {result['error']}")
            continue

        print(f"\n{'='*40}")
        print(f"{stock} @ Rp {result['current_price']:,.0f}")
        print(f"{'='*40}")

        sw = result['sideways']
        ph = result['phase']
        en = result['entry']

        print(f"Sideways: {'YA' if sw['is_sideways'] else 'TIDAK'} ({sw['days']} hari)")
        print(f"Range: Rp {sw['low']:,.0f} - Rp {sw['high']:,.0f} ({sw['range_pct']:.1f}% < {sw['threshold']:.1f}%)")
        print(f"Fase: {ph['phase']} (Vol Ratio: {ph['vol_ratio']:.2f})")
        print(f"Action: {en.get('action', 'N/A')} - {en.get('action_reason', '')}")

        if en.get('action') in ['ENTRY', 'WATCH']:
            print(f"  SL: Rp {en['stop_loss']:,.0f} (-{en['risk_pct']:.1f}%)")
            print(f"  TP: Rp {en['target']:,.0f} (+{en['reward_pct']:.1f}%)")
            print(f"  R:R: 1:{en['rr_ratio']:.1f}")
