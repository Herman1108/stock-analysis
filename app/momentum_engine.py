"""
MOMENTUM/IMPULSE ENGINE - Deteksi Breakout Agresif
Modul terpisah untuk mendeteksi momentum/impulse breakout
"""

import pandas as pd
import numpy as np


def detect_impulse_signal(price_df: pd.DataFrame, broker_df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    MOMENTUM ENGINE - Deteksi breakout agresif TANPA fase akumulasi.

    Berbeda dengan Accumulation Engine yang mencari "hidden accumulation",
    Impulse Engine mendeteksi pergerakan agresif yang langsung breakout.

    Kondisi Impulse/Momentum:
    1. Volume hari ini > 2x rata-rata volume (5 hari)
    2. Close hari ini > High tertinggi (5 hari sebelumnya) = Breakout
    3. CPR hari ini > 55% (close lebih dekat ke high)

    Karakteristik:
    - Fast, aggressive, volume spike, CPR high
    - Tidak butuh fase sideways/akumulasi sebelumnya
    - Risiko tinggi, momentum trader dominan
    - Cocok untuk swing/momentum trading, BUKAN value investing

    Returns:
        dict dengan impulse_detected, type, strength, metrics, educational_message
    """
    if price_df.empty or len(price_df) < lookback + 1:
        return {
            'impulse_detected': False,
            'reason': 'Data tidak cukup',
            'engine_type': 'MOMENTUM'
        }

    price_df = price_df.sort_values('date').copy()

    # Data hari ini
    today = price_df.iloc[-1]
    today_date = today['date']
    today_close = today['close_price']
    today_high = today['high_price']
    today_low = today['low_price']
    today_volume = today['volume']

    # Data lookback (exclude hari ini)
    recent = price_df.iloc[-(lookback+1):-1]

    # === METRICS CALCULATION ===

    # 1. Volume Spike: Volume hari ini vs rata-rata
    avg_volume = recent['volume'].mean()
    volume_ratio = (today_volume / avg_volume) if avg_volume > 0 else 1
    volume_spike_pct = (volume_ratio - 1) * 100
    is_volume_spike = volume_ratio >= 2.0  # 2x atau lebih

    # 2. Price Breakout: Close hari ini vs High tertinggi lookback
    recent_high = recent['high_price'].max()
    is_breakout = today_close > recent_high
    breakout_pct = ((today_close - recent_high) / recent_high * 100) if recent_high > 0 else 0

    # 3. CPR hari ini: posisi close dalam range hari ini
    today_range = today_high - today_low
    if today_range > 0:
        today_cpr = (today_close - today_low) / today_range
    else:
        today_cpr = 0.5
    is_cpr_bullish = today_cpr > 0.55

    # 4. Price momentum (perubahan dari kemarin)
    yesterday_close = price_df.iloc[-2]['close_price'] if len(price_df) >= 2 else today_close
    daily_change_pct = ((today_close - yesterday_close) / yesterday_close * 100) if yesterday_close > 0 else 0

    # 5. Broker flow hari ini (optional, untuk konfirmasi)
    net_flow = 0
    num_buyers = 0
    num_sellers = 0
    if not broker_df.empty:
        today_broker = broker_df[broker_df['date'] == today_date]
        if not today_broker.empty:
            net_flow = today_broker['net_lot'].sum()
            num_buyers = len(today_broker[today_broker['net_lot'] > 0])
            num_sellers = len(today_broker[today_broker['net_lot'] < 0])

    # === IMPULSE DETECTION LOGIC ===

    # Core impulse: Volume spike + Breakout + Bullish CPR
    impulse_detected = is_volume_spike and is_breakout and is_cpr_bullish

    # Determine strength
    if impulse_detected:
        if volume_ratio >= 3.0 and breakout_pct >= 3.0 and today_cpr >= 0.70:
            strength = 'STRONG'
            signal_type = 'IMPULSE_BREAKOUT'
        elif volume_ratio >= 2.5 or (breakout_pct >= 2.0 and today_cpr >= 0.60):
            strength = 'MODERATE'
            signal_type = 'MOMENTUM_SURGE'
        else:
            strength = 'WEAK'
            signal_type = 'MOMENTUM_EARLY'
    else:
        strength = None
        signal_type = None

    # Check for "near impulse" (almost triggered)
    near_impulse = (
        (is_volume_spike and is_breakout and not is_cpr_bullish) or
        (is_volume_spike and is_cpr_bullish and not is_breakout) or
        (is_breakout and is_cpr_bullish and volume_ratio >= 1.5)  # Close to 2x
    )

    # === EDUCATIONAL MESSAGE ===
    if impulse_detected:
        if strength == 'STRONG':
            educational = (
                "IMPULSE KUAT TERDETEKSI! Harga breakout dengan volume >3x rata-rata. "
                "Pergerakan agresif tanpa fase akumulasi panjang. "
                "Risiko tinggi - momentum trader dominan. "
                "Jika masuk, gunakan stop loss ketat dan jangan averaging down."
            )
        elif strength == 'MODERATE':
            educational = (
                "MOMENTUM SURGE terdeteksi. Volume spike dengan breakout harga. "
                "Pergerakan cepat yang didorong momentum buyer. "
                "Pertimbangkan entry dengan posisi kecil dan stop loss di bawah breakout level."
            )
        else:
            educational = (
                "Momentum awal terdeteksi. Volume dan harga mulai bergerak. "
                "Butuh konfirmasi lanjutan untuk validasi. "
                "Pantau apakah volume spike berlanjut atau hanya spike sesaat."
            )
    elif near_impulse:
        educational = (
            "Hampir memenuhi kriteria impulse/momentum. "
            "Salah satu kondisi belum terpenuhi. Pantau perkembangan besok."
        )
    else:
        educational = (
            "Tidak ada impulse/momentum terdeteksi. "
            "Harga dalam kondisi normal tanpa breakout signifikan."
        )

    # === DECISION SUPPORT ===
    if impulse_detected:
        if strength == 'STRONG':
            decision = 'MASUK_MOMENTUM'
            decision_reason = f"Breakout kuat +{breakout_pct:.1f}% dengan volume {volume_ratio:.1f}x. Entry momentum dengan strict stop loss."
        elif strength == 'MODERATE':
            decision = 'PANTAU_BREAKOUT'
            decision_reason = "Momentum building. Konfirmasi diperlukan sebelum entry penuh."
        else:
            decision = 'TUNGGU'
            decision_reason = "Sinyal masih lemah. Tunggu konfirmasi volume dan harga."
    elif near_impulse:
        decision = 'SIAGA'
        decision_reason = "Hampir impulse. Siapkan watchlist untuk entry jika terkonfirmasi."
    else:
        decision = 'TIDAK_ADA_SINYAL'
        decision_reason = "Tidak ada momentum. Cari peluang di saham lain atau tunggu akumulasi."

    return {
        'impulse_detected': impulse_detected,
        'near_impulse': near_impulse,
        'engine_type': 'MOMENTUM',
        'signal_type': signal_type,
        'strength': strength,
        'metrics': {
            'volume_ratio': round(volume_ratio, 2),
            'volume_spike_pct': round(volume_spike_pct, 1),
            'is_volume_spike': is_volume_spike,
            'recent_high': recent_high,
            'breakout_pct': round(breakout_pct, 2),
            'is_breakout': is_breakout,
            'today_cpr': round(today_cpr, 3),
            'today_cpr_pct': round(today_cpr * 100, 1),
            'is_cpr_bullish': is_cpr_bullish,
            'daily_change_pct': round(daily_change_pct, 2),
            'net_flow': net_flow,
            'num_buyers': num_buyers,
            'num_sellers': num_sellers
        },
        'trigger_conditions': {
            'volume_2x': is_volume_spike,
            'price_breakout': is_breakout,
            'cpr_bullish': is_cpr_bullish,
            'conditions_met': sum([is_volume_spike, is_breakout, is_cpr_bullish]),
            'total_conditions': 3
        },
        'decision': {
            'action': decision,
            'reason': decision_reason
        },
        'educational': educational,
        'trigger_date': str(today_date)[:10] if today_date else None,
        'trigger_price': today_close
    }
