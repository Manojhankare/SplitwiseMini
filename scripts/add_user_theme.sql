-- Run once in Supabase SQL editor (create_all will NOT add columns to existing tables).

ALTER TABLE users ADD COLUMN IF NOT EXISTS theme_mode VARCHAR(16);
ALTER TABLE users ADD COLUMN IF NOT EXISTS theme_accent VARCHAR(16);
