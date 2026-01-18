# -*- coding: utf-8 -*-
"""
Analisis Volume: RETEST vs BREAKOUT
Apakah RETEST seharusnya volume rendah? BREAKOUT volume tinggi?
"""

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

from backtest_v11_universal import run_backtest, V11_PARAMS, STOCK_ZONES
import statistics


def analyze():
    print('=' * 100)
    print('ANALISIS VOLUME: RETEST vs BREAKOUT')
    print('Apakah RETEST seharusnya volume rendah? BREAKOUT volume tinggi?')
    print('=' * 100)

    # Run with NO filter to get all trades
    no_filter_params = {
        'vol_lookback': 20,
        'min_vol_ratio': 0,  # No filter
        'use_rsi_filter': False,
        'rsi_period': 14,
        'max_rsi': 100
    }

    all_trades = []

    for stock in sorted(STOCK_ZONES.keys()):
        result = run_backtest(stock, v11_params=no_filter_params)
        if result:
            for t in result['trades']:
                if t['exit_reason'] != 'OPEN':
                    t['stock_code'] = result['stock_code']
                    all_trades.append(t)

    # Separate by entry type
    retest_trades = [t for t in all_trades if t['type'] == 'RETEST']
    breakout_trades = [t for t in all_trades if t['type'] in ['BO_HOLD', 'BO_PULLBACK']]

    # ================================================================
    # RETEST ANALYSIS
    # ================================================================
    print()
    print('=' * 100)
    print('1. ANALISIS RETEST TRADES')
    print('=' * 100)

    retest_win = [t for t in retest_trades if t['pnl'] > 0]
    retest_loss = [t for t in retest_trades if t['pnl'] <= 0]

    print(f"""
Total RETEST: {len(retest_trades)}
  - WIN : {len(retest_win)} ({len(retest_win)/len(retest_trades)*100:.1f}%)
  - LOSS: {len(retest_loss)} ({len(retest_loss)/len(retest_trades)*100:.1f}%)
""")

    retest_win_vol = [t['vol_ratio'] for t in retest_win if t.get('vol_ratio')]
    retest_loss_vol = [t['vol_ratio'] for t in retest_loss if t.get('vol_ratio')]

    if retest_win_vol and retest_loss_vol:
        print('Volume Ratio Analysis (RETEST):')
        print(f'  WIN  - Mean: {statistics.mean(retest_win_vol):.2f}x, Median: {statistics.median(retest_win_vol):.2f}x, Min: {min(retest_win_vol):.2f}x, Max: {max(retest_win_vol):.2f}x')
        print(f'  LOSS - Mean: {statistics.mean(retest_loss_vol):.2f}x, Median: {statistics.median(retest_loss_vol):.2f}x, Min: {min(retest_loss_vol):.2f}x, Max: {max(retest_loss_vol):.2f}x')
        print()

    print('Detail RETEST WIN (sorted by PnL):')
    print(f"{'#':<3} {'Stock':<6} {'Date':<12} {'Vol':>8} {'PnL':>10} {'Exit':<10}")
    print('-' * 55)
    for i, t in enumerate(sorted(retest_win, key=lambda x: -x['pnl']), 1):
        vol = f"{t.get('vol_ratio', 0):.2f}x" if t.get('vol_ratio') else 'N/A'
        print(f"{i:<3} {t['stock_code']:<6} {t['entry_date']:<12} {vol:>8} {t['pnl']:>+9.1f}% {t['exit_reason']:<10}")

    print()
    print('Detail RETEST LOSS (sorted by PnL):')
    print(f"{'#':<3} {'Stock':<6} {'Date':<12} {'Vol':>8} {'PnL':>10} {'Exit':<10}")
    print('-' * 55)
    for i, t in enumerate(sorted(retest_loss, key=lambda x: x['pnl']), 1):
        vol = f"{t.get('vol_ratio', 0):.2f}x" if t.get('vol_ratio') else 'N/A'
        print(f"{i:<3} {t['stock_code']:<6} {t['entry_date']:<12} {vol:>8} {t['pnl']:>+9.1f}% {t['exit_reason']:<10}")

    # ================================================================
    # BREAKOUT ANALYSIS
    # ================================================================
    print()
    print('=' * 100)
    print('2. ANALISIS BREAKOUT TRADES')
    print('=' * 100)

    bo_win = [t for t in breakout_trades if t['pnl'] > 0]
    bo_loss = [t for t in breakout_trades if t['pnl'] <= 0]

    print(f"""
Total BREAKOUT: {len(breakout_trades)}
  - WIN : {len(bo_win)} ({len(bo_win)/len(breakout_trades)*100:.1f}% if breakout_trades else 0)
  - LOSS: {len(bo_loss)} ({len(bo_loss)/len(breakout_trades)*100:.1f}% if breakout_trades else 0)
""")

    bo_win_vol = [t['vol_ratio'] for t in bo_win if t.get('vol_ratio')]
    bo_loss_vol = [t['vol_ratio'] for t in bo_loss if t.get('vol_ratio')]

    if bo_win_vol:
        print('Volume Ratio Analysis (BREAKOUT):')
        print(f'  WIN  - Mean: {statistics.mean(bo_win_vol):.2f}x, Median: {statistics.median(bo_win_vol):.2f}x, Min: {min(bo_win_vol):.2f}x, Max: {max(bo_win_vol):.2f}x')
        if bo_loss_vol:
            print(f'  LOSS - Mean: {statistics.mean(bo_loss_vol):.2f}x, Median: {statistics.median(bo_loss_vol):.2f}x, Min: {min(bo_loss_vol):.2f}x, Max: {max(bo_loss_vol):.2f}x')
        else:
            print('  LOSS - No data (semua BREAKOUT WIN!)')
        print()

    print('Detail BREAKOUT WIN (sorted by PnL):')
    print(f"{'#':<3} {'Stock':<6} {'Type':<12} {'Date':<12} {'Vol':>8} {'PnL':>10}")
    print('-' * 60)
    for i, t in enumerate(sorted(bo_win, key=lambda x: -x['pnl']), 1):
        vol = f"{t.get('vol_ratio', 0):.2f}x" if t.get('vol_ratio') else 'N/A'
        print(f"{i:<3} {t['stock_code']:<6} {t['type']:<12} {t['entry_date']:<12} {vol:>8} {t['pnl']:>+9.1f}%")

    if bo_loss:
        print()
        print('Detail BREAKOUT LOSS (sorted by PnL):')
        print(f"{'#':<3} {'Stock':<6} {'Type':<12} {'Date':<12} {'Vol':>8} {'PnL':>10}")
        print('-' * 60)
        for i, t in enumerate(sorted(bo_loss, key=lambda x: x['pnl']), 1):
            vol = f"{t.get('vol_ratio', 0):.2f}x" if t.get('vol_ratio') else 'N/A'
            print(f"{i:<3} {t['stock_code']:<6} {t['type']:<12} {t['entry_date']:<12} {vol:>8} {t['pnl']:>+9.1f}%")

    # ================================================================
    # THRESHOLD ANALYSIS
    # ================================================================
    print()
    print('=' * 100)
    print('3. VOLUME THRESHOLD ANALYSIS BY ENTRY TYPE')
    print('=' * 100)

    # RETEST - Volume >= threshold
    print()
    print('RETEST - Jika filter Vol >= threshold:')
    print(f"{'Threshold':<15} {'WIN':>8} {'LOSS':>8} {'Total':>8} {'WinRate':>10} {'vs Base':>10}")
    print('-' * 65)
    base_wr = len(retest_win) / len(retest_trades) * 100 if retest_trades else 0
    for threshold in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
        win_above = len([t for t in retest_win if t.get('vol_ratio') and t['vol_ratio'] >= threshold])
        loss_above = len([t for t in retest_loss if t.get('vol_ratio') and t['vol_ratio'] >= threshold])
        total = win_above + loss_above
        wr = win_above / total * 100 if total else 0
        diff = wr - base_wr
        print(f"Vol >= {threshold:.1f}x      {win_above:>8} {loss_above:>8} {total:>8} {wr:>9.1f}% {diff:>+9.1f}%")

    # RETEST - Volume < threshold (LOW volume filter)
    print()
    print('RETEST - Jika filter Vol < threshold (RENDAH):')
    print(f"{'Threshold':<15} {'WIN':>8} {'LOSS':>8} {'Total':>8} {'WinRate':>10} {'vs Base':>10}")
    print('-' * 65)
    for threshold in [0.8, 1.0, 1.2, 1.5, 2.0]:
        win_below = len([t for t in retest_win if t.get('vol_ratio') and t['vol_ratio'] < threshold])
        loss_below = len([t for t in retest_loss if t.get('vol_ratio') and t['vol_ratio'] < threshold])
        total = win_below + loss_below
        wr = win_below / total * 100 if total else 0
        diff = wr - base_wr
        print(f"Vol < {threshold:.1f}x       {win_below:>8} {loss_below:>8} {total:>8} {wr:>9.1f}% {diff:>+9.1f}%")

    # BREAKOUT - Volume >= threshold
    print()
    print('BREAKOUT - Jika filter Vol >= threshold:')
    print(f"{'Threshold':<15} {'WIN':>8} {'LOSS':>8} {'Total':>8} {'WinRate':>10}")
    print('-' * 55)
    for threshold in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
        win_above = len([t for t in bo_win if t.get('vol_ratio') and t['vol_ratio'] >= threshold])
        loss_above = len([t for t in bo_loss if t.get('vol_ratio') and t['vol_ratio'] >= threshold])
        total = win_above + loss_above
        wr = win_above / total * 100 if total else 0
        print(f"Vol >= {threshold:.1f}x      {win_above:>8} {loss_above:>8} {total:>8} {wr:>9.1f}%")

    # ================================================================
    # KESIMPULAN
    # ================================================================
    print()
    print('=' * 100)
    print('4. KESIMPULAN & REKOMENDASI')
    print('=' * 100)

    print()
    print('RETEST Analysis:')
    if retest_win_vol and retest_loss_vol:
        retest_win_mean = statistics.mean(retest_win_vol)
        retest_loss_mean = statistics.mean(retest_loss_vol)
        print(f'  WIN  avg volume: {retest_win_mean:.2f}x')
        print(f'  LOSS avg volume: {retest_loss_mean:.2f}x')
        if retest_win_mean > retest_loss_mean:
            print(f'  --> RETEST WIN cenderung punya volume LEBIH TINGGI')
            print(f'  --> Hipotesis "RETEST harus volume rendah" TIDAK TERBUKTI')
        else:
            print(f'  --> RETEST WIN cenderung punya volume LEBIH RENDAH')
            print(f'  --> Hipotesis "RETEST harus volume rendah" TERBUKTI')

    print()
    print('BREAKOUT Analysis:')
    if bo_win_vol:
        bo_win_mean = statistics.mean(bo_win_vol)
        print(f'  WIN avg volume: {bo_win_mean:.2f}x')
        if bo_loss_vol:
            bo_loss_mean = statistics.mean(bo_loss_vol)
            print(f'  LOSS avg volume: {bo_loss_mean:.2f}x')
            if bo_win_mean > bo_loss_mean:
                print(f'  --> BREAKOUT WIN cenderung punya volume LEBIH TINGGI')
                print(f'  --> Filter "BREAKOUT harus volume tinggi" VALID')
            else:
                print(f'  --> BREAKOUT WIN cenderung punya volume LEBIH RENDAH')
        else:
            print(f'  --> Semua BREAKOUT adalah WIN!')

    print()
    print('=' * 100)
    print('REKOMENDASI FILTER V11c (berdasarkan data):')
    print('=' * 100)


if __name__ == '__main__':
    analyze()
