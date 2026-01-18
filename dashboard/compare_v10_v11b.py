# -*- coding: utf-8 -*-
"""
Perbandingan V10 vs V11b (Volume >= 1.0x TANPA RSI Filter)
"""

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

from backtest_v10_universal import run_backtest as run_v10, STOCK_ZONES
from backtest_v11_universal import run_backtest as run_v11, V11_PARAMS


def compare():
    print('=' * 110)
    print('PERBANDINGAN V10 vs V11b (Volume >= 1.0x TANPA RSI Filter)')
    print('=' * 110)

    # V11b params - no RSI filter
    v11b_params = V11_PARAMS.copy()
    v11b_params['use_rsi_filter'] = False

    v10_results = []
    v11b_results = []

    for stock_code in sorted(STOCK_ZONES.keys()):
        v10 = run_v10(stock_code)
        v11b = run_v11(stock_code, v11_params=v11b_params)
        if v10:
            v10_results.append(v10)
        if v11b:
            v11b_results.append(v11b)

    # Collect all trades for detailed comparison
    all_v10_trades = []
    all_v11b_trades = []
    all_filtered = []

    for r in v10_results:
        for t in r['trades']:
            t['stock_code'] = r['stock_code']
            if t['exit_reason'] != 'OPEN':
                all_v10_trades.append(t)

    for r in v11b_results:
        for t in r['trades']:
            t['stock_code'] = r['stock_code']
            if t['exit_reason'] != 'OPEN':
                all_v11b_trades.append(t)
        for f in r.get('filtered_entries', []):
            f['stock_code'] = r['stock_code']
            all_filtered.append(f)

    # Per-stock comparison
    print()
    print('=' * 110)
    print('PERBANDINGAN PER SAHAM')
    print('=' * 110)
    print(f"\n{'Stock':<8} {'------- V10 -------':^30} {'------ V11b ------':^30} {'Improvement':^15}")
    print(f"{'':8} {'Trades':>8} {'WR':>8} {'PnL':>12} {'Trades':>8} {'WR':>8} {'PnL':>12} {'WR':>8} {'PnL':>10}")
    print('-' * 110)

    total_v10_trades = 0
    total_v10_wins = 0
    total_v10_pnl = 0
    total_v11_trades = 0
    total_v11_wins = 0
    total_v11_pnl = 0
    total_filtered = 0

    for stock in sorted(STOCK_ZONES.keys()):
        v10 = next((r for r in v10_results if r['stock_code'] == stock), None)
        v11 = next((r for r in v11b_results if r['stock_code'] == stock), None)

        if v10 and v11:
            v10_closed = [t for t in v10['trades'] if t['exit_reason'] != 'OPEN']
            v10_wins = len([t for t in v10_closed if t['pnl'] > 0])
            v10_pnl = sum(t['pnl'] for t in v10_closed)
            v10_wr = v10_wins / len(v10_closed) * 100 if v10_closed else 0

            v11_closed = [t for t in v11['trades'] if t['exit_reason'] != 'OPEN']
            v11_wins = len([t for t in v11_closed if t['pnl'] > 0])
            v11_pnl = sum(t['pnl'] for t in v11_closed)
            v11_wr = v11_wins / len(v11_closed) * 100 if v11_closed else 0

            filtered = len(v11.get('filtered_entries', []))

            wr_diff = v11_wr - v10_wr
            pnl_diff = v11_pnl - v10_pnl

            total_v10_trades += len(v10_closed)
            total_v10_wins += v10_wins
            total_v10_pnl += v10_pnl
            total_v11_trades += len(v11_closed)
            total_v11_wins += v11_wins
            total_v11_pnl += v11_pnl
            total_filtered += filtered

            wr_sign = '+' if wr_diff > 0 else ''
            pnl_sign = '+' if pnl_diff > 0 else ''
            print(f"{stock:<8} {len(v10_closed):>8} {v10_wr:>7.1f}% {v10_pnl:>+11.1f}% {len(v11_closed):>8} {v11_wr:>7.1f}% {v11_pnl:>+11.1f}% {wr_sign}{wr_diff:>7.1f}% {pnl_sign}{pnl_diff:>9.1f}%")

    print('-' * 110)
    total_v10_wr = total_v10_wins / total_v10_trades * 100 if total_v10_trades else 0
    total_v11_wr = total_v11_wins / total_v11_trades * 100 if total_v11_trades else 0
    wr_diff = total_v11_wr - total_v10_wr
    pnl_diff = total_v11_pnl - total_v10_pnl
    wr_sign = '+' if wr_diff > 0 else ''
    pnl_sign = '+' if pnl_diff > 0 else ''
    print(f"{'TOTAL':<8} {total_v10_trades:>8} {total_v10_wr:>7.1f}% {total_v10_pnl:>+11.1f}% {total_v11_trades:>8} {total_v11_wr:>7.1f}% {total_v11_pnl:>+11.1f}% {wr_sign}{wr_diff:>7.1f}% {pnl_sign}{pnl_diff:>9.1f}%")

    # Summary boxes
    print()
    print('=' * 110)
    print('RINGKASAN PERBANDINGAN')
    print('=' * 110)

    avg_v10 = total_v10_pnl / total_v10_trades if total_v10_trades else 0
    avg_v11 = total_v11_pnl / total_v11_trades if total_v11_trades else 0
    avg_sign = '+' if avg_v11 - avg_v10 > 0 else ''

    print(f'''
+------------------------------------------+------------------------------------------+
|              FORMULA V10                 |         FORMULA V11b (Vol Only)          |
+------------------------------------------+------------------------------------------+
|  Total Trades    : {total_v10_trades:>5}                  |  Total Trades    : {total_v11_trades:>5}                  |
|  Wins            : {total_v10_wins:>5}                  |  Wins            : {total_v11_wins:>5}                  |
|  Losses          : {total_v10_trades - total_v10_wins:>5}                  |  Losses          : {total_v11_trades - total_v11_wins:>5}                  |
|  Win Rate        : {total_v10_wr:>5.1f}%                |  Win Rate        : {total_v11_wr:>5.1f}%                |
|  Total PnL       : {total_v10_pnl:>+6.1f}%               |  Total PnL       : {total_v11_pnl:>+6.1f}%               |
|  Avg PnL/Trade   : {avg_v10:>+6.2f}%               |  Avg PnL/Trade   : {avg_v11:>+6.2f}%               |
|                                          |  Filtered        : {total_filtered:>5}                  |
+------------------------------------------+------------------------------------------+

IMPROVEMENT V11b vs V10:
  - Win Rate       : {wr_sign}{wr_diff:.1f}% ({total_v10_wr:.1f}% -> {total_v11_wr:.1f}%)
  - Total PnL      : {pnl_sign}{pnl_diff:.1f}%
  - Avg PnL/Trade  : {avg_sign}{avg_v11 - avg_v10:.2f}% ({avg_v10:.2f}% -> {avg_v11:.2f}%)
  - Trades Filtered: {total_filtered} ({total_filtered/total_v10_trades*100 if total_v10_trades else 0:.1f}% of V10 signals)
''')

    # Detail: What trades were filtered and their V10 outcome
    print('=' * 110)
    print('DETAIL TRADE YANG DI-FILTER V11b')
    print('=' * 110)

    # Find V10 outcome for each filtered entry
    print()
    print('Mencari outcome V10 untuk setiap entry yang di-filter...')
    print()

    filtered_would_win = []
    filtered_would_lose = []

    for f in all_filtered:
        # Find matching V10 trade
        v10_match = None
        for t in all_v10_trades:
            if t['stock_code'] == f['stock_code'] and t['entry_date'] == f['date'] and t['type'] == f['type']:
                v10_match = t
                break

        if v10_match:
            f['v10_outcome'] = 'WIN' if v10_match['pnl'] > 0 else 'LOSS'
            f['v10_pnl'] = v10_match['pnl']
            f['v10_exit_reason'] = v10_match['exit_reason']
            if v10_match['pnl'] > 0:
                filtered_would_win.append(f)
            else:
                filtered_would_lose.append(f)
        else:
            f['v10_outcome'] = 'N/A'
            f['v10_pnl'] = 0
            f['v10_exit_reason'] = 'N/A'

    print(f'Total Filtered: {len(all_filtered)}')
    print(f'  - Would be WIN in V10 : {len(filtered_would_win)} (MISSED OPPORTUNITIES)')
    print(f'  - Would be LOSS in V10: {len(filtered_would_lose)} (AVOIDED LOSSES)')
    print()

    # Show filtered that would have been losses (good filter)
    if filtered_would_lose:
        print('AVOIDED LOSSES (Filter Berhasil Menghindari Kerugian):')
        print(f"{'#':<3} {'Stock':<6} {'Type':<12} {'Date':<12} {'Vol':>8} {'V10 PnL':>10} {'V10 Exit':<10}")
        print('-' * 70)
        for idx, f in enumerate(sorted(filtered_would_lose, key=lambda x: x['v10_pnl']), 1):
            vol = f"{f.get('vol_ratio', 0):.2f}x" if f.get('vol_ratio') else 'N/A'
            print(f"{idx:<3} {f['stock_code']:<6} {f['type']:<12} {f['date']:<12} {vol:>8} {f['v10_pnl']:>+9.1f}% {f['v10_exit_reason']:<10}")

        total_avoided_loss = sum(f['v10_pnl'] for f in filtered_would_lose)
        print(f'                                              Total: {total_avoided_loss:>+9.1f}%')
    else:
        total_avoided_loss = 0
        print('AVOIDED LOSSES: Tidak ada')

    print()

    if filtered_would_win:
        print('MISSED OPPORTUNITIES (Trade Bagus yang Ter-filter):')
        print(f"{'#':<3} {'Stock':<6} {'Type':<12} {'Date':<12} {'Vol':>8} {'V10 PnL':>10} {'V10 Exit':<10}")
        print('-' * 70)
        for idx, f in enumerate(sorted(filtered_would_win, key=lambda x: -x['v10_pnl']), 1):
            vol = f"{f.get('vol_ratio', 0):.2f}x" if f.get('vol_ratio') else 'N/A'
            print(f"{idx:<3} {f['stock_code']:<6} {f['type']:<12} {f['date']:<12} {vol:>8} {f['v10_pnl']:>+9.1f}% {f['v10_exit_reason']:<10}")

        total_missed = sum(f['v10_pnl'] for f in filtered_would_win)
        print(f'                                              Total: {total_missed:>+9.1f}%')
    else:
        total_missed = 0
        print('MISSED OPPORTUNITIES: Tidak ada')

    print()
    print('=' * 110)
    print('DETAIL SEMUA TRADE V11b (sorted by PnL)')
    print('=' * 110)
    print(f"{'#':<3} {'Stock':<6} {'Type':<12} {'Entry':<12} {'Exit':<12} {'Result':<8} {'PnL':>10} {'Vol':>8}")
    print('-' * 85)
    for idx, t in enumerate(sorted(all_v11b_trades, key=lambda x: -x['pnl']), 1):
        vol = f"{t.get('vol_ratio', 0):.1f}x" if t.get('vol_ratio') else 'N/A'
        result = 'WIN' if t['pnl'] > 0 else 'LOSS'
        print(f"{idx:<3} {t['stock_code']:<6} {t['type']:<12} {t['entry_date']:<12} {t['exit_date']:<12} {result:<8} {t['pnl']:>+9.1f}% {vol:>8}")

    print()
    print('=' * 110)
    print('KESIMPULAN V11b (Volume >= 1.0x tanpa RSI)')
    print('=' * 110)

    net_filter_effect = abs(total_avoided_loss) - total_missed
    print(f'''
Filter Analysis:

  Avoided Losses : {abs(total_avoided_loss):>+.1f}% (dari {len(filtered_would_lose)} trade yang akan rugi)
  Missed Wins    : {total_missed:>+.1f}% (dari {len(filtered_would_win)} trade yang akan untung)
  ---------------
  Net Effect     : {'+' if net_filter_effect > 0 else ''}{net_filter_effect:.1f}%

Performance Comparison:

  Metric              V10          V11b         Change
  ---------------------------------------------------------
  Win Rate         {total_v10_wr:>6.1f}%       {total_v11_wr:>6.1f}%       {wr_sign}{wr_diff:>6.1f}%
  Total PnL       {total_v10_pnl:>+7.1f}%      {total_v11_pnl:>+7.1f}%      {pnl_sign}{pnl_diff:>6.1f}%
  Avg PnL/Trade   {avg_v10:>+7.2f}%      {avg_v11:>+7.2f}%      {avg_sign}{avg_v11 - avg_v10:>6.2f}%
  Trades             {total_v10_trades:>5}          {total_v11_trades:>5}          {total_v11_trades - total_v10_trades:>+5}
''')

    # Final verdict
    print('=' * 110)
    print('VERDICT')
    print('=' * 110)

    if wr_diff > 5 and avg_v11 > avg_v10:
        print('''
  ✅ V11b RECOMMENDED

  - Win Rate meningkat signifikan (+{:.1f}%)
  - Avg PnL per trade meningkat (+{:.2f}%)
  - Filter volume efektif mengurangi loss trades

  Trade-off: Total PnL lebih rendah karena jumlah trade berkurang,
             tapi KUALITAS trade lebih baik.
'''.format(wr_diff, avg_v11 - avg_v10))
    elif wr_diff > 0:
        print('''
  ⚠️ V11b MARGINAL IMPROVEMENT

  - Win Rate naik sedikit (+{:.1f}%)
  - Filter mungkin terlalu ketat atau kurang tepat
'''.format(wr_diff))
    else:
        print('''
  ❌ V11b NOT RECOMMENDED

  - Win Rate tidak meningkat atau malah turun
  - Filter tidak efektif
''')


if __name__ == '__main__':
    compare()
