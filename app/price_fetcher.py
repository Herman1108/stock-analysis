"""
Fetch historical price data from Yahoo Finance
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from database import get_cursor

def fetch_yahoo_finance(stock_code: str = 'CDIA', period: str = '6mo') -> pd.DataFrame:
    """
    Fetch data harga dari Yahoo Finance
    """
    # Format ticker untuk Indonesia: CDIA.JK
    ticker = f"{stock_code}.JK"
    print(f"Fetching data for {ticker}...")

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)

        if df.empty:
            print(f"No data found for {ticker}")
            return pd.DataFrame()

        df = df.reset_index()
        print(f"Found {len(df)} records from Yahoo Finance")
        return df
    except Exception as e:
        print(f"Error fetching Yahoo Finance data: {e}")
        return pd.DataFrame()

def import_yahoo_data(stock_code: str = 'CDIA', period: str = '6mo'):
    """
    Import data dari Yahoo Finance ke database
    Hanya insert data yang belum ada
    """
    df = fetch_yahoo_finance(stock_code, period)

    if df.empty:
        return 0

    insert_query = """
        INSERT INTO stock_daily
        (stock_code, date, open_price, high_price, low_price, close_price, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (stock_code, date) DO NOTHING
    """

    records_imported = 0
    with get_cursor() as cursor:
        for _, row in df.iterrows():
            try:
                date = row['Date'].date() if hasattr(row['Date'], 'date') else row['Date']

                cursor.execute(insert_query, (
                    stock_code,
                    date,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                ))
                records_imported += 1
            except Exception as e:
                pass  # Skip duplicates silently

    print(f"Imported {records_imported} new price records from Yahoo Finance")
    return records_imported

if __name__ == "__main__":
    import_yahoo_data('CDIA', '6mo')
