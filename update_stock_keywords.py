"""Update STOCK_KEYWORDS in news_service.py with all 30 emiten"""

# Complete STOCK_KEYWORDS with all emiten
STOCK_KEYWORDS = '''{
    'BBCA': ['BBCA', 'Bank Central Asia'],
    'BMRI': ['BMRI', 'Bank Mandiri'],
    'BBRI': ['BBRI', 'Bank BRI'],
    'BBNI': ['BBNI', 'Bank BNI'],
    'TLKM': ['TLKM', 'Telkom'],
    'ASII': ['ASII', 'Astra'],
    'UNVR': ['UNVR', 'Unilever Indonesia'],
    'HMSP': ['HMSP', 'Sampoerna'],
    'GGRM': ['GGRM', 'Gudang Garam'],
    'ICBP': ['ICBP', 'Indofood CBP'],
    'INDF': ['INDF', 'Indofood'],
    'KLBF': ['KLBF', 'Kalbe Farma'],
    'PGAS': ['PGAS', 'PGN'],
    'PTBA': ['PTBA', 'Bukit Asam'],
    'ADRO': ['ADRO', 'Adaro'],
    'ANTM': ['ANTM', 'Antam'],
    'INCO': ['INCO', 'Vale Indonesia'],
    'CPIN': ['CPIN', 'Charoen Pokphand'],
    'EXCL': ['EXCL', 'XL Axiata'],
    'ISAT': ['ISAT', 'Indosat'],
    'SMGR': ['SMGR', 'Semen Indonesia'],
    'INTP': ['INTP', 'Indocement'],
    'UNTR': ['UNTR', 'United Tractors'],
    'JSMR': ['JSMR', 'Jasa Marga'],
    'WIKA': ['WIKA', 'Wijaya Karya'],
    'PANI': ['PANI', 'Pantai Indah'],
    'BREN': ['BREN', 'Barito Renewables'],
    'CUAN': ['CUAN', 'Petrindo Jaya'],
    'DSSA': ['DSSA', 'Dian Swastatika'],
    'AMMN': ['AMMN', 'Amman Mineral'],
}'''

# Read news_service.py
with open('dashboard/news_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace STOCK_KEYWORDS
import re
pattern = r"STOCK_KEYWORDS = \{[^}]+\}"
content = re.sub(pattern, f"STOCK_KEYWORDS = {STOCK_KEYWORDS}", content)

with open('dashboard/news_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Also update app/news_service.py
with open('app/news_service.py', 'r', encoding='utf-8') as f:
    content2 = f.read()

content2 = re.sub(pattern, f"STOCK_KEYWORDS = {STOCK_KEYWORDS}", content2)

with open('app/news_service.py', 'w', encoding='utf-8') as f:
    f.write(content2)

print("STOCK_KEYWORDS updated with 30 emiten!")
