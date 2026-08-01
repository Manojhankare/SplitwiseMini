# Splitwise Mini — Project Overview

Multi-user personal expense tracker: shared bills, personal spending, settlements, itemized reports, and a monthly consumption budget. Each logged-in user only sees their own people, groups, expenses, and settlements (`user_id` isolation).

## Stack

- **Backend:** Flask (MVC blueprints) + SQLAlchemy + Flask-Login
- **DB:** Postgres (Supabase recommended)
- **Frontend:** Single-page UI in `app/templates/index.html` (HTML/CSS/vanilla JS)
- **Deploy:** Local `python run.py`; production often Vercel (`vercel.json`)

See [README.md](../README.md) for setup, env vars, and the full API list.

## Architecture

```
app/
  __init__.py          # create_app, blueprints, optional create_all + admin seed
  config.py            # Config, should_create_db_on_startup
  extensions.py        # db, login_manager
  models/              # User, Person, Group, Expense, Settlement
  controllers/         # auth, page, expense (/api), admin
  templates/           # index.html (main app), login, register, admin
scripts/               # one-off SQL ALTERs / indexes for existing DBs
docs/                  # this file + AGENTS.md
```

**Important:** `db.create_all()` creates missing *tables* on a fresh DB. It does **not** add columns to existing tables. Production schema changes need scripts under `scripts/` (e.g. `add_monthly_budget.sql`).

## Domains

| Domain | Meaning |
|--------|---------|
| **People** | Named contacts for splits (`self` is the logged-in user alias in expense/settlement strings) |
| **Groups** | Named member sets for convenience when building splits |
| **Expenses** | Personal (`is_personal`) or shared; equal split via `_equal_shares` (cent remainder) |
| **Settlements** | Payments between people; may link to an expense |
| **Balances** | Net ledger per person for a period (zero-sum across people) |
| **Report** | Itemized rows + self pairwise summary |
| **Budget** | Monthly *consumption* target for the current UTC calendar month |

## Balance semantics

- Per person in `balances`: **positive = is owed**, **negative = owes**.
- The map is **zero-sum**. Do not sum all positives and negatives for “your” net — use `balances.self` or pairwise `self_summary`.
- Pairwise with self (`owe_you` / `you_owe`) is computed in `Expense.compute_pairwise_with_self`.

## Budget semantics

Stored on `users.monthly_budget` (nullable). Progress is always for the **current UTC calendar month**, independent of the Report/Balances period picker.

For that month:

- **budget_personal** — personal expenses where `payer == "self"` (full amount)
- **budget_my_shared** — shared expenses where `"self"` is a participant; amount = `_equal_shares(...)["self"]`
- **budget_spent** — personal + my shared (counts toward the target)
- **budget_shared_total** — sum of full shared bill amounts (“shared bills”; context only, not toward budget)

Settlements are **not** included (settle-up is debt, not new spend).

Budget is **consumption** (your share), not cash you paid. If you paid a shared bill but are not in `participants`, that bill does not add to `budget_spent`.

UI home: compact hero strip — primary figure is **Left this month** (`monthly_budget − budget_spent`) or **Over budget** / **My spend this month** if no target; thin progress; denser tiles for You owe, You’re owed, My spend, Shared bills. Add tab stays default so the form sits under the strip. Settings → Monthly budget via `PUT /api/settings/budget`. Bootstrap budget fields come from a **separate** current-month expense fetch (not the period-filtered list).

## Period filters

Optional on bootstrap / expenses / settlements / balances / report:

- `year` + `month` — calendar month
- `from` + `to` — inclusive range (wins if both styles sent)
- omit — all time

UI defaults Report/Balances to the current *local* month. Budget month is always *UTC* on the server (edge case near IST midnight at month boundaries).

## Auth & multi-tenant

- Register / login session; data scoped by `current_user.id`
- Admin role: `/admin` user management
- Always filter mutations and reads by `user_id`

## UI structure (`index.html`)

- Compact greeting + slim budget hero (left this month / my spend) + Add as default tab
- Tabs: Add · Report · Balances · Settings (floating bottom nav)
- Period bar on Report/Balances
- Settle modal (bottom sheet)
- IDs and `onclick` / `fetch` paths are wired tightly — preserve them when restyling

## Schema migrations (existing DB)

Run in Supabase SQL editor when deploying related features:

- `scripts/add_indexes.sql`
- `scripts/add_monthly_budget.sql` — `ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_budget ...`

## Related docs

- [README.md](../README.md) — setup and API reference
- [AGENTS.md](AGENTS.md) — playbook for AI agents working on this repo
