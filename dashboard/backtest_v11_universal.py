# -*- coding: utf-8 -*-
"""
Universal Backtest Formula V11
V10 + Volume Confirmation + RSI Filter

Perubahan dari V10:
1. Entry hanya jika Volume >= 1.0x average (20-day)
2. Entry hanya jika RSI < 70 (hindari overbought)
"""

import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

import psycopg2
from psycopg2.extras import RealDictCursor
from zones_config import STOCK_ZONES, DEFAULT_PARAMS


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


# V11 Additional Parameters
V11_PARAMS = {
    'vol_lookback': 20,        # Lookback period for volume average
    'min_vol_ratio': 1.0,      # Minimum volume ratio vs average
    'rsi_period': 14,          # RSI calculation period
    'max_rsi': 70,             # Maximum RSI for entry (avoid overbought)
    'use_rsi_filter': True,    # Enable/disable RSI filter
}

# State machine constants
STATE_IDLE = 0
STATE_RETEST_PENDING = 1
STATE_BREAKOUT_GATE = 2
STATE_BREAKOUT_ARMED = 3


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


def calculate_volume_ratio(data, idx, lookback=20):
    """Calculate volume ratio vs average - V11 NEW"""
    if idx < lookback:
        return None

    current_vol = float(data[idx]['volume'])
    avg_vol = sum(float(data[i]['volume']) for i in range(idx-lookback, idx)) / lookback

    if avg_vol == 0:
        return None

    return current_vol / avg_vol


def calculate_rsi(data, idx, period=14):
    """Calculate RSI - V11 NEW"""
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


def check_v11_filters(data, idx, v11_params):
    """
    Check V11 additional filters - Volume and RSI
    Returns (passed, vol_ratio, rsi, reject_reason)
    """
    vol_ratio = calculate_volume_ratio(data, idx, v11_params['vol_lookback'])
    rsi = calculate_rsi(data, idx, v11_params['rsi_period'])

    # Check volume filter
    if vol_ratio is None:
        return False, vol_ratio, rsi, "VOL_NO_DATA"

    if vol_ratio < v11_params['min_vol_ratio']:
        return False, vol_ratio, rsi, f"VOL_LOW ({vol_ratio:.2f}x < {v11_params['min_vol_ratio']}x)"

    # Check RSI filter (if enabled)
    if v11_params['use_rsi_filter']:
        if rsi is None:
            return False, vol_ratio, rsi, "RSI_NO_DATA"

        if rsi >= v11_params['max_rsi']:
            return False, vol_ratio, rsi, f"RSI_HIGH ({rsi:.0f} >= {v11_params['max_rsi']})"

    return True, vol_ratio, rsi, None


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


def run_backtest(stock_code, params=None, v11_params=None, start_date='2024-01-01', verbose=False):
    if params is None:
        params = DEFAULT_PARAMS.copy()

    if v11_params is None:
        v11_params = V11_PARAMS.copy()

    zones = STOCK_ZONES.get(stock_code.upper())
    if not zones:
        print(f"No zones configured for {stock_code}")
        return None

    zh = ZoneHelper(zones)

    try:
        conn = get_db_connection()
        all_data = get_stock_data(stock_code, conn)
        conn.close()
    except Exception as e:
        print(f"Database error for {stock_code}: {e}")
        return None

    if not all_data or len(all_data) < 30:
        print(f"Insufficient data for {stock_code}")
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
    pending_entry_conditions = None  # V11b1 checklist conditions at entry

    trades = []
    events_log = []
    filtered_entries = []  # V11: Track filtered entries

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

        # Pending entry execution with V11 filters
        if pending_entry_type and position is None:
            entry_price = open_price
            sl, tp = calculate_sl_tp(zh, pending_entry_type, pending_entry_zone_low,
                                      pending_entry_zone_high, pending_entry_zone_num,
                                      entry_price, params)

            if tp <= entry_price:
                if verbose:
                    events_log.append(f"{date_str}: SKIP_ENTRY {pending_entry_type} Z{pending_entry_zone_num} - TP ({tp:,.0f}) <= entry ({entry_price:,.0f})")
            else:
                # V11: Check volume and RSI filters
                v11_passed, vol_ratio, rsi, reject_reason = check_v11_filters(all_data, pending_entry_idx, v11_params)

                if not v11_passed:
                    # Entry filtered out by V11
                    filtered_entries.append({
                        'date': date_str,
                        'type': pending_entry_type,
                        'zone_num': pending_entry_zone_num,
                        'price': entry_price,
                        'vol_ratio': vol_ratio,
                        'rsi': rsi,
                        'reason': reject_reason,
                    })
                    if verbose:
                        events_log.append(f"{date_str}: V11_FILTER {pending_entry_type} Z{pending_entry_zone_num} - {reject_reason}")
                else:
                    # Entry passes V11 filters
                    # Add vol_ratio to entry_conditions for V11b1 checklist
                    if pending_entry_conditions:
                        pending_entry_conditions['vol_ratio'] = vol_ratio
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
                        'vol_ratio': vol_ratio,
                        'rsi': rsi,
                        'entry_conditions': pending_entry_conditions,  # V11b1 checklist at entry
                    }
                    if verbose:
                        events_log.append(f"{date_str}: ENTRY {pending_entry_type} Z{pending_entry_zone_num} @ {entry_price:,.0f} (Vol:{vol_ratio:.1f}x, RSI:{rsi:.0f})")

            pending_entry_type = None
            pending_entry_zone_low = None
            pending_entry_zone_high = None
            pending_entry_zone_num = 0
            pending_entry_idx = 0
            pending_entry_conditions = None

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
                if verbose:
                    events_log.append(f"{date_str}: EXIT {exit_reason} @ {exit_price:,.0f} ({pnl:+.1f}%)")
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
                if verbose:
                    events_log.append(f"{date_str}: BO_START Z{bo_zone_num}")

        # Breakout gate
        if breakout_locked and state == STATE_BREAKOUT_GATE and breakout_count < 3:
            days_since_start = i - breakout_start_idx
            if days_since_start > 0:
                if close >= locked_zone_high:
                    breakout_count += 1
                    if breakout_count >= 3:
                        breakout_gate_passed = True
                        state = STATE_BREAKOUT_ARMED
                        if verbose:
                            events_log.append(f"{date_str}: GATE_PASSED Z{locked_zone_num}")
                elif close >= locked_zone_low and close < locked_zone_high:
                    breakout_count = 0
                    breakout_start_idx = i
                    if verbose:
                        events_log.append(f"{date_str}: GATE_RESET Z{locked_zone_num}")
                else:
                    breakout_locked = False
                    breakout_count = 0
                    breakout_gate_passed = False
                    state = STATE_IDLE
                    if verbose:
                        events_log.append(f"{date_str}: GATE_FAIL Z{locked_zone_num}")

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
                    # Save entry conditions for BREAKOUT (different from RETEST)
                    pending_entry_conditions = {
                        'trigger_date': date_str,
                        'touch_support': True,  # Breakout counts as support confirmation
                        'hold_above_slow': True,
                        'within_35pct': True,
                        'from_above': True,
                        'prior_r_touch': True,
                        'reclaim': True,  # Breakout is a form of reclaim
                    }
                    if verbose:
                        events_log.append(f"{date_str}: TRIGGER {pending_entry_type} Z{locked_zone_num}")

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
                    # Save V11b1 checklist conditions at trigger time
                    pending_entry_conditions = {
                        'trigger_date': date_str,
                        'touch_support': s_touch,
                        'hold_above_slow': s_hold,
                        'within_35pct': s_not_late,
                        'from_above': s_from_above,
                        'prior_r_touch': prior_resistance_touched,
                        'reclaim': False,  # Will be set on confirm
                    }
                    if verbose:
                        events_log.append(f"{date_str}: RETEST_TRIGGER Z{s_zone_num}")

            if state == STATE_RETEST_PENDING:
                bars_from_touch = i - retest_touch_idx
                if close < locked_zone_low:
                    state = STATE_IDLE
                    retest_touch_idx = 0
                    if verbose:
                        events_log.append(f"{date_str}: RETEST_CANCEL Z{locked_zone_num}")
                elif bars_from_touch <= params['confirm_bars_retest']:
                    any_reclaim = close >= locked_zone_high + buffer
                    if any_reclaim:
                        pending_entry_type = 'RETEST'
                        pending_entry_zone_low = locked_zone_low
                        pending_entry_zone_high = locked_zone_high
                        pending_entry_zone_num = locked_zone_num
                        pending_entry_idx = i
                        # Mark reclaim confirmed in entry conditions
                        if pending_entry_conditions:
                            pending_entry_conditions['reclaim'] = True
                            pending_entry_conditions['confirm_date'] = date_str
                        if verbose:
                            events_log.append(f"{date_str}: RETEST_CONFIRM Z{locked_zone_num}")
                        prior_resistance_touched = False
                        state = STATE_IDLE
                        retest_touch_idx = 0
                elif bars_from_touch > params['confirm_bars_retest']:
                    state = STATE_IDLE
                    retest_touch_idx = 0
                    if verbose:
                        events_log.append(f"{date_str}: RETEST_TIMEOUT Z{locked_zone_num}")

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

    # Calculate summary stats
    closed_trades = [t for t in trades if t.get('exit_reason') != 'OPEN']
    wins = len([t for t in closed_trades if t.get('pnl', 0) > 0])
    losses = len([t for t in closed_trades if t.get('pnl', 0) <= 0])
    total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
    win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0

    return {
        'stock_code': stock_code,
        'zones': zones,
        'trades': trades,
        'filtered_entries': filtered_entries,
        'events_log': events_log,
        'wins': wins,
        'losses': losses,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
    }


def print_report(result):
    if not result:
        return

    stock_code = result['stock_code']
    zones = result['zones']
    trades = result['trades']
    filtered = result.get('filtered_entries', [])

    closed = [t for t in trades if t['exit_reason'] != 'OPEN']
    wins = [t for t in closed if t['pnl'] > 0]
    losses = [t for t in closed if t['pnl'] <= 0]
    total_pnl = sum(t['pnl'] for t in closed)

    print(f"\n{'='*90}")
    print(f"BACKTEST V11 - {stock_code}")
    print(f"{'='*90}")

    print("\nZONES:")
    for znum, z in sorted(zones.items()):
        print(f"  Z{znum}: {z['low']:,} - {z['high']:,}")

    print(f"\nSUMMARY:")
    print(f"  Total Trades : {len(trades)}")
    print(f"  Closed       : {len(closed)}")
    print(f"  Wins         : {len(wins)}")
    print(f"  Losses       : {len(losses)}")
    print(f"  Win Rate     : {len(wins)/len(closed)*100:.1f}%" if closed else "  Win Rate     : N/A")
    print(f"  Total PnL    : {total_pnl:+.2f}%")
    print(f"  Avg PnL      : {total_pnl/len(closed):+.2f}%" if closed else "  Avg PnL      : N/A")
    print(f"  Filtered Out : {len(filtered)} entries")

    if trades:
        print(f"\nTRADES:")
        print(f"  {'#':<3} {'Type':<12} {'Zone':<5} {'Entry':<12} {'Price':>10} {'Exit':<12} {'ExitP':>10} {'Reason':<10} {'PnL':>8} {'Vol':>6} {'RSI':>5}")
        print(f"  {'-'*100}")
        for idx, t in enumerate(trades, 1):
            vol = f"{t.get('vol_ratio', 0):.1f}x" if t.get('vol_ratio') else "N/A"
            rsi = f"{t.get('rsi', 0):.0f}" if t.get('rsi') else "N/A"
            print(f"  {idx:<3} {t['type']:<12} Z{t['zone_num']:<4} {t['entry_date']:<12} {t['entry_price']:>10,.0f} {t['exit_date']:<12} {t['exit_price']:>10,.0f} {t['exit_reason']:<10} {t['pnl']:>+7.1f}% {vol:>6} {rsi:>5}")

    if filtered:
        print(f"\nFILTERED ENTRIES (V11):")
        print(f"  {'#':<3} {'Type':<12} {'Zone':<5} {'Date':<12} {'Price':>10} {'Vol':>8} {'RSI':>5} {'Reason':<30}")
        print(f"  {'-'*90}")
        for idx, f in enumerate(filtered, 1):
            vol = f"{f.get('vol_ratio', 0):.2f}x" if f.get('vol_ratio') else "N/A"
            rsi = f"{f.get('rsi', 0):.0f}" if f.get('rsi') else "N/A"
            print(f"  {idx:<3} {f['type']:<12} Z{f['zone_num']:<4} {f['date']:<12} {f['price']:>10,.0f} {vol:>8} {rsi:>5} {f['reason']:<30}")


def run_all_backtests():
    """Run backtest for all configured stocks"""
    results = []

    print("=" * 90)
    print("FORMULA V11 - BACKTEST ALL STOCKS")
    print("V10 + Volume >= 1.0x + RSI < 70")
    print("=" * 90)

    for stock_code in sorted(STOCK_ZONES.keys()):
        result = run_backtest(stock_code)
        if result:
            results.append(result)
            print_report(result)

    # Summary table
    print("\n" + "=" * 90)
    print("RINGKASAN SEMUA SAHAM - V11")
    print("=" * 90)
    print(f"{'Stock':<8} {'Trades':>8} {'Wins':>8} {'Losses':>8} {'WinRate':>10} {'TotalPnL':>12} {'Filtered':>10}")
    print("-" * 70)

    total_trades = 0
    total_wins = 0
    total_pnl = 0
    total_filtered = 0

    for r in results:
        closed = [t for t in r['trades'] if t['exit_reason'] != 'OPEN']
        wins = [t for t in closed if t['pnl'] > 0]
        losses = [t for t in closed if t['pnl'] <= 0]
        pnl = sum(t['pnl'] for t in closed)
        wr = len(wins)/len(closed)*100 if closed else 0
        filtered = len(r.get('filtered_entries', []))

        total_trades += len(closed)
        total_wins += len(wins)
        total_pnl += pnl
        total_filtered += filtered

        print(f"{r['stock_code']:<8} {len(closed):>8} {len(wins):>8} {len(losses):>8} {wr:>9.1f}% {pnl:>+11.2f}% {filtered:>10}")

    print("-" * 70)
    overall_wr = total_wins/total_trades*100 if total_trades else 0
    print(f"{'TOTAL':<8} {total_trades:>8} {total_wins:>8} {total_trades-total_wins:>8} {overall_wr:>9.1f}% {total_pnl:>+11.2f}% {total_filtered:>10}")

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Backtest Formula V11')
    parser.add_argument('stock', nargs='?', default='ALL', help='Stock code or ALL')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed events')
    parser.add_argument('--no-rsi', action='store_true', help='Disable RSI filter')
    args = parser.parse_args()

    v11_params = V11_PARAMS.copy()
    if args.no_rsi:
        v11_params['use_rsi_filter'] = False

    if args.stock.upper() == 'ALL':
        run_all_backtests()
    else:
        result = run_backtest(args.stock, v11_params=v11_params, verbose=args.verbose)
        if result:
            print_report(result)
            if args.verbose and result['events_log']:
                print(f"\nEVENTS LOG:")
                for e in result['events_log']:
                    print(f"  {e}")
