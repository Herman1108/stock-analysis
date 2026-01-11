"""
HERMANSTOCK.COM - DATA UPLOADER
================================
Tool untuk upload data Excel ke website www.hermanstock.com

Fitur:
- Upload single file atau batch (semua file)
- Sync ke lokal dan Railway (production) database
- Support daily update (hanya update data baru)

Jalankan: python upload_to_web.py
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
import pandas as pd
from datetime import datetime
import re

# ============================================================
# KONFIGURASI
# ============================================================

EMITEN_FOLDER = r"C:\doc Herman\emiten"

# Database configurations
LOCAL_DB = {
    'host': 'localhost',
    'database': 'stock_analysis',
    'user': 'postgres',
    'password': 'postgres',
    'port': 5432
}

# Railway production database
RAILWAY_DB = {
    'dsn': 'postgresql://postgres:wxGIEGsxfQOZHkLCFYABwzzPPEYNERpS@interchange.proxy.rlwy.net:42590/railway'
}

# Skip files
SKIP_FILES = ['tanggal 1 tahun.xlsx', '9 haji.xlsx']

# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_connection(db_config, name=''):
    """Get database connection"""
    try:
        if 'dsn' in db_config:
            conn = psycopg2.connect(db_config['dsn'], connect_timeout=30)
        else:
            conn = psycopg2.connect(**db_config, connect_timeout=30)
        return conn
    except Exception as e:
        print(f"  [ERROR] Cannot connect to {name}: {e}")
        return None

def test_connections():
    """Test both database connections"""
    print("\nTesting database connections...")

    # Test local
    local_conn = get_connection(LOCAL_DB, 'Local')
    if local_conn:
        print("  [OK] Local database connected")
        local_conn.close()
    else:
        print("  [FAIL] Local database")

    # Test Railway
    railway_conn = get_connection(RAILWAY_DB, 'Railway')
    if railway_conn:
        print("  [OK] Railway database connected")
        railway_conn.close()
    else:
        print("  [FAIL] Railway database")

    return local_conn is not None, railway_conn is not None

# ============================================================
# PARSER FUNCTIONS
# ============================================================

def safe_float(val) -> float:
    """Safely convert value to float"""
    if pd.isna(val) or val == '' or val == '-' or str(val).strip() == '-':
        return 0.0
    try:
        return float(str(val).strip().replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def parse_value_string(val_str) -> float:
    """Parse string nilai dengan suffix B/M/K ke numeric"""
    if pd.isna(val_str) or val_str == '' or val_str == '-':
        return 0.0

    val_str = str(val_str).strip().replace(',', '')

    multipliers = {'B': 1e9, 'M': 1e6, 'K': 1e3, 'T': 1e12}
    suffix = val_str[-1].upper() if val_str else ''

    if suffix in multipliers:
        try:
            return float(val_str[:-1]) * multipliers[suffix]
        except ValueError:
            return 0.0
    else:
        try:
            return float(val_str)
        except ValueError:
            return 0.0

def parse_change_string(change_str):
    """Parse string change seperti "-5 (-0.30%)" """
    if pd.isna(change_str) or change_str == '':
        return 0.0, 0.0

    change_str = str(change_str)
    match = re.match(r'([+-]?\d+(?:\.\d+)?)\s*\(([+-]?\d+(?:\.\d+)?)%\)', change_str)
    if match:
        return float(match.group(1)), float(match.group(2))
    try:
        return float(change_str), 0.0
    except:
        return 0.0, 0.0

def read_excel_data(file_path: str):
    """Baca file Excel dan return dataframe untuk broker summary dan price data"""
    print(f"  Reading: {os.path.basename(file_path)}")

    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)

    # ===== PARSE PRICE DATA (Kolom L-X, index 11-23) =====
    price_df = pd.DataFrame()
    if len(df.columns) >= 24:
        price_columns = df.iloc[:, 11:24].copy()
        price_columns.columns = ['date', 'close', 'change', 'value', 'volume', 'freq',
                                'f_buy', 'f_sell', 'n_foreign', 'open', 'high', 'low', 'avg']
        price_df = price_columns[1:].copy()
        price_df = price_df.dropna(subset=['date'])
        price_df = price_df[price_df['date'] != 'Date']

    # ===== PARSE BROKER SUMMARY DATA (Kolom A-H, index 0-7) =====
    broker_data = []
    current_date = None

    month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'jun': 6,
                'jul': 7, 'agu': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12}

    for idx, row in df.iterrows():
        col0 = row[0]
        col4 = row[4] if len(row) > 4 else None

        if pd.notna(col0):
            if isinstance(col0, datetime):
                current_date = col0.date()
                continue

            col0_str = str(col0).strip().lower()

            if col0_str in ['buy', 'buy_val', '']:
                continue

            # Check if date row
            date_match = re.search(r'(\d{1,2})\s*(jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des)', col0_str, re.IGNORECASE)
            if date_match and (len(row) < 2 or pd.isna(row[1])):
                day = int(date_match.group(1))
                month = month_map.get(date_match.group(2).lower(), 12)
                year = datetime.now().year
                if month > datetime.now().month:
                    year -= 1
                current_date = datetime(year, month, day).date()
                continue

            # Data row
            if current_date and col0_str not in ['buy', '-', '']:
                buy_broker = col0_str.upper()
                buy_val = parse_value_string(row[1]) if len(row) > 1 else 0
                buy_lot = parse_value_string(row[2]) if len(row) > 2 else 0
                buy_avg = safe_float(row[3]) if len(row) > 3 else 0

                if buy_broker and buy_broker != '-' and len(buy_broker) <= 4:
                    broker_data.append({
                        'date': current_date,
                        'broker_code': buy_broker,
                        'buy_value': buy_val,
                        'buy_lot': int(buy_lot),
                        'buy_avg': buy_avg,
                        'sell_value': 0,
                        'sell_lot': 0,
                        'sell_avg': 0
                    })

        # Sell side
        if current_date and pd.notna(col4):
            col4_str = str(col4).strip().upper()
            if col4_str not in ['SL', 'SELL', '-', ''] and len(col4_str) <= 4:
                sell_broker = col4_str
                sell_val = parse_value_string(row[5]) if len(row) > 5 else 0
                sell_lot = parse_value_string(row[6]) if len(row) > 6 else 0
                sell_avg = safe_float(row[7]) if len(row) > 7 else 0

                found = False
                for item in broker_data:
                    if item['date'] == current_date and item['broker_code'] == sell_broker:
                        item['sell_value'] = sell_val
                        item['sell_lot'] = int(sell_lot)
                        item['sell_avg'] = sell_avg
                        found = True
                        break

                if not found:
                    broker_data.append({
                        'date': current_date,
                        'broker_code': sell_broker,
                        'buy_value': 0,
                        'buy_lot': 0,
                        'buy_avg': 0,
                        'sell_value': sell_val,
                        'sell_lot': int(sell_lot),
                        'sell_avg': sell_avg
                    })

    broker_df = pd.DataFrame(broker_data)

    return broker_df, price_df

# ============================================================
# IMPORT FUNCTIONS
# ============================================================

def import_to_database(conn, stock_code, broker_df, price_df, db_name=''):
    """Import data ke database"""
    cursor = conn.cursor()

    broker_count = 0
    price_count = 0

    # Import broker data
    if not broker_df.empty:
        insert_broker = """
            INSERT INTO broker_summary
            (stock_code, date, broker_code, buy_value, buy_lot, buy_avg,
             sell_value, sell_lot, sell_avg, net_value, net_lot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (stock_code, date, broker_code) DO UPDATE SET
                buy_value = EXCLUDED.buy_value,
                buy_lot = EXCLUDED.buy_lot,
                buy_avg = EXCLUDED.buy_avg,
                sell_value = EXCLUDED.sell_value,
                sell_lot = EXCLUDED.sell_lot,
                sell_avg = EXCLUDED.sell_avg,
                net_value = EXCLUDED.net_value,
                net_lot = EXCLUDED.net_lot
        """

        batch_data = []
        for _, row in broker_df.iterrows():
            net_value = row['buy_value'] - row['sell_value']
            net_lot = row['buy_lot'] - row['sell_lot']
            batch_data.append((
                stock_code,
                row['date'],
                row['broker_code'],
                row['buy_value'],
                row['buy_lot'],
                row['buy_avg'],
                row['sell_value'],
                row['sell_lot'],
                row['sell_avg'],
                net_value,
                net_lot
            ))

        try:
            execute_batch(cursor, insert_broker, batch_data, page_size=500)
            broker_count = len(batch_data)
        except Exception as e:
            print(f"    [ERROR] Broker import to {db_name}: {e}")

    # Import price data
    if not price_df.empty:
        insert_price = """
            INSERT INTO stock_daily
            (stock_code, date, open_price, high_price, low_price, close_price, avg_price,
             volume, value, frequency, foreign_buy, foreign_sell, net_foreign,
             change_value, change_percent)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (stock_code, date) DO UPDATE SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                avg_price = EXCLUDED.avg_price,
                volume = EXCLUDED.volume,
                value = EXCLUDED.value,
                frequency = EXCLUDED.frequency,
                foreign_buy = EXCLUDED.foreign_buy,
                foreign_sell = EXCLUDED.foreign_sell,
                net_foreign = EXCLUDED.net_foreign,
                change_value = EXCLUDED.change_value,
                change_percent = EXCLUDED.change_percent
        """

        for _, row in price_df.iterrows():
            try:
                if isinstance(row['date'], datetime):
                    date = row['date'].date()
                elif isinstance(row['date'], str):
                    date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                else:
                    date = pd.to_datetime(row['date']).date()

                change_val, change_pct = parse_change_string(row['change'])

                cursor.execute(insert_price, (
                    stock_code,
                    date,
                    float(row['open']) if pd.notna(row['open']) else None,
                    float(row['high']) if pd.notna(row['high']) else None,
                    float(row['low']) if pd.notna(row['low']) else None,
                    float(row['close']) if pd.notna(row['close']) else None,
                    float(row['avg']) if pd.notna(row['avg']) else None,
                    int(parse_value_string(row['volume'])),
                    parse_value_string(row['value']),
                    int(parse_value_string(row['freq'])),
                    parse_value_string(row['f_buy']),
                    parse_value_string(row['f_sell']),
                    parse_value_string(row['n_foreign']),
                    change_val,
                    change_pct
                ))
                price_count += 1
            except Exception as e:
                pass

    conn.commit()
    cursor.close()

    return broker_count, price_count

# ============================================================
# MAIN FUNCTIONS
# ============================================================

def list_excel_files():
    """List all Excel files in emiten folder"""
    files = []
    if os.path.exists(EMITEN_FOLDER):
        for f in os.listdir(EMITEN_FOLDER):
            if f.endswith('.xlsx') and f not in SKIP_FILES and not f.startswith('~'):
                files.append(f)
    return sorted(files)

def upload_single(file_name, upload_local=True, upload_railway=True):
    """Upload single file"""
    file_path = os.path.join(EMITEN_FOLDER, file_name)
    if not os.path.exists(file_path):
        print(f"  [ERROR] File not found: {file_path}")
        return False

    # Extract stock code from filename
    stock_code = os.path.splitext(file_name)[0].upper()
    stock_code = stock_code.replace(' - COPY', '').strip()

    print(f"\n  Processing: {file_name} -> {stock_code}")

    # Read data
    try:
        broker_df, price_df = read_excel_data(file_path)
        print(f"    Found: {len(broker_df)} broker rows, {len(price_df)} price rows")
    except Exception as e:
        print(f"    [ERROR] Reading file: {e}")
        return False

    if broker_df.empty and price_df.empty:
        print(f"    [SKIP] No data found")
        return False

    # Upload to local
    if upload_local:
        local_conn = get_connection(LOCAL_DB, 'Local')
        if local_conn:
            try:
                b, p = import_to_database(local_conn, stock_code, broker_df, price_df, 'Local')
                print(f"    [LOCAL] {b} broker, {p} price rows")
                local_conn.close()
            except Exception as e:
                print(f"    [ERROR] Local: {e}")

    # Upload to Railway
    if upload_railway:
        railway_conn = get_connection(RAILWAY_DB, 'Railway')
        if railway_conn:
            try:
                b, p = import_to_database(railway_conn, stock_code, broker_df, price_df, 'Railway')
                print(f"    [RAILWAY] {b} broker, {p} price rows")
                railway_conn.close()
            except Exception as e:
                print(f"    [ERROR] Railway: {e}")

    return True

def upload_all():
    """Upload all files"""
    files = list_excel_files()
    print(f"\nFound {len(files)} Excel files to upload:")
    for f in files:
        print(f"  - {f}")

    confirm = input("\nUpload all files? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    success = 0
    failed = 0

    for file_name in files:
        if upload_single(file_name):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Upload completed!")
    print(f"  Success: {success}, Failed: {failed}")
    print(f"{'='*60}")

def main():
    print("=" * 60)
    print("  HERMANSTOCK.COM - DATA UPLOADER")
    print("=" * 60)

    # Test connections
    local_ok, railway_ok = test_connections()

    if not local_ok and not railway_ok:
        print("\n[ERROR] No database connection available!")
        return

    # List files
    files = list_excel_files()

    if not files:
        print(f"\n[ERROR] No Excel files found in {EMITEN_FOLDER}")
        return

    print(f"\nAvailable files ({len(files)}):")
    for i, f in enumerate(files, 1):
        print(f"  {i}. {f}")

    print(f"\n  A. Upload ALL files")
    print(f"  Q. Quit")

    choice = input("\nPilih nomor file atau A untuk semua: ").strip().upper()

    if choice == 'Q':
        return
    elif choice == 'A':
        upload_all()
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                upload_single(files[idx], upload_local=local_ok, upload_railway=railway_ok)
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid choice")

    print("\nDone!")

if __name__ == "__main__":
    main()
