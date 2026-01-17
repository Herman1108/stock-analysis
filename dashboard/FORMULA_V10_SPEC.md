# FORMULA V10 - Trading Strategy Specification
**Last Updated: January 2026**

---

## OVERVIEW

Formula V10 adalah strategi trading berbasis Support & Resistance Zone dengan 2 tipe entry:
1. **RETEST** - Entry saat harga retest zona support yang sudah menjadi resistance
2. **BREAKOUT** - Entry saat harga breakout zona resistance

---

## ZONE CONFIGURATION

### Structure
```python
ZONES = {
    zone_number: {'low': price_low, 'high': price_high}
}
```

### Configured Stocks (14 stocks)
| Stock | Z1 | Z2 | Z3 | Z4 | Z5 |
|-------|----|----|----|----|-----|
| CBDK | 5,350-5,575 | 7,100-7,250 | 9,225-9,400 | - | - |
| PANI | 7,050-7,425 | 9,850-10,325 | 12,550-13,050 | 16,025-16,575 | - |
| MBMA | 372-405 | 690-715 | 890-920 | - | - |
| PTRO | 6,825-7,125 | 8,525-8,750 | 10,150-10,525 | - | - |
| BREN | 3,400-4,200 | 7,200-8,000 | 11,225-11,800 | - | - |
| BRPT | 1,525-1,725 | 2,460-2,670 | 3,880-4,130 | - | - |
| CBRE | 940-1,015 | 1,625-1,710 | - | - | - |
| CDIA | 1,440-1,480 | 1,670-1,735 | 1,950-2,050 | - | - |
| DSNG | 660-685 | 865-900 | 1,245-1,340 | 1,840-1,875 | - |
| FUTR | 370-398 | 605-635 | 815-840 | - | - |
| HRUM | 590-640 | 920-960 | 1,535-1,610 | 1,855-1,930 | - |
| TINS | 1,485-1,585 | 2,170-2,380 | - | - | - |
| WIFI | 1,140-1,245 | 2,360-2,510 | - | - | - |
| NCKL | 595-615 | 775-800 | 930-955 | 1,080-1,125 | 1,395-1,435 |

---

## DEFAULT PARAMETERS

```python
DEFAULT_PARAMS = {
    # Buffer Configuration
    'buffer_method': 'ATR',      # 'ATR' or 'PCT'
    'atr_len': 14,               # ATR period
    'atr_mult': 0.20,            # ATR multiplier for buffer
    'pct_buffer': 0.005,         # Percentage buffer (if PCT method)

    # Risk Management
    'sl_pct': 0.05,              # Stop Loss: 5% below zone
    'tp_mode': 'next_zone_2pct', # Take Profit mode
    'tp_buffer_pct': 0.02,       # TP buffer: 2% below next zone
    'max_hold_bars': 60,         # Maximum holding period

    # Entry Execution
    'entry_execution': 'next_open',  # Execute at next day open

    # Broker Filter (disabled)
    'use_broker_filter': False,
    'allow_no_broker_data': True,

    # Confirmation Settings
    'confirm_bars_retest': 3,       # Max bars for retest confirmation
    'confirm_closes_breakout': 2,   # Required closes for breakout
    'retest_confirm_mode': 'ANY',   # Confirmation mode
    'not_late_pct': 0.35,           # Maximum allowed entry distance
}
```

---

## STATE MACHINE

```
STATE_IDLE (0)           - No active signal tracking
STATE_RETEST_PENDING (1) - Waiting for retest confirmation
STATE_BREAKOUT_GATE (2)  - Breakout detected, waiting for gate validation
STATE_BREAKOUT_ARMED (3) - Gate passed, waiting for entry confirmation
```

---

## ENTRY TYPE 1: RETEST

### Prerequisites
1. **PRIOR_RESISTANCE_TOUCHED** - Price must have touched resistance zone before retest

### Entry Conditions (ALL must be TRUE)
1. **SUPPORT_TOUCH**: `low <= S_high`
   - Low of candle touches zone high

2. **SUPPORT_HOLD**: `close >= S_low`
   - Close stays above zone low

3. **FROM_ABOVE**: `prev_close > S_high`
   - Previous close was above zone (coming from above)

4. **NOT_LATE**: `close <= S_high + 0.35 × (TP - S_high)`
   - Close is not too far above the zone
   - Maximum allowed: 35% of distance from zone to TP

5. **PRIOR_R_TOUCH**: `prior_resistance_touched == True`
   - Must have previously touched resistance zone

### Confirmation
- Within `confirm_bars_retest` (3 bars):
  - **RECLAIM**: `close >= S_high + buffer`
  - If close drops below `S_low`, signal cancelled

### Stop Loss & Take Profit
- **SL**: `zone_low × (1 - 0.05)` = 5% below zone low
- **TP**: `next_zone_low × (1 - 0.02)` = 2% below next resistance zone

---

## ENTRY TYPE 2: BREAKOUT

### Breakout Detection
```
prev_close <= zone_LOW AND close > zone_HIGH
```
- Previous close at or below zone low
- Current close above zone high
- This is a "clean breakout" from below the zone to above it

### Gate Validation (3-Day Rule)
After breakout detected:
1. **Day 0**: Breakout day, count = 1
2. **Day 1+**: If `close >= zone_high`, count++
3. **GATE_PASSED** when count reaches 3

Gate can fail or reset:
- **GATE_FAIL**: `close < zone_low` → Back to IDLE
- **GATE_RESET**: `zone_low <= close < zone_high` → Reset count, restart

### Post-Gate Entry

#### Path A: BO_HOLD (No Pullback)
1. After gate passed, track `confirm_closes` above zone
2. If `close > zone_high` for `confirm_closes_breakout` (2) consecutive days
3. Entry triggered: **BO_HOLD**

#### Path B: BO_PULLBACK (With Pullback)
1. After gate passed, if `close` falls inside zone (`zone_low - buffer` to `zone_high + buffer`)
2. **PULLBACK** detected, reset confirm count
3. If `close > zone_high` again: **PULLBACK_REBREAK**, count = 1
4. If next `close > zone_high`: count = 2, entry triggered: **BO_PULLBACK**

### Stop Loss & Take Profit
- **BO_HOLD SL**: `zone_high × (1 - 0.05)` = 5% below zone high
- **BO_PULLBACK SL**: `zone_low × (1 - 0.05)` = 5% below zone low
- **TP**: `next_zone_low × (1 - 0.02)` = 2% below next resistance zone

---

## HELPER FUNCTIONS

### Buffer Calculation
```python
if buffer_method == 'ATR':
    buffer = ATR(14) × 0.20
else:
    buffer = close × 0.005
```

### Active Support
```python
def get_active_support(close):
    # 1. If close is INSIDE a zone, that zone is support
    # 2. Otherwise, find nearest zone BELOW close
```

### Active Resistance
```python
def get_active_resistance(close):
    # 1. If close is INSIDE a zone, that zone is resistance
    # 2. Otherwise, find nearest zone ABOVE close
```

### Detect Breakout Zone
```python
def detect_breakout_zone(prev_close, close):
    for zone in zones:
        if prev_close <= zone_low AND close > zone_high:
            return zone
```

---

## EXIT CONDITIONS

| Condition | Exit Price | Result |
|-----------|------------|--------|
| `low <= SL` | SL price | Loss |
| `high >= TP` | TP price | Win |
| `bars >= max_hold_bars` | Close price | Variable |

---

## FLOWCHART

```
                    ┌─────────────┐
                    │   IDLE      │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
     │  Retest   │   │ Breakout  │   │   Wait    │
     │  Signal   │   │  Signal   │   │           │
     └─────┬─────┘   └─────┬─────┘   └───────────┘
           │               │
           │         ┌─────▼─────┐
           │         │   GATE    │
           │         │   3-day   │
           │         └─────┬─────┘
           │               │
           │         ┌─────▼─────┐
           │         │   ARMED   │
           │         └─────┬─────┘
           │               │
           │     ┌─────────┼─────────┐
           │     │                   │
     ┌─────▼─────▼─────┐   ┌────────▼────────┐
     │    CONFIRM      │   │   PULLBACK      │
     │    (reclaim/    │   │   then rebreak  │
     │    2-closes)    │   │                 │
     └────────┬────────┘   └────────┬────────┘
              │                     │
        ┌─────▼─────────────────────▼─────┐
        │           ENTRY                  │
        │     (next_open execution)        │
        └─────────────────┬───────────────┘
                          │
        ┌─────────────────▼───────────────┐
        │        POSITION MANAGEMENT       │
        │   SL / TP / Max Hold Check       │
        └─────────────────┬───────────────┘
                          │
                    ┌─────▼─────┐
                    │   EXIT    │
                    └───────────┘
```

---

## IMPORTANT NOTES

1. **Prior Resistance Touch Initialization**
   - Must scan historical data before `start_idx` to initialize `prior_resistance_touched`
   - Without this, RETEST signals may be missed

2. **Data Requirements**
   - Minimum 15 bars needed before backtest starts (14 for ATR + 1)
   - New stocks may have insufficient data for early dates

3. **Frozen State**
   - When in `BREAKOUT_GATE` state (count < 3), RETEST signals are frozen
   - Prevents conflicting signals

4. **Zone Override**
   - A new breakout of a different zone can override current tracking
   - Helps adapt to rapid price movements

---

## BACKTEST RESULTS (as of January 2026)

| Stock | Trades | Wins | Losses | Win Rate | Total PnL |
|-------|--------|------|--------|----------|-----------|
| NCKL | 7 | 6 | 1 | 85.7% | +52.20% |
| DSNG | 4 | 4 | 0 | 100.0% | +50.58% |
| PANI | 8 | 7 | 1 | 87.5% | +47.95% |
| CDIA | 3 | 3 | 0 | 100.0% | +32.52% |
| BREN | 3 | 3 | 0 | 100.0% | +29.47% |
| CBDK | 5 | 4 | 1 | 80.0% | +26.49% |
| HRUM | 3 | 2 | 1 | 66.7% | +23.79% |
| BRPT | 2 | 1 | 1 | 50.0% | +22.36% |
| FUTR | 2 | 1 | 1 | 50.0% | +11.35% |
| TINS | 1 | 1 | 0 | 100.0% | +7.94% |
| MBMA | 0 | 0 | 0 | N/A | 0.00% |
| WIFI | 1 | 0 | 1 | 0.0% | -3.54% |
| PTRO | 0 | 0 | 0 | N/A | 0.00% |
| CBRE | 1 | 0 | 1 | 0.0% | -5.00% |
| **TOTAL** | **40** | **28** | **12** | **70.0%** | **+325.58%** |

---

## FILES

| File | Description |
|------|-------------|
| `zones_config.py` | Master zone configuration for all stocks |
| `backtest_v10_universal.py` | Universal backtest engine |
| `debug_cbdk_v10.py` | Debug script for CBDK |
| `debug_pani_v10.py` | Debug script for PANI |
| `FORMULA_V10_SPEC.md` | This specification document |

---

## VERSION HISTORY

- **V10**: Fixed prior_resistance_touched initialization, universal backtest system
- **V9-V1**: Earlier iterations (deprecated)
