# -*- coding: utf-8 -*-
"""
KONFIGURASI FORMULA TRADING PER EMITEN
Berdasarkan hasil backtest Strong S/R + Phase Filter + VR

PANI: 6 trades, 83.3% WR, +32.73% PnL - SANGAT COCOK
BREN: 5 trades, 60% WR, +13.01% PnL - COCOK
MBMA: 2 trades, 50% WR, +6.02% PnL - COCOK
"""

STOCK_FORMULAS = {
    'PANI': {
        'name': 'PT Pantai Indah Kapuk Dua Tbk',
        'sector': 'Property',
        'status': 'SANGAT_COCOK',

        # Parameter Entry
        'entry': {
            'timing': 'OPEN_H+1',  # Entry di OPEN hari setelah sinyal
            'valid_phases': ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION'],
            'min_score': 30,
            'max_distance_from_support': 5.0,  # Max 5% dari support
        },

        # Parameter Stop Loss & Take Profit
        'exit': {
            'stop_loss_pct': 5.0,      # SL = Support - 5%
            'take_profit_pct': 2.0,    # TP = Resistance - 2%
            'use_trailing_stop': False,
            'exit_on_distribution': True,  # Exit jika VR <= 0.8
        },

        # Parameter S/R Detection
        'sr_detection': {
            'pivot_left_bars': 5,
            'pivot_right_bars': 5,
            'tolerance_pct': 2.0,      # Toleransi clustering S/R
            'min_touches': 2,          # Min touches untuk strong level
        },

        # Parameter VR Calculation
        'vr_calculation': {
            'lookback': 30,            # 30 hari lookback
            'tolerance_pct': 3.0,      # Zone ±3% dari level
        },

        # Phase Thresholds
        'phase_thresholds': {
            'strong_accumulation': 4.0,   # VR >= 4.0
            'accumulation': 2.0,          # VR >= 2.0
            'weak_accumulation': 1.5,     # VR >= 1.5
            'distribution': 0.8,          # VR <= 0.8
            'strong_distribution': 0.5,   # VR <= 0.5
        },

        # Backtest Results
        'backtest': {
            'total_trades': 6,
            'wins': 5,
            'losses': 1,
            'win_rate': 83.3,
            'total_pnl': 32.73,
            'best_phase': 'STRONG_ACCUMULATION',
        }
    },

    'BREN': {
        'name': 'PT Barito Renewables Energy Tbk',
        'sector': 'Energy',
        'status': 'COCOK',

        # Parameter Entry
        'entry': {
            'timing': 'OPEN_H+1',
            'valid_phases': ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION'],
            'min_score': 30,
            'max_distance_from_support': 5.0,
        },

        # Parameter Stop Loss & Take Profit
        'exit': {
            'stop_loss_pct': 5.0,
            'take_profit_pct': 2.0,
            'use_trailing_stop': False,
            'exit_on_distribution': True,
        },

        # Parameter S/R Detection
        'sr_detection': {
            'pivot_left_bars': 5,
            'pivot_right_bars': 5,
            'tolerance_pct': 2.0,
            'min_touches': 2,
        },

        # Parameter VR Calculation
        'vr_calculation': {
            'lookback': 30,
            'tolerance_pct': 3.0,
        },

        # Phase Thresholds
        'phase_thresholds': {
            'strong_accumulation': 4.0,
            'accumulation': 2.0,
            'weak_accumulation': 1.5,
            'distribution': 0.8,
            'strong_distribution': 0.5,
        },

        # Backtest Results
        'backtest': {
            'total_trades': 5,
            'wins': 3,
            'losses': 2,
            'win_rate': 60.0,
            'total_pnl': 13.01,
            'best_phase': 'STRONG_ACCUMULATION',
        }
    },

    'MBMA': {
        'name': 'PT Merdeka Battery Materials Tbk',
        'sector': 'Mining/Battery',
        'status': 'COCOK',

        # Parameter Entry
        'entry': {
            'timing': 'OPEN_H+1',
            'valid_phases': ['STRONG_ACCUMULATION', 'ACCUMULATION', 'WEAK_ACCUMULATION'],
            'min_score': 30,
            'max_distance_from_support': 5.0,
        },

        # Parameter Stop Loss & Take Profit
        'exit': {
            'stop_loss_pct': 5.0,
            'take_profit_pct': 2.0,
            'use_trailing_stop': False,
            'exit_on_distribution': True,
        },

        # Parameter S/R Detection
        'sr_detection': {
            'pivot_left_bars': 5,
            'pivot_right_bars': 5,
            'tolerance_pct': 2.0,
            'min_touches': 2,
        },

        # Parameter VR Calculation
        'vr_calculation': {
            'lookback': 30,
            'tolerance_pct': 3.0,
        },

        # Phase Thresholds
        'phase_thresholds': {
            'strong_accumulation': 4.0,
            'accumulation': 2.0,
            'weak_accumulation': 1.5,
            'distribution': 0.8,
            'strong_distribution': 0.5,
        },

        # Backtest Results
        'backtest': {
            'total_trades': 2,
            'wins': 1,
            'losses': 1,
            'win_rate': 50.0,
            'total_pnl': 6.02,
            'best_phase': 'ACCUMULATION',
        }
    },
}


def get_formula(stock_code):
    """Get formula configuration for a specific stock"""
    return STOCK_FORMULAS.get(stock_code.upper())


def get_all_stocks():
    """Get list of all configured stocks"""
    return list(STOCK_FORMULAS.keys())


def print_formula(stock_code):
    """Print formula details for a stock"""
    formula = get_formula(stock_code)
    if not formula:
        print(f"Formula untuk {stock_code} tidak ditemukan")
        return

    print(f"\n{'='*60}")
    print(f"FORMULA TRADING: {stock_code}")
    print(f"{'='*60}")
    print(f"Nama    : {formula['name']}")
    print(f"Sektor  : {formula['sector']}")
    print(f"Status  : {formula['status']}")

    print(f"\n--- PARAMETER ENTRY ---")
    e = formula['entry']
    print(f"  Timing      : {e['timing']}")
    print(f"  Valid Phase : {', '.join(e['valid_phases'])}")
    print(f"  Min Score   : {e['min_score']}")
    print(f"  Max Dist    : {e['max_distance_from_support']}% dari support")

    print(f"\n--- PARAMETER EXIT ---")
    x = formula['exit']
    print(f"  Stop Loss   : Support - {x['stop_loss_pct']}%")
    print(f"  Take Profit : Resistance - {x['take_profit_pct']}%")
    print(f"  Trailing    : {'Ya' if x['use_trailing_stop'] else 'Tidak'}")
    print(f"  Exit Dist.  : {'Ya' if x['exit_on_distribution'] else 'Tidak'}")

    print(f"\n--- PHASE THRESHOLDS ---")
    p = formula['phase_thresholds']
    print(f"  STRONG_ACCUMULATION : VR >= {p['strong_accumulation']}")
    print(f"  ACCUMULATION        : VR >= {p['accumulation']}")
    print(f"  WEAK_ACCUMULATION   : VR >= {p['weak_accumulation']}")
    print(f"  DISTRIBUTION        : VR <= {p['distribution']}")

    print(f"\n--- BACKTEST RESULTS ---")
    b = formula['backtest']
    print(f"  Total Trades : {b['total_trades']}")
    print(f"  Win Rate     : {b['win_rate']}%")
    print(f"  Total PnL    : +{b['total_pnl']}%")
    print(f"  Best Phase   : {b['best_phase']}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("        KONFIGURASI FORMULA TRADING - 3 EMITEN")
    print("="*60)

    for stock in get_all_stocks():
        print_formula(stock)
