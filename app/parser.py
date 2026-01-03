"""
Parser untuk data Excel CDIA
Membaca dan mengimport data broker summary dan harga dari file Excel
"""
import pandas as pd
import re
from datetime import datetime
from typing import Tuple, List, Dict
from database import get_cursor, execute_query

def parse_value_string(val_str) -> float:
    """
    Parse string nilai dengan suffix B/M/K ke numeric
    Contoh: "35.7B" -> 35700000000
    """
    if pd.isna(val_str) or val_str == '' or val_str == '-':
        return 0.0

    val_str = str(val_str).strip().replace(',', '')

    # Cek suffix
    multipliers = {'B': 1e9, 'M': 1e6, 'K': 1e3}
    suffix = val_str[-1].upper()

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

def parse_change_string(change_str) -> Tuple[float, float]:
    """
    Parse string change seperti "-5 (-0.30%)" menjadi (value, percent)
    """
    if pd.isna(change_str) or change_str == '':
        return 0.0, 0.0

    change_str = str(change_str)

    # Pattern: "+25 (1.52%)" atau "-5 (-0.30%)"
    match = re.match(r'([+-]?\d+(?:\.\d+)?)\s*\(([+-]?\d+(?:\.\d+)?)%\)', change_str)
    if match:
        value = float(match.group(1))
        percent = float(match.group(2))
        return value, percent

    # Coba parse sebagai angka saja
    try:
        return float(change_str), 0.0
    except:
        return 0.0, 0.0

def read_excel_data(file_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Baca file Excel dan return dataframe untuk broker summary dan price data
    """
    print(f"Reading Excel file: {file_path}")

    # Baca Excel tanpa header
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)

    # ===== PARSE PRICE DATA (Kolom L-X, index 11-23) =====
    price_columns = df.iloc[:, 11:24].copy()

    # Ambil header dari row pertama
    price_columns.columns = ['date', 'close', 'change', 'value', 'volume', 'freq',
                            'f_buy', 'f_sell', 'n_foreign', 'open', 'high', 'low', 'avg']

    # Skip header row dan filter yang punya data valid
    price_df = price_columns[1:].copy()  # Skip header row
    price_df = price_df.dropna(subset=['date'])
    price_df = price_df[price_df['date'] != 'Date']

    print(f"Found {len(price_df)} price records")

    # ===== PARSE BROKER SUMMARY DATA (Kolom A-H, index 0-7) =====
    broker_data = []
    current_date = None

    for idx, row in df.iterrows():
        col0 = row[0]
        col4 = row[4]

        # Cek apakah ini baris tanggal (format: "30 des" atau datetime)
        if pd.notna(col0):
            # Cek apakah datetime
            if isinstance(col0, datetime):
                current_date = col0.date()
                continue

            col0_str = str(col0).strip().lower()

            # Skip header row
            if col0_str == 'buy' or col0_str == 'buy_val':
                continue

            # Cek apakah tanggal format "30 des" atau similar
            date_patterns = [
                r'(\d{1,2})\s*(jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des)',
                r'(\d{4}-\d{2}-\d{2})'
            ]

            is_date_row = False
            for pattern in date_patterns:
                if re.search(pattern, col0_str, re.IGNORECASE):
                    is_date_row = True
                    break

            if is_date_row and pd.isna(row[1]):
                # Ini baris tanggal separator
                # Parse tanggal
                if isinstance(col0, datetime):
                    current_date = col0.date()
                else:
                    # Parse manual dari string
                    month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'jun': 6,
                                'jul': 7, 'agu': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12}
                    match = re.search(r'(\d{1,2})\s*(jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des)',
                                     col0_str, re.IGNORECASE)
                    if match:
                        day = int(match.group(1))
                        month = month_map.get(match.group(2).lower(), 12)
                        # Asumsi tahun 2025
                        current_date = datetime(2025, month, day).date()
                continue

            # Ini baris data broker (bukan tanggal, bukan header)
            if current_date and col0_str not in ['buy', '-', '']:
                buy_broker = col0_str.upper()
                buy_val = parse_value_string(row[1])
                buy_lot = parse_value_string(row[2])
                buy_avg = float(row[3]) if pd.notna(row[3]) else 0

                # Tambahkan data buy
                if buy_broker and buy_broker != '-':
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

        # Process sell side (kolom 4-7)
        if current_date and pd.notna(col4):
            col4_str = str(col4).strip().upper()
            if col4_str not in ['SL', 'SELL', '-', '']:
                sell_broker = col4_str
                sell_val = parse_value_string(row[5])
                sell_lot = parse_value_string(row[6])
                sell_avg = float(row[7]) if pd.notna(row[7]) else 0

                # Cari apakah broker sudah ada untuk tanggal ini
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
    print(f"Found {len(broker_df)} broker records")

    return broker_df, price_df

def import_price_data(price_df: pd.DataFrame, stock_code: str = 'CDIA'):
    """Import data harga ke database"""
    print(f"Importing {len(price_df)} price records...")

    insert_query = """
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

    records_imported = 0
    with get_cursor() as cursor:
        for _, row in price_df.iterrows():
            try:
                # Parse date
                if isinstance(row['date'], datetime):
                    date = row['date'].date()
                elif isinstance(row['date'], str):
                    date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                else:
                    date = pd.to_datetime(row['date']).date()

                # Parse change
                change_val, change_pct = parse_change_string(row['change'])

                cursor.execute(insert_query, (
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
                records_imported += 1
            except Exception as e:
                print(f"Error importing row: {row['date']} - {e}")

    print(f"Imported {records_imported} price records")
    return records_imported

def import_broker_data(broker_df: pd.DataFrame, stock_code: str = 'CDIA'):
    """Import data broker ke database dengan BATCH INSERT (optimized for speed)"""
    from psycopg2.extras import execute_batch

    print(f"Importing {len(broker_df)} broker records (batch mode)...")

    insert_query = """
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

    # Prepare batch data
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

    records_imported = 0
    try:
        with get_cursor() as cursor:
            # Batch insert - much faster than individual inserts
            # page_size=500 means 500 records per batch
            execute_batch(cursor, insert_query, batch_data, page_size=500)
            records_imported = len(batch_data)
            print(f"Batch import successful: {records_imported} records")
    except Exception as e:
        print(f"Batch import error: {e}")
        # Fallback to individual inserts if batch fails
        print("Falling back to individual inserts...")
        with get_cursor() as cursor:
            for data in batch_data:
                try:
                    cursor.execute(insert_query, data)
                    records_imported += 1
                except Exception as inner_e:
                    print(f"Error: {inner_e}")

    print(f"Imported {records_imported} broker records")
    return records_imported

def read_ipo_position_data(file_path: str) -> Tuple[pd.DataFrame, str]:
    """
    Baca data IPO position dari kolom Z-AH (index 25-32)
    Return: (DataFrame dengan posisi IPO per broker, period string)
    """
    print(f"Reading IPO position data from: {file_path}")

    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)

    # Check if IPO columns exist (column 25+)
    if len(df.columns) < 33:
        print("No IPO position data found (columns Z-AH not present)")
        return pd.DataFrame(), ""

    # Get period from row 0, column 25
    period_str = str(df.iloc[0, 25]) if pd.notna(df.iloc[0, 25]) else ""
    print(f"IPO Period: {period_str}")

    # Parse IPO data (starting from row 2, columns 25-32)
    ipo_data = []

    for idx in range(2, len(df)):
        row = df.iloc[idx]

        # Buy side (columns 25-28)
        buy_broker = row[25] if pd.notna(row[25]) else None
        buy_val = parse_value_string(row[26]) if pd.notna(row[26]) else 0
        buy_lot = parse_value_string(row[27]) if pd.notna(row[27]) else 0
        buy_avg = float(row[28]) if pd.notna(row[28]) else 0

        # Sell side (columns 29-32)
        sell_broker = row[29] if pd.notna(row[29]) else None
        sell_val = parse_value_string(row[30]) if pd.notna(row[30]) else 0
        sell_lot = parse_value_string(row[31]) if pd.notna(row[31]) else 0
        sell_avg = float(row[32]) if pd.notna(row[32]) else 0

        # Skip if both sides are empty
        if not buy_broker and not sell_broker:
            continue

        # Add buy record
        if buy_broker and str(buy_broker).strip().upper() not in ['BUY', '-', '', 'NAN']:
            ipo_data.append({
                'broker_code': str(buy_broker).strip().upper(),
                'buy_value': buy_val,
                'buy_lot': int(buy_lot),
                'buy_avg': buy_avg,
                'sell_value': 0,
                'sell_lot': 0,
                'sell_avg': 0
            })

        # Add sell record (will be merged with buy if same broker)
        if sell_broker and str(sell_broker).strip().upper() not in ['SELL', 'SL', '-', '', 'NAN']:
            sell_broker_code = str(sell_broker).strip().upper()
            # Check if broker already exists in buy side
            found = False
            for item in ipo_data:
                if item['broker_code'] == sell_broker_code:
                    item['sell_value'] = sell_val
                    item['sell_lot'] = int(sell_lot)
                    item['sell_avg'] = sell_avg
                    found = True
                    break

            if not found:
                ipo_data.append({
                    'broker_code': sell_broker_code,
                    'buy_value': 0,
                    'buy_lot': 0,
                    'buy_avg': 0,
                    'sell_value': sell_val,
                    'sell_lot': int(sell_lot),
                    'sell_avg': sell_avg
                })

    ipo_df = pd.DataFrame(ipo_data)

    # Aggregate by broker (in case same broker appears multiple times)
    # Note: For IPO data, each broker should only appear once, but we handle duplicates just in case
    if not ipo_df.empty:
        # For weighted average: (sum of value) / (sum of lot)
        # But we'll use the avg from Excel directly since it's already calculated
        ipo_df = ipo_df.groupby('broker_code').agg({
            'buy_value': 'sum',
            'buy_lot': 'sum',
            'buy_avg': 'first',  # Use first value (from Excel directly)
            'sell_value': 'sum',
            'sell_lot': 'sum',
            'sell_avg': 'first'   # Use first value (from Excel directly)
        }).reset_index()

    print(f"Found {len(ipo_df)} broker IPO positions")
    return ipo_df, period_str


def import_ipo_position(ipo_df: pd.DataFrame, stock_code: str, period_str: str = ''):
    """Import data IPO position ke database (REPLACE mode)"""
    from psycopg2.extras import execute_batch

    if ipo_df.empty:
        print("No IPO position data to import")
        return 0

    print(f"Importing {len(ipo_df)} IPO position records for {stock_code}...")

    # Parse period dates
    period_start = None
    period_end = None
    if period_str:
        try:
            # Format: "1/01/2018 - 02/01/2025"
            parts = period_str.split(' - ')
            if len(parts) == 2:
                period_start = datetime.strptime(parts[0].strip(), '%d/%m/%Y').date()
                period_end = datetime.strptime(parts[1].strip(), '%d/%m/%Y').date()
        except:
            pass

    insert_query = """
        INSERT INTO broker_ipo_position
        (stock_code, broker_code, total_buy_value, total_buy_lot, avg_buy_price,
         total_sell_value, total_sell_lot, avg_sell_price, period_start, period_end)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (stock_code, broker_code) DO UPDATE SET
            total_buy_value = EXCLUDED.total_buy_value,
            total_buy_lot = EXCLUDED.total_buy_lot,
            avg_buy_price = EXCLUDED.avg_buy_price,
            total_sell_value = EXCLUDED.total_sell_value,
            total_sell_lot = EXCLUDED.total_sell_lot,
            avg_sell_price = EXCLUDED.avg_sell_price,
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            updated_at = NOW()
    """

    batch_data = []
    for _, row in ipo_df.iterrows():
        batch_data.append((
            stock_code,
            row['broker_code'],
            row['buy_value'],
            row['buy_lot'],
            row['buy_avg'],
            row['sell_value'],
            row['sell_lot'],
            row['sell_avg'],
            period_start,
            period_end
        ))

    records_imported = 0
    try:
        with get_cursor() as cursor:
            execute_batch(cursor, insert_query, batch_data, page_size=100)
            records_imported = len(batch_data)
            print(f"IPO position import successful: {records_imported} records")
    except Exception as e:
        print(f"IPO position import error: {e}")

    return records_imported


def import_excel(file_path: str, stock_code: str = 'CDIA'):
    """Main function untuk import semua data dari Excel"""
    print("=" * 60)
    print(f"Importing data from: {file_path}")
    print(f"Stock code: {stock_code}")
    print("=" * 60)

    # Read Excel
    broker_df, price_df = read_excel_data(file_path)

    # Import price data
    price_count = import_price_data(price_df, stock_code)

    # Import broker data
    broker_count = import_broker_data(broker_df, stock_code)

    # Read and import IPO position data (if exists)
    ipo_df, period_str = read_ipo_position_data(file_path)
    ipo_count = 0
    if not ipo_df.empty:
        ipo_count = import_ipo_position(ipo_df, stock_code, period_str)

    print("=" * 60)
    print(f"Import completed!")
    print(f"Price records: {price_count}")
    print(f"Broker records: {broker_count}")
    print(f"IPO position records: {ipo_count}")
    print("=" * 60)

    return price_count, broker_count, ipo_count

if __name__ == "__main__":
    import sys

    # Default file path
    file_path = r"C:\doc Herman\cdia.xlsx"

    if len(sys.argv) > 1:
        file_path = sys.argv[1]

    import_excel(file_path)
