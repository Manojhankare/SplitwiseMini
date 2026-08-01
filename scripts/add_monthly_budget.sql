-- Run once in Supabase SQL editor (create_all will NOT add columns to existing tables).

ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_budget NUMERIC(12, 2);
