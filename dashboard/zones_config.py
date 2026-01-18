# -*- coding: utf-8 -*-
"""
Master Configuration - Support & Resistance Zones
Formula V10 - All Stocks
"""

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
        1: {'low': 1440, 'high': 1480},
        2: {'low': 1670, 'high': 1735},
        3: {'low': 1950, 'high': 2050},
    },
    'DSNG': {
        1: {'low': 660, 'high': 685},
        2: {'low': 865, 'high': 900},
        3: {'low': 1055, 'high': 1085},
        4: {'low': 1245, 'high': 1340},
        5: {'low': 1840, 'high': 1875},
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
}

# Default parameters for all stocks
DEFAULT_PARAMS = {
    'buffer_method': 'ATR',
    'atr_len': 14,
    'atr_mult': 0.20,
    'pct_buffer': 0.005,

    'sl_pct': 0.05,
    'tp_mode': 'next_zone_2pct',
    'tp_buffer_pct': 0.02,
    'max_hold_bars': 60,

    'entry_execution': 'next_open',

    'use_broker_filter': False,
    'allow_no_broker_data': True,

    'confirm_bars_retest': 3,
    'confirm_closes_breakout': 2,
    'retest_confirm_mode': 'ANY',
    'not_late_pct': 0.35,
}


def get_zones(stock_code):
    """Get zones for a specific stock"""
    return STOCK_ZONES.get(stock_code.upper(), {})


def print_all_zones():
    """Print all configured zones"""
    for stock, zones in STOCK_ZONES.items():
        print(f"\n{stock}:")
        for znum, z in sorted(zones.items()):
            print(f"  Z{znum}: {z['low']:,} - {z['high']:,}")


if __name__ == '__main__':
    print("=" * 60)
    print("MASTER ZONES CONFIGURATION - Formula V10")
    print("=" * 60)
    print_all_zones()
