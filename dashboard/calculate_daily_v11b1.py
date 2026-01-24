# -*- coding: utf-8 -*-
"""
CALCULATE DAILY V11B1 - Pre-compute Results per Emiten
======================================================
Jalankan setelah update data harian.
Setiap emiten diproses independen - error di satu emiten tidak mempengaruhi yang lain.

Usage:
    python calculate_daily_v11b1.py              # Process all stocks
    python calculate_daily_v11b1.py CUAN MBMA   # Process specific stocks
"""

import sys
import os
import json
from datetime import datetime, date
from decimal import Decimal

# Add dashboard directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Import V11b1 components
from zones_config import STOCK_ZONES, get_zones, DEFAULT_PARAMS, STOCK_FORMULA
from backtest_v11b1_universal import (
    run_backtest,
    ZoneHelper,
    support_touch,
    support_hold,
    support_from_above,
    support_not_late,
    calculate_volume_ratio,
    get_db_connection,
    calculate_ma,
    check_ma_uptrend
)

# ============================================================
# CONFIGURATION
# ============================================================

# All V11b1 stocks
V11B1_STOCKS = [
    'ADMR', 'BBCA', 'BMRI', 'BREN', 'BRPT',
    'CBDK', 'CBRE', 'CDIA', 'CUAN', 'DSNG',
    'FUTR', 'HRUM', 'MBMA', 'MDKA', 'NCKL',
    'PANI', 'PTRO', 'RATU', 'TINS', 'WIFI'
]

FORMULA_VERSION = 'V11b1'

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_latest_price_data(conn, stock_code, days=120):
    """Get latest price data for a stock (default 120 days for MA100 calculation)"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT date, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM stock_daily
        WHERE stock_code = %s
        AND close_price IS NOT NULL
        ORDER BY date DESC
        LIMIT %s
    ''', (stock_code, days))
    rows = cur.fetchall()
    cur.close()
    return list(reversed(rows)) if rows else []


def calculate_stock_status(stock_code, conn):
    """
    Calculate V11b1 status for a single stock.
    Returns dict with all calculated values.
    """
    result = {
        'stock_code': stock_code,
        'calc_date': date.today(),
        'has_error': False,
        'error_message': None,
    }

    try:
        # Get zones
        zones = get_zones(stock_code)
        if not zones:
            result['has_error'] = True
            result['error_message'] = f'No zones configured for {stock_code}'
            return result

        zh = ZoneHelper(zones)

        # Get price data (120 days for MA100 calculation)
        price_data = get_latest_price_data(conn, stock_code, days=120)
        if not price_data or len(price_data) < 5:
            result['has_error'] = True
            result['error_message'] = f'Insufficient price data for {stock_code}'
            return result

        # Current price info
        latest = price_data[-1]
        prev = price_data[-2] if len(price_data) > 1 else latest

        current_price = float(latest['close'])
        prev_close = float(prev['close'])
        price_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        result['current_price'] = current_price
        result['price_change_pct'] = round(price_change_pct, 2)

        # Get active support and resistance zones
        s_low, s_high, s_zone_num = zh.get_active_support(current_price)
        r_low, r_high, r_zone_num = zh.get_active_resistance(current_price)

        result['support_zone_num'] = s_zone_num
        result['support_zone_low'] = s_low
        result['support_zone_high'] = s_high
        result['resistance_zone_num'] = r_zone_num
        result['resistance_zone_low'] = r_low
        result['resistance_zone_high'] = r_high

        # Calculate volume ratio
        vol_ratio = None
        if len(price_data) >= 20:
            current_vol = float(latest['volume'])
            avg_vol = sum(float(d['volume']) for d in price_data[-21:-1]) / 20
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else None

        result['vol_ratio'] = round(vol_ratio, 2) if vol_ratio else None
        result['vol_status'] = 'OK' if vol_ratio and vol_ratio >= 1.0 else 'LOW'

        # Count days above zone
        days_above = 0
        if s_high:
            for d in reversed(price_data):
                if float(d['close']) > s_high:
                    days_above += 1
                else:
                    break
        result['days_above_zone'] = days_above

        # Check if came from below (within last 7 days)
        came_from_below = False
        if s_high and len(price_data) >= 7:
            for d in price_data[-7:]:
                if float(d['close']) <= s_high:
                    came_from_below = True
                    break
        result['came_from_below'] = came_from_below

        # Check if came from above (previous close > zone_high) - for RETEST detection
        came_from_above = False
        if s_high and len(price_data) >= 2:
            prev_close = float(price_data[-2]['close'])
            if prev_close > s_high:
                came_from_above = True
            # Also check if recently came from above (within 7 days had close > zone_high)
            for d in price_data[-7:]:
                if float(d['close']) > s_high:
                    came_from_above = True
                    break
        result['came_from_above'] = came_from_above

        # Determine status and confirm_type
        status = 'NEUTRAL'
        confirm_type = 'WAIT'
        action = 'WATCH'
        action_reason = ''

        if s_high:
            # Check position relative to zones
            in_zone = s_low <= current_price <= s_high if s_low and s_high else False
            above_zone = current_price > s_high if s_high else False
            below_zone = current_price < s_low if s_low else False

            # Check if below resistance zone (breakout failed)
            below_resistance = False
            if r_low and current_price < r_low:
                below_resistance = True

            if above_zone:
                # V11b1 Spec: BREAKOUT requires came_from_below = TRUE
                # "Dalam 7 hari sebelumnya, minimal ada 1 close <= zone_high"
                if came_from_below:
                    # Valid breakout - price rose from below/within zone recently
                    if days_above >= 3:
                        confirm_type = 'BREAKOUT_OK'
                        status = 'BREAKOUT'
                    else:
                        confirm_type = f'BREAKOUT ({days_above}/3)'
                        status = 'BREAKOUT'

                    # Check not_late for entry
                    tp = zh.get_tp_for_zone(s_zone_num, current_price, DEFAULT_PARAMS)
                    if tp and s_high:
                        distance_to_tp = tp - s_high
                        threshold = s_high + (distance_to_tp * 0.40)
                        is_not_late = current_price <= threshold

                        if confirm_type == 'BREAKOUT_OK':
                            if vol_ratio and vol_ratio >= 1.0 and is_not_late:
                                action = 'ENTRY'
                                action_reason = f'BREAKOUT confirmed! Vol {vol_ratio:.2f}x OK'
                            elif not is_not_late:
                                action = 'WAIT_PULLBACK'
                                action_reason = f'Tunggu pullback ke Rp {threshold:,.0f}'
                                result['pullback_entry_price'] = threshold
                                result['pullback_sl'] = s_low * 0.95 if s_low else None
                                result['pullback_tp'] = tp
                                if result['pullback_sl'] and result['pullback_entry_price']:
                                    risk = result['pullback_entry_price'] - result['pullback_sl']
                                    reward = tp - result['pullback_entry_price']
                                    result['pullback_rr_ratio'] = round(reward / risk, 2) if risk > 0 else None
                            else:
                                action = 'WATCH'
                                action_reason = f'Vol {vol_ratio:.2f}x < 1.0x, tunggu volume'
                        else:
                            action = 'WATCH'
                            action_reason = f'Tunggu {3 - days_above} hari lagi di atas zona'
                else:
                    # Price above zone but NEVER came from below - NOT a breakout
                    status = 'ABOVE_SUPPORT'
                    confirm_type = 'DI_ATAS_ZONA'
                    action = 'WATCH'
                    action_reason = f'Di atas zona {s_low:,.0f}-{s_high:,.0f} - tunggu retest'

            elif in_zone:
                # Check for RETEST condition when price is IN_ZONE
                # RETEST: price came from above and is now in/touching support zone
                if came_from_above:
                    # RETEST detected - price came from above and is now in support zone
                    status = 'RETEST_ZONE'

                    # Check if today's low touched support (for retest confirmation)
                    today_low = float(latest['low'])
                    touched_support = today_low <= s_high

                    # Check not_late for entry
                    tp = zh.get_tp_for_zone(s_zone_num, current_price, DEFAULT_PARAMS)
                    is_not_late = True
                    if tp and s_high:
                        distance_to_tp = tp - s_high
                        threshold = s_high + (distance_to_tp * 0.40)
                        is_not_late = current_price <= threshold

                    # RETEST is VALID if close >= support_low (still holding support)
                    # RETEST is CANCELLED only if close < support_low
                    if current_price >= s_low:
                        confirm_type = 'RETEST_OK'

                        if vol_ratio and vol_ratio >= 1.0 and is_not_late:
                            action = 'ENTRY'
                            action_reason = f'RETEST confirmed! Vol {vol_ratio:.2f}x OK, support hold'
                        elif not is_not_late:
                            action = 'WAIT_PULLBACK'
                            action_reason = f'Tunggu pullback ke Rp {threshold:,.0f}'
                        else:
                            action = 'WATCH'
                            action_reason = f'RETEST valid, tunggu volume >= 1.0x (current: {vol_ratio:.2f}x)'
                    else:
                        # This shouldn't happen if in_zone is True, but just in case
                        confirm_type = 'BREAKDOWN'
                        action = 'AVOID'
                        action_reason = f'Support breakdown < {s_low:,.0f}'
                else:
                    # Price in zone but didn't come from above - neutral
                    status = 'IN_ZONE'
                    confirm_type = 'WAIT'
                    action = 'WATCH'
                    action_reason = 'Dalam zona, pantau akumulasi'

            elif below_zone:
                status = 'BELOW_ZONE'
                confirm_type = 'BREAKDOWN'
                action = 'AVOID'
                action_reason = f'Harga di bawah support {s_low:,.0f}'

        # V11b2 MA Filter: Block entry if MA30 <= MA100 (downtrend)
        stock_formula = STOCK_FORMULA.get(stock_code.upper(), 'V11b1')
        ma_uptrend = True
        ma30 = None
        ma100 = None
        if stock_formula == 'V11b2' and len(price_data) >= 100:
            ma_uptrend = check_ma_uptrend(price_data, len(price_data) - 1, ma_short=30, ma_long=100)
            ma30 = calculate_ma(price_data, len(price_data) - 1, 30)
            ma100 = calculate_ma(price_data, len(price_data) - 1, 100)
            result['ma_uptrend'] = ma_uptrend
            result['ma30'] = ma30
            result['ma100'] = ma100

            # V11b2: If MA downtrend, block entry or show FROM_RESISTANCE
            if not ma_uptrend:
                if action in ('ENTRY', 'WAIT_PULLBACK'):
                    action = 'WATCH'
                    action_reason = f'V11b2: MA30 ({ma30:,.0f}) <= MA100 ({ma100:,.0f}) - downtrend, entry blocked'
                    confirm_type = 'FROM_RESISTANCE'
                elif confirm_type in ('DI_ATAS_ZONA', 'BREAKOUT_OK') and not came_from_below:
                    # V11b2: Price above zone but in downtrend - FROM_RESISTANCE
                    status = 'ABOVE_SUPPORT'
                    confirm_type = 'FROM_RESISTANCE'
                    action = 'WATCH'
                    action_reason = f'V11b2: MA30 ({ma30:,.0f}) <= MA100 ({ma100:,.0f}) - downtrend. Support: {s_low:,.0f}-{s_high:,.0f}'

        result['status'] = status
        result['confirm_type'] = confirm_type
        result['action'] = action
        result['action_reason'] = action_reason
        result['formula_version'] = stock_formula

        # Build checklist
        checklist = {
            'came_from_below': came_from_below,
            'close_above_zone_high': current_price > s_high if s_high else False,
            'days_above_3': days_above >= 3,
            'volume_ok': vol_ratio >= 1.0 if vol_ratio else False,
        }
        result['checklist'] = checklist

        # Run backtest
        backtest_result = run_backtest(stock_code, start_date='2024-01-01')
        if backtest_result:
            trades = backtest_result.get('trades', [])
            result['trade_history'] = trades
            result['total_trades'] = len(trades)

            closed_trades = [t for t in trades if t.get('exit_reason') != 'OPEN']
            wins = len([t for t in closed_trades if t.get('pnl', 0) > 0])
            losses = len([t for t in closed_trades if t.get('pnl', 0) <= 0])

            result['wins'] = wins
            result['losses'] = losses
            result['win_rate'] = round(wins / len(closed_trades) * 100, 1) if closed_trades else 0
            result['total_pnl'] = round(sum(t.get('pnl', 0) for t in closed_trades), 1)

            # Check for open position (any year - trade is OPEN regardless of entry date)
            for trade in trades:
                if trade.get('exit_reason') == 'OPEN':
                    result['has_open_position'] = True
                    result['position_entry_date'] = trade.get('entry_date', '')
                    result['position_entry_price'] = trade.get('entry_price')
                    result['position_current_pnl'] = trade.get('pnl')
                    result['position_sl'] = trade.get('sl')
                    result['position_tp'] = trade.get('tp')
                    result['action'] = 'RUNNING'
                    result['status'] = 'RUNNING'
                    break

    except Exception as e:
        result['has_error'] = True
        result['error_message'] = str(e)

    return result


def save_result_to_db(conn, stock_code, result):
    """Save calculated result to stock's own table"""
    table_name = f'v11b1_results_{stock_code.lower()}'

    # Convert trade_history and checklist to JSON
    trade_history_json = Json(result.get('trade_history')) if result.get('trade_history') else None
    checklist_json = Json(result.get('checklist')) if result.get('checklist') else None

    cur = conn.cursor()

    try:
        # Upsert - insert or update if date exists
        cur.execute(f'''
            INSERT INTO {table_name} (
                calc_date, current_price, price_change_pct,
                status, action, action_reason,
                support_zone_num, support_zone_low, support_zone_high,
                resistance_zone_num, resistance_zone_low, resistance_zone_high,
                confirm_type, days_above_zone, came_from_below,
                vol_ratio, vol_status,
                has_open_position, position_entry_date, position_entry_price,
                position_current_pnl, position_sl, position_tp,
                trade_history, total_trades, wins, losses, win_rate, total_pnl,
                checklist,
                pullback_entry_price, pullback_sl, pullback_tp, pullback_rr_ratio,
                has_error, error_message, formula_version
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (calc_date) DO UPDATE SET
                current_price = EXCLUDED.current_price,
                price_change_pct = EXCLUDED.price_change_pct,
                status = EXCLUDED.status,
                action = EXCLUDED.action,
                action_reason = EXCLUDED.action_reason,
                support_zone_num = EXCLUDED.support_zone_num,
                support_zone_low = EXCLUDED.support_zone_low,
                support_zone_high = EXCLUDED.support_zone_high,
                resistance_zone_num = EXCLUDED.resistance_zone_num,
                resistance_zone_low = EXCLUDED.resistance_zone_low,
                resistance_zone_high = EXCLUDED.resistance_zone_high,
                confirm_type = EXCLUDED.confirm_type,
                days_above_zone = EXCLUDED.days_above_zone,
                came_from_below = EXCLUDED.came_from_below,
                vol_ratio = EXCLUDED.vol_ratio,
                vol_status = EXCLUDED.vol_status,
                has_open_position = EXCLUDED.has_open_position,
                position_entry_date = EXCLUDED.position_entry_date,
                position_entry_price = EXCLUDED.position_entry_price,
                position_current_pnl = EXCLUDED.position_current_pnl,
                position_sl = EXCLUDED.position_sl,
                position_tp = EXCLUDED.position_tp,
                trade_history = EXCLUDED.trade_history,
                total_trades = EXCLUDED.total_trades,
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses,
                win_rate = EXCLUDED.win_rate,
                total_pnl = EXCLUDED.total_pnl,
                checklist = EXCLUDED.checklist,
                pullback_entry_price = EXCLUDED.pullback_entry_price,
                pullback_sl = EXCLUDED.pullback_sl,
                pullback_tp = EXCLUDED.pullback_tp,
                pullback_rr_ratio = EXCLUDED.pullback_rr_ratio,
                has_error = EXCLUDED.has_error,
                error_message = EXCLUDED.error_message,
                formula_version = EXCLUDED.formula_version,
                calc_timestamp = NOW()
        ''', (
            result.get('calc_date'),
            result.get('current_price'),
            result.get('price_change_pct'),
            result.get('status'),
            result.get('action'),
            result.get('action_reason'),
            result.get('support_zone_num'),
            result.get('support_zone_low'),
            result.get('support_zone_high'),
            result.get('resistance_zone_num'),
            result.get('resistance_zone_low'),
            result.get('resistance_zone_high'),
            result.get('confirm_type'),
            result.get('days_above_zone'),
            result.get('came_from_below'),
            result.get('vol_ratio'),
            result.get('vol_status'),
            result.get('has_open_position', False),
            result.get('position_entry_date'),
            result.get('position_entry_price'),
            result.get('position_current_pnl'),
            result.get('position_sl'),
            result.get('position_tp'),
            trade_history_json,
            result.get('total_trades', 0),
            result.get('wins', 0),
            result.get('losses', 0),
            result.get('win_rate', 0),
            result.get('total_pnl', 0),
            checklist_json,
            result.get('pullback_entry_price'),
            result.get('pullback_sl'),
            result.get('pullback_tp'),
            result.get('pullback_rr_ratio'),
            result.get('has_error', False),
            result.get('error_message'),
            result.get('formula_version', FORMULA_VERSION)
        ))

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        print(f'    [ERROR] Failed to save: {e}')
        return False

    finally:
        cur.close()


def ensure_table_exists(conn, stock_code):
    """Create table for stock if not exists"""
    table_name = f'v11b1_results_{stock_code.lower()}'
    cur = conn.cursor()

    try:
        cur.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                calc_date DATE NOT NULL,
                calc_timestamp TIMESTAMP DEFAULT NOW(),
                current_price DECIMAL(12,2),
                price_change_pct DECIMAL(8,2),
                status VARCHAR(50),
                action VARCHAR(50),
                action_reason TEXT,
                support_zone_num INTEGER,
                support_zone_low DECIMAL(12,2),
                support_zone_high DECIMAL(12,2),
                resistance_zone_num INTEGER,
                resistance_zone_low DECIMAL(12,2),
                resistance_zone_high DECIMAL(12,2),
                confirm_type VARCHAR(50),
                days_above_zone INTEGER DEFAULT 0,
                came_from_below BOOLEAN DEFAULT FALSE,
                vol_ratio DECIMAL(8,2),
                vol_status VARCHAR(20),
                has_open_position BOOLEAN DEFAULT FALSE,
                position_entry_date DATE,
                position_entry_price DECIMAL(12,2),
                position_current_pnl DECIMAL(8,2),
                position_sl DECIMAL(12,2),
                position_tp DECIMAL(12,2),
                trade_history JSONB,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_rate DECIMAL(5,2),
                total_pnl DECIMAL(8,2),
                checklist JSONB,
                pullback_entry_price DECIMAL(12,2),
                pullback_sl DECIMAL(12,2),
                pullback_tp DECIMAL(12,2),
                pullback_rr_ratio DECIMAL(5,2),
                has_error BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                formula_version VARCHAR(20) DEFAULT 'V11b1',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(calc_date)
            )
        ''')
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f'    [ERROR] Failed to create table: {e}')
        return False
    finally:
        cur.close()


# ============================================================
# MAIN EXECUTION
# ============================================================

def process_stock(stock_code, conn):
    """Process single stock - isolated from other stocks"""
    print(f'\n[{stock_code}] Processing...')

    try:
        # Ensure table exists
        if not ensure_table_exists(conn, stock_code):
            print(f'    [FAIL] Could not create table')
            return False

        # Calculate status
        result = calculate_stock_status(stock_code, conn)

        if result.get('has_error'):
            print(f'    [ERROR] {result.get("error_message")}')
            # Still save the error to database
            save_result_to_db(conn, stock_code, result)
            return False

        # Save to database
        if save_result_to_db(conn, stock_code, result):
            status = result.get('status', 'UNKNOWN')
            action = result.get('action', 'UNKNOWN')
            price = result.get('current_price', 0)
            print(f'    [OK] Price: {price:,.0f} | Status: {status} | Action: {action}')
            return True
        else:
            return False

    except Exception as e:
        print(f'    [EXCEPTION] {e}')
        return False


def main():
    """Main execution - process all or specific stocks"""
    print('=' * 60)
    print('  CALCULATE DAILY V11B1 - Pre-compute Results')
    print('=' * 60)
    print(f'  Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # Determine which stocks to process
    if len(sys.argv) > 1:
        stocks_to_process = [s.upper() for s in sys.argv[1:]]
        print(f'\nProcessing specific stocks: {", ".join(stocks_to_process)}')
    else:
        stocks_to_process = V11B1_STOCKS
        print(f'\nProcessing all {len(stocks_to_process)} stocks')

    # Connect to database
    try:
        conn = get_db_connection()
        print('\n[DB] Connected successfully')
    except Exception as e:
        print(f'\n[DB ERROR] {e}')
        return

    # Process each stock independently
    success = 0
    failed = 0
    errors = []

    for stock_code in stocks_to_process:
        if stock_code not in STOCK_ZONES:
            print(f'\n[{stock_code}] SKIP - Not in STOCK_ZONES config')
            continue

        if process_stock(stock_code, conn):
            success += 1
        else:
            failed += 1
            errors.append(stock_code)

    conn.close()

    # Summary
    print('\n' + '=' * 60)
    print('  SUMMARY')
    print('=' * 60)
    print(f'  Success: {success}')
    print(f'  Failed:  {failed}')
    if errors:
        print(f'  Errors:  {", ".join(errors)}')
    print('=' * 60)


if __name__ == '__main__':
    main()
