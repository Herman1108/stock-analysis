# -*- coding: utf-8 -*-
"""
SIGNAL HISTORY - V8 ATR-Quality Based
=====================================
Menggunakan V8 ATR-Quality method untuk S/R detection.
PENTING: Import fungsi dari strong_sr_v8_atr.py untuk konsistensi.

Metode V8:
1. ATR(14) untuk toleransi zona dinamis
2. Pivot detection (fractal 3 kiri 3 kanan)
3. Clustering level ke "bucket" berdasarkan tolerance
4. Filter: Touches >= 3, Quality >= 0.5
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import statistics
import math

# Import V8/V9 functions dari strong_sr_v8_atr untuk konsistensi
from strong_sr_v8_atr import (
    filter_data_1year,
    calculate_true_range,
    calculate_atr,
    calculate_tolerance,
    detect_pivots,
    cluster_levels,
    calculate_strength_score,
    get_strong_levels,
    get_nearest_sr,
    get_custom_sr_zones,
    calculate_vr as calculate_vr_v8,
    get_phase,
    backtest_v9
)


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


# ================== MAIN FUNCTIONS ==================
# Semua fungsi V8 (ATR, Pivot, Cluster, Strength, Phase) di-import dari strong_sr_v8_atr.py

def get_current_strong_sr(stock_code):
    """Get current Strong S/R levels using V8 ATR-Quality method (menggunakan fungsi dari strong_sr_v8_atr)"""
    conn = get_db_connection()
    try:
        data = get_stock_data(stock_code, conn)
        if not data or len(data) < 60:
            return None

        data_1year = filter_data_1year(data)
        if len(data_1year) < 30:
            data_1year = data

        # V8: Calculate ATR and tolerance (menggunakan fungsi dari strong_sr_v8_atr)
        tr_list = calculate_true_range(data_1year)
        atr_list = calculate_atr(tr_list)
        tol_price = calculate_tolerance(data_1year, atr_list)

        # V8: Get strong levels (menggunakan fungsi dari strong_sr_v8_atr)
        strong_supports, strong_resistances = get_strong_levels(data_1year, tol_price)

        current_price = float(data[-1]['close'])
        support, resistance = get_nearest_sr(strong_supports, strong_resistances, current_price)

        vr = None
        phase = None
        if support:
            vr = calculate_vr_v8(data, support['level'])
            phase = get_phase(vr)

        return {
            'method': 'V8_ATR_QUALITY',
            'tolerance': tol_price,
            'support': support['level'] if support else None,
            'support_touches': support['touches'] if support else 0,
            'support_quality': support['quality'] if support else 0,
            'resistance': resistance['level'] if resistance else None,
            'resistance_touches': resistance['touches'] if resistance else 0,
            'resistance_quality': resistance['quality'] if resistance else 0,
            'current_price': current_price,
            'vr': vr,
            'phase': phase
        }
    except Exception as e:
        print(f"Error getting Strong S/R for {stock_code}: {e}")
        return None
    finally:
        conn.close()


def get_signal_history_sr(stock_code, start_date='2025-01-02'):
    """
    Get signal history using V8 ATR-Quality S/R detection.
    Entry criteria: Near Support (<=5%), Phase Accumulation, Quality >= 50%, Touches >= 3
    """
    conn = get_db_connection()

    try:
        data = get_stock_data(stock_code, conn)
        if not data:
            return {'error': 'No data', 'signals': []}

        # Get custom formula
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM stock_formula WHERE stock_code = %s', (stock_code,))
        formula = cur.fetchone()

        if formula:
            sl_pct = float(formula.get('stop_loss_pct', 5.0)) / 100
            tp_pct = float(formula.get('take_profit_pct', 2.0)) / 100
            valid_phases = formula.get('valid_phases') or ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']
        else:
            sl_pct = 0.05
            tp_pct = 0.02
            valid_phases = ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION']

        # V8: Filter data 1 tahun dan hitung ATR/tolerance (menggunakan fungsi dari strong_sr_v8_atr)
        data_1year = filter_data_1year(data)
        if len(data_1year) < 30:
            data_1year = data

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
            # V8: Get strong levels dengan fungsi dari strong_sr_v8_atr untuk konsistensi
            strong_supports, strong_resistances = get_strong_levels(data_1year, tol_price)

        if not strong_supports:
            return {
                'summary': {
                    'stock_code': stock_code,
                    'method': 'V8_ATR_QUALITY',
                    'error': 'No strong support found (Quality < 50% or Touches < 3)',
                    'total_signals': 0,
                    'closed_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0,
                    'total_pnl': 0
                },
                'signals': []
            }

        signals = []
        position = None

        # Find start index
        start_idx = 60
        for i, d in enumerate(data):
            if str(d['date']) >= start_date and i >= 60:
                start_idx = i
                break

        for i in range(start_idx, len(data)):
            price = float(data[i]['close'])
            support, resistance = get_nearest_sr(strong_supports, strong_resistances, price)

            if position is None:
                if support:
                    dist = (price - support['level']) / price * 100
                    if dist <= 5.0:  # Within 5% of support
                        # Gunakan calculate_vr_v8 dari strong_sr_v8_atr dengan data slice
                        vr = calculate_vr_v8(data[:i+1], support['level'])
                        phase = get_phase(vr)

                        # V8 Entry: Phase valid + Quality >= 50% + Touches >= 3
                        if phase in valid_phases and support['quality'] >= 0.5 and support['touches'] >= 3:
                            if i + 1 < len(data):
                                next_day = data[i + 1]
                                entry_price = float(next_day['open'])
                                sl = support['level'] * (1 - sl_pct)
                                tp = resistance['level'] * (1 - tp_pct) if resistance else entry_price * 1.15

                                # PENTING: Jangan entry jika entry_price >= target (tidak ada upside)
                                if entry_price >= tp:
                                    continue  # Skip entry, tidak ada potensi profit

                                position = {
                                    'signal_date': data[i]['date'],
                                    'entry_date': next_day['date'],
                                    'entry_price': entry_price,
                                    'support': support['level'],
                                    'support_quality': support['quality'],
                                    'support_touches': support['touches'],
                                    'resistance': resistance['level'] if resistance else None,
                                    'stop_loss': sl,
                                    'target': tp,
                                    'phase': phase,
                                    'vr': vr,
                                    'tolerance': tol_price
                                }
            else:
                # Check exit conditions
                exit_reason = None

                if price <= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                elif price >= position['target']:
                    exit_reason = 'TARGET'

                if exit_reason:
                    pnl = (price - position['entry_price']) / position['entry_price'] * 100
                    signals.append({
                        **position,
                        'exit_date': data[i]['date'],
                        'exit_price': price,
                        'exit_reason': exit_reason,
                        'pnl': pnl,
                        'result': 'WIN' if pnl > 0 else 'LOSS',
                        'days_held': (data[i]['date'] - position['entry_date']).days
                    })
                    position = None

        # If still in position
        if position:
            last = data[-1]
            pnl = (float(last['close']) - position['entry_price']) / position['entry_price'] * 100
            signals.append({
                **position,
                'exit_date': last['date'],
                'exit_price': float(last['close']),
                'exit_reason': 'OPEN',
                'pnl': pnl,
                'result': 'OPEN',
                'days_held': (last['date'] - position['entry_date']).days
            })

        # Summary
        closed = [s for s in signals if s['exit_reason'] != 'OPEN']
        wins = [s for s in closed if s['pnl'] > 0]
        losses = [s for s in closed if s['pnl'] <= 0]

        summary = {
            'stock_code': stock_code,
            'method': 'V8_ATR_QUALITY',
            'period': f"{start_date} - sekarang",
            'tolerance': tol_price,
            'total_signals': len(signals),
            'closed_trades': len(closed),
            'open_trades': len(signals) - len(closed),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(closed) * 100 if closed else 0,
            'total_pnl': sum(s['pnl'] for s in closed),
            'avg_pnl': sum(s['pnl'] for s in closed) / len(closed) if closed else 0,
            'by_exit': {},
            'by_phase': {}
        }

        # Group by exit reason
        for s in closed:
            reason = s['exit_reason']
            if reason not in summary['by_exit']:
                summary['by_exit'][reason] = {'count': 0, 'pnl': 0, 'wins': 0}
            summary['by_exit'][reason]['count'] += 1
            summary['by_exit'][reason]['pnl'] += s['pnl']
            if s['pnl'] > 0:
                summary['by_exit'][reason]['wins'] += 1

        # Group by phase
        for s in closed:
            phase = s['phase']
            if phase not in summary['by_phase']:
                summary['by_phase'][phase] = {'count': 0, 'pnl': 0, 'wins': 0}
            summary['by_phase'][phase]['count'] += 1
            summary['by_phase'][phase]['pnl'] += s['pnl']
            if s['pnl'] > 0:
                summary['by_phase'][phase]['wins'] += 1

        return {
            'summary': summary,
            'signals': signals
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'signals': []}
    finally:
        conn.close()


def get_signal_history_v9(stock_code, start_date='2025-01-02'):
    """
    Get signal history using V9 Retest Pattern.
    Converts backtest_v9 output to signal_history format.
    """
    result = backtest_v9(stock_code, start_date)

    if result.get('error'):
        return {
            'summary': {
                'stock_code': stock_code,
                'method': 'V9_RETEST_PATTERN',
                'error': result['error'],
                'total_signals': 0,
                'closed_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_pnl': 0
            },
            'signals': []
        }

    # Convert trades to signals format
    signals = []
    for t in result.get('trades', []):
        signals.append({
            'signal_date': t.get('signal_date'),
            'entry_date': t.get('entry_date'),
            'entry_price': t.get('entry_price'),
            'support': t.get('support'),
            'support_quality': t.get('support_quality', 1.0),
            'support_touches': t.get('support_touches', 99),
            'resistance': t.get('resistance'),
            'resistance_touched_date': t.get('resistance_touched_date'),
            'stop_loss': t.get('stop_loss'),
            'target': t.get('target'),
            'phase': t.get('phase'),
            'vr': t.get('vr'),
            'exit_date': t.get('exit_date'),
            'exit_price': t.get('exit_price'),
            'exit_reason': t.get('exit_reason'),
            'pnl': t.get('pnl'),
            'result': t.get('result'),
            'days_held': t.get('days_held')
        })

    # Build summary
    closed = [s for s in signals if s['exit_reason'] != 'OPEN']
    wins = [s for s in closed if s['pnl'] > 0]
    losses = [s for s in closed if s['pnl'] <= 0]

    summary = {
        'stock_code': stock_code,
        'method': 'V9_RETEST_PATTERN',
        'period': f"{start_date} - sekarang",
        'total_signals': len(signals),
        'closed_trades': len(closed),
        'open_trades': len(signals) - len(closed),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(closed) * 100 if closed else 0,
        'total_pnl': sum(s['pnl'] for s in closed),
        'avg_pnl': sum(s['pnl'] for s in closed) / len(closed) if closed else 0,
        'by_exit': {},
        'by_phase': {}
    }

    # Group by exit reason
    for s in closed:
        reason = s['exit_reason']
        if reason not in summary['by_exit']:
            summary['by_exit'][reason] = {'count': 0, 'pnl': 0, 'wins': 0}
        summary['by_exit'][reason]['count'] += 1
        summary['by_exit'][reason]['pnl'] += s['pnl']
        if s['pnl'] > 0:
            summary['by_exit'][reason]['wins'] += 1

    # Group by phase
    for s in closed:
        phase = s['phase']
        if phase not in summary['by_phase']:
            summary['by_phase'][phase] = {'count': 0, 'pnl': 0, 'wins': 0}
        summary['by_phase'][phase]['count'] += 1
        summary['by_phase'][phase]['pnl'] += s['pnl']
        if s['pnl'] > 0:
            summary['by_phase'][phase]['wins'] += 1

    return {
        'summary': summary,
        'signals': signals
    }


def get_signal_history_auto(stock_code, start_date='2025-01-02'):
    """
    Auto-select V8 or V9 based on whether stock has custom S/R zones.
    - V9 (Retest Pattern): untuk stock dengan custom zones
    - V8 (ATR-Quality): untuk stock tanpa custom zones
    """
    conn = get_db_connection()
    try:
        custom_supports, custom_resistances = get_custom_sr_zones(stock_code, conn)

        if custom_supports and custom_resistances:
            # Use V9 for stocks with custom zones
            conn.close()
            return get_signal_history_v9(stock_code, start_date)
        else:
            # Use V8 for stocks without custom zones
            conn.close()
            return get_signal_history_sr(stock_code, start_date)
    except:
        conn.close()
        return get_signal_history_sr(stock_code, start_date)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    for stock in ['PTRO', 'CBDK', 'BREN', 'BRPT', 'CDIA']:
        print('='*80)
        print(f'RIWAYAT SINYAL {stock} (V8 ATR-Quality)')
        print('='*80)

        result = get_signal_history_sr(stock, '2025-01-02')

        if result.get('error'):
            print(f'Error: {result["error"]}')
            continue

        s = result['summary']
        signals = result['signals']

        print(f"""
RINGKASAN:
  Method      : {s.get('method', 'N/A')}
  Tolerance   : Rp {s.get('tolerance', 0):,.0f}
  Periode     : {s.get('period', 'N/A')}
  Total Sinyal: {s['total_signals']}
  Closed      : {s['closed_trades']}
  Open        : {s['open_trades']}
  Wins        : {s['wins']}
  Losses      : {s['losses']}
  Win Rate    : {s['win_rate']:.1f}%
  Total PnL   : {s['total_pnl']:+.2f}%
  Avg PnL     : {s.get('avg_pnl', 0):+.2f}%
""")

        if s.get('by_phase'):
            print("BY PHASE:")
            for phase, data in s['by_phase'].items():
                wr = data['wins']/data['count']*100 if data['count'] else 0
                print(f"  {phase}: {data['count']} trades, WR: {wr:.0f}%, PnL: {data['pnl']:+.2f}%")

        if s.get('by_exit'):
            print("\nBY EXIT REASON:")
            for reason, data in s['by_exit'].items():
                print(f"  {reason}: {data['count']} trades, PnL: {data['pnl']:+.2f}%")

        if signals:
            print("\nDETAIL SINYAL:")
            print("-"*80)
            for i, sig in enumerate(signals, 1):
                icon = '+' if sig['pnl'] > 0 else '-' if sig['exit_reason'] != 'OPEN' else '*'
                vr_str = f"{sig['vr']:.1f}x" if sig['vr'] < 100 else '999x'
                q_str = f"{sig['support_quality']:.0%}" if sig.get('support_quality') else 'N/A'
                print(f"{icon}{i}. {str(sig['entry_date'])[:10]} Entry @ Rp {sig['entry_price']:,.0f} | {sig['phase']} (VR:{vr_str}, Q:{q_str})")
                print(f"    {str(sig['exit_date'])[:10]} Exit  @ Rp {sig['exit_price']:,.0f} | {sig['exit_reason']} | PnL: {sig['pnl']:+.2f}%")
                print()
