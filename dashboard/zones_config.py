# -*- coding: utf-8 -*-
"""
Master Configuration - Support & Resistance Zones
Formula Assignment per Stock

Updated: 2026-01-22 (Added RATU)
"""

# ============================================================================
# FORMULA ASSIGNMENT PER STOCK
# ============================================================================
# V11b1: Volume >= 1.0x (tunggu max 6 hari) - Lihat formula_v11b1_spec.py
# V11b2: V11b1 + MA30 > MA100 trend filter  - Lihat formula_v11b2_spec.py

STOCK_FORMULA = {
    # V11b1 Stocks (19 emiten) - Volume >= 1.0x
    'ADMR': 'V11b1',
    'BMRI': 'V11b1',
    'BREN': 'V11b1',
    'BRPT': 'V11b1',
    'CBDK': 'V11b1',
    'CBRE': 'V11b1',   # Note: 0% win rate - HINDARI
    'CDIA': 'V11b1',
    'CUAN': 'V11b1',
    'DSNG': 'V11b1',
    'FUTR': 'V11b1',
    'HRUM': 'V11b1',
    'MBMA': 'V11b1',
    'MDKA': 'V11b1',   # Reference stock untuk V11b1
    'NCKL': 'V11b1',
    'PANI': 'V11b1',
    'PTRO': 'V11b1',
    'RATU': 'V11b1',
    'TINS': 'V11b1',
    'WIFI': 'V11b1',   # Note: Low win rate - HINDARI

    # V11b2 Stocks (1 emiten) - V11b1 + MA30 > MA100 filter
    'BBCA': 'V11b2',   # Reference stock untuk V11b2
}

STOCK_ZONES = {
    'CBDK': {
        1: {'low': 5350, 'high': 5575},
        2: {'low': 7100, 'high': 7250},
        3: {'low': 9225, 'high': 9400},
    },
    'PANI': {
        1: {'low': 7050, 'high': 7425},
        2: {'low': 9850, 'high': 10625},
        3: {'low': 12550, 'high': 13050},
        4: {'low': 16025, 'high': 16575},
    },
    'MBMA': {
        1: {'low': 372, 'high': 405},
        2: {'low': 690, 'high': 715},
        3: {'low': 890, 'high': 920},
    },
    'PTRO': {
        1: {'low': 6825, 'high': 7125},
        2: {'low': 8525, 'high': 8750},
        3: {'low': 10150, 'high': 10525},
        4: {'low': 11825, 'high': 12200},
        5: {'low': 13650, 'high': 14050},
    },
    'RATU': {
        1: {'low': 6325, 'high': 6575},
        2: {'low': 7875, 'high': 8075},
        3: {'low': 9800, 'high': 10025},
        4: {'low': 11675, 'high': 11975},
    },
    'BREN': {
        1: {'low': 3400, 'high': 4200},
        2: {'low': 7200, 'high': 8000},
        3: {'low': 11225, 'high': 11800},
    },
    'BRPT': {
        1: {'low': 1525, 'high': 1725},
        2: {'low': 2460, 'high': 2670},
        3: {'low': 3880, 'high': 4130},
    },
    'CBRE': {
        1: {'low': 940, 'high': 1015},
        2: {'low': 1625, 'high': 1710},
    },
    'CDIA': {
        1: {'low': 1440, 'high': 1490},
        2: {'low': 1670, 'high': 1735},
        3: {'low': 1950, 'high': 2050},
    },
    'DSNG': {
        1: {'low': 660, 'high': 685},
        2: {'low': 865, 'high': 900},
        3: {'low': 1055, 'high': 1085},
        4: {'low': 1300, 'high': 1340},
        5: {'low': 1515, 'high': 1565},
        6: {'low': 1840, 'high': 1875},
    },
    'FUTR': {
        1: {'low': 370, 'high': 398},
        2: {'low': 605, 'high': 635},
        3: {'low': 815, 'high': 840},
    },
    'HRUM': {
        1: {'low': 590, 'high': 640},
        2: {'low': 920, 'high': 960},
        3: {'low': 1535, 'high': 1610},
        4: {'low': 1855, 'high': 1930},
    },
    'TINS': {
        1: {'low': 1485, 'high': 1585},
        2: {'low': 2170, 'high': 2380},
        3: {'low': 2940, 'high': 3040},
        4: {'low': 3490, 'high': 3610},
    },
    'WIFI': {
        1: {'low': 1140, 'high': 1245},
        2: {'low': 2360, 'high': 2510},
    },
    'NCKL': {
        1: {'low': 595, 'high': 615},
        2: {'low': 775, 'high': 800},
        3: {'low': 930, 'high': 955},
        4: {'low': 1080, 'high': 1125},
        5: {'low': 1395, 'high': 1435},
        6: {'low': 1680, 'high': 1710},
    },
    'BBCA': {
        1: {'low': 7050, 'high': 7225},
        2: {'low': 8075, 'high': 8150},
        3: {'low': 9200, 'high': 9375},
        4: {'low': 10175, 'high': 10275},
    },
    'BMRI': {
        1: {'low': 3130, 'high': 3300},
        2: {'low': 4070, 'high': 4260},
        3: {'low': 5550, 'high': 5675},
        4: {'low': 7225, 'high': 7400},
    },
    'ADMR': {
        1: {'low': 1005, 'high': 1065},
        2: {'low': 1195, 'high': 1260},
        3: {'low': 1435, 'high': 1525},
        4: {'low': 1830, 'high': 1930},
        5: {'low': 2300, 'high': 2360},
    },
    'MDKA': {
        1: {'low': 1160, 'high': 1290},
        2: {'low': 2160, 'high': 2240},
        3: {'low': 2810, 'high': 2970},
        4: {'low': 3780, 'high': 3940},
        5: {'low': 4680, 'high': 4840},
        6: {'low': 5450, 'high': 5600},
    },
    'CUAN': {
        1: {'low': 484, 'high': 545},
        2: {'low': 910, 'high': 980},
        3: {'low': 1370, 'high': 1450},
        4: {'low': 1920, 'high': 2010},
        5: {'low': 2560, 'high': 2680},
    },
}

# Default parameters for all stocks (REVISED V11b1)
DEFAULT_PARAMS = {
    'buffer_method': 'ATR',
    'atr_len': 14,
    'atr_mult': 0.20,
    'pct_buffer': 0.005,

    'sl_pct': 0.05,
    'tp_mode': 'next_zone_2pct',
    'tp_buffer_pct': 0.02,
    'max_hold_bars': 90,  # Updated: 60 → 90 hari

    'entry_execution': 'next_open',

    'use_broker_filter': False,
    'allow_no_broker_data': True,

    'confirm_bars_retest': 3,
    'confirm_closes_breakout': 2,
    'retest_confirm_mode': 'ANY',
    'not_late_pct': 0.40,  # Updated: 0.35 → 0.40
}


def get_zones(stock_code):
    """Get zones for a specific stock"""
    return STOCK_ZONES.get(stock_code.upper(), {})


def get_formula(stock_code):
    """Get assigned formula for a specific stock"""
    return STOCK_FORMULA.get(stock_code.upper(), 'V11b1')


def print_all_zones():
    """Print all configured zones"""
    for stock, zones in STOCK_ZONES.items():
        print(f"\n{stock}:")
        for znum, z in sorted(zones.items()):
            print(f"  Z{znum}: {z['low']:,} - {z['high']:,}")


def print_formula_assignments():
    """Print formula assignments per stock"""
    print("\nFORMULA ASSIGNMENTS:")
    print("-" * 40)
    v11b1_stocks = [s for s, f in STOCK_FORMULA.items() if f == 'V11b1']
    v11b2_stocks = [s for s, f in STOCK_FORMULA.items() if f == 'V11b2']
    print(f"V11b1 ({len(v11b1_stocks)} stocks): {', '.join(sorted(v11b1_stocks))}")
    print(f"V11b2 ({len(v11b2_stocks)} stocks): {', '.join(sorted(v11b2_stocks))}")


if __name__ == '__main__':
    print("=" * 60)
    print("MASTER CONFIGURATION - Formula V11b1/V11b2")
    print("=" * 60)
    print_formula_assignments()
    print_all_zones()
