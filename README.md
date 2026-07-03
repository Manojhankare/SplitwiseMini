# Splitwise Mini

Multi-user expense tracker: shared bills with groups, personal spending, itemized reports, and per-user isolated data.

## Stack
- Flask MVC + SQLAlchemy + Flask-Login
- Postgres (Supabase)

## Setup
1. Drop all existing tables in Supabase (fresh schema).
2. Copy `.env.example` to `.env` and fill in values.
3. `pip install -r requirements.txt`
4. `python run.py` — creates tables and seeds admin user from `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

## First use
1. Login as admin at http://localhost:5000/login (or register a new account).
2. Add **People** (manoj, akshay, baba, etc.).
3. Create **Groups** (e.g. "Roommates") by selecting members.
4. Add expenses — use **Quick select group** to auto-check participants.
5. View **Itemized report** and **Balances**.

## Environment variables
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string |
| `SECRET_KEY` | Flask session secret (required) |
| `ADMIN_USERNAME` | Initial admin username (seeded once) |
| `ADMIN_PASSWORD` | Initial admin password |

## Auth
- `/register` — open sign-up; each user gets isolated people, groups, expenses
- `/login` — session login
- `/admin` — admin dashboard (user list, enable/disable, delete)

## API (all require login)
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
- `GET /api/expenses`, `/api/balances`, `/api/report?filter=all|shared|personal`
- `DELETE /api/delete/<id>`

## Admin API
- `GET /admin/users`
- `POST /admin/users/<id>/toggle`
- `DELETE /admin/users/<id>`

## SaaS notes
User model includes `role`, `is_active`, `created_at` for future billing integration. No payment features yet.
