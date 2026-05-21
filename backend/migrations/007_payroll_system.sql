-- Migration 007: Worker Payroll, Hiring & Tips System
-- Date: 2026-05-04
--
-- Creates 8 tables supporting the full payroll/tips/T4 feature set:
--   employee_payroll_profiles  - compensation & SIN per shop_employee
--   payroll_constants          - province-specific 2025 tax brackets (seeded)
--   payslips                   - individual pay period records
--   tips_log                   - per-employee tip entries
--   tip_pools                  - per-shift pooled tips
--   tip_pool_splits            - distribution rows within a pool
--   remittances                - CRA source-deduction remittance schedule
--   t4_records                 - year-end T4 data

-- ──────────────────────────────────────────────────────────────────────────────
-- 1. employee_payroll_profiles
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS employee_payroll_profiles (
    id                  SERIAL PRIMARY KEY,
    shop_employee_id    INTEGER NOT NULL UNIQUE REFERENCES shop_employees(id) ON DELETE CASCADE,
    shop_id             INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    -- compensation
    pay_type            VARCHAR(10)  NOT NULL DEFAULT 'hourly'  -- 'hourly' | 'salary'
                        CHECK (pay_type IN ('hourly', 'salary')),
    hourly_rate         NUMERIC(10, 4) NULL,                    -- e.g. 20.0000
    annual_salary       NUMERIC(12, 2) NULL,                    -- used when pay_type='salary'
    pay_frequency       VARCHAR(10)  NOT NULL DEFAULT 'biweekly'
                        CHECK (pay_frequency IN ('weekly', 'biweekly', 'semi_monthly', 'monthly')),

    -- tax identity
    sin_encrypted       TEXT NULL,                              -- AES-256 ciphertext
    sin_last4           CHAR(4) NULL,                           -- display only
    province            CHAR(2)  NOT NULL DEFAULT 'ON',         -- ISO province code
    td1_federal_claim   NUMERIC(10, 2) NOT NULL DEFAULT 15705.00,  -- federal basic personal amount (update annually via CRA T4127)
    td1_prov_claim      NUMERIC(10, 2) NOT NULL DEFAULT 11865.00,  -- ON 2025 basic personal amount
    additional_tax      NUMERIC(10, 2) NOT NULL DEFAULT 0.00,   -- extra withholding per period

    -- employment dates
    hire_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    termination_date    DATE NULL,

    -- YTD accumulators (reset annually)
    ytd_gross           NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ytd_cpp             NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ytd_ei              NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ytd_fed_tax         NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ytd_prov_tax        NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ytd_tips            NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ytd_year            INTEGER NOT NULL DEFAULT EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER,

    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_epp_shop_employee_id ON employee_payroll_profiles(shop_employee_id);
CREATE INDEX IF NOT EXISTS idx_epp_shop_id          ON employee_payroll_profiles(shop_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 2. payroll_constants  (seeded below)
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payroll_constants (
    id              SERIAL PRIMARY KEY,
    tax_year        INTEGER      NOT NULL,
    province        CHAR(2)      NOT NULL,

    -- CPP (federal)
    cpp_rate            NUMERIC(8, 6) NOT NULL,   -- e.g. 0.0595
    cpp_employee_max    NUMERIC(10, 2) NOT NULL,  -- max annual employee contribution
    cpp_basic_exemption NUMERIC(10, 2) NOT NULL,  -- annual basic exemption

    -- EI (federal)
    ei_rate             NUMERIC(8, 6) NOT NULL,   -- e.g. 0.0166
    ei_employee_max     NUMERIC(10, 2) NOT NULL,  -- max annual employee premium
    ei_insurable_max    NUMERIC(12, 2) NOT NULL,  -- max insurable earnings

    -- Federal income tax brackets (JSON array [{min, max|null, rate}])
    fed_brackets        JSONB NOT NULL,

    -- Provincial income tax brackets
    prov_brackets       JSONB NOT NULL,

    -- Provincial surtax (ON only meaningful right now)
    prov_surtax         JSONB NOT NULL DEFAULT '{}',

    UNIQUE (tax_year, province)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- 3. payslips
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payslips (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    shop_employee_id    INTEGER NOT NULL REFERENCES shop_employees(id) ON DELETE CASCADE,

    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    pay_date            DATE NOT NULL,

    -- earnings
    regular_hours       NUMERIC(7, 2) NOT NULL DEFAULT 0.00,
    overtime_hours      NUMERIC(7, 2) NOT NULL DEFAULT 0.00,
    gross_pay           NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    tips_included       NUMERIC(12, 2) NOT NULL DEFAULT 0.00,  -- pooled/individual tips added to gross

    -- deductions
    cpp_deduction       NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    ei_deduction        NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    fed_tax             NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    prov_tax            NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    other_deductions    NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_deductions    NUMERIC(10, 2) NOT NULL DEFAULT 0.00,

    net_pay             NUMERIC(12, 2) NOT NULL DEFAULT 0.00,

    status              VARCHAR(15) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'approved', 'paid', 'void')),
    approved_by         INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    approved_at         TIMESTAMP NULL,

    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payslips_shop_id          ON payslips(shop_id);
CREATE INDEX IF NOT EXISTS idx_payslips_shop_employee_id ON payslips(shop_employee_id);
CREATE INDEX IF NOT EXISTS idx_payslips_period_start     ON payslips(period_start);
CREATE INDEX IF NOT EXISTS idx_payslips_status           ON payslips(status);

-- ──────────────────────────────────────────────────────────────────────────────
-- 4. tip_pools  (must come before tips_log due to FK)
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tip_pools (
    id              SERIAL PRIMARY KEY,
    shop_id         INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    pool_date       DATE NOT NULL,
    total_amount    NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    status          VARCHAR(10) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'splitting', 'split', 'paid')),
    split_method    VARCHAR(15) NOT NULL DEFAULT 'hours_worked'
                    CHECK (split_method IN ('equal', 'hours_worked', 'manual')),
    approved_by     INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    approved_at     TIMESTAMP NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tip_pools_shop_id    ON tip_pools(shop_id);
CREATE INDEX IF NOT EXISTS idx_tip_pools_pool_date  ON tip_pools(pool_date);

-- ──────────────────────────────────────────────────────────────────────────────
-- 5. tips_log
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tips_log (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    shop_employee_id    INTEGER NOT NULL REFERENCES shop_employees(id) ON DELETE CASCADE,
    queue_item_id       INTEGER NULL REFERENCES queue_items(id) ON DELETE SET NULL,

    amount              NUMERIC(10, 2) NOT NULL CHECK (amount >= 0),
    tip_type            VARCHAR(10) NOT NULL DEFAULT 'card'
                        CHECK (tip_type IN ('card', 'cash', 'pooled')),
    note                TEXT NULL,
    tip_date            DATE NOT NULL DEFAULT CURRENT_DATE,

    -- link to payslip when included in pay
    payslip_id          INTEGER NULL REFERENCES payslips(id) ON DELETE SET NULL,
    pooled_in           INTEGER NULL REFERENCES tip_pools(id) ON DELETE SET NULL,

    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tips_log_shop_id          ON tips_log(shop_id);
CREATE INDEX IF NOT EXISTS idx_tips_log_shop_employee_id ON tips_log(shop_employee_id);
CREATE INDEX IF NOT EXISTS idx_tips_log_tip_date         ON tips_log(tip_date);

-- ──────────────────────────────────────────────────────────────────────────────
-- 6. tip_pool_splits
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tip_pool_splits (
    id                  SERIAL PRIMARY KEY,
    tip_pool_id         INTEGER NOT NULL REFERENCES tip_pools(id) ON DELETE CASCADE,
    shop_employee_id    INTEGER NOT NULL REFERENCES shop_employees(id) ON DELETE CASCADE,
    hours_worked        NUMERIC(7, 2) NOT NULL DEFAULT 0.00,
    split_amount        NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tip_pool_splits_pool_id     ON tip_pool_splits(tip_pool_id);
CREATE INDEX IF NOT EXISTS idx_tip_pool_splits_employee_id ON tip_pool_splits(shop_employee_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 7. remittances
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS remittances (
    id              SERIAL PRIMARY KEY,
    shop_id         INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    due_date        DATE NOT NULL,

    cpp_employee    NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    cpp_employer    NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ei_employee     NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    ei_employer     NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    fed_tax         NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    prov_tax        NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_owing     NUMERIC(12, 2) NOT NULL DEFAULT 0.00,

    status          VARCHAR(10) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'filed', 'paid', 'overdue')),
    paid_at         TIMESTAMP NULL,
    notes           TEXT NULL,

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_remittances_shop_id  ON remittances(shop_id);
CREATE INDEX IF NOT EXISTS idx_remittances_due_date ON remittances(due_date);
CREATE INDEX IF NOT EXISTS idx_remittances_status   ON remittances(status);

-- ──────────────────────────────────────────────────────────────────────────────
-- 8. t4_records
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS t4_records (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    shop_employee_id    INTEGER NOT NULL REFERENCES shop_employees(id) ON DELETE CASCADE,
    tax_year            INTEGER NOT NULL,

    -- T4 box fields
    box_14_employment_income    NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    box_16_cpp_contributions    NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    box_18_ei_premiums          NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    box_22_income_tax_deducted  NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    box_24_ei_insurable_earnings NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    box_26_cpp_pensionable_earnings NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    box_40_tips_gratuities      NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    box_50_rpp_or_dpsp          NUMERIC(10, 2) NOT NULL DEFAULT 0.00,

    province                    CHAR(2) NOT NULL DEFAULT 'ON',
    status                      VARCHAR(10) NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft', 'filed', 'amended')),
    filed_at                    TIMESTAMP NULL,

    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE (shop_employee_id, tax_year)
);

CREATE INDEX IF NOT EXISTS idx_t4_records_shop_id          ON t4_records(shop_id);
CREATE INDEX IF NOT EXISTS idx_t4_records_shop_employee_id ON t4_records(shop_employee_id);
CREATE INDEX IF NOT EXISTS idx_t4_records_tax_year         ON t4_records(tax_year);

-- ──────────────────────────────────────────────────────────────────────────────
-- Seed payroll_constants: 2025, all 10 provinces
-- Source: CRA T4127 Payroll Deductions Formulas (January 1 2025 edition)
-- ──────────────────────────────────────────────────────────────────────────────

-- Federal constants are the same for all provinces; prov_brackets differ.
-- cpp_rate 5.95% (2025), max cpp annual = 4055.50, basic_exemption = 3500.00
-- ei_rate  1.66% (2025), max ei annual = 1049.12, insurable_max = 63200.00
-- Federal brackets 2025: 15% / 20.5% / 26% / 29% / 33%

INSERT INTO payroll_constants (
    tax_year, province,
    cpp_rate, cpp_employee_max, cpp_basic_exemption,
    ei_rate, ei_employee_max, ei_insurable_max,
    fed_brackets, prov_brackets, prov_surtax
) VALUES

-- Ontario
(2025, 'ON',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":52886,"rate":0.0505},{"min":52886,"max":105775,"rate":0.0915},{"min":105775,"max":150000,"rate":0.1116},{"min":150000,"max":220000,"rate":0.1216},{"min":220000,"max":null,"rate":0.1316}]',
 '{"threshold1":5554,"surcharge1":0.20,"threshold2":7108,"surcharge2":0.56}'),

-- British Columbia
(2025, 'BC',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":47937,"rate":0.0506},{"min":47937,"max":95875,"rate":0.077},{"min":95875,"max":110076,"rate":0.105},{"min":110076,"max":133664,"rate":0.1229},{"min":133664,"max":181232,"rate":0.147},{"min":181232,"max":252752,"rate":0.168},{"min":252752,"max":null,"rate":0.205}]',
 '{}'),

-- Alberta
(2025, 'AB',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":148269,"rate":0.10},{"min":148269,"max":177922,"rate":0.12},{"min":177922,"max":237230,"rate":0.13},{"min":237230,"max":355845,"rate":0.14},{"min":355845,"max":null,"rate":0.15}]',
 '{}'),

-- Quebec (TP-1015 — Calculator must raise NotImplementedError for QC)
(2025, 'QC',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":55867,"rate":0.14},{"min":55867,"max":111733,"rate":0.19},{"min":111733,"max":135701,"rate":0.24},{"min":135701,"max":null,"rate":0.2575}]',
 '{"qpip_note":"Quebec uses TP-1015 which differs from T4127 — use RQ provincial calculator"}'),

-- Manitoba
(2025, 'MB',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":47000,"rate":0.108},{"min":47000,"max":100000,"rate":0.1275},{"min":100000,"max":null,"rate":0.174}]',
 '{}'),

-- Saskatchewan
(2025, 'SK',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":49720,"rate":0.105},{"min":49720,"max":142058,"rate":0.125},{"min":142058,"max":null,"rate":0.145}]',
 '{}'),

-- Nova Scotia
(2025, 'NS',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":29590,"rate":0.0879},{"min":29590,"max":59180,"rate":0.1495},{"min":59180,"max":93000,"rate":0.1667},{"min":93000,"max":150000,"rate":0.175},{"min":150000,"max":null,"rate":0.21}]',
 '{}'),

-- New Brunswick
(2025, 'NB',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":49958,"rate":0.094},{"min":49958,"max":99916,"rate":0.14},{"min":99916,"max":185064,"rate":0.16},{"min":185064,"max":null,"rate":0.195}]',
 '{}'),

-- Prince Edward Island
(2025, 'PE',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":32656,"rate":0.094},{"min":32656,"max":64313,"rate":0.1637},{"min":64313,"max":105000,"rate":0.18},{"min":105000,"max":140000,"rate":0.1875},{"min":140000,"max":null,"rate":0.19}]',
 '{}'),

-- Newfoundland and Labrador
(2025, 'NL',
 0.0595, 4055.50, 3500.00,
 0.0166, 1049.12, 63200.00,
 '[{"min":0,"max":57375,"rate":0.15},{"min":57375,"max":114750,"rate":0.205},{"min":114750,"max":177882,"rate":0.26},{"min":177882,"max":253414,"rate":0.29},{"min":253414,"max":null,"rate":0.33}]',
 '[{"min":0,"max":43198,"rate":0.087},{"min":43198,"max":86395,"rate":0.145},{"min":86395,"max":154244,"rate":0.158},{"min":154244,"max":215943,"rate":0.178},{"min":215943,"max":275870,"rate":0.198},{"min":275870,"max":551739,"rate":0.208},{"min":551739,"max":null,"rate":0.213}]',
 '{}')

ON CONFLICT (tax_year, province) DO NOTHING;
