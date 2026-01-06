"""
DETEKSI AKUMULASI vs DISTRIBUSI - Formula Lengkap
Berdasarkan indikator kuantitatif untuk fase sideways

Indikator yang digunakan:
1. CPR (Close Position Ratio)
2. UV/DV (Up Volume / Down Volume Ratio)
3. VRPR (Volume Relative to Price Range)
4. Broker Influence Score (BIS)
5. Broker Persistence
6. Absorption Detection
7. Smart Money Divergence
"""
import sys
sys.path.insert(0, 'C:/Users/chuwi/stock-analysis/app')

import pandas as pd
import numpy as np
from datetime import timedelta
from database import execute_query

# ============================================================
# PARAMETER KONFIGURASI
# ============================================================
PARAMS = {
    'sideways_threshold_pct': 10.0,   # Range < 10% = sideways
    'sideways_window': 20,            # Window untuk deteksi sideways
    'min_sideways_days': 5,           # Minimum hari untuk fase sideways valid
    'cpr_accum_threshold': 0.60,      # CPR >= 0.60 = akumulasi
    'cpr_distrib_threshold': 0.40,    # CPR <= 0.40 = distribusi
    'uvdv_accum_threshold': 1.2,      # UV/DV > 1.2 = akumulasi
    'uvdv_distrib_threshold': 0.8,    # UV/DV < 0.8 = distribusi
    'persistence_min_days': 5,        # Minimum hari konsisten
}


def get_price_data(stock_code: str) -> pd.DataFrame:
    """Ambil data harga OHLCV"""
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


def get_broker_data(stock_code: str) -> pd.DataFrame:
    """Ambil data broker summary"""
    query = """
        SELECT date, broker_code, net_lot, net_value, buy_value, sell_value, buy_lot, sell_lot
        FROM broker_summary
        WHERE stock_code = %s
        ORDER BY date, broker_code
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    for col in ['net_lot', 'net_value', 'buy_value', 'sell_value', 'buy_lot', 'sell_lot']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def get_issued_shares(stock_code: str) -> float:
    """Ambil jumlah saham beredar"""
    query = "SELECT issued_shares FROM stock_fundamental WHERE stock_code = %s"
    result = execute_query(query, (stock_code,), use_cache=False)
    if result:
        return float(result[0]['issued_shares'])
    return None


# ============================================================
# STEP 1: IDENTIFIKASI PERIODE SIDEWAYS
# ============================================================
def identify_sideways_periods(price_df: pd.DataFrame) -> list:
    """
    Identifikasi periode sideways berdasarkan range harga

    Kriteria: Range % = (MAX(High) - MIN(Low)) / AVG(Close) < 10%
    """
    df = price_df.copy()
    window = PARAMS['sideways_window']

    # Hitung rolling range
    df['rolling_high'] = df['high_price'].rolling(window=window, min_periods=window).max()
    df['rolling_low'] = df['low_price'].rolling(window=window, min_periods=window).min()
    df['rolling_avg'] = df['close_price'].rolling(window=window, min_periods=window).mean()
    df['range_pct'] = (df['rolling_high'] - df['rolling_low']) / df['rolling_avg'] * 100
    df['is_sideways'] = df['range_pct'] < PARAMS['sideways_threshold_pct']

    # Identifikasi periode sideways
    sideways_periods = []
    in_sideways = False
    start_idx = None

    for i in range(len(df)):
        if pd.isna(df.iloc[i]['range_pct']):
            continue

        if df.iloc[i]['is_sideways']:
            if not in_sideways:
                in_sideways = True
                start_idx = i
        else:
            if in_sideways and start_idx is not None:
                duration = i - start_idx
                if duration >= PARAMS['min_sideways_days']:
                    sideways_periods.append({
                        'start_idx': start_idx,
                        'end_idx': i - 1,
                        'start_date': df.iloc[start_idx]['date'],
                        'end_date': df.iloc[i-1]['date'],
                        'duration': duration,
                        'high': df.iloc[start_idx:i]['high_price'].max(),
                        'low': df.iloc[start_idx:i]['low_price'].min(),
                        'avg_close': df.iloc[start_idx:i]['close_price'].mean(),
                        'range_pct': (df.iloc[start_idx:i]['high_price'].max() -
                                     df.iloc[start_idx:i]['low_price'].min()) /
                                     df.iloc[start_idx:i]['close_price'].mean() * 100
                    })
                in_sideways = False
                start_idx = None

    # Cek jika masih dalam sideways di akhir data
    if in_sideways and start_idx is not None:
        duration = len(df) - start_idx
        if duration >= PARAMS['min_sideways_days']:
            sideways_periods.append({
                'start_idx': start_idx,
                'end_idx': len(df) - 1,
                'start_date': df.iloc[start_idx]['date'],
                'end_date': df.iloc[-1]['date'],
                'duration': duration,
                'high': df.iloc[start_idx:]['high_price'].max(),
                'low': df.iloc[start_idx:]['low_price'].min(),
                'avg_close': df.iloc[start_idx:]['close_price'].mean(),
                'range_pct': (df.iloc[start_idx:]['high_price'].max() -
                             df.iloc[start_idx:]['low_price'].min()) /
                             df.iloc[start_idx:]['close_price'].mean() * 100
            })

    return sideways_periods, df


# ============================================================
# INDIKATOR 1: CPR (Close Position Ratio)
# ============================================================
def calculate_cpr(price_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    CPR = (Close - Low) / (High - Low)

    Interpretasi:
    - 0 = close di low (bearish)
    - 1 = close di high (bullish)
    - Avg CPR >= 0.60 = Akumulasi
    - Avg CPR <= 0.40 = Distribusi
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    # Hindari division by zero
    df['range'] = df['high_price'] - df['low_price']
    df['cpr'] = np.where(df['range'] > 0,
                         (df['close_price'] - df['low_price']) / df['range'],
                         0.5)

    avg_cpr = df['cpr'].mean()
    cpr_trend = df['cpr'].diff().mean()  # Trend CPR (naik/turun)

    # Scoring
    if avg_cpr >= PARAMS['cpr_accum_threshold']:
        signal = 'AKUMULASI'
        score = 1
    elif avg_cpr <= PARAMS['cpr_distrib_threshold']:
        signal = 'DISTRIBUSI'
        score = -1
    else:
        signal = 'NETRAL'
        score = 0

    return {
        'avg_cpr': round(avg_cpr, 3),
        'cpr_trend': round(cpr_trend, 4),
        'signal': signal,
        'score': score,
        'daily_cpr': df[['date', 'cpr']].to_dict('records')
    }


# ============================================================
# INDIKATOR 2: UV/DV (Up Volume / Down Volume Ratio)
# ============================================================
def calculate_uvdv(price_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Up Volume = Volume saat Close > Open
    Down Volume = Volume saat Close < Open
    UV/DV Ratio = Up Volume / Down Volume

    Interpretasi:
    - UV/DV > 1.2 = Akumulasi
    - UV/DV < 0.8 = Distribusi
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    df['up_volume'] = np.where(df['close_price'] > df['open_price'], df['volume'], 0)
    df['down_volume'] = np.where(df['close_price'] < df['open_price'], df['volume'], 0)

    total_up = df['up_volume'].sum()
    total_down = df['down_volume'].sum()

    uvdv_ratio = total_up / total_down if total_down > 0 else float('inf')

    # Scoring
    if uvdv_ratio > PARAMS['uvdv_accum_threshold']:
        signal = 'AKUMULASI'
        score = 1
    elif uvdv_ratio < PARAMS['uvdv_distrib_threshold']:
        signal = 'DISTRIBUSI'
        score = -1
    else:
        signal = 'NETRAL'
        score = 0

    return {
        'total_up_volume': total_up,
        'total_down_volume': total_down,
        'uvdv_ratio': round(uvdv_ratio, 3),
        'signal': signal,
        'score': score
    }


# ============================================================
# INDIKATOR 3: VRPR (Volume Relative to Price Range)
# ============================================================
def calculate_vrpr(price_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    VRPR = Average Volume / (High - Low)

    Mengukur: volume besar tapi harga tidak bergerak = ada tangan besar
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    df['range'] = df['high_price'] - df['low_price']
    df['vrpr'] = np.where(df['range'] > 0, df['volume'] / df['range'], 0)

    avg_vrpr = df['vrpr'].mean()
    vrpr_trend = df['vrpr'].diff().mean()

    # Hitung VRPR relatif terhadap periode sebelumnya
    # (untuk ini kita perlu data sebelum sideways)

    return {
        'avg_vrpr': round(avg_vrpr, 0),
        'vrpr_trend': round(vrpr_trend, 2),
        'interpretation': 'VRPR tinggi + range sempit = ada akumulasi/distribusi tersembunyi'
    }


# ============================================================
# INDIKATOR 4: Broker Influence Score (BIS)
# ============================================================
def calculate_broker_influence(broker_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Broker Influence Score = Net_Value × Participation

    Dimana:
    - Net_Value = Buy_Value - Sell_Value
    - Participation = (Buy_Value + Sell_Value) / Total_Market_Value
    """
    df = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)].copy()

    if df.empty:
        return {'top_accumulators': [], 'top_distributors': [], 'net_influence': 0}

    # Hitung per broker
    broker_stats = df.groupby('broker_code').agg({
        'buy_value': 'sum',
        'sell_value': 'sum',
        'net_value': 'sum',
        'net_lot': 'sum'
    }).reset_index()

    total_market_value = (broker_stats['buy_value'] + broker_stats['sell_value']).sum()

    broker_stats['participation'] = (broker_stats['buy_value'] + broker_stats['sell_value']) / total_market_value
    broker_stats['influence_score'] = broker_stats['net_value'] * broker_stats['participation']

    # Sort by influence
    broker_stats = broker_stats.sort_values('influence_score', ascending=False)

    # Top accumulators (influence positif)
    top_accum = broker_stats[broker_stats['influence_score'] > 0].head(5)
    top_distrib = broker_stats[broker_stats['influence_score'] < 0].head(5)

    # Net influence keseluruhan
    net_influence = broker_stats['influence_score'].sum()

    return {
        'top_accumulators': top_accum[['broker_code', 'net_value', 'net_lot', 'participation', 'influence_score']].to_dict('records'),
        'top_distributors': top_distrib[['broker_code', 'net_value', 'net_lot', 'participation', 'influence_score']].to_dict('records'),
        'net_influence': net_influence,
        'signal': 'AKUMULASI' if net_influence > 0 else 'DISTRIBUSI',
        'score': 1 if net_influence > 0 else -1
    }


# ============================================================
# INDIKATOR 5: Broker Persistence
# ============================================================
def calculate_broker_persistence(broker_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Persistence = jumlah hari konsisten net buy/sell

    Interpretasi:
    - >= 5 hari = mulai ada niat
    - >= 10 hari = terencana
    - >= 15 hari = institusional
    """
    df = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)].copy()

    if df.empty:
        return {'persistent_accumulators': [], 'persistent_distributors': []}

    # Hitung per broker per hari
    daily_broker = df.groupby(['broker_code', 'date']).agg({
        'net_lot': 'sum',
        'net_value': 'sum'
    }).reset_index()

    persistence_stats = []

    for broker in daily_broker['broker_code'].unique():
        broker_data = daily_broker[daily_broker['broker_code'] == broker].sort_values('date')

        # Hitung hari akumulasi dan distribusi
        accum_days = len(broker_data[broker_data['net_lot'] > 0])
        distrib_days = len(broker_data[broker_data['net_lot'] < 0])
        total_days = len(broker_data)

        # Hitung consecutive days (streak)
        net_lots = broker_data['net_lot'].values
        max_accum_streak = 0
        max_distrib_streak = 0
        current_accum = 0
        current_distrib = 0

        for nl in net_lots:
            if nl > 0:
                current_accum += 1
                current_distrib = 0
                max_accum_streak = max(max_accum_streak, current_accum)
            elif nl < 0:
                current_distrib += 1
                current_accum = 0
                max_distrib_streak = max(max_distrib_streak, current_distrib)
            else:
                current_accum = 0
                current_distrib = 0

        total_net_lot = broker_data['net_lot'].sum()
        total_net_value = broker_data['net_value'].sum()

        persistence_stats.append({
            'broker_code': broker,
            'accum_days': accum_days,
            'distrib_days': distrib_days,
            'total_days': total_days,
            'accum_pct': accum_days / total_days * 100 if total_days > 0 else 0,
            'max_accum_streak': max_accum_streak,
            'max_distrib_streak': max_distrib_streak,
            'total_net_lot': total_net_lot,
            'total_net_value': total_net_value
        })

    # Sort by persistence
    persistence_df = pd.DataFrame(persistence_stats)

    # Top persistent accumulators
    accum_sorted = persistence_df[persistence_df['total_net_lot'] > 0].sort_values(
        ['max_accum_streak', 'accum_days'], ascending=False
    ).head(5)

    # Top persistent distributors
    distrib_sorted = persistence_df[persistence_df['total_net_lot'] < 0].sort_values(
        ['max_distrib_streak', 'distrib_days'], ascending=False
    ).head(5)

    return {
        'persistent_accumulators': accum_sorted.to_dict('records'),
        'persistent_distributors': distrib_sorted.to_dict('records')
    }


# ============================================================
# INDIKATOR 6: Absorption Detection (Early Accumulation)
# ============================================================
def calculate_absorption(price_df: pd.DataFrame, broker_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Absorption = Sell besar diserap tanpa breakdown

    Ciri:
    - Sell value tinggi
    - Range sempit
    - Close tetap stabil
    """
    pdf = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()
    bdf = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)].copy()

    if pdf.empty or bdf.empty:
        return {'absorption_score': 0, 'is_absorbing': False}

    # Hitung total sell value dan range
    total_sell = bdf['sell_value'].sum()
    avg_range = (pdf['high_price'] - pdf['low_price']).mean()

    # Absorption ratio
    absorption_ratio = total_sell / avg_range if avg_range > 0 else 0

    # Cek apakah close tetap stabil (tidak breakdown)
    first_close = pdf.iloc[0]['close_price']
    last_close = pdf.iloc[-1]['close_price']
    close_change_pct = (last_close - first_close) / first_close * 100

    # High absorption + stable close = akumulasi
    is_absorbing = absorption_ratio > 0 and close_change_pct > -3

    return {
        'total_sell_value': total_sell,
        'avg_range': avg_range,
        'absorption_ratio': round(absorption_ratio, 0),
        'close_change_pct': round(close_change_pct, 2),
        'is_absorbing': is_absorbing,
        'interpretation': 'Sell diserap tanpa breakdown' if is_absorbing else 'Tidak ada absorption'
    }


# ============================================================
# INDIKATOR 7: Smart Money Divergence
# ============================================================
def calculate_smart_money_divergence(price_df: pd.DataFrame, broker_df: pd.DataFrame,
                                      start_date, end_date, sensitive_brokers: list) -> dict:
    """
    Korelasi antara Net Broker Flow vs Price Change

    - Net buy ↑, harga flat → Akumulasi tersembunyi
    - Net sell ↑, harga flat → Distribusi diam-diam
    """
    pdf = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()
    bdf = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)]

    if len(sensitive_brokers) > 0:
        bdf = bdf[bdf['broker_code'].isin(sensitive_brokers)]

    if pdf.empty or bdf.empty:
        return {'divergence': 0, 'signal': 'UNKNOWN'}

    # Aggregate daily broker flow
    daily_flow = bdf.groupby('date').agg({'net_lot': 'sum', 'net_value': 'sum'}).reset_index()

    # Merge dengan price
    merged = pdf.merge(daily_flow, on='date', how='left')
    merged['net_lot'] = merged['net_lot'].fillna(0)
    merged['price_change'] = merged['close_price'].pct_change() * 100

    # Hitung korelasi
    valid_data = merged.dropna(subset=['price_change'])
    if len(valid_data) > 3:
        correlation = valid_data['net_lot'].corr(valid_data['price_change'])
    else:
        correlation = 0

    # Total net flow
    total_net_lot = merged['net_lot'].sum()
    total_price_change = (merged.iloc[-1]['close_price'] - merged.iloc[0]['close_price']) / merged.iloc[0]['close_price'] * 100

    # Divergence detection
    if total_net_lot > 0 and abs(total_price_change) < 5:
        signal = 'AKUMULASI TERSEMBUNYI'
        score = 1
    elif total_net_lot < 0 and abs(total_price_change) < 5:
        signal = 'DISTRIBUSI DIAM-DIAM'
        score = -1
    else:
        signal = 'SINKRON'
        score = 0

    return {
        'correlation': round(correlation, 3) if not np.isnan(correlation) else 0,
        'total_net_lot': total_net_lot,
        'total_price_change_pct': round(total_price_change, 2),
        'signal': signal,
        'score': score
    }


# ============================================================
# SCORING SYSTEM TERINTEGRASI
# ============================================================
def calculate_final_score(cpr_result, uvdv_result, broker_influence, divergence_result) -> dict:
    """
    Sistem skoring:
    - CPR: 30%
    - UV/DV: 25%
    - Broker Influence: 25%
    - Smart Money Divergence: 20%

    Score +3 s/d +5 = AKUMULASI
    Score -3 s/d -5 = DISTRIBUSI
    """
    weights = {
        'cpr': 0.30,
        'uvdv': 0.25,
        'broker_influence': 0.25,
        'divergence': 0.20
    }

    scores = {
        'cpr': cpr_result.get('score', 0),
        'uvdv': uvdv_result.get('score', 0),
        'broker_influence': broker_influence.get('score', 0),
        'divergence': divergence_result.get('score', 0)
    }

    # Weighted score
    weighted_score = sum(scores[k] * weights[k] for k in weights)

    # Raw score (sum)
    raw_score = sum(scores.values())

    # Final verdict
    if raw_score >= 3:
        verdict = 'AKUMULASI KUAT'
        confidence = 'HIGH'
    elif raw_score >= 1:
        verdict = 'AKUMULASI'
        confidence = 'MEDIUM'
    elif raw_score <= -3:
        verdict = 'DISTRIBUSI KUAT'
        confidence = 'HIGH'
    elif raw_score <= -1:
        verdict = 'DISTRIBUSI'
        confidence = 'MEDIUM'
    else:
        verdict = 'SIDEWAYS NETRAL'
        confidence = 'LOW'

    return {
        'scores': scores,
        'weights': weights,
        'weighted_score': round(weighted_score, 3),
        'raw_score': raw_score,
        'verdict': verdict,
        'confidence': confidence
    }


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================
def analyze_accumulation_distribution(stock_code: str):
    """Main function untuk analisa akumulasi vs distribusi"""

    print(f"\n{'='*80}")
    print(f"ANALISA AKUMULASI vs DISTRIBUSI: {stock_code}")
    print(f"{'='*80}")

    # Load data
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)
    issued_shares = get_issued_shares(stock_code)

    print(f"\nData Overview:")
    print(f"  - Price data: {len(price_df)} hari ({price_df['date'].min()} s/d {price_df['date'].max()})")
    print(f"  - Broker data: {len(broker_df)} records, {broker_df['broker_code'].nunique()} broker")
    print(f"  - Issued Shares: {issued_shares:,.0f}" if issued_shares else "  - Issued Shares: N/A")

    # Step 1: Identifikasi periode sideways
    print(f"\n{'='*80}")
    print("STEP 1: IDENTIFIKASI PERIODE SIDEWAYS")
    print(f"{'='*80}")
    print(f"Kriteria: Range < {PARAMS['sideways_threshold_pct']}% dalam {PARAMS['sideways_window']} hari")

    sideways_periods, df_with_range = identify_sideways_periods(price_df)

    print(f"\nDitemukan {len(sideways_periods)} periode sideways:")
    for i, sw in enumerate(sideways_periods):
        print(f"  [{i+1}] {sw['start_date'].strftime('%d %b %Y')} - {sw['end_date'].strftime('%d %b %Y')}")
        print(f"      Durasi: {sw['duration']} hari, Range: {sw['range_pct']:.1f}%")
        print(f"      Harga: Rp {sw['low']:,.0f} - Rp {sw['high']:,.0f}")

    # Analisa periode sideways terakhir (atau yang dipilih)
    if not sideways_periods:
        print("\n[WARNING] Tidak ada periode sideways ditemukan!")
        print("Menganalisa 30 hari terakhir sebagai alternatif...")

        # Gunakan 30 hari terakhir
        end_date = price_df['date'].max()
        start_date = end_date - timedelta(days=30)
        analysis_period = {'start_date': start_date, 'end_date': end_date, 'duration': 30}
    else:
        # Gunakan sideways terakhir
        analysis_period = sideways_periods[-1]

    start_date = analysis_period['start_date']
    end_date = analysis_period['end_date']

    print(f"\n{'='*80}")
    print(f"ANALISA PERIODE: {start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}")
    print(f"{'='*80}")

    # Hitung semua indikator
    print(f"\n--- INDIKATOR 1: CPR (Close Position Ratio) ---")
    cpr_result = calculate_cpr(price_df, start_date, end_date)
    print(f"  Avg CPR: {cpr_result['avg_cpr']:.3f}")
    print(f"  CPR Trend: {cpr_result['cpr_trend']:+.4f}")
    print(f"  Signal: {cpr_result['signal']} (Score: {cpr_result['score']:+d})")

    print(f"\n--- INDIKATOR 2: UV/DV (Up/Down Volume Ratio) ---")
    uvdv_result = calculate_uvdv(price_df, start_date, end_date)
    print(f"  Up Volume: {uvdv_result['total_up_volume']:,.0f}")
    print(f"  Down Volume: {uvdv_result['total_down_volume']:,.0f}")
    print(f"  UV/DV Ratio: {uvdv_result['uvdv_ratio']:.3f}")
    print(f"  Signal: {uvdv_result['signal']} (Score: {uvdv_result['score']:+d})")

    print(f"\n--- INDIKATOR 3: VRPR (Volume/Price Range) ---")
    vrpr_result = calculate_vrpr(price_df, start_date, end_date)
    print(f"  Avg VRPR: {vrpr_result['avg_vrpr']:,.0f}")
    print(f"  VRPR Trend: {vrpr_result['vrpr_trend']:+,.0f}")
    print(f"  Note: {vrpr_result['interpretation']}")

    print(f"\n--- INDIKATOR 4: BROKER INFLUENCE SCORE ---")
    broker_influence = calculate_broker_influence(broker_df, start_date, end_date)
    print(f"  Net Influence: {broker_influence['net_influence']:,.0f}")
    print(f"  Signal: {broker_influence['signal']} (Score: {broker_influence['score']:+d})")
    print(f"\n  Top Accumulators:")
    for b in broker_influence['top_accumulators'][:3]:
        print(f"    {b['broker_code']}: Net {b['net_lot']:+,.0f} lot, Influence {b['influence_score']:,.0f}")
    print(f"\n  Top Distributors:")
    for b in broker_influence['top_distributors'][:3]:
        print(f"    {b['broker_code']}: Net {b['net_lot']:+,.0f} lot, Influence {b['influence_score']:,.0f}")

    print(f"\n--- INDIKATOR 5: BROKER PERSISTENCE ---")
    persistence = calculate_broker_persistence(broker_df, start_date, end_date)
    print(f"  Persistent Accumulators:")
    for b in persistence['persistent_accumulators'][:3]:
        print(f"    {b['broker_code']}: {b['accum_days']}/{b['total_days']} hari akum, streak {b['max_accum_streak']} hari")
    print(f"\n  Persistent Distributors:")
    for b in persistence['persistent_distributors'][:3]:
        print(f"    {b['broker_code']}: {b['distrib_days']}/{b['total_days']} hari distrib, streak {b['max_distrib_streak']} hari")

    print(f"\n--- INDIKATOR 6: ABSORPTION DETECTION ---")
    absorption = calculate_absorption(price_df, broker_df, start_date, end_date)
    print(f"  Total Sell Value: Rp {absorption['total_sell_value']/1e9:,.2f} Miliar")
    print(f"  Avg Range: Rp {absorption['avg_range']:,.0f}")
    print(f"  Absorption Ratio: {absorption['absorption_ratio']:,.0f}")
    print(f"  Close Change: {absorption['close_change_pct']:+.2f}%")
    print(f"  Is Absorbing: {'YA' if absorption['is_absorbing'] else 'TIDAK'}")

    print(f"\n--- INDIKATOR 7: SMART MONEY DIVERGENCE ---")
    # Ambil top 5 broker dengan influence tertinggi
    sensitive_brokers = [b['broker_code'] for b in broker_influence['top_accumulators'][:5]]
    divergence = calculate_smart_money_divergence(price_df, broker_df, start_date, end_date, sensitive_brokers)
    print(f"  Broker Flow vs Price Correlation: {divergence['correlation']:.3f}")
    print(f"  Total Net Lot: {divergence['total_net_lot']:+,.0f}")
    print(f"  Total Price Change: {divergence['total_price_change_pct']:+.2f}%")
    print(f"  Signal: {divergence['signal']} (Score: {divergence['score']:+d})")

    # Final Scoring
    print(f"\n{'='*80}")
    print("FINAL SCORING")
    print(f"{'='*80}")

    final_score = calculate_final_score(cpr_result, uvdv_result, broker_influence, divergence)

    print(f"\n  Component Scores:")
    print(f"    CPR Score:              {final_score['scores']['cpr']:+d} (weight: {final_score['weights']['cpr']*100:.0f}%)")
    print(f"    UV/DV Score:            {final_score['scores']['uvdv']:+d} (weight: {final_score['weights']['uvdv']*100:.0f}%)")
    print(f"    Broker Influence Score: {final_score['scores']['broker_influence']:+d} (weight: {final_score['weights']['broker_influence']*100:.0f}%)")
    print(f"    Divergence Score:       {final_score['scores']['divergence']:+d} (weight: {final_score['weights']['divergence']*100:.0f}%)")

    print(f"\n  Raw Score: {final_score['raw_score']:+d}")
    print(f"  Weighted Score: {final_score['weighted_score']:+.3f}")

    print(f"\n{'='*80}")
    print(f"  >>> VERDICT: {final_score['verdict']} <<<")
    print(f"  >>> CONFIDENCE: {final_score['confidence']} <<<")
    print(f"{'='*80}")

    return {
        'stock_code': stock_code,
        'analysis_period': {'start': start_date, 'end': end_date},
        'sideways_periods': sideways_periods,
        'indicators': {
            'cpr': cpr_result,
            'uvdv': uvdv_result,
            'vrpr': vrpr_result,
            'broker_influence': broker_influence,
            'persistence': persistence,
            'absorption': absorption,
            'divergence': divergence
        },
        'final_score': final_score
    }


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    result = analyze_accumulation_distribution('NCKL')
