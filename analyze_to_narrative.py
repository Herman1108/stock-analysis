"""
Stock Analysis to Narrative Generator
Generates educational narrative analysis from stock data
"""
import sys
import os
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from database import execute_query
from composite_analyzer import (
    calculate_price_movements,
    get_comprehensive_analysis
)

def get_stock_fundamental(stock_code: str) -> dict:
    """Get fundamental data for stock"""
    query = """
        SELECT * FROM stock_fundamental
        WHERE stock_code = %s
        ORDER BY report_date DESC LIMIT 1
    """
    result = execute_query(query, (stock_code,))
    if result:
        return dict(result[0])
    return {}

def get_stock_profile(stock_code: str) -> dict:
    """Get company profile"""
    query = """
        SELECT * FROM stock_profile
        WHERE stock_code = %s
    """
    result = execute_query(query, (stock_code,))
    if result:
        return dict(result[0])
    return {}

def get_support_resistance(stock_code: str) -> dict:
    """Calculate support and resistance levels"""
    query = """
        SELECT close_price, high_price, low_price
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date DESC LIMIT 30
    """
    result = execute_query(query, (stock_code,))
    if not result:
        return {}

    prices = [float(r['close_price']) for r in result]
    highs = [float(r['high_price']) for r in result]
    lows = [float(r['low_price']) for r in result]

    current = prices[0]
    support = min(lows)
    resistance = max(highs)

    return {
        'current': current,
        'support': support,
        'resistance': resistance,
        'distance_to_support': ((current - support) / current) * 100,
        'distance_to_resistance': ((resistance - current) / current) * 100,
        'position': 'Dekat Support' if (current - support) < (resistance - current) else 'Dekat Resistance'
    }

def get_accumulation_signal(stock_code: str) -> dict:
    """Get accumulation signal from broker data"""
    query = """
        SELECT
            SUM(CASE WHEN net_value > 0 THEN net_value ELSE 0 END) as total_buy,
            SUM(CASE WHEN net_value < 0 THEN ABS(net_value) ELSE 0 END) as total_sell,
            COUNT(DISTINCT broker_code) as broker_count
        FROM broker_summary
        WHERE stock_code = %s
        AND date >= CURRENT_DATE - INTERVAL '30 days'
    """
    result = execute_query(query, (stock_code,))
    if not result or not result[0]['total_buy']:
        return {'signal': 'N/A', 'confidence': 'LOW'}

    data = result[0]
    total_buy = float(data['total_buy'] or 0)
    total_sell = float(data['total_sell'] or 0)
    total_flow = total_buy + total_sell

    if total_flow == 0:
        return {'signal': 'NETRAL', 'confidence': 'LOW', 'ratio': 50}

    buy_ratio = (total_buy / total_flow) * 100

    if buy_ratio >= 60:
        signal = 'AKUMULASI'
        confidence = 'HIGH' if buy_ratio >= 70 else 'MEDIUM'
    elif buy_ratio <= 40:
        signal = 'DISTRIBUSI'
        confidence = 'HIGH' if buy_ratio <= 30 else 'MEDIUM'
    else:
        signal = 'NETRAL'
        confidence = 'LOW'

    return {
        'signal': signal,
        'confidence': confidence,
        'ratio': round(buy_ratio, 1),
        'total_buy': total_buy,
        'total_sell': total_sell
    }

def format_rupiah(value):
    """Format number to Rupiah"""
    if value is None:
        return "N/A"
    if abs(value) >= 1e12:
        return f"Rp {value/1e12:,.2f} T"
    elif abs(value) >= 1e9:
        return f"Rp {value/1e9:,.2f} M"
    elif abs(value) >= 1e6:
        return f"Rp {value/1e6:,.2f} Jt"
    else:
        return f"Rp {value:,.0f}"

def generate_narrative(stock_code: str) -> str:
    """Generate educational narrative analysis"""

    # Get all data
    profile = get_stock_profile(stock_code)
    fundamental = get_stock_fundamental(stock_code)
    movements = calculate_price_movements(stock_code)
    sr_levels = get_support_resistance(stock_code)
    accumulation = get_accumulation_signal(stock_code)

    # Get comprehensive analysis
    try:
        analysis = get_comprehensive_analysis(stock_code)
    except Exception as e:
        analysis = {}

    current_price = movements.get('current_price', 0)
    current_date = movements.get('current_date', datetime.now())

    # Build narrative
    narrative = []
    narrative.append("=" * 70)
    narrative.append(f"ANALISIS SAHAM {stock_code}")
    narrative.append(f"Tanggal Analisis: {datetime.now().strftime('%d %B %Y, %H:%M WIB')}")
    narrative.append("=" * 70)
    narrative.append("")

    # Company Profile
    if profile:
        narrative.append("PROFIL PERUSAHAAN")
        narrative.append("-" * 40)
        narrative.append(f"Nama    : {profile.get('company_name', stock_code)}")
        narrative.append(f"Sektor  : {profile.get('sector', 'N/A')}")
        if profile.get('ipo_price'):
            narrative.append(f"Harga IPO: Rp {profile.get('ipo_price'):,.0f}")
        narrative.append("")

    # Current Price
    narrative.append("KONDISI HARGA SAAT INI")
    narrative.append("-" * 40)
    narrative.append(f"Harga Terakhir: Rp {current_price:,.0f}")
    narrative.append("")

    # Price Movements
    narrative.append("PERGERAKAN HARGA:")
    periods = movements.get('periods', {})
    for period, data in periods.items():
        if data.get('change_pct') is not None:
            direction = "naik" if data['change_pct'] > 0 else "turun" if data['change_pct'] < 0 else "tetap"
            narrative.append(f"  - {period}: {direction} {abs(data['change_pct']):.2f}%")
    narrative.append("")

    # Support & Resistance
    if sr_levels:
        narrative.append("LEVEL SUPPORT & RESISTANCE")
        narrative.append("-" * 40)
        narrative.append(f"Support    : Rp {sr_levels['support']:,.0f} (jarak {sr_levels['distance_to_support']:.1f}%)")
        narrative.append(f"Resistance : Rp {sr_levels['resistance']:,.0f} (jarak {sr_levels['distance_to_resistance']:.1f}%)")
        narrative.append(f"Posisi     : {sr_levels['position']}")
        narrative.append("")

        narrative.append("INTERPRETASI:")
        if sr_levels['position'] == 'Dekat Support':
            narrative.append("  Harga berada dekat level support. Ini bisa menjadi area yang menarik")
            narrative.append("  untuk pembelian jika support mampu menahan tekanan jual. Namun,")
            narrative.append("  jika support tembus, waspadai potensi penurunan lebih lanjut.")
        else:
            narrative.append("  Harga berada dekat level resistance. Perhatikan apakah harga mampu")
            narrative.append("  menembus resistance. Jika berhasil breakout dengan volume tinggi,")
            narrative.append("  ini bisa menjadi sinyal bullish. Jika gagal, harga mungkin terkoreksi.")
        narrative.append("")

    # Accumulation Signal
    narrative.append("ANALISIS AKUMULASI/DISTRIBUSI")
    narrative.append("-" * 40)
    narrative.append(f"Sinyal      : {accumulation['signal']}")
    narrative.append(f"Confidence  : {accumulation['confidence']}")
    narrative.append(f"Buy Ratio   : {accumulation.get('ratio', 0):.1f}%")
    narrative.append("")

    narrative.append("INTERPRETASI:")
    if accumulation['signal'] == 'AKUMULASI':
        narrative.append("  Terdeteksi pola AKUMULASI - ada pihak yang secara bertahap mengumpulkan")
        narrative.append("  saham ini. Pola akumulasi biasanya muncul sebelum kenaikan harga, namun")
        narrative.append("  timing tidak bisa diprediksi dengan pasti. Tips: masuk bertahap di zona")
        narrative.append("  entry, jangan all-in, siapkan stop loss di bawah invalidation level.")
    elif accumulation['signal'] == 'DISTRIBUSI':
        narrative.append("  Terdeteksi pola DISTRIBUSI - ada pihak yang menjual saham secara bertahap.")
        narrative.append("  Pola distribusi biasanya mendahului penurunan harga. Pertimbangkan untuk")
        narrative.append("  mengurangi posisi atau menunggu konfirmasi reversal sebelum entry.")
    else:
        narrative.append("  Sinyal NETRAL - tidak ada akumulasi atau distribusi yang signifikan.")
        narrative.append("  Pasar masih wait and see. Tunggu konfirmasi arah sebelum mengambil posisi.")
    narrative.append("")

    # Fundamental Analysis
    if fundamental:
        narrative.append("ANALISIS FUNDAMENTAL")
        narrative.append("-" * 40)

        per = fundamental.get('per')
        pbv = fundamental.get('pbvr') or fundamental.get('pbv')
        roe = fundamental.get('roe')

        if per:
            narrative.append(f"PER (Price to Earning Ratio): {per:.1f}x")
            if per < 10:
                narrative.append("  -> Valuasi MURAH (PER < 10)")
            elif per < 20:
                narrative.append("  -> Valuasi WAJAR (PER 10-20)")
            else:
                narrative.append("  -> Valuasi PREMIUM (PER > 20)")

        if pbv:
            narrative.append(f"PBV (Price to Book Value): {pbv:.1f}x")
            if pbv < 1:
                narrative.append("  -> Harga di bawah nilai buku (undervalued)")
            elif pbv < 3:
                narrative.append("  -> Valuasi wajar")
            else:
                narrative.append("  -> Premium, perlu justifikasi growth")

        if roe:
            narrative.append(f"ROE (Return on Equity): {roe:.1f}%")
            if roe > 15:
                narrative.append("  -> ROE tinggi, perusahaan efisien menggunakan modal")
            elif roe > 10:
                narrative.append("  -> ROE cukup baik")
            else:
                narrative.append("  -> ROE rendah, perlu diperhatikan")
        narrative.append("")

    # Trading Recommendation
    narrative.append("REKOMENDASI & STRATEGI")
    narrative.append("-" * 40)

    # Determine signal
    signal = "WAIT"
    if accumulation['signal'] == 'AKUMULASI' and sr_levels.get('position') == 'Dekat Support':
        signal = "BUY (Entry Bertahap)"
    elif accumulation['signal'] == 'DISTRIBUSI':
        signal = "SELL/AVOID"

    narrative.append(f"Sinyal: {signal}")
    narrative.append("")

    if signal.startswith("BUY"):
        narrative.append("STRATEGI ENTRY:")
        entry_zone = sr_levels['support'] * 1.02  # 2% above support
        narrative.append(f"  - Zona Entry: Rp {entry_zone:,.0f} - Rp {current_price:,.0f}")
        narrative.append(f"  - Support (Stop Loss): Rp {sr_levels['support']:,.0f}")
        narrative.append(f"  - Target 1 (Resistance): Rp {sr_levels['resistance']:,.0f}")
        narrative.append("")
        narrative.append("MONEY MANAGEMENT:")
        narrative.append("  - Risiko maksimal: 2% dari modal")
        narrative.append("  - Entry bertahap: 30% - 30% - 40%")
        narrative.append("  - Cut loss jika close di bawah support")
    elif signal == "SELL/AVOID":
        narrative.append("STRATEGI:")
        narrative.append("  - Hindari pembelian saat ini")
        narrative.append("  - Jika sudah punya posisi, pertimbangkan take profit")
        narrative.append("  - Tunggu konfirmasi reversal untuk entry baru")
    else:
        narrative.append("STRATEGI:")
        narrative.append("  - Observasi dulu, sinyal belum jelas")
        narrative.append("  - Tunggu konfirmasi akumulasi atau breakout")
        narrative.append("  - Siapkan watchlist dan tentukan level entry")

    narrative.append("")
    narrative.append("=" * 70)
    narrative.append("DISCLAIMER")
    narrative.append("=" * 70)
    narrative.append("Analisis ini bersifat edukatif dan bukan rekomendasi investasi.")
    narrative.append("Keputusan investasi sepenuhnya tanggung jawab investor.")
    narrative.append("Selalu lakukan riset mandiri sebelum mengambil keputusan.")
    narrative.append("=" * 70)

    return "\n".join(narrative)

def save_narrative(stock_code: str, output_dir: str = None):
    """Generate and save narrative to file"""
    if output_dir is None:
        output_dir = r"C:\doc Herman\analisa analysis"

    # Create directory if not exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate narrative
    narrative = generate_narrative(stock_code)

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Analisis_{stock_code}_{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(narrative)

    print(f"Analisis berhasil disimpan ke: {filepath}")
    print("\n" + "=" * 50)
    print("PREVIEW ANALISIS:")
    print("=" * 50)
    print(narrative[:2000] + "..." if len(narrative) > 2000 else narrative)

    return filepath

if __name__ == "__main__":
    # Default to BBCA if no argument
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    save_narrative(stock_code.upper())
