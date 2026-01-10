"""
DYNAMIC SIGNAL VALIDATION MODULE
Formula dinamis untuk deteksi Akumulasi/Distribusi
Bisa dipakai untuk semua emiten

15 Elemen Trust-Building:
1. One-Line Insight (Headline)
2. Score Gauge (0-100)
3. CPR Indicator
4. Top 3-5 Broker Flow
5. Volume vs Range (Absorption)
6. Timeline Persistence
7. Failed Move Counter
8. Before vs After Snapshot
9. Tanggal & Harga Deteksi
10. Checklist Validasi
11. Broker Persistence
12. Confidence Band
13. Market Context
14. Risk Flag
15. What This Means (Edukatif)
"""
import sys
sys.path.insert(0, 'C:/Users/chuwi/stock-analysis/app')

import pandas as pd
import numpy as np
from datetime import timedelta
from database import execute_query
from composite_analyzer import analyze_support_resistance
from momentum_engine import detect_impulse_signal


# ============================================================
# PARAMETER DINAMIS - Bisa di-adjust per emiten
# ============================================================
DEFAULT_PARAMS = {
    'analysis_days': 30,           # Periode analisis default
    'sideways_threshold': 10.0,    # Range < 10% = sideways
    'cpr_accum': 0.60,             # CPR >= 0.60 = akumulasi
    'cpr_distrib': 0.40,           # CPR <= 0.40 = distribusi
    'uvdv_accum': 1.2,             # UV/DV > 1.2 = akumulasi
    'uvdv_distrib': 0.8,           # UV/DV < 0.8 = distribusi
    'min_persistence': 5,          # Min hari konsisten
    'min_brokers_rotation': 3,     # Min broker untuk rotasi sehat
    'failed_break_threshold': 2,   # Min failed breaks untuk valid
}


# ============================================================
# DATA FETCHING - Dinamis untuk semua emiten
# ============================================================
def get_price_data(stock_code: str) -> pd.DataFrame:
    """Ambil data harga OHLCV untuk emiten apapun"""
    query = """
        SELECT date, open_price, high_price, low_price, close_price, volume, value
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    if df.empty:
        return df
    for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 'value']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def get_broker_data(stock_code: str) -> pd.DataFrame:
    """Ambil data broker summary untuk emiten apapun"""
    query = """
        SELECT date, broker_code, net_lot, net_value, buy_value, sell_value, buy_lot, sell_lot
        FROM broker_summary
        WHERE stock_code = %s
        ORDER BY date, broker_code
    """
    result = execute_query(query, (stock_code,), use_cache=False)
    df = pd.DataFrame(result)
    if df.empty:
        return df
    for col in ['net_lot', 'net_value', 'buy_value', 'sell_value', 'buy_lot', 'sell_lot']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def get_stock_info(stock_code: str) -> dict:
    """Ambil info emiten (issued shares)"""
    query = """
        SELECT issued_shares
        FROM stock_fundamental
        WHERE stock_code = %s
    """
    try:
        result = execute_query(query, (stock_code,), use_cache=False)
        if result:
            return {
                'issued_shares': float(result[0].get('issued_shares', 0) or 0),
            }
    except Exception:
        pass
    return {'issued_shares': 0}


def get_company_profile(stock_code: str) -> dict:
    """Ambil profil perusahaan untuk Header Metadata"""
    query = """
        SELECT company_name, ipo_price, ipo_date, market_cap
        FROM stock_profile
        WHERE stock_code = %s
    """
    try:
        result = execute_query(query, (stock_code,), use_cache=False)
        if result:
            row = result[0]
            return {
                'company_name': row.get('company_name', stock_code),
                'ipo_price': float(row.get('ipo_price', 0) or 0),
                'ipo_date': row.get('ipo_date'),
                'market_cap': float(row.get('market_cap', 0) or 0),
            }
    except Exception:
        pass
    return {'company_name': stock_code, 'ipo_price': 0, 'ipo_date': None, 'market_cap': 0}


def get_daily_flow_timeline(stock_code: str, days: int = 20) -> list:
    """
    Ambil data flow harian untuk Timeline Persistence visual
    Returns: list of dict dengan date, net_flow, status (BUY/SELL/NEUTRAL)
    Uses buy vs sell dominance ratio instead of net (since net often cancels out)
    """
    query = """
        SELECT
            date,
            SUM(net_value) as net_flow,
            SUM(net_lot) as net_lot,
            SUM(CASE WHEN net_lot > 0 THEN net_lot ELSE 0 END) as buy_lot,
            SUM(CASE WHEN net_lot < 0 THEN ABS(net_lot) ELSE 0 END) as sell_lot,
            COUNT(CASE WHEN net_lot > 0 THEN 1 END) as buy_brokers,
            COUNT(CASE WHEN net_lot < 0 THEN 1 END) as sell_brokers
        FROM broker_summary
        WHERE stock_code = %s
        GROUP BY date
        ORDER BY date DESC
        LIMIT %s
    """
    try:
        result = execute_query(query, (stock_code, days), use_cache=False)
        timeline = []
        for row in result:
            net_flow = float(row.get('net_flow', 0) or 0)
            net_lot = float(row.get('net_lot', 0) or 0)
            buy_lot = float(row.get('buy_lot', 0) or 0)
            sell_lot = float(row.get('sell_lot', 0) or 0)
            buy_brokers = int(row.get('buy_brokers', 0) or 0)
            sell_brokers = int(row.get('sell_brokers', 0) or 0)

            # Determine dominance based on buy vs sell ratio
            total_lot = buy_lot + sell_lot
            if total_lot > 0:
                buy_ratio = buy_lot / total_lot
                sell_ratio = sell_lot / total_lot

                # Also consider broker count dominance
                total_brokers = buy_brokers + sell_brokers
                broker_buy_ratio = buy_brokers / total_brokers if total_brokers > 0 else 0.5

                # Combined score: 70% volume ratio + 30% broker count ratio
                buy_score = (buy_ratio * 0.7) + (broker_buy_ratio * 0.3)

                if buy_score > 0.55:  # Buy dominates (>55%)
                    status = 'BUY'
                elif buy_score < 0.45:  # Sell dominates (<45%)
                    status = 'SELL'
                else:
                    status = 'NEUTRAL'
            else:
                status = 'NEUTRAL'

            timeline.append({
                'date': row.get('date'),
                'net_flow': net_flow,
                'net_lot': net_lot,
                'buy_lot': buy_lot,
                'sell_lot': sell_lot,
                'status': status
            })

        # Reverse to show oldest first
        return list(reversed(timeline))
    except Exception:
        return []


def get_market_status(stock_code: str, days: int = 20) -> dict:
    """
    Tentukan status market (SIDEWAYS/TRENDING UP/TRENDING DOWN)
    Berdasarkan price range dalam periode
    """
    query = """
        SELECT MIN(low_price) as low, MAX(high_price) as high,
               (SELECT close_price FROM stock_daily WHERE stock_code = %s ORDER BY date DESC LIMIT 1) as last_close,
               (SELECT close_price FROM stock_daily WHERE stock_code = %s ORDER BY date ASC LIMIT 1 OFFSET %s) as first_close
        FROM stock_daily
        WHERE stock_code = %s
        AND date >= CURRENT_DATE - INTERVAL '%s days'
    """
    try:
        result = execute_query(query, (stock_code, stock_code, days-1, stock_code, days), use_cache=False)
        if result:
            row = result[0]
            low = float(row.get('low', 0) or 0)
            high = float(row.get('high', 0) or 0)
            last_close = float(row.get('last_close', 0) or 0)
            first_close = float(row.get('first_close', 0) or low)

            if high > 0:
                range_pct = ((high - low) / low) * 100 if low > 0 else 0
                change_pct = ((last_close - first_close) / first_close) * 100 if first_close > 0 else 0

                if range_pct < 15:
                    status = 'SIDEWAYS'
                elif change_pct > 10:
                    status = 'TRENDING UP'
                elif change_pct < -10:
                    status = 'TRENDING DOWN'
                else:
                    status = 'SIDEWAYS'

                return {
                    'status': status,
                    'range_pct': round(range_pct, 1),
                    'change_pct': round(change_pct, 1),
                    'low': low,
                    'high': high
                }
    except Exception:
        pass
    return {'status': 'UNKNOWN', 'range_pct': 0, 'change_pct': 0, 'low': 0, 'high': 0}


def get_risk_events(stock_code: str) -> list:
    """
    Check for potential risk events (corporate actions, etc)
    For now returns static warnings based on data patterns
    """
    risks = []

    # Check for unusual volume spike (potential corporate action)
    query = """
        SELECT
            (SELECT AVG(volume) FROM stock_daily WHERE stock_code = %s ORDER BY date DESC LIMIT 20) as avg_vol,
            (SELECT volume FROM stock_daily WHERE stock_code = %s ORDER BY date DESC LIMIT 1) as last_vol
    """
    try:
        result = execute_query(query, (stock_code, stock_code), use_cache=False)
        if result:
            avg_vol = float(result[0].get('avg_vol', 0) or 0)
            last_vol = float(result[0].get('last_vol', 0) or 0)

            if avg_vol > 0 and last_vol > avg_vol * 3:
                risks.append({
                    'type': 'VOLUME_SPIKE',
                    'icon': '📊',
                    'message': 'Volume spike terdeteksi - kemungkinan ada corporate action',
                    'severity': 'MEDIUM'
                })
    except Exception:
        pass

    # Check for price at 52-week high/low
    query2 = """
        SELECT
            MAX(high_price) as high_52w,
            MIN(low_price) as low_52w,
            (SELECT close_price FROM stock_daily WHERE stock_code = %s ORDER BY date DESC LIMIT 1) as last_close
        FROM stock_daily
        WHERE stock_code = %s
        AND date >= CURRENT_DATE - INTERVAL '252 days'
    """
    try:
        result = execute_query(query2, (stock_code, stock_code), use_cache=False)
        if result:
            high_52w = float(result[0].get('high_52w', 0) or 0)
            low_52w = float(result[0].get('low_52w', 0) or 0)
            last_close = float(result[0].get('last_close', 0) or 0)

            if high_52w > 0 and last_close >= high_52w * 0.95:
                risks.append({
                    'type': 'NEAR_52W_HIGH',
                    'icon': '⚠️',
                    'message': f'Harga mendekati 52-week high (Rp {high_52w:,.0f})',
                    'severity': 'LOW'
                })
            elif low_52w > 0 and last_close <= low_52w * 1.05:
                risks.append({
                    'type': 'NEAR_52W_LOW',
                    'icon': '⚠️',
                    'message': f'Harga mendekati 52-week low (Rp {low_52w:,.0f})',
                    'severity': 'MEDIUM'
                })
    except Exception:
        pass

    return risks


def get_all_broker_details(stock_code: str, days: int = 30) -> dict:
    """
    Ambil semua detail broker untuk Hidden/Expandable Section
    """
    query = """
        SELECT
            broker_code,
            SUM(net_lot) as total_net_lot,
            SUM(net_value) as total_net_value,
            SUM(buy_value) as total_buy,
            SUM(sell_value) as total_sell,
            COUNT(DISTINCT date) as active_days,
            SUM(CASE WHEN net_lot > 0 THEN 1 ELSE 0 END) as buy_days,
            SUM(CASE WHEN net_lot < 0 THEN 1 ELSE 0 END) as sell_days
        FROM broker_summary
        WHERE stock_code = %s
        AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY broker_code
        ORDER BY total_net_value DESC
    """
    try:
        result = execute_query(query, (stock_code, days), use_cache=False)

        accumulators = []
        distributors = []

        for row in result:
            broker_data = {
                'broker_code': row.get('broker_code', ''),
                'total_net_lot': float(row.get('total_net_lot', 0) or 0),
                'total_net_value': float(row.get('total_net_value', 0) or 0),
                'total_buy': float(row.get('total_buy', 0) or 0),
                'total_sell': float(row.get('total_sell', 0) or 0),
                'active_days': int(row.get('active_days', 0) or 0),
                'buy_days': int(row.get('buy_days', 0) or 0),
                'sell_days': int(row.get('sell_days', 0) or 0),
            }

            if broker_data['total_net_lot'] > 0:
                accumulators.append(broker_data)
            else:
                distributors.append(broker_data)

        # Sort distributors by net value (most negative first)
        distributors.sort(key=lambda x: x['total_net_value'])

        return {
            'accumulators': accumulators,
            'distributors': distributors,
            'total_accumulators': len(accumulators),
            'total_distributors': len(distributors),
        }
    except Exception:
        return {'accumulators': [], 'distributors': [], 'total_accumulators': 0, 'total_distributors': 0}


# ============================================================
# INDIKATOR 1: CPR (Close Position Ratio)
# ============================================================
def calculate_cpr(df: pd.DataFrame, params: dict = None) -> dict:
    """
    CPR = (Close - Low) / (High - Low)

    Logika Awam:
    - CPR tinggi (>60%) = Harga tutup dekat harga tertinggi hari itu = Pembeli dominan
    - CPR rendah (<40%) = Harga tutup dekat harga terendah = Penjual dominan
    """
    if params is None:
        params = DEFAULT_PARAMS

    if df.empty:
        return {'avg_cpr': 0.5, 'signal': 'NO DATA', 'passed': False, 'score': 0,
                'explanation': 'Data tidak tersedia'}

    df = df.copy()
    df['range'] = df['high_price'] - df['low_price']
    df['cpr'] = np.where(df['range'] > 0,
                         (df['close_price'] - df['low_price']) / df['range'],
                         0.5)

    avg_cpr = df['cpr'].mean()
    cpr_pct = int(avg_cpr * 100)

    if avg_cpr >= params['cpr_accum']:
        signal = 'AKUMULASI'
        passed = True
        score = 1
        explanation = f"Close rata-rata di {cpr_pct}% dari range (dekat HIGH = pembeli kuat)"
    elif avg_cpr <= params['cpr_distrib']:
        signal = 'DISTRIBUSI'
        passed = True
        score = -1
        explanation = f"Close rata-rata di {cpr_pct}% dari range (dekat LOW = penjual kuat)"
    else:
        signal = 'NETRAL'
        passed = False
        score = 0
        explanation = f"Close rata-rata di {cpr_pct}% dari range (tengah = seimbang)"

    return {
        'avg_cpr': round(avg_cpr, 3),
        'cpr_pct': cpr_pct,
        'signal': signal,
        'passed': passed,
        'score': score,
        'explanation': explanation
    }


# ============================================================
# INDIKATOR 2: UV/DV (Up Volume / Down Volume)
# ============================================================
def calculate_uvdv(df: pd.DataFrame, params: dict = None) -> dict:
    """
    UV/DV = Total volume saat naik / Total volume saat turun

    Logika Awam:
    - UV/DV > 1.2 = Volume lebih besar saat harga naik = Ada yang beli banyak
    - UV/DV < 0.8 = Volume lebih besar saat harga turun = Ada yang jual banyak
    """
    if params is None:
        params = DEFAULT_PARAMS

    if df.empty:
        return {'uvdv_ratio': 1.0, 'signal': 'NO DATA', 'passed': False, 'score': 0,
                'explanation': 'Data tidak tersedia'}

    df = df.copy()
    df['up_vol'] = np.where(df['close_price'] > df['open_price'], df['volume'], 0)
    df['down_vol'] = np.where(df['close_price'] < df['open_price'], df['volume'], 0)

    total_up = df['up_vol'].sum()
    total_down = df['down_vol'].sum()

    uvdv = total_up / total_down if total_down > 0 else 2.0

    if uvdv > params['uvdv_accum']:
        signal = 'AKUMULASI'
        passed = True
        score = 1
        explanation = f"Volume naik {uvdv:.1f}x lebih besar dari volume turun"
    elif uvdv < params['uvdv_distrib']:
        signal = 'DISTRIBUSI'
        passed = True
        score = -1
        explanation = f"Volume turun lebih dominan (rasio {uvdv:.2f})"
    else:
        signal = 'NETRAL'
        passed = False
        score = 0
        explanation = f"Volume naik/turun seimbang (rasio {uvdv:.2f})"

    return {
        'uvdv_ratio': round(uvdv, 2),
        'total_up_volume': total_up,
        'total_down_volume': total_down,
        'signal': signal,
        'passed': passed,
        'score': score,
        'explanation': explanation
    }


# ============================================================
# INDIKATOR 3: Broker Influence
# ============================================================
def calculate_broker_influence(broker_df: pd.DataFrame) -> dict:
    """
    Siapa broker paling berpengaruh dan apa aksinya

    Logika Awam:
    - Broker dengan pengaruh besar net beli = Ada institusi mengumpulkan
    - Broker dengan pengaruh besar net jual = Ada institusi menjual
    """
    if broker_df.empty:
        return {'net_influence': 0, 'signal': 'NO DATA', 'passed': False, 'score': 0,
                'top_accumulators': [], 'top_distributors': [],
                'explanation': 'Data broker tidak tersedia'}

    # Aggregate per broker
    stats = broker_df.groupby('broker_code').agg({
        'buy_value': 'sum',
        'sell_value': 'sum',
        'net_value': 'sum',
        'net_lot': 'sum'
    }).reset_index()

    total_value = (stats['buy_value'] + stats['sell_value']).sum()

    if total_value > 0:
        stats['participation'] = (stats['buy_value'] + stats['sell_value']) / total_value
        stats['influence'] = stats['net_value'] * stats['participation']
    else:
        stats['participation'] = 0
        stats['influence'] = 0

    net_influence = stats['influence'].sum()

    # Top accumulators & distributors
    top_accum = stats[stats['net_lot'] > 0].nlargest(5, 'net_lot')[['broker_code', 'net_lot', 'net_value']].to_dict('records')
    top_distrib = stats[stats['net_lot'] < 0].nsmallest(5, 'net_lot')[['broker_code', 'net_lot', 'net_value']].to_dict('records')

    if net_influence > 0:
        signal = 'AKUMULASI'
        score = 1
        explanation = f"Net pengaruh broker: +Rp {net_influence/1e9:.2f}M (beli dominan)"
    else:
        signal = 'DISTRIBUSI'
        score = -1
        explanation = f"Net pengaruh broker: Rp {net_influence/1e9:.2f}M (jual dominan)"

    return {
        'net_influence': net_influence,
        'signal': signal,
        'passed': True,
        'score': score,
        'top_accumulators': top_accum,
        'top_distributors': top_distrib,
        'explanation': explanation
    }


# ============================================================
# INDIKATOR 4: Broker Persistence (Konsistensi)
# ============================================================
def calculate_broker_persistence(broker_df: pd.DataFrame, params: dict = None) -> dict:
    """
    Seberapa konsisten broker melakukan aksi

    Logika Awam:
    - >= 5 hari berturut akumulasi = Mulai serius
    - >= 10 hari = Terencana
    - >= 15 hari = Institusional (bandar besar)
    """
    if params is None:
        params = DEFAULT_PARAMS

    if broker_df.empty:
        return {'max_streak': 0, 'level': 'NO DATA', 'persistent_brokers': [],
                'explanation': 'Data tidak tersedia'}

    daily = broker_df.groupby(['broker_code', 'date']).agg({'net_lot': 'sum'}).reset_index()

    results = []
    for broker in daily['broker_code'].unique():
        bdata = daily[daily['broker_code'] == broker].sort_values('date')

        max_accum = 0
        max_distrib = 0
        curr_accum = 0
        curr_distrib = 0

        for nl in bdata['net_lot'].values:
            if nl > 0:
                curr_accum += 1
                curr_distrib = 0
                max_accum = max(max_accum, curr_accum)
            elif nl < 0:
                curr_distrib += 1
                curr_accum = 0
                max_distrib = max(max_distrib, curr_distrib)
            else:
                curr_accum = 0
                curr_distrib = 0

        results.append({
            'broker': broker,
            'max_accum_streak': max_accum,
            'max_distrib_streak': max_distrib,
            'total_net_lot': bdata['net_lot'].sum(),
            'days_active': len(bdata)
        })

    pdf = pd.DataFrame(results)

    # Top persistent accumulators
    top_accum = pdf[pdf['total_net_lot'] > 0].nlargest(5, 'max_accum_streak').to_dict('records')
    top_distrib = pdf[pdf['total_net_lot'] < 0].nlargest(5, 'max_distrib_streak').to_dict('records')

    max_streak = pdf['max_accum_streak'].max() if not pdf.empty else 0

    if max_streak >= 15:
        level = 'INSTITUSIONAL'
    elif max_streak >= 10:
        level = 'TERENCANA'
    elif max_streak >= 5:
        level = 'MULAI SERIUS'
    else:
        level = 'SPEKULATIF'

    return {
        'max_streak': max_streak,
        'level': level,
        'persistent_brokers': top_accum[:3],
        'persistent_distributors': top_distrib[:3],
        'explanation': f"Broker paling konsisten: {max_streak} hari berturut ({level})"
    }


# ============================================================
# INDIKATOR 5: Failed Breaks (Pertahanan Harga)
# ============================================================
def calculate_failed_breaks(df: pd.DataFrame, params: dict = None) -> dict:
    """
    Berapa kali harga gagal menembus support/resistance

    Logika Awam:
    - Banyak gagal breakdown = Support kuat, ada yang menahan jatuh
    - Banyak gagal breakout = Resistance kuat, ada yang menahan naik
    """
    if params is None:
        params = DEFAULT_PARAMS

    if len(df) < 5:
        return {'failed_breakdowns': 0, 'failed_breakouts': 0, 'signal': 'NO DATA',
                'passed': False, 'explanation': 'Data tidak cukup'}

    # Support = Low 10%, Resistance = High 90%
    support = df['low_price'].quantile(0.1)
    resistance = df['high_price'].quantile(0.9)

    failed_bd = 0
    failed_bo = 0

    for i in range(1, len(df)):
        row = df.iloc[i]
        # Failed breakdown: tembus support tapi close di atas
        if row['low_price'] < support and row['close_price'] > support:
            failed_bd += 1
        # Failed breakout: tembus resistance tapi close di bawah
        if row['high_price'] > resistance and row['close_price'] < resistance:
            failed_bo += 1

    threshold = params['failed_break_threshold']

    if failed_bd >= threshold and failed_bd > failed_bo:
        signal = 'AKUMULASI'
        passed = True
        explanation = f"{failed_bd}x breakdown gagal = Support kuat, ada yang menahan"
    elif failed_bo >= threshold and failed_bo > failed_bd:
        signal = 'DISTRIBUSI'
        passed = True
        explanation = f"{failed_bo}x breakout gagal = Resistance kuat, ada yang jual"
    else:
        signal = 'NETRAL'
        passed = False
        explanation = f"Tidak ada pola pertahanan jelas ({failed_bd} BD, {failed_bo} BO)"

    return {
        'failed_breakdowns': failed_bd,
        'failed_breakouts': failed_bo,
        'support': support,
        'resistance': resistance,
        'signal': signal,
        'passed': passed,
        'explanation': explanation
    }


# ============================================================
# INDIKATOR 6: Volume Elasticity
# ============================================================
def calculate_elasticity(df: pd.DataFrame) -> dict:
    """
    Seberapa responsif harga terhadap volume

    Logika Awam:
    - Volume naik banyak tapi harga diam = Ada yang menahan harga (akumulasi/distribusi)
    - Volume dan harga bergerak sama = Pasar normal
    """
    if len(df) < 5:
        return {'elasticity': 0, 'signal': 'NO DATA', 'passed': False,
                'explanation': 'Data tidak cukup'}

    first_close = df.iloc[0]['close_price']
    last_close = df.iloc[-1]['close_price']
    price_change = abs((last_close - first_close) / first_close * 100) if first_close > 0 else 0

    first_vol = df.iloc[:5]['volume'].mean()
    last_vol = df.iloc[-5:]['volume'].mean()
    vol_change = abs((last_vol - first_vol) / first_vol * 100) if first_vol > 0 else 0

    elasticity = price_change / vol_change if vol_change > 0 else 999

    if elasticity < 0.3 and vol_change > 10:
        signal = 'ADA PENAHAN KUAT'
        passed = True
        explanation = f"Volume +{vol_change:.0f}% tapi harga cuma {price_change:.1f}% = Ada akumulasi/distribusi"
    elif elasticity < 0.5:
        signal = 'ADA PENAHAN'
        passed = True
        explanation = f"Volume bergerak lebih dari harga = Ada yang menahan"
    else:
        signal = 'PASAR BEBAS'
        passed = False
        explanation = f"Volume dan harga bergerak normal"

    return {
        'elasticity': round(elasticity, 3) if elasticity < 100 else 999,
        'price_change_pct': round(price_change, 2),
        'volume_change_pct': round(vol_change, 2),
        'signal': signal,
        'passed': passed,
        'explanation': explanation
    }


# ============================================================
# MULTI-HORIZON VOLUME VS PRICE ANALYSIS
# ============================================================
def calculate_volume_price_multi_horizon(df: pd.DataFrame) -> dict:
    """
    Analisis multi-horizon untuk Volume vs Price:
    - Micro (1 hari): Deteksi kejadian
    - Core (5 hari): Validasi niat - WAJIB
    - Structural (10 hari): Konfirmasi fase

    Absorption detected when:
    - Volume meningkat TAPI price range tetap sempit
    """
    if len(df) < 10:
        return {
            'status': 'NO_DATA',
            'significance': 'INSUFFICIENT',
            'horizons': {},
            'conclusion': 'Data tidak cukup untuk analisis multi-horizon'
        }

    df = df.sort_values('date').copy()

    def calc_horizon(data, window, prev_window=None):
        """Calculate metrics for a specific time horizon"""
        if len(data) < window:
            return None

        recent = data.tail(window)

        # Volume change
        avg_vol_recent = recent['volume'].mean()

        if prev_window and len(data) >= window + prev_window:
            prev_data = data.iloc[-(window + prev_window):-window]
            avg_vol_prev = prev_data['volume'].mean() if len(prev_data) > 0 else avg_vol_recent
        else:
            # Use earlier data as baseline
            earlier = data.iloc[:window] if len(data) > window else data.iloc[:len(data)//2]
            avg_vol_prev = earlier['volume'].mean() if len(earlier) > 0 else avg_vol_recent

        vol_change_pct = ((avg_vol_recent - avg_vol_prev) / avg_vol_prev * 100) if avg_vol_prev > 0 else 0

        # Price range (high-low as % of mid price)
        high = recent['high_price'].max()
        low = recent['low_price'].min()
        mid = (high + low) / 2
        price_range_pct = ((high - low) / mid * 100) if mid > 0 else 0

        # Price change (close to close)
        # For 1 day horizon, compare today vs yesterday from full data
        if window == 1 and len(data) >= 2:
            last_close = data.iloc[-1]['close_price']
            prev_close = data.iloc[-2]['close_price']
            price_change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close > 0 else 0
        else:
            first_close = recent.iloc[0]['close_price']
            last_close = recent.iloc[-1]['close_price']
            price_change_pct = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0

        # Average daily range for comparison
        daily_ranges = ((recent['high_price'] - recent['low_price']) / recent['low_price'] * 100)
        avg_daily_range = daily_ranges.mean()

        # Absorption detection: volume up + range narrow
        is_absorption = vol_change_pct > 10 and price_range_pct < 8
        
        # Determine absorption type based on price direction
        # Price DOWN + high volume + tight range = AKUMULASI (smart money buying)
        # Price UP + high volume + tight range = DISTRIBUSI (smart money selling)
        absorption_type = None
        if is_absorption:
            if price_change_pct <= 0:
                absorption_type = 'AKUMULASI'  # Price down/flat = buying from weak hands
            else:
                absorption_type = 'DISTRIBUSI'  # Price up = selling to FOMO buyers

        return {
            'volume_change_pct': round(vol_change_pct, 1),
            'price_change_pct': round(price_change_pct, 2),
            'price_range_pct': round(price_range_pct, 2),
            'avg_daily_range': round(avg_daily_range, 2),
            'is_absorption': is_absorption,
            'absorption_type': absorption_type
        }

    # Calculate for each horizon
    horizons = {
        '1d': calc_horizon(df, 1, 5),   # Micro: 1 day vs 5 day avg
        '5d': calc_horizon(df, 5, 5),   # Core: 5 day vs prev 5 day
        '10d': calc_horizon(df, 10, 10) # Structural: 10 day vs prev 10 day
    }

    # Determine significance
    micro_absorption = horizons.get('1d', {}).get('is_absorption', False) if horizons.get('1d') else False
    core_absorption = horizons.get('5d', {}).get('is_absorption', False) if horizons.get('5d') else False
    structural_absorption = horizons.get('10d', {}).get('is_absorption', False) if horizons.get('10d') else False

    # Significance classification
    if core_absorption and micro_absorption:
        significance = 'SIGNIFICANT'
        status = 'ABSORPTION_CONFIRMED'
    elif core_absorption:
        significance = 'MODERATE'
        status = 'ABSORPTION_BUILDING'
    elif micro_absorption:
        significance = 'EARLY'
        status = 'ABSORPTION_EARLY'
    else:
        significance = 'NONE'
        status = 'NO_ABSORPTION'

    # Generate conclusion
    if significance == 'SIGNIFICANT':
        conclusion = "ABSORPTION SIGNIFIKAN - Volume meningkat konsisten 1-5 hari tanpa pelebaran range. Ada akumulasi/distribusi terstruktur."
    elif significance == 'MODERATE':
        conclusion = "ABSORPTION MODERAT - Volume meningkat dalam 5 hari dengan range terkendali. Validasi niat mulai terbentuk."
    elif significance == 'EARLY':
        conclusion = "ABSORPTION AWAL - Volume spike 1 hari terdeteksi, BELUM terkonfirmasi. Butuh validasi 3-5 hari."
    else:
        # Determine actual market condition
        vol_5d = horizons.get('5d', {}).get('volume_change_pct', 0) if horizons.get('5d') else 0
        price_5d = horizons.get('5d', {}).get('price_change_pct', 0) if horizons.get('5d') else 0
        range_5d = horizons.get('5d', {}).get('price_range_pct', 0) if horizons.get('5d') else 0

        if vol_5d > 10 and price_5d > 5:
            conclusion = "RALLY/MARKUP - Volume dan harga naik bersamaan. Buying pressure dominan."
        elif vol_5d > 10 and price_5d < -5:
            conclusion = "DISTRIBUTION - Volume tinggi dengan harga turun. Selling pressure dominan."
        elif vol_5d <= 10 and abs(price_5d) <= 5:
            conclusion = "KONSOLIDASI - Volume dan harga stabil. Menunggu breakout/breakdown."
        elif price_5d > 5:
            conclusion = "WEAK RALLY - Harga naik tanpa dukungan volume. Waspada pullback."
        elif price_5d < -5:
            conclusion = "WEAK SELLING - Harga turun tanpa volume tinggi. Potensi reversal."
        else:
            conclusion = "NETRAL - Tidak ada pola signifikan dalam 5 hari terakhir."

    return {
        'status': status,
        'significance': significance,
        'horizons': horizons,
        'conclusion': conclusion,
        'micro_absorption': micro_absorption,
        'core_absorption': core_absorption,
        'structural_absorption': structural_absorption
    }


# ============================================================
# INDIKATOR 7: Broker Rotation
# ============================================================
def calculate_rotation(broker_df: pd.DataFrame, params: dict = None) -> dict:
    """
    Apakah banyak broker searah atau cuma 1-2

    Logika Awam:
    - Banyak broker akumulasi = Institusional, bukan spekulan
    - Cuma 1-2 broker = Spekulatif, berisiko
    """
    if params is None:
        params = DEFAULT_PARAMS

    if broker_df.empty:
        return {'num_accumulators': 0, 'signal': 'NO DATA', 'passed': False,
                'explanation': 'Data tidak tersedia'}

    stats = broker_df.groupby('broker_code').agg({'net_lot': 'sum'}).reset_index()

    accumulators = len(stats[stats['net_lot'] > 0])
    distributors = len(stats[stats['net_lot'] < 0])

    min_brokers = params['min_brokers_rotation']

    if accumulators >= min_brokers:
        # Cek konsentrasi
        top3 = stats[stats['net_lot'] > 0].nlargest(3, 'net_lot')['net_lot'].sum()
        total = stats[stats['net_lot'] > 0]['net_lot'].sum()
        concentration = (top3 / total * 100) if total > 0 else 100

        if concentration < 80:
            signal = 'ROTASI SEHAT'
            passed = True
            explanation = f"{accumulators} broker akumulasi, tidak terkonsentrasi ({concentration:.0f}%)"
        else:
            signal = 'TERKONSENTRASI'
            passed = False
            explanation = f"Akumulasi terkonsentrasi di sedikit broker ({concentration:.0f}%)"
    else:
        signal = 'KURANG BROKER'
        passed = False
        concentration = 0
        explanation = f"Hanya {accumulators} broker akumulasi (min {min_brokers})"

    return {
        'num_accumulators': accumulators,
        'num_distributors': distributors,
        'concentration': round(concentration, 1) if 'concentration' in dir() else 0,
        'signal': signal,
        'passed': passed,
        'explanation': explanation
    }


# ============================================================
# DETEKSI PERIODE AKUMULASI/DISTRIBUSI
# ============================================================
def detect_signal_period(price_df: pd.DataFrame, broker_df: pd.DataFrame) -> dict:
    """
    Deteksi sinyal dengan riwayat perubahan lengkap

    Return:
    - detection_date: tanggal pertama sinyal terdeteksi
    - detection_price: harga saat deteksi
    - detection_signal: sinyal saat deteksi (ACCUMULATION/DISTRIBUTION)
    - current_signal: sinyal saat ini
    - current_price: harga saat ini
    - price_change_pct: perubahan harga dari deteksi
    - signal_history: list riwayat perubahan sinyal [{date, price, signal, strength, cpr, net_lot}]
    """
    if price_df.empty or broker_df.empty:
        return None

    daily_signals = []

    # Analisa rolling 10 hari untuk setiap hari
    for i in range(10, len(price_df)):
        start_idx = max(0, i - 10)
        window = price_df.iloc[start_idx:i+1].copy()

        if len(window) < 5:
            continue

        current_date = window.iloc[-1]['date']
        current_price = window.iloc[-1]['close_price']

        # Hitung CPR window
        window['range'] = window['high_price'] - window['low_price']
        window['cpr'] = np.where(window['range'] > 0,
                                 (window['close_price'] - window['low_price']) / window['range'],
                                 0.5)
        avg_cpr = window['cpr'].mean()

        # Hitung broker flow
        start_date = window['date'].min()
        end_date = window['date'].max()
        broker_window = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)]
        net_lot = broker_window['net_lot'].sum() if not broker_window.empty else 0

        # Hitung jumlah broker aktif
        num_buyers = broker_window[broker_window['net_lot'] > 0]['broker_code'].nunique() if not broker_window.empty else 0
        num_sellers = broker_window[broker_window['net_lot'] < 0]['broker_code'].nunique() if not broker_window.empty else 0

        # Tentukan sinyal dan kekuatan
        signal = None
        strength = None

        if avg_cpr >= 0.70 and net_lot > 0 and num_buyers >= 5:
            signal = 'ACCUMULATION'
            strength = 'STRONG'
        elif avg_cpr >= 0.58 and net_lot > 0:
            signal = 'ACCUMULATION'
            strength = 'WEAK' if avg_cpr < 0.65 or num_buyers < 3 else 'MODERATE'
        elif avg_cpr <= 0.30 and net_lot < 0 and num_sellers >= 5:
            signal = 'DISTRIBUTION'
            strength = 'STRONG'
        elif avg_cpr <= 0.42 and net_lot < 0:
            signal = 'DISTRIBUTION'
            strength = 'WEAK' if avg_cpr > 0.35 or num_sellers < 3 else 'MODERATE'
        else:
            signal = 'NEUTRAL'
            strength = None

        daily_signals.append({
            'date': current_date,
            'price': current_price,
            'signal': signal,
            'strength': strength,
            'cpr': avg_cpr,
            'net_lot': net_lot,
            'num_buyers': num_buyers,
            'num_sellers': num_sellers
        })

    if not daily_signals:
        return None

    # Bangun riwayat perubahan sinyal (hanya catat saat ada perubahan)
    signal_history = []
    last_signal = None
    last_strength = None

    for day in daily_signals:
        current_sig = day['signal']
        current_str = day['strength']

        # Catat jika sinyal berubah ATAU kekuatan berubah
        if current_sig != last_signal or (current_sig != 'NEUTRAL' and current_str != last_strength):
            signal_history.append({
                'date': day['date'],
                'price': day['price'],
                'signal': current_sig,
                'strength': current_str,
                'cpr': round(day['cpr'] * 100, 1),
                'net_lot': day['net_lot'],
                'num_buyers': day['num_buyers'],
                'num_sellers': day['num_sellers']
            })
            last_signal = current_sig
            last_strength = current_str

    if not signal_history:
        return None

    # Cari deteksi pertama (sinyal non-neutral pertama)
    first_detection = None
    for h in signal_history:
        if h['signal'] != 'NEUTRAL':
            first_detection = h
            break

    if not first_detection:
        # Tidak ada sinyal terdeteksi, return status saat ini saja
        latest = daily_signals[-1]
        return {
            'detection_date': None,
            'detection_price': None,
            'detection_signal': None,
            'current_signal': latest['signal'],
            'current_price': latest['price'],
            'price_change_pct': 0,
            'signal_history': signal_history[-10:]  # 10 perubahan terakhir
        }

    current = daily_signals[-1]
    return {
        'detection_date': first_detection['date'],
        'detection_price': first_detection['price'],
        'detection_signal': first_detection['signal'],
        'detection_strength': first_detection['strength'],
        'current_signal': current['signal'],
        'current_strength': current.get('strength'),
        'current_price': current['price'],
        'price_change_pct': (current['price'] - first_detection['price']) / first_detection['price'] * 100 if first_detection['price'] > 0 else 0,
        'signal_history': signal_history  # Full history
    }


# ============================================================
# DETEKSI MARKUP TRIGGER (Transisi dari Akumulasi ke Markup)
# ============================================================
def detect_markup_trigger(price_df: pd.DataFrame, broker_df: pd.DataFrame, detection: dict) -> dict:
    """
    Deteksi apakah harga sedang memasuki fase MARKUP setelah akumulasi.

    Kondisi Markup Trigger:
    1. Ada akumulasi sebelumnya (detection_signal = ACCUMULATION)
    2. Close hari ini > High 3-5 hari terakhir (breakout)
    3. Volume spike (volume > 1.5x avg)
    4. Net flow tidak negatif

    Returns:
        dict dengan markup_triggered, source_signal, breakout_pct, volume_spike_pct
    """
    if price_df.empty or len(price_df) < 5:
        return {'markup_triggered': False}

    # Cek apakah ada akumulasi sebelumnya
    prior_accumulation = False
    prior_strength = None

    if detection:
        # Cek dari signal_history - apakah pernah ada ACCUMULATION
        history = detection.get('signal_history', [])
        for h in history:
            if h.get('signal') == 'ACCUMULATION':
                prior_accumulation = True
                prior_strength = h.get('strength', 'WEAK')
                break

    if not prior_accumulation:
        return {'markup_triggered': False, 'reason': 'No prior accumulation'}

    # Data hari ini
    today = price_df.iloc[-1]
    today_close = today['close_price']
    today_volume = today['volume']
    today_date = today['date']

    # High 3-5 hari terakhir (exclude hari ini)
    lookback = min(5, len(price_df) - 1)
    if lookback < 3:
        return {'markup_triggered': False, 'reason': 'Not enough data'}

    recent = price_df.iloc[-(lookback+1):-1]  # 3-5 hari sebelum hari ini
    recent_high = recent['high_price'].max()
    avg_volume = recent['volume'].mean()

    # Kondisi breakout
    is_breakout = today_close > recent_high
    breakout_pct = ((today_close - recent_high) / recent_high * 100) if recent_high > 0 else 0

    # Kondisi volume spike
    volume_spike = (today_volume / avg_volume) if avg_volume > 0 else 1
    is_volume_spike = volume_spike >= 1.3  # 30% lebih tinggi dari rata-rata

    # Kondisi net flow (hari ini)
    today_broker = broker_df[broker_df['date'] == today_date] if not broker_df.empty else pd.DataFrame()
    net_flow = today_broker['net_lot'].sum() if not today_broker.empty else 0
    is_positive_flow = net_flow >= 0

    # Markup triggered jika: breakout + (volume spike ATAU positive flow)
    markup_triggered = is_breakout and (is_volume_spike or is_positive_flow)

    return {
        'markup_triggered': markup_triggered,
        'source_signal': 'ACCUMULATION',
        'source_strength': prior_strength,
        'breakout': is_breakout,
        'breakout_pct': round(breakout_pct, 2),
        'recent_high': recent_high,
        'volume_spike': is_volume_spike,
        'volume_spike_pct': round((volume_spike - 1) * 100, 1),
        'net_flow': net_flow,
        'positive_flow': is_positive_flow,
        'trigger_date': str(today_date)[:10] if today_date else None
    }


# ============================================================
# DECISION RULE ENGINE (WAIT/ENTRY/ADD/EXIT)
# ============================================================
def calculate_decision_rule(
    price_df: pd.DataFrame,
    validation_score: int,
    overall_signal: str,
    cpr_value: float,
    range_pct: float,
    markup_trigger: dict,
    detection: dict
) -> dict:
    """
    Menentukan keputusan trading berdasarkan kondisi saat ini.

    Decision Rules:
    - WAIT: Netral, validasi < 4/6, range > 20%, CPR 45-55%
    - ENTRY: Akumulasi WEAK/MODERATE, validasi >= 4, CPR >= 58%, range <= 18%
    - ADD: Akumulasi STRONG, CPR > 62%, konfirmasi markup
    - HOLD: Trending up tapi sinyal netral, tidak ada risk flag
    - EXIT: Distribusi, CPR < 45%, broker distrib dominan

    Returns:
        dict dengan decision, reason, entry_zone, invalidation_price
    """
    if price_df.empty or len(price_df) < 5:
        return {
            'decision': 'WAIT',
            'decision_id': 'wait',
            'color': 'secondary',
            'icon': '⏳',
            'reason': 'Data tidak cukup untuk analisis',
            'entry_zone': None,
            'invalidation_price': None
        }

    # Calculate price zones
    recent_prices = price_df.tail(20)
    range_high = recent_prices['high_price'].max()
    range_low = recent_prices['low_price'].min()
    current_price = price_df.iloc[-1]['close_price']

    # Entry zone = lower 20-40% of range
    entry_zone_low = range_low
    entry_zone_high = range_low + 0.4 * (range_high - range_low)

    # Support level (recent low)
    support_level = recent_prices.tail(10)['low_price'].min()
    invalidation_price = support_level * 0.97  # 3% di bawah support

    # Cek apakah ada prior accumulation
    has_prior_accum = False
    if detection and detection.get('signal_history'):
        for h in detection['signal_history']:
            if h.get('signal') == 'ACCUMULATION':
                has_prior_accum = True
                break

    # === DECISION LOGIC ===

    # 1. MARKUP sudah triggered → HOLD (jangan kejar)
    if markup_trigger and markup_trigger.get('markup_triggered'):
        return {
            'decision': 'HOLD',
            'decision_id': 'hold',
            'color': 'info',
            'icon': '✋',
            'reason': 'Markup sudah berjalan. Jangan kejar harga, tunggu pullback atau kelola posisi yang ada.',
            'entry_zone': {'low': entry_zone_low, 'high': entry_zone_high},
            'invalidation_price': invalidation_price,
            'support_level': support_level,
            'current_vs_entry': 'ABOVE' if current_price > entry_zone_high else 'IN_ZONE' if current_price >= entry_zone_low else 'BELOW'
        }

    # 2. DISTRIBUTION → EXIT/REDUCE
    if overall_signal == 'DISTRIBUSI' or (cpr_value < 0.45 and validation_score <= 2):
        return {
            'decision': 'EXIT',
            'decision_id': 'exit',
            'color': 'danger',
            'icon': '🚨',
            'reason': 'Distribusi terdeteksi. Pertimbangkan untuk mengurangi atau menutup posisi.',
            'entry_zone': {'low': entry_zone_low, 'high': entry_zone_high},
            'invalidation_price': invalidation_price,
            'support_level': support_level,
            'current_vs_entry': 'ABOVE' if current_price > entry_zone_high else 'IN_ZONE' if current_price >= entry_zone_low else 'BELOW'
        }

    # 3. STRONG ACCUMULATION → ADD
    if overall_signal == 'AKUMULASI' and validation_score >= 5 and cpr_value >= 0.62:
        return {
            'decision': 'ADD',
            'decision_id': 'add',
            'color': 'primary',
            'icon': '➕',
            'reason': f'Akumulasi terkonfirmasi kuat ({validation_score}/6 validasi). Layak untuk menambah posisi saat pullback.',
            'entry_zone': {'low': entry_zone_low, 'high': entry_zone_high},
            'invalidation_price': invalidation_price,
            'support_level': support_level,
            'current_vs_entry': 'ABOVE' if current_price > entry_zone_high else 'IN_ZONE' if current_price >= entry_zone_low else 'BELOW'
        }

    # 4. WEAK/MODERATE ACCUMULATION → ENTRY
    if overall_signal == 'AKUMULASI' and validation_score >= 4 and cpr_value >= 0.55 and range_pct <= 20:
        zone_status = 'ABOVE' if current_price > entry_zone_high else 'IN_ZONE' if current_price >= entry_zone_low else 'BELOW'
        if zone_status == 'IN_ZONE':
            reason = f'Akumulasi awal terdeteksi. Harga di zona entry. Pertimbangkan masuk bertahap (30-50%).'
        elif zone_status == 'ABOVE':
            reason = f'Akumulasi terdeteksi tapi harga sudah di atas zona entry. Tunggu pullback ke Rp {entry_zone_high:,.0f}.'
        else:
            reason = f'Akumulasi terdeteksi. Harga di bawah zona entry - bisa jadi peluang atau warning.'

        return {
            'decision': 'ENTRY',
            'decision_id': 'entry',
            'color': 'success',
            'icon': '🟢',
            'reason': reason,
            'entry_zone': {'low': entry_zone_low, 'high': entry_zone_high},
            'invalidation_price': invalidation_price,
            'support_level': support_level,
            'current_vs_entry': zone_status
        }

    # 5. NEUTRAL dengan prior accumulation → HOLD/WAIT
    if overall_signal == 'NETRAL' and has_prior_accum:
        return {
            'decision': 'HOLD',
            'decision_id': 'hold',
            'color': 'info',
            'icon': '✋',
            'reason': 'Fase konsolidasi setelah akumulasi. Pertahankan posisi jika sudah punya, atau tunggu sinyal baru.',
            'entry_zone': {'low': entry_zone_low, 'high': entry_zone_high},
            'invalidation_price': invalidation_price,
            'support_level': support_level,
            'current_vs_entry': 'ABOVE' if current_price > entry_zone_high else 'IN_ZONE' if current_price >= entry_zone_low else 'BELOW'
        }

    # 6. Default → WAIT
    reasons = []
    if validation_score < 4:
        reasons.append(f"validasi hanya {validation_score}/6")
    if range_pct > 20:
        reasons.append(f"range terlalu lebar ({range_pct:.1f}%)")
    if 0.45 <= cpr_value <= 0.55:
        reasons.append("CPR netral (tarik-menarik)")

    return {
        'decision': 'WAIT',
        'decision_id': 'wait',
        'color': 'secondary',
        'icon': '⏳',
        'reason': f"Pasar belum siap: {', '.join(reasons) if reasons else 'sinyal tidak jelas'}. Observasi dulu.",
        'entry_zone': {'low': entry_zone_low, 'high': entry_zone_high},
        'invalidation_price': invalidation_price,
        'support_level': support_level,
        'current_vs_entry': 'ABOVE' if current_price > entry_zone_high else 'IN_ZONE' if current_price >= entry_zone_low else 'BELOW'
    }


# ============================================================
# MAIN: GET COMPREHENSIVE VALIDATION (Dinamis untuk semua emiten)
# ============================================================
def get_comprehensive_validation(stock_code: str, analysis_days: int = 30, params: dict = None) -> dict:
    """
    Fungsi utama untuk mendapatkan validasi komprehensif
    DINAMIS - Bisa dipakai untuk emiten apapun

    Args:
        stock_code: Kode saham (BBCA, TLKM, NCKL, dll)
        analysis_days: Jumlah hari analisis (default 30)
        params: Parameter custom (optional)

    Returns:
        Dict dengan semua hasil validasi dan confidence score
    """
    if params is None:
        params = DEFAULT_PARAMS.copy()
        params['analysis_days'] = analysis_days

    # Fetch data
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)
    stock_info = get_stock_info(stock_code)

    if price_df.empty:
        return {
            'error': f'Data harga tidak tersedia untuk {stock_code}',
            'stock_code': stock_code,
            'validations': {},
            'confidence': {'level': 'NO_DATA', 'passed': 0, 'total': 6, 'pass_rate': 0}
        }

    # Filter by analysis period
    end_date = price_df['date'].max()
    start_date = end_date - timedelta(days=analysis_days)

    price_filtered = price_df[price_df['date'] >= start_date].copy()
    broker_filtered = broker_df[broker_df['date'] >= start_date].copy() if not broker_df.empty else broker_df

    current_price = price_filtered.iloc[-1]['close_price'] if not price_filtered.empty else 0
    current_date = price_filtered.iloc[-1]['date'] if not price_filtered.empty else None

    # === RUN ALL VALIDATIONS ===
    validations = {}

    # 1. CPR
    validations['cpr'] = calculate_cpr(price_filtered, params)

    # 2. UV/DV
    validations['uvdv'] = calculate_uvdv(price_filtered, params)

    # 3. Broker Influence
    validations['broker_influence'] = calculate_broker_influence(broker_filtered)

    # 4. Broker Persistence
    validations['persistence'] = calculate_broker_persistence(broker_filtered, params)

    # 5. Failed Breaks
    validations['failed_breaks'] = calculate_failed_breaks(price_filtered, params)

    # 6. Elasticity
    validations['elasticity'] = calculate_elasticity(price_filtered)

    # 7. Rotation
    validations['rotation'] = calculate_rotation(broker_filtered, params)

    # === DETECTION (hanya dalam periode analisis) ===
    detection = detect_signal_period(price_filtered, broker_filtered)

    # === MARKUP TRIGGER DETECTION ===
    markup_trigger = detect_markup_trigger(price_filtered, broker_filtered, detection)

    # === IMPULSE/MOMENTUM DETECTION (NEW ENGINE) ===
    impulse_signal = detect_impulse_signal(price_filtered, broker_filtered, lookback=5)

    # === CALCULATE CONFIDENCE ===
    checks = ['cpr', 'uvdv', 'broker_influence', 'failed_breaks', 'elasticity', 'rotation']
    passed = sum(1 for c in checks if validations.get(c, {}).get('passed', False))
    total = len(checks)
    pass_rate = (passed / total * 100) if total > 0 else 0

    # Count signals
    accum_score = sum(1 for v in validations.values() if v.get('signal') == 'AKUMULASI')
    distrib_score = sum(1 for v in validations.values() if v.get('signal') == 'DISTRIBUSI')

    if accum_score > distrib_score:
        overall_signal = 'AKUMULASI'
    elif distrib_score > accum_score:
        overall_signal = 'DISTRIBUSI'
    else:
        overall_signal = 'NETRAL'

    # Confidence level
    if pass_rate >= 80:
        conf_level = 'VERY_HIGH'
        recommendation = 'Sinyal sangat kuat - layak untuk dipertimbangkan'
    elif pass_rate >= 60:
        conf_level = 'HIGH'
        recommendation = 'Sinyal kuat - perhatikan dengan serius'
    elif pass_rate >= 40:
        conf_level = 'MEDIUM'
        recommendation = 'Sinyal sedang - butuh konfirmasi tambahan'
    elif pass_rate >= 20:
        conf_level = 'LOW'
        recommendation = 'Sinyal lemah - risiko false positive tinggi'
    else:
        conf_level = 'VERY_LOW'
        recommendation = 'Tidak ada sinyal valid - hindari action'

    # === BUILD ONE-LINE INSIGHT (Context-aware) ===
    rotation = validations.get('rotation', {})
    num_accum = rotation.get('num_accumulators', 0)
    persistence = validations.get('persistence', {})
    max_streak = persistence.get('max_streak', 0)

    # Prioritas: Impulse > Markup Trigger > Accumulation > Distribution > Neutral
    if impulse_signal.get('impulse_detected'):
        # IMPULSE/MOMENTUM detected (highest priority - different engine!)
        imp_strength = impulse_signal.get('strength', 'WEAK')
        imp_metrics = impulse_signal.get('metrics', {})
        vol_ratio = imp_metrics.get('volume_ratio', 1)
        breakout_pct = imp_metrics.get('breakout_pct', 0)
        insight = f"MOMENTUM/IMPULSE terdeteksi ({imp_strength})! Volume {vol_ratio:.1f}x rata-rata dengan breakout +{breakout_pct:.1f}%. Risiko tinggi, momentum trader dominan."
    elif impulse_signal.get('near_impulse'):
        # Near impulse - almost triggered
        conds = impulse_signal.get('trigger_conditions', {})
        met = conds.get('conditions_met', 0)
        insight = f"Hampir impulse ({met}/3 kondisi). Pantau volume spike dan breakout untuk konfirmasi."
    elif markup_trigger.get('markup_triggered'):
        # Markup phase detected (after accumulation)
        source_str = markup_trigger.get('source_strength', 'WEAK')
        breakout_pct = markup_trigger.get('breakout_pct', 0)
        insight = f"Harga memasuki FASE MARKUP setelah akumulasi ({source_str}) terdeteksi. Breakout +{breakout_pct:.1f}% dari resistance terdekat."
    elif overall_signal == 'AKUMULASI':
        insight = f"Akumulasi terdeteksi oleh {num_accum} broker dengan konsistensi {max_streak} hari. {passed}/6 validasi terpenuhi."
    elif overall_signal == 'DISTRIBUSI':
        insight = f"Distribusi terdeteksi - {passed}/6 indikator menunjukkan pelepasan oleh pelaku besar."
    else:
        # Neutral - tapi cek apakah ada prior accumulation
        has_prior_accum = False
        if detection and detection.get('signal_history'):
            for h in detection['signal_history']:
                if h.get('signal') == 'ACCUMULATION':
                    has_prior_accum = True
                    break

        if has_prior_accum:
            insight = f"Fase konsolidasi setelah akumulasi awal. Pantau breakout untuk konfirmasi markup."
        else:
            insight = f"Pola belum jelas - hanya {passed}/6 validasi terpenuhi. Pantau perkembangan."

    # === WHAT THIS MEANS (Context-aware) ===
    if impulse_signal.get('impulse_detected'):
        # Impulse/Momentum explanation
        what_means = impulse_signal.get('educational', 'Momentum breakout terdeteksi tanpa fase akumulasi. Risiko tinggi.')
    elif impulse_signal.get('near_impulse'):
        what_means = "Sinyal momentum hampir terpenuhi. Salah satu kondisi (volume 2x, breakout, atau CPR bullish) belum tercapai. Pantau perkembangan."
    elif markup_trigger.get('markup_triggered'):
        what_means = f"Harga mulai bergerak naik setelah periode akumulasi. Ini adalah transisi dari pengumpulan ke markup. Volume dan momentum mendukung pergerakan ini."
    elif overall_signal == 'AKUMULASI' and conf_level in ['HIGH', 'VERY_HIGH']:
        what_means = "Ada pihak yang mengumpulkan saham secara bertahap. Pola ini biasanya muncul sebelum kenaikan, namun timing tidak bisa diprediksi."
    elif overall_signal == 'AKUMULASI':
        what_means = "Akumulasi awal terdeteksi namun belum terkonfirmasi kuat. Pantau perkembangan sebelum mengambil keputusan."
    elif overall_signal == 'DISTRIBUSI':
        what_means = "Terdeteksi penjualan bertahap oleh pelaku besar. Berhati-hati dengan posisi beli baru."
    else:
        what_means = "Pola belum terbentuk jelas. Pantau perkembangan untuk konfirmasi arah selanjutnya."

    # === CALCULATE PRICE RANGE ===
    if not price_filtered.empty:
        range_high = price_filtered['high_price'].max()
        range_low = price_filtered['low_price'].min()
        range_pct = ((range_high - range_low) / range_low * 100) if range_low > 0 else 0
    else:
        range_pct = 0

    # === DECISION RULE ===
    cpr_value = validations.get('cpr', {}).get('avg_cpr', 0.5)
    decision_rule = calculate_decision_rule(
        price_filtered, passed, overall_signal, cpr_value, range_pct, markup_trigger, detection
    )

    return {
        'stock_code': stock_code,
        'stock_info': stock_info,
        'analysis_date': current_date,
        'current_price': current_price,
        'period': {
            'start': start_date,
            'end': end_date,
            'days': analysis_days
        },
        'detection': detection,
        'markup_trigger': markup_trigger,
        'impulse_signal': impulse_signal,
        'decision_rule': decision_rule,
        'validations': validations,
        'summary': {
            'overall_signal': overall_signal,
            'accum_score': accum_score,
            'distrib_score': distrib_score,
            'insight': insight,
            'what_means': what_means
        },
        'confidence': {
            'level': conf_level,
            'passed': passed,
            'total': total,
            'pass_rate': round(pass_rate, 1),
            'recommendation': recommendation
        }
    }


# ============================================================
# UNIFIED ANALYSIS SUMMARY (Gabungan 3 Submenu)
# ============================================================
def get_unified_analysis_summary(stock_code: str) -> dict:
    """
    Mengumpulkan semua data dari 3 submenu untuk halaman Analysis utama.

    Returns:
        dict dengan:
        - decision: Keputusan utama (WAIT/ENTRY/ADD/HOLD/EXIT)
        - fundamental: Ringkasan fundamental
        - support_resistance: Level-level kunci
        - accumulation: Hasil deteksi akumulasi
        - key_points: Poin-poin penting untuk keputusan
    """
    # 1. Get Accumulation data (sudah lengkap)
    accum_data = get_comprehensive_validation(stock_code, 30)

    # 2. Get Fundamental data
    fundamental = {}
    try:
        query = """
            SELECT * FROM stock_fundamental
            WHERE stock_code = %s
            ORDER BY report_date DESC LIMIT 1
        """
        result = execute_query(query, (stock_code,))
        if result:
            row = result[0]
            per = row.get('per', 0) or 0
            pbvr = row.get('pbvr', 0) or 0
            roe = row.get('roe', 0) or 0

            # Valuasi assessment
            if per > 0 and per < 15:
                valuation = 'MURAH'
                valuation_color = 'success'
            elif per >= 15 and per <= 25:
                valuation = 'WAJAR'
                valuation_color = 'warning'
            else:
                valuation = 'MAHAL' if per > 25 else 'N/A'
                valuation_color = 'danger' if per > 25 else 'secondary'

            fundamental = {
                'per': per,
                'pbvr': pbvr,
                'roe': roe,
                'valuation': valuation,
                'valuation_color': valuation_color,
                'has_data': True
            }
        else:
            fundamental = {'has_data': False, 'valuation': 'N/A', 'valuation_color': 'secondary'}
    except:
        fundamental = {'has_data': False, 'valuation': 'N/A', 'valuation_color': 'secondary'}

    # 3. Get Support & Resistance data (using multi-method analysis for consistency with S/R submenu)
    support_resistance = {}
    try:
        sr_analysis = analyze_support_resistance(stock_code)
        if sr_analysis and sr_analysis.get('current_price'):
            current_price = sr_analysis['current_price']
            key_support = sr_analysis.get('key_support', current_price * 0.95)
            key_resistance = sr_analysis.get('key_resistance', current_price * 1.05)
            interpretation = sr_analysis.get('interpretation', {})

            dist_from_support = interpretation.get('support_distance_pct', 0)
            dist_from_resistance = interpretation.get('resistance_distance_pct', 0)

            support_resistance = {
                'current_price': current_price,
                'support_20d': key_support,  # Using multi-method key support
                'resistance_20d': key_resistance,  # Using multi-method key resistance
                'dist_from_support': dist_from_support,
                'dist_from_resistance': dist_from_resistance,
                'position': 'NEAR_SUPPORT' if dist_from_support < 5 else 'NEAR_RESISTANCE' if dist_from_resistance < 5 else 'MIDDLE',
                'has_data': True,
                'sr_analysis': sr_analysis  # Include full analysis for reference
            }
        else:
            support_resistance = {'has_data': False}
    except Exception as e:
        support_resistance = {'has_data': False, 'error': str(e)}

    # 4. Build Key Points for Decision
    key_points = []
    warnings = []

    # From Accumulation and Momentum Engines
    decision_rule = accum_data.get('decision_rule', {})
    markup_trigger = accum_data.get('markup_trigger', {})
    impulse_signal = accum_data.get('impulse_signal', {})
    confidence = accum_data.get('confidence', {})

    # HIGHEST PRIORITY: Impulse/Momentum Signal
    if impulse_signal.get('impulse_detected'):
        imp_strength = impulse_signal.get('strength', 'WEAK')
        imp_metrics = impulse_signal.get('metrics', {})
        vol_ratio = imp_metrics.get('volume_ratio', 1)
        key_points.insert(0, {
            'icon': '⚡',
            'text': f'MOMENTUM ({imp_strength}) - Volume {vol_ratio:.1f}x, breakout terdeteksi',
            'color': 'danger'  # Red to indicate high risk
        })
        warnings.append({
            'icon': '⚠️',
            'text': 'Risiko tinggi! Momentum tanpa akumulasi. Gunakan stop loss ketat.',
            'color': 'danger'
        })
    elif impulse_signal.get('near_impulse'):
        conds = impulse_signal.get('trigger_conditions', {})
        met = conds.get('conditions_met', 0)
        key_points.append({
            'icon': '👁️',
            'text': f'Hampir impulse ({met}/3 kondisi). Pantau volume spike.',
            'color': 'info'
        })

    # Markup trigger (after accumulation)
    if markup_trigger.get('markup_triggered') and not impulse_signal.get('impulse_detected'):
        key_points.append({
            'icon': '🔥',
            'text': 'MARKUP TRIGGERED - Harga breakout setelah akumulasi',
            'color': 'warning'
        })

    if confidence.get('pass_rate', 0) >= 60:
        key_points.append({
            'icon': '✅',
            'text': f"Validasi kuat: {confidence.get('passed', 0)}/6 kriteria terpenuhi",
            'color': 'success'
        })
    elif confidence.get('pass_rate', 0) < 40:
        warnings.append({
            'icon': '⚠️',
            'text': f"Validasi lemah: hanya {confidence.get('passed', 0)}/6 kriteria",
            'color': 'danger'
        })

    # From Support/Resistance
    if support_resistance.get('has_data'):
        if support_resistance.get('position') == 'NEAR_SUPPORT':
            key_points.append({
                'icon': '🛡️',
                'text': f"Harga dekat support (Rp {support_resistance.get('support_20d', 0):,.0f})",
                'color': 'success'
            })
        elif support_resistance.get('position') == 'NEAR_RESISTANCE':
            warnings.append({
                'icon': '🚧',
                'text': f"Harga dekat resistance (Rp {support_resistance.get('resistance_20d', 0):,.0f})",
                'color': 'warning'
            })

    # From Fundamental
    if fundamental.get('has_data'):
        if fundamental.get('valuation') == 'MURAH':
            key_points.append({
                'icon': '💰',
                'text': f"Valuasi murah (PER: {fundamental.get('per', 0):.1f}x)",
                'color': 'success'
            })
        elif fundamental.get('valuation') == 'MAHAL':
            warnings.append({
                'icon': '💸',
                'text': f"Valuasi mahal (PER: {fundamental.get('per', 0):.1f}x)",
                'color': 'danger'
            })

    # 5. Final Decision Summary
    decision = decision_rule.get('decision', 'WAIT')
    decision_icon = decision_rule.get('icon', '⏳')
    decision_color = decision_rule.get('color', 'secondary')
    decision_reason = decision_rule.get('reason', '')

    # Override decision description for better clarity
    decision_descriptions = {
        'WAIT': 'Observasi dulu, sinyal belum jelas',
        'ENTRY': 'Pertimbangkan untuk masuk bertahap',
        'ADD': 'Layak untuk menambah posisi',
        'HOLD': 'Pertahankan posisi, jangan kejar',
        'EXIT': 'Pertimbangkan untuk keluar/kurangi',
        # Momentum-specific decisions
        'MASUK_MOMENTUM': 'Entry momentum dengan stop loss ketat',
        'PANTAU_BREAKOUT': 'Momentum building, pantau konfirmasi',
        'TUNGGU': 'Sinyal lemah, tunggu konfirmasi',
        'SIAGA': 'Hampir impulse, siapkan watchlist',
        'TIDAK_ADA_SINYAL': 'Tidak ada sinyal momentum'
    }

    # Check if impulse overrides accumulation decision
    if impulse_signal.get('impulse_detected'):
        imp_decision = impulse_signal.get('decision', {})
        decision = imp_decision.get('action', decision)
        decision_reason = imp_decision.get('reason', decision_reason)
        decision_icon = '⚡'
        decision_color = 'danger'  # Red for high risk momentum

    return {
        'stock_code': stock_code,
        'decision': {
            'action': decision,
            'icon': decision_icon,
            'color': decision_color,
            'reason': decision_reason,
            'description': decision_descriptions.get(decision, decision_reason)
        },
        'accumulation': accum_data,
        'impulse': impulse_signal,
        'fundamental': fundamental,
        'support_resistance': support_resistance,
        'key_points': key_points,
        'warnings': warnings,
        'entry_zone': decision_rule.get('entry_zone'),
        'invalidation': decision_rule.get('invalidation_price'),
        'support_level': decision_rule.get('support_level')
    }


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    # Test dengan beberapa emiten
    for stock in ['NCKL', 'BBCA', 'PANI']:
        print(f"\n{'='*70}")
        print(f"VALIDASI: {stock}")
        print(f"{'='*70}")

        result = get_comprehensive_validation(stock, 30)

        if result.get('error'):
            print(f"Error: {result['error']}")
            continue

        print(f"Tanggal: {result['analysis_date']}")
        print(f"Harga: Rp {result['current_price']:,.0f}")
        print(f"\nInsight: {result['summary']['insight']}")
        print(f"\nValidasi:")
        for name, v in result['validations'].items():
            status = 'PASS' if v.get('passed') else 'FAIL'
            print(f"  [{status}] {name}: {v.get('signal', 'N/A')}")

        print(f"\nConfidence: {result['confidence']['level']} ({result['confidence']['pass_rate']}%)")
        print(f"Rekomendasi: {result['confidence']['recommendation']}")
