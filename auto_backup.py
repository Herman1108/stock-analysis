"""
Auto Backup Database to GitHub
Automatically backup PostgreSQL database and push to GitHub
"""
import os
import subprocess
from datetime import datetime

# Configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'stock_analysis'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres123'),
    'port': os.environ.get('DB_PORT', '5432')
}

REPO_PATH = r"E:\Herman_Irawan\herman_stock\stock-analysis"
BACKUP_FILE = os.path.join(REPO_PATH, "database_backup.sql")
PG_DUMP_PATH = r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"


def backup_database():
    """Export database to SQL file"""
    print(f"[{datetime.now()}] Starting database backup...")

    # Set password environment variable
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']

    # pg_dump command
    cmd = [
        PG_DUMP_PATH,
        '-h', DB_CONFIG['host'],
        '-p', DB_CONFIG['port'],
        '-U', DB_CONFIG['user'],
        '-d', DB_CONFIG['database'],
        '-f', BACKUP_FILE,
        '--no-owner',
        '--no-privileges'
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            file_size = os.path.getsize(BACKUP_FILE) / 1024  # KB
            print(f"[{datetime.now()}] Backup successful! Size: {file_size:.1f} KB")
            return True
        else:
            print(f"[{datetime.now()}] Backup failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Backup error: {e}")
        return False


def push_to_github(message=None):
    """Commit and push backup to GitHub"""
    print(f"[{datetime.now()}] Pushing to GitHub...")

    if message is None:
        message = f"Auto backup: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    try:
        # Change to repo directory
        os.chdir(REPO_PATH)

        # Git commands
        subprocess.run(['git', 'add', 'database_backup.sql'], capture_output=True)

        # Check if there are changes
        status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if not status.stdout.strip():
            print(f"[{datetime.now()}] No changes to commit")
            return True

        # Commit
        subprocess.run(['git', 'commit', '-m', message], capture_output=True)

        # Push
        result = subprocess.run(['git', 'push'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Push successful!")
            return True
        else:
            print(f"[{datetime.now()}] Push failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"[{datetime.now()}] Git error: {e}")
        return False


def auto_backup_and_push(message=None):
    """Full auto backup: export DB + push to GitHub"""
    print("=" * 50)
    print("  AUTO BACKUP TO GITHUB")
    print("=" * 50)

    # Step 1: Backup database
    if not backup_database():
        return False

    # Step 2: Push to GitHub
    if not push_to_github(message):
        return False

    print("=" * 50)
    print("  BACKUP COMPLETE!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    auto_backup_and_push()
