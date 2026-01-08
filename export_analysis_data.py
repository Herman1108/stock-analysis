"""
Export All Stock Analysis Data for Claude Code Analysis
Extracts complete data from Dashboard + Analysis pages
"""
import sys
import os
import json
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from database import execute_query
from analyzer import (
    get_price_data, get_broker_data,
    get_top_accumulators, get_top_distributors,
    get_bandarmology_summary
)
from composite_analyzer import (
    get_comprehensive_analysis,
    calculate_price_movements,
    analyze_support_resistance,
    get_multi_period_summary,
    analyze_avg_buy_position
)
from signal_validation import (
    get_comprehensive_validation,
    get_company_profile,
    get_unified_analysis_summary,
    DEFAULT_PARAMS
)

def get_stock_fundamental(stock_code: str) -> dict:
    """Get fundamental data"""
    query = """
        SELECT * FROM stock_fundamental
        WHERE stock_code = %s
        ORDER BY report_date DESC LIMIT 1
    """
    result = execute_query(query, (stock_code,))
    if result:
        data = dict(result[0])
        # Convert Decimal to float
        for k, v in data.items():
            if hasattr(v, '__float__'):
                data[k] = float(v)
        return data
    return {}

def get_stock_profile(stock_code: str) -> dict:
    """Get company profile"""
    query = "SELECT * FROM stock_profile WHERE stock_code = %s"
    result = execute_query(query, (stock_code,))
    if result:
        data = dict(result[0])
        for k, v in data.items():
            if hasattr(v, '__float__'):
                data[k] = float(v)
        return data
    return {}

def get_recent_price_data(stock_code: str, days: int = 30) -> list:
    """Get recent price data"""
    query = """
        SELECT date, open_price, high_price, low_price, close_price, volume, value
        FROM stock_daily
        WHERE stock_code = %s
        ORDER BY date DESC LIMIT %s
    """
    result = execute_query(query, (stock_code, days))
    data = []
    for r in result:
        row = dict(r)
        row['date'] = str(row['date'])
        for k, v in row.items():
            if hasattr(v, '__float__'):
                row[k] = float(v)
        data.append(row)
    return data

def get_broker_flow_summary(stock_code: str, days: int = 30) -> dict:
    """Get broker flow summary"""
    query = """
        SELECT
            broker_code,
            SUM(buy_value) as total_buy,
            SUM(sell_value) as total_sell,
            SUM(net_value) as total_net,
            SUM(net_lot) as total_lot,
            COUNT(*) as trading_days
        FROM broker_summary
        WHERE stock_code = %s AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY broker_code
        ORDER BY total_net DESC
        LIMIT 20
    """
    result = execute_query(query, (stock_code, days))

    top_buyers = []
    top_sellers = []
    for r in result:
        row = {
            'broker': r['broker_code'],
            'net_value': float(r['total_net'] or 0),
            'buy_value': float(r['total_buy'] or 0),
            'sell_value': float(r['total_sell'] or 0),
            'net_lot': float(r['total_lot'] or 0),
            'trading_days': r['trading_days']
        }
        if row['net_value'] > 0:
            top_buyers.append(row)
        else:
            top_sellers.append(row)

    return {
        'top_buyers': top_buyers[:10],
        'top_sellers': sorted(top_sellers, key=lambda x: x['net_value'])[:10]
    }

def format_value(val):
    """Format large numbers"""
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"{val/1e12:.2f}T"
    elif abs(val) >= 1e9:
        return f"{val/1e9:.2f}M"
    elif abs(val) >= 1e6:
        return f"{val/1e6:.2f}Jt"
    else:
        return f"{val:,.0f}"

def export_all_data(stock_code: str) -> dict:
    """Export all analysis data for Claude Code"""

    print(f"Mengambil data {stock_code}...")

    # 1. Company Profile
    profile = get_stock_profile(stock_code)

    # 2. Fundamental Data
    fundamental = get_stock_fundamental(stock_code)

    # 3. Price Data (30 hari)
    price_data = get_recent_price_data(stock_code, 30)
    current_price = price_data[0]['close_price'] if price_data else 0

    # 4. Price Movements (multi-period)
    movements = calculate_price_movements(stock_code)

    # 5. Support & Resistance
    sr_analysis = analyze_support_resistance(stock_code)

    # 6. Broker Flow Summary
    broker_flow = get_broker_flow_summary(stock_code, 30)

    # 7. Comprehensive Analysis (6 components)
    comprehensive = get_comprehensive_analysis(stock_code)

    # 8. Multi-period Summary
    multi_period = get_multi_period_summary(stock_code)

    # 9. Avg Buy Position Analysis
    avg_buy = analyze_avg_buy_position(stock_code, current_price)

    # 10. Validation Summary
    try:
        validation = get_comprehensive_validation(stock_code)
    except:
        validation = {}

    # Compile all data
    all_data = {
        'stock_code': stock_code,
        'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'current_price': current_price,

        # Profile & Fundamental
        'company_profile': profile,
        'fundamental': fundamental,

        # Price Analysis
        'price_movements': movements,
        'support_resistance': sr_analysis,

        # Broker Analysis
        'broker_flow_30d': broker_flow,
        'avg_buy_analysis': avg_buy,

        # Comprehensive Analysis (6 Components)
        'composite_score': comprehensive.get('composite', {}),
        'broker_sensitivity': comprehensive.get('broker_sensitivity', {}),
        'foreign_flow': comprehensive.get('foreign_flow', {}),
        'smart_money': comprehensive.get('smart_money', {}),
        'price_position': comprehensive.get('price_position', {}),
        'accumulation_phase': comprehensive.get('accumulation_phase', {}),
        'volume_analysis': comprehensive.get('volume_analysis', {}),

        # Multi-period
        'multi_period_summary': multi_period,

        # Validation
        'validation': validation,

        # Recent Price Data (5 hari terakhir untuk context)
        'recent_prices': price_data[:5]
    }

    return all_data

def create_analysis_prompt(data: dict) -> str:
    """Create prompt for Claude Code analysis"""

    stock = data['stock_code']
    price = data['current_price']
    composite = data.get('composite_score', {})

    prompt = f"""Analisis mendalam saham {stock} berdasarkan data berikut:

=== DATA SAHAM {stock} ===
Harga Terakhir: Rp {price:,.0f}
Waktu Export: {data['export_time']}

=== PROFIL PERUSAHAAN ===
{json.dumps(data['company_profile'], indent=2, default=str)}

=== DATA FUNDAMENTAL ===
{json.dumps(data['fundamental'], indent=2, default=str)}

=== PERGERAKAN HARGA ===
{json.dumps(data['price_movements'], indent=2, default=str)}

=== SUPPORT & RESISTANCE ===
{json.dumps(data['support_resistance'], indent=2, default=str)}

=== BROKER FLOW (30 Hari) ===
Top Buyers: {json.dumps(data['broker_flow_30d'].get('top_buyers', [])[:5], indent=2, default=str)}
Top Sellers: {json.dumps(data['broker_flow_30d'].get('top_sellers', [])[:5], indent=2, default=str)}

=== COMPOSITE ANALYSIS ===
Composite Score: {composite.get('composite_score', 'N/A')}
Action: {composite.get('action', 'N/A')}
Action Desc: {composite.get('action_desc', 'N/A')}

Components:
{json.dumps(composite.get('components', {}), indent=2, default=str)}

=== BROKER SENSITIVITY ===
{json.dumps(data.get('broker_sensitivity', {}), indent=2, default=str)[:2000]}

=== FOREIGN FLOW ===
{json.dumps(data.get('foreign_flow', {}), indent=2, default=str)}

=== SMART MONEY INDICATOR ===
{json.dumps(data.get('smart_money', {}), indent=2, default=str)}

=== PRICE POSITION ===
{json.dumps(data.get('price_position', {}), indent=2, default=str)}

=== ACCUMULATION PHASE ===
{json.dumps(data.get('accumulation_phase', {}), indent=2, default=str)}

=== VOLUME ANALYSIS ===
{json.dumps(data.get('volume_analysis', {}), indent=2, default=str)}

=== AVG BUY ANALYSIS ===
{json.dumps(data.get('avg_buy_analysis', {}), indent=2, default=str)}

=== HARGA 5 HARI TERAKHIR ===
{json.dumps(data.get('recent_prices', []), indent=2, default=str)}

---

TUGAS: Buatkan analisis naratif yang EDUKATIF dalam Bahasa Indonesia dengan struktur:

1. RINGKASAN EKSEKUTIF (2-3 paragraf)
   - Kondisi saham saat ini
   - Sinyal utama dan rekomendasi

2. ANALISIS TEKNIKAL
   - Interpretasi support/resistance
   - Trend harga multi-periode
   - Volume analysis

3. ANALISIS BROKER FLOW (Bandarmology)
   - Siapa yang akumulasi/distribusi
   - Foreign flow momentum
   - Smart money indicator

4. ANALISIS FUNDAMENTAL
   - Valuasi (PER, PBV, ROE)
   - Perbandingan dengan sektor

5. LEVEL TRADING
   - Zona Entry yang disarankan
   - Stop Loss level
   - Target Price (TP1, TP2)

6. RISIKO & PERINGATAN
   - Faktor risiko yang perlu diperhatikan
   - Warning signals jika ada

7. KESIMPULAN & STRATEGI
   - Action plan yang jelas
   - Money management suggestion

Simpan hasil analisis ke: C:\\doc Herman\\analisa analysis\\Analisis_AI_{stock}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt
"""
    return prompt

def save_for_claude(stock_code: str):
    """Export data and save prompt for Claude Code"""

    # Export all data
    data = export_all_data(stock_code)

    # Save raw data as JSON
    output_dir = r"C:\doc Herman\analisa analysis"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save JSON data
    json_file = os.path.join(output_dir, f"data_{stock_code}_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    # Create prompt file
    prompt = create_analysis_prompt(data)
    prompt_file = os.path.join(output_dir, f"prompt_{stock_code}_{timestamp}.txt")
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    print(f"\n{'='*60}")
    print(f"DATA EXPORTED FOR {stock_code}")
    print(f"{'='*60}")
    print(f"JSON Data : {json_file}")
    print(f"Prompt    : {prompt_file}")
    print(f"{'='*60}")

    return json_file, prompt_file, prompt

if __name__ == "__main__":
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    save_for_claude(stock_code.upper())
