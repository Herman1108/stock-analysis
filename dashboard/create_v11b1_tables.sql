-- ============================================================
-- V11B1 PRE-COMPUTED RESULTS TABLES
-- Setiap emiten punya tabel sendiri untuk isolasi error
-- ============================================================

-- Template untuk membuat tabel per emiten
-- Jalankan untuk setiap emiten: CUAN, MBMA, MDKA, etc.

-- Function untuk create table per stock
CREATE OR REPLACE FUNCTION create_v11b1_table(stock_code TEXT)
RETURNS VOID AS $$
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS v11b1_results_%s (
            id SERIAL PRIMARY KEY,
            calc_date DATE NOT NULL,
            calc_timestamp TIMESTAMP DEFAULT NOW(),

            -- Current Price Info
            current_price DECIMAL(12,2),
            price_change_pct DECIMAL(8,2),

            -- Status V11b1
            status VARCHAR(50),              -- BREAKOUT, RETEST, WATCH, NEUTRAL, RUNNING, AVOID
            action VARCHAR(50),              -- ENTRY, WAIT_PULLBACK, WATCH, EXIT, HOLD
            action_reason TEXT,

            -- Active Zones
            support_zone_num INTEGER,
            support_zone_low DECIMAL(12,2),
            support_zone_high DECIMAL(12,2),
            resistance_zone_num INTEGER,
            resistance_zone_low DECIMAL(12,2),
            resistance_zone_high DECIMAL(12,2),

            -- Breakout/Retest Tracking
            confirm_type VARCHAR(50),        -- BREAKOUT_OK, BREAKOUT (x/3), RETEST_OK, etc.
            days_above_zone INTEGER DEFAULT 0,
            came_from_below BOOLEAN DEFAULT FALSE,

            -- Volume Info
            vol_ratio DECIMAL(8,2),
            vol_status VARCHAR(20),          -- OK, LOW, HIGH

            -- Position Info (if RUNNING)
            has_open_position BOOLEAN DEFAULT FALSE,
            position_entry_date DATE,
            position_entry_price DECIMAL(12,2),
            position_current_pnl DECIMAL(8,2),
            position_sl DECIMAL(12,2),
            position_tp DECIMAL(12,2),

            -- Trade History (JSON array)
            trade_history JSONB,
            total_trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            win_rate DECIMAL(5,2),
            total_pnl DECIMAL(8,2),

            -- Checklist Items (JSON)
            checklist JSONB,

            -- Pullback Calculation (if WAIT_PULLBACK)
            pullback_entry_price DECIMAL(12,2),
            pullback_sl DECIMAL(12,2),
            pullback_tp DECIMAL(12,2),
            pullback_rr_ratio DECIMAL(5,2),

            -- Error Handling
            has_error BOOLEAN DEFAULT FALSE,
            error_message TEXT,

            -- Metadata
            formula_version VARCHAR(20) DEFAULT ''V11b1'',
            created_at TIMESTAMP DEFAULT NOW(),

            UNIQUE(calc_date)
        )', lower(stock_code));

    -- Create index for faster lookups
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_v11b1_%s_date
        ON v11b1_results_%s(calc_date DESC)', lower(stock_code), lower(stock_code));

END;
$$ LANGUAGE plpgsql;

-- Create tables for all V11b1 stocks
SELECT create_v11b1_table('ADMR');
SELECT create_v11b1_table('BBCA');
SELECT create_v11b1_table('BMRI');
SELECT create_v11b1_table('BREN');
SELECT create_v11b1_table('BRPT');
SELECT create_v11b1_table('CBDK');
SELECT create_v11b1_table('CBRE');
SELECT create_v11b1_table('CDIA');
SELECT create_v11b1_table('CUAN');
SELECT create_v11b1_table('DSNG');
SELECT create_v11b1_table('FUTR');
SELECT create_v11b1_table('HRUM');
SELECT create_v11b1_table('MBMA');
SELECT create_v11b1_table('MDKA');
SELECT create_v11b1_table('NCKL');
SELECT create_v11b1_table('PANI');
SELECT create_v11b1_table('PTRO');
SELECT create_v11b1_table('RATU');
SELECT create_v11b1_table('TINS');
SELECT create_v11b1_table('WIFI');

-- Verify tables created
SELECT table_name
FROM information_schema.tables
WHERE table_name LIKE 'v11b1_results_%'
ORDER BY table_name;
