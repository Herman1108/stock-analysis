# -*- coding: utf-8 -*-
"""
Perbandingan Formula V10 vs V11
"""

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

from backtest_v10_universal import run_backtest as run_v10, STOCK_ZONES
from backtest_v11_universal import run_backtest as run_v11, V11_PARAMS


def compare_formulas():
    print("=" * 100)
    print("PERBANDINGAN FORMULA V10 vs V11")
    print("=" * 100)
    print("\nV10: Base formula dengan zona S/R fix")
    print("V11: V10 + Volume >= 1.0x + RSI < 70")
    print()

    v10_results = []
    v11_results = []

    for stock_code in sorted(STOCK_ZONES.keys()):
        v10 = run_v10(stock_code)
        v11 = run_v11(stock_code)

        if v10:
            v10_results.append(v10)
        if v11:
            v11_results.append(v11)

    # Per-stock comparison
    print("\n" + "=" * 100)
    print("PERBANDINGAN PER SAHAM")
    print("=" * 100)
    print(f"\n{'Stock':<8} {'------- V10 -------':^30} {'------- V11 -------':^30} {'Improvement':^15}")
    print(f"{'':8} {'Trades':>8} {'WR':>8} {'PnL':>12} {'Trades':>8} {'WR':>8} {'PnL':>12} {'WR':>8} {'PnL':>10}")
    print("-" * 100)

    total_v10_trades = 0
    total_v10_wins = 0
    total_v10_pnl = 0
    total_v11_trades = 0
    total_v11_wins = 0
    total_v11_pnl = 0
    total_filtered = 0

    for stock in sorted(STOCK_ZONES.keys()):
        v10 = next((r for r in v10_results if r['stock_code'] == stock), None)
        v11 = next((r for r in v11_results if r['stock_code'] == stock), None)

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

            wr_color = '+' if wr_diff > 0 else ''
            pnl_color = '+' if pnl_diff > 0 else ''

            print(f"{stock:<8} {len(v10_closed):>8} {v10_wr:>7.1f}% {v10_pnl:>+11.1f}% {len(v11_closed):>8} {v11_wr:>7.1f}% {v11_pnl:>+11.1f}% {wr_color}{wr_diff:>7.1f}% {pnl_color}{pnl_diff:>9.1f}%")

    print("-" * 100)

    # Total comparison
    total_v10_wr = total_v10_wins / total_v10_trades * 100 if total_v10_trades else 0
    total_v11_wr = total_v11_wins / total_v11_trades * 100 if total_v11_trades else 0
    wr_diff = total_v11_wr - total_v10_wr
    pnl_diff = total_v11_pnl - total_v10_pnl

    print(f"{'TOTAL':<8} {total_v10_trades:>8} {total_v10_wr:>7.1f}% {total_v10_pnl:>+11.1f}% {total_v11_trades:>8} {total_v11_wr:>7.1f}% {total_v11_pnl:>+11.1f}% {'+' if wr_diff > 0 else ''}{wr_diff:>7.1f}% {'+' if pnl_diff > 0 else ''}{pnl_diff:>9.1f}%")

    # Summary
    print("\n" + "=" * 100)
    print("RINGKASAN")
    print("=" * 100)

    print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                         FORMULA V10                                      ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Total Trades    : {total_v10_trades:>5}                                              ║
║  Wins            : {total_v10_wins:>5}                                              ║
║  Losses          : {total_v10_trades - total_v10_wins:>5}                                              ║
║  Win Rate        : {total_v10_wr:>5.1f}%                                            ║
║  Total PnL       : {total_v10_pnl:>+6.1f}%                                           ║
║  Avg PnL/Trade   : {total_v10_pnl/total_v10_trades if total_v10_trades else 0:>+6.2f}%                                           ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║                         FORMULA V11                                      ║
║              (V10 + Volume >= 1.0x + RSI < 70)                           ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Total Trades    : {total_v11_trades:>5}                                              ║
║  Wins            : {total_v11_wins:>5}                                              ║
║  Losses          : {total_v11_trades - total_v11_wins:>5}                                              ║
║  Win Rate        : {total_v11_wr:>5.1f}%                                            ║
║  Total PnL       : {total_v11_pnl:>+6.1f}%                                           ║
║  Avg PnL/Trade   : {total_v11_pnl/total_v11_trades if total_v11_trades else 0:>+6.2f}%                                           ║
║  Filtered Entries: {total_filtered:>5}                                              ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║                         IMPROVEMENT                                      ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Win Rate Change : {'+' if wr_diff > 0 else ''}{wr_diff:>5.1f}%                                            ║
║  PnL Change      : {'+' if pnl_diff > 0 else ''}{pnl_diff:>5.1f}%                                            ║
║  Trades Filtered : {total_filtered:>5} ({total_filtered/(total_v10_trades)*100 if total_v10_trades else 0:.1f}% of V10 signals)                     ║
╚══════════════════════════════════════════════════════════════════════════╝
""")

    # Analyze filtered trades - what would have happened if we entered?
    print("\n" + "=" * 100)
    print("ANALISIS TRADE YANG DI-FILTER V11")
    print("=" * 100)

    # Get filtered entries details from V11 results
    all_filtered = []
    for r in v11_results:
        for f in r.get('filtered_entries', []):
            f['stock_code'] = r['stock_code']
            all_filtered.append(f)

    if all_filtered:
        # Count by reason
        vol_low = [f for f in all_filtered if 'VOL_LOW' in f.get('reason', '')]
        rsi_high = [f for f in all_filtered if 'RSI_HIGH' in f.get('reason', '')]

        print(f"\n  Total Filtered: {len(all_filtered)}")
        print(f"    - Volume Low : {len(vol_low)} ({len(vol_low)/len(all_filtered)*100:.1f}%)")
        print(f"    - RSI High   : {len(rsi_high)} ({len(rsi_high)/len(all_filtered)*100:.1f}%)")

        print(f"\n  Detail Filtered Entries:")
        print(f"  {'#':<3} {'Stock':<6} {'Type':<12} {'Date':<12} {'Price':>10} {'Vol':>8} {'RSI':>5} {'Reason':<25}")
        print(f"  {'-'*90}")
        for idx, f in enumerate(all_filtered, 1):
            vol = f"{f.get('vol_ratio', 0):.2f}x" if f.get('vol_ratio') else "N/A"
            rsi = f"{f.get('rsi', 0):.0f}" if f.get('rsi') else "N/A"
            print(f"  {idx:<3} {f['stock_code']:<6} {f['type']:<12} {f['date']:<12} {f['price']:>10,.0f} {vol:>8} {rsi:>5} {f['reason']:<25}")

    # Conclusion
    print("\n" + "=" * 100)
    print("KESIMPULAN")
    print("=" * 100)

    if wr_diff > 0:
        print(f"\n  ✅ V11 LEBIH BAIK dari V10:")
        print(f"     - Win Rate naik {wr_diff:.1f}% ({total_v10_wr:.1f}% → {total_v11_wr:.1f}%)")
        if pnl_diff > 0:
            print(f"     - Total PnL naik {pnl_diff:.1f}%")
        else:
            print(f"     - Total PnL turun {abs(pnl_diff):.1f}% (karena jumlah trade berkurang)")
        print(f"     - {total_filtered} trade di-filter ({total_filtered/(total_v10_trades)*100 if total_v10_trades else 0:.1f}% dari signal V10)")
    elif wr_diff < 0:
        print(f"\n  ❌ V11 TIDAK LEBIH BAIK dari V10:")
        print(f"     - Win Rate turun {abs(wr_diff):.1f}%")
    else:
        print(f"\n  ➖ V11 SAMA dengan V10")

    print("\n")


if __name__ == '__main__':
    compare_formulas()
