-- =====================================================
-- CDIA Broker-Price Correlation Analysis System
-- Database Schema
-- =====================================================

-- Tabel: Data harga harian
CREATE TABLE stock_daily (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open_price NUMERIC(12,2),
    high_price NUMERIC(12,2),
    low_price NUMERIC(12,2),
    close_price NUMERIC(12,2),
    avg_price NUMERIC(12,2),
    volume BIGINT,
    value NUMERIC(18,2),
    frequency INTEGER,
    foreign_buy NUMERIC(18,2),
    foreign_sell NUMERIC(18,2),
    net_foreign NUMERIC(18,2),
    change_value NUMERIC(12,2),
    change_percent NUMERIC(8,4),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_code, date)
);

-- Tabel: Broker summary harian
CREATE TABLE broker_summary (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    broker_code VARCHAR(10) NOT NULL,
    buy_value NUMERIC(18,2) DEFAULT 0,
    buy_lot BIGINT DEFAULT 0,
    buy_avg NUMERIC(12,2) DEFAULT 0,
    sell_value NUMERIC(18,2) DEFAULT 0,
    sell_lot BIGINT DEFAULT 0,
    sell_avg NUMERIC(12,2) DEFAULT 0,
    net_value NUMERIC(18,2) DEFAULT 0,
    net_lot BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_code, date, broker_code)
);

-- Tabel: Deteksi zona sideways
CREATE TABLE sideways_zones (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    support_price NUMERIC(12,2),
    resistance_price NUMERIC(12,2),
    range_percent NUMERIC(8,4),
    duration_days INTEGER,
    status VARCHAR(20) DEFAULT 'ongoing', -- ongoing, breakout_up, breakout_down
    breakout_date DATE,
    breakout_price NUMERIC(12,2),
    breakout_volume BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tabel: Pola akumulasi broker
CREATE TABLE broker_accumulation (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    broker_code VARCHAR(10) NOT NULL,
    sideways_zone_id INTEGER REFERENCES sideways_zones(id),
    start_date DATE NOT NULL,
    end_date DATE,
    accumulation_days INTEGER,
    total_net_value NUMERIC(18,2),
    total_net_lot BIGINT,
    avg_daily_net NUMERIC(18,2),
    is_before_breakout BOOLEAN DEFAULT FALSE,
    days_before_breakout INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabel: Broker sensitivity score (hasil analisis)
CREATE TABLE broker_sensitivity (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    broker_code VARCHAR(10) NOT NULL,
    total_breakouts INTEGER DEFAULT 0,
    breakouts_participated INTEGER DEFAULT 0,
    participation_rate NUMERIC(8,4) DEFAULT 0,
    avg_accumulation_days NUMERIC(8,2) DEFAULT 0,
    avg_accumulation_value NUMERIC(18,2) DEFAULT 0,
    avg_days_before_breakout NUMERIC(8,2) DEFAULT 0,
    success_rate NUMERIC(8,4) DEFAULT 0,
    sensitivity_score NUMERIC(8,2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_code, broker_code)
);

-- Tabel: Alert history
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    alert_type VARCHAR(50) NOT NULL, -- accumulation_detected, breakout_imminent, etc
    broker_code VARCHAR(10),
    message TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index untuk performa query
CREATE INDEX idx_stock_daily_date ON stock_daily(stock_code, date);
CREATE INDEX idx_broker_summary_date ON broker_summary(stock_code, date);
CREATE INDEX idx_broker_summary_broker ON broker_summary(broker_code, date);
CREATE INDEX idx_sideways_zones_status ON sideways_zones(stock_code, status);
CREATE INDEX idx_broker_accumulation_zone ON broker_accumulation(sideways_zone_id);
CREATE INDEX idx_alerts_stock ON alerts(stock_code, created_at);

-- View: Broker net flow harian
CREATE VIEW v_broker_daily_net AS
SELECT
    stock_code,
    date,
    broker_code,
    buy_value,
    sell_value,
    net_value,
    buy_lot,
    sell_lot,
    net_lot,
    CASE
        WHEN net_value > 0 THEN 'accumulation'
        WHEN net_value < 0 THEN 'distribution'
        ELSE 'neutral'
    END as flow_type
FROM broker_summary
ORDER BY date, net_value DESC;

-- View: Top accumulator per hari
CREATE VIEW v_top_accumulators AS
SELECT
    stock_code,
    date,
    broker_code,
    net_value,
    net_lot,
    ROW_NUMBER() OVER (PARTITION BY stock_code, date ORDER BY net_value DESC) as rank
FROM broker_summary
WHERE net_value > 0;

-- View: Top distributor per hari
CREATE VIEW v_top_distributors AS
SELECT
    stock_code,
    date,
    broker_code,
    net_value,
    net_lot,
    ROW_NUMBER() OVER (PARTITION BY stock_code, date ORDER BY net_value ASC) as rank
FROM broker_summary
WHERE net_value < 0;

-- Function: Parse value string (e.g., "35.7B" -> 35700000000)
CREATE OR REPLACE FUNCTION parse_value_string(val_str TEXT)
RETURNS NUMERIC AS $$
DECLARE
    num_part NUMERIC;
    suffix CHAR(1);
    multiplier NUMERIC;
BEGIN
    IF val_str IS NULL OR val_str = '' OR val_str = '-' THEN
        RETURN 0;
    END IF;

    -- Remove commas
    val_str := REPLACE(val_str, ',', '');

    -- Get suffix (last character)
    suffix := UPPER(RIGHT(val_str, 1));

    -- Determine multiplier
    CASE suffix
        WHEN 'B' THEN multiplier := 1000000000;
        WHEN 'M' THEN multiplier := 1000000;
        WHEN 'K' THEN multiplier := 1000;
        ELSE multiplier := 1;
    END CASE;

    -- Extract numeric part
    IF suffix IN ('B', 'M', 'K') THEN
        num_part := CAST(LEFT(val_str, LENGTH(val_str) - 1) AS NUMERIC);
    ELSE
        num_part := CAST(val_str AS NUMERIC);
    END IF;

    RETURN num_part * multiplier;
EXCEPTION
    WHEN OTHERS THEN
        RETURN 0;
END;
$$ LANGUAGE plpgsql;
