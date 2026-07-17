-- Run once in Supabase SQL editor (create_all will not add indexes to existing tables).
-- Composite indexes cover user_id equality lookups via leftmost prefix.

CREATE INDEX IF NOT EXISTS ix_expenses_user_id_expense_date
  ON expenses (user_id, expense_date DESC);

CREATE INDEX IF NOT EXISTS ix_settlements_user_id_settlement_date
  ON settlements (user_id, settlement_date DESC);

CREATE INDEX IF NOT EXISTS ix_settlements_expense_id
  ON settlements (expense_id);
