# -*- coding: utf-8 -*-
"""
Save Formula Assignment dan Backtest Results ke Database Localhost
Menggunakan backtest_v11_universal.py (sama dengan dashboard)
"""

import sys
import os
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

import psycopg2
from psycopg2.extras import RealDictCursor
from zones_config import STOCK_ZONES, STOCK_FORMULA, get_formula
from backtest_v11_universal import run_backtest


def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host='localhost',
            database='stock_analysis',
            user='postgres',
            password='postgres'
        )


def create_tables(conn):
    """Create tables for formula assignment and backtest results"""
    cur = conn.cursor()

    # Table for formula assignments
    cur.execute('''
        CREATE TABLE IF NOT EXISTS formula_assignment (
            id SERIAL PRIMARY KEY,
            stock_code VARCHAR(10) NOT NULL,
            formula VARCHAR(20) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code)
        )
    ''')

    # Table for backtest results summary
    cur.execute('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            id SERIAL PRIMARY KEY,
            stock_code VARCHAR(10) NOT NULL,
            formula VARCHAR(20) NOT NULL,
            backtest_date DATE NOT NULL,
            total_trades INTEGER,
            wins INTEGER,
            losses INTEGER,
            open_trades INTEGER,
            win_rate DECIMAL(5,2),
            total_pnl DECIMAL(10,2),
            avg_pnl DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table for individual trade details
    cur.execute('''
        CREATE TABLE IF NOT EXISTS backtest_trades (
            id SERIAL PRIMARY KEY,
            stock_code VARCHAR(10) NOT NULL,
            formula VARCHAR(20) NOT NULL,
            backtest_date DATE NOT NULL,
            trade_type VARCHAR(20),
            zone_num INTEGER,
            entry_date DATE,
            entry_price DECIMAL(12,2),
            exit_date DATE,
            exit_price DECIMAL(12,2),
            sl_price DECIMAL(12,2),
            tp_price DECIMAL(12,2),
            pnl DECIMAL(10,2),
            exit_reason VARCHAR(20),
            vol_ratio DECIMAL(5,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    print("Tables created/verified successfully")


def clear_today_data(conn):
    """Clear today's backtest data to avoid duplicates"""
    cur = conn.cursor()
    today = datetime.now().date()

    cur.execute('DELETE FROM backtest_results WHERE backtest_date = %s', (today,))
    cur.execute('DELETE FROM backtest_trades WHERE backtest_date = %s', (today,))
    conn.commit()
    print(f"Cleared existing data for {today}")


def save_formula_assignments(conn):
    """Save formula assignments to database"""
    cur = conn.cursor()

    for stock, formula in STOCK_FORMULA.items():
        cur.execute('''
            INSERT INTO formula_assignment (stock_code, formula, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (stock_code)
            DO UPDATE SET formula = EXCLUDED.formula, updated_at = EXCLUDED.updated_at
        ''', (stock, formula, datetime.now()))

    conn.commit()
    print(f"Saved {len(STOCK_FORMULA)} formula assignments")


def run_and_save_backtest(conn, stock_code):
    """Run backtest and save results"""
    cur = conn.cursor()
    backtest_date = datetime.now().date()
    formula = get_formula(stock_code)

    # Run backtest using dashboard's backtest function
    result = run_backtest(stock_code, verbose=False)

    if result is None:
        return None

    trades = result.get('trades', [])

    # Calculate stats
    closed = [t for t in trades if t.get('exit_reason') not in ['OPEN', None] and t.get('exit_price', 0) > 0]
    open_trades = len(trades) - len(closed)
    wins = len([t for t in closed if t['pnl'] > 0])
    losses = len(closed) - wins
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = wins / len(closed) * 100 if closed else 0
    avg_pnl = total_pnl / len(trades) if trades else 0

    # Save summary
    cur.execute('''
        INSERT INTO backtest_results
        (stock_code, formula, backtest_date, total_trades, wins, losses, open_trades,
         win_rate, total_pnl, avg_pnl)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        stock_code, formula, backtest_date,
        len(trades), wins, losses, open_trades,
        win_rate, total_pnl, avg_pnl
    ))

    # Save individual trades
    for trade in trades:
        exit_price = trade.get('exit_price', 0)
        if exit_price == 0:
            exit_price = None

        cur.execute('''
            INSERT INTO backtest_trades
            (stock_code, formula, backtest_date, trade_type, zone_num,
             entry_date, entry_price, exit_date, exit_price, sl_price, tp_price,
             pnl, exit_reason, vol_ratio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            stock_code, formula, backtest_date,
            trade['type'], trade['zone_num'],
            trade['entry_date'], trade['entry_price'],
            trade.get('exit_date'), exit_price,
            trade.get('sl'), trade.get('tp'),
            trade['pnl'], trade.get('exit_reason'),
            trade.get('vol_ratio')
        ))

    conn.commit()

    return {
        'stock': stock_code,
        'formula': formula,
        'trades': len(trades),
        'wins': wins,
        'losses': losses,
        'open': open_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl
    }


def main():
    print("=" * 80)
    print("SAVING FORMULA & BACKTEST RESULTS TO LOCALHOST")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        conn = get_db_connection()
        print("Connected to database successfully")
    except Exception as e:
        print(f"Database connection error: {e}")
        return

    # Create tables
    print("\n1. Creating/verifying tables...")
    create_tables(conn)

    # Clear today's data
    print("\n2. Clearing today's existing data...")
    clear_today_data(conn)

    # Save formula assignments
    print("\n3. Saving formula assignments...")
    save_formula_assignments(conn)

    # Run backtests and save results
    print("\n4. Running backtests and saving results...")
    print("-" * 80)

    all_results = []

    # Print header
    print(f"{'Stock':<8} {'Formula':<8} {'Trades':>7} {'W/L':>8} {'Open':>6} {'WR':>8} {'PnL':>10}")
    print("-" * 80)

    for stock in sorted(STOCK_FORMULA.keys()):
        result = run_and_save_backtest(conn, stock)
        if result:
            all_results.append(result)
            wl = f"{result['wins']}/{result['losses']}"
            print(f"{stock:<8} {result['formula']:<8} {result['trades']:>7} {wl:>8} {result['open']:>6} {result['win_rate']:>7.1f}% {result['total_pnl']:>+9.1f}%")
        else:
            print(f"{stock:<8} ERROR")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    v11b1_results = [r for r in all_results if r['formula'] == 'V11b1']
    v11b2_results = [r for r in all_results if r['formula'] == 'V11b2']

    # V11b1 Summary
    if v11b1_results:
        v11b1_trades = sum(r['trades'] for r in v11b1_results)
        v11b1_wins = sum(r['wins'] for r in v11b1_results)
        v11b1_losses = sum(r['losses'] for r in v11b1_results)
        v11b1_pnl = sum(r['total_pnl'] for r in v11b1_results)
        v11b1_wr = v11b1_wins / (v11b1_wins + v11b1_losses) * 100 if (v11b1_wins + v11b1_losses) > 0 else 0

        print(f"\nV11b1 ({len(v11b1_results)} emiten):")
        print(f"  Trades: {v11b1_trades} | Wins: {v11b1_wins} | Losses: {v11b1_losses}")
        print(f"  Win Rate: {v11b1_wr:.1f}% | Total PnL: {v11b1_pnl:+.1f}%")

    # V11b2 Summary
    if v11b2_results:
        v11b2_trades = sum(r['trades'] for r in v11b2_results)
        v11b2_wins = sum(r['wins'] for r in v11b2_results)
        v11b2_losses = sum(r['losses'] for r in v11b2_results)
        v11b2_pnl = sum(r['total_pnl'] for r in v11b2_results)
        v11b2_wr = v11b2_wins / (v11b2_wins + v11b2_losses) * 100 if (v11b2_wins + v11b2_losses) > 0 else 0

        print(f"\nV11b2 ({len(v11b2_results)} emiten):")
        print(f"  Trades: {v11b2_trades} | Wins: {v11b2_wins} | Losses: {v11b2_losses}")
        print(f"  Win Rate: {v11b2_wr:.1f}% | Total PnL: {v11b2_pnl:+.1f}%")

    # Overall
    total_trades = sum(r['trades'] for r in all_results)
    total_wins = sum(r['wins'] for r in all_results)
    total_losses = sum(r['losses'] for r in all_results)
    total_pnl = sum(r['total_pnl'] for r in all_results)
    overall_wr = total_wins / (total_wins + total_losses) * 100 if (total_wins + total_losses) > 0 else 0

    print(f"\nOVERALL ({len(all_results)} emiten):")
    print(f"  Trades: {total_trades} | Wins: {total_wins} | Losses: {total_losses}")
    print(f"  Win Rate: {overall_wr:.1f}% | Total PnL: {total_pnl:+.1f}%")

    conn.close()
    print("\n" + "=" * 80)
    print("DONE - Data saved to localhost PostgreSQL")
    print("=" * 80)


if __name__ == '__main__':
    main()
