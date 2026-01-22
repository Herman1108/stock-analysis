# -*- coding: utf-8 -*-
"""
Universal Backtest Formula V11b1
V10 + Volume Confirmation dengan WAITING

Perbedaan dari V11b:
- V11b: Jika vol < 1.0x saat trigger → SKIP entry
- V11b1: Jika vol < 1.0x saat trigger → TUNGGU sampai vol >= 1.0x
         Entry hanya jika harga masih dalam 35% dari TP

Logic:
1. Saat RETEST/BREAKOUT trigger dengan vol < 1.0x → masuk mode WAITING
2. Setiap hari cek: vol >= 1.0x DAN harga masih valid (dalam 35% ke TP)?
3. Jika ya → ENTRY
4. Jika harga keluar dari zona valid → CANCEL waiting
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


# V11b1 Parameters (REVISED)
V11B1_PARAMS = {
    'vol_lookback': 20,           # Periode rata-rata volume
    'min_vol_ratio': 1.0,         # Min volume ratio untuk entry
    'max_wait_days': 6,           # Maksimal tunggu 6 hari (cancel di hari ke-7)
    'not_late_pct': 0.40,         # Harga harus dalam 40% dari S_high ke TP
    'bo_accumulation_days': 7,    # Cek 7 hari sebelumnya untuk akumulasi breakout
    'gate_days': 3,               # Validasi 3 hari berturut-turut di atas resistance
}

# State machine constants
STATE_IDLE = 0
STATE_RETEST_PENDING = 1
STATE_BREAKOUT_GATE = 2
STATE_BREAKOUT_ARMED = 3
STATE_WAITING_VOLUME = 4  # NEW: Waiting for volume confirmation


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
    if idx < lookback:
        return None
    current_vol = float(data[idx]['volume'])
    avg_vol = sum(float(data[i]['volume']) for i in range(idx-lookback, idx)) / lookback
    if avg_vol == 0:
        return None
    return current_vol / avg_vol


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

    def detect_breakout_zone(self, data, idx, accumulation_days=7):
        """
        Breakout Detection dengan Akumulasi 7 Hari (REVISED)

        Kondisi:
        1. Close hari ini > zone_high (breakout)
        2. Dalam 7 hari sebelumnya, minimal ada 1 close <= zone_high
           (bisa dari bawah zona, dalam zona, atau sempat di atas lalu turun)
        """
        if idx < 1:
            return None, None, 0

        close = float(data[idx]['close'])

        for znum in sorted(self.zones.keys()):
            z_high = self.zones[znum]['high']
            z_low = self.zones[znum]['low']

            # Kondisi 1: Close hari ini di atas zona
            if close > z_high:
                # Kondisi 2: Cek akumulasi - minimal 1 hari dalam 7 hari sebelumnya
                # ada close <= zone_high (di bawah atau dalam zona)
                has_accumulation = False
                lookback = min(accumulation_days, idx)

                for j in range(1, lookback + 1):
                    prev_idx = idx - j
                    if prev_idx >= 0:
                        prev_close = float(data[prev_idx]['close'])
                        if prev_close <= z_high:  # Di bawah atau dalam zona
                            has_accumulation = True
                            break

                if has_accumulation:
                    return z_low, z_high, znum

        return None, None, 0


def support_touch(low, s_high):
    return low <= s_high

def support_hold(close, s_low):
    return close >= s_low

def support_from_above(prev_close, s_high):
    return prev_close > s_high

def support_not_late(close, s_high, tp, params_or_pct=0.40):
    """Check if price is not too late (within threshold % to TP)
    params_or_pct can be either a dict with 'not_late_pct' key or a float value
    V11b1 default: 40%
    """
    if isinstance(params_or_pct, dict):
        not_late_pct = params_or_pct.get('not_late_pct', 0.40)
    else:
        not_late_pct = params_or_pct
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


def run_backtest(stock_code, params=None, v11b1_params=None, start_date='2024-01-01', verbose=False):
    if params is None:
        params = DEFAULT_PARAMS.copy()

    if v11b1_params is None:
        v11b1_params = V11B1_PARAMS.copy()

    zones = STOCK_ZONES.get(stock_code.upper())
    if not zones:
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

    # V11b1: Waiting for volume confirmation
    waiting_entry = None  # {'type', 'zone_low', 'zone_high', 'zone_num', 'tp', 'start_idx', 'trigger_vol'}

    trades = []
    events_log = []
    waiting_entries = []  # Track entries that went through waiting
    direct_entries = []   # Track entries that had volume immediately

    start_idx = params['atr_len'] + 1
    for i, d in enumerate(all_data):
        if str(d['date']) >= start_date and i >= start_idx:
            start_idx = i
            break

    # Initialize prior_resistance_touched
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
        vol_ratio = calculate_volume_ratio(all_data, i, v11b1_params['vol_lookback'])

        s_low, s_high, s_zone_num = zh.get_active_support(close)
        r_low, r_high, r_zone_num = zh.get_active_resistance(close)

        frozen = breakout_locked and breakout_count < 3

        # Track resistance touch
        if r_high is not None and not breakout_locked:
            r_touch = high >= r_low - buffer
            if r_touch:
                prior_resistance_touched = True
                prior_resistance_zone = r_zone_num

        # ================================================================
        # V11b1: CHECK WAITING ENTRY FOR VOLUME CONFIRMATION (REVISED)
        # ================================================================
        if waiting_entry and position is None:
            days_waiting = i - waiting_entry['start_idx']

            # Check if price still valid (within 40% to TP) - untuk entry
            price_valid = support_not_late(close, waiting_entry['zone_high'], waiting_entry['tp'], v11b1_params['not_late_pct'])

            # Check if price still >= zone_low (di bawah zona = RESET)
            above_zone_low = close >= waiting_entry['zone_low']

            if not above_zone_low:
                # Price dropped BELOW zone_low → RESET waiting
                if verbose:
                    events_log.append(f"{date_str}: WAIT_RESET {waiting_entry['type']} Z{waiting_entry['zone_num']} - price below zone_low")
                waiting_entry = None
                # Also reset breakout state if applicable
                if state == STATE_BREAKOUT_ARMED:
                    breakout_locked = False
                    breakout_count = 0
                    breakout_gate_passed = False
                    state = STATE_IDLE
            elif days_waiting > v11b1_params['max_wait_days']:
                # Waited > 6 hari (cancel di hari ke-7)
                if verbose:
                    events_log.append(f"{date_str}: WAIT_TIMEOUT {waiting_entry['type']} Z{waiting_entry['zone_num']} after {days_waiting} days")
                waiting_entry = None
                if state == STATE_BREAKOUT_ARMED:
                    breakout_locked = False
                    breakout_count = 0
                    breakout_gate_passed = False
                    state = STATE_IDLE
            elif vol_ratio and vol_ratio >= v11b1_params['min_vol_ratio'] and price_valid:
                # VOLUME CONFIRMED dan harga masih valid (< 40% ke TP) → ENTRY!
                entry_price = open_price
                # SL selalu dari zone_low (unified)
                sl = waiting_entry['zone_low'] * (1 - params['sl_pct'])
                tp = zh.get_tp_for_zone(waiting_entry['zone_num'], entry_price, params)

                if tp > entry_price:
                    position = {
                        'type': waiting_entry['type'],
                        'entry_date': date_str,
                        'entry_price': entry_price,
                        'entry_idx': i,
                        'zone_num': waiting_entry['zone_num'],
                        'zone_low': waiting_entry['zone_low'],
                        'zone_high': waiting_entry['zone_high'],
                        'sl': sl,
                        'tp': tp,
                        'vol_ratio': vol_ratio,
                        'waited_days': days_waiting,
                        'trigger_vol': waiting_entry['trigger_vol'],
                        'entry_method': 'WAITED',
                    }
                    waiting_entries.append({
                        'stock': stock_code,
                        'type': waiting_entry['type'],
                        'trigger_date': waiting_entry['trigger_date'],
                        'trigger_vol': waiting_entry['trigger_vol'],
                        'entry_date': date_str,
                        'entry_vol': vol_ratio,
                        'waited_days': days_waiting,
                    })
                    if verbose:
                        events_log.append(f"{date_str}: WAIT_ENTRY {waiting_entry['type']} Z{waiting_entry['zone_num']} @ {entry_price:,.0f} (waited {days_waiting}d, vol {vol_ratio:.2f}x)")

                    # Reset breakout state after entry
                    if state == STATE_BREAKOUT_ARMED:
                        breakout_locked = False
                        breakout_count = 0
                        breakout_gate_passed = False
                        state = STATE_IDLE

                waiting_entry = None

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

        # Breakout detection (dengan akumulasi 7 hari)
        bo_zone_low, bo_zone_high, bo_zone_num = zh.detect_breakout_zone(
            all_data, i, v11b1_params.get('bo_accumulation_days', 7)
        )
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

        # Breakout gate (REVISED: reset if dalam zona, CANCEL if di bawah zona)
        if breakout_locked and state == STATE_BREAKOUT_GATE and breakout_count < 3:
            days_since_start = i - breakout_start_idx
            if days_since_start > 0:
                if close > locked_zone_high:
                    # Close di atas zona → count++
                    breakout_count += 1
                    if breakout_count >= 3:
                        breakout_gate_passed = True
                        state = STATE_BREAKOUT_ARMED
                        if verbose:
                            events_log.append(f"{date_str}: GATE_PASSED Z{locked_zone_num}")
                elif close >= locked_zone_low:
                    # Close dalam zona (zone_low <= close <= zone_high) → RESET count
                    breakout_count = 0
                    breakout_start_idx = i
                    if verbose:
                        events_log.append(f"{date_str}: GATE_RESET Z{locked_zone_num} (dalam zona)")
                else:
                    # Close di bawah zona (< zone_low) → CANCEL breakout (spec: breakout gagal)
                    breakout_locked = False
                    breakout_count = 0
                    breakout_gate_passed = False
                    state = STATE_IDLE
                    locked_zone_low = None
                    locked_zone_high = None
                    locked_zone_num = 0
                    if verbose:
                        events_log.append(f"{date_str}: GATE_CANCEL Z{locked_zone_num} (close < zone_low, breakout gagal)")

        # Breakout entry (REVISED: simplified, langsung setelah GATE_PASSED)
        if breakout_gate_passed and state == STATE_BREAKOUT_ARMED and position is None and waiting_entry is None:
            # Setelah GATE_PASSED (3 hari valid), langsung cek konfirmasi
            tp = zh.get_tp_for_zone(locked_zone_num, close, params)
            tp_for_check = tp

            # Cek not_late: harga masih dalam 40% jarak ke TP
            price_valid = support_not_late(close, locked_zone_high, tp_for_check, v11b1_params['not_late_pct'])

            if price_valid:
                entry_type = 'BREAKOUT'  # Unified type (no more BO_HOLD/BO_PULLBACK distinction)

                # V11b1: Check volume
                if vol_ratio and vol_ratio >= v11b1_params['min_vol_ratio']:
                    # Volume OK - direct entry
                    entry_price = open_price
                    # SL selalu dari zone_low (unified)
                    sl = locked_zone_low * (1 - params['sl_pct'])
                    tp = zh.get_tp_for_zone(locked_zone_num, entry_price, params)

                    if tp > entry_price:
                        position = {
                            'type': entry_type,
                            'entry_date': date_str,
                            'entry_price': entry_price,
                            'entry_idx': i,
                            'zone_num': locked_zone_num,
                            'zone_low': locked_zone_low,
                            'zone_high': locked_zone_high,
                            'sl': sl,
                            'tp': tp,
                            'vol_ratio': vol_ratio,
                            'waited_days': 0,
                            'trigger_vol': vol_ratio,
                            'entry_method': 'DIRECT',
                        }
                        direct_entries.append({
                            'stock': stock_code,
                            'type': entry_type,
                            'date': date_str,
                            'vol': vol_ratio,
                        })
                        if verbose:
                            events_log.append(f"{date_str}: DIRECT_ENTRY {entry_type} Z{locked_zone_num} (vol {vol_ratio:.2f}x)")

                        # Reset breakout state after entry
                        prior_resistance_touched = False
                        prior_resistance_zone = 0
                        breakout_locked = False
                        breakout_count = 0
                        breakout_gate_passed = False
                        state = STATE_IDLE
                else:
                    # Volume LOW - enter waiting mode
                    waiting_entry = {
                        'type': entry_type,
                        'zone_low': locked_zone_low,
                        'zone_high': locked_zone_high,
                        'zone_num': locked_zone_num,
                        'tp': tp,
                        'start_idx': i,
                        'trigger_date': date_str,
                        'trigger_vol': vol_ratio if vol_ratio else 0,
                    }
                    if verbose:
                        vol_str = f"{vol_ratio:.2f}x" if vol_ratio else "N/A"
                        events_log.append(f"{date_str}: WAIT_START {entry_type} Z{locked_zone_num} (vol {vol_str} < {v11b1_params['min_vol_ratio']}x)")

                    # Keep breakout state during waiting (don't reset yet)
            else:
                # Price too far from zone, but stay in ARMED state
                if verbose:
                    events_log.append(f"{date_str}: BO_ARMED Z{locked_zone_num} waiting (price {close:,.0f} > 40% to TP)")

        # Handle BREAKOUT_ARMED state: cancel if price drops back into or below zone
        # This allows retest detection to take over when price returns to the zone
        if state == STATE_BREAKOUT_ARMED and locked_zone_high is not None:
            if close <= locked_zone_high:
                # Price dropped back into zone (close <= zone_high) → CANCEL breakout
                # This enables retest detection when price returns to support
                if verbose:
                    if waiting_entry:
                        events_log.append(f"{date_str}: WAIT_CANCEL {waiting_entry['type']} Z{locked_zone_num} (close <= zone_high, breakout failed)")
                    else:
                        events_log.append(f"{date_str}: BO_CANCEL Z{locked_zone_num} (close <= zone_high, price back in zone)")
                waiting_entry = None
                breakout_locked = False
                breakout_count = 0
                breakout_gate_passed = False
                state = STATE_IDLE
                locked_zone_low = None
                locked_zone_high = None
                locked_zone_num = 0

        # Retest detection
        if not frozen and position is None and waiting_entry is None:
            if state == STATE_IDLE and s_low is not None:
                tp_for_check = zh.get_tp_for_zone(s_zone_num, s_high, params)
                s_touch = support_touch(low, s_high)
                s_hold = support_hold(close, s_low)
                s_from_above = support_from_above(prev_close, s_high)
                s_not_late = support_not_late(close, s_high, tp_for_check, v11b1_params['not_late_pct'])

                # prior_resistance_zone harus > s_zone_num (resistance di ATAS support)
                if s_touch and s_hold and s_not_late and s_from_above and prior_resistance_touched and prior_resistance_zone > s_zone_num:
                    state = STATE_RETEST_PENDING
                    retest_touch_idx = i
                    locked_zone_low = s_low
                    locked_zone_high = s_high
                    locked_zone_num = s_zone_num
                    if verbose:
                        events_log.append(f"{date_str}: RETEST_TRIGGER Z{s_zone_num}")

            if state == STATE_RETEST_PENDING:
                bars_from_touch = i - retest_touch_idx
                if close < locked_zone_low:
                    # Price dropped below zone → RESET
                    state = STATE_IDLE
                    retest_touch_idx = 0
                elif bars_from_touch <= params['confirm_bars_retest']:
                    any_reclaim = close >= locked_zone_high + buffer
                    if any_reclaim:
                        tp = zh.get_tp_for_zone(locked_zone_num, close, params)

                        # V11b1: Check volume
                        if vol_ratio and vol_ratio >= v11b1_params['min_vol_ratio']:
                            # Volume OK - direct entry
                            entry_price = open_price
                            # SL selalu dari zone_low (unified)
                            sl = locked_zone_low * (1 - params['sl_pct'])
                            tp = zh.get_tp_for_zone(locked_zone_num, entry_price, params)

                            if tp > entry_price:
                                position = {
                                    'type': 'RETEST',
                                    'entry_date': date_str,
                                    'entry_price': entry_price,
                                    'entry_idx': i,
                                    'zone_num': locked_zone_num,
                                    'zone_low': locked_zone_low,
                                    'zone_high': locked_zone_high,
                                    'sl': sl,
                                    'tp': tp,
                                    'vol_ratio': vol_ratio,
                                    'waited_days': 0,
                                    'trigger_vol': vol_ratio,
                                    'entry_method': 'DIRECT',
                                }
                                direct_entries.append({
                                    'stock': stock_code,
                                    'type': 'RETEST',
                                    'date': date_str,
                                    'vol': vol_ratio,
                                })
                                if verbose:
                                    events_log.append(f"{date_str}: DIRECT_ENTRY RETEST Z{locked_zone_num} (vol {vol_ratio:.2f}x)")
                        else:
                            # Volume LOW - enter waiting mode
                            waiting_entry = {
                                'type': 'RETEST',
                                'zone_low': locked_zone_low,
                                'zone_high': locked_zone_high,
                                'zone_num': locked_zone_num,
                                'tp': tp,
                                'start_idx': i,
                                'trigger_date': date_str,
                                'trigger_vol': vol_ratio if vol_ratio else 0,
                            }
                            if verbose:
                                vol_str = f"{vol_ratio:.2f}x" if vol_ratio else "N/A"
                                events_log.append(f"{date_str}: WAIT_START RETEST Z{locked_zone_num} (vol {vol_str} < {v11b1_params['min_vol_ratio']}x)")

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

    # Calculate summary
    closed_trades = [t for t in trades if t.get('exit_reason') != 'OPEN']
    wins = len([t for t in closed_trades if t.get('pnl', 0) > 0])
    losses = len([t for t in closed_trades if t.get('pnl', 0) <= 0])
    total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
    win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0

    return {
        'stock_code': stock_code,
        'zones': zones,
        'trades': trades,
        'events_log': events_log,
        'wins': wins,
        'losses': losses,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'waiting_entries': waiting_entries,
        'direct_entries': direct_entries,
    }


def print_report(result):
    if not result:
        return

    stock_code = result['stock_code']
    trades = result['trades']
    waiting = result.get('waiting_entries', [])
    direct = result.get('direct_entries', [])

    closed = [t for t in trades if t['exit_reason'] != 'OPEN']
    wins = [t for t in closed if t['pnl'] > 0]
    losses = [t for t in closed if t['pnl'] <= 0]
    total_pnl = sum(t['pnl'] for t in closed)

    print(f"\n{'='*100}")
    print(f"BACKTEST V11b1 - {stock_code}")
    print(f"{'='*100}")

    print(f"\nSUMMARY:")
    print(f"  Total Trades : {len(trades)}")
    print(f"  Closed       : {len(closed)}")
    print(f"  Wins         : {len(wins)}")
    print(f"  Losses       : {len(losses)}")
    print(f"  Win Rate     : {len(wins)/len(closed)*100:.1f}%" if closed else "  Win Rate     : N/A")
    print(f"  Total PnL    : {total_pnl:+.2f}%")
    print(f"  Direct Entry : {len(direct)}")
    print(f"  Waited Entry : {len(waiting)}")

    if trades:
        print(f"\nTRADES:")
        print(f"  {'#':<3} {'Type':<12} {'Zone':<5} {'Entry':<12} {'Price':>10} {'Method':<8} {'Wait':>5} {'Vol':>6} {'Exit':<12} {'Reason':<8} {'PnL':>8}")
        print(f"  {'-'*110}")
        for idx, t in enumerate(trades, 1):
            method = t.get('entry_method', 'N/A')[:6]
            waited = t.get('waited_days', 0)
            vol = f"{t.get('vol_ratio', 0):.1f}x" if t.get('vol_ratio') else 'N/A'
            print(f"  {idx:<3} {t['type']:<12} Z{t['zone_num']:<4} {t['entry_date']:<12} {t['entry_price']:>10,.0f} {method:<8} {waited:>5}d {vol:>6} {t['exit_date']:<12} {t['exit_reason']:<8} {t['pnl']:>+7.1f}%")


def run_all_backtests():
    results = []

    print("=" * 100)
    print("FORMULA V11b1 - BACKTEST ALL STOCKS")
    print("V10 + Volume Wait (entry saat vol >= 1.0x, harga masih valid)")
    print("=" * 100)

    for stock_code in sorted(STOCK_ZONES.keys()):
        result = run_backtest(stock_code)
        if result:
            results.append(result)
            print_report(result)

    # Summary
    print("\n" + "=" * 100)
    print("RINGKASAN V11b1")
    print("=" * 100)

    total_trades = 0
    total_wins = 0
    total_pnl = 0
    total_direct = 0
    total_waited = 0

    print(f"\n{'Stock':<8} {'Trades':>8} {'Wins':>8} {'Losses':>8} {'WinRate':>10} {'TotalPnL':>12} {'Direct':>8} {'Waited':>8}")
    print("-" * 85)

    for r in results:
        closed = [t for t in r['trades'] if t['exit_reason'] != 'OPEN']
        wins = len([t for t in closed if t['pnl'] > 0])
        losses = len([t for t in closed if t['pnl'] <= 0])
        pnl = sum(t['pnl'] for t in closed)
        wr = wins / len(closed) * 100 if closed else 0
        direct = len(r.get('direct_entries', []))
        waited = len(r.get('waiting_entries', []))

        total_trades += len(closed)
        total_wins += wins
        total_pnl += pnl
        total_direct += direct
        total_waited += waited

        print(f"{r['stock_code']:<8} {len(closed):>8} {wins:>8} {losses:>8} {wr:>9.1f}% {pnl:>+11.1f}% {direct:>8} {waited:>8}")

    print("-" * 85)
    overall_wr = total_wins / total_trades * 100 if total_trades else 0
    print(f"{'TOTAL':<8} {total_trades:>8} {total_wins:>8} {total_trades - total_wins:>8} {overall_wr:>9.1f}% {total_pnl:>+11.1f}% {total_direct:>8} {total_waited:>8}")

    return results


if __name__ == '__main__':
    run_all_backtests()
