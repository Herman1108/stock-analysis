"""
Dynamic Threshold Calculator for Buy/Sell Signals
Auto-updates based on historical patterns

Features:
- ACCUMULATION patterns (sideways + broker accumulation -> rally/breakout up)
- DISTRIBUTION patterns (sideways + broker distribution -> decline/breakdown down)
- Self-learning: thresholds update as new patterns are discovered
- Different breakout thresholds for big cap (5%) vs small cap (10%)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from database import execute_query

# Market Cap Categories (Standard IDX)
# Big Cap (First Liner): > 10 Triliun
# Mid Cap (Second Liner): 500 Miliar - 10 Triliun
# Small Cap (Third Liner): < 500 Miliar

MARKET_CAP_BIG = 10e12      # 10 Triliun
MARKET_CAP_MID = 500e9      # 500 Miliar

# Default thresholds for SMALL CAP (< 500 Miliar)
DEFAULT_THRESHOLD_SMALL_CAP = {
    'min_sideways_days': 5,
    'min_pct_shares': 0.01,  # 0.01%
    'signal_day_pct': 0.75,  # Signal at 75% of avg sideways duration
    'breakout_pct': 0.10,    # 10% for small cap
    'breakdown_pct': -0.10   # -10% for small cap
}

# Default thresholds for MID CAP (500 Miliar - 10 Triliun)
DEFAULT_THRESHOLD_MID_CAP = {
    'min_sideways_days': 6,
    'min_pct_shares': 0.03,  # 0.03%
    'signal_day_pct': 0.75,
    'breakout_pct': 0.075,   # 7.5% for mid cap
    'breakdown_pct': -0.075  # -7.5% for mid cap
}

# Default thresholds for BIG CAP (> 10 Triliun)
DEFAULT_THRESHOLD_BIG_CAP = {
    'min_sideways_days': 7,
    'min_pct_shares': 0.05,  # 0.05%
    'signal_day_pct': 0.75,
    'breakout_pct': 0.05,    # 5% for big cap
    'breakdown_pct': -0.05   # -5% for big cap
}


def get_sensitive_brokers(stock_code: str, top_n: int = 5) -> Tuple[List[str], List[Dict]]:
    """Get top sensitive brokers for a stock"""
    from composite_analyzer import calculate_broker_sensitivity_advanced
    sensitivity_data = calculate_broker_sensitivity_advanced(stock_code)
    brokers = sensitivity_data.get('brokers', [])[:top_n]
    return [b['broker_code'] for b in brokers], brokers


def get_stock_data(stock_code: str) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """Get price data, broker data, and issued shares"""
    # Price data
    query = '''SELECT date, open_price, high_price, low_price, close_price, volume
               FROM stock_daily WHERE stock_code = %s ORDER BY date'''
    price_df = pd.DataFrame(execute_query(query, (stock_code,), use_cache=False))
    if not price_df.empty:
        for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume']:
            if col in price_df.columns:
                price_df[col] = price_df[col].astype(float)

    # Broker data
    query = '''SELECT date, broker_code, net_lot, net_value
               FROM broker_summary WHERE stock_code = %s ORDER BY date'''
    broker_df = pd.DataFrame(execute_query(query, (stock_code,), use_cache=False))
    if not broker_df.empty:
        broker_df['net_lot'] = broker_df['net_lot'].astype(float)
        broker_df['net_value'] = broker_df['net_value'].astype(float)

    # Issued shares
    query = 'SELECT issued_shares FROM stock_fundamental WHERE stock_code = %s'
    result = execute_query(query, (stock_code,), use_cache=False)
    issued_shares = float(result[0]['issued_shares']) if result else 1e10  # Default 10B

    return price_df, broker_df, issued_shares


def find_sideways_periods(price_df: pd.DataFrame,
                          window: int = 7,
                          max_range_pct: float = 10.0,
                          min_duration: int = 5) -> List[Dict]:
    """
    Find sideways periods where price range is below threshold

    Args:
        price_df: Price dataframe with date, high_price, low_price
        window: Rolling window for range calculation
        max_range_pct: Maximum price range % to be considered sideways
        min_duration: Minimum days to be considered a sideways period

    Returns:
        List of sideways period dictionaries
    """
    df = price_df.copy()
    df['rolling_high'] = df['high_price'].rolling(window=window, min_periods=window).max()
    df['rolling_low'] = df['low_price'].rolling(window=window, min_periods=window).min()
    df['range_pct'] = (df['rolling_high'] - df['rolling_low']) / df['rolling_low'] * 100
    df['is_sideways'] = df['range_pct'] < max_range_pct

    sideways_periods = []
    in_sideways = False
    start_idx = None

    for i in range(len(df)):
        if df.iloc[i]['is_sideways'] and not pd.isna(df.iloc[i]['range_pct']):
            if not in_sideways:
                in_sideways = True
                start_idx = i
        else:
            if in_sideways and start_idx is not None:
                duration = i - start_idx
                if duration >= min_duration:
                    period_data = df.iloc[start_idx:i]
                    sideways_periods.append({
                        'start_idx': start_idx,
                        'end_idx': i - 1,
                        'start_date': df.iloc[start_idx]['date'],
                        'end_date': df.iloc[i-1]['date'],
                        'duration': duration,
                        'high': period_data['high_price'].max(),
                        'low': period_data['low_price'].min(),
                        'range_pct': (period_data['high_price'].max() - period_data['low_price'].min()) / period_data['low_price'].min() * 100
                    })
                in_sideways = False
                start_idx = None

    # Handle last period if still in sideways
    if in_sideways and start_idx is not None:
        duration = len(df) - start_idx
        if duration >= min_duration:
            period_data = df.iloc[start_idx:]
            sideways_periods.append({
                'start_idx': start_idx,
                'end_idx': len(df) - 1,
                'start_date': df.iloc[start_idx]['date'],
                'end_date': df.iloc[-1]['date'],
                'duration': duration,
                'high': period_data['high_price'].max(),
                'low': period_data['low_price'].min(),
                'range_pct': (period_data['high_price'].max() - period_data['low_price'].min()) / period_data['low_price'].min() * 100,
                'is_current': True  # Mark as ongoing sideways
            })

    return sideways_periods


def analyze_broker_activity_in_period(broker_df: pd.DataFrame,
                                       sensitive_codes: List[str],
                                       start_date: datetime,
                                       end_date: datetime,
                                       issued_shares: float) -> Dict:
    """
    Analyze sensitive broker activity during a period

    Returns:
        Dictionary with accumulation/distribution metrics
    """
    period_data = broker_df[
        (broker_df['date'] >= start_date) &
        (broker_df['date'] <= end_date) &
        (broker_df['broker_code'].isin(sensitive_codes))
    ]

    total_net_lot = period_data['net_lot'].sum() if not period_data.empty else 0
    total_net_value = period_data['net_value'].sum() if not period_data.empty else 0

    # Per broker analysis
    broker_stats = {}
    for code in sensitive_codes:
        broker_data = period_data[period_data['broker_code'] == code]
        if not broker_data.empty:
            accum_days = len(broker_data[broker_data['net_lot'] > 0])
            distrib_days = len(broker_data[broker_data['net_lot'] < 0])
            total_lot = broker_data['net_lot'].sum()
            broker_stats[code] = {
                'accum_days': accum_days,
                'distrib_days': distrib_days,
                'net_lot': total_lot,
                'is_accumulating': total_lot > 0
            }
        else:
            broker_stats[code] = {
                'accum_days': 0,
                'distrib_days': 0,
                'net_lot': 0,
                'is_accumulating': False
            }

    # Count brokers accumulating vs distributing
    brokers_accumulating = sum(1 for b in broker_stats.values() if b['is_accumulating'])
    brokers_distributing = sum(1 for b in broker_stats.values() if b['net_lot'] < 0)

    pct_of_shares = (total_net_lot * 100 / issued_shares) * 100 if issued_shares else 0

    return {
        'total_net_lot': total_net_lot,
        'total_net_value': total_net_value,
        'pct_of_shares': pct_of_shares,
        'brokers_accumulating': brokers_accumulating,
        'brokers_distributing': brokers_distributing,
        'broker_stats': broker_stats,
        'is_accumulation': brokers_accumulating >= 3 and total_net_lot > 0,
        'is_distribution': brokers_distributing >= 3 and total_net_lot < 0
    }


def check_breakout_or_breakdown(price_df: pd.DataFrame,
                                 sideways_end_date: datetime,
                                 sideways_high: float,
                                 sideways_low: float,
                                 breakout_pct: float = 0.10,
                                 breakdown_pct: float = -0.10,
                                 lookforward_days: int = 30) -> Dict:
    """
    Check if breakout (up) or breakdown (down) occurred after sideways

    Args:
        breakout_pct: Percentage above sideways high to be considered breakout (e.g., 0.10 = 10%)
        breakdown_pct: Percentage below sideways low to be considered breakdown (e.g., -0.10 = -10%)
    """
    future_df = price_df[price_df['date'] > sideways_end_date].head(lookforward_days)

    breakout_target = sideways_high * (1 + breakout_pct)
    breakdown_target = sideways_low * (1 + breakdown_pct)

    result = {
        'breakout': False,
        'breakdown': False,
        'breakout_date': None,
        'breakdown_date': None,
        'breakout_price': None,
        'breakdown_price': None,
        'days_to_breakout': None,
        'days_to_breakdown': None
    }

    for _, row in future_df.iterrows():
        # Check breakout (price goes above target)
        if not result['breakout'] and row['high_price'] >= breakout_target:
            result['breakout'] = True
            result['breakout_date'] = row['date']
            result['breakout_price'] = row['high_price']
            result['days_to_breakout'] = (row['date'] - sideways_end_date).days

        # Check breakdown (price goes below target)
        if not result['breakdown'] and row['low_price'] <= breakdown_target:
            result['breakdown'] = True
            result['breakdown_date'] = row['date']
            result['breakdown_price'] = row['low_price']
            result['days_to_breakdown'] = (row['date'] - sideways_end_date).days

        # If both found, stop
        if result['breakout'] and result['breakdown']:
            break

    return result


def calculate_dynamic_threshold(stock_code: str) -> Dict:
    """
    Calculate dynamic thresholds based on historical patterns.

    This function analyzes ALL historical data and calculates thresholds
    that auto-update as new patterns are discovered.

    Returns:
        Dictionary with:
        - accumulation_threshold: for BUY signals
        - distribution_threshold: for SELL signals
        - patterns_found: list of valid patterns
        - confidence: LOW/MEDIUM/HIGH based on sample size
    """
    # Check market cap from database
    query = '''SELECT sf.issued_shares,
               (SELECT close_price FROM stock_daily WHERE stock_code = %s ORDER BY date DESC LIMIT 1) as last_price
               FROM stock_fundamental sf WHERE sf.stock_code = %s'''
    result = execute_query(query, (stock_code, stock_code), use_cache=False)

    market_cap = 0
    if result:
        issued = float(result[0]['issued_shares']) if result[0]['issued_shares'] else 0
        price = float(result[0]['last_price']) if result[0]['last_price'] else 0
        market_cap = issued * price

    # Determine market cap category (Standard IDX)
    # Big Cap: > 10 Triliun
    # Mid Cap: 500 Miliar - 10 Triliun
    # Small Cap: < 500 Miliar
    if market_cap >= MARKET_CAP_BIG:
        cap_category = 'BIG_CAP'
        is_big_cap = True
        is_mid_cap = False
    elif market_cap >= MARKET_CAP_MID:
        cap_category = 'MID_CAP'
        is_big_cap = False
        is_mid_cap = True
    else:
        cap_category = 'SMALL_CAP'
        is_big_cap = False
        is_mid_cap = False

    # Set breakout/breakdown thresholds based on market cap category
    if is_big_cap:
        breakout_pct = 0.05    # 5% for big cap
        breakdown_pct = -0.05
    elif is_mid_cap:
        breakout_pct = 0.075   # 7.5% for mid cap
        breakdown_pct = -0.075
    else:
        breakout_pct = 0.10    # 10% for small cap
        breakdown_pct = -0.10

    # Get data
    price_df, broker_df, issued_shares = get_stock_data(stock_code)

    # Select default threshold based on market cap category
    if is_big_cap:
        default = DEFAULT_THRESHOLD_BIG_CAP
    elif is_mid_cap:
        default = DEFAULT_THRESHOLD_MID_CAP
    else:
        default = DEFAULT_THRESHOLD_SMALL_CAP

    if price_df.empty or broker_df.empty:
        return {
            'stock_code': stock_code,
            'market_cap': market_cap,
            'cap_category': cap_category,
            'is_big_cap': is_big_cap,
            'is_mid_cap': is_mid_cap,
            'accumulation': default.copy(),
            'distribution': default.copy(),
            'patterns': {'accumulation': [], 'distribution': []},
            'confidence': 'NO_DATA',
            'message': 'Insufficient data for analysis'
        }

    # Get sensitive brokers
    sensitive_codes, sensitive_info = get_sensitive_brokers(stock_code)

    if not sensitive_codes:
        return {
            'stock_code': stock_code,
            'market_cap': market_cap,
            'cap_category': cap_category,
            'is_big_cap': is_big_cap,
            'is_mid_cap': is_mid_cap,
            'accumulation': default.copy(),
            'distribution': default.copy(),
            'patterns': {'accumulation': [], 'distribution': []},
            'confidence': 'NO_DATA',
            'message': 'No sensitive brokers found'
        }

    # Find sideways periods
    sideways_periods = find_sideways_periods(price_df)

    # Analyze each sideways period
    accumulation_patterns = []
    distribution_patterns = []

    for sw in sideways_periods:
        # Skip if this is current ongoing sideways
        if sw.get('is_current', False):
            continue

        # Analyze broker activity
        broker_activity = analyze_broker_activity_in_period(
            broker_df, sensitive_codes,
            sw['start_date'], sw['end_date'],
            issued_shares
        )

        # Check for breakout or breakdown
        price_movement = check_breakout_or_breakdown(
            price_df, sw['end_date'],
            sw['high'], sw['low'],
            breakout_pct, breakdown_pct
        )

        # Valid ACCUMULATION pattern: broker accumulation + breakout
        if broker_activity['is_accumulation'] and price_movement['breakout']:
            accumulation_patterns.append({
                'sideways_start': sw['start_date'],
                'sideways_end': sw['end_date'],
                'sideways_days': sw['duration'],
                'sideways_high': sw['high'],
                'sideways_low': sw['low'],
                'net_lot': broker_activity['total_net_lot'],
                'pct_shares': broker_activity['pct_of_shares'],
                'brokers_accumulating': broker_activity['brokers_accumulating'],
                'breakout_date': price_movement['breakout_date'],
                'days_to_breakout': price_movement['days_to_breakout'],
                'breakout_price': price_movement['breakout_price']
            })

        # Valid DISTRIBUTION pattern: broker distribution + breakdown
        if broker_activity['is_distribution'] and price_movement['breakdown']:
            distribution_patterns.append({
                'sideways_start': sw['start_date'],
                'sideways_end': sw['end_date'],
                'sideways_days': sw['duration'],
                'sideways_high': sw['high'],
                'sideways_low': sw['low'],
                'net_lot': broker_activity['total_net_lot'],
                'pct_shares': broker_activity['pct_of_shares'],
                'brokers_distributing': broker_activity['brokers_distributing'],
                'breakdown_date': price_movement['breakdown_date'],
                'days_to_breakdown': price_movement['days_to_breakdown'],
                'breakdown_price': price_movement['breakdown_price']
            })

    # Calculate thresholds from patterns
    # (default already set above based on cap_category)

    # ACCUMULATION threshold
    if accumulation_patterns:
        avg_sideways = np.mean([p['sideways_days'] for p in accumulation_patterns])
        avg_pct_shares = np.mean([abs(p['pct_shares']) for p in accumulation_patterns])
        avg_days_to_breakout = np.mean([p['days_to_breakout'] for p in accumulation_patterns])

        accum_threshold = {
            'min_sideways_days': max(3, int(avg_sideways * 0.75)),
            'min_pct_shares': avg_pct_shares * 0.75,
            'signal_day_pct': 0.75,
            'avg_days_to_breakout': avg_days_to_breakout,
            'breakout_pct': breakout_pct,
            'sample_size': len(accumulation_patterns)
        }
    else:
        accum_threshold = default.copy()
        accum_threshold['breakout_pct'] = breakout_pct
        accum_threshold['sample_size'] = 0

    # DISTRIBUTION threshold
    if distribution_patterns:
        avg_sideways = np.mean([p['sideways_days'] for p in distribution_patterns])
        avg_pct_shares = np.mean([abs(p['pct_shares']) for p in distribution_patterns])
        avg_days_to_breakdown = np.mean([p['days_to_breakdown'] for p in distribution_patterns])

        distrib_threshold = {
            'min_sideways_days': max(3, int(avg_sideways * 0.75)),
            'min_pct_shares': avg_pct_shares * 0.75,
            'signal_day_pct': 0.75,
            'avg_days_to_breakdown': avg_days_to_breakdown,
            'breakdown_pct': breakdown_pct,
            'sample_size': len(distribution_patterns)
        }
    else:
        distrib_threshold = default.copy()
        distrib_threshold['breakdown_pct'] = breakdown_pct
        distrib_threshold['sample_size'] = 0

    # Determine confidence level
    total_patterns = len(accumulation_patterns) + len(distribution_patterns)
    if total_patterns >= 6:
        confidence = 'HIGH'
    elif total_patterns >= 3:
        confidence = 'MEDIUM'
    elif total_patterns >= 1:
        confidence = 'LOW'
    else:
        confidence = 'NO_PATTERN'

    return {
        'stock_code': stock_code,
        'market_cap': market_cap,
        'market_cap_formatted': f"Rp {market_cap/1e12:.1f} T" if market_cap >= 1e12 else f"Rp {market_cap/1e9:.1f} M",
        'cap_category': cap_category,
        'is_big_cap': is_big_cap,
        'is_mid_cap': is_mid_cap,
        'issued_shares': issued_shares,
        'sensitive_brokers': sensitive_codes,
        'accumulation': accum_threshold,
        'distribution': distrib_threshold,
        'patterns': {
            'accumulation': accumulation_patterns,
            'distribution': distribution_patterns
        },
        'total_sideways_found': len(sideways_periods),
        'confidence': confidence,
        'last_calculated': datetime.now().isoformat()
    }


def get_current_market_phase(stock_code: str) -> Dict:
    """
    Determine current market phase based on dynamic thresholds.

    Returns:
        Dictionary with current phase info and signals
    """
    # Get dynamic thresholds
    thresholds = calculate_dynamic_threshold(stock_code)

    # Get current data
    price_df, broker_df, issued_shares = get_stock_data(stock_code)
    sensitive_codes = thresholds['sensitive_brokers']

    if price_df.empty:
        return {'phase': 'NO_DATA', 'signal': None}

    # Find current sideways (if any)
    sideways_periods = find_sideways_periods(price_df)
    current_sideways = None

    for sw in sideways_periods:
        if sw.get('is_current', False):
            current_sideways = sw
            break

    if not current_sideways:
        # Check if in rally or decline
        recent_prices = price_df.tail(10)
        price_change_10d = (recent_prices.iloc[-1]['close_price'] - recent_prices.iloc[0]['close_price']) / recent_prices.iloc[0]['close_price'] * 100

        if price_change_10d > 5:
            return {'phase': 'RALLY', 'signal': None, 'price_change_10d': price_change_10d}
        elif price_change_10d < -5:
            return {'phase': 'DECLINE', 'signal': None, 'price_change_10d': price_change_10d}
        else:
            return {'phase': 'TRANSITION', 'signal': None, 'price_change_10d': price_change_10d}

    # Analyze broker activity in current sideways
    broker_activity = analyze_broker_activity_in_period(
        broker_df, sensitive_codes,
        current_sideways['start_date'], current_sideways['end_date'],
        issued_shares
    )

    # Determine phase and check for signals
    accum_threshold = thresholds['accumulation']
    distrib_threshold = thresholds['distribution']

    sideways_days = current_sideways['duration']
    pct_shares = abs(broker_activity['pct_of_shares'])

    result = {
        'phase': 'SIDEWAYS',
        'sideways_days': sideways_days,
        'sideways_start': current_sideways['start_date'],
        'sideways_high': current_sideways['high'],
        'sideways_low': current_sideways['low'],
        'broker_activity': broker_activity,
        'thresholds': thresholds,
        'signal': None
    }

    # Check for BUY signal (accumulation)
    if broker_activity['is_accumulation']:
        result['phase'] = 'ACCUMULATION'

        # Check if thresholds met
        days_threshold_met = sideways_days >= accum_threshold['min_sideways_days']
        pct_threshold_met = pct_shares >= accum_threshold['min_pct_shares']

        if days_threshold_met and pct_threshold_met:
            result['signal'] = {
                'type': 'BUY',
                'strength': 'STRONG' if pct_shares >= accum_threshold['min_pct_shares'] * 1.5 else 'MODERATE',
                'sideways_days': sideways_days,
                'pct_shares_accumulated': broker_activity['pct_of_shares'],
                'brokers_accumulating': broker_activity['brokers_accumulating'],
                'breakout_target': current_sideways['high'] * (1 + accum_threshold['breakout_pct']),
                'stop_loss': current_sideways['low'] * 0.97  # 3% below sideways low
            }
        elif days_threshold_met or pct_threshold_met:
            result['signal'] = {
                'type': 'BUY_PENDING',
                'days_threshold_met': days_threshold_met,
                'pct_threshold_met': pct_threshold_met,
                'days_remaining': max(0, accum_threshold['min_sideways_days'] - sideways_days),
                'pct_remaining': max(0, accum_threshold['min_pct_shares'] - pct_shares)
            }

    # Check for SELL signal (distribution)
    elif broker_activity['is_distribution']:
        result['phase'] = 'DISTRIBUTION'

        days_threshold_met = sideways_days >= distrib_threshold['min_sideways_days']
        pct_threshold_met = pct_shares >= distrib_threshold['min_pct_shares']

        if days_threshold_met and pct_threshold_met:
            result['signal'] = {
                'type': 'SELL',
                'strength': 'STRONG' if pct_shares >= distrib_threshold['min_pct_shares'] * 1.5 else 'MODERATE',
                'sideways_days': sideways_days,
                'pct_shares_distributed': broker_activity['pct_of_shares'],
                'brokers_distributing': broker_activity['brokers_distributing'],
                'breakdown_target': current_sideways['low'] * (1 + distrib_threshold['breakdown_pct']),
                'resistance': current_sideways['high'] * 1.03  # 3% above sideways high
            }
        elif days_threshold_met or pct_threshold_met:
            result['signal'] = {
                'type': 'SELL_PENDING',
                'days_threshold_met': days_threshold_met,
                'pct_threshold_met': pct_threshold_met
            }

    return result


# Test function
if __name__ == "__main__":
    for stock in ['CDIA', 'PANI', 'BBCA']:
        print(f"\n{'='*70}")
        print(f"DYNAMIC THRESHOLD: {stock}")
        print(f"{'='*70}")

        result = calculate_dynamic_threshold(stock)

        print(f"\nStock: {result['stock_code']}")
        print(f"Market Cap: {result.get('market_cap_formatted', 'N/A')}")
        print(f"Category: {result.get('cap_category', 'N/A')}")
        print(f"Sensitive Brokers: {result['sensitive_brokers']}")
        print(f"Confidence: {result['confidence']}")

        print(f"\nACCUMULATION Threshold:")
        for k, v in result['accumulation'].items():
            print(f"  {k}: {v}")

        print(f"\nDISTRIBUTION Threshold:")
        for k, v in result['distribution'].items():
            print(f"  {k}: {v}")

        print(f"\nPatterns Found:")
        print(f"  Accumulation: {len(result['patterns']['accumulation'])}")
        print(f"  Distribution: {len(result['patterns']['distribution'])}")
