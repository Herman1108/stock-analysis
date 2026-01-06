"""
STEP 1 & 2: Perhitungan Broker Sensitif dan Deteksi Fase Market
Formula Dinamis untuk Signal Tracker
"""
import sys
sys.path.insert(0, 'C:/Users/chuwi/stock-analysis/app')

import pandas as pd
import numpy as np
from datetime import timedelta
from database import execute_query

# ============================================================
# PARAMETER YANG BISA DI-TUNING
# ============================================================
PARAMS = {
    'lookback_days': 60,          # Periode analisis historis
    'future_days': 5,             # Hari kedepan untuk cek kenaikan harga
    'min_price_increase': 3.0,    # % kenaikan harga minimum untuk dianggap "win"
    'sideways_range_pct': 10.0,   # Range harga < X% = sideways
    'sideways_window': 7,         # Window untuk deteksi sideways (hari)
    'rally_threshold': 3.0,       # % kenaikan untuk fase RALLY
    'decline_threshold': -3.0,    # % penurunan untuk fase DECLINE
    'top_sensitive_brokers': 5,   # Jumlah broker sensitif yang diambil
}


def get_price_data(stock_code: str) -> pd.DataFrame:
    """Ambil data harga"""
    query = """
        SELECT date, open_price, high_price, low_price, close_price, volume
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def get_broker_data(stock_code: str) -> pd.DataFrame:
    """Ambil data broker"""
    query = """
        SELECT date, broker_code, net_lot, net_value, buy_value, sell_value
        FROM broker_summary
        WHERE stock_code = %s
        ORDER BY date, broker_code
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    for col in ['net_lot', 'net_value', 'buy_value', 'sell_value']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


# ============================================================
# STEP 1: IDENTIFIKASI BROKER SENSITIF
# ============================================================
def calculate_sensitive_brokers(stock_code: str):
    """
    FORMULA STEP 1: Identifikasi Broker Sensitif

    Broker sensitif = broker yang akumulasinya MENDAHULUI kenaikan harga

    Untuk setiap broker, hitung:
    1. Win Rate = (Jumlah akumulasi diikuti kenaikan) / (Total akumulasi) * 100
    2. Lead Time = Rata-rata hari antara akumulasi dan puncak harga
    3. Correlation = Korelasi antara net_lot broker vs future price change

    Sensitivity Score = (Win Rate * 0.4) + (Lead Time Score * 0.3) + (Correlation * 0.3)
    """
    print(f"\n{'='*70}")
    print(f"STEP 1: IDENTIFIKASI BROKER SENSITIF - {stock_code}")
    print(f"{'='*70}")

    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or broker_df.empty:
        print("ERROR: Data tidak tersedia")
        return None

    print(f"\nData Overview:")
    print(f"  - Price data: {len(price_df)} hari ({price_df['date'].min()} s/d {price_df['date'].max()})")
    print(f"  - Broker data: {len(broker_df)} records, {broker_df['broker_code'].nunique()} broker unik")

    # Hitung future price change untuk setiap tanggal
    price_df = price_df.sort_values('date').reset_index(drop=True)
    price_df['future_max_price'] = price_df['close_price'].shift(-PARAMS['future_days']).rolling(
        window=PARAMS['future_days'], min_periods=1
    ).max().shift(PARAMS['future_days'])

    # Alternatif: hitung max price dalam X hari kedepan
    future_max = []
    for i in range(len(price_df)):
        future_slice = price_df.iloc[i+1:i+1+PARAMS['future_days']]
        if len(future_slice) > 0:
            future_max.append(future_slice['high_price'].max())
        else:
            future_max.append(np.nan)
    price_df['future_max_price'] = future_max

    price_df['future_return_pct'] = (
        (price_df['future_max_price'] - price_df['close_price']) / price_df['close_price'] * 100
    )

    # Merge dengan broker data
    merged = broker_df.merge(price_df[['date', 'close_price', 'future_return_pct']], on='date', how='left')

    # Analisis per broker
    print(f"\n{'='*70}")
    print("ANALISIS PER BROKER:")
    print(f"{'='*70}")
    print(f"\nFormula:")
    print(f"  Win Rate = (Akumulasi diikuti kenaikan >= {PARAMS['min_price_increase']}%) / Total Akumulasi * 100")
    print(f"  Lead Time = Rata-rata hari hingga harga naik {PARAMS['min_price_increase']}%")
    print(f"  Future Days = {PARAMS['future_days']} hari kedepan")

    broker_stats = []
    unique_brokers = merged['broker_code'].unique()

    for broker in unique_brokers:
        broker_data = merged[merged['broker_code'] == broker].copy()

        # Filter hari dimana broker AKUMULASI (net_lot > 0)
        accum_days = broker_data[broker_data['net_lot'] > 0]

        if len(accum_days) < 5:  # Minimal 5 hari akumulasi
            continue

        # Hitung Win Rate
        wins = accum_days[accum_days['future_return_pct'] >= PARAMS['min_price_increase']]
        win_rate = len(wins) / len(accum_days) * 100 if len(accum_days) > 0 else 0

        # Hitung rata-rata return setelah akumulasi
        avg_return = accum_days['future_return_pct'].mean()

        # Hitung total akumulasi
        total_accum_lot = accum_days['net_lot'].sum()
        total_accum_value = accum_days['net_value'].sum()

        # Hitung korelasi net_lot vs future_return
        valid_data = broker_data.dropna(subset=['future_return_pct'])
        if len(valid_data) > 10:
            correlation = valid_data['net_lot'].corr(valid_data['future_return_pct'])
        else:
            correlation = 0

        # Lead Time Score (semakin cepat semakin bagus, normalize 0-100)
        # Asumsi lead time ideal = 1-3 hari
        lead_time_score = min(100, max(0, (PARAMS['future_days'] - 1) / PARAMS['future_days'] * 100))

        # Sensitivity Score
        sensitivity_score = (
            win_rate * 0.4 +
            (correlation * 100 if correlation > 0 else 0) * 0.3 +
            lead_time_score * 0.3
        )

        broker_stats.append({
            'broker_code': broker,
            'accum_days': len(accum_days),
            'win_count': len(wins),
            'win_rate': round(win_rate, 1),
            'avg_return': round(avg_return, 2),
            'correlation': round(correlation, 3) if not np.isnan(correlation) else 0,
            'total_accum_lot': total_accum_lot,
            'total_accum_value': total_accum_value,
            'sensitivity_score': round(sensitivity_score, 1)
        })

    # Sort by sensitivity score
    broker_stats = sorted(broker_stats, key=lambda x: x['sensitivity_score'], reverse=True)

    # Tampilkan Top Brokers
    print(f"\n{'='*70}")
    print(f"TOP {PARAMS['top_sensitive_brokers']} BROKER SENSITIF:")
    print(f"{'='*70}")
    print(f"\n{'Rank':<5} {'Broker':<8} {'Akum Days':<10} {'Win Rate':<10} {'Avg Return':<12} {'Correlation':<12} {'Score':<8}")
    print(f"{'-'*5} {'-'*8} {'-'*10} {'-'*10} {'-'*12} {'-'*12} {'-'*8}")

    top_brokers = broker_stats[:PARAMS['top_sensitive_brokers']]
    for i, b in enumerate(top_brokers, 1):
        print(f"{i:<5} {b['broker_code']:<8} {b['accum_days']:<10} {b['win_rate']:<10.1f}% {b['avg_return']:<12.2f}% {b['correlation']:<12.3f} {b['sensitivity_score']:<8.1f}")

    return {
        'stock_code': stock_code,
        'params': PARAMS,
        'top_brokers': top_brokers,
        'all_broker_stats': broker_stats
    }


# ============================================================
# STEP 2: DETEKSI FASE MARKET
# ============================================================
def detect_market_phase(stock_code: str, sensitive_brokers: list):
    """
    FORMULA STEP 2: Deteksi Fase Market

    Fase Market ditentukan berdasarkan:
    1. SIDEWAYS: Rolling range (high-low) < 10% dalam 7 hari
    2. ACCUMULATION: SIDEWAYS + Net lot broker sensitif > 0
    3. DISTRIBUTION: SIDEWAYS + Net lot broker sensitif < 0
    4. RALLY: Price change 3 hari > +3%
    5. DECLINE: Price change 3 hari < -3%
    """
    print(f"\n{'='*70}")
    print(f"STEP 2: DETEKSI FASE MARKET - {stock_code}")
    print(f"{'='*70}")

    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    print(f"\nBroker Sensitif yang dimonitor: {sensitive_brokers}")
    print(f"\nParameter Deteksi Fase:")
    print(f"  - Sideways Range: < {PARAMS['sideways_range_pct']}%")
    print(f"  - Sideways Window: {PARAMS['sideways_window']} hari")
    print(f"  - Rally Threshold: > +{PARAMS['rally_threshold']}%")
    print(f"  - Decline Threshold: < {PARAMS['decline_threshold']}%")

    # Hitung rolling high/low untuk deteksi sideways
    df = price_df.copy().sort_values('date').reset_index(drop=True)
    df['rolling_high'] = df['high_price'].rolling(window=PARAMS['sideways_window'], min_periods=1).max()
    df['rolling_low'] = df['low_price'].rolling(window=PARAMS['sideways_window'], min_periods=1).min()
    df['range_pct'] = (df['rolling_high'] - df['rolling_low']) / df['rolling_low'] * 100
    df['is_sideways'] = df['range_pct'] < PARAMS['sideways_range_pct']

    # Hitung price change 3 hari
    df['price_change_3d'] = (df['close_price'] - df['close_price'].shift(3)) / df['close_price'].shift(3) * 100

    # Hitung net lot broker sensitif per hari
    sens_broker_df = broker_df[broker_df['broker_code'].isin(sensitive_brokers)]
    daily_sens_lot = sens_broker_df.groupby('date').agg({
        'net_lot': 'sum',
        'net_value': 'sum'
    }).reset_index()
    daily_sens_lot.columns = ['date', 'sens_net_lot', 'sens_net_value']

    # Merge
    df = df.merge(daily_sens_lot, on='date', how='left')
    df['sens_net_lot'] = df['sens_net_lot'].fillna(0)
    df['sens_net_value'] = df['sens_net_value'].fillna(0)

    # Tentukan fase untuk setiap hari
    def determine_phase(row):
        if pd.isna(row['price_change_3d']):
            return 'UNKNOWN'

        is_sideways = row['is_sideways']
        price_change = row['price_change_3d']
        sens_lot = row['sens_net_lot']

        if is_sideways:
            if sens_lot > 0:
                return 'ACCUMULATION'
            elif sens_lot < 0:
                return 'DISTRIBUTION'
            else:
                return 'SIDEWAYS'
        else:
            if price_change > PARAMS['rally_threshold']:
                return 'RALLY'
            elif price_change < PARAMS['decline_threshold']:
                return 'DECLINE'
            else:
                return 'TRANSITION'

    df['market_phase'] = df.apply(determine_phase, axis=1)

    # Tampilkan hasil 10 hari terakhir
    print(f"\n{'='*70}")
    print("FASE MARKET 10 HARI TERAKHIR:")
    print(f"{'='*70}")

    recent = df.tail(10)
    print(f"\n{'Date':<12} {'Close':<10} {'Range%':<8} {'Sideways':<10} {'Change3D':<10} {'SensLot':<12} {'Phase':<15}")
    print(f"{'-'*12} {'-'*10} {'-'*8} {'-'*10} {'-'*10} {'-'*12} {'-'*15}")

    for _, row in recent.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        sideways_str = 'YES' if row['is_sideways'] else 'NO'
        change_str = f"{row['price_change_3d']:+.1f}%" if not pd.isna(row['price_change_3d']) else 'N/A'
        print(f"{date_str:<12} {row['close_price']:<10,.0f} {row['range_pct']:<8.1f}% {sideways_str:<10} {change_str:<10} {row['sens_net_lot']:<12,.0f} {row['market_phase']:<15}")

    # Fase saat ini (hari terakhir)
    current = df.iloc[-1]
    print(f"\n{'='*70}")
    print("FASE SAAT INI:")
    print(f"{'='*70}")
    print(f"  Tanggal: {current['date'].strftime('%Y-%m-%d')}")
    print(f"  Harga: Rp {current['close_price']:,.0f}")
    print(f"  Range 7 Hari: {current['range_pct']:.1f}% ({'SIDEWAYS' if current['is_sideways'] else 'TRENDING'})")
    print(f"  Price Change 3D: {current['price_change_3d']:+.1f}%" if not pd.isna(current['price_change_3d']) else "  Price Change 3D: N/A")
    print(f"  Net Lot Broker Sensitif: {current['sens_net_lot']:+,.0f}")
    print(f"  >>> FASE: {current['market_phase']} <<<")

    # Hitung statistik fase
    phase_counts = df['market_phase'].value_counts()
    print(f"\nDistribusi Fase (seluruh periode):")
    for phase, count in phase_counts.items():
        pct = count / len(df) * 100
        print(f"  {phase}: {count} hari ({pct:.1f}%)")

    return {
        'stock_code': stock_code,
        'current_date': current['date'],
        'current_price': current['close_price'],
        'current_phase': current['market_phase'],
        'is_sideways': current['is_sideways'],
        'range_pct': current['range_pct'],
        'price_change_3d': current['price_change_3d'],
        'sens_net_lot': current['sens_net_lot'],
        'phase_history': df[['date', 'close_price', 'market_phase', 'sens_net_lot']].tail(30).to_dict('records')
    }


# ============================================================
# MAIN: JALANKAN STEP 1 & 2
# ============================================================
if __name__ == "__main__":
    stock_code = 'NCKL'

    # STEP 1: Identifikasi Broker Sensitif
    step1_result = calculate_sensitive_brokers(stock_code)

    if step1_result:
        # Ambil list broker sensitif
        sensitive_broker_codes = [b['broker_code'] for b in step1_result['top_brokers']]

        # STEP 2: Deteksi Fase Market
        step2_result = detect_market_phase(stock_code, sensitive_broker_codes)

        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY STEP 1 & 2")
        print(f"{'='*70}")
        print(f"\nSTEP 1 - Broker Sensitif {stock_code}:")
        for i, b in enumerate(step1_result['top_brokers'], 1):
            print(f"  {i}. {b['broker_code']} (Win Rate: {b['win_rate']}%, Score: {b['sensitivity_score']})")

        print(f"\nSTEP 2 - Fase Market Saat Ini:")
        print(f"  Fase: {step2_result['current_phase']}")
        print(f"  Harga: Rp {step2_result['current_price']:,.0f}")
        print(f"  Net Lot Sensitif: {step2_result['sens_net_lot']:+,.0f}")
