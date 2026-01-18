# -*- coding: utf-8 -*-
"""
Analisis Volume & Akumulasi pada Trade V10
Membandingkan kondisi entry antara trade yang TP vs yang Loss
"""

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from zones_config import STOCK_ZONES, DEFAULT_PARAMS
from collections import defaultdict
import statistics


def get_db_connection():
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


def calculate_volume_metrics(data, idx, lookback=20):
    """Hitung volume ratio vs rata-rata"""
    if idx < lookback:
        return None, None

    current_vol = float(data[idx]['volume'])
    avg_vol = sum(float(data[i]['volume']) for i in range(idx-lookback, idx)) / lookback

    if avg_vol == 0:
        return None, None

    vol_ratio = current_vol / avg_vol
    return vol_ratio, avg_vol


def calculate_accumulation_vr(data, idx, zone_low, zone_high, lookback=30):
    """
    Hitung Volume Ratio (VR) di sekitar zona support
    VR > 1 = lebih banyak volume di bawah zona (akumulasi)
    VR < 1 = lebih banyak volume di atas zona (distribusi)
    """
    if idx < lookback:
        return None, 'UNKNOWN'

    vol_below = 0  # Volume saat harga di bawah/dalam zona
    vol_above = 0  # Volume saat harga di atas zona

    for i in range(idx - lookback, idx + 1):
        d = data[i]
        close = float(d['close'])
        vol = float(d['volume'])

        if close <= zone_high:
            vol_below += vol
        else:
            vol_above += vol

    if vol_above == 0:
        vr = 999.0 if vol_below > 0 else 1.0
    else:
        vr = vol_below / vol_above

    # Tentukan fase
    if vr >= 2.0:
        phase = 'STRONG_ACC'
    elif vr >= 1.5:
        phase = 'ACCUMULATION'
    elif vr >= 1.0:
        phase = 'WEAK_ACC'
    elif vr >= 0.7:
        phase = 'NEUTRAL'
    elif vr >= 0.5:
        phase = 'DISTRIBUTION'
    else:
        phase = 'STRONG_DIST'

    return vr, phase


def calculate_price_momentum(data, idx, lookback=5):
    """Hitung momentum harga (% change dalam N hari)"""
    if idx < lookback:
        return None

    current = float(data[idx]['close'])
    past = float(data[idx - lookback]['close'])

    return (current - past) / past * 100


def calculate_rsi(data, idx, period=14):
    """Hitung RSI"""
    if idx < period:
        return None

    gains = []
    losses = []

    for i in range(idx - period + 1, idx + 1):
        change = float(data[i]['close']) - float(data[i-1]['close'])
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ============================================================
# Import V10 Backtest Logic
# ============================================================
STATE_IDLE = 0
STATE_RETEST_PENDING = 1
STATE_BREAKOUT_GATE = 2
STATE_BREAKOUT_ARMED = 3


def calculate_true_range(data):
    tr_list = []
    for i, d in enumerate(data):
        high = float(d['high'])
        low = float(d['low'])
        if i == 0:
            tr = high - low
        else:
            prev_close = float(data[i-1]['close'])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return tr_list


def calculate_atr(tr_list, period=14):
    atr_list = []
    for i in range(len(tr_list)):
        if i < period - 1:
            atr_list.append(None)
        else:
            atr = sum(tr_list[i-period+1:i+1]) / period
            atr_list.append(atr)
    return atr_list


def get_buffer(data, idx, atr_list, params):
    if params['buffer_method'] == 'ATR':
        atr = atr_list[idx] if atr_list[idx] is not None else 10
        return atr * params['atr_mult']
    else:
        return float(data[idx]['close']) * params['pct_buffer']


class ZoneHelper:
    def __init__(self, zones):
        self.zones = zones

    def get_active_support(self, close):
        for znum in sorted(self.zones.keys()):
            if self.zones[znum]['low'] <= close <= self.zones[znum]['high']:
                return self.zones[znum]['low'], self.zones[znum]['high'], znum

        best_zone = None
        best_dist = float('inf')
        for znum in sorted(self.zones.keys()):
            if close > self.zones[znum]['high']:
                dist = close - self.zones[znum]['high']
                if dist < best_dist:
                    best_dist = dist
                    best_zone = (self.zones[znum]['low'], self.zones[znum]['high'], znum)

        if best_zone:
            return best_zone
        return None, None, 0

    def get_active_resistance(self, close):
        for znum in sorted(self.zones.keys()):
            if self.zones[znum]['low'] <= close <= self.zones[znum]['high']:
                return self.zones[znum]['low'], self.zones[znum]['high'], znum

        best_zone = None
        best_dist = float('inf')
        for znum in sorted(self.zones.keys()):
            if close < self.zones[znum]['low']:
                dist = self.zones[znum]['low'] - close
                if dist < best_dist:
                    best_dist = dist
                    best_zone = (self.zones[znum]['low'], self.zones[znum]['high'], znum)

        if best_zone:
            return best_zone
        return None, None, 0

    def get_next_resistance_zone(self, price):
        best_zone = None
        best_dist = float('inf')

        for znum in sorted(self.zones.keys()):
            if price < self.zones[znum]['low']:
                dist = self.zones[znum]['low'] - price
                if dist < best_dist:
                    best_dist = dist
                    best_zone = self.zones[znum]

        return best_zone

    def get_tp_for_zone(self, zone_num, price, params):
        tp_buffer_pct = params.get('tp_buffer_pct', 0.02)
        next_r_zone = self.get_next_resistance_zone(price)
        if next_r_zone is not None:
            tp = next_r_zone['low'] * (1 - tp_buffer_pct)
        else:
            tp = price * 1.20
        return tp

    def detect_breakout_zone(self, prev_close, close):
        for znum in sorted(self.zones.keys()):
            z_high = self.zones[znum]['high']
            z_low = self.zones[znum]['low']
            if prev_close <= z_low and close > z_high:
                return z_low, z_high, znum
        return None, None, 0


def support_touch(low, s_high):
    return low <= s_high

def support_hold(close, s_low):
    return close >= s_low

def support_from_above(prev_close, s_high):
    return prev_close > s_high

def support_not_late(close, s_high, tp, params):
    not_late_pct = params.get('not_late_pct', 0.35)
    distance_to_tp = tp - s_high
    max_close = s_high + (not_late_pct * distance_to_tp)
    return close <= max_close

def resistance_inside(close, r_low, r_high, buffer):
    return close >= r_low - buffer and close <= r_high + buffer


def calculate_sl_tp(zh, entry_type, zone_low, zone_high, zone_num, entry_price, params):
    sl_pct = params['sl_pct']
    tp_buffer_pct = params.get('tp_buffer_pct', 0.02)

    if entry_type == 'RETEST':
        sl = zone_low * (1 - sl_pct)
    elif entry_type == 'BO_HOLD':
        sl = zone_high * (1 - sl_pct)
    elif entry_type == 'BO_PULLBACK':
        sl = zone_low * (1 - sl_pct)
    else:
        sl = zone_low * (1 - sl_pct)

    next_r_zone = zh.get_next_resistance_zone(entry_price)
    if next_r_zone is not None:
        tp = next_r_zone['low'] * (1 - tp_buffer_pct)
    else:
        tp = entry_price + 2 * (entry_price - sl)

    return sl, tp


def run_backtest_with_analysis(stock_code, all_data, params=None, start_date='2024-01-01'):
    """Run V10 backtest with volume/accumulation analysis at entry"""
    if params is None:
        params = DEFAULT_PARAMS.copy()

    zones = STOCK_ZONES.get(stock_code.upper())
    if not zones:
        return None

    zh = ZoneHelper(zones)

    if not all_data or len(all_data) < 30:
        return None

    tr_list = calculate_true_range(all_data)
    atr_list = calculate_atr(tr_list, params['atr_len'])

    # State tracking
    state = STATE_IDLE
    breakout_locked = False
    breakout_count = 0
    breakout_start_idx = 0
    breakout_gate_passed = False
    pulled_back = False
    pullback_rebreak = False
    post_gate_confirm_count = 0

    retest_touch_idx = 0
    prior_resistance_touched = False
    prior_resistance_zone = 0

    locked_zone_low = None
    locked_zone_high = None
    locked_zone_num = 0

    position = None
    pending_entry_type = None
    pending_entry_zone_low = None
    pending_entry_zone_high = None
    pending_entry_zone_num = 0
    pending_entry_idx = 0

    trades = []

    start_idx = params['atr_len'] + 1
    for i, d in enumerate(all_data):
        if str(d['date']) >= start_date and i >= start_idx:
            start_idx = i
            break

    # Initialize prior_resistance_touched from historical data
    for i in range(start_idx):
        close = float(all_data[i]['close'])
        high = float(all_data[i]['high'])
        r_low, r_high, r_zone_num = zh.get_active_resistance(close)
        if r_high is not None:
            approx_buffer = close * 0.01
            if high >= r_low - approx_buffer:
                prior_resistance_touched = True
                prior_resistance_zone = r_zone_num

    for i in range(start_idx, len(all_data)):
        d = all_data[i]
        date_str = str(d['date'])[:10]

        close = float(d['close'])
        low = float(d['low'])
        high = float(d['high'])
        open_price = float(d['open'])
        prev_close = float(all_data[i-1]['close']) if i > 0 else close

        buffer = get_buffer(all_data, i, atr_list, params)

        s_low, s_high, s_zone_num = zh.get_active_support(close)
        r_low, r_high, r_zone_num = zh.get_active_resistance(close)

        frozen = breakout_locked and breakout_count < 3

        # Track resistance touch
        if r_high is not None and not breakout_locked:
            r_touch = high >= r_low - buffer
            if r_touch:
                prior_resistance_touched = True
                prior_resistance_zone = r_zone_num

        # Pending entry execution
        if pending_entry_type and position is None:
            entry_price = open_price
            sl, tp = calculate_sl_tp(zh, pending_entry_type, pending_entry_zone_low,
                                      pending_entry_zone_high, pending_entry_zone_num,
                                      entry_price, params)
            if tp > entry_price:
                # Calculate metrics at entry
                vol_ratio, avg_vol = calculate_volume_metrics(all_data, pending_entry_idx)
                vr, acc_phase = calculate_accumulation_vr(all_data, pending_entry_idx,
                                                          pending_entry_zone_low,
                                                          pending_entry_zone_high)
                momentum = calculate_price_momentum(all_data, pending_entry_idx)
                rsi = calculate_rsi(all_data, pending_entry_idx)

                position = {
                    'type': pending_entry_type,
                    'entry_date': date_str,
                    'entry_price': entry_price,
                    'entry_idx': i,
                    'zone_num': pending_entry_zone_num,
                    'zone_low': pending_entry_zone_low,
                    'zone_high': pending_entry_zone_high,
                    'sl': sl,
                    'tp': tp,
                    # Entry analysis metrics
                    'vol_ratio': vol_ratio,
                    'avg_vol': avg_vol,
                    'vr': vr,
                    'acc_phase': acc_phase,
                    'momentum': momentum,
                    'rsi': rsi,
                }

            pending_entry_type = None
            pending_entry_zone_low = None
            pending_entry_zone_high = None
            pending_entry_zone_num = 0
            pending_entry_idx = 0

        # Position management
        if position:
            exit_reason = None
            exit_price = None

            if low <= position['sl']:
                exit_reason = 'SL Hit'
                exit_price = position['sl']
            elif high >= position['tp']:
                exit_reason = 'TP Hit'
                exit_price = position['tp']
            elif (i - position['entry_idx']) >= params['max_hold_bars']:
                exit_reason = 'Max Hold'
                exit_price = close

            if exit_reason:
                pnl = (exit_price - position['entry_price']) / position['entry_price'] * 100
                trades.append({
                    **position,
                    'exit_date': date_str,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl': pnl,
                })
                position = None
                continue

        # Breakout detection
        bo_zone_low, bo_zone_high, bo_zone_num = zh.detect_breakout_zone(prev_close, close)
        if bo_zone_num > 0:
            is_different_zone = (locked_zone_num != bo_zone_num)
            if not breakout_locked or (is_different_zone and state in [STATE_BREAKOUT_ARMED, STATE_BREAKOUT_GATE]):
                if state == STATE_RETEST_PENDING:
                    retest_touch_idx = 0

                breakout_locked = True
                breakout_start_idx = i
                breakout_count = 1
                breakout_gate_passed = False
                pulled_back = False
                pullback_rebreak = False
                post_gate_confirm_count = 0
                locked_zone_low = bo_zone_low
                locked_zone_high = bo_zone_high
                locked_zone_num = bo_zone_num
                state = STATE_BREAKOUT_GATE

        # Breakout gate
        if breakout_locked and state == STATE_BREAKOUT_GATE and breakout_count < 3:
            days_since_start = i - breakout_start_idx
            if days_since_start > 0:
                if close >= locked_zone_high:
                    breakout_count += 1
                    if breakout_count >= 3:
                        breakout_gate_passed = True
                        state = STATE_BREAKOUT_ARMED
                elif close >= locked_zone_low and close < locked_zone_high:
                    breakout_count = 0
                    breakout_start_idx = i
                else:
                    breakout_locked = False
                    breakout_count = 0
                    breakout_gate_passed = False
                    state = STATE_IDLE

        # Breakout entry
        if breakout_gate_passed and state == STATE_BREAKOUT_ARMED:
            locked_r_break = close > locked_zone_high
            locked_r_inside = resistance_inside(close, locked_zone_low, locked_zone_high, buffer)

            if locked_r_inside and not pulled_back:
                pulled_back = True
                pullback_rebreak = False
                post_gate_confirm_count = 0

            if locked_r_break:
                can_enter = False
                if pulled_back:
                    if not pullback_rebreak:
                        pullback_rebreak = True
                        post_gate_confirm_count = 1
                    else:
                        post_gate_confirm_count += 1
                        if post_gate_confirm_count >= 2:
                            can_enter = True
                else:
                    post_gate_confirm_count += 1
                    if post_gate_confirm_count >= params['confirm_closes_breakout']:
                        can_enter = True

                if can_enter and position is None:
                    if pulled_back:
                        pending_entry_type = 'BO_PULLBACK'
                    else:
                        pending_entry_type = 'BO_HOLD'
                    pending_entry_zone_low = locked_zone_low
                    pending_entry_zone_high = locked_zone_high
                    pending_entry_zone_num = locked_zone_num
                    pending_entry_idx = i

                    prior_resistance_touched = False
                    prior_resistance_zone = 0
                    breakout_locked = False
                    breakout_count = 0
                    breakout_gate_passed = False
                    pulled_back = False
                    pullback_rebreak = False
                    post_gate_confirm_count = 0
                    locked_zone_low = None
                    locked_zone_high = None
                    locked_zone_num = 0
                    state = STATE_IDLE
            else:
                if not locked_r_inside:
                    post_gate_confirm_count = 0

        # Retest
        if not frozen and position is None:
            if state == STATE_IDLE and s_low is not None:
                tp_for_check = zh.get_tp_for_zone(s_zone_num, s_high, params)
                s_touch = support_touch(low, s_high)
                s_hold = support_hold(close, s_low)
                s_from_above = support_from_above(prev_close, s_high)
                s_not_late = support_not_late(close, s_high, tp_for_check, params)

                if s_touch and s_hold and s_not_late and s_from_above and prior_resistance_touched:
                    state = STATE_RETEST_PENDING
                    retest_touch_idx = i
                    locked_zone_low = s_low
                    locked_zone_high = s_high
                    locked_zone_num = s_zone_num

            if state == STATE_RETEST_PENDING:
                bars_from_touch = i - retest_touch_idx
                if close < locked_zone_low:
                    state = STATE_IDLE
                    retest_touch_idx = 0
                elif bars_from_touch <= params['confirm_bars_retest']:
                    any_reclaim = close >= locked_zone_high + buffer
                    if any_reclaim:
                        pending_entry_type = 'RETEST'
                        pending_entry_zone_low = locked_zone_low
                        pending_entry_zone_high = locked_zone_high
                        pending_entry_zone_num = locked_zone_num
                        pending_entry_idx = i
                        prior_resistance_touched = False
                        state = STATE_IDLE
                        retest_touch_idx = 0
                elif bars_from_touch > params['confirm_bars_retest']:
                    state = STATE_IDLE
                    retest_touch_idx = 0

    # Close open position
    if position:
        last = all_data[-1]
        pnl = (float(last['close']) - position['entry_price']) / position['entry_price'] * 100
        trades.append({
            **position,
            'exit_date': str(last['date'])[:10],
            'exit_price': float(last['close']),
            'exit_reason': 'OPEN',
            'pnl': pnl,
        })

    return trades


def analyze_trades():
    """Analyze all V10 trades comparing TP vs Loss"""
    conn = get_db_connection()

    all_trades = []

    print("=" * 100)
    print("ANALISIS VOLUME & AKUMULASI - FORMULA V10")
    print("Membandingkan kondisi entry antara trade TP vs Loss")
    print("=" * 100)

    for stock_code in sorted(STOCK_ZONES.keys()):
        try:
            data = get_stock_data(stock_code, conn)
            trades = run_backtest_with_analysis(stock_code, data)
            if trades:
                for t in trades:
                    t['stock_code'] = stock_code
                all_trades.extend(trades)
        except Exception as e:
            print(f"Error {stock_code}: {e}")

    conn.close()

    # Separate TP and Loss trades
    tp_trades = [t for t in all_trades if t['exit_reason'] == 'TP Hit']
    sl_trades = [t for t in all_trades if t['exit_reason'] == 'SL Hit']
    max_hold_trades = [t for t in all_trades if t['exit_reason'] == 'Max Hold']

    print(f"\nTotal Trades: {len(all_trades)}")
    print(f"  - TP Hit  : {len(tp_trades)}")
    print(f"  - SL Hit  : {len(sl_trades)}")
    print(f"  - Max Hold: {len(max_hold_trades)}")
    print(f"  - Open    : {len([t for t in all_trades if t['exit_reason'] == 'OPEN'])}")

    # ============================================================
    # VOLUME RATIO ANALYSIS
    # ============================================================
    print("\n" + "=" * 100)
    print("1. VOLUME RATIO (vs 20-day average)")
    print("=" * 100)

    tp_vol = [t['vol_ratio'] for t in tp_trades if t.get('vol_ratio')]
    sl_vol = [t['vol_ratio'] for t in sl_trades if t.get('vol_ratio')]

    if tp_vol and sl_vol:
        print(f"\n{'Metric':<20} {'TP Trades':>15} {'SL Trades':>15} {'Difference':>15}")
        print("-" * 70)
        print(f"{'Count':<20} {len(tp_vol):>15} {len(sl_vol):>15}")
        print(f"{'Mean Vol Ratio':<20} {statistics.mean(tp_vol):>15.2f}x {statistics.mean(sl_vol):>15.2f}x {statistics.mean(tp_vol) - statistics.mean(sl_vol):>+15.2f}x")
        print(f"{'Median Vol Ratio':<20} {statistics.median(tp_vol):>15.2f}x {statistics.median(sl_vol):>15.2f}x {statistics.median(tp_vol) - statistics.median(sl_vol):>+15.2f}x")
        print(f"{'Min':<20} {min(tp_vol):>15.2f}x {min(sl_vol):>15.2f}x")
        print(f"{'Max':<20} {max(tp_vol):>15.2f}x {max(sl_vol):>15.2f}x")

        # Volume threshold analysis
        print("\n  Volume Ratio Threshold Analysis:")
        for threshold in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0]:
            tp_above = len([v for v in tp_vol if v >= threshold])
            sl_above = len([v for v in sl_vol if v >= threshold])
            tp_pct = tp_above / len(tp_vol) * 100 if tp_vol else 0
            sl_pct = sl_above / len(sl_vol) * 100 if sl_vol else 0
            print(f"    Vol >= {threshold:.1f}x: TP {tp_above:>3}/{len(tp_vol)} ({tp_pct:>5.1f}%) | SL {sl_above:>3}/{len(sl_vol)} ({sl_pct:>5.1f}%)")

    # ============================================================
    # ACCUMULATION VR ANALYSIS
    # ============================================================
    print("\n" + "=" * 100)
    print("2. ACCUMULATION VR (Volume Below/Above Zone)")
    print("=" * 100)

    tp_vr = [t['vr'] for t in tp_trades if t.get('vr') and t.get('vr') < 100]
    sl_vr = [t['vr'] for t in sl_trades if t.get('vr') and t.get('vr') < 100]

    if tp_vr and sl_vr:
        print(f"\n{'Metric':<20} {'TP Trades':>15} {'SL Trades':>15} {'Difference':>15}")
        print("-" * 70)
        print(f"{'Count':<20} {len(tp_vr):>15} {len(sl_vr):>15}")
        print(f"{'Mean VR':<20} {statistics.mean(tp_vr):>15.2f} {statistics.mean(sl_vr):>15.2f} {statistics.mean(tp_vr) - statistics.mean(sl_vr):>+15.2f}")
        print(f"{'Median VR':<20} {statistics.median(tp_vr):>15.2f} {statistics.median(sl_vr):>15.2f} {statistics.median(tp_vr) - statistics.median(sl_vr):>+15.2f}")

    # Phase analysis
    print("\n  Accumulation Phase Distribution:")
    phases = ['STRONG_ACC', 'ACCUMULATION', 'WEAK_ACC', 'NEUTRAL', 'DISTRIBUTION', 'STRONG_DIST']
    tp_phases = [t.get('acc_phase', 'UNKNOWN') for t in tp_trades]
    sl_phases = [t.get('acc_phase', 'UNKNOWN') for t in sl_trades]

    print(f"    {'Phase':<15} {'TP Trades':>12} {'%':>8} {'SL Trades':>12} {'%':>8}")
    print(f"    {'-'*55}")
    for phase in phases:
        tp_count = tp_phases.count(phase)
        sl_count = sl_phases.count(phase)
        tp_pct = tp_count / len(tp_phases) * 100 if tp_phases else 0
        sl_pct = sl_count / len(sl_phases) * 100 if sl_phases else 0
        print(f"    {phase:<15} {tp_count:>12} {tp_pct:>7.1f}% {sl_count:>12} {sl_pct:>7.1f}%")

    # ============================================================
    # RSI ANALYSIS
    # ============================================================
    print("\n" + "=" * 100)
    print("3. RSI AT ENTRY")
    print("=" * 100)

    tp_rsi = [t['rsi'] for t in tp_trades if t.get('rsi')]
    sl_rsi = [t['rsi'] for t in sl_trades if t.get('rsi')]

    if tp_rsi and sl_rsi:
        print(f"\n{'Metric':<20} {'TP Trades':>15} {'SL Trades':>15} {'Difference':>15}")
        print("-" * 70)
        print(f"{'Mean RSI':<20} {statistics.mean(tp_rsi):>15.1f} {statistics.mean(sl_rsi):>15.1f} {statistics.mean(tp_rsi) - statistics.mean(sl_rsi):>+15.1f}")
        print(f"{'Median RSI':<20} {statistics.median(tp_rsi):>15.1f} {statistics.median(sl_rsi):>15.1f} {statistics.median(tp_rsi) - statistics.median(sl_rsi):>+15.1f}")

        # RSI range analysis
        print("\n  RSI Range Analysis:")
        ranges = [(0, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 100)]
        for low, high in ranges:
            tp_in = len([r for r in tp_rsi if low <= r < high])
            sl_in = len([r for r in sl_rsi if low <= r < high])
            tp_pct = tp_in / len(tp_rsi) * 100 if tp_rsi else 0
            sl_pct = sl_in / len(sl_rsi) * 100 if sl_rsi else 0
            print(f"    RSI {low:>2}-{high:<3}: TP {tp_in:>3}/{len(tp_rsi)} ({tp_pct:>5.1f}%) | SL {sl_in:>3}/{len(sl_rsi)} ({sl_pct:>5.1f}%)")

    # ============================================================
    # MOMENTUM ANALYSIS
    # ============================================================
    print("\n" + "=" * 100)
    print("4. PRICE MOMENTUM (5-day % change)")
    print("=" * 100)

    tp_mom = [t['momentum'] for t in tp_trades if t.get('momentum') is not None]
    sl_mom = [t['momentum'] for t in sl_trades if t.get('momentum') is not None]

    if tp_mom and sl_mom:
        print(f"\n{'Metric':<20} {'TP Trades':>15} {'SL Trades':>15} {'Difference':>15}")
        print("-" * 70)
        print(f"{'Mean Momentum':<20} {statistics.mean(tp_mom):>14.1f}% {statistics.mean(sl_mom):>14.1f}% {statistics.mean(tp_mom) - statistics.mean(sl_mom):>+14.1f}%")
        print(f"{'Median Momentum':<20} {statistics.median(tp_mom):>14.1f}% {statistics.median(sl_mom):>14.1f}% {statistics.median(tp_mom) - statistics.median(sl_mom):>+14.1f}%")

    # ============================================================
    # ENTRY TYPE ANALYSIS
    # ============================================================
    print("\n" + "=" * 100)
    print("5. ENTRY TYPE ANALYSIS")
    print("=" * 100)

    entry_types = ['RETEST', 'BO_HOLD', 'BO_PULLBACK']
    print(f"\n{'Entry Type':<15} {'TP':>8} {'SL':>8} {'MaxHold':>8} {'WinRate':>10}")
    print("-" * 55)
    for etype in entry_types:
        tp_count = len([t for t in tp_trades if t['type'] == etype])
        sl_count = len([t for t in sl_trades if t['type'] == etype])
        mh_count = len([t for t in max_hold_trades if t['type'] == etype])
        total = tp_count + sl_count + mh_count
        wr = tp_count / total * 100 if total else 0
        print(f"{etype:<15} {tp_count:>8} {sl_count:>8} {mh_count:>8} {wr:>9.1f}%")

    # ============================================================
    # DETAILED TRADE LIST
    # ============================================================
    print("\n" + "=" * 100)
    print("6. DETAIL SEMUA TRADE (sorted by PnL)")
    print("=" * 100)

    closed_trades = [t for t in all_trades if t['exit_reason'] != 'OPEN']
    closed_trades.sort(key=lambda x: x['pnl'], reverse=True)

    print(f"\n{'#':<3} {'Stock':<6} {'Type':<12} {'Entry':<12} {'Exit':<12} {'Result':<8} {'PnL':>8} {'VolR':>6} {'VR':>6} {'Phase':<12} {'RSI':>5}")
    print("-" * 110)

    for idx, t in enumerate(closed_trades, 1):
        vol_r = f"{t.get('vol_ratio', 0):.1f}x" if t.get('vol_ratio') else "N/A"
        vr = f"{t.get('vr', 0):.1f}" if t.get('vr') and t.get('vr') < 100 else "N/A"
        rsi = f"{t.get('rsi', 0):.0f}" if t.get('rsi') else "N/A"
        phase = t.get('acc_phase', 'N/A')[:10]
        result = 'WIN' if t['pnl'] > 0 else 'LOSS'

        print(f"{idx:<3} {t['stock_code']:<6} {t['type']:<12} {t['entry_date']:<12} {t['exit_date']:<12} {result:<8} {t['pnl']:>+7.1f}% {vol_r:>6} {vr:>6} {phase:<12} {rsi:>5}")

    # ============================================================
    # RECOMMENDATIONS
    # ============================================================
    print("\n" + "=" * 100)
    print("7. REKOMENDASI UNTUK FORMULA V11")
    print("=" * 100)

    if tp_vol and sl_vol and tp_vr and sl_vr:
        print("\nBerdasarkan analisis di atas:")

        # Volume recommendation
        avg_tp_vol = statistics.mean(tp_vol)
        avg_sl_vol = statistics.mean(sl_vol)
        if avg_tp_vol > avg_sl_vol:
            print(f"\n  [VOLUME] Trade TP cenderung punya volume ratio lebih TINGGI")
            print(f"           TP Mean: {avg_tp_vol:.2f}x vs SL Mean: {avg_sl_vol:.2f}x")
            print(f"           REKOMENDASI: Filter entry dengan Vol >= 1.0x average")
        else:
            print(f"\n  [VOLUME] Volume ratio tidak signifikan membedakan TP vs SL")

        # Accumulation recommendation
        avg_tp_vr = statistics.mean(tp_vr)
        avg_sl_vr = statistics.mean(sl_vr)
        if avg_tp_vr > avg_sl_vr:
            print(f"\n  [AKUMULASI] Trade TP cenderung punya VR lebih TINGGI (lebih accumulation)")
            print(f"              TP Mean: {avg_tp_vr:.2f} vs SL Mean: {avg_sl_vr:.2f}")
            print(f"              REKOMENDASI: Filter entry dengan VR >= 1.0 (minimal WEAK_ACC)")
        else:
            print(f"\n  [AKUMULASI] VR tidak signifikan membedakan TP vs SL")

        # Phase recommendation
        acc_phases = ['STRONG_ACC', 'ACCUMULATION', 'WEAK_ACC']
        tp_acc = len([p for p in tp_phases if p in acc_phases])
        sl_acc = len([p for p in sl_phases if p in acc_phases])
        tp_acc_pct = tp_acc / len(tp_phases) * 100 if tp_phases else 0
        sl_acc_pct = sl_acc / len(sl_phases) * 100 if sl_phases else 0

        print(f"\n  [FASE] Trade dalam fase akumulasi:")
        print(f"         TP: {tp_acc}/{len(tp_phases)} ({tp_acc_pct:.1f}%)")
        print(f"         SL: {sl_acc}/{len(sl_phases)} ({sl_acc_pct:.1f}%)")
        if tp_acc_pct > sl_acc_pct:
            print(f"         REKOMENDASI: Filter entry hanya saat fase ACCUMULATION")


if __name__ == '__main__':
    analyze_trades()
