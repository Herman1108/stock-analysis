# -*- coding: utf-8 -*-
"""
BACKTEST V6 FORMULA
===================
Backtest formula V6 yang digunakan di menu Analysis.

Entry Criteria (ALL must be true):
1. Sideways terdeteksi (Range% < Percentile 40)
2. Phase = ACCUMULATION (Vol Ratio > 1.2)
3. Near Support (position < 50% of range)
4. Minimal 2/4 konfirmasi signals
5. R:R ratio >= 1.5

Exit:
- Stop Loss: Low Sideways - (Range x 2%)
- Take Profit: High Sideways
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import sys
sys.stdout.reconfigure(encoding='utf-8')


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='stock_analysis',
        user='postgres',
        password='postgres'
    )


def load_stock_data(stock_code):
    """Load all stock data"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT date, high_price as high, low_price as low,
               close_price as close, volume
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date ASC
    ''', (stock_code,))
    data = cur.fetchall()
    conn.close()

    result = []
    for i, row in enumerate(data):
        prev_close = data[i-1]['close'] if i > 0 else row['close']
        change = ((row['close'] - prev_close) / prev_close * 100) if prev_close else 0
        result.append({
            'date': row['date'],
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']),
            'change': change
        })
    return result


def calculate_historical_ranges(data, window_size=10, history_periods=60):
    """Calculate historical ranges for threshold calibration"""
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
    """Get adaptive threshold based on historical data"""
    if len(data) < history_periods + lookback_window:
        return None

    hist_data = data[:-lookback_window] if lookback_window > 0 else data
    hist_ranges = calculate_historical_ranges(hist_data, lookback_window, history_periods)

    if len(hist_ranges) < 10:
        return None

    sorted_ranges = sorted(hist_ranges)
    idx = int(len(sorted_ranges) * percentile / 100)
    return sorted_ranges[idx]


def detect_sideways(data, min_days=3, max_days=15):
    """Detect sideways with adaptive threshold"""
    if len(data) < max_days + 60:
        return None

    best_result = None

    for lookback in range(min_days, max_days + 1):
        threshold = get_adaptive_threshold(data, lookback)
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
                    'threshold': threshold
                }

    if best_result:
        return best_result

    # Not sideways - return info for longest window
    threshold = get_adaptive_threshold(data, max_days)
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
            'threshold': threshold
        }

    return None


def analyze_phase(data, sideways_info):
    """Analyze accumulation vs distribution"""
    if not sideways_info:
        return None

    days = sideways_info['days']
    window = data[-days:]
    mid_price = (sideways_info['high'] + sideways_info['low']) / 2

    vol_lower = 0
    vol_upper = 0

    for d in window:
        if d['close'] < mid_price:
            vol_lower += d['volume']
        else:
            vol_upper += d['volume']

    vol_ratio = vol_lower / vol_upper if vol_upper > 0 else 1

    # Determine phase - Updated: Vol Ratio > 3.0 for ACCUMULATION
    if vol_ratio > 4.0:
        phase = 'ACCUMULATION'
    elif vol_ratio < 0.8:
        phase = 'DISTRIBUTION'
    elif vol_ratio > 1.5:
        phase = 'WEAK_ACCUMULATION'
    else:
        phase = 'NEUTRAL'

    return {
        'phase': phase,
        'vol_ratio': vol_ratio,
        'vol_lower': vol_lower,
        'vol_upper': vol_upper
    }


def check_entry_signal(data, sideways_info, phase_info):
    """Check entry signal with confirmations"""
    if not sideways_info or not phase_info:
        return None

    today = data[-1]
    comp_days = data[-6:-1] if len(data) >= 6 else data[:-1]

    # Position in range
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

    # Count confirmations
    score = 0
    if near_support:
        score += 1
    if today['change'] > 0.5 and close_pos > 0.6:
        score += 1
    if range_exp > 1.1:
        score += 1
    if vol_ratio > 1.2:
        score += 1

    # Risk Management
    stop_loss = sideways_info['low'] - (sideways_info['range'] * 0.02)
    target = sideways_info['high']

    risk_pct = (today['close'] - stop_loss) / today['close'] * 100
    reward_pct = (target - today['close']) / today['close'] * 100
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

    # Entry criteria
    is_accumulation = phase_info['phase'] == 'ACCUMULATION'

    confirmed = (
        sideways_info['is_sideways'] and
        is_accumulation and
        score >= 2 and
        near_support and
        rr_ratio >= 1.5
    )

    return {
        'confirmed': confirmed,
        'score': score,
        'pos_in_range': pos_in_range,
        'near_support': near_support,
        'is_accumulation': is_accumulation,
        'stop_loss': stop_loss,
        'target': target,
        'risk_pct': risk_pct,
        'reward_pct': reward_pct,
        'rr_ratio': rr_ratio
    }


def run_backtest(stock_code, start_from_days_ago=None):
    """
    Run backtest for stock with V6 formula
    """
    print(f"\n{'='*80}")
    print(f"BACKTEST V6 FORMULA - {stock_code}")
    print(f"{'='*80}")

    all_data = load_stock_data(stock_code)

    if len(all_data) < 100:
        print("Data tidak cukup untuk backtest (minimum 100 hari)")
        return

    print(f"Total data: {len(all_data)} hari ({all_data[0]['date']} - {all_data[-1]['date']})")

    # Start backtest from day 80 onwards (need history for calculation)
    start_idx = 80
    if start_from_days_ago:
        start_idx = max(80, len(all_data) - start_from_days_ago)

    trades = []
    current_position = None

    print(f"\nBacktest period: {all_data[start_idx]['date']} - {all_data[-1]['date']}")
    print(f"{'='*80}")

    for i in range(start_idx, len(all_data)):
        today = all_data[i]
        data_until_today = all_data[:i+1]

        # Check if we have an open position
        if current_position:
            # Check exit conditions
            hit_sl = today['low'] <= current_position['stop_loss']
            hit_tp = today['high'] >= current_position['target']

            if hit_sl or hit_tp:
                if hit_sl and hit_tp:
                    # Both hit - assume SL hit first if open < entry
                    exit_price = current_position['stop_loss'] if today['close'] < current_position['entry_price'] else current_position['target']
                    exit_type = 'SL' if today['close'] < current_position['entry_price'] else 'TP'
                elif hit_sl:
                    exit_price = current_position['stop_loss']
                    exit_type = 'SL'
                else:
                    exit_price = current_position['target']
                    exit_type = 'TP'

                pnl_pct = (exit_price - current_position['entry_price']) / current_position['entry_price'] * 100

                trade = {
                    'entry_date': current_position['entry_date'],
                    'entry_price': current_position['entry_price'],
                    'exit_date': today['date'],
                    'exit_price': exit_price,
                    'exit_type': exit_type,
                    'pnl_pct': pnl_pct,
                    'holding_days': (today['date'] - current_position['entry_date']).days,
                    'stop_loss': current_position['stop_loss'],
                    'target': current_position['target'],
                    'vol_ratio': current_position['vol_ratio'],
                    'score': current_position['score']
                }
                trades.append(trade)

                print(f"\n  EXIT [{exit_type}] {today['date']}")
                print(f"    Entry: Rp {current_position['entry_price']:,.0f} -> Exit: Rp {exit_price:,.0f}")
                print(f"    P&L: {pnl_pct:+.1f}% | Holding: {trade['holding_days']} days")

                current_position = None

        # Check for entry signal if no position
        if current_position is None:
            sideways = detect_sideways(data_until_today)
            if sideways:
                phase = analyze_phase(data_until_today, sideways)
                if phase:
                    entry = check_entry_signal(data_until_today, sideways, phase)

                    if entry and entry['confirmed']:
                        current_position = {
                            'entry_date': today['date'],
                            'entry_price': today['close'],
                            'stop_loss': entry['stop_loss'],
                            'target': entry['target'],
                            'vol_ratio': phase['vol_ratio'],
                            'score': entry['score']
                        }

                        print(f"\n  ENTRY {today['date']} @ Rp {today['close']:,.0f}")
                        print(f"    Sideways: {sideways['days']} hari | Phase: {phase['phase']} | Vol Ratio: {phase['vol_ratio']:.2f}")
                        print(f"    Score: {entry['score']}/4 | Pos: {entry['pos_in_range']*100:.0f}%")
                        print(f"    SL: Rp {entry['stop_loss']:,.0f} (-{entry['risk_pct']:.1f}%)")
                        print(f"    TP: Rp {entry['target']:,.0f} (+{entry['reward_pct']:.1f}%)")
                        print(f"    R:R: 1:{entry['rr_ratio']:.1f}")

    # Close any open position at last price
    if current_position:
        last_day = all_data[-1]
        pnl_pct = (last_day['close'] - current_position['entry_price']) / current_position['entry_price'] * 100

        trade = {
            'entry_date': current_position['entry_date'],
            'entry_price': current_position['entry_price'],
            'exit_date': last_day['date'],
            'exit_price': last_day['close'],
            'exit_type': 'OPEN',
            'pnl_pct': pnl_pct,
            'holding_days': (last_day['date'] - current_position['entry_date']).days,
            'stop_loss': current_position['stop_loss'],
            'target': current_position['target'],
            'vol_ratio': current_position['vol_ratio'],
            'score': current_position['score']
        }
        trades.append(trade)

        print(f"\n  OPEN POSITION (not closed)")
        print(f"    Entry: {current_position['entry_date']} @ Rp {current_position['entry_price']:,.0f}")
        print(f"    Current: Rp {last_day['close']:,.0f} | P&L: {pnl_pct:+.1f}%")

    # Summary
    print(f"\n{'='*80}")
    print("BACKTEST SUMMARY")
    print(f"{'='*80}")

    if not trades:
        print("Tidak ada trade yang dieksekusi")
        return

    total_trades = len(trades)
    closed_trades = [t for t in trades if t['exit_type'] != 'OPEN']

    if closed_trades:
        wins = [t for t in closed_trades if t['pnl_pct'] > 0]
        losses = [t for t in closed_trades if t['pnl_pct'] <= 0]

        win_rate = len(wins) / len(closed_trades) * 100

        total_pnl = sum(t['pnl_pct'] for t in closed_trades)
        avg_pnl = total_pnl / len(closed_trades)

        avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0

        avg_holding = sum(t['holding_days'] for t in closed_trades) / len(closed_trades)

        # Profit Factor
        gross_profit = sum(t['pnl_pct'] for t in wins) if wins else 0
        gross_loss = abs(sum(t['pnl_pct'] for t in losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        print(f"\nTotal Trades: {total_trades} (Closed: {len(closed_trades)}, Open: {total_trades - len(closed_trades)})")
        print(f"\n--- CLOSED TRADES ---")
        print(f"Win Rate: {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
        print(f"Total P&L: {total_pnl:+.1f}%")
        print(f"Avg P&L per Trade: {avg_pnl:+.1f}%")
        print(f"Avg Win: {avg_win:+.1f}% | Avg Loss: {avg_loss:+.1f}%")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Avg Holding Days: {avg_holding:.0f}")

        print(f"\n--- BY EXIT TYPE ---")
        tp_trades = [t for t in closed_trades if t['exit_type'] == 'TP']
        sl_trades = [t for t in closed_trades if t['exit_type'] == 'SL']
        print(f"Take Profit: {len(tp_trades)} trades ({len(tp_trades)/len(closed_trades)*100:.0f}%)")
        print(f"Stop Loss: {len(sl_trades)} trades ({len(sl_trades)/len(closed_trades)*100:.0f}%)")

    # List all trades
    print(f"\n--- TRADE LIST ---")
    print(f"{'No':<4} {'Entry Date':<12} {'Entry':>10} {'Exit Date':<12} {'Exit':>10} {'Type':<5} {'P&L':>8} {'Days':>5} {'VR':>5}")
    print("-" * 85)

    for i, t in enumerate(trades, 1):
        print(f"{i:<4} {str(t['entry_date']):<12} {t['entry_price']:>10,.0f} {str(t['exit_date']):<12} {t['exit_price']:>10,.0f} {t['exit_type']:<5} {t['pnl_pct']:>+7.1f}% {t['holding_days']:>5} {t['vol_ratio']:>5.2f}")

    return trades


if __name__ == "__main__":
    # Backtest NCKL
    run_backtest('NCKL')
