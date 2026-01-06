"""
Analyze Sideways -> Breakout patterns with Sensitive Broker Accumulation
"""
import sys
sys.path.insert(0, 'C:/Users/chuwi/stock-analysis/app')

import pandas as pd
import numpy as np
from database import execute_query
from composite_analyzer import calculate_broker_sensitivity_advanced


def analyze_sideways_to_breakout(stock_code):
    print(f'\n{"="*70}')
    print(f'ANALISA SIDEWAYS -> BREAKOUT: {stock_code}')
    print(f'{"="*70}')

    # 1. Get Sensitive Brokers
    sens_data = calculate_broker_sensitivity_advanced(stock_code)
    sensitive_brokers = sens_data.get('brokers', [])[:5]
    sensitive_codes = [b['broker_code'] for b in sensitive_brokers]
    print(f'\n[1] BROKER SENSITIF: {sensitive_codes}')
    for b in sensitive_brokers:
        print(f'    {b["broker_code"]}: Win Rate {b["win_rate"]:.0f}%, Lead Time {b["avg_lead_time"]:.1f} hari')

    # 2. Get Issued Shares
    query = 'SELECT issued_shares FROM stock_fundamental WHERE stock_code = %s'
    result = execute_query(query, (stock_code,), use_cache=False)
    issued_shares = float(result[0]['issued_shares']) if result else None
    print(f'\n[2] ISSUED SHARES: {issued_shares/1e9:.2f} Miliar')

    # 3. Get Price Data
    query = '''SELECT date, open_price, high_price, low_price, close_price
               FROM stock_daily WHERE stock_code = %s ORDER BY date'''
    price_df = pd.DataFrame(execute_query(query, (stock_code,), use_cache=False))
    for col in ['open_price', 'high_price', 'low_price', 'close_price']:
        price_df[col] = price_df[col].astype(float)

    # 4. Get Broker Data
    query = '''SELECT date, broker_code, net_lot, net_value
               FROM broker_summary WHERE stock_code = %s ORDER BY date'''
    broker_df = pd.DataFrame(execute_query(query, (stock_code,), use_cache=False))
    broker_df['net_lot'] = broker_df['net_lot'].astype(float)
    broker_df['net_value'] = broker_df['net_value'].astype(float)

    # 5. Find SIDEWAYS periods (rolling 7 days, range < 10%)
    print(f'\n[3] MENCARI PERIODE SIDEWAYS (range < 10%, min 7 hari)...')

    df = price_df.copy()
    df['rolling_high'] = df['high_price'].rolling(window=7, min_periods=7).max()
    df['rolling_low'] = df['low_price'].rolling(window=7, min_periods=7).min()
    df['range_pct'] = (df['rolling_high'] - df['rolling_low']) / df['rolling_low'] * 100
    df['is_sideways'] = df['range_pct'] < 10

    # Identify sideways periods
    sideways_periods = []
    in_sideways = False
    start_idx = None

    for i in range(len(df)):
        if df.iloc[i]['is_sideways'] and not pd.isna(df.iloc[i]['range_pct']):
            if not in_sideways:
                in_sideways = True
                start_idx = i
        else:
            if in_sideways and start_idx is not None:
                duration = i - start_idx
                if duration >= 5:  # Minimum 5 days sideways
                    sideways_periods.append({
                        'start_idx': start_idx,
                        'end_idx': i - 1,
                        'start_date': df.iloc[start_idx]['date'],
                        'end_date': df.iloc[i-1]['date'],
                        'duration': duration,
                        'high': df.iloc[start_idx:i]['high_price'].max(),
                        'low': df.iloc[start_idx:i]['low_price'].min()
                    })
                in_sideways = False
                start_idx = None

    print(f'    Ditemukan {len(sideways_periods)} periode sideways')

    # 6. For each sideways, check breakout and sensitive broker accumulation
    print(f'\n[4] ANALISA SETIAP PERIODE SIDEWAYS:')

    valid_patterns = []

    for idx, sw in enumerate(sideways_periods):
        sw_start = sw['start_date']
        sw_end = sw['end_date']
        sw_high = sw['high']
        sw_low = sw['low']
        sw_duration = sw['duration']
        breakout_target = sw_high * 1.10  # 10% above sideways high

        # Check if breakout happened after sideways
        future_df = df[df['date'] > sw_end].head(30)  # Look 30 days ahead
        breakout_date = None
        breakout_price = None
        days_to_breakout = None

        for j, row in future_df.iterrows():
            if row['high_price'] >= breakout_target:
                breakout_date = row['date']
                breakout_price = row['high_price']
                days_to_breakout = (breakout_date - sw_end).days
                break

        # Calculate sensitive broker accumulation during sideways
        sw_broker_data = broker_df[
            (broker_df['date'] >= sw_start) &
            (broker_df['date'] <= sw_end) &
            (broker_df['broker_code'].isin(sensitive_codes))
        ]

        total_net_lot = sw_broker_data['net_lot'].sum()
        total_net_value = sw_broker_data['net_value'].sum()

        # Count how many days each broker accumulated
        broker_accum_days = {}
        broker_accum_lots = {}
        for code in sensitive_codes:
            broker_data = sw_broker_data[sw_broker_data['broker_code'] == code]
            accum_days = len(broker_data[broker_data['net_lot'] > 0])
            total_lots = broker_data['net_lot'].sum()
            broker_accum_days[code] = accum_days
            broker_accum_lots[code] = total_lots

        # Check if majority (>=3) of sensitive brokers accumulated
        brokers_accumulating = sum(1 for v in broker_accum_lots.values() if v > 0)
        is_valid_accumulation = brokers_accumulating >= 3 and total_net_lot > 0

        pct_of_shares = (total_net_lot * 100 / issued_shares) * 100 if issued_shares else 0

        print(f'\n  [{idx+1}] Sideways: {sw_start.strftime("%d %b")} - {sw_end.strftime("%d %b %Y")} ({sw_duration} hari)')
        print(f'      Range: Rp {sw_low:,.0f} - Rp {sw_high:,.0f} ({(sw_high-sw_low)/sw_low*100:.1f}%)')
        print(f'      Target Breakout (>10%): Rp {breakout_target:,.0f}')

        if breakout_date:
            print(f'      BREAKOUT: {breakout_date.strftime("%d %b %Y")} @ Rp {breakout_price:,.0f} ({days_to_breakout} hari setelah)')
        else:
            print(f'      BREAKOUT: Tidak terjadi dalam 30 hari')

        print(f'      Akumulasi Broker Sensitif:')
        print(f'        Total: {total_net_lot:+,.0f} lot ({pct_of_shares:+.4f}% shares)')
        print(f'        Broker accumulating: {brokers_accumulating}/5')
        for code in sensitive_codes:
            days = broker_accum_days[code]
            lots = broker_accum_lots[code]
            status = "ACCUM" if lots > 0 else "DIST"
            print(f'          {code}: {days} hari, {lots:+,.0f} lot [{status}]')

        if breakout_date and is_valid_accumulation:
            print(f'      STATUS: *** VALID PATTERN ***')
            valid_patterns.append({
                'sideways_start': sw_start,
                'sideways_end': sw_end,
                'sideways_days': sw_duration,
                'sideways_high': sw_high,
                'sideways_low': sw_low,
                'breakout_date': breakout_date,
                'days_to_breakout': days_to_breakout,
                'total_lot': total_net_lot,
                'pct_shares': pct_of_shares,
                'brokers_accumulating': brokers_accumulating
            })
        else:
            reason = 'No breakout' if not breakout_date else 'Not enough accumulation'
            print(f'      STATUS: INVALID ({reason})')

    # 7. Summary
    print(f'\n{"="*70}')
    print(f'SUMMARY: {stock_code}')
    print(f'{"="*70}')
    print(f'Total Sideways Periods: {len(sideways_periods)}')
    print(f'Valid Patterns (Sideways + Accumulation + Breakout): {len(valid_patterns)}')

    if valid_patterns:
        avg_sideways_days = np.mean([p['sideways_days'] for p in valid_patterns])
        avg_days_to_breakout = np.mean([p['days_to_breakout'] for p in valid_patterns])
        avg_lot = np.mean([p['total_lot'] for p in valid_patterns])
        avg_pct = np.mean([p['pct_shares'] for p in valid_patterns])

        print(f'\n  STATISTIK POLA VALID:')
        print(f'    Avg Sideways Duration: {avg_sideways_days:.1f} hari')
        print(f'    Avg Days to Breakout: {avg_days_to_breakout:.1f} hari')
        print(f'    Avg Accumulation: {avg_lot:,.0f} lot ({avg_pct:.4f}% shares)')

        print(f'\n  THRESHOLD REKOMENDASI (75% of avg):')
        min_sideways = int(avg_sideways_days * 0.75)
        min_lot = avg_lot * 0.75
        min_pct = avg_pct * 0.75
        signal_day = int(avg_sideways_days * 0.75)

        print(f'    Min Sideways Days: {min_sideways} hari')
        print(f'    Min Accumulation: {min_lot:,.0f} lot ({min_pct:.4f}% shares)')
        print(f'    Signal Day: Hari ke-{signal_day} dari sideways')

        return {
            'stock_code': stock_code,
            'total_sideways': len(sideways_periods),
            'valid_patterns': len(valid_patterns),
            'avg_sideways_days': avg_sideways_days,
            'avg_days_to_breakout': avg_days_to_breakout,
            'avg_lot': avg_lot,
            'avg_pct_shares': avg_pct,
            'threshold': {
                'min_sideways_days': min_sideways,
                'min_lot': min_lot,
                'min_pct_shares': min_pct,
                'signal_day': signal_day
            }
        }
    else:
        print('\n  Tidak ada pola valid ditemukan.')
        return None


if __name__ == "__main__":
    # Analyze all stocks
    results = {}
    for stock in ['CDIA', 'PANI', 'BBCA']:
        result = analyze_sideways_to_breakout(stock)
        if result:
            results[stock] = result

    # Final comparison
    if results:
        print(f'\n{"="*70}')
        print('PERBANDINGAN THRESHOLD ANTAR EMITEN')
        print(f'{"="*70}')
        print(f'{"Stock":<8} {"Sideways":<10} {"Accum Lot":<15} {"% Shares":<12} {"Signal Day":<10}')
        print(f'{"-"*8} {"-"*10} {"-"*15} {"-"*12} {"-"*10}')
        for stock, data in results.items():
            t = data['threshold']
            print(f'{stock:<8} {t["min_sideways_days"]:<10} {t["min_lot"]:>12,.0f} {t["min_pct_shares"]:>10.4f}% {t["signal_day"]:<10}')
