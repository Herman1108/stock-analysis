# -*- coding: utf-8 -*-
"""
FORMULA V11b2 - SPESIFIKASI LENGKAP
===================================

Tanggal Update: 2026-01-20
Versi: V11b2

DESKRIPSI:
Formula V11b1 + MA Trend Filter.
Hanya entry saat MA30 > MA100 (uptrend).

EMITEN YANG MENGGUNAKAN V11b2:
- BBCA
- MBMA
- HRUM
- CDIA

"""

# ============================================================================
# PARAMETER V11b2
# ============================================================================

V11B2_PARAMS = {
    # Inherited from V11b1
    'vol_lookback': 20,           # Periode rata-rata volume (20 hari trading)
    'min_vol_ratio': 1.0,         # Min volume ratio untuk entry (1.0x = sama dengan avg)
    'max_wait_days': 6,           # Maksimal tunggu 6 hari (cancel di hari ke-7)
    'not_late_pct': 0.40,         # Harga harus dalam 40% dari zone_high ke TP
    'bo_accumulation_days': 7,    # Cek 7 hari sebelumnya untuk akumulasi breakout
    'gate_days': 3,               # Validasi 3 hari berturut-turut di atas resistance

    # V11b2 Specific - MA Trend Filter
    'use_ma_filter': True,        # Enable MA trend filter
    'ma_short': 30,               # MA short period (MA30)
    'ma_long': 100,               # MA long period (MA100)
}

DEFAULT_PARAMS = {
    'buffer_method': 'ATR',       # Metode buffer: 'ATR' atau 'PCT'
    'atr_len': 14,                # Periode ATR
    'atr_mult': 0.20,             # ATR multiplier (buffer = ATR * 0.20)
    'pct_buffer': 0.005,          # Jika PCT: buffer = close * 0.5%

    'sl_pct': 0.05,               # Stop Loss = zone_low * (1 - 5%)
    'tp_buffer_pct': 0.02,        # TP = next_resistance_low * (1 - 2%)
    'max_hold_bars': 90,          # Max hold 90 hari

    'confirm_bars_retest': 3,     # Max 3 bar untuk reclaim setelah touch support
    'confirm_closes_breakout': 2, # Confirm closes untuk breakout
    'not_late_pct': 0.40,         # Max jarak dari support ke TP
}

# ============================================================================
# EMITEN V11b2
# ============================================================================

V11B2_STOCKS = ['BBCA', 'MBMA', 'HRUM', 'CDIA']

# ============================================================================
# LOGIKA V11b2
# ============================================================================
"""
V11b2 = V11b1 + MA TREND FILTER
================================

SEMUA LOGIKA V11b1 BERLAKU (Breakout + Retest + Volume Confirmation)

TAMBAHAN FILTER MA:
------------------
Sebelum entry (baik BREAKOUT maupun RETEST), cek:
- MA30 > MA100 ? → ENTRY DIBOLEHKAN
- MA30 <= MA100 ? → ENTRY DIBLOKIR (downtrend)

TUJUAN:
-------
Menghindari entry saat market dalam downtrend.
Lebih konservatif dibanding V11b1.

CONTOH:
-------
BBCA Oktober 2025:
- RETEST Z1 terjadi (low=7,225)
- Checklist V11b1 semua ✅
- TAPI MA30 (7,700) < MA100 (8,400) = DOWNTREND
- Entry DIBLOKIR oleh MA filter
- Hasil: 0 trades

BBCA Januari 2026:
- MA30 (8,118) > MA100 (8,073) = UPTREND
- Entry DIBOLEHKAN
"""

# ============================================================================
# PERBANDINGAN V11b1 vs V11b2
# ============================================================================
"""
| Aspek               | V11b1              | V11b2                    |
|---------------------|--------------------|--------------------------|
| Volume Filter       | >= 1.0x avg        | >= 1.0x avg              |
| MA Trend Filter     | TIDAK              | MA30 > MA100             |
| Karakteristik       | Lebih agresif      | Lebih konservatif        |
| Trade Frequency     | Lebih banyak       | Lebih sedikit            |
| Risk                | Medium             | Lower (hanya uptrend)    |

EMITEN:
- V11b1: MDKA, ADMR, PTRO, PANI, NCKL, DSNG, BREN, BRPT, CBDK, CBRE,
         FUTR, TINS, WIFI, BMRI
- V11b2: BBCA, MBMA, HRUM, CDIA
"""

# ============================================================================
# ZONES UNTUK EMITEN V11b2
# ============================================================================

BBCA_ZONES = {
    1: {'low': 7050, 'high': 7225},
    2: {'low': 8075, 'high': 8150},
    3: {'low': 9200, 'high': 9375},
    4: {'low': 10175, 'high': 10275},
}

MBMA_ZONES = {
    1: {'low': 372, 'high': 405},
    2: {'low': 690, 'high': 715},
    3: {'low': 890, 'high': 920},
}

HRUM_ZONES = {
    1: {'low': 590, 'high': 640},
    2: {'low': 920, 'high': 960},
    3: {'low': 1535, 'high': 1610},
    4: {'low': 1855, 'high': 1930},
}

CDIA_ZONES = {
    1: {'low': 1440, 'high': 1490},
    2: {'low': 1670, 'high': 1735},
    3: {'low': 1950, 'high': 2050},
}


if __name__ == '__main__':
    print("=" * 60)
    print("FORMULA V11b2 SPECIFICATION")
    print("=" * 60)
    print("\nV11B2_PARAMS:")
    for k, v in V11B2_PARAMS.items():
        print(f"  {k}: {v}")
    print(f"\nV11B2_STOCKS: {V11B2_STOCKS}")
    print("\nZONES:")
    for stock in V11B2_STOCKS:
        zones = globals().get(f"{stock}_ZONES", {})
        print(f"\n  {stock}:")
        for znum, z in sorted(zones.items()):
            print(f"    Z{znum}: {z['low']:,} - {z['high']:,}")
