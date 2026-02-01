"""
Parser untuk data Excel CDIA
Membaca dan mengimport data broker summary dan harga dari file Excel
"""
import pandas as pd
import re
from datetime import datetime
from typing import Tuple, List, Dict
from database import get_cursor, execute_query

def safe_float(val) -> float:
    """
    Safely convert value to float, handling '-', empty, and NaN values
    """
    if pd.isna(val) or val == '' or val == '-' or str(val).strip() == '-':
        return 0.0
    try:
        return float(str(val).strip().replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

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
                buy_avg = safe_float(row[3])

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
                sell_avg = safe_float(row[7])

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
    """Import data harga ke database (replace mode: delete all lalu insert fresh)"""
    print(f"Importing {len(price_df)} price records (replace mode)...")

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
        # Replace mode: hapus semua data price untuk stock ini, lalu insert fresh
        cursor.execute("DELETE FROM stock_daily WHERE stock_code = %s", (stock_code,))
        deleted = cursor.rowcount
        print(f"  Deleted {deleted} old price records for {stock_code}")
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
    """Import data broker ke database (replace mode: delete all lalu insert fresh)"""
    from psycopg2.extras import execute_batch

    print(f"Importing {len(broker_df)} broker records (replace mode)...")

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
            # Replace mode: hapus semua data broker untuk stock ini, lalu insert fresh
            cursor.execute("DELETE FROM broker_summary WHERE stock_code = %s", (stock_code,))
            deleted = cursor.rowcount
            print(f"  Deleted {deleted} old broker records for {stock_code}")

            execute_batch(cursor, insert_query, batch_data, page_size=500)
            records_imported = len(batch_data)
            print(f"Batch import successful: {records_imported} records")
    except Exception as e:
        print(f"Batch import error: {e}")
        print("Falling back to individual inserts...")
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM broker_summary WHERE stock_code = %s", (stock_code,))
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

    # Read and import profile data (if exists)
    profile_data = read_profile_data(file_path)
    profile_count = 0
    if profile_data:
        profile_count = import_profile_data(profile_data, stock_code)

    print("=" * 60)
    print(f"Import completed!")
    print(f"Price records: {price_count}")
    print(f"Broker records: {broker_count}")
    print(f"IPO position records: {ipo_count}")
    print(f"Profile imported: {'Yes' if profile_count > 0 else 'No'}")
    print("=" * 60)

    return price_count, broker_count, ipo_count, profile_count

def read_profile_data(file_path: str) -> Dict:
    """
    Baca data Company Profile dari kolom AI-AJ (index 34-35)
    Return: Dictionary dengan data profile
    """
    import json
    print(f"Reading profile data from: {file_path}")

    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)

    # Check if profile columns exist (column 34+)
    if len(df.columns) < 36:
        print("No profile data found (columns AI-AJ not present)")
        return {}

    # Check if column AI has profile data
    col_ai = df.iloc[:, 34]
    if col_ai.isna().all() or str(col_ai.iloc[0]).strip() != 'COMPANY PROFILE':
        print("No profile data found in column AI")
        return {}

    profile = {}

    # Parse profile data by finding section headers
    current_section = None
    for idx in range(len(df)):
        cell_ai = df.iloc[idx, 34]
        cell_aj = df.iloc[idx, 35] if len(df.columns) > 35 else None

        if pd.isna(cell_ai):
            continue

        cell_ai_str = str(cell_ai).strip()

        # Detect sections
        if cell_ai_str == 'IDENTITAS PERUSAHAAN':
            current_section = 'identity'
            continue
        elif cell_ai_str == 'SEJARAH & PENCATATAN':
            current_section = 'history'
            continue
        elif cell_ai_str == 'LATAR BELAKANG PERUSAHAAN':
            current_section = 'background'
            profile['company_background'] = ''
            continue
        elif cell_ai_str == 'KOMPOSISI PEMEGANG SAHAM':
            current_section = 'shareholders'
            continue
        elif cell_ai_str == 'PERKEMBANGAN JUMLAH INVESTOR':
            current_section = 'investor_history'
            profile['shareholder_history'] = []
            continue
        elif cell_ai_str == 'JAJARAN DIREKSI':
            current_section = 'directors'
            profile['directors'] = []
            continue
        elif cell_ai_str == 'DEWAN KOMISARIS':
            current_section = 'commissioners'
            profile['commissioners'] = []
            continue

        # Parse data based on section
        if current_section == 'identity' and pd.notna(cell_aj):
            cell_aj_str = str(cell_aj).strip()
            if cell_ai_str == 'Nama Emiten':
                profile['company_name'] = cell_aj_str
            elif cell_ai_str == 'Kode Saham':
                profile['stock_code'] = cell_aj_str
            elif cell_ai_str == 'Papan Pencatatan':
                profile['listing_board'] = cell_aj_str
            elif cell_ai_str == 'Sektor Usaha':
                profile['sector'] = cell_aj_str
            elif cell_ai_str == 'Sub Sektor':
                profile['subsector'] = cell_aj_str
            elif cell_ai_str == 'Bidang Industri':
                profile['industry'] = cell_aj_str
            elif cell_ai_str == 'Aktivitas Bisnis':
                profile['business_activity'] = cell_aj_str

        elif current_section == 'history' and pd.notna(cell_aj):
            cell_aj_str = str(cell_aj).strip()
            if cell_ai_str == 'Tanggal Pencatatan':
                try:
                    profile['listing_date'] = datetime.strptime(cell_aj_str, '%d %B %Y').date()
                except:
                    profile['listing_date_str'] = cell_aj_str
            elif cell_ai_str == 'Tanggal Efektif':
                try:
                    profile['effective_date'] = datetime.strptime(cell_aj_str, '%d %B %Y').date()
                except:
                    profile['effective_date_str'] = cell_aj_str
            elif cell_ai_str == 'Nilai Nominal':
                profile['nominal_value'] = parse_value_string(cell_aj_str.replace('Rp', '').strip())
            elif cell_ai_str == 'Harga Penawaran Perdana':
                profile['ipo_price'] = parse_value_string(cell_aj_str.replace('Rp', '').strip())
            elif cell_ai_str == 'Jumlah Saham IPO':
                profile['ipo_shares'] = int(parse_value_string(cell_aj_str.replace('lembar', '').replace('.', '').strip()))
            elif cell_ai_str == 'Dana IPO Terhimpun':
                profile['ipo_amount'] = parse_value_string(cell_aj_str.replace('Rp', '').replace('Miliar', 'B').replace('Triliun', 'T').strip())
            elif cell_ai_str == 'Penjamin Emisi':
                profile['underwriter'] = cell_aj_str
            elif cell_ai_str == 'Biro Administrasi Efek':
                profile['share_registrar'] = cell_aj_str

        elif current_section == 'background':
            # Append background text
            if profile.get('company_background'):
                profile['company_background'] += ' ' + cell_ai_str
            else:
                profile['company_background'] = cell_ai_str

        elif current_section == 'shareholders' and pd.notna(cell_aj):
            cell_aj_str = str(cell_aj).strip()
            if 'Pengendali' in cell_ai_str:
                profile['major_shareholder'] = cell_ai_str.replace('(Pengendali)', '').strip()
                profile['major_shareholder_pct'] = float(cell_aj_str.replace('%', '').replace(',', '.'))
            elif 'Publik' in cell_ai_str:
                profile['public_pct'] = float(cell_aj_str.replace('%', '').replace(',', '.'))
            elif 'Total' in cell_ai_str:
                profile['total_shares'] = int(parse_value_string(cell_aj_str.replace('lembar', '').replace('.', '').strip()))

        elif current_section == 'investor_history' and pd.notna(cell_aj):
            cell_aj_str = str(cell_aj).strip()
            profile['shareholder_history'].append({
                'period': cell_ai_str,
                'count': cell_aj_str
            })

        elif current_section == 'directors' and pd.notna(cell_aj):
            cell_aj_str = str(cell_aj).strip()
            # Only match exact "Presiden Direktur", not "Wakil Presiden Direktur"
            if cell_ai_str == 'Presiden Direktur':
                profile['president_director'] = cell_aj_str
            profile['directors'].append({
                'position': cell_ai_str,
                'name': cell_aj_str
            })

        elif current_section == 'commissioners' and pd.notna(cell_aj):
            cell_aj_str = str(cell_aj).strip()
            # Only match exact "Presiden Komisaris", not "Wakil Presiden Komisaris"
            if cell_ai_str == 'Presiden Komisaris':
                profile['president_commissioner'] = cell_aj_str
            profile['commissioners'].append({
                'position': cell_ai_str,
                'name': cell_aj_str
            })

    print(f"Profile data parsed: {profile.get('stock_code', 'Unknown')}")
    return profile


def import_profile_data(profile: Dict, stock_code: str = None):
    """Import profile data ke database"""
    import json

    if not profile:
        print("No profile data to import")
        return 0

    # Use stock_code from profile or parameter
    code = stock_code or profile.get('stock_code', 'UNKNOWN')
    print(f"Importing profile for {code}...")

    # Convert lists to JSON strings
    directors_json = json.dumps(profile.get('directors', []))
    commissioners_json = json.dumps(profile.get('commissioners', []))
    shareholder_history_json = json.dumps(profile.get('shareholder_history', []))

    insert_query = """
        INSERT INTO stock_profile
        (stock_code, company_name, listing_board, sector, subsector, industry, business_activity,
         listing_date, effective_date, nominal_value, ipo_price, ipo_shares, ipo_amount,
         underwriter, share_registrar, company_background, major_shareholder, major_shareholder_pct,
         public_pct, total_shares, president_director, president_commissioner, directors, commissioners,
         shareholder_history, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (stock_code) DO UPDATE SET
            company_name = EXCLUDED.company_name,
            listing_board = EXCLUDED.listing_board,
            sector = EXCLUDED.sector,
            subsector = EXCLUDED.subsector,
            industry = EXCLUDED.industry,
            business_activity = EXCLUDED.business_activity,
            listing_date = EXCLUDED.listing_date,
            effective_date = EXCLUDED.effective_date,
            nominal_value = EXCLUDED.nominal_value,
            ipo_price = EXCLUDED.ipo_price,
            ipo_shares = EXCLUDED.ipo_shares,
            ipo_amount = EXCLUDED.ipo_amount,
            underwriter = EXCLUDED.underwriter,
            share_registrar = EXCLUDED.share_registrar,
            company_background = EXCLUDED.company_background,
            major_shareholder = EXCLUDED.major_shareholder,
            major_shareholder_pct = EXCLUDED.major_shareholder_pct,
            public_pct = EXCLUDED.public_pct,
            total_shares = EXCLUDED.total_shares,
            president_director = EXCLUDED.president_director,
            president_commissioner = EXCLUDED.president_commissioner,
            directors = EXCLUDED.directors,
            commissioners = EXCLUDED.commissioners,
            shareholder_history = EXCLUDED.shareholder_history,
            updated_at = NOW()
    """

    try:
        with get_cursor() as cursor:
            cursor.execute(insert_query, (
                code,
                profile.get('company_name'),
                profile.get('listing_board'),
                profile.get('sector'),
                profile.get('subsector'),
                profile.get('industry'),
                profile.get('business_activity'),
                profile.get('listing_date'),
                profile.get('effective_date'),
                profile.get('nominal_value'),
                profile.get('ipo_price'),
                profile.get('ipo_shares'),
                profile.get('ipo_amount'),
                profile.get('underwriter'),
                profile.get('share_registrar'),
                profile.get('company_background'),
                profile.get('major_shareholder'),
                profile.get('major_shareholder_pct'),
                profile.get('public_pct'),
                profile.get('total_shares'),
                profile.get('president_director'),
                profile.get('president_commissioner'),
                directors_json,
                commissioners_json,
                shareholder_history_json
            ))
            print(f"Profile imported successfully for {code}")
            return 1
    except Exception as e:
        print(f"Profile import error: {e}")
        return 0


def read_fundamental_data(file_path: str) -> Dict:
    """
    Parse fundamental data dari kolom AL-AM Excel file.
    Menggunakan keyword matching untuk mendukung berbagai format label.
    """
    print(f"Reading fundamental data from: {file_path}")

    try:
        df = pd.read_excel(file_path, sheet_name=0, header=None)
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return {}

    # Check if columns AL-AM exist (index 37-38)
    if df.shape[1] < 39:
        print(f"File only has {df.shape[1]} columns, no fundamental data (need columns AL-AM)")
        return {}

    fund_data = {}
    report_date = None

    # Keyword mapping - maps keywords to database field names
    # Format: 'keyword_in_label': 'database_field'
    keyword_map = {
        # Shares & Market Cap
        ('saham beredar', 'total saham'): 'issued_shares',
        ('kapitalisasi',): 'market_cap',
        ('indeks saham',): 'stock_index',
        # Financial Position
        ('pendapatan usaha', 'total pendapatan'): 'sales',
        ('total aset',): 'assets',
        ('total liabilitas', 'total kewajiban'): 'liability',
        ('total ekuitas',): 'equity',
        ('capex', 'belanja modal'): 'capex',
        ('biaya operasional', 'beban operasional'): 'operating_expense',
        ('arus kas operasional', 'arus kas dari operasi'): 'operating_cashflow',
        ('arus kas bersih',): 'net_cashflow',
        ('laba usaha', 'laba operasi'): 'operating_profit',
        ('laba tahun berjalan', 'laba bersih'): 'net_profit',
        # Per Share Data
        ('dps', 'dividen per saham'): 'dps',
        ('eps', 'laba per saham'): 'eps',
        ('rps', 'pendapatan per saham'): 'rps',
        ('bvps', 'nilai buku per saham'): 'bvps',
        ('cfps', 'arus kas per saham'): 'cfps',
        ('ceps', 'kas setara per saham'): 'ceps',
        ('navs', 'aset bersih per saham'): 'navs',
        # Valuation Metrics
        ('yield dividen', 'imbal hasil dividen'): 'dividend_yield',
        ('(per)', 'harga/laba', 'harga terhadap laba', 'rasio harga/laba'): 'per',
        ('(psr)', 'harga/pendapatan', 'harga terhadap penjualan'): 'psr',
        ('(pbv)', 'harga/nilai buku', 'harga terhadap nilai buku'): 'pbvr',
        ('(pcfr)', 'harga/arus kas', 'harga terhadap arus kas'): 'pcfr',
        # Profitability Ratios
        ('dpr', 'pembayaran dividen'): 'dpr',
        ('gpm', 'laba kotor'): 'gpm',
        ('opm', 'laba usaha', 'marjin laba usaha'): 'opm',
        ('npm', 'laba bersih', 'marjin laba bersih'): 'npm',
        ('ebitm', 'ebit'): 'ebitm',
        ('roe', 'pengembalian ekuitas', 'imbal hasil ekuitas'): 'roe',
        ('roa', 'pengembalian aset', 'imbal hasil aset'): 'roa',
        # Liquidity Ratios
        ('der', 'utang/ekuitas', 'utang terhadap ekuitas'): 'der',
        ('cash ratio', 'rasio kas'): 'cash_ratio',
        ('quick ratio', 'rasio cepat'): 'quick_ratio',
        ('current ratio', 'rasio lancar'): 'current_ratio',
    }

    def parse_money_value(val_str):
        """Parse monetary values like 'Rp 1,74 Triliun' or 'Rp 128,15 Miliar'"""
        if pd.isna(val_str) or val_str in ['', '-', 'NaN']:
            return 0.0

        val_str = str(val_str).strip()

        # Remove 'Rp' prefix
        val_str = val_str.replace('Rp', '').strip()

        # Handle multipliers
        multipliers = {
            'triliun': 1e12, 'trilliun': 1e12, 't': 1e12,
            'miliar': 1e9, 'milyar': 1e9, 'm': 1e6,
            'juta': 1e6,
            'ribu': 1e3, 'k': 1e3
        }

        val_lower = val_str.lower()
        multiplier = 1.0

        for key, mult in multipliers.items():
            if key in val_lower:
                multiplier = mult
                val_str = val_lower.replace(key, '').strip()
                break

        # Clean and parse number
        val_str = val_str.replace('.', '').replace(',', '.').strip()

        try:
            return float(val_str) * multiplier
        except:
            return 0.0

    def parse_shares_value(val_str):
        """Parse shares like '123,28 Miliar lembar'"""
        if pd.isna(val_str) or val_str in ['', '-', 'NaN']:
            return 0

        val_str = str(val_str).lower().replace('lembar', '').strip()
        return int(parse_money_value(val_str))

    def parse_ratio_value(val_str):
        """Parse ratio values like '17,10x' or '45,25%'"""
        if pd.isna(val_str) or val_str in ['', '-', 'NaN']:
            return 0.0

        val_str = str(val_str).strip()

        # Remove 'x' suffix for ratios like PER
        val_str = val_str.replace('x', '').replace('X', '').strip()

        # Check if percentage
        is_percent = '%' in val_str
        val_str = val_str.replace('%', '').strip()

        # Clean number format (Indonesian uses comma as decimal)
        val_str = val_str.replace('.', '').replace(',', '.').strip()

        try:
            value = float(val_str)
            # Convert percentage to decimal for storage
            if is_percent:
                value = value / 100
            return value
        except:
            return 0.0

    def parse_per_share_value(val_str):
        """Parse per-share values like 'Rp 469,38' or 'Rp 55'"""
        if pd.isna(val_str) or val_str in ['', '-', 'NaN']:
            return 0.0

        val_str = str(val_str).replace('Rp', '').strip()
        val_str = val_str.replace('.', '').replace(',', '.').strip()

        try:
            return float(val_str)
        except:
            return 0.0

    def match_keyword(label, keywords):
        """Check if label contains any of the keywords"""
        label_lower = label.lower()
        for keyword in keywords:
            if keyword.lower() in label_lower:
                return True
        return False

    # Parse each row
    for i in range(min(70, len(df))):  # Check first 70 rows
        label = str(df.iloc[i, 37]) if pd.notna(df.iloc[i, 37]) else ''
        value = df.iloc[i, 38] if pd.notna(df.iloc[i, 38]) else ''

        if not label or label == 'nan':
            continue

        label_lower = label.lower()

        # Extract report date
        if 'per ' in label_lower and ('september' in label_lower or 'desember' in label_lower or
                                       'maret' in label_lower or 'juni' in label_lower or
                                       '2024' in label_lower or '2025' in label_lower):
            # Try to parse date like "Per 30 September 2025"
            try:
                date_match = re.search(r'(\d{1,2})\s*(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s*(\d{4})', label_lower)
                if date_match:
                    day = int(date_match.group(1))
                    month_name = date_match.group(2)
                    year = int(date_match.group(3))
                    month_map = {'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
                                'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12}
                    month = month_map.get(month_name, 1)
                    report_date = datetime(year, month, day).date()
                    fund_data['report_date'] = report_date
                    print(f"  Found report date: {report_date}")
            except Exception as e:
                pass
            continue

        # Match against keyword map
        for keywords, field in keyword_map.items():
            if match_keyword(label, keywords):
                # Skip if already set (avoid overwriting with wrong value)
                if field in fund_data:
                    continue

                # Parse value based on field type
                if field == 'issued_shares':
                    fund_data[field] = parse_shares_value(value)
                elif field in ['market_cap', 'sales', 'assets', 'liability', 'equity', 'capex',
                              'operating_expense', 'operating_cashflow', 'net_cashflow',
                              'operating_profit', 'net_profit']:
                    fund_data[field] = parse_money_value(value)
                elif field in ['dps', 'eps', 'rps', 'bvps', 'cfps', 'ceps', 'navs']:
                    fund_data[field] = parse_per_share_value(value)
                elif field == 'stock_index':
                    try:
                        fund_data[field] = float(str(value).replace('.', '').replace(',', '.'))
                    except:
                        fund_data[field] = 0.0
                else:
                    # Ratio values (percentages and multipliers)
                    fund_data[field] = parse_ratio_value(value)

                print(f"  {field}: {fund_data[field]} (from '{label}' = '{value}')")
                break

    if fund_data:
        print(f"Parsed {len(fund_data)} fundamental fields")
    else:
        print("No fundamental data found in file")

    return fund_data


def import_fundamental_data(fund_data: Dict, stock_code: str) -> int:
    """Import fundamental data ke database"""
    if not fund_data:
        print("No fundamental data to import")
        return 0

    print(f"Importing fundamental data for {stock_code}...")

    # Set default report date if not found
    if 'report_date' not in fund_data:
        fund_data['report_date'] = datetime.now().date()

    insert_query = """
        INSERT INTO stock_fundamental
        (stock_code, report_date, issued_shares, market_cap, stock_index,
         sales, assets, liability, equity, capex, operating_expense,
         operating_cashflow, net_cashflow, operating_profit, net_profit,
         dps, eps, rps, bvps, cfps, ceps, navs,
         dividend_yield, per, psr, pbvr, pcfr, dpr,
         gpm, opm, npm, ebitm, roe, roa,
         der, cash_ratio, quick_ratio, current_ratio,
         updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (stock_code, report_date) DO UPDATE SET
            issued_shares = EXCLUDED.issued_shares,
            market_cap = EXCLUDED.market_cap,
            stock_index = EXCLUDED.stock_index,
            sales = EXCLUDED.sales,
            assets = EXCLUDED.assets,
            liability = EXCLUDED.liability,
            equity = EXCLUDED.equity,
            capex = EXCLUDED.capex,
            operating_expense = EXCLUDED.operating_expense,
            operating_cashflow = EXCLUDED.operating_cashflow,
            net_cashflow = EXCLUDED.net_cashflow,
            operating_profit = EXCLUDED.operating_profit,
            net_profit = EXCLUDED.net_profit,
            dps = EXCLUDED.dps,
            eps = EXCLUDED.eps,
            rps = EXCLUDED.rps,
            bvps = EXCLUDED.bvps,
            cfps = EXCLUDED.cfps,
            ceps = EXCLUDED.ceps,
            navs = EXCLUDED.navs,
            dividend_yield = EXCLUDED.dividend_yield,
            per = EXCLUDED.per,
            psr = EXCLUDED.psr,
            pbvr = EXCLUDED.pbvr,
            pcfr = EXCLUDED.pcfr,
            dpr = EXCLUDED.dpr,
            gpm = EXCLUDED.gpm,
            opm = EXCLUDED.opm,
            npm = EXCLUDED.npm,
            ebitm = EXCLUDED.ebitm,
            roe = EXCLUDED.roe,
            roa = EXCLUDED.roa,
            der = EXCLUDED.der,
            cash_ratio = EXCLUDED.cash_ratio,
            quick_ratio = EXCLUDED.quick_ratio,
            current_ratio = EXCLUDED.current_ratio,
            updated_at = NOW()
    """

    try:
        with get_cursor() as cursor:
            cursor.execute(insert_query, (
                stock_code,
                fund_data.get('report_date'),
                fund_data.get('issued_shares', 0),
                fund_data.get('market_cap', 0),
                fund_data.get('stock_index', 0),
                fund_data.get('sales', 0),
                fund_data.get('assets', 0),
                fund_data.get('liability', 0),
                fund_data.get('equity', 0),
                fund_data.get('capex', 0),
                fund_data.get('operating_expense', 0),
                fund_data.get('operating_cashflow', 0),
                fund_data.get('net_cashflow', 0),
                fund_data.get('operating_profit', 0),
                fund_data.get('net_profit', 0),
                fund_data.get('dps', 0),
                fund_data.get('eps', 0),
                fund_data.get('rps', 0),
                fund_data.get('bvps', 0),
                fund_data.get('cfps', 0),
                fund_data.get('ceps', 0),
                fund_data.get('navs', 0),
                fund_data.get('dividend_yield', 0),
                fund_data.get('per', 0),
                fund_data.get('psr', 0),
                fund_data.get('pbvr', 0),
                fund_data.get('pcfr', 0),
                fund_data.get('dpr', 0),
                fund_data.get('gpm', 0),
                fund_data.get('opm', 0),
                fund_data.get('npm', 0),
                fund_data.get('ebitm', 0),
                fund_data.get('roe', 0),
                fund_data.get('roa', 0),
                fund_data.get('der', 0),
                fund_data.get('cash_ratio', 0),
                fund_data.get('quick_ratio', 0),
                fund_data.get('current_ratio', 0),
            ))
            print(f"Fundamental data imported successfully for {stock_code}")
            return 1
    except Exception as e:
        print(f"Fundamental import error: {e}")
        return 0


if __name__ == "__main__":
    import sys

    # Default file path
    file_path = r"C:\doc Herman\cdia.xlsx"

    if len(sys.argv) > 1:
        file_path = sys.argv[1]

    import_excel(file_path)
