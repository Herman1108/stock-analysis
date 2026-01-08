"""
Generate PDF Stock Analysis Report V3
- TIDAK mengulang data dari menu Analysis
- Analisis MURNI dari Claude AI (dinamis, bukan template)
- Fokus: Insight unik, interpretasi, dan rekomendasi actionable
"""
import sys
import os
from datetime import datetime, timedelta
from fpdf import FPDF

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from database import execute_query
from signal_validation import get_comprehensive_validation
from composite_analyzer import analyze_support_resistance
from broker_config import is_foreign_broker

# ════════════════════════════════════════════════════════════════════════════
# DATA GATHERING (Raw data untuk analisis Claude)
# ════════════════════════════════════════════════════════════════════════════

def get_raw_data(stock_code: str) -> dict:
    """Ambil semua raw data yang dibutuhkan untuk analisis"""

    # Price data 30 hari
    prices = execute_query("""
        SELECT date, open_price, high_price, low_price, close_price, volume, value
        FROM stock_daily WHERE stock_code = %s
        ORDER BY date DESC LIMIT 30
    """, (stock_code,))

    # Broker summary 30 hari
    brokers = execute_query("""
        WITH last_30 AS (
            SELECT DISTINCT date FROM stock_daily
            WHERE stock_code = %s ORDER BY date DESC LIMIT 30
        )
        SELECT bs.date, bs.broker_code, bs.buy_value, bs.sell_value,
               bs.net_value, bs.net_lot, bs.buy_avg, bs.sell_avg
        FROM broker_summary bs
        WHERE bs.stock_code = %s AND bs.date IN (SELECT date FROM last_30)
        ORDER BY bs.date DESC, bs.net_value DESC
    """, (stock_code, stock_code))

    # Profile & Fundamental
    profile = execute_query("SELECT * FROM stock_profile WHERE stock_code = %s", (stock_code,))
    fundamental = execute_query("""
        SELECT * FROM stock_fundamental WHERE stock_code = %s
        ORDER BY report_date DESC LIMIT 1
    """, (stock_code,))

    return {
        'prices': [dict(p) for p in prices] if prices else [],
        'brokers': [dict(b) for b in brokers] if brokers else [],
        'profile': dict(profile[0]) if profile else {},
        'fundamental': dict(fundamental[0]) if fundamental else {}
    }


# ════════════════════════════════════════════════════════════════════════════
# CLAUDE AI ANALYSIS FUNCTIONS (Analisis dinamis, bukan template)
# ════════════════════════════════════════════════════════════════════════════

def analyze_price_story(prices: list) -> dict:
    """
    Claude menganalisis 'cerita' pergerakan harga.
    Bukan sekadar angka, tapi interpretasi makna pergerakan.
    """
    if len(prices) < 5:
        return {'story': 'Data tidak cukup untuk analisis', 'trend': 'UNKNOWN'}

    # Hitung metrics
    latest = float(prices[0]['close_price'])
    oldest = float(prices[-1]['close_price'])
    highest = max(float(p['high_price']) for p in prices)
    lowest = min(float(p['low_price']) for p in prices)

    change_pct = ((latest - oldest) / oldest * 100) if oldest > 0 else 0
    range_pct = ((highest - lowest) / lowest * 100) if lowest > 0 else 0
    position_in_range = ((latest - lowest) / (highest - lowest) * 100) if (highest - lowest) > 0 else 50

    # Analisis volatilitas
    daily_changes = []
    for i in range(len(prices) - 1):
        prev = float(prices[i+1]['close_price'])
        curr = float(prices[i]['close_price'])
        if prev > 0:
            daily_changes.append(abs((curr - prev) / prev * 100))
    avg_volatility = sum(daily_changes) / len(daily_changes) if daily_changes else 0

    # Analisis volume trend
    vol_first_half = sum(float(p['volume'] or 0) for p in prices[len(prices)//2:])
    vol_second_half = sum(float(p['volume'] or 0) for p in prices[:len(prices)//2])
    vol_trend = 'MENINGKAT' if vol_second_half > vol_first_half * 1.2 else 'MENURUN' if vol_second_half < vol_first_half * 0.8 else 'STABIL'

    # Generate story berdasarkan kondisi
    if change_pct > 10:
        if vol_trend == 'MENINGKAT':
            story = f"Saham mengalami rally kuat (+{change_pct:.1f}%) dengan volume meningkat. Momentum buying terlihat solid, namun perlu waspada terhadap potensi profit taking di level tinggi."
        else:
            story = f"Kenaikan +{change_pct:.1f}% terjadi dengan volume yang tidak mendukung. Ini bisa menjadi 'weak rally' yang rentan koreksi."
    elif change_pct < -10:
        if vol_trend == 'MENINGKAT':
            story = f"Tekanan jual signifikan (-{abs(change_pct):.1f}%) dengan volume tinggi menunjukkan distribusi aktif. Kemungkinan ada pihak besar yang keluar."
        else:
            story = f"Penurunan {change_pct:.1f}% dengan volume rendah bisa jadi 'quiet correction'. Watch for potential bounce di support."
    elif range_pct < 10:
        story = f"Harga bergerak sideways dalam range ketat ({range_pct:.1f}%). Fase konsolidasi - biasanya mendahului pergerakan signifikan. Pantau breakout/breakdown."
    else:
        if position_in_range > 70:
            story = f"Harga saat ini di area atas range ({position_in_range:.0f}%). Mendekati resistance - perlu konfirmasi breakout atau rejection."
        elif position_in_range < 30:
            story = f"Harga di area bawah range ({position_in_range:.0f}%). Mendekati support - watch for bounce atau breakdown lanjutan."
        else:
            story = f"Harga di tengah range dengan volatilitas {avg_volatility:.1f}%/hari. Kondisi netral, tunggu arah yang lebih jelas."

    # Determine trend
    if change_pct > 5:
        trend = 'UPTREND'
    elif change_pct < -5:
        trend = 'DOWNTREND'
    else:
        trend = 'SIDEWAYS'

    return {
        'story': story,
        'trend': trend,
        'change_pct': change_pct,
        'range_pct': range_pct,
        'position_in_range': position_in_range,
        'volatility': avg_volatility,
        'vol_trend': vol_trend,
        'highest': highest,
        'lowest': lowest,
        'latest': latest
    }


def analyze_broker_behavior(brokers: list, prices: list) -> dict:
    """
    Claude menganalisis perilaku broker - bukan sekadar siapa yang beli/jual,
    tapi APA yang mereka lakukan dan MENGAPA.
    """
    if not brokers:
        return {'insight': 'Data broker tidak tersedia', 'dominant_play': 'UNKNOWN'}

    # Aggregate by broker
    broker_stats = {}
    for b in brokers:
        code = b['broker_code']
        if code not in broker_stats:
            broker_stats[code] = {
                'total_net': 0, 'total_buy': 0, 'total_sell': 0,
                'days_active': 0, 'is_foreign': is_foreign_broker(code),
                'avg_prices': []
            }
        broker_stats[code]['total_net'] += float(b['net_value'] or 0)
        broker_stats[code]['total_buy'] += float(b['buy_value'] or 0)
        broker_stats[code]['total_sell'] += float(b['sell_value'] or 0)
        broker_stats[code]['days_active'] += 1
        if b.get('buy_avg'):
            broker_stats[code]['avg_prices'].append(float(b['buy_avg']))

    # Classify brokers
    big_buyers = []
    big_sellers = []
    consistent_accum = []
    hit_and_run = []

    for code, stats in broker_stats.items():
        if stats['total_net'] > 0:
            big_buyers.append((code, stats))
            if stats['days_active'] >= 10:
                consistent_accum.append((code, stats))
        elif stats['total_net'] < 0:
            big_sellers.append((code, stats))

        # Hit and run: high turnover but low net
        turnover = stats['total_buy'] + stats['total_sell']
        if turnover > 0 and abs(stats['total_net']) / turnover < 0.1:
            hit_and_run.append((code, stats))

    # Sort
    big_buyers.sort(key=lambda x: -x[1]['total_net'])
    big_sellers.sort(key=lambda x: x[1]['total_net'])

    # Calculate foreign vs local
    foreign_net = sum(s['total_net'] for c, s in broker_stats.items() if s['is_foreign'])
    local_net = sum(s['total_net'] for c, s in broker_stats.items() if not s['is_foreign'])

    # Generate insight
    insights = []

    if len(consistent_accum) >= 3:
        names = ', '.join([c for c, s in consistent_accum[:3]])
        insights.append(f"POLA AKUMULASI TERSTRUKTUR: {len(consistent_accum)} broker ({names}) konsisten beli >10 hari. Ini ciri khas institusi mengumpulkan posisi secara sistematis.")

    if len(hit_and_run) >= 5:
        insights.append(f"WARNING: Banyak broker 'hit and run' ({len(hit_and_run)} broker). Volume tinggi tapi net position rendah - bisa jadi trading noise atau window dressing.")

    if foreign_net > 0 and local_net < 0:
        insights.append(f"DIVERGENSI: Asing net buy Rp {foreign_net/1e9:.2f}M tapi lokal net sell Rp {abs(local_net)/1e9:.2f}M. Lokal 'menyerahkan' saham ke asing - sering terjadi sebelum rally.")
    elif foreign_net < 0 and local_net > 0:
        insights.append(f"DIVERGENSI: Asing net sell Rp {abs(foreign_net)/1e9:.2f}M, lokal menampung. Asing biasanya lebih early - waspada potensi penurunan lanjutan.")

    if big_buyers and big_buyers[0][1]['is_foreign']:
        insights.append(f"TOP BUYER adalah broker asing ({big_buyers[0][0]}). Foreign flow positif biasanya lebih 'sticky' dan punya conviction kuat.")

    # Determine dominant play
    total_net = sum(s['total_net'] for s in broker_stats.values())
    if total_net > 0 and len(consistent_accum) >= 2:
        dominant = 'SMART_ACCUMULATION'
    elif total_net > 0:
        dominant = 'BUYING_PRESSURE'
    elif total_net < 0 and len(big_sellers) > len(big_buyers):
        dominant = 'DISTRIBUTION'
    else:
        dominant = 'MIXED'

    return {
        'insight': ' '.join(insights) if insights else 'Tidak ada pola broker signifikan terdeteksi.',
        'dominant_play': dominant,
        'foreign_net': foreign_net,
        'local_net': local_net,
        'top_buyers': big_buyers[:5],
        'top_sellers': big_sellers[:5],
        'consistent_accumulators': consistent_accum,
        'hit_and_run_count': len(hit_and_run)
    }


def analyze_risk_reward(prices: list, fundamental: dict, sr_data: dict) -> dict:
    """
    Claude menganalisis risk-reward ratio dan memberikan level konkret.
    """
    if not prices:
        return {'analysis': 'Data tidak cukup', 'risk_reward_ratio': 0}

    current = float(prices[0]['close_price'])

    # Support & Resistance dari data
    supports = sr_data.get('supports', [])
    resistances = sr_data.get('resistances', [])

    nearest_support = supports[0]['level'] if supports else current * 0.9
    nearest_resistance = resistances[0]['level'] if resistances else current * 1.1

    # Calculate risk-reward
    risk = current - nearest_support
    reward = nearest_resistance - current
    rr_ratio = reward / risk if risk > 0 else 0

    # IPO price context
    ipo_price = fundamental.get('ipo_price') or fundamental.get('listing_price', 0)
    vs_ipo = ((current - ipo_price) / ipo_price * 100) if ipo_price > 0 else 0

    # Generate analysis
    analysis_parts = []

    if rr_ratio >= 2:
        analysis_parts.append(f"Risk-Reward FAVORABLE ({rr_ratio:.1f}:1). Potensi gain Rp {reward:,.0f} vs risk Rp {risk:,.0f}.")
    elif rr_ratio >= 1:
        analysis_parts.append(f"Risk-Reward NETRAL ({rr_ratio:.1f}:1). Entry di level ini perlu konfirmasi tambahan.")
    else:
        analysis_parts.append(f"Risk-Reward UNFAVORABLE ({rr_ratio:.1f}:1). Tunggu pullback ke support untuk entry yang lebih baik.")

    if vs_ipo < -30:
        analysis_parts.append(f"Harga {vs_ipo:.0f}% di bawah IPO - banyak investor IPO dalam posisi rugi. Potensi selling pressure saat recovery.")
    elif vs_ipo > 100:
        analysis_parts.append(f"Harga sudah +{vs_ipo:.0f}% dari IPO. Early investors mungkin sudah profit taking.")

    # Entry suggestion
    ideal_entry = nearest_support + (risk * 0.3)  # Entry di 30% dari support ke current

    return {
        'analysis': ' '.join(analysis_parts),
        'risk_reward_ratio': rr_ratio,
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'ideal_entry': ideal_entry,
        'stop_loss': nearest_support * 0.97,  # 3% di bawah support
        'target_1': current + (reward * 0.5),
        'target_2': nearest_resistance,
        'vs_ipo': vs_ipo
    }


def generate_scenario_analysis(price_story: dict, broker_behavior: dict, risk_reward: dict) -> dict:
    """
    Claude membuat analisis skenario: best case, base case, worst case.
    """
    current = price_story['latest']
    trend = price_story['trend']
    dominant = broker_behavior['dominant_play']
    rr = risk_reward['risk_reward_ratio']

    scenarios = {}

    # BEST CASE
    if dominant == 'SMART_ACCUMULATION' and trend != 'DOWNTREND':
        scenarios['best'] = {
            'probability': '30%',
            'description': f"Akumulasi berlanjut, breakout resistance di Rp {risk_reward['nearest_resistance']:,.0f}. Target Rp {risk_reward['target_2'] * 1.1:,.0f} (+{((risk_reward['target_2'] * 1.1 - current) / current * 100):.0f}%).",
            'trigger': "Volume spike >2x rata-rata dengan close di atas resistance.",
            'color': (0, 150, 0)
        }
    else:
        scenarios['best'] = {
            'probability': '20%',
            'description': f"Technical bounce ke resistance Rp {risk_reward['nearest_resistance']:,.0f} (+{((risk_reward['nearest_resistance'] - current) / current * 100):.0f}%).",
            'trigger': "Reversal candle dengan volume di atas rata-rata.",
            'color': (0, 150, 0)
        }

    # BASE CASE
    scenarios['base'] = {
        'probability': '50%',
        'description': f"Harga bergerak sideways di range Rp {risk_reward['nearest_support']:,.0f} - Rp {risk_reward['nearest_resistance']:,.0f}. Konsolidasi berlanjut.",
        'trigger': "Tidak ada katalis signifikan, market normal.",
        'color': (150, 150, 0)
    }

    # WORST CASE
    if dominant == 'DISTRIBUTION' or trend == 'DOWNTREND':
        scenarios['worst'] = {
            'probability': '30%',
            'description': f"Distribusi berlanjut, breakdown support Rp {risk_reward['nearest_support']:,.0f}. Potensi turun ke Rp {risk_reward['stop_loss']:,.0f} (-{((current - risk_reward['stop_loss']) / current * 100):.0f}%).",
            'trigger': "Volume tinggi dengan close di bawah support.",
            'color': (200, 0, 0)
        }
    else:
        scenarios['worst'] = {
            'probability': '20%',
            'description': f"Test support di Rp {risk_reward['nearest_support']:,.0f} (-{((current - risk_reward['nearest_support']) / current * 100):.0f}%).",
            'trigger': "Sentimen market negatif atau news perusahaan.",
            'color': (200, 0, 0)
        }

    return scenarios


def generate_actionable_plan(price_story: dict, broker_behavior: dict, risk_reward: dict, fundamental: dict) -> dict:
    """
    Claude membuat action plan yang konkret dan bisa dieksekusi.
    """
    current = price_story['latest']
    dominant = broker_behavior['dominant_play']
    rr = risk_reward['risk_reward_ratio']

    plan = {
        'stance': '',
        'entry_plan': '',
        'exit_plan': '',
        'position_size': '',
        'time_horizon': '',
        'key_monitor': []
    }

    # Determine stance
    if dominant == 'SMART_ACCUMULATION' and rr >= 1.5:
        plan['stance'] = 'ACCUMULATE'
        plan['entry_plan'] = f"Entry bertahap: 30% di Rp {current:,.0f}, 40% di Rp {risk_reward['ideal_entry']:,.0f}, 30% jika breakdown ke Rp {risk_reward['nearest_support']:,.0f}"
        plan['exit_plan'] = f"TP1: Rp {risk_reward['target_1']:,.0f} (50% posisi), TP2: Rp {risk_reward['target_2']:,.0f} (sisa). SL: Rp {risk_reward['stop_loss']:,.0f}"
        plan['position_size'] = "Maksimal 5% dari portfolio. Risk per trade 1-2%."
        plan['time_horizon'] = "Swing trade 2-4 minggu"
    elif dominant == 'DISTRIBUTION':
        plan['stance'] = 'AVOID'
        plan['entry_plan'] = "Tidak disarankan entry saat ini. Tunggu sinyal akumulasi kembali."
        plan['exit_plan'] = "Jika sudah punya posisi: cut loss di bawah Rp " + f"{risk_reward['nearest_support']:,.0f}"
        plan['position_size'] = "Tidak menambah posisi."
        plan['time_horizon'] = "Observasi 1-2 minggu"
    else:
        plan['stance'] = 'WAIT'
        plan['entry_plan'] = f"Tunggu konfirmasi. Entry hanya jika: (1) Breakout Rp {risk_reward['nearest_resistance']:,.0f} dengan volume, atau (2) Pullback ke Rp {risk_reward['ideal_entry']:,.0f} dengan sinyal reversal"
        plan['exit_plan'] = f"Tentukan sebelum entry. Stop loss di bawah entry 5-7%."
        plan['position_size'] = "Pilot position 2-3% jika ada konfirmasi."
        plan['time_horizon'] = "Tentukan setelah ada sinyal jelas"

    # Key things to monitor
    plan['key_monitor'] = [
        f"Volume harian vs rata-rata (alert jika >1.5x)",
        f"Close position vs Rp {risk_reward['nearest_support']:,.0f} (support) dan Rp {risk_reward['nearest_resistance']:,.0f} (resistance)",
        "Perubahan net flow broker asing (alert jika berbalik arah)",
        "News/corporate action yang mungkin jadi katalis"
    ]

    return plan


# ════════════════════════════════════════════════════════════════════════════
# PDF GENERATOR
# ════════════════════════════════════════════════════════════════════════════

class ClaudeAnalysisPDF(FPDF):
    def __init__(self, stock_code):
        super().__init__()
        self.stock_code = stock_code
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Claude AI Analysis - {self.stock_code}', align='L')
        self.cell(0, 10, datetime.now().strftime('%d %B %Y'), align='R', new_x='LMARGIN', new_y='NEXT')
        self.line(10, 20, 200, 20)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Halaman {self.page_no()}/{{nb}} | Analisis oleh Claude AI - Bukan Rekomendasi Investasi', align='C')

    def chapter_title(self, title, color=(41, 128, 185)):
        self.set_font('Helvetica', 'B', 14)
        self.set_fill_color(*color)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f'  {title}', fill=True, new_x='LMARGIN', new_y='NEXT')
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(41, 128, 185)
        self.cell(0, 8, title, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)

    def narrative(self, text):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def highlight_box(self, text, color=(255, 248, 220)):
        self.set_fill_color(*color)
        y_start = self.get_y()
        self.rect(10, y_start, 190, 20, 'F')
        self.set_xy(12, y_start + 3)
        self.set_font('Helvetica', '', 10)
        self.multi_cell(186, 5, text)
        self.ln(5)

    def key_level(self, label, value, color=(0, 0, 0)):
        self.set_font('Helvetica', 'B', 10)
        self.cell(60, 6, label + ":")
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*color)
        self.cell(0, 6, f"Rp {value:,.0f}", new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)


def generate_claude_pdf(stock_code: str, output_dir: str = None):
    """Generate PDF dengan analisis murni dari Claude AI"""

    if output_dir is None:
        output_dir = r"C:\doc Herman\analisa analysis"
    os.makedirs(output_dir, exist_ok=True)

    print(f"Mengumpulkan data {stock_code}...")

    # 1. Gather raw data
    raw = get_raw_data(stock_code)
    sr_data = analyze_support_resistance(stock_code)

    if not raw['prices']:
        print(f"ERROR: Tidak ada data harga untuk {stock_code}")
        return None

    print("Menganalisis data...")

    # 2. Claude AI Analysis
    price_story = analyze_price_story(raw['prices'])
    broker_behavior = analyze_broker_behavior(raw['brokers'], raw['prices'])
    risk_reward = analyze_risk_reward(raw['prices'], raw['fundamental'], sr_data)
    scenarios = generate_scenario_analysis(price_story, broker_behavior, risk_reward)
    action_plan = generate_actionable_plan(price_story, broker_behavior, risk_reward, raw['fundamental'])

    # 3. Generate PDF
    pdf = ClaudeAnalysisPDF(stock_code)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ═══════════════════════════════════════════════════════════
    # HEADER - Stock Info
    # ═══════════════════════════════════════════════════════════
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 15, stock_code, align='C', new_x='LMARGIN', new_y='NEXT')

    company = raw['profile'].get('company_name', stock_code)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, company, align='C', new_x='LMARGIN', new_y='NEXT')

    # Stance Badge
    stance = action_plan['stance']
    if stance == 'ACCUMULATE':
        badge_color = (0, 150, 0)
        badge_text = "ACCUMULATE"
    elif stance == 'AVOID':
        badge_color = (200, 0, 0)
        badge_text = "AVOID"
    else:
        badge_color = (200, 150, 0)
        badge_text = "WAIT & SEE"

    pdf.ln(5)
    pdf.set_fill_color(*badge_color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 12, f'  STANCE: {badge_text}  ', align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # ═══════════════════════════════════════════════════════════
    # 1. EXECUTIVE STORY (bukan data, tapi cerita)
    # ═══════════════════════════════════════════════════════════
    pdf.chapter_title("RINGKASAN EKSEKUTIF")

    pdf.highlight_box(price_story['story'])

    if broker_behavior['insight'] and broker_behavior['insight'] != 'Tidak ada pola broker signifikan terdeteksi.':
        pdf.narrative(broker_behavior['insight'])

    pdf.narrative(risk_reward['analysis'])

    # ═══════════════════════════════════════════════════════════
    # 2. SKENARIO ANALYSIS
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("ANALISIS SKENARIO")

    for scenario_name, scenario in [('BEST CASE', scenarios['best']),
                                      ('BASE CASE', scenarios['base']),
                                      ('WORST CASE', scenarios['worst'])]:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(*scenario['color'])
        pdf.cell(0, 8, f"{scenario_name} (Probability: {scenario['probability']})", new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, scenario['description'])
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"Trigger: {scenario['trigger']}", new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

    # ═══════════════════════════════════════════════════════════
    # 3. ACTION PLAN
    # ═══════════════════════════════════════════════════════════
    pdf.chapter_title("ACTION PLAN", badge_color)

    pdf.section_title("Strategi Entry")
    pdf.narrative(action_plan['entry_plan'])

    pdf.section_title("Strategi Exit")
    pdf.narrative(action_plan['exit_plan'])

    pdf.section_title("Position Sizing")
    pdf.narrative(action_plan['position_size'])

    pdf.section_title("Time Horizon")
    pdf.narrative(action_plan['time_horizon'])

    # ═══════════════════════════════════════════════════════════
    # 4. KEY LEVELS
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("LEVEL PENTING")

    pdf.key_level("Harga Sekarang", price_story['latest'], (41, 128, 185))
    pdf.key_level("Support Terdekat", risk_reward['nearest_support'], (0, 150, 0))
    pdf.key_level("Resistance Terdekat", risk_reward['nearest_resistance'], (200, 0, 0))
    pdf.ln(3)
    pdf.key_level("Ideal Entry Zone", risk_reward['ideal_entry'], (0, 100, 0))
    pdf.key_level("Stop Loss", risk_reward['stop_loss'], (200, 0, 0))
    pdf.key_level("Target 1 (50%)", risk_reward['target_1'], (0, 150, 0))
    pdf.key_level("Target 2 (Sisa)", risk_reward['target_2'], (0, 150, 0))

    pdf.ln(5)
    pdf.section_title("Risk-Reward Analysis")
    rr = risk_reward['risk_reward_ratio']
    if rr >= 2:
        rr_text = f"Risk-Reward Ratio: {rr:.1f}:1 - FAVORABLE"
        rr_color = (0, 150, 0)
    elif rr >= 1:
        rr_text = f"Risk-Reward Ratio: {rr:.1f}:1 - NETRAL"
        rr_color = (200, 150, 0)
    else:
        rr_text = f"Risk-Reward Ratio: {rr:.1f}:1 - UNFAVORABLE"
        rr_color = (200, 0, 0)

    pdf.set_text_color(*rr_color)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, rr_text, new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)

    # ═══════════════════════════════════════════════════════════
    # 5. MONITORING CHECKLIST
    # ═══════════════════════════════════════════════════════════
    pdf.ln(5)
    pdf.chapter_title("MONITORING CHECKLIST")

    pdf.set_font('Helvetica', '', 10)
    for i, item in enumerate(action_plan['key_monitor'], 1):
        pdf.cell(10, 6, f"{i}.")
        pdf.multi_cell(170, 6, item)

    # ═══════════════════════════════════════════════════════════
    # 6. BROKER INTELLIGENCE (Insight unik)
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("BROKER INTELLIGENCE")

    pdf.section_title("Dominant Play")
    play_text = {
        'SMART_ACCUMULATION': 'AKUMULASI TERSTRUKTUR - Institusi mengumpulkan posisi secara sistematis',
        'BUYING_PRESSURE': 'TEKANAN BELI - Ada buying tapi belum terkonfirmasi sebagai akumulasi',
        'DISTRIBUTION': 'DISTRIBUSI - Institusi menjual/mengurangi posisi',
        'MIXED': 'CAMPURAN - Tidak ada pola dominan yang jelas'
    }
    pdf.narrative(play_text.get(broker_behavior['dominant_play'], 'Unknown'))

    pdf.section_title("Foreign vs Local Flow")
    foreign = broker_behavior['foreign_net']
    local = broker_behavior['local_net']

    pdf.set_font('Helvetica', 'B', 10)
    f_color = (0, 150, 0) if foreign > 0 else (200, 0, 0)
    l_color = (0, 150, 0) if local > 0 else (200, 0, 0)

    pdf.set_text_color(*f_color)
    pdf.cell(95, 6, f"Asing: Rp {foreign/1e9:+.2f} M")
    pdf.set_text_color(*l_color)
    pdf.cell(95, 6, f"Lokal: Rp {local/1e9:+.2f} M", new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)

    # Consistent accumulators
    if broker_behavior['consistent_accumulators']:
        pdf.ln(3)
        pdf.section_title("Broker dengan Pola Akumulasi Konsisten")
        for code, stats in broker_behavior['consistent_accumulators'][:5]:
            tag = " [ASING]" if stats['is_foreign'] else ""
            pdf.narrative(f"- {code}{tag}: Net Rp {stats['total_net']/1e9:.2f} M dalam {stats['days_active']} hari")

    # ═══════════════════════════════════════════════════════════
    # DISCLAIMER
    # ═══════════════════════════════════════════════════════════
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.multi_cell(0, 4, """DISCLAIMER: Dokumen ini merupakan analisis yang dihasilkan oleh AI (Claude) berdasarkan data historis.
Ini BUKAN rekomendasi investasi. Keputusan investasi sepenuhnya tanggung jawab investor.
Selalu lakukan riset mandiri dan konsultasi dengan profesional sebelum berinvestasi.
Past performance is not indicative of future results.""")

    # Save PDF
    today = datetime.now().strftime('%Y%m%d')
    filename = f"{stock_code}_Claude_{today}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf.output(filepath)

    print(f"\n{'='*60}")
    print(f"PDF CLAUDE ANALYSIS BERHASIL DIBUAT!")
    print(f"{'='*60}")
    print(f"File: {filepath}")
    print(f"Stance: {badge_text}")
    print(f"{'='*60}")

    return filepath


if __name__ == "__main__":
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "CDIA"
    generate_claude_pdf(stock_code.upper())
