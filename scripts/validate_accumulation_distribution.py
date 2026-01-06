"""
VALIDATION LAYER untuk Akumulasi vs Distribusi
Confirmation Stack untuk memastikan sinyal tidak false positive

Validation Checks:
1. Market Acceptance Test (Close ≈ VWAP)
2. Failed Breakdown/Breakout Count
3. Volume Elasticity Test
4. Time Compression Validation
5. Broker Rotation Check
6. Loss Absorption Test
7. Multi-Timeframe Agreement
8. Final Confidence Matrix
"""
import sys
sys.path.insert(0, 'C:/Users/chuwi/stock-analysis/app')

import pandas as pd
import numpy as np
from datetime import timedelta
from database import execute_query

# Import fungsi dari script sebelumnya
from detect_accumulation_distribution import (
    get_price_data, get_broker_data, get_issued_shares,
    identify_sideways_periods, calculate_cpr, calculate_uvdv,
    calculate_vrpr, calculate_broker_influence, calculate_broker_persistence,
    calculate_absorption, calculate_smart_money_divergence, calculate_final_score
)


# ============================================================
# VALIDATION 1: MARKET ACCEPTANCE TEST
# ============================================================
def validate_market_acceptance(price_df: pd.DataFrame, start_date, end_date, tolerance_pct=0.3) -> dict:
    """
    Market Acceptance = Close ≈ VWAP

    Acceptance Ratio = jumlah hari ABS(Close - VWAP) / VWAP <= 0.3%

    Tinggi + net buy → Akumulasi valid
    Tinggi + net sell → Distribusi rapi
    Rendah → False signal
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    if df.empty:
        return {'acceptance_ratio': 0, 'passed': False}

    # Hitung VWAP per hari: VWAP = Cumulative(Price × Volume) / Cumulative(Volume)
    # Untuk harian, kita bisa approx dengan Typical Price
    df['typical_price'] = (df['high_price'] + df['low_price'] + df['close_price']) / 3

    # Untuk running VWAP selama periode
    df['cum_pv'] = (df['typical_price'] * df['volume']).cumsum()
    df['cum_vol'] = df['volume'].cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']

    # Hitung acceptance per hari
    df['vwap_diff_pct'] = abs(df['close_price'] - df['vwap']) / df['vwap'] * 100
    df['is_accepted'] = df['vwap_diff_pct'] <= tolerance_pct

    acceptance_ratio = df['is_accepted'].sum() / len(df) * 100 if len(df) > 0 else 0

    # Berapa hari close di atas vs di bawah VWAP
    above_vwap = len(df[df['close_price'] > df['vwap']])
    below_vwap = len(df[df['close_price'] < df['vwap']])

    # Signal
    if acceptance_ratio >= 50:
        if above_vwap > below_vwap:
            signal = 'AKUMULASI VALID'
        else:
            signal = 'DISTRIBUSI RAPI'
        passed = True
    else:
        signal = 'FALSE SIGNAL RISK'
        passed = False

    return {
        'acceptance_ratio': round(acceptance_ratio, 1),
        'days_above_vwap': above_vwap,
        'days_below_vwap': below_vwap,
        'signal': signal,
        'passed': passed,
        'score': 1 if passed else 0
    }


# ============================================================
# VALIDATION 2: FAILED BREAKDOWN/BREAKOUT COUNT
# ============================================================
def validate_failed_breaks(price_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Failed Breakdown = tembus low range tapi gagal close di bawahnya
    Failed Breakout = tembus high range tapi gagal close di atasnya

    2-3x failed breakdown → Akumulasi
    2-3x failed breakout → Distribusi
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    if len(df) < 5:
        return {'failed_breakdowns': 0, 'failed_breakouts': 0, 'signal': 'INSUFFICIENT DATA'}

    # Hitung range support/resistance
    range_high = df['high_price'].quantile(0.9)  # Resistance zone
    range_low = df['low_price'].quantile(0.1)    # Support zone

    failed_breakdowns = 0
    failed_breakouts = 0

    for i in range(1, len(df)):
        row = df.iloc[i]

        # Failed breakdown: low tembus support tapi close di atasnya
        if row['low_price'] < range_low and row['close_price'] > range_low:
            failed_breakdowns += 1

        # Failed breakout: high tembus resistance tapi close di bawahnya
        if row['high_price'] > range_high and row['close_price'] < range_high:
            failed_breakouts += 1

    # Interpretasi
    if failed_breakdowns >= 2 and failed_breakdowns > failed_breakouts:
        signal = 'AKUMULASI (support defended)'
        passed = True
        direction = 'ACCUMULATION'
    elif failed_breakouts >= 2 and failed_breakouts > failed_breakdowns:
        signal = 'DISTRIBUSI (resistance held)'
        passed = True
        direction = 'DISTRIBUTION'
    else:
        signal = 'NETRAL'
        passed = False
        direction = 'NEUTRAL'

    return {
        'range_high': range_high,
        'range_low': range_low,
        'failed_breakdowns': failed_breakdowns,
        'failed_breakouts': failed_breakouts,
        'signal': signal,
        'direction': direction,
        'passed': passed,
        'score': 1 if passed else 0
    }


# ============================================================
# VALIDATION 3: VOLUME ELASTICITY TEST
# ============================================================
def validate_volume_elasticity(price_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Elasticity = %ΔPrice / %ΔVolume

    Elasticity Rendah = Ada penahan (akum/distribusi)
    Elasticity Tinggi = Pasar bebas (markup/markdown)

    Sideway + volume naik + elasticity rendah = validasi kuat
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    if len(df) < 5:
        return {'elasticity': 0, 'signal': 'INSUFFICIENT DATA'}

    # Hitung perubahan harga dan volume
    first_close = df.iloc[0]['close_price']
    last_close = df.iloc[-1]['close_price']
    price_change_pct = abs((last_close - first_close) / first_close * 100)

    first_vol = df.iloc[:5]['volume'].mean()  # Avg 5 hari pertama
    last_vol = df.iloc[-5:]['volume'].mean()  # Avg 5 hari terakhir
    volume_change_pct = abs((last_vol - first_vol) / first_vol * 100) if first_vol > 0 else 0

    # Elasticity
    elasticity = price_change_pct / volume_change_pct if volume_change_pct > 0 else float('inf')

    # Interpretasi
    # Elasticity < 0.5 → harga bergerak sedikit meski volume berubah banyak
    if elasticity < 0.3 and volume_change_pct > 10:
        signal = 'VALIDASI KUAT (volume naik, harga tertahan)'
        passed = True
    elif elasticity < 0.5:
        signal = 'VALIDASI SEDANG'
        passed = True
    else:
        signal = 'PASAR BEBAS (tidak ada penahan)'
        passed = False

    return {
        'price_change_pct': round(price_change_pct, 2),
        'volume_change_pct': round(volume_change_pct, 2),
        'elasticity': round(elasticity, 3) if elasticity != float('inf') else 'INF',
        'signal': signal,
        'passed': passed,
        'score': 1 if passed else 0
    }


# ============================================================
# VALIDATION 4: TIME COMPRESSION VALIDATION
# ============================================================
def validate_time_compression(price_df: pd.DataFrame, start_date, end_date) -> dict:
    """
    Time Compression = Energy build-up

    Cek:
    - Range makin sempit (STDDEV(High-Low) ↓)
    - Volume stabil / naik
    - Volatilitas turun

    Jika didukung net buy → Akumulasi valid
    """
    df = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()

    if len(df) < 10:
        return {'compression_detected': False, 'signal': 'INSUFFICIENT DATA'}

    # Bagi jadi 2 bagian: awal vs akhir
    mid_point = len(df) // 2
    first_half = df.iloc[:mid_point]
    second_half = df.iloc[mid_point:]

    # Hitung range per hari
    first_half_range = (first_half['high_price'] - first_half['low_price']).std()
    second_half_range = (second_half['high_price'] - second_half['low_price']).std()

    # Hitung volume
    first_half_vol = first_half['volume'].mean()
    second_half_vol = second_half['volume'].mean()

    # Compression = range menyempit
    range_compression = second_half_range < first_half_range
    volume_stable_up = second_half_vol >= first_half_vol * 0.8  # Volume tidak turun signifikan

    compression_detected = range_compression and volume_stable_up

    if compression_detected:
        signal = 'ENERGY BUILD-UP DETECTED'
        passed = True
    else:
        signal = 'NO COMPRESSION'
        passed = False

    return {
        'first_half_range_std': round(first_half_range, 2),
        'second_half_range_std': round(second_half_range, 2),
        'range_compression': range_compression,
        'first_half_vol': round(first_half_vol, 0),
        'second_half_vol': round(second_half_vol, 0),
        'volume_stable': volume_stable_up,
        'compression_detected': compression_detected,
        'signal': signal,
        'passed': passed,
        'score': 1 if passed else 0
    }


# ============================================================
# VALIDATION 5: BROKER ROTATION CHECK
# ============================================================
def validate_broker_rotation(broker_df: pd.DataFrame, start_date, end_date, min_brokers=3) -> dict:
    """
    Broker Rotation = Multiple brokers accumulating/distributing

    Rotasi sehat (>=3 broker searah) → Akumulasi institusi
    Satu broker doang → Spekulatif

    Institusi besar jarang kerja sendirian.
    """
    df = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)].copy()

    if df.empty:
        return {'rotation_valid': False, 'signal': 'NO DATA'}

    # Hitung net lot per broker
    broker_totals = df.groupby('broker_code').agg({
        'net_lot': 'sum',
        'net_value': 'sum'
    }).reset_index()

    # Hitung berapa broker yang net buy vs net sell
    accumulators = broker_totals[broker_totals['net_lot'] > 0]
    distributors = broker_totals[broker_totals['net_lot'] < 0]

    num_accumulators = len(accumulators)
    num_distributors = len(distributors)

    # Top accumulators
    top_accum = accumulators.nlargest(5, 'net_lot')
    top_distrib = distributors.nsmallest(5, 'net_lot')

    # Cek apakah top 3 punya kontribusi signifikan
    if num_accumulators >= min_brokers:
        top3_accum_lot = top_accum.head(3)['net_lot'].sum()
        total_accum_lot = accumulators['net_lot'].sum()
        concentration = top3_accum_lot / total_accum_lot * 100 if total_accum_lot > 0 else 0

        if concentration < 80:  # Tidak terkonsentrasi di 1-2 broker
            rotation_valid = True
            signal = 'ROTASI SEHAT (multi-broker akumulasi)'
            direction = 'ACCUMULATION'
        else:
            rotation_valid = False
            signal = 'TERKONSENTRASI (spekulatif)'
            direction = 'SPECULATIVE'
    elif num_distributors >= min_brokers:
        top3_distrib_lot = abs(top_distrib.head(3)['net_lot'].sum())
        total_distrib_lot = abs(distributors['net_lot'].sum())
        concentration = top3_distrib_lot / total_distrib_lot * 100 if total_distrib_lot > 0 else 0

        if concentration < 80:
            rotation_valid = True
            signal = 'ROTASI SEHAT (multi-broker distribusi)'
            direction = 'DISTRIBUTION'
        else:
            rotation_valid = False
            signal = 'TERKONSENTRASI (spekulatif)'
            direction = 'SPECULATIVE'
    else:
        rotation_valid = False
        signal = 'TIDAK CUKUP BROKER'
        direction = 'UNKNOWN'
        concentration = 0

    return {
        'num_accumulators': num_accumulators,
        'num_distributors': num_distributors,
        'top_accumulators': top_accum[['broker_code', 'net_lot']].to_dict('records'),
        'top_distributors': top_distrib[['broker_code', 'net_lot']].to_dict('records'),
        'concentration_pct': round(concentration, 1) if 'concentration' in dir() else 0,
        'rotation_valid': rotation_valid,
        'signal': signal,
        'direction': direction,
        'passed': rotation_valid,
        'score': 1 if rotation_valid else 0
    }


# ============================================================
# VALIDATION 6: LOSS ABSORPTION TEST
# ============================================================
def validate_loss_absorption(price_df: pd.DataFrame, broker_df: pd.DataFrame,
                              start_date, end_date) -> dict:
    """
    Loss Absorption = Down days tanpa follow-through

    Cek:
    - Banyak candle merah
    - Tapi low tidak turun signifikan
    - Broker besar net buy

    → Distribusi risiko ke pasar = Akumulasi
    """
    pdf = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()
    bdf = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)]

    if pdf.empty:
        return {'absorption_valid': False, 'signal': 'NO DATA'}

    # Hitung down days (close < open)
    pdf['is_down'] = pdf['close_price'] < pdf['open_price']
    down_days = pdf['is_down'].sum()
    total_days = len(pdf)
    down_ratio = down_days / total_days * 100 if total_days > 0 else 0

    # Hitung apakah low turun signifikan
    first_low = pdf.iloc[0]['low_price']
    min_low = pdf['low_price'].min()
    low_drop_pct = (first_low - min_low) / first_low * 100

    # Cek net broker selama down days
    down_dates = pdf[pdf['is_down']]['date'].tolist()
    broker_on_down = bdf[bdf['date'].isin(down_dates)]
    net_lot_on_down = broker_on_down['net_lot'].sum() if not broker_on_down.empty else 0

    # Absorption = banyak down days, tapi low tidak turun banyak, dan ada net buy
    if down_ratio >= 40 and low_drop_pct < 5 and net_lot_on_down > 0:
        absorption_valid = True
        signal = 'LOSS ABSORBED (akumulasi valid)'
    elif down_ratio >= 30 and low_drop_pct < 3:
        absorption_valid = True
        signal = 'PARTIAL ABSORPTION'
    else:
        absorption_valid = False
        signal = 'NO ABSORPTION'

    return {
        'down_days': down_days,
        'total_days': total_days,
        'down_ratio_pct': round(down_ratio, 1),
        'low_drop_pct': round(low_drop_pct, 2),
        'net_lot_on_down_days': net_lot_on_down,
        'absorption_valid': absorption_valid,
        'signal': signal,
        'passed': absorption_valid,
        'score': 1 if absorption_valid else 0
    }


# ============================================================
# VALIDATION 7: MULTI-TIMEFRAME AGREEMENT
# ============================================================
def validate_multi_timeframe(price_df: pd.DataFrame, broker_df: pd.DataFrame,
                              start_date, end_date) -> dict:
    """
    Multi-Timeframe Agreement

    Kalau daily & weekly beda cerita → jangan percaya daily.

    Validasi:
    - Weekly CPR >= 0.55
    - Weekly broker flow searah daily
    """
    pdf = price_df[(price_df['date'] >= start_date) & (price_df['date'] <= end_date)].copy()
    bdf = broker_df[(broker_df['date'] >= start_date) & (broker_df['date'] <= end_date)].copy()

    if len(pdf) < 7:
        return {'mtf_agreement': False, 'signal': 'INSUFFICIENT DATA', 'passed': False,
                'weekly_avg_cpr': 0, 'daily_avg_cpr': 0, 'weekly_net_lot': 0, 'daily_net_lot': 0,
                'cpr_agreement': False, 'flow_agreement': False, 'score': 0}

    # Pastikan date adalah datetime
    pdf['date'] = pd.to_datetime(pdf['date'])
    bdf['date'] = pd.to_datetime(bdf['date'])

    # Konversi ke weekly
    pdf['week'] = pdf['date'].dt.isocalendar().week
    pdf['year'] = pdf['date'].dt.year

    weekly = pdf.groupby(['year', 'week']).agg({
        'open_price': 'first',
        'high_price': 'max',
        'low_price': 'min',
        'close_price': 'last',
        'volume': 'sum'
    }).reset_index()

    # Hitung weekly CPR
    weekly['range'] = weekly['high_price'] - weekly['low_price']
    weekly['cpr'] = np.where(weekly['range'] > 0,
                             (weekly['close_price'] - weekly['low_price']) / weekly['range'],
                             0.5)

    weekly_avg_cpr = weekly['cpr'].mean()

    # Hitung daily CPR untuk perbandingan
    pdf['range'] = pdf['high_price'] - pdf['low_price']
    pdf['cpr'] = np.where(pdf['range'] > 0,
                          (pdf['close_price'] - pdf['low_price']) / pdf['range'],
                          0.5)
    daily_avg_cpr = pdf['cpr'].mean()

    # Hitung weekly broker flow
    bdf_copy = bdf.copy()
    bdf_copy['week'] = bdf_copy['date'].dt.isocalendar().week
    bdf_copy['year'] = bdf_copy['date'].dt.year

    weekly_broker = bdf_copy.groupby(['year', 'week']).agg({
        'net_lot': 'sum',
        'net_value': 'sum'
    }).reset_index()

    weekly_net_lot = weekly_broker['net_lot'].sum()
    daily_net_lot = bdf['net_lot'].sum()

    # Agreement check
    # CPR agreement
    cpr_agreement = (weekly_avg_cpr >= 0.55 and daily_avg_cpr >= 0.55) or \
                   (weekly_avg_cpr <= 0.45 and daily_avg_cpr <= 0.45)

    # Flow agreement
    flow_agreement = (weekly_net_lot > 0 and daily_net_lot > 0) or \
                    (weekly_net_lot < 0 and daily_net_lot < 0)

    mtf_agreement = cpr_agreement and flow_agreement

    if mtf_agreement:
        if weekly_avg_cpr >= 0.55 and weekly_net_lot > 0:
            signal = 'MTF AGREEMENT: AKUMULASI'
        elif weekly_avg_cpr <= 0.45 and weekly_net_lot < 0:
            signal = 'MTF AGREEMENT: DISTRIBUSI'
        else:
            signal = 'MTF AGREEMENT: SEARAH'
    else:
        signal = 'MTF CONFLICT (hati-hati!)'

    return {
        'weekly_avg_cpr': round(weekly_avg_cpr, 3),
        'daily_avg_cpr': round(daily_avg_cpr, 3),
        'weekly_net_lot': weekly_net_lot,
        'daily_net_lot': daily_net_lot,
        'cpr_agreement': cpr_agreement,
        'flow_agreement': flow_agreement,
        'mtf_agreement': mtf_agreement,
        'signal': signal,
        'passed': mtf_agreement,
        'score': 1 if mtf_agreement else 0
    }


# ============================================================
# FINAL CONFIDENCE MATRIX
# ============================================================
def calculate_confidence_matrix(validations: dict) -> dict:
    """
    Final Confidence Matrix

    Entry hanya kalau >= 6 poin lolos:
    ☑ Sideway valid
    ☑ Broker influence jelas
    ☑ Persistence cukup
    ☑ Market acceptance tinggi
    ☑ Elasticity rendah
    ☑ Failed breakdown/breakout
    ☑ Multi-timeframe searah
    ☑ Broker rotation sehat
    """
    checklist = {
        'market_acceptance': validations.get('market_acceptance', {}).get('passed', False),
        'failed_breaks': validations.get('failed_breaks', {}).get('passed', False),
        'volume_elasticity': validations.get('volume_elasticity', {}).get('passed', False),
        'time_compression': validations.get('time_compression', {}).get('passed', False),
        'broker_rotation': validations.get('broker_rotation', {}).get('passed', False),
        'loss_absorption': validations.get('loss_absorption', {}).get('passed', False),
        'multi_timeframe': validations.get('multi_timeframe', {}).get('passed', False),
    }

    passed_count = sum(checklist.values())
    total_checks = len(checklist)

    # Confidence level
    if passed_count >= 6:
        confidence = 'VERY HIGH'
        recommendation = 'VALID SIGNAL - Safe to act'
    elif passed_count >= 5:
        confidence = 'HIGH'
        recommendation = 'VALID SIGNAL - Proceed with caution'
    elif passed_count >= 4:
        confidence = 'MEDIUM'
        recommendation = 'POSSIBLE SIGNAL - Need more confirmation'
    elif passed_count >= 2:
        confidence = 'LOW'
        recommendation = 'WEAK SIGNAL - High risk of false positive'
    else:
        confidence = 'VERY LOW'
        recommendation = 'INVALID SIGNAL - Do not act'

    return {
        'checklist': checklist,
        'passed_count': passed_count,
        'total_checks': total_checks,
        'pass_rate_pct': round(passed_count / total_checks * 100, 1),
        'confidence': confidence,
        'recommendation': recommendation
    }


# ============================================================
# MAIN VALIDATION FUNCTION
# ============================================================
def run_full_validation(stock_code: str, analysis_days: int = 30):
    """
    Run semua validation checks untuk stock tertentu
    """
    print(f"\n{'='*80}")
    print(f"VALIDATION LAYER: {stock_code}")
    print(f"{'='*80}")

    # Load data
    price_df = get_price_data(stock_code)
    broker_df = get_broker_data(stock_code)

    # Tentukan periode analisa
    end_date = price_df['date'].max()
    start_date = end_date - timedelta(days=analysis_days)

    print(f"\nPeriode Analisa: {start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}")
    print(f"Total: {analysis_days} hari")

    validations = {}

    # Validation 1: Market Acceptance
    print(f"\n{'='*80}")
    print("VALIDATION 1: MARKET ACCEPTANCE TEST")
    print(f"{'='*80}")
    v1 = validate_market_acceptance(price_df, start_date, end_date)
    validations['market_acceptance'] = v1
    print(f"  Acceptance Ratio: {v1['acceptance_ratio']}%")
    print(f"  Days Above VWAP: {v1['days_above_vwap']}")
    print(f"  Days Below VWAP: {v1['days_below_vwap']}")
    print(f"  Signal: {v1['signal']}")
    print(f"  PASSED: {'YES' if v1['passed'] else 'NO'}")

    # Validation 2: Failed Breaks
    print(f"\n{'='*80}")
    print("VALIDATION 2: FAILED BREAKDOWN/BREAKOUT COUNT")
    print(f"{'='*80}")
    v2 = validate_failed_breaks(price_df, start_date, end_date)
    validations['failed_breaks'] = v2
    print(f"  Range: Rp {v2.get('range_low', 0):,.0f} - Rp {v2.get('range_high', 0):,.0f}")
    print(f"  Failed Breakdowns: {v2['failed_breakdowns']}")
    print(f"  Failed Breakouts: {v2['failed_breakouts']}")
    print(f"  Signal: {v2['signal']}")
    print(f"  PASSED: {'YES' if v2['passed'] else 'NO'}")

    # Validation 3: Volume Elasticity
    print(f"\n{'='*80}")
    print("VALIDATION 3: VOLUME ELASTICITY TEST")
    print(f"{'='*80}")
    v3 = validate_volume_elasticity(price_df, start_date, end_date)
    validations['volume_elasticity'] = v3
    print(f"  Price Change: {v3['price_change_pct']}%")
    print(f"  Volume Change: {v3['volume_change_pct']}%")
    print(f"  Elasticity: {v3['elasticity']}")
    print(f"  Signal: {v3['signal']}")
    print(f"  PASSED: {'YES' if v3['passed'] else 'NO'}")

    # Validation 4: Time Compression
    print(f"\n{'='*80}")
    print("VALIDATION 4: TIME COMPRESSION VALIDATION")
    print(f"{'='*80}")
    v4 = validate_time_compression(price_df, start_date, end_date)
    validations['time_compression'] = v4
    print(f"  First Half Range STD: {v4.get('first_half_range_std', 'N/A')}")
    print(f"  Second Half Range STD: {v4.get('second_half_range_std', 'N/A')}")
    print(f"  Range Compression: {'YA' if v4.get('range_compression') else 'TIDAK'}")
    print(f"  Volume Stable: {'YA' if v4.get('volume_stable') else 'TIDAK'}")
    print(f"  Signal: {v4['signal']}")
    print(f"  PASSED: {'YES' if v4['passed'] else 'NO'}")

    # Validation 5: Broker Rotation
    print(f"\n{'='*80}")
    print("VALIDATION 5: BROKER ROTATION CHECK")
    print(f"{'='*80}")
    v5 = validate_broker_rotation(broker_df, start_date, end_date)
    validations['broker_rotation'] = v5
    print(f"  Accumulators: {v5['num_accumulators']} broker")
    print(f"  Distributors: {v5['num_distributors']} broker")
    print(f"  Concentration: {v5.get('concentration_pct', 0)}%")
    print(f"  Signal: {v5['signal']}")
    print(f"  PASSED: {'YES' if v5['passed'] else 'NO'}")

    if v5.get('top_accumulators'):
        print(f"\n  Top Accumulators:")
        for b in v5['top_accumulators'][:3]:
            print(f"    {b['broker_code']}: {b['net_lot']:+,.0f} lot")

    # Validation 6: Loss Absorption
    print(f"\n{'='*80}")
    print("VALIDATION 6: LOSS ABSORPTION TEST")
    print(f"{'='*80}")
    v6 = validate_loss_absorption(price_df, broker_df, start_date, end_date)
    validations['loss_absorption'] = v6
    print(f"  Down Days: {v6['down_days']}/{v6['total_days']} ({v6['down_ratio_pct']}%)")
    print(f"  Low Drop: {v6['low_drop_pct']}%")
    print(f"  Net Lot on Down Days: {v6['net_lot_on_down_days']:+,.0f}")
    print(f"  Signal: {v6['signal']}")
    print(f"  PASSED: {'YES' if v6['passed'] else 'NO'}")

    # Validation 7: Multi-Timeframe
    print(f"\n{'='*80}")
    print("VALIDATION 7: MULTI-TIMEFRAME AGREEMENT")
    print(f"{'='*80}")
    v7 = validate_multi_timeframe(price_df, broker_df, start_date, end_date)
    validations['multi_timeframe'] = v7
    print(f"  Weekly CPR: {v7['weekly_avg_cpr']}")
    print(f"  Daily CPR: {v7['daily_avg_cpr']}")
    print(f"  Weekly Net Lot: {v7['weekly_net_lot']:+,.0f}")
    print(f"  Daily Net Lot: {v7['daily_net_lot']:+,.0f}")
    print(f"  CPR Agreement: {'YA' if v7['cpr_agreement'] else 'TIDAK'}")
    print(f"  Flow Agreement: {'YA' if v7['flow_agreement'] else 'TIDAK'}")
    print(f"  Signal: {v7['signal']}")
    print(f"  PASSED: {'YES' if v7['passed'] else 'NO'}")

    # Final Confidence Matrix
    print(f"\n{'='*80}")
    print("FINAL CONFIDENCE MATRIX")
    print(f"{'='*80}")

    confidence = calculate_confidence_matrix(validations)

    print(f"\n  CHECKLIST:")
    for check, passed in confidence['checklist'].items():
        status = 'YES' if passed else 'NO'
        print(f"    [{status}] {check.replace('_', ' ').title()}")

    print(f"\n  SUMMARY:")
    print(f"    Passed: {confidence['passed_count']}/{confidence['total_checks']} ({confidence['pass_rate_pct']}%)")
    print(f"    Confidence Level: {confidence['confidence']}")

    print(f"\n{'='*80}")
    print(f"  >>> RECOMMENDATION: {confidence['recommendation']} <<<")
    print(f"{'='*80}")

    return {
        'stock_code': stock_code,
        'period': {'start': start_date, 'end': end_date},
        'validations': validations,
        'confidence_matrix': confidence
    }


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    result = run_full_validation('NCKL', analysis_days=30)
