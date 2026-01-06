"""
Market Cycle Analysis - Identify Accumulation, Rally, Distribution phases
Calculates patterns dynamically based on historical data
"""
import sys
sys.path.insert(0, 'C:/Users/chuwi/stock-analysis/app')

import pandas as pd
import numpy as np
from datetime import timedelta
from database import execute_query

# Parameters
SIDEWAYS_THRESHOLD_PCT = 10  # Price range < 10% = sideways
ROLLING_WINDOW = 7  # Days for rolling calculation


def get_price_data(stock_code):
    """Get price data for a stock"""
    query = """
        SELECT date, open_price, high_price, low_price, close_price, volume, value
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 'value']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def get_broker_data(stock_code):
    """Get broker summary data"""
    query = """
        SELECT date, broker_code, net_value, net_lot, buy_value, sell_value
        FROM broker_summary
        WHERE stock_code = %s
        ORDER BY date, broker_code
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    for col in ['net_value', 'net_lot', 'buy_value', 'sell_value']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def get_sensitive_brokers(stock_code, top_n=5):
    """Get top sensitive brokers for a stock"""
    from composite_analyzer import calculate_broker_sensitivity_advanced
    sensitivity_data = calculate_broker_sensitivity_advanced(stock_code)
    brokers = sensitivity_data.get('brokers', [])[:top_n]
    return [b['broker_code'] for b in brokers], brokers


def get_issued_shares(stock_code):
    """Get issued shares from stock_fundamental"""
    query = "SELECT issued_shares FROM stock_fundamental WHERE stock_code = %s"
    result = execute_query(query, (stock_code,), use_cache=False)
    if result:
        return float(result[0]['issued_shares'])
    return None


def identify_market_phases(price_df, broker_df, sensitive_broker_codes, issued_shares):
    """
    Identify market phases: ACCUMULATION, RALLY, DISTRIBUTION, DECLINE

    Returns list of phases with details
    """
    df = price_df.copy()

    # Calculate rolling high/low for sideways detection
    df['rolling_high'] = df['high_price'].rolling(window=ROLLING_WINDOW, min_periods=1).max()
    df['rolling_low'] = df['low_price'].rolling(window=ROLLING_WINDOW, min_periods=1).min()
    df['range_pct'] = (df['rolling_high'] - df['rolling_low']) / df['rolling_low'] * 100

    # Identify sideways periods
    df['is_sideways'] = df['range_pct'] < SIDEWAYS_THRESHOLD_PCT

    # Calculate daily sensitive broker accumulation
    sensitive_daily = []
    for date in df['date']:
        broker_on_date = broker_df[
            (broker_df['date'] == date) &
            (broker_df['broker_code'].isin(sensitive_broker_codes))
        ]
        if not broker_on_date.empty:
            net_lot = float(broker_on_date['net_lot'].sum())
            net_value = float(broker_on_date['net_value'].sum())
            num_accumulating = len(broker_on_date[broker_on_date['net_lot'] > 0])
        else:
            net_lot = 0
            net_value = 0
            num_accumulating = 0

        sensitive_daily.append({
            'date': date,
            'net_lot': net_lot,
            'net_value': net_value,
            'num_accumulating': num_accumulating
        })

    sensitive_df = pd.DataFrame(sensitive_daily)
    df = df.merge(sensitive_df, on='date', how='left')

    # Identify phases
    phases = []
    current_phase = None
    phase_start_idx = 0

    for i in range(len(df)):
        row = df.iloc[i]

        # Determine current state
        is_sideways = row['is_sideways']
        is_accumulating = row['net_lot'] > 0

        # Price trend (compare to 3 days ago)
        if i >= 3:
            price_change_3d = (row['close_price'] - df.iloc[i-3]['close_price']) / df.iloc[i-3]['close_price'] * 100
        else:
            price_change_3d = 0

        # Determine phase
        if is_sideways:
            if is_accumulating:
                new_phase = 'ACCUMULATION'
            else:
                new_phase = 'DISTRIBUTION'
        else:
            if price_change_3d > 3:
                new_phase = 'RALLY'
            elif price_change_3d < -3:
                new_phase = 'DECLINE'
            else:
                new_phase = current_phase or 'TRANSITION'

        # Phase change detected
        if new_phase != current_phase and current_phase is not None:
            # Save previous phase
            phase_data = df.iloc[phase_start_idx:i]
            if len(phase_data) >= 2:  # Minimum 2 days
                phases.append({
                    'phase': current_phase,
                    'start_date': phase_data.iloc[0]['date'],
                    'end_date': phase_data.iloc[-1]['date'],
                    'duration': len(phase_data),
                    'start_price': float(phase_data.iloc[0]['close_price']),
                    'end_price': float(phase_data.iloc[-1]['close_price']),
                    'high_price': float(phase_data['high_price'].max()),
                    'low_price': float(phase_data['low_price'].min()),
                    'price_change_pct': float((phase_data.iloc[-1]['close_price'] - phase_data.iloc[0]['close_price']) / phase_data.iloc[0]['close_price'] * 100),
                    'net_lot': float(phase_data['net_lot'].sum()),
                    'net_value': float(phase_data['net_value'].sum()),
                    'pct_of_shares': float(phase_data['net_lot'].sum() * 100) / issued_shares * 100 if issued_shares else 0
                })
            phase_start_idx = i

        current_phase = new_phase

    # Don't forget the last phase
    if current_phase and phase_start_idx < len(df) - 1:
        phase_data = df.iloc[phase_start_idx:]
        if len(phase_data) >= 2:
            phases.append({
                'phase': current_phase,
                'start_date': phase_data.iloc[0]['date'],
                'end_date': phase_data.iloc[-1]['date'],
                'duration': len(phase_data),
                'start_price': float(phase_data.iloc[0]['close_price']),
                'end_price': float(phase_data.iloc[-1]['close_price']),
                'high_price': float(phase_data['high_price'].max()),
                'low_price': float(phase_data['low_price'].min()),
                'price_change_pct': float((phase_data.iloc[-1]['close_price'] - phase_data.iloc[0]['close_price']) / phase_data.iloc[0]['close_price'] * 100),
                'net_lot': float(phase_data['net_lot'].sum()),
                'net_value': float(phase_data['net_value'].sum()),
                'pct_of_shares': float(phase_data['net_lot'].sum() * 100) / issued_shares * 100 if issued_shares else 0
            })

    return phases, df


def find_accumulation_to_rally_patterns(phases):
    """
    Find patterns where ACCUMULATION is followed by RALLY
    """
    patterns = []

    for i in range(len(phases) - 1):
        if phases[i]['phase'] == 'ACCUMULATION' and phases[i+1]['phase'] == 'RALLY':
            accum = phases[i]
            rally = phases[i+1]

            patterns.append({
                'accum_start': accum['start_date'],
                'accum_end': accum['end_date'],
                'accum_duration': accum['duration'],
                'accum_net_lot': accum['net_lot'],
                'accum_pct_shares': accum['pct_of_shares'],
                'accum_price_range': accum['high_price'] - accum['low_price'],
                'accum_range_pct': (accum['high_price'] - accum['low_price']) / accum['low_price'] * 100,
                'rally_start': rally['start_date'],
                'rally_end': rally['end_date'],
                'rally_duration': rally['duration'],
                'rally_start_price': rally['start_price'],
                'rally_peak_price': rally['high_price'],
                'rally_pct': rally['price_change_pct'],
                'rally_max_pct': (rally['high_price'] - rally['start_price']) / rally['start_price'] * 100
            })

    return patterns


def analyze_stock(stock_code):
    """Main analysis function for a stock"""
    print(f"\n{'='*70}")
    print(f"ANALISA MARKET CYCLE: {stock_code}")
    print(f"{'='*70}")

    # Get data
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)
    sensitive_codes, sensitive_info = get_sensitive_brokers(stock_code)
    issued_shares = get_issued_shares(stock_code)

    print(f"\nData Overview:")
    print(f"  Price data: {len(price_df)} days ({price_df['date'].min()} to {price_df['date'].max()})")
    print(f"  Issued Shares: {issued_shares:,.0f} ({issued_shares/1e9:.2f} Miliar)")
    print(f"  Sensitive Brokers: {sensitive_codes}")

    # Identify phases
    phases, df_with_phases = identify_market_phases(price_df, broker_df, sensitive_codes, issued_shares)

    print(f"\n{'='*70}")
    print("FASE-FASE MARKET YANG TERIDENTIFIKASI:")
    print(f"{'='*70}")

    for i, phase in enumerate(phases):
        phase_type = phase['phase']
        emoji = {'ACCUMULATION': '[ACCUM]', 'RALLY': '[RALLY]', 'DISTRIBUTION': '[DISTR]', 'DECLINE': '[DECLN]', 'TRANSITION': '[TRANS]'}.get(phase_type, '[?]')

        print(f"\n{emoji} Phase #{i+1}: {phase_type}")
        print(f"   Period: {phase['start_date'].strftime('%d %b %Y')} - {phase['end_date'].strftime('%d %b %Y')} ({phase['duration']} hari)")
        print(f"   Price: Rp {phase['start_price']:,.0f} -> Rp {phase['end_price']:,.0f} ({phase['price_change_pct']:+.1f}%)")
        print(f"   Range: Rp {phase['low_price']:,.0f} - Rp {phase['high_price']:,.0f}")
        print(f"   Net Lot Broker Sensitif: {phase['net_lot']:+,.0f} lot ({phase['pct_of_shares']:+.4f}% of shares)")
        print(f"   Net Value: Rp {phase['net_value']/1e9:+,.2f} Miliar")

    # Find ACCUMULATION -> RALLY patterns
    patterns = find_accumulation_to_rally_patterns(phases)

    if patterns:
        print(f"\n{'='*70}")
        print("POLA ACCUMULATION -> RALLY:")
        print(f"{'='*70}")

        for i, p in enumerate(patterns):
            print(f"\n[PATTERN] Pola #{i+1}:")
            print(f"   ACCUMULATION:")
            print(f"      Period: {p['accum_start'].strftime('%d %b %Y')} - {p['accum_end'].strftime('%d %b %Y')} ({p['accum_duration']} hari)")
            print(f"      Net Lot: {p['accum_net_lot']:+,.0f} ({p['accum_pct_shares']:+.4f}% of shares)")
            print(f"      Price Range: {p['accum_range_pct']:.1f}%")
            print(f"   RALLY:")
            print(f"      Period: {p['rally_start'].strftime('%d %b %Y')} - {p['rally_end'].strftime('%d %b %Y')} ({p['rally_duration']} hari)")
            print(f"      Price: Rp {p['rally_start_price']:,.0f} -> Rp {p['rally_peak_price']:,.0f}")
            print(f"      Gain: +{p['rally_max_pct']:.1f}%")

        # Calculate statistics
        print(f"\n{'='*70}")
        print("STATISTIK POLA (ACCUMULATION -> RALLY):")
        print(f"{'='*70}")

        accum_durations = [p['accum_duration'] for p in patterns]
        accum_pct_shares = [p['accum_pct_shares'] for p in patterns]
        accum_ranges = [p['accum_range_pct'] for p in patterns]
        rally_durations = [p['rally_duration'] for p in patterns]
        rally_gains = [p['rally_max_pct'] for p in patterns]

        print(f"\n   ACCUMULATION:")
        print(f"      Durasi Rata-rata    : {np.mean(accum_durations):.1f} hari")
        print(f"      Durasi Min-Max      : {min(accum_durations)} - {max(accum_durations)} hari")
        print(f"      % Shares Rata-rata  : {np.mean(accum_pct_shares):.4f}%")
        print(f"      % Shares Min-Max    : {min(accum_pct_shares):.4f}% - {max(accum_pct_shares):.4f}%")
        print(f"      Price Range Avg     : {np.mean(accum_ranges):.1f}%")

        print(f"\n   RALLY:")
        print(f"      Durasi Rata-rata    : {np.mean(rally_durations):.1f} hari")
        print(f"      Durasi Min-Max      : {min(rally_durations)} - {max(rally_durations)} hari")
        print(f"      Gain Rata-rata      : +{np.mean(rally_gains):.1f}%")
        print(f"      Gain Min-Max        : +{min(rally_gains):.1f}% - +{max(rally_gains):.1f}%")

        # Recommended thresholds (75% of average)
        print(f"\n{'='*70}")
        print("RECOMMENDED THRESHOLDS (75% of Average):")
        print(f"{'='*70}")
        print(f"   Min Accumulation Days  : {int(np.mean(accum_durations) * 0.75)} hari")
        print(f"   Min % of Shares        : {np.mean(accum_pct_shares) * 0.75:.4f}%")
        print(f"   Signal Threshold Days  : {int(np.mean(accum_durations) * 0.75)} hari")

        # Correlation analysis
        if len(patterns) >= 3:
            corr_duration = np.corrcoef(accum_durations, rally_gains)[0, 1]
            corr_volume = np.corrcoef(accum_pct_shares, rally_gains)[0, 1]

            print(f"\n{'='*70}")
            print("KORELASI:")
            print(f"{'='*70}")
            print(f"   Accum Duration vs Rally Gain: {corr_duration:.2f}")
            print(f"   Accum Volume vs Rally Gain  : {corr_volume:.2f}")
    else:
        print("\n[WARNING] Tidak ditemukan pola ACCUMULATION -> RALLY yang lengkap")

    return phases, patterns


if __name__ == "__main__":
    # Analyze CDIA
    phases_cdia, patterns_cdia = analyze_stock('CDIA')

    print("\n" + "="*70)
    print("ANALISA SELESAI")
    print("="*70)
