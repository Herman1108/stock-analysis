"""
Comprehensive V11b1 check for all stocks
"""
import sys
sys.path.insert(0, r'C:\Users\chuwi\stock-analysis\app')
sys.path.insert(0, r'C:\Users\chuwi\stock-analysis\dashboard')

from database import execute_query
from zones_config import STOCK_ZONES, get_zones

print('=' * 80)
print('COMPREHENSIVE V11B1 CHECK - ALL STOCKS')
print('=' * 80)

stocks = sorted(STOCK_ZONES.keys())
issues = []

for stock in stocks:
    print(f'\n--- {stock} ---')

    # Get precomputed data
    try:
        result = execute_query(f'''
            SELECT calc_date, status, action, confirm_type, current_price,
                   support_zone_low, support_zone_high, support_zone_num,
                   has_open_position, vol_ratio, trade_history
            FROM v11b1_results_{stock.lower()}
            ORDER BY calc_date DESC
            LIMIT 1
        ''')
    except Exception as e:
        print(f'  ERROR: Could not query table - {e}')
        issues.append(f'{stock}: Table query error')
        continue

    if not result:
        print(f'  WARNING: No data in table')
        issues.append(f'{stock}: No data')
        continue

    r = dict(result[0])
    price = float(r.get('current_price') or 0)
    s_low = float(r.get('support_zone_low') or 0)
    s_high = float(r.get('support_zone_high') or 0)
    s_num = r.get('support_zone_num')
    has_pos = r.get('has_open_position')
    vol_ratio = float(r.get('vol_ratio') or 0)
    confirm_type = r.get('confirm_type', '')
    status = r.get('status', '')
    action = r.get('action', '')

    print(f'  Price: {price:,.0f}')
    print(f'  Support Zone: Z{s_num} ({s_low:,.0f}-{s_high:,.0f})')
    print(f'  Status: {status} | Action: {action} | Confirm: {confirm_type}')

    # Calculate expected zone status
    if s_high > 0:
        if price > s_high:
            expected_zone = 'ABOVE'
        elif price >= s_low:
            expected_zone = 'IN_ZONE'
        else:
            expected_zone = 'BELOW'
        print(f'  Zone Status: {expected_zone} (price vs zone)')
    else:
        expected_zone = 'N/A'
        print(f'  Zone Status: N/A (no support zone)')

    # Check open position
    if has_pos:
        print(f'  ** HAS OPEN POSITION **')
        trade_history = r.get('trade_history', [])
        open_trade = None
        for t in (trade_history or []):
            if t.get('exit_reason') == 'OPEN':
                open_trade = t
                break

        if open_trade:
            trade_type = open_trade.get('type', 'UNKNOWN')
            entry_cond = open_trade.get('entry_conditions', {})
            trade_vol = open_trade.get('vol_ratio', 0)
            print(f'     Type: {trade_type}')
            print(f'     Entry Conditions: {entry_cond}')
            print(f'     Entry Vol Ratio: {trade_vol:.2f}x')

            # Validate
            if not entry_cond:
                issues.append(f'{stock}: Missing entry_conditions in trade')
            if trade_vol == 0:
                issues.append(f'{stock}: Missing vol_ratio in trade')
            if trade_type not in ['BREAKOUT', 'RETEST']:
                issues.append(f'{stock}: Unknown trade type {trade_type}')
        else:
            print(f'     WARNING: has_open_position=True but no OPEN trade found!')
            issues.append(f'{stock}: has_open_position=True but no OPEN trade in history')

    # Check for status consistency
    if has_pos and status != 'RUNNING':
        issues.append(f'{stock}: has_open_position=True but status={status} (should be RUNNING)')
    if (not has_pos) and status == 'RUNNING':
        issues.append(f'{stock}: has_open_position=False but status=RUNNING')

print('\n')
print('=' * 80)
print('SUMMARY')
print('=' * 80)
print(f'Total stocks checked: {len(stocks)}')
print(f'Issues found: {len(issues)}')

if issues:
    print('\nISSUES:')
    for i, issue in enumerate(issues, 1):
        print(f'  {i}. {issue}')
else:
    print('\nAll stocks passed validation!')
