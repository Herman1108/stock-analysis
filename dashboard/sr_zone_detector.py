# -*- coding: utf-8 -*-
"""
SR ZONE DETECTOR - Fungsi untuk Deteksi Zona Support/Resistance
Dapat diimpor ke dashboard atau script lain
"""

def detect_sr_zones(data_list, zone_height=40, min_days=10):
    """
    Deteksi zona Support/Resistance horizontal

    Parameters:
    -----------
    data_list : list of dict
        Data OHLCV dengan keys: date, high, low, close, volume
    zone_height : int
        Tinggi zona dalam rupiah (default 40)
    min_days : int
        Minimal berapa hari harga harus berada di zona (default 10)

    Returns:
    --------
    list of dict
        Zona-zona S/R dengan keys: low, high, mid, strength, type
    """

    if not data_list:
        return []

    min_price = min(d['low'] for d in data_list)
    max_price = max(d['high'] for d in data_list)

    zones = []
    price = min_price

    while price <= max_price:
        zone_low = price
        zone_high = price + zone_height

        # Count days in zone
        days_in_zone = 0
        bounces = 0
        touches_as_support = 0
        touches_as_resistance = 0
        last_was_in = False

        for d in data_list:
            in_zone = not (d['high'] < zone_low or d['low'] > zone_high)

            if in_zone:
                days_in_zone += 1

                # Check if acting as support or resistance
                if d['low'] >= zone_low and d['low'] <= zone_high:
                    touches_as_support += 1
                if d['high'] >= zone_low and d['high'] <= zone_high:
                    touches_as_resistance += 1

            if last_was_in and not in_zone:
                bounces += 1

            last_was_in = in_zone

        if days_in_zone >= min_days:
            # Determine zone type
            if touches_as_support > touches_as_resistance * 1.5:
                zone_type = 'SUPPORT'
            elif touches_as_resistance > touches_as_support * 1.5:
                zone_type = 'RESISTANCE'
            else:
                zone_type = 'S/R ZONE'

            zones.append({
                'low': zone_low,
                'high': zone_high,
                'mid': (zone_low + zone_high) / 2,
                'days': days_in_zone,
                'bounces': bounces,
                'strength': days_in_zone + bounces * 3,
                'type': zone_type
            })

        price += zone_height / 2

    # Remove overlaps
    zones.sort(key=lambda x: x['strength'], reverse=True)
    final = []

    for zone in zones:
        is_overlap = False
        for existing in final:
            overlap_low = max(zone['low'], existing['low'])
            overlap_high = min(zone['high'], existing['high'])
            if overlap_high > overlap_low:
                overlap_pct = (overlap_high - overlap_low) / zone_height
                if overlap_pct > 0.5:
                    is_overlap = True
                    break

        if not is_overlap:
            final.append(zone)

    final.sort(key=lambda x: x['mid'])
    return final


def detect_pivot_zones(data_list, lookback=2, tolerance=25):
    """
    Deteksi zona dari swing high/low points

    Parameters:
    -----------
    data_list : list of dict
        Data OHLCV
    lookback : int
        Berapa bar untuk konfirmasi pivot
    tolerance : float
        Toleransi untuk mengelompokkan pivot yang berdekatan

    Returns:
    --------
    list of dict
        Zona pivot dengan keys: low, high, mid, touches, type
    """

    if len(data_list) < lookback * 2 + 1:
        return []

    pivots = []

    for i in range(lookback, len(data_list) - lookback):
        is_high = all(data_list[i]['high'] >= data_list[i-j]['high'] and
                     data_list[i]['high'] >= data_list[i+j]['high']
                     for j in range(1, lookback+1))

        is_low = all(data_list[i]['low'] <= data_list[i-j]['low'] and
                    data_list[i]['low'] <= data_list[i+j]['low']
                    for j in range(1, lookback+1))

        if is_high:
            pivots.append({'price': data_list[i]['high'], 'type': 'HIGH'})
        if is_low:
            pivots.append({'price': data_list[i]['low'], 'type': 'LOW'})

    # Cluster nearby pivots
    pivots.sort(key=lambda x: x['price'])
    zones = []
    used = set()

    for i, p in enumerate(pivots):
        if i in used:
            continue

        cluster = [p]
        used.add(i)

        for j, other in enumerate(pivots):
            if j in used:
                continue
            if abs(other['price'] - p['price']) <= tolerance:
                cluster.append(other)
                used.add(j)

        if len(cluster) >= 2:
            prices = [c['price'] for c in cluster]
            high_count = sum(1 for c in cluster if c['type'] == 'HIGH')
            low_count = sum(1 for c in cluster if c['type'] == 'LOW')

            zones.append({
                'low': min(prices) - 5,
                'high': max(prices) + 5,
                'mid': sum(prices) / len(prices),
                'touches': len(cluster),
                'type': 'RESISTANCE' if high_count > low_count else 'SUPPORT'
            })

    zones.sort(key=lambda x: x['mid'])
    return zones


def get_key_zones(data_list, max_zones=15):
    """
    Fungsi utama: Dapatkan zona S/R kunci dengan menggabungkan semua metode

    Parameters:
    -----------
    data_list : list of dict
        Data OHLCV
    max_zones : int
        Maksimal jumlah zona yang dikembalikan

    Returns:
    --------
    list of dict
        Zona-zona S/R terurut dari harga terendah
    """

    # Detect using both methods
    horizontal = detect_sr_zones(data_list, zone_height=40, min_days=12)
    pivot = detect_pivot_zones(data_list, lookback=2, tolerance=30)

    # Combine
    all_zones = []

    for z in horizontal:
        all_zones.append({
            'low': z['low'],
            'high': z['high'],
            'mid': z['mid'],
            'strength': z['strength'],
            'type': z['type'],
            'source': 'HORIZONTAL'
        })

    for z in pivot:
        all_zones.append({
            'low': z['low'],
            'high': z['high'],
            'mid': z['mid'],
            'strength': z['touches'] * 5,
            'type': z['type'],
            'source': 'PIVOT'
        })

    # Remove duplicates
    all_zones.sort(key=lambda x: x['strength'], reverse=True)
    final = []

    for zone in all_zones:
        is_dup = False
        for existing in final:
            if abs(zone['mid'] - existing['mid']) < 35:
                is_dup = True
                break
        if not is_dup and len(final) < max_zones:
            final.append(zone)

    final.sort(key=lambda x: x['mid'])
    return final


def analyze_current_position(data_list, zones):
    """
    Analisis posisi harga saat ini relatif terhadap zona S/R

    Returns:
    --------
    dict dengan info support/resistance terdekat
    """

    if not data_list or not zones:
        return {}

    current = data_list[-1]['close']

    zones_below = [z for z in zones if z['high'] < current]
    zones_above = [z for z in zones if z['low'] > current]
    zones_at = [z for z in zones if z['low'] <= current <= z['high']]

    result = {
        'current_price': current,
        'in_zone': zones_at[0] if zones_at else None,
        'nearest_support': max(zones_below, key=lambda x: x['high']) if zones_below else None,
        'nearest_resistance': min(zones_above, key=lambda x: x['low']) if zones_above else None
    }

    return result


# ============ TEST ============
if __name__ == '__main__':
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    conn = psycopg2.connect(
        host='localhost',
        database='stock_analysis',
        user='postgres',
        password='postgres'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT date, high_price as high, low_price as low,
               close_price as close, volume
        FROM stock_daily
        WHERE stock_code = 'NCKL'
        ORDER BY date ASC
    ''')

    data = [{'date': r['date'], 'high': float(r['high']), 'low': float(r['low']),
             'close': float(r['close']), 'volume': int(r['volume'])} for r in cur.fetchall()]

    print("="*70)
    print("SR ZONE DETECTOR - TEST")
    print("="*70)

    zones = get_key_zones(data, max_zones=12)

    print(f"\nZona S/R Terdeteksi: {len(zones)}")
    print(f"\n{'No':<4} {'Low':>8} {'High':>8} {'Type':<12} {'Source':<12}")
    print("-"*55)

    for idx, z in enumerate(zones, 1):
        print(f"{idx:<4} {z['low']:>8,.0f} {z['high']:>8,.0f} {z['type']:<12} {z['source']:<12}")

    # Current position
    position = analyze_current_position(data, zones)

    print(f"\n" + "="*70)
    print(f"Harga Saat Ini: {position['current_price']:,.0f}")
    print("="*70)

    if position['in_zone']:
        z = position['in_zone']
        print(f"DALAM ZONA: {z['low']:,.0f} - {z['high']:,.0f}")

    if position['nearest_support']:
        z = position['nearest_support']
        dist = (position['current_price'] - z['high']) / position['current_price'] * 100
        print(f"Support Terdekat: {z['low']:,.0f} - {z['high']:,.0f} (jarak {dist:.1f}%)")

    if position['nearest_resistance']:
        z = position['nearest_resistance']
        dist = (z['low'] - position['current_price']) / position['current_price'] * 100
        print(f"Resistance Terdekat: {z['low']:,.0f} - {z['high']:,.0f} (jarak {dist:.1f}%)")

    conn.close()
