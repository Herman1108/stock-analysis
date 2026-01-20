# -*- coding: utf-8 -*-
"""
FORMULA V11b1 - SPESIFIKASI LENGKAP (REVISED)
==============================================

Tanggal Update: 2026-01-20 (Added WAIT_PULLBACK mode)
Versi: V11b1 Revised v3

DESKRIPSI:
Formula trading dengan Breakout + Retest detection,
Volume Confirmation dengan Waiting Mode dan Pullback Entry.

PERUBAHAN TERBARU:
- Klarifikasi Gate RESET: close dalam zona → reset count, mulai ulang
- Klarifikasi Gate CANCEL: close di bawah zona → breakout gagal total
- Dokumentasi skenario Gate yang lebih detail dengan contoh
- [NEW] WAIT_PULLBACK: Rekomendasi entry jika harga > 40% dari TP

"""

# ============================================================================
# PARAMETER V11b1
# ============================================================================

V11B1_PARAMS = {
    'vol_lookback': 20,           # Periode rata-rata volume (20 hari trading)
    'min_vol_ratio': 1.0,         # Min volume ratio untuk entry (1.0x = sama dengan avg)
    'max_wait_days': 6,           # Maksimal tunggu 6 hari (cancel di hari ke-7)
    'not_late_pct': 0.40,         # Harga harus dalam 40% dari zone_high ke TP
    'bo_accumulation_days': 7,    # Cek 7 hari sebelumnya untuk akumulasi breakout
    'gate_days': 3,               # Validasi 3 hari berturut-turut di atas resistance
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
    'confirm_closes_breakout': 2, # Confirm closes untuk breakout (tidak dipakai lagi)
    'not_late_pct': 0.40,         # Max jarak dari support ke TP
}

# ============================================================================
# LOGIKA BREAKOUT
# ============================================================================
"""
BREAKOUT DETECTION (dengan Akumulasi 7 Hari):
---------------------------------------------
1. Close hari ini > zone_high (breakout)
2. Dalam 7 hari sebelumnya, minimal ada 1 close <= zone_high
   (bisa dari bawah zona, dalam zona, atau sempat di atas lalu turun)

GATE VALIDATION (3 Hari):
-------------------------
Setelah breakout terdeteksi, hitung 3 hari berturut-turut close > zone_high.

4.1 Skenario Gate PASSED (Normal):
──────────────────────────────────────────────────────────────────────────────
  Zona: 2,810 - 2,970 (zone_high = 2,970)

  Hari 1: close = 3,050 (> zone_high) → count=1
  Hari 2: close = 3,020 (> zone_high) → count=2
  Hari 3: close = 3,100 (> zone_high) → count=3, GATE_PASSED!
──────────────────────────────────────────────────────────────────────────────

4.2 Skenario Gate RESET:
Jika close DALAM zona (antara zone_low dan zone_high) → RESET count ke 0
──────────────────────────────────────────────────────────────────────────────
  Zona: 2,810 - 2,970

  Hari 1: close = 3,050 → count=1
  Hari 2: close = 2,950 (DALAM zona!) → count=0, RESET!
          breakout_start_idx = hari 2 (mulai ulang)
  Hari 3: close = 3,020 → count=1 (mulai ulang)
  Hari 4: close = 3,050 → count=2
  Hari 5: close = 3,100 → count=3, GATE_PASSED!
──────────────────────────────────────────────────────────────────────────────

4.3 Skenario Gate CANCEL:
Jika close DI BAWAH zona (< zone_low) → CANCEL, harus ada breakout BARU
──────────────────────────────────────────────────────────────────────────────
  Zona: 2,810 - 2,970

  Hari 1: close = 3,050 → count=1
  Hari 2: close = 2,750 (DI BAWAH zona! < 2,810) → CANCEL!

  Breakout ini GAGAL. Harus ada breakout BARU untuk mulai lagi.
  (Harga harus naik dari bawah/dalam zona ke atas zone_high lagi)
──────────────────────────────────────────────────────────────────────────────

RINGKASAN GATE RULES:
─────────────────────
| Kondisi                      | Aksi        | Keterangan                     |
|------------------------------|-------------|--------------------------------|
| close > zone_high            | count += 1  | Lanjut hitungan                |
| zone_low <= close <= zone_high | RESET     | count=0, mulai ulang           |
| close < zone_low             | CANCEL      | Breakout gagal, tunggu sinyal baru |

ENTRY SETELAH GATE_PASSED:
--------------------------
1. Cek not_late: harga masih dalam 40% jarak ke TP
   - threshold = zone_high + (TP - zone_high) * 0.40
   - harga <= threshold → valid
2. Cek volume:
   - vol >= 1.0x → DIRECT ENTRY
   - vol < 1.0x → WAITING MODE (max 6 hari)

WAITING MODE:
-------------
- Setiap hari cek:
  - vol >= 1.0x DAN harga valid? → ENTRY
  - close < zone_low? → CANCEL (bukan reset)
  - close dalam zona? → TETAP VALID (lanjut tunggu)
  - > 6 hari? → TIMEOUT

SL/TP:
------
- SL = zone_low * 0.95 (unified untuk semua entry type)
- TP = next_resistance_low * 0.98

WAIT_PULLBACK MODE (Harga Terlalu Jauh):
----------------------------------------
Jika harga > 40% threshold (terlalu jauh dari zona untuk entry langsung),
sistem akan memberikan REKOMENDASI ENTRY di harga pullback.

5.1 Kondisi WAIT_PULLBACK:
──────────────────────────────────────────────────────────────────────────────
  - Gate sudah PASSED (3 hari di atas zona)
  - Volume >= 1.0x (atau dalam waiting mode)
  - TAPI harga > threshold 40%
  - threshold = zone_high + (TP - zone_high) * 0.40

5.2 Perhitungan Rekomendasi Entry:
──────────────────────────────────────────────────────────────────────────────
  recommended_entry = zone_high + (TP - zone_high) * 0.40
  SL = zone_low * 0.95
  TP = next_resistance_low * 0.98

  Contoh (MDKA Z3):
  - Zone: 2,810 - 2,970
  - TP: 3,780 * 0.98 = 3,704
  - Threshold/Rekom Entry = 2,970 + (3,704 - 2,970) * 0.40 = 3,264
  - SL = 2,810 * 0.95 = 2,670
  - Jika harga saat ini 3,400 (> 3,264), maka:
    Status: WAIT_PULLBACK
    Rekomendasi: Entry di 3,264 atau lebih rendah

5.3 Monitoring Harian:
──────────────────────────────────────────────────────────────────────────────
  Setiap hari cek:
  - Jika LOW <= recommended_entry → ENTRY di next_open
  - Jika close < zone_low → CANCEL (breakout gagal)
  - Jika HIGH >= TP → CANCEL (harga sudah mencapai target tanpa pullback)
  - Max 6 hari tunggu (sama dengan waiting mode volume)

5.4 Entry Trigger:
──────────────────────────────────────────────────────────────────────────────
  Kondisi entry terpenuhi jika:
  - Candle menyentuh/menembus recommended_entry (low <= recommended_entry)
  - Volume pada hari itu >= 1.0x (atau skip volume check)
  - Entry di NEXT_OPEN (hari berikutnya)

5.5 Contoh Skenario WAIT_PULLBACK:
──────────────────────────────────────────────────────────────────────────────
  Zone Z3: 2,810 - 2,970
  TP: 3,704 (Z4_low * 0.98)
  Threshold: 3,264

  Hari 1: close = 3,100, GATE_PASSED
  Hari 2: close = 3,350, > 3,264 → WAIT_PULLBACK (rekom entry: 3,264)
  Hari 3: low = 3,200 (< 3,264) → TRIGGER! Entry besok
  Hari 4: open = 3,280 → ENTRY @ 3,280
          SL: 2,670, TP: 3,704
          Status: RUNNING

RINGKASAN STATUS ENTRY:
───────────────────────
| Kondisi                         | Status          | Aksi                    |
|---------------------------------|-----------------|-------------------------|
| Gate OK, Vol OK, Harga OK       | ENTRY           | Langsung entry          |
| Gate OK, Vol LOW, Harga OK      | WAIT_VOL        | Tunggu vol >= 1.0x      |
| Gate OK, Vol OK, Harga > 40%    | WAIT_PULLBACK   | Tunggu pullback ke 40%  |
| Gate OK, Vol LOW, Harga > 40%   | WAIT_PULLBACK   | Tunggu pullback + vol   |
"""

# ============================================================================
# LOGIKA RETEST
# ============================================================================
"""
RETEST DETECTION:
-----------------
Kondisi (semua harus TRUE):
1. s_touch: LOW <= support_high (candle menyentuh zona)
2. s_hold: CLOSE >= support_low (tidak breakdown)
3. s_from_above: prev_close > support_high (datang dari atas)
4. s_not_late: close <= support_high + 40% distance ke TP
5. prior_resistance_touched: HIGH pernah touch resistance di atas
6. prior_resistance_zone > s_zone_num (resistance di ATAS support)

KONFIRMASI (dalam 3 bar):
-------------------------
- any_reclaim: close >= support_high + buffer
- Jika reclaim → cek volume → ENTRY atau WAITING
- Jika close < support_low → RESET
- Jika > 3 bar tanpa reclaim → RESET

SL/TP:
------
- SL = zone_low * 0.95
- TP = next_resistance_low * 0.98
"""

# ============================================================================
# MDKA ZONES CONFIGURATION
# ============================================================================

MDKA_ZONES = {
    1: {'low': 1160, 'high': 1290},   # Support/Resistance Zone 1
    2: {'low': 2160, 'high': 2240},   # Support/Resistance Zone 2
    3: {'low': 2810, 'high': 2970},   # Support/Resistance Zone 3
    4: {'low': 3780, 'high': 3940},   # Support/Resistance Zone 4
    5: {'low': 4680, 'high': 4840},   # Support/Resistance Zone 5
    6: {'low': 5450, 'high': 5600},   # Support/Resistance Zone 6
}

# ============================================================================
# CONTOH PERHITUNGAN MDKA
# ============================================================================
"""
MDKA Current Position (2026-01-19):
-----------------------------------
- Harga: 3,060
- Entry: BREAKOUT Z3 @ 3,090 (2026-01-15)
- SL: 2,810 * 0.95 = 2,670
- TP: 3,780 * 0.98 = 3,704
- Risk: (3,090 - 2,670) / 3,090 = 13.6%
- Reward: (3,704 - 3,090) / 3,090 = 19.9%
- R:R = 1 : 1.46
"""

# ============================================================================
# RINGKASAN PERUBAHAN V11b1 REVISED
# ============================================================================
"""
| Parameter              | Sebelum | Sesudah |
|------------------------|---------|---------|
| not_late_pct           | 0.35    | 0.40    |
| max_wait_days          | 5       | 6       |
| max_hold_bars          | 60      | 90      |
| bo_accumulation_days   | 1       | 7       |
| Entry Type             | BO_HOLD/BO_PULLBACK | BREAKOUT (unified) |
| SL Calculation         | Varies  | zone_low * 0.95 (unified) |

GATE VALIDATION RULES (Updated):
--------------------------------
| Kondisi Close          | Sebelum        | Sesudah                    |
|------------------------|----------------|----------------------------|
| > zone_high            | count += 1     | count += 1 (sama)          |
| Dalam zona (low-high)  | Cancel         | RESET (count=0, mulai ulang)|
| < zone_low             | Cancel         | CANCEL (breakout gagal)    |

WAITING MODE RULES:
-------------------
| Kondisi Close          | Aksi                                       |
|------------------------|-------------------------------------------|
| Dalam zona             | VALID - lanjut tunggu volume >= 1.0x     |
| < zone_low             | CANCEL - breakout gagal                   |
| > 6 hari               | TIMEOUT - cancel waiting                  |

WAIT_PULLBACK RULES:
--------------------
| Kondisi                | Aksi                                       |
|------------------------|-------------------------------------------|
| low <= rekom_entry     | ENTRY - trigger di next_open              |
| close < zone_low       | CANCEL - breakout gagal                   |
| high >= TP             | CANCEL - harga sudah capai target         |
| > 6 hari               | TIMEOUT - cancel waiting                  |
"""

if __name__ == '__main__':
    print("=" * 60)
    print("FORMULA V11b1 SPECIFICATION")
    print("=" * 60)
    print("\nV11B1_PARAMS:")
    for k, v in V11B1_PARAMS.items():
        print(f"  {k}: {v}")
    print("\nDEFAULT_PARAMS:")
    for k, v in DEFAULT_PARAMS.items():
        print(f"  {k}: {v}")
    print("\nMDKA_ZONES:")
    for znum, zone in MDKA_ZONES.items():
        print(f"  Z{znum}: {zone['low']:,} - {zone['high']:,}")
