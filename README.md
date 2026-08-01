# Splitwise Mini

Multi-user expense tracker: shared bills with groups, personal spending, itemized reports, monthly budget, and per-user isolated data.

## Docs
- [docs/PROJECT.md](docs/PROJECT.md) — architecture, domains, balance & budget semantics
- [docs/AGENTS.md](docs/AGENTS.md) — playbook for AI agents (where to edit, pitfalls, feature checklist)

## Stack
- Flask MVC + SQLAlchemy + Flask-Login
- Postgres (Supabase)

## Setup
1. Drop all existing tables in Supabase (fresh schema), or on an existing DB run:
   - `scripts/add_indexes.sql`
   - `scripts/add_monthly_budget.sql` (adds `users.monthly_budget`)
2. Copy `.env.example` to `.env` and fill in values (prefer Supabase **pooler** URL on port `6543`).
3. `pip install -r requirements.txt`
4. Set `FLASK_ENV=development` locally, then `python run.py` — creates tables and seeds admin from `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
5. On Vercel: omit `FLASK_ENV` (or set production) so cold starts skip `create_all` / seed. Run SQL scripts manually for schema changes.

## First use
1. Login as admin at http://localhost:5000/login (or register a new account).
2. Add **People** (manoj, akshay, baba, etc.).
3. Create **Groups** (e.g. "Roommates") by selecting members.
4. Add expenses — use **Quick select group** to auto-check participants.
5. View **Itemized report** and **Balances**.

## Environment variables
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string (pooler `:6543` recommended on Vercel) |
| `SECRET_KEY` | Flask session secret (required) |
| `ADMIN_USERNAME` | Initial admin username (seeded once in development) |
| `ADMIN_PASSWORD` | Initial admin password |
| `FLASK_ENV` | Set to `development` locally to create tables + seed on startup |
| `ENABLE_DB_CREATE` | Set to `1` to force schema create without `FLASK_ENV=development` |

## Auth
- `/register` — open sign-up; each user gets isolated people, groups, expenses
- `/login` — session login
- `/admin` — admin dashboard (user list, enable/disable, delete)

## API (all require login)
- `GET /api/bootstrap?filter=all|shared|personal` — people, groups, expenses, settlements, balances, report, plus monthly budget fields (`monthly_budget`, `budget_spent`, `budget_personal`, `budget_my_shared`, `budget_shared_total`) for the **current UTC month** (independent of period filters)
- Period (optional on bootstrap / expenses / settlements / balances / report; omit = all time):
  - `year=2026&month=8` — calendar month
  - `from=2026-08-01&to=2026-08-31` — inclusive range (wins if both styles sent)
- `GET/POST /api/people`, `DELETE /api/people/<id>`
- `GET/POST /api/groups`, `PUT/DELETE /api/groups/<id>`
- `POST /api/add` — structured body:
  ```json
  {
    "description": "food jay malhar",
    "amount": 240,
    "payer": "manoj",
    "participants": ["manoj", "baba", "akshay"],
    "is_personal": false,
    "date": "2026-07-03"
  }
  ```
- `PUT /api/expenses/<id>` — same body as add; update an existing expense
- `GET /api/expenses`, `/api/settlements`, `/api/balances`, `/api/report?filter=all|shared|personal`
- `GET /api/expenses/<id>/outstanding` — full outstanding for settle (not period-scoped)
- `POST /api/settlements`, `DELETE /api/settlements/<id>`
- `DELETE /api/delete/<id>`
- `GET /api/settings/budget` — `{ "monthly_budget": 2000 | null }`
- `PUT /api/settings/budget` — body `{ "monthly_budget": 2000 }` (`null` or `0` clears)

UI defaults Report/Balances to the **current local month** via period params; people/groups and mutations stay unscoped. Budget progress always uses the **current UTC month**.

## Admin API
- `GET /admin/users`
- `POST /admin/users/<id>/toggle`
- `DELETE /admin/users/<id>`

## SaaS notes
User model includes `role`, `is_active`, `created_at`, `monthly_budget` for personal limits / future billing integration. No payment features yet.
