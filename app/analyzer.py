"""
Analyzer untuk deteksi sideways, breakout, dan korelasi broker
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from database import get_cursor, execute_query

# ============================================================
# PARAMETER KONFIGURASI
# ============================================================
SIDEWAYS_RANGE_PERCENT = 5.0  # Range maksimal untuk sideways (%)
SIDEWAYS_MIN_DAYS = 7         # Durasi minimal sideways (hari)
BREAKOUT_BUFFER_PERCENT = 1.0 # Buffer untuk konfirmasi breakout (%)
VOLUME_SPIKE_RATIO = 1.5      # Rasio volume untuk konfirmasi breakout
ACCUMULATION_MIN_DAYS = 3     # Minimal hari net buy berturut untuk akumulasi

# ============================================================
# DATA RETRIEVAL
# ============================================================
def get_price_data(stock_code: str = 'CDIA', days: int = 180) -> pd.DataFrame:
    """Ambil data harga dari database"""
    query = """
        SELECT date, open_price, high_price, low_price, close_price,
               volume, value, net_foreign
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date
    """
    results = execute_query(query, (stock_code,))
    df = pd.DataFrame(results)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        # Convert numeric columns
        numeric_cols = ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 'value', 'net_foreign']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def get_broker_data(stock_code: str = 'CDIA') -> pd.DataFrame:
    """Ambil data broker dari database"""
    query = """
        SELECT date, broker_code, buy_value, sell_value, net_value,
               buy_lot, sell_lot, net_lot
        FROM broker_summary
        WHERE stock_code = %s
        ORDER BY date, net_value DESC
    """
    results = execute_query(query, (stock_code,))
    df = pd.DataFrame(results)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        # Convert numeric columns
        numeric_cols = ['buy_value', 'sell_value', 'net_value', 'buy_lot', 'sell_lot', 'net_lot']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# ============================================================
# SIDEWAYS & BREAKOUT DETECTION
# ============================================================
def detect_sideways_zones(price_df: pd.DataFrame) -> List[Dict]:
    """
    Deteksi zona sideways dalam data harga
    Kriteria: range < SIDEWAYS_RANGE_PERCENT% selama minimal SIDEWAYS_MIN_DAYS hari
    """
    if price_df.empty or len(price_df) < SIDEWAYS_MIN_DAYS:
        return []

    zones = []
    i = 0

    while i < len(price_df) - SIDEWAYS_MIN_DAYS + 1:
        # Cek window dari posisi i
        for window_size in range(SIDEWAYS_MIN_DAYS, len(price_df) - i + 1):
            window = price_df.iloc[i:i + window_size]
            high = window['high_price'].max()
            low = window['low_price'].min()
            range_pct = ((high - low) / low) * 100 if low > 0 else 0

            # Jika range masih dalam batas sideways, extend window
            if range_pct <= SIDEWAYS_RANGE_PERCENT:
                continue
            else:
                # Window sebelumnya adalah zona sideways
                if window_size > SIDEWAYS_MIN_DAYS:
                    sideways_window = price_df.iloc[i:i + window_size - 1]
                    zone = {
                        'start_date': sideways_window['date'].iloc[0],
                        'end_date': sideways_window['date'].iloc[-1],
                        'support': sideways_window['low_price'].min(),
                        'resistance': sideways_window['high_price'].max(),
                        'range_percent': ((sideways_window['high_price'].max() -
                                          sideways_window['low_price'].min()) /
                                          sideways_window['low_price'].min()) * 100,
                        'duration_days': len(sideways_window),
                        'status': 'completed'
                    }

                    # Cek breakout setelah zona sideways
                    if i + window_size < len(price_df):
                        next_day = price_df.iloc[i + window_size - 1]
                        if next_day['close_price'] > zone['resistance'] * (1 + BREAKOUT_BUFFER_PERCENT/100):
                            zone['status'] = 'breakout_up'
                            zone['breakout_date'] = next_day['date']
                            zone['breakout_price'] = next_day['close_price']
                        elif next_day['close_price'] < zone['support'] * (1 - BREAKOUT_BUFFER_PERCENT/100):
                            zone['status'] = 'breakout_down'
                            zone['breakout_date'] = next_day['date']
                            zone['breakout_price'] = next_day['close_price']

                    zones.append(zone)
                    i = i + window_size - 1
                break
        else:
            # Seluruh sisa data adalah sideways
            sideways_window = price_df.iloc[i:]
            if len(sideways_window) >= SIDEWAYS_MIN_DAYS:
                zone = {
                    'start_date': sideways_window['date'].iloc[0],
                    'end_date': sideways_window['date'].iloc[-1],
                    'support': sideways_window['low_price'].min(),
                    'resistance': sideways_window['high_price'].max(),
                    'range_percent': ((sideways_window['high_price'].max() -
                                      sideways_window['low_price'].min()) /
                                      sideways_window['low_price'].min()) * 100,
                    'duration_days': len(sideways_window),
                    'status': 'ongoing'
                }
                zones.append(zone)
            break

        i += 1

    return zones

def find_current_market_phase(price_df: pd.DataFrame) -> Dict:
    """
    Tentukan fase market saat ini (sideways/uptrend/downtrend)
    """
    if price_df.empty or len(price_df) < SIDEWAYS_MIN_DAYS:
        return {'phase': 'unknown', 'details': {}}

    # Ambil data terakhir (7-14 hari)
    recent = price_df.tail(14)
    high = recent['high_price'].max()
    low = recent['low_price'].min()
    range_pct = ((high - low) / low) * 100 if low > 0 else 0

    # Hitung trend
    first_close = recent['close_price'].iloc[0]
    last_close = recent['close_price'].iloc[-1]
    change_pct = ((last_close - first_close) / first_close) * 100

    if range_pct <= SIDEWAYS_RANGE_PERCENT:
        phase = 'sideways'
    elif change_pct > 3:
        phase = 'uptrend'
    elif change_pct < -3:
        phase = 'downtrend'
    else:
        phase = 'sideways'

    return {
        'phase': phase,
        'details': {
            'range_percent': round(range_pct, 2),
            'change_percent': round(change_pct, 2),
            'support': low,
            'resistance': high,
            'current_price': last_close,
            'days_analyzed': len(recent)
        }
    }

# ============================================================
# BROKER ANALYSIS
# ============================================================
def analyze_broker_accumulation(broker_df: pd.DataFrame, stock_code: str = 'CDIA') -> pd.DataFrame:
    """
    Analisis pola akumulasi per broker
    Menghitung streak net buy dan total akumulasi
    """
    if broker_df.empty:
        return pd.DataFrame()

    results = []

    for broker in broker_df['broker_code'].unique():
        broker_data = broker_df[broker_df['broker_code'] == broker].sort_values('date')

        # Hitung streak net buy
        streak = 0
        max_streak = 0
        streak_start = None
        current_streak_start = None
        total_net = 0
        accumulation_periods = []

        for _, row in broker_data.iterrows():
            if row['net_value'] > 0:
                if streak == 0:
                    current_streak_start = row['date']
                streak += 1
                total_net += row['net_value']
                max_streak = max(max_streak, streak)
            else:
                if streak >= ACCUMULATION_MIN_DAYS:
                    accumulation_periods.append({
                        'start': current_streak_start,
                        'end': row['date'],
                        'days': streak,
                        'total': total_net
                    })
                streak = 0
                total_net = 0

        # Cek streak terakhir
        if streak >= ACCUMULATION_MIN_DAYS:
            accumulation_periods.append({
                'start': current_streak_start,
                'end': broker_data['date'].iloc[-1],
                'days': streak,
                'total': total_net,
                'ongoing': True
            })

        # Summary statistics
        total_buy = broker_data['buy_value'].sum()
        total_sell = broker_data['sell_value'].sum()
        total_net_all = broker_data['net_value'].sum()
        days_net_buy = len(broker_data[broker_data['net_value'] > 0])
        days_net_sell = len(broker_data[broker_data['net_value'] < 0])

        results.append({
            'broker_code': broker,
            'total_buy': total_buy,
            'total_sell': total_sell,
            'total_net': total_net_all,
            'days_active': len(broker_data),
            'days_net_buy': days_net_buy,
            'days_net_sell': days_net_sell,
            'buy_ratio': days_net_buy / len(broker_data) if len(broker_data) > 0 else 0,
            'max_streak': max_streak,
            'accumulation_periods': len(accumulation_periods),
            'current_streak': streak if streak >= ACCUMULATION_MIN_DAYS else 0
        })

    return pd.DataFrame(results).sort_values('total_net', ascending=False)

def get_top_accumulators(broker_df: pd.DataFrame, date: datetime = None, top_n: int = 10) -> pd.DataFrame:
    """
    Dapatkan top broker accumulator untuk tanggal tertentu atau overall
    """
    if broker_df.empty:
        return pd.DataFrame()

    if date:
        daily = broker_df[broker_df['date'] == date]
    else:
        # Overall summary
        daily = broker_df.groupby('broker_code').agg({
            'buy_value': 'sum',
            'sell_value': 'sum',
            'net_value': 'sum',
            'buy_lot': 'sum',
            'sell_lot': 'sum',
            'net_lot': 'sum'
        }).reset_index()

    return daily.nlargest(top_n, 'net_value')

def get_top_distributors(broker_df: pd.DataFrame, date: datetime = None, top_n: int = 10) -> pd.DataFrame:
    """
    Dapatkan top broker distributor untuk tanggal tertentu atau overall
    """
    if broker_df.empty:
        return pd.DataFrame()

    if date:
        daily = broker_df[broker_df['date'] == date]
    else:
        # Overall summary
        daily = broker_df.groupby('broker_code').agg({
            'buy_value': 'sum',
            'sell_value': 'sum',
            'net_value': 'sum',
            'buy_lot': 'sum',
            'sell_lot': 'sum',
            'net_lot': 'sum'
        }).reset_index()

    return daily.nsmallest(top_n, 'net_value')

# ============================================================
# DYNAMIC PARAMETER CALCULATION
# ============================================================
def calculate_optimal_lookback_days(stock_code: str = 'CDIA') -> Dict:
    """
    Hitung parameter lookback optimal berdasarkan data historis.
    Menganalisis berapa hari sebelum uptrend broker biasanya mulai akumulasi.

    Returns:
        Dict dengan optimal_days, stats, dan detail analisis
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or broker_df.empty:
        return {
            'optimal_days': 10,  # Default fallback
            'method': 'default',
            'reason': 'Insufficient data'
        }

    price_df = price_df.sort_values('date').reset_index(drop=True)

    # 1. Identifikasi periode uptrend (kenaikan >= 5% dalam 5-15 hari)
    uptrend_periods = []
    i = 0
    while i < len(price_df) - 5:
        start_price = price_df.loc[i, 'close_price']

        for j in range(i + 5, min(i + 16, len(price_df))):
            end_price = price_df.loc[j, 'close_price']
            change_pct = ((end_price - start_price) / start_price) * 100

            if change_pct >= 5:
                uptrend_periods.append({
                    'start_date': price_df.loc[i, 'date'],
                    'end_date': price_df.loc[j, 'date'],
                    'start_idx': i,
                    'change_pct': change_pct
                })
                i = j
                break
        i += 1

    if not uptrend_periods:
        return {
            'optimal_days': 10,
            'method': 'default',
            'reason': 'No uptrend periods found',
            'uptrend_count': 0
        }

    # 2. Untuk setiap uptrend, cari kapan broker mulai akumulasi
    accumulation_starts = []

    for period in uptrend_periods:
        uptrend_start = period['start_date']

        # Cek berbagai lookback window (5-20 hari sebelum uptrend)
        for lookback in range(5, 21):
            lookback_start = uptrend_start - timedelta(days=lookback + 5)
            lookback_end = uptrend_start - timedelta(days=lookback - 5)

            pre_brokers = broker_df[
                (broker_df['date'] >= lookback_start) &
                (broker_df['date'] < lookback_end)
            ]

            if pre_brokers.empty:
                continue

            # Hitung total net buy dalam periode ini
            total_net = pre_brokers.groupby('broker_code')['net_value'].sum()
            accumulating_brokers = len(total_net[total_net > 0])

            if accumulating_brokers >= 5:  # Minimal 5 broker akumulasi
                accumulation_starts.append({
                    'uptrend_date': uptrend_start,
                    'lookback_days': lookback,
                    'accumulating_brokers': accumulating_brokers,
                    'total_net': total_net[total_net > 0].sum()
                })

    if not accumulation_starts:
        return {
            'optimal_days': 10,
            'method': 'default',
            'reason': 'Cannot detect accumulation pattern',
            'uptrend_count': len(uptrend_periods)
        }

    # 3. Analisis statistik untuk menentukan optimal lookback
    lookback_days = [a['lookback_days'] for a in accumulation_starts]

    # Hitung berbagai statistik
    mean_days = np.mean(lookback_days)
    median_days = np.median(lookback_days)
    std_days = np.std(lookback_days)
    min_days = min(lookback_days)
    max_days = max(lookback_days)

    # Mode (nilai paling sering muncul)
    from collections import Counter
    mode_counter = Counter(lookback_days)
    mode_days = mode_counter.most_common(1)[0][0]

    # Pilih optimal: gunakan median (lebih robust terhadap outlier)
    optimal_days = int(round(median_days))

    # Pastikan dalam range wajar (7-15 hari)
    optimal_days = max(7, min(15, optimal_days))

    return {
        'optimal_days': optimal_days,
        'method': 'calculated_from_data',
        'stats': {
            'mean': round(mean_days, 1),
            'median': round(median_days, 1),
            'mode': mode_days,
            'std': round(std_days, 1),
            'min': min_days,
            'max': max_days,
            'sample_size': len(lookback_days)
        },
        'uptrend_count': len(uptrend_periods),
        'accumulation_patterns': len(accumulation_starts),
        'recommendation': f"Berdasarkan {len(uptrend_periods)} periode uptrend historis, "
                         f"broker umumnya mulai akumulasi {optimal_days} hari sebelum harga naik "
                         f"(median: {median_days:.0f} hari, range: {min_days}-{max_days} hari)"
    }


# ============================================================
# CORRELATION ANALYSIS
# ============================================================
def analyze_broker_breakout_correlation(price_df: pd.DataFrame, broker_df: pd.DataFrame,
                                        stock_code: str = 'CDIA') -> pd.DataFrame:
    """
    Analisis korelasi antara akumulasi broker dengan breakout
    """
    if price_df.empty or broker_df.empty:
        return pd.DataFrame()

    # Deteksi zona sideways dan breakout
    zones = detect_sideways_zones(price_df)
    breakout_zones = [z for z in zones if z['status'] in ['breakout_up', 'breakout_down']]

    if not breakout_zones:
        print("No breakout zones found in price data")
        return pd.DataFrame()

    # Untuk setiap breakout, analisis broker yang akumulasi sebelumnya
    broker_scores = {}

    for zone in breakout_zones:
        if zone['status'] != 'breakout_up':
            continue  # Fokus pada breakout up

        # Filter broker data selama periode sideways
        sideways_brokers = broker_df[
            (broker_df['date'] >= zone['start_date']) &
            (broker_df['date'] <= zone['end_date'])
        ]

        # Hitung net accumulation per broker selama sideways
        broker_accum = sideways_brokers.groupby('broker_code').agg({
            'net_value': 'sum',
            'net_lot': 'sum',
            'date': 'count'
        }).reset_index()
        broker_accum.columns = ['broker_code', 'total_net', 'total_lot', 'days_active']

        # Hitung hari net buy
        for _, row in broker_accum.iterrows():
            broker = row['broker_code']
            broker_daily = sideways_brokers[sideways_brokers['broker_code'] == broker]
            days_net_buy = len(broker_daily[broker_daily['net_value'] > 0])

            if broker not in broker_scores:
                broker_scores[broker] = {
                    'broker_code': broker,
                    'breakouts_participated': 0,
                    'total_accumulation': 0,
                    'total_days_before': 0,
                    'avg_accumulation': 0
                }

            if row['total_net'] > 0:  # Broker was accumulating
                broker_scores[broker]['breakouts_participated'] += 1
                broker_scores[broker]['total_accumulation'] += row['total_net']
                broker_scores[broker]['total_days_before'] += days_net_buy

    # Hitung score
    total_breakouts = len([z for z in breakout_zones if z['status'] == 'breakout_up'])

    results = []
    for broker, data in broker_scores.items():
        if data['breakouts_participated'] > 0:
            participation_rate = data['breakouts_participated'] / total_breakouts
            avg_accum_days = data['total_days_before'] / data['breakouts_participated']
            avg_accum_value = data['total_accumulation'] / data['breakouts_participated']

            # Simple scoring formula
            score = (participation_rate * 40) + \
                    (min(avg_accum_days / 10, 1) * 30) + \
                    (min(avg_accum_value / 50e9, 1) * 30)

            results.append({
                'broker_code': broker,
                'total_breakouts': total_breakouts,
                'breakouts_participated': data['breakouts_participated'],
                'participation_rate': round(participation_rate * 100, 1),
                'avg_accumulation_days': round(avg_accum_days, 1),
                'avg_accumulation_value': avg_accum_value,
                'sensitivity_score': round(score, 1)
            })

    return pd.DataFrame(results).sort_values('sensitivity_score', ascending=False)

# ============================================================
# ALERT GENERATION
# ============================================================
def check_accumulation_alerts(broker_df: pd.DataFrame, stock_code: str = 'CDIA') -> List[Dict]:
    """
    Cek apakah ada pola akumulasi yang perlu di-alert
    """
    alerts = []

    if broker_df.empty:
        return alerts

    # Ambil data 7 hari terakhir
    recent_dates = broker_df['date'].unique()
    recent_dates = sorted(recent_dates)[-7:]

    recent = broker_df[broker_df['date'].isin(recent_dates)]

    # Cek setiap broker untuk streak net buy
    for broker in recent['broker_code'].unique():
        broker_recent = recent[recent['broker_code'] == broker].sort_values('date')

        # Hitung streak
        streak = 0
        total_net = 0

        for _, row in broker_recent.iterrows():
            if row['net_value'] > 0:
                streak += 1
                total_net += row['net_value']
            else:
                break

        if streak >= ACCUMULATION_MIN_DAYS:
            alerts.append({
                'type': 'accumulation_detected',
                'broker_code': broker,
                'streak_days': streak,
                'total_net_value': total_net,
                'message': f"Broker {broker} akumulasi {streak} hari berturut-turut, "
                          f"total Rp {total_net/1e9:.1f} Miliar"
            })

    return alerts

# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================
def run_full_analysis(stock_code: str = 'CDIA') -> Dict:
    """
    Jalankan analisis lengkap
    """
    print(f"Running full analysis for {stock_code}...")

    # Get data
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    print(f"Price data: {len(price_df)} records")
    print(f"Broker data: {len(broker_df)} records")

    results = {
        'stock_code': stock_code,
        'analysis_date': datetime.now(),
        'price_data_range': {
            'start': price_df['date'].min() if not price_df.empty else None,
            'end': price_df['date'].max() if not price_df.empty else None,
            'records': len(price_df)
        },
        'broker_data_range': {
            'start': broker_df['date'].min() if not broker_df.empty else None,
            'end': broker_df['date'].max() if not broker_df.empty else None,
            'records': len(broker_df)
        }
    }

    # Market phase
    results['market_phase'] = find_current_market_phase(price_df)

    # Sideways zones
    results['sideways_zones'] = detect_sideways_zones(price_df)

    # Broker analysis
    results['broker_summary'] = analyze_broker_accumulation(broker_df, stock_code)

    # Top accumulators & distributors
    results['top_accumulators'] = get_top_accumulators(broker_df, top_n=10)
    results['top_distributors'] = get_top_distributors(broker_df, top_n=10)

    # Correlation analysis
    results['broker_sensitivity'] = analyze_broker_breakout_correlation(price_df, broker_df, stock_code)

    # Alerts
    results['alerts'] = check_accumulation_alerts(broker_df, stock_code)

    return results

def print_analysis_report(results: Dict):
    """Print analysis results"""
    print("\n" + "=" * 70)
    print(f"CDIA BROKER-PRICE ANALYSIS REPORT")
    print(f"Generated: {results['analysis_date']}")
    print("=" * 70)

    # Market Phase
    phase = results['market_phase']
    print(f"\n[MARKET PHASE] {phase['phase'].upper()}")
    if phase['details']:
        print(f"   Range: {phase['details'].get('range_percent', 0):.1f}%")
        print(f"   Change: {phase['details'].get('change_percent', 0):.1f}%")
        print(f"   Support: {phase['details'].get('support', 0):,.0f}")
        print(f"   Resistance: {phase['details'].get('resistance', 0):,.0f}")

    # Top Accumulators
    print(f"\n[+] TOP 10 ACCUMULATORS (Overall)")
    print("-" * 50)
    if not results['top_accumulators'].empty:
        for _, row in results['top_accumulators'].head(10).iterrows():
            print(f"   {row['broker_code']:5} Net: Rp {row['net_value']/1e9:>8.1f}B")

    # Top Distributors
    print(f"\n[-] TOP 10 DISTRIBUTORS (Overall)")
    print("-" * 50)
    if not results['top_distributors'].empty:
        for _, row in results['top_distributors'].head(10).iterrows():
            print(f"   {row['broker_code']:5} Net: Rp {row['net_value']/1e9:>8.1f}B")

    # Alerts
    if results['alerts']:
        print(f"\n[!] ALERTS")
        print("-" * 50)
        for alert in results['alerts']:
            print(f"   {alert['message']}")

    print("\n" + "=" * 70)

def analyze_broker_price_correlation(stock_code: str = 'CDIA', lookback_days: int = None) -> Dict:
    """
    Analisis korelasi mendalam antara akumulasi broker dan pergerakan harga.

    Args:
        stock_code: Kode saham
        lookback_days: Jumlah hari lookback. Jika None, akan dihitung otomatis dari data.
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or broker_df.empty:
        return {}

    # Hitung optimal lookback days jika tidak dispesifikasi
    if lookback_days is None:
        lookback_params = calculate_optimal_lookback_days(stock_code)
        lookback_days = lookback_params.get('optimal_days', 10)
    else:
        lookback_params = {'optimal_days': lookback_days, 'method': 'manual'}

    results = {
        'stock_code': stock_code,
        'analysis_date': datetime.now(),
        'lookback_params': lookback_params,  # Include parameter info in results
        'price_periods': [],
        'broker_sensitivity': [],
        'current_status': {},
        'historical_patterns': []
    }

    # 1. Identifikasi periode kenaikan harga signifikan (>5% dalam 5-10 hari)
    price_df = price_df.sort_values('date').reset_index(drop=True)

    uptrend_periods = []
    i = 0
    while i < len(price_df) - 5:
        start_price = price_df.loc[i, 'close_price']

        # Cari kenaikan signifikan dalam 5-15 hari ke depan
        for j in range(i + 5, min(i + 16, len(price_df))):
            end_price = price_df.loc[j, 'close_price']
            change_pct = ((end_price - start_price) / start_price) * 100

            if change_pct >= 5:  # Kenaikan minimal 5%
                uptrend_periods.append({
                    'start_date': price_df.loc[i, 'date'],
                    'end_date': price_df.loc[j, 'date'],
                    'start_price': start_price,
                    'end_price': end_price,
                    'change_pct': change_pct,
                    'duration_days': j - i
                })
                i = j  # Skip ke akhir periode ini
                break
        i += 1

    results['uptrend_periods'] = uptrend_periods

    # 2. Untuk setiap periode uptrend, analisis broker yang akumulasi sebelumnya
    broker_patterns = {}

    for period in uptrend_periods:
        # Ambil data broker SEBELUM uptrend dimulai (menggunakan parameter dinamis)
        lookback_start = period['start_date'] - timedelta(days=lookback_days + 5)
        lookback_end = period['start_date']

        pre_uptrend_brokers = broker_df[
            (broker_df['date'] >= lookback_start) &
            (broker_df['date'] < lookback_end)
        ]

        if pre_uptrend_brokers.empty:
            continue

        # Hitung akumulasi per broker sebelum uptrend
        broker_accum = pre_uptrend_brokers.groupby('broker_code').agg({
            'net_value': 'sum',
            'net_lot': 'sum',
            'date': 'count'
        }).reset_index()

        # Filter broker yang net buy (akumulasi)
        accumulators = broker_accum[broker_accum['net_value'] > 0].sort_values('net_value', ascending=False)

        for _, row in accumulators.head(10).iterrows():
            broker = row['broker_code']
            if broker not in broker_patterns:
                broker_patterns[broker] = {
                    'broker_code': broker,
                    'uptrend_participated': 0,
                    'total_pre_accumulation': 0,
                    'accumulation_days_list': [],
                    'uptrend_returns': []
                }

            broker_patterns[broker]['uptrend_participated'] += 1
            broker_patterns[broker]['total_pre_accumulation'] += row['net_value']
            broker_patterns[broker]['accumulation_days_list'].append(row['date'])
            broker_patterns[broker]['uptrend_returns'].append(period['change_pct'])

    # 3. Hitung sensitivity score untuk setiap broker
    total_uptrends = len(uptrend_periods)

    for broker, data in broker_patterns.items():
        if data['uptrend_participated'] > 0:
            participation_rate = data['uptrend_participated'] / max(total_uptrends, 1)
            avg_accum_days = np.mean(data['accumulation_days_list']) if data['accumulation_days_list'] else 0
            avg_return = np.mean(data['uptrend_returns']) if data['uptrend_returns'] else 0

            # Sensitivity Score Formula
            # Higher score = broker yang lebih sering akumulasi sebelum uptrend
            score = (participation_rate * 50) + (min(avg_accum_days / 10, 1) * 25) + (min(avg_return / 10, 1) * 25)

            data['participation_rate'] = participation_rate * 100
            data['avg_accumulation_days'] = avg_accum_days
            data['avg_uptrend_return'] = avg_return
            data['sensitivity_score'] = round(score, 1)

    # Sort by sensitivity score
    results['broker_sensitivity'] = sorted(
        [v for v in broker_patterns.values() if v.get('sensitivity_score', 0) > 0],
        key=lambda x: x['sensitivity_score'],
        reverse=True
    )

    # 4. Analisis kondisi saat ini
    # Ambil data N hari terakhir (berdasarkan parameter dinamis)
    recent_dates = sorted(broker_df['date'].unique())[-lookback_days:]
    recent_brokers = broker_df[broker_df['date'].isin(recent_dates)]

    # Hitung akumulasi recent per broker
    recent_accum = recent_brokers.groupby('broker_code').agg({
        'net_value': 'sum',
        'date': 'count'
    }).reset_index()
    recent_accum.columns = ['broker_code', 'net_value_period', 'days_active']

    # Hitung streak saat ini
    current_accumulators = []
    for broker in recent_accum[recent_accum['net_value_period'] > 0]['broker_code']:
        broker_recent = recent_brokers[recent_brokers['broker_code'] == broker].sort_values('date', ascending=False)

        streak = 0
        for _, row in broker_recent.iterrows():
            if row['net_value'] > 0:
                streak += 1
            else:
                break

        net_period = recent_accum[recent_accum['broker_code'] == broker]['net_value_period'].iloc[0]

        # Check if this broker is sensitive
        sensitivity = next((b for b in results['broker_sensitivity'] if b['broker_code'] == broker), None)

        current_accumulators.append({
            'broker_code': broker,
            'current_streak': streak,
            'net_value_period': net_period,
            'is_sensitive': sensitivity is not None,
            'sensitivity_score': sensitivity['sensitivity_score'] if sensitivity else 0
        })

    current_accumulators.sort(key=lambda x: x['sensitivity_score'], reverse=True)

    # Current price analysis
    if len(price_df) >= lookback_days:
        recent_prices = price_df.tail(lookback_days)
        price_period_change = ((recent_prices['close_price'].iloc[-1] - recent_prices['close_price'].iloc[0]) /
                               recent_prices['close_price'].iloc[0]) * 100
        current_price = recent_prices['close_price'].iloc[-1]
        high_period = recent_prices['high_price'].max()
        low_period = recent_prices['low_price'].min()
    else:
        price_period_change = 0
        current_price = price_df['close_price'].iloc[-1] if not price_df.empty else 0
        high_period = current_price
        low_period = current_price

    results['current_status'] = {
        'lookback_days': lookback_days,
        'current_price': current_price,
        'price_period_change': price_period_change,
        'high_period': high_period,
        'low_period': low_period,
        'current_accumulators': current_accumulators[:15],
        'sensitive_brokers_accumulating': len([a for a in current_accumulators if a['is_sensitive'] and a['current_streak'] >= 3]),
        'total_sensitive_brokers': len(results['broker_sensitivity'])
    }

    # 5. Pattern matching - apakah kondisi saat ini mirip dengan sebelum uptrend historis?
    pattern_match_score = 0
    matching_patterns = []

    sensitive_currently_active = [a['broker_code'] for a in current_accumulators
                                   if a['is_sensitive'] and a['current_streak'] >= 3]

    for period in uptrend_periods:
        lookback_start = period['start_date'] - timedelta(days=lookback_days)
        lookback_end = period['start_date']

        pre_brokers = broker_df[
            (broker_df['date'] >= lookback_start) &
            (broker_df['date'] < lookback_end)
        ]

        pre_accum = pre_brokers.groupby('broker_code')['net_value'].sum()
        pre_accumulators = pre_accum[pre_accum > 0].index.tolist()

        # Hitung overlap dengan kondisi saat ini
        overlap = set(sensitive_currently_active) & set(pre_accumulators)
        if len(overlap) >= 2:
            matching_patterns.append({
                'period': period,
                'matching_brokers': list(overlap),
                'match_count': len(overlap)
            })

    if matching_patterns:
        avg_return_matched = np.mean([p['period']['change_pct'] for p in matching_patterns])
        results['pattern_match'] = {
            'is_matching': True,
            'matching_patterns_count': len(matching_patterns),
            'avg_historical_return': avg_return_matched,
            'matching_brokers': list(set([b for p in matching_patterns for b in p['matching_brokers']])),
            'confidence': min(len(matching_patterns) / max(len(uptrend_periods), 1) * 100, 100)
        }
    else:
        results['pattern_match'] = {
            'is_matching': False,
            'matching_patterns_count': 0,
            'avg_historical_return': 0,
            'matching_brokers': [],
            'confidence': 0
        }

    return results


# ============================================================
# BANDARMOLOGY INDICATORS
# ============================================================

def analyze_price_pressure(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Analisis tekanan beli/jual berdasarkan posisi Close terhadap Avg
    - Close > Avg = buying pressure (smart money accumulating)
    - Close < Avg = selling pressure (distribution)
    - Spread High-Low = volatilitas
    """
    if price_df.empty:
        return pd.DataFrame()

    df = price_df.copy()

    # Calculate pressure
    df['pressure'] = df.apply(
        lambda row: 'buying' if row['close_price'] > row.get('avg_price', row['close_price'])
        else ('selling' if row['close_price'] < row.get('avg_price', row['close_price']) else 'neutral'),
        axis=1
    )

    # Calculate spread (volatility)
    df['spread'] = df['high_price'] - df['low_price']
    df['spread_pct'] = (df['spread'] / df['low_price'] * 100).round(2)

    # Pressure strength: distance from avg
    df['pressure_strength'] = df.apply(
        lambda row: ((row['close_price'] - row.get('avg_price', row['close_price'])) /
                    row.get('avg_price', row['close_price']) * 100)
        if row.get('avg_price', 0) > 0 else 0,
        axis=1
    ).round(2)

    return df


def calculate_foreign_accumulation_index(price_df: pd.DataFrame, days: int = None) -> Dict:
    """
    Foreign Accumulation Index = Σ(Net Foreign) / n hari
    Mengukur rata-rata akumulasi/distribusi oleh investor asing
    """
    if price_df.empty:
        return {'fai': 0, 'trend': 'neutral', 'total_net_foreign': 0, 'days': 0}

    if days:
        df = price_df.tail(days)
    else:
        df = price_df

    total_net_foreign = df['net_foreign'].sum()
    n_days = len(df)
    fai = total_net_foreign / n_days if n_days > 0 else 0

    # Determine trend
    if fai > 1e9:  # > 1B average daily
        trend = 'strong_accumulation'
    elif fai > 0:
        trend = 'accumulation'
    elif fai > -1e9:
        trend = 'distribution'
    else:
        trend = 'strong_distribution'

    # Recent trend (last 5 days vs previous)
    if len(df) >= 10:
        recent_5 = df.tail(5)['net_foreign'].sum() / 5
        prev_5 = df.tail(10).head(5)['net_foreign'].sum() / 5
        momentum = 'increasing' if recent_5 > prev_5 else 'decreasing'
    else:
        momentum = 'unknown'

    return {
        'fai': fai,
        'fai_billion': round(fai / 1e9, 2),
        'trend': trend,
        'momentum': momentum,
        'total_net_foreign': total_net_foreign,
        'total_net_foreign_billion': round(total_net_foreign / 1e9, 2),
        'days': n_days
    }


def calculate_smart_money_indicator(price_df: pd.DataFrame, broker_df: pd.DataFrame) -> pd.DataFrame:
    """
    Smart Money Indicator per hari:
    - Volume tinggi (> avg 20 hari)
    - Frequency rendah (< avg 20 hari) --> transaksi besar, bukan retail
    - Close > Avg --> buying pressure

    Score: 0-100, higher = more smart money activity
    """
    if price_df.empty:
        return pd.DataFrame()

    df = price_df.copy().sort_values('date').reset_index(drop=True)

    # Calculate 20-day rolling averages
    df['vol_avg_20'] = df['volume'].rolling(window=20, min_periods=5).mean()
    df['freq_avg_20'] = df['frequency'].rolling(window=20, min_periods=5).mean() if 'frequency' in df.columns else df['volume']

    # Smart Money conditions
    df['high_volume'] = df['volume'] > df['vol_avg_20']
    df['low_frequency'] = df['frequency'] < df['freq_avg_20'] if 'frequency' in df.columns else False
    df['buying_pressure'] = df['close_price'] > df.get('avg_price', df['close_price'])

    # Calculate Smart Money Score (0-100)
    def calc_smi_score(row):
        score = 0
        # Volume factor (0-40)
        if row['vol_avg_20'] > 0:
            vol_ratio = row['volume'] / row['vol_avg_20']
            score += min(vol_ratio * 20, 40)

        # Frequency factor (0-30) - lower is better for smart money
        if 'frequency' in row.index and row['freq_avg_20'] > 0:
            freq_ratio = row['freq_avg_20'] / max(row['frequency'], 1)
            score += min(freq_ratio * 15, 30)
        else:
            score += 15  # neutral if no freq data

        # Price pressure factor (0-30)
        if row.get('avg_price', 0) > 0:
            pressure = (row['close_price'] - row['avg_price']) / row['avg_price'] * 100
            if pressure > 0:
                score += min(pressure * 10, 30)

        return round(score, 1)

    df['smi_score'] = df.apply(calc_smi_score, axis=1)

    # Smart Money Signal
    df['smi_signal'] = df.apply(
        lambda row: 'STRONG_BUY' if row['smi_score'] >= 70
        else ('BUY' if row['smi_score'] >= 50
        else ('NEUTRAL' if row['smi_score'] >= 30 else 'WEAK')),
        axis=1
    )

    return df


def calculate_distribution_signal(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Distribution Signal per hari:
    - Volume tinggi (> avg 20 hari)
    - Frequency tinggi (> avg 20 hari) --> banyak transaksi kecil (retail)
    - Close < Avg --> selling pressure

    Score: 0-100, higher = more distribution activity
    """
    if price_df.empty:
        return pd.DataFrame()

    df = price_df.copy().sort_values('date').reset_index(drop=True)

    # Calculate 20-day rolling averages
    df['vol_avg_20'] = df['volume'].rolling(window=20, min_periods=5).mean()
    df['freq_avg_20'] = df['frequency'].rolling(window=20, min_periods=5).mean() if 'frequency' in df.columns else df['volume']

    # Distribution conditions
    df['high_volume'] = df['volume'] > df['vol_avg_20']
    df['high_frequency'] = df['frequency'] > df['freq_avg_20'] if 'frequency' in df.columns else False
    df['selling_pressure'] = df['close_price'] < df.get('avg_price', df['close_price'])

    # Calculate Distribution Score (0-100)
    def calc_dist_score(row):
        score = 0
        # Volume factor (0-35)
        if row['vol_avg_20'] > 0:
            vol_ratio = row['volume'] / row['vol_avg_20']
            score += min(vol_ratio * 17.5, 35)

        # Frequency factor (0-35) - higher frequency = more retail = distribution
        if 'frequency' in row.index and row['freq_avg_20'] > 0:
            freq_ratio = row['frequency'] / row['freq_avg_20']
            score += min(freq_ratio * 17.5, 35)
        else:
            score += 17.5  # neutral

        # Price pressure factor (0-30)
        if row.get('avg_price', 0) > 0:
            pressure = (row['avg_price'] - row['close_price']) / row['avg_price'] * 100
            if pressure > 0:
                score += min(pressure * 10, 30)

        return round(score, 1)

    df['dist_score'] = df.apply(calc_dist_score, axis=1)

    # Distribution Signal
    df['dist_signal'] = df.apply(
        lambda row: 'STRONG_DIST' if row['dist_score'] >= 70
        else ('DISTRIBUTION' if row['dist_score'] >= 50
        else ('NEUTRAL' if row['dist_score'] >= 30 else 'WEAK')),
        axis=1
    )

    return df


def calculate_broker_consistency_score(broker_df: pd.DataFrame, stock_code: str = 'CDIA') -> pd.DataFrame:
    """
    Broker Consistency Score:
    - Berapa hari broker X akumulasi berturut-turut
    - Total akumulasi dalam periode konsisten
    - Rata-rata nilai akumulasi harian

    Score: kombinasi streak length + total value + consistency ratio
    """
    if broker_df.empty:
        return pd.DataFrame()

    results = []

    for broker in broker_df['broker_code'].unique():
        broker_data = broker_df[broker_df['broker_code'] == broker].sort_values('date')

        if broker_data.empty:
            continue

        # Calculate current streak
        current_streak = 0
        current_streak_value = 0
        max_streak = 0
        max_streak_value = 0

        # Track all streaks
        streaks = []
        temp_streak = 0
        temp_value = 0

        for _, row in broker_data.iterrows():
            if row['net_value'] > 0:
                temp_streak += 1
                temp_value += row['net_value']
            else:
                if temp_streak >= 3:
                    streaks.append({'days': temp_streak, 'value': temp_value})
                    if temp_streak > max_streak:
                        max_streak = temp_streak
                        max_streak_value = temp_value
                temp_streak = 0
                temp_value = 0

        # Check final streak (current)
        if temp_streak > 0:
            current_streak = temp_streak
            current_streak_value = temp_value
            if temp_streak >= 3:
                streaks.append({'days': temp_streak, 'value': temp_value})
            if temp_streak > max_streak:
                max_streak = temp_streak
                max_streak_value = temp_value

        # Calculate statistics
        total_days = len(broker_data)
        days_net_buy = len(broker_data[broker_data['net_value'] > 0])
        days_net_sell = len(broker_data[broker_data['net_value'] < 0])
        consistency_ratio = days_net_buy / total_days if total_days > 0 else 0

        total_net = broker_data['net_value'].sum()
        avg_daily_net = total_net / total_days if total_days > 0 else 0

        # Calculate Consistency Score (0-100)
        # Components:
        # - Current streak (0-30): longer streak = higher score
        # - Consistency ratio (0-30): more buy days = higher score
        # - Max streak (0-20): historical max streak
        # - Total net (0-20): overall accumulation

        streak_score = min(current_streak * 6, 30)  # 5 days = 30
        ratio_score = consistency_ratio * 30
        max_streak_score = min(max_streak * 4, 20)  # 5 days = 20
        net_score = min(abs(total_net) / 50e9 * 20, 20) if total_net > 0 else 0

        consistency_score = round(streak_score + ratio_score + max_streak_score + net_score, 1)

        results.append({
            'broker_code': broker,
            'current_streak': current_streak,
            'current_streak_value': current_streak_value,
            'max_streak': max_streak,
            'max_streak_value': max_streak_value,
            'total_streaks': len(streaks),
            'total_days': total_days,
            'days_net_buy': days_net_buy,
            'days_net_sell': days_net_sell,
            'consistency_ratio': round(consistency_ratio * 100, 1),
            'total_net': total_net,
            'avg_daily_net': avg_daily_net,
            'consistency_score': consistency_score,
            'status': 'accumulating' if current_streak >= 3 else ('active' if current_streak > 0 else 'idle')
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('consistency_score', ascending=False)

    return df


def get_bandarmology_summary(stock_code: str = 'CDIA', lookback_days: int = None) -> Dict:
    """
    Generate comprehensive Bandarmology summary with all indicators
    """
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    if price_df.empty or broker_df.empty:
        return {}

    # Calculate optimal lookback if not specified
    if lookback_days is None:
        lookback_params = calculate_optimal_lookback_days(stock_code)
        lookback_days = lookback_params.get('optimal_days', 10)

    # 1. Price Pressure Analysis
    pressure_df = analyze_price_pressure(price_df)
    recent_pressure = pressure_df.tail(lookback_days) if not pressure_df.empty else pd.DataFrame()

    if not recent_pressure.empty:
        buying_days = len(recent_pressure[recent_pressure['pressure'] == 'buying'])
        selling_days = len(recent_pressure[recent_pressure['pressure'] == 'selling'])
        avg_spread = recent_pressure['spread_pct'].mean()
        latest_pressure = recent_pressure.iloc[-1]['pressure']
        latest_spread = recent_pressure.iloc[-1]['spread_pct']
    else:
        buying_days = selling_days = 0
        avg_spread = latest_pressure = latest_spread = 0

    # 2. Foreign Accumulation Index
    fai_data = calculate_foreign_accumulation_index(price_df, lookback_days)

    # 3. Smart Money Indicator
    smi_df = calculate_smart_money_indicator(price_df, broker_df)
    recent_smi = smi_df.tail(lookback_days) if not smi_df.empty else pd.DataFrame()

    if not recent_smi.empty:
        avg_smi = recent_smi['smi_score'].mean()
        latest_smi = recent_smi.iloc[-1]['smi_score']
        latest_smi_signal = recent_smi.iloc[-1]['smi_signal']
        strong_buy_days = len(recent_smi[recent_smi['smi_signal'] == 'STRONG_BUY'])
    else:
        avg_smi = latest_smi = 0
        latest_smi_signal = 'UNKNOWN'
        strong_buy_days = 0

    # 4. Distribution Signal
    dist_df = calculate_distribution_signal(price_df)
    recent_dist = dist_df.tail(lookback_days) if not dist_df.empty else pd.DataFrame()

    if not recent_dist.empty:
        avg_dist = recent_dist['dist_score'].mean()
        latest_dist = recent_dist.iloc[-1]['dist_score']
        latest_dist_signal = recent_dist.iloc[-1]['dist_signal']
        strong_dist_days = len(recent_dist[recent_dist['dist_signal'] == 'STRONG_DIST'])
    else:
        avg_dist = latest_dist = 0
        latest_dist_signal = 'UNKNOWN'
        strong_dist_days = 0

    # 5. Broker Consistency Score
    broker_consistency = calculate_broker_consistency_score(broker_df, stock_code)

    # Get top consistent accumulators
    if not broker_consistency.empty:
        top_accumulators = broker_consistency[broker_consistency['status'] == 'accumulating'].head(10)
        active_accumulators = len(broker_consistency[broker_consistency['current_streak'] >= 3])
    else:
        top_accumulators = pd.DataFrame()
        active_accumulators = 0

    # Calculate overall Bandarmology Score (0-100)
    # Weighted combination of all indicators
    bandar_score = 0

    # SMI vs Distribution balance (0-40)
    if avg_smi > avg_dist:
        bandar_score += min((avg_smi - avg_dist) * 0.8, 40)
    else:
        bandar_score -= min((avg_dist - avg_smi) * 0.4, 20)

    # Foreign flow (0-25)
    if fai_data['fai'] > 0:
        bandar_score += min(fai_data['fai_billion'] * 5, 25)
    else:
        bandar_score += max(fai_data['fai_billion'] * 2.5, -12.5)

    # Pressure balance (0-20)
    if buying_days > selling_days:
        bandar_score += min((buying_days - selling_days) * 4, 20)
    else:
        bandar_score -= min((selling_days - buying_days) * 2, 10)

    # Active accumulators (0-15)
    bandar_score += min(active_accumulators * 1.5, 15)

    bandar_score = max(0, min(100, round(bandar_score, 1)))

    # Determine overall signal
    if bandar_score >= 70:
        overall_signal = 'STRONG_ACCUMULATION'
        signal_color = 'success'
    elif bandar_score >= 50:
        overall_signal = 'ACCUMULATION'
        signal_color = 'info'
    elif bandar_score >= 30:
        overall_signal = 'NEUTRAL'
        signal_color = 'secondary'
    elif bandar_score >= 15:
        overall_signal = 'DISTRIBUTION'
        signal_color = 'warning'
    else:
        overall_signal = 'STRONG_DISTRIBUTION'
        signal_color = 'danger'

    return {
        'stock_code': stock_code,
        'lookback_days': lookback_days,
        'analysis_date': datetime.now(),

        # Overall
        'bandar_score': bandar_score,
        'overall_signal': overall_signal,
        'signal_color': signal_color,

        # Price Pressure
        'price_pressure': {
            'buying_days': buying_days,
            'selling_days': selling_days,
            'avg_spread_pct': round(avg_spread, 2) if avg_spread else 0,
            'latest_pressure': latest_pressure,
            'latest_spread_pct': round(latest_spread, 2) if latest_spread else 0,
            'pressure_balance': buying_days - selling_days
        },

        # Foreign Accumulation
        'foreign_accumulation': fai_data,

        # Smart Money Indicator
        'smart_money': {
            'avg_score': round(avg_smi, 1),
            'latest_score': round(latest_smi, 1),
            'latest_signal': latest_smi_signal,
            'strong_buy_days': strong_buy_days
        },

        # Distribution Signal
        'distribution': {
            'avg_score': round(avg_dist, 1),
            'latest_score': round(latest_dist, 1),
            'latest_signal': latest_dist_signal,
            'strong_dist_days': strong_dist_days
        },

        # Broker Consistency
        'broker_consistency': {
            'active_accumulators': active_accumulators,
            'top_accumulators': top_accumulators.to_dict('records') if not top_accumulators.empty else [],
            'full_data': broker_consistency
        },

        # Daily data for charts
        'daily_smi': smi_df[['date', 'smi_score', 'smi_signal']].tail(30).to_dict('records') if not smi_df.empty else [],
        'daily_dist': dist_df[['date', 'dist_score', 'dist_signal']].tail(30).to_dict('records') if not dist_df.empty else [],
        'daily_pressure': pressure_df[['date', 'pressure', 'spread_pct', 'pressure_strength']].tail(30).to_dict('records') if not pressure_df.empty else []
    }


if __name__ == "__main__":
    results = run_full_analysis('CDIA')
    print_analysis_report(results)
