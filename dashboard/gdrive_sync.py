# -*- coding: utf-8 -*-
"""
Google Drive Sync Module
Sync data dari Google Drive ke database PostgreSQL

Supports two credential methods:
1. Environment Variable: GOOGLE_CREDENTIALS_JSON (JSON content as string)
2. File: google_credentials.json in dashboard folder
"""

import os
import sys
import io
import json
import tempfile
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Add app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("Warning: Google API libraries not installed. Run: pip install google-api-python-client google-auth")

# Import parser functions
try:
    from parser import (
        read_excel_data, import_price_data, import_broker_data,
        read_profile_data, import_profile_data,
        read_fundamental_data, import_fundamental_data,
        read_ipo_position_data, import_ipo_position
    )
    PARSER_AVAILABLE = True
except ImportError as e:
    PARSER_AVAILABLE = False
    print(f"Warning: Could not import parser: {e}")


# Google Drive folder ID (from URL)
# URL: https://drive.google.com/drive/folders/1vV0mSOZRxwK3L0NrzgwzZsghK4s0AiIQ
GDRIVE_FOLDER_ID = "1vV0mSOZRxwK3L0NrzgwzZsghK4s0AiIQ"

# Credentials can be provided via:
# 1. GOOGLE_CREDENTIALS_JSON env var (JSON content as string) - for Railway/cloud
# 2. GOOGLE_CREDENTIALS_PATH env var (path to JSON file)
# 3. Default file: dashboard/google_credentials.json
CREDENTIALS_JSON_ENV = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
CREDENTIALS_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH',
                                   os.path.join(os.path.dirname(__file__), 'google_credentials.json'))

# All tracked stocks
ALL_STOCKS = ['ADMR', 'BBCA', 'BMRI', 'BREN', 'BRPT', 'CBDK', 'CBRE', 'CDIA',
              'CUAN', 'DSNG', 'FUTR', 'HRUM', 'MBMA', 'MDKA', 'NCKL', 'PANI',
              'PTRO', 'TINS', 'WIFI']


class GDriveSyncResult:
    """Result object for sync operation"""
    def __init__(self):
        self.success = False
        self.stocks_processed = []
        self.errors = []
        self.logs = []
        self.stats = {
            'price_records': 0,
            'broker_records': 0,
            'fundamental_records': 0,
            'profile_records': 0,
            'ipo_records': 0
        }

    def add_log(self, message: str, level: str = 'info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.logs.append({
            'time': timestamp,
            'level': level,
            'message': message
        })
        print(f"[{timestamp}] [{level.upper()}] {message}")

    def add_error(self, stock: str, error: str):
        self.errors.append({'stock': stock, 'error': error})
        self.add_log(f"{stock}: {error}", 'error')


def get_credentials_info() -> Dict:
    """Check which credentials method is available"""
    info = {
        'method': None,
        'available': False,
        'details': ''
    }

    # Check env var first (priority for cloud deployment)
    if CREDENTIALS_JSON_ENV:
        try:
            json.loads(CREDENTIALS_JSON_ENV)
            info['method'] = 'env_var'
            info['available'] = True
            info['details'] = 'GOOGLE_CREDENTIALS_JSON environment variable'
            return info
        except json.JSONDecodeError:
            info['details'] = 'GOOGLE_CREDENTIALS_JSON is set but invalid JSON'

    # Check file
    if os.path.exists(CREDENTIALS_PATH):
        info['method'] = 'file'
        info['available'] = True
        info['details'] = f'File: {CREDENTIALS_PATH}'
        return info

    info['details'] = 'No credentials found (env var or file)'
    return info


def get_gdrive_service():
    """Initialize Google Drive API service"""
    if not GOOGLE_API_AVAILABLE:
        raise Exception("Google API libraries not installed. Run: pip install google-api-python-client google-auth")

    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    # Try environment variable first (for Railway/cloud deployment)
    if CREDENTIALS_JSON_ENV:
        try:
            creds_dict = json.loads(CREDENTIALS_JSON_ENV)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
            print("Using credentials from GOOGLE_CREDENTIALS_JSON environment variable")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in GOOGLE_CREDENTIALS_JSON: {e}")
    # Fall back to file
    elif os.path.exists(CREDENTIALS_PATH):
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        print(f"Using credentials from file: {CREDENTIALS_PATH}")
    else:
        raise Exception(
            "Google credentials not found!\n"
            "Please provide credentials via one of:\n"
            "1. GOOGLE_CREDENTIALS_JSON env var (JSON content)\n"
            f"2. File: {CREDENTIALS_PATH}"
        )

    service = build('drive', 'v3', credentials=credentials)
    return service


def list_files_in_folder(service, folder_id: str = GDRIVE_FOLDER_ID) -> List[Dict]:
    """List all Excel files in the Google Drive folder"""
    query = f"'{folder_id}' in parents and (mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mimeType='application/vnd.ms-excel')"

    results = service.files().list(
        q=query,
        pageSize=100,
        fields="files(id, name, modifiedTime, size)"
    ).execute()

    files = results.get('files', [])
    return files


def download_file(service, file_id: str, file_name: str, temp_dir: str) -> str:
    """Download a file from Google Drive to temp directory"""
    request = service.files().get_media(fileId=file_id)

    file_path = os.path.join(temp_dir, file_name)

    with io.FileIO(file_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    return file_path


def get_stock_code_from_filename(filename: str) -> Optional[str]:
    """Extract stock code from filename like 'ADMR.xlsx' or 'fundamental_ADMR.xlsx'"""
    name = filename.upper().replace('.XLSX', '').replace('.XLS', '')

    # Check for fundamental file format
    if name.startswith('FUNDAMENTAL_'):
        code = name.replace('FUNDAMENTAL_', '')
        if code in ALL_STOCKS:
            return code

    # Check for direct stock code
    if name in ALL_STOCKS:
        return name

    # Try to find stock code in filename
    for stock in ALL_STOCKS:
        if stock in name:
            return stock

    return None


def sync_stock_data(
    stocks: List[str] = None,
    data_types: List[str] = None,
    folder_id: str = GDRIVE_FOLDER_ID
) -> GDriveSyncResult:
    """
    Sync data from Google Drive for specified stocks

    Args:
        stocks: List of stock codes to sync, or None for all
        data_types: List of data types ('price', 'broker', 'fundamental'), or None for all
        folder_id: Google Drive folder ID

    Returns:
        GDriveSyncResult object with sync status and logs
    """
    result = GDriveSyncResult()

    # Validate inputs
    if not stocks:
        stocks = ALL_STOCKS
    else:
        stocks = [s.upper() for s in stocks if s and s != 'ALL']
        if not stocks:
            stocks = ALL_STOCKS

    if not data_types:
        data_types = ['price', 'broker', 'fundamental']

    result.add_log(f"Starting sync for {len(stocks)} stocks: {', '.join(stocks)}")
    result.add_log(f"Data types: {', '.join(data_types)}")

    # Check dependencies
    if not GOOGLE_API_AVAILABLE:
        result.add_error('SYSTEM', 'Google API libraries not installed')
        return result

    if not PARSER_AVAILABLE:
        result.add_error('SYSTEM', 'Parser module not available')
        return result

    # Initialize Google Drive service
    try:
        service = get_gdrive_service()
        result.add_log("Google Drive API connected successfully")
    except Exception as e:
        result.add_error('SYSTEM', f"Failed to connect to Google Drive: {str(e)}")
        return result

    # List files in folder
    try:
        files = list_files_in_folder(service, folder_id)
        result.add_log(f"Found {len(files)} Excel files in Google Drive folder")
    except Exception as e:
        result.add_error('SYSTEM', f"Failed to list files: {str(e)}")
        return result

    # Create mapping of stock code to file info
    stock_files = {}
    for f in files:
        stock_code = get_stock_code_from_filename(f['name'])
        if stock_code:
            if stock_code not in stock_files:
                stock_files[stock_code] = []
            stock_files[stock_code].append(f)

    # Create temp directory for downloads
    with tempfile.TemporaryDirectory() as temp_dir:
        result.add_log(f"Using temp directory: {temp_dir}")

        # Process each stock
        for stock in stocks:
            if stock not in stock_files:
                result.add_log(f"{stock}: No files found in Google Drive", 'warning')
                continue

            result.add_log(f"{stock}: Processing...")

            try:
                # Download and process each file for this stock
                for file_info in stock_files[stock]:
                    filename = file_info['name']

                    # Download file
                    result.add_log(f"{stock}: Downloading {filename}...")
                    file_path = download_file(service, file_info['id'], filename, temp_dir)

                    # Determine file type
                    is_fundamental = 'fundamental' in filename.lower()

                    if is_fundamental and 'fundamental' in data_types:
                        # Process fundamental data
                        result.add_log(f"{stock}: Parsing fundamental data...")
                        fund_data = read_fundamental_data(file_path)
                        if fund_data:
                            count = import_fundamental_data(fund_data, stock)
                            result.stats['fundamental_records'] += count
                            result.add_log(f"{stock}: Imported {count} fundamental record")

                    elif not is_fundamental:
                        # Process price and broker data
                        if 'price' in data_types or 'broker' in data_types:
                            result.add_log(f"{stock}: Parsing Excel data...")
                            broker_df, price_df = read_excel_data(file_path)

                            if 'price' in data_types and len(price_df) > 0:
                                count = import_price_data(price_df, stock)
                                result.stats['price_records'] += count
                                result.add_log(f"{stock}: Imported {count} price records")

                            if 'broker' in data_types and len(broker_df) > 0:
                                count = import_broker_data(broker_df, stock)
                                result.stats['broker_records'] += count
                                result.add_log(f"{stock}: Imported {count} broker records")

                            # Try IPO position (optional, don't fail if error)
                            try:
                                ipo_df, period_str = read_ipo_position_data(file_path)
                                if not ipo_df.empty:
                                    count = import_ipo_position(ipo_df, stock, period_str)
                                    result.stats['ipo_records'] += count
                                    result.add_log(f"{stock}: Imported {count} IPO position records")
                            except Exception as e:
                                result.add_log(f"{stock}: IPO position skipped ({str(e)[:50]})", 'warning')

                            # Try profile data (optional, don't fail if error)
                            try:
                                profile_data = read_profile_data(file_path)
                                if profile_data:
                                    count = import_profile_data(profile_data, stock)
                                    result.stats['profile_records'] += count
                                    result.add_log(f"{stock}: Imported profile data")
                            except Exception as e:
                                result.add_log(f"{stock}: Profile skipped ({str(e)[:50]})", 'warning')

                result.stocks_processed.append(stock)
                result.add_log(f"{stock}: Completed successfully", 'success')

            except Exception as e:
                result.add_error(stock, str(e))

    # Summary
    result.success = len(result.stocks_processed) > 0
    result.add_log(f"Sync completed: {len(result.stocks_processed)}/{len(stocks)} stocks processed")
    result.add_log(f"Stats: {result.stats['price_records']} price, {result.stats['broker_records']} broker, "
                  f"{result.stats['fundamental_records']} fundamental records")

    return result


def check_setup_status() -> Dict:
    """Check if Google Drive sync is properly configured"""
    creds_info = get_credentials_info()

    status = {
        'google_api_installed': GOOGLE_API_AVAILABLE,
        'parser_available': PARSER_AVAILABLE,
        'credentials_available': creds_info['available'],
        'credentials_method': creds_info['method'],
        'credentials_details': creds_info['details'],
        'folder_id': GDRIVE_FOLDER_ID,
        'ready': False,
        'missing': []
    }

    if not status['google_api_installed']:
        status['missing'].append('Google API libraries (pip install google-api-python-client google-auth)')

    if not status['parser_available']:
        status['missing'].append('Parser module')

    if not status['credentials_available']:
        status['missing'].append('Google credentials (GOOGLE_CREDENTIALS_JSON env var atau file google_credentials.json)')

    status['ready'] = len(status['missing']) == 0

    return status


if __name__ == '__main__':
    print("=" * 60)
    print("GOOGLE DRIVE SYNC - STATUS CHECK")
    print("=" * 60)

    status = check_setup_status()

    print(f"\nGoogle API Installed: {'Yes' if status['google_api_installed'] else 'No'}")
    print(f"Parser Available: {'Yes' if status['parser_available'] else 'No'}")
    print(f"Credentials Available: {'Yes' if status['credentials_available'] else 'No'}")
    print(f"Credentials Method: {status['credentials_method'] or 'None'}")
    print(f"Credentials Details: {status['credentials_details']}")
    print(f"Folder ID: {status['folder_id']}")

    if status['ready']:
        print("\n[OK] Google Drive sync is ready!")

        # Test connection
        print("\nTesting connection...")
        try:
            service = get_gdrive_service()
            files = list_files_in_folder(service)
            print(f"[OK] Connected! Found {len(files)} files in folder:")
            for f in files[:10]:
                print(f"  - {f['name']}")
            if len(files) > 10:
                print(f"  ... and {len(files) - 10} more")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
    else:
        print("\n[!] Setup incomplete. Missing:")
        for item in status['missing']:
            print(f"  - {item}")

        print("\n" + "=" * 60)
        print("SETUP INSTRUCTIONS")
        print("=" * 60)
        print("""
1. Install Google API libraries:
   pip install google-api-python-client google-auth

2. Create Google Cloud Project:
   - Go to https://console.cloud.google.com
   - Create new project or select existing
   - Enable "Google Drive API"

3. Create Service Account:
   - Go to IAM & Admin > Service Accounts
   - Create new service account
   - Download JSON key file

4. Set credentials (choose one):
   OPTION A - Environment Variable (recommended for Railway):
   - Set GOOGLE_CREDENTIALS_JSON with the entire JSON content

   OPTION B - File:
   - Save JSON as 'google_credentials.json' in dashboard folder

5. Share Google Drive folder:
   - Open folder in Google Drive
   - Click Share
   - Add service account email (client_email from JSON)
   - Give "Viewer" access
""")
