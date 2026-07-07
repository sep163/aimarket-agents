-- Агент 5. Маркетинговая аналитика. Схема PostgreSQL.
-- Применяется автоматически при старте (см. db.apply_schema), можно также
-- выполнить руками один раз: psql $DATABASE_URL -f schema.sql

-- Ежедневные метрики по рекламным кампаниям, нормализованные под общую схему
-- (Яндекс.Директ, VK Ads, и любые каналы, которые добавят позже).
CREATE TABLE IF NOT EXISTS ad_metrics_daily (
    id              BIGSERIAL PRIMARY KEY,
    channel         TEXT NOT NULL,
    campaign_id     TEXT NOT NULL,
    campaign_name   TEXT,
    metric_date     DATE NOT NULL,
    spend           NUMERIC(14,2) NOT NULL DEFAULT 0,
    clicks          INTEGER NOT NULL DEFAULT 0,
    impressions     INTEGER NOT NULL DEFAULT 0,
    conversions     INTEGER NOT NULL DEFAULT 0,
    cpl             NUMERIC(14,2),
    ctr             NUMERIC(7,4),
    raw_payload     JSONB,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (channel, campaign_id, metric_date)
);
CREATE INDEX IF NOT EXISTS idx_ad_metrics_daily_date ON ad_metrics_daily (metric_date);
CREATE INDEX IF NOT EXISTS idx_ad_metrics_daily_channel ON ad_metrics_daily (channel);

-- Воронка из CRM или CSV выгрузки.
CREATE TABLE IF NOT EXISTS crm_funnel (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    lead_id         TEXT,
    channel         TEXT,
    stage           TEXT NOT NULL,
    stage_date      DATE NOT NULL,
    amount          NUMERIC(14,2),
    raw_payload     JSONB,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crm_funnel_stage_date ON crm_funnel (stage_date);

-- Проблемы клиентов из созвонов (раздел client feedback MD wiki, Агент 1).
CREATE TABLE IF NOT EXISTS client_feedback (
    id              BIGSERIAL PRIMARY KEY,
    source_call_id  TEXT,
    problem_tag     TEXT NOT NULL,
    quote           TEXT,
    call_date       DATE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_client_feedback_tag ON client_feedback (problem_tag);
CREATE INDEX IF NOT EXISTS idx_client_feedback_date ON client_feedback (call_date);

-- Пороги для детекции аномалий (используются в weekly_report.py, сейчас 20% захардкожено в коде).
CREATE TABLE IF NOT EXISTS anomaly_config (
    metric_name     TEXT PRIMARY KEY,
    channel         TEXT,
    threshold_pct   NUMERIC(5,2) NOT NULL DEFAULT 20.00,
    direction       TEXT NOT NULL DEFAULT 'both'
);

INSERT INTO anomaly_config (metric_name, channel, threshold_pct, direction) VALUES
    ('spend', NULL, 20.00, 'both'),
    ('cpl', NULL, 20.00, 'up'),
    ('conversions', NULL, 20.00, 'down')
ON CONFLICT (metric_name) DO NOTHING;

-- Журнал отправленных отчётов и ответов Q&A бота (аудит).
CREATE TABLE IF NOT EXISTS report_log (
    id                  BIGSERIAL PRIMARY KEY,
    report_type         TEXT NOT NULL,
    period_start        DATE,
    period_end          DATE,
    telegram_chat_id    TEXT,
    content             TEXT,
    sent_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
