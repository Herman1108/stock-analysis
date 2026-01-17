# -*- coding: utf-8 -*-
"""
ALGORITMA DETEKSI SUPPORT & RESISTANCE KUAT
============================================
Menggunakan beberapa metode:
1. Pivot Points (Swing High/Low)
2. Multi-Touch Detection (level yang di-test berkali-kali)
3. Volume Confirmation (volume tinggi di level tersebut)
4. Cluster Zones (gabungkan level berdekatan)
5. Round Number Psychology (level psikologis)
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

# Ensure app directory is in path for database import
app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from database import get_connection

# Module-level connection removed - use get_connection() context manager instead
conn = None
cur = None


def get_stock_data(stock_code):
    """Ambil data saham dari database"""
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('''
            SELECT date, open_price as open, high_price as high,
                   low_price as low, close_price as close, volume,
                   change_percent as change
            FROM stock_daily
            WHERE stock_code = %s
            ORDER BY date ASC
        ''', (stock_code,))
        return cur.fetchall()


# ============================================================
# 1. PIVOT POINTS DETECTION (Swing High/Low)
# ============================================================
def detect_pivot_points(data, left_bars=5, right_bars=5):
    """
    Deteksi Pivot High dan Pivot Low

    Pivot High: High yang lebih tinggi dari 'left_bars' candle sebelum
                DAN 'right_bars' candle sesudah
    Pivot Low:  Low yang lebih rendah dari 'left_bars' candle sebelum
                DAN 'right_bars' candle sesudah
    """
    pivot_highs = []
    pivot_lows = []

    for i in range(left_bars, len(data) - right_bars):
        current_high = float(data[i]['high'])
        current_low = float(data[i]['low'])

        # Check Pivot High
        is_pivot_high = True
        for j in range(i - left_bars, i):
            if float(data[j]['high']) >= current_high:
                is_pivot_high = False
                break
        if is_pivot_high:
            for j in range(i + 1, i + right_bars + 1):
                if float(data[j]['high']) >= current_high:
                    is_pivot_high = False
                    break

        if is_pivot_high:
            pivot_highs.append({
                'date': data[i]['date'],
                'price': current_high,
                'type': 'RESISTANCE',
                'volume': float(data[i]['volume']),
                'index': i
            })

        # Check Pivot Low
        is_pivot_low = True
        for j in range(i - left_bars, i):
            if float(data[j]['low']) <= current_low:
                is_pivot_low = False
                break
        if is_pivot_low:
            for j in range(i + 1, i + right_bars + 1):
                if float(data[j]['low']) <= current_low:
                    is_pivot_low = False
                    break

        if is_pivot_low:
            pivot_lows.append({
                'date': data[i]['date'],
                'price': current_low,
                'type': 'SUPPORT',
                'volume': float(data[i]['volume']),
                'index': i
            })

    return pivot_highs, pivot_lows


# ============================================================
# 2. MULTI-TOUCH DETECTION
# ============================================================
def detect_multi_touch(data, pivot_highs, pivot_lows, tolerance_pct=1.5):
    """
    Cari level yang sudah di-touch/test berkali-kali

    tolerance_pct: toleransi persentase untuk menganggap 2 level sama
    """
    all_levels = []

    # Combine all pivots
    for p in pivot_highs:
        all_levels.append(p)
    for p in pivot_lows:
        all_levels.append(p)

    # Group by similar price levels
    level_groups = []
    used = set()

    for i, level in enumerate(all_levels):
        if i in used:
            continue

        group = [level]
        used.add(i)

        for j, other in enumerate(all_levels):
            if j in used:
                continue

            # Check if prices are within tolerance
            price_diff_pct = abs(level['price'] - other['price']) / level['price'] * 100
            if price_diff_pct <= tolerance_pct:
                group.append(other)
                used.add(j)

        if len(group) >= 2:  # At least 2 touches
            avg_price = sum(p['price'] for p in group) / len(group)
            total_volume = sum(p['volume'] for p in group)
            dates = [p['date'] for p in group]

            # Determine if it's S or R based on majority
            support_count = sum(1 for p in group if p['type'] == 'SUPPORT')
            resistance_count = len(group) - support_count

            level_type = 'SUPPORT' if support_count > resistance_count else 'RESISTANCE'
            if support_count > 0 and resistance_count > 0:
                level_type = 'S/R FLIP'  # Level yang berfungsi sebagai S dan R

            level_groups.append({
                'price': round(avg_price, 0),
                'touches': len(group),
                'type': level_type,
                'total_volume': total_volume,
                'dates': sorted(dates),
                'strength': len(group) * 10 + (total_volume / 1e9)  # Score
            })

    return sorted(level_groups, key=lambda x: -x['strength'])


# ============================================================
# 3. VOLUME-WEIGHTED S/R
# ============================================================
def detect_volume_sr(data, lookback=60, top_n=10):
    """
    Deteksi S/R berdasarkan volume tinggi

    High volume di suatu level = level tersebut signifikan
    """
    # Create price-volume map
    price_volume = defaultdict(lambda: {'volume': 0, 'dates': [], 'highs': 0, 'lows': 0})

    # Round prices to nearest 50 or 100 for grouping
    def round_price(price):
        if price < 5000:
            return round(price / 25) * 25
        elif price < 10000:
            return round(price / 50) * 50
        else:
            return round(price / 100) * 100

    recent_data = data[-lookback:] if len(data) > lookback else data

    for d in recent_data:
        high = round_price(float(d['high']))
        low = round_price(float(d['low']))
        vol = float(d['volume'])
        date = d['date']

        # Add volume to high and low levels
        price_volume[high]['volume'] += vol * 0.5
        price_volume[high]['dates'].append(date)
        price_volume[high]['highs'] += 1

        price_volume[low]['volume'] += vol * 0.5
        price_volume[low]['dates'].append(date)
        price_volume[low]['lows'] += 1

    # Sort by volume
    sorted_levels = sorted(price_volume.items(), key=lambda x: -x[1]['volume'])[:top_n]

    result = []
    for price, info in sorted_levels:
        level_type = 'RESISTANCE' if info['highs'] > info['lows'] else 'SUPPORT'
        result.append({
            'price': price,
            'volume': info['volume'],
            'touch_count': len(set(info['dates'])),
            'type': level_type,
            'last_date': max(info['dates']) if info['dates'] else None
        })

    return result


# ============================================================
# 4. CLUSTER ZONES
# ============================================================
def create_cluster_zones(multi_touch_levels, volume_levels, cluster_tolerance_pct=2.0):
    """
    Gabungkan level yang berdekatan menjadi ZONE

    Zone lebih reliable daripada single line
    """
    all_prices = []

    for level in multi_touch_levels:
        all_prices.append({
            'price': level['price'],
            'strength': level['strength'],
            'type': level['type'],
            'source': 'multi_touch',
            'touches': level['touches'],
            'dates': level['dates']
        })

    for level in volume_levels:
        all_prices.append({
            'price': level['price'],
            'strength': level['volume'] / 1e9,
            'type': level['type'],
            'source': 'volume',
            'touches': level['touch_count'],
            'dates': [level['last_date']] if level['last_date'] else []
        })

    # Sort by price
    all_prices.sort(key=lambda x: x['price'])

    # Cluster nearby prices
    zones = []
    used = set()

    for i, level in enumerate(all_prices):
        if i in used:
            continue

        cluster = [level]
        used.add(i)

        for j, other in enumerate(all_prices):
            if j in used:
                continue

            price_diff_pct = abs(level['price'] - other['price']) / level['price'] * 100
            if price_diff_pct <= cluster_tolerance_pct:
                cluster.append(other)
                used.add(j)

        if cluster:
            prices = [c['price'] for c in cluster]
            zone_low = min(prices)
            zone_high = max(prices)
            zone_mid = sum(prices) / len(prices)

            total_strength = sum(c['strength'] for c in cluster)
            total_touches = sum(c['touches'] for c in cluster)

            all_dates = []
            for c in cluster:
                all_dates.extend(c['dates'])

            # Determine zone type
            support_count = sum(1 for c in cluster if c['type'] == 'SUPPORT')
            resistance_count = sum(1 for c in cluster if c['type'] == 'RESISTANCE')

            if support_count > 0 and resistance_count > 0:
                zone_type = 'S/R ZONE'
            elif support_count > resistance_count:
                zone_type = 'SUPPORT ZONE'
            else:
                zone_type = 'RESISTANCE ZONE'

            zones.append({
                'zone_low': round(zone_low, 0),
                'zone_high': round(zone_high, 0),
                'zone_mid': round(zone_mid, 0),
                'type': zone_type,
                'strength': total_strength,
                'touches': total_touches,
                'sources': len(cluster),
                'dates': sorted(set(all_dates))
            })

    return sorted(zones, key=lambda x: -x['strength'])


# ============================================================
# 5. ROUND NUMBER PSYCHOLOGY
# ============================================================
def detect_round_numbers(data, recent_range_pct=20):
    """
    Deteksi level psikologis (angka bulat)

    Level seperti 10,000, 15,000, dll sering menjadi S/R
    """
    recent_data = data[-60:] if len(data) > 60 else data

    high_price = max(float(d['high']) for d in recent_data)
    low_price = min(float(d['low']) for d in recent_data)
    current_price = float(data[-1]['close'])

    # Determine round number interval based on price range
    if current_price < 1000:
        interval = 100
    elif current_price < 5000:
        interval = 250
    elif current_price < 10000:
        interval = 500
    else:
        interval = 1000

    round_levels = []

    # Find round numbers in range
    start = int(low_price / interval) * interval
    end = int(high_price / interval + 1) * interval

    for level in range(start, end + interval, interval):
        if low_price * 0.9 <= level <= high_price * 1.1:
            # Check how many times price touched this level
            touches = 0
            touch_dates = []
            total_vol = 0

            for d in recent_data:
                h = float(d['high'])
                l = float(d['low'])

                # Check if price crossed or touched this level
                if l <= level <= h:
                    touches += 1
                    touch_dates.append(d['date'])
                    total_vol += float(d['volume'])

            if touches >= 2:
                round_levels.append({
                    'price': level,
                    'touches': touches,
                    'type': 'PSYCHOLOGICAL',
                    'dates': touch_dates,
                    'volume': total_vol
                })

    return sorted(round_levels, key=lambda x: -x['touches'])


# ============================================================
# MAIN - Analisis PANI
# ============================================================
if __name__ == '__main__':
    stock_code = 'PANI'

    print("=" * 80)
    print(f"ANALISIS SUPPORT & RESISTANCE KUAT - {stock_code}")
    print("=" * 80)

    # Get data
    data = get_stock_data(stock_code)
    if not data:
        print(f"No data found for {stock_code}")
        exit()

    print(f"\nTotal data: {len(data)} records")
    print(f"Period: {data[0]['date']} to {data[-1]['date']}")
    print(f"Current Price: Rp {float(data[-1]['close']):,.0f}")

    # 1. Detect Pivot Points
    print("\n" + "=" * 80)
    print("1. PIVOT POINTS (Swing High/Low)")
    print("=" * 80)
    print("""
Formula:
- Pivot High: High[i] > High[i-5...i-1] DAN High[i] > High[i+1...i+5]
- Pivot Low:  Low[i] < Low[i-5...i-1] DAN Low[i] < Low[i+1...i+5]
""")

    pivot_highs, pivot_lows = detect_pivot_points(data, left_bars=5, right_bars=5)

    print(f"\nPivot Highs (Resistance): {len(pivot_highs)}")
    print("-" * 60)
    for i, p in enumerate(pivot_highs[-10:], 1):  # Last 10
        print(f"  {i}. {p['date']} | Rp {p['price']:,.0f} | Vol: {p['volume']/1e6:.1f}M")

    print(f"\nPivot Lows (Support): {len(pivot_lows)}")
    print("-" * 60)
    for i, p in enumerate(pivot_lows[-10:], 1):  # Last 10
        print(f"  {i}. {p['date']} | Rp {p['price']:,.0f} | Vol: {p['volume']/1e6:.1f}M")

    # 2. Multi-Touch Detection
    print("\n" + "=" * 80)
    print("2. MULTI-TOUCH LEVELS (Level yang di-test berkali-kali)")
    print("=" * 80)
    print("""
Formula:
- Cari pivot points yang harganya berdekatan (toleransi 1.5%)
- Level dengan 2+ touches = KUAT
- Level dengan 3+ touches = SANGAT KUAT
""")

    multi_touch = detect_multi_touch(data, pivot_highs, pivot_lows, tolerance_pct=1.5)

    print(f"\nMulti-Touch Levels: {len(multi_touch)}")
    print("-" * 60)
    for i, level in enumerate(multi_touch[:15], 1):
        strength_label = "SANGAT KUAT" if level['touches'] >= 3 else "KUAT"
        print(f"\n  {i}. Rp {level['price']:,.0f} [{level['type']}] - {level['touches']} touches - {strength_label}")
        print(f"     Tanggal: {', '.join(str(d) for d in level['dates'][:5])}")
        if len(level['dates']) > 5:
            print(f"              ... dan {len(level['dates'])-5} lainnya")

    # 3. Volume-Weighted S/R
    print("\n" + "=" * 80)
    print("3. VOLUME-WEIGHTED S/R (Level dengan volume tinggi)")
    print("=" * 80)
    print("""
Formula:
- Kumpulkan volume di setiap level harga
- Level dengan volume tinggi = lebih signifikan
- High volume menunjukkan banyak transaksi di level tersebut
""")

    volume_sr = detect_volume_sr(data, lookback=120, top_n=10)

    print(f"\nTop 10 Volume S/R Levels:")
    print("-" * 60)
    for i, level in enumerate(volume_sr, 1):
        print(f"  {i}. Rp {level['price']:,.0f} [{level['type']}]")
        print(f"     Volume: {level['volume']/1e9:.2f}B | Touches: {level['touch_count']} | Last: {level['last_date']}")

    # 4. Cluster Zones
    print("\n" + "=" * 80)
    print("4. CLUSTER ZONES (Gabungan level berdekatan)")
    print("=" * 80)
    print("""
Formula:
- Gabungkan semua level dari multi-touch dan volume
- Level dalam range 2% digabung menjadi ZONE
- Zone lebih reliable daripada single line
""")

    zones = create_cluster_zones(multi_touch, volume_sr, cluster_tolerance_pct=2.0)

    print(f"\nStrong Zones: {len(zones)}")
    print("-" * 60)
    for i, zone in enumerate(zones[:10], 1):
        print(f"\n  ZONE {i}: Rp {zone['zone_low']:,.0f} - Rp {zone['zone_high']:,.0f}")
        print(f"  Type: {zone['type']} | Strength: {zone['strength']:.1f} | Touches: {zone['touches']}")
        print(f"  Mid: Rp {zone['zone_mid']:,.0f}")
        if zone['dates']:
            print(f"  Dates: {', '.join(str(d) for d in zone['dates'][:3])}")

    # 5. Round Numbers
    print("\n" + "=" * 80)
    print("5. PSYCHOLOGICAL LEVELS (Angka Bulat)")
    print("=" * 80)
    print("""
Formula:
- Level psikologis: 10,000, 11,000, 12,000, dll
- Trader sering menempatkan order di angka bulat
- Semakin sering di-test, semakin kuat
""")

    round_levels = detect_round_numbers(data)

    print(f"\nPsychological Levels:")
    print("-" * 60)
    for i, level in enumerate(round_levels[:10], 1):
        print(f"  {i}. Rp {level['price']:,.0f} | Touches: {level['touches']}")
        print(f"     Dates: {', '.join(str(d) for d in level['dates'][:3])}...")

    # SUMMARY - Strong S/R Levels
    print("\n" + "=" * 80)
    print("RINGKASAN: LEVEL S/R TERKUAT")
    print("=" * 80)

    current_price = float(data[-1]['close'])

    # Collect all strong levels
    all_strong_levels = []

    # From multi-touch (3+ touches)
    for level in multi_touch:
        if level['touches'] >= 2:
            all_strong_levels.append({
                'price': level['price'],
                'type': level['type'],
                'reason': f"{level['touches']} touches",
                'dates': level['dates'],
                'strength': level['strength']
            })

    # From zones (high strength)
    for zone in zones[:5]:
        all_strong_levels.append({
            'price': zone['zone_mid'],
            'type': zone['type'],
            'reason': f"Zone {zone['zone_low']:,.0f}-{zone['zone_high']:,.0f}",
            'dates': zone['dates'],
            'strength': zone['strength']
        })

    # Sort by distance from current price
    all_strong_levels.sort(key=lambda x: abs(x['price'] - current_price))

    # Separate to Support and Resistance
    supports = [l for l in all_strong_levels if l['price'] < current_price]
    resistances = [l for l in all_strong_levels if l['price'] >= current_price]

    print(f"\nHarga Saat Ini: Rp {current_price:,.0f}")
    print(f"Tanggal Terakhir: {data[-1]['date']}")

    print(f"\n{'='*40}")
    print("SUPPORT TERDEKAT (di bawah harga saat ini)")
    print(f"{'='*40}")
    for i, s in enumerate(supports[:5], 1):
        distance = (current_price - s['price']) / current_price * 100
        print(f"\n  S{i}. Rp {s['price']:,.0f} ({distance:.1f}% di bawah)")
        print(f"      Alasan: {s['reason']}")
        print(f"      Tanggal test: {', '.join(str(d) for d in s['dates'][:3])}")

    print(f"\n{'='*40}")
    print("RESISTANCE TERDEKAT (di atas harga saat ini)")
    print(f"{'='*40}")
    for i, r in enumerate(resistances[:5], 1):
        distance = (r['price'] - current_price) / current_price * 100
        print(f"\n  R{i}. Rp {r['price']:,.0f} ({distance:.1f}% di atas)")
        print(f"      Alasan: {r['reason']}")
        print(f"      Tanggal test: {', '.join(str(d) for d in r['dates'][:3])}")

    # Trading Recommendation
    print("\n" + "=" * 80)
    print("REKOMENDASI TRADING")
    print("=" * 80)

    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None

    if nearest_support and nearest_resistance:
        risk = current_price - nearest_support['price']
        reward = nearest_resistance['price'] - current_price
        rr_ratio = reward / risk if risk > 0 else 0

        print(f"""
Posisi dalam Range:
  Support Terdekat : Rp {nearest_support['price']:,.0f}
  Harga Saat Ini   : Rp {current_price:,.0f}
  Resistance       : Rp {nearest_resistance['price']:,.0f}

Kalkulasi R:R:
  Risk (ke Support)     : Rp {risk:,.0f} ({risk/current_price*100:.1f}%)
  Reward (ke Resistance): Rp {reward:,.0f} ({reward/current_price*100:.1f}%)
  Risk:Reward Ratio     : 1:{rr_ratio:.1f}
""")

        if rr_ratio >= 2:
            print("  >> FAVORABLE untuk entry (R:R >= 2)")
        elif rr_ratio >= 1.5:
            print("  >> ACCEPTABLE untuk entry (R:R >= 1.5)")
        else:
            print("  >> KURANG FAVORABLE - tunggu pullback ke support")

    conn.close()
