# Splitwise Mini

Track shared bills and personal spending. Add expenses via a structured form (description, amount, date, payer, participants) or optional AI text parsing (Groq). View itemized per-person breakdowns and shared balances.

Example shared: food at jay malhar, ₹240, paid by manoj, split manoj + baba + akshay.
Example personal: bus fare ₹45, paid by manoj (no split).

## Stack
- Frontend: Jinja template at `app/templates/index.html` (no framework)
- Backend: Flask MVC app (`app/` package), entry via `run.py`
- DB: Postgres via Supabase with SQLAlchemy ORM
- AI parsing (optional): [Groq](https://groq.com/) OpenAI-compatible chat completions API

## Project structure (MVC)
```
SplitwiseMini/
├── run.py
├── app/
│   ├── __init__.py                 # create_app() + db.create_all()
│   ├── config.py
│   ├── extensions.py
│   ├── models/
│   │   ├── expense.py              # expenses + report logic
│   │   └── person.py               # managed people list
│   ├── services/ai_service.py
│   ├── controllers/
│   ├── utils/auth.py
│   └── templates/index.html
```

## 1. Set up Supabase
1. Create a free project at supabase.com.
2. Copy the Postgres connection string (Session pooler or direct).
3. **Delete any old tables** if upgrading schema — the app recreates `expenses` and `people` on startup via `db.create_all()`.

## 2. Get a Groq API key (optional, for AI text input)
Get a free API key from [Groq Console](https://console.groq.com/).

## 3. Run locally
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, GROQ_API_KEY, BASIC_AUTH_*
python run.py
```
Open http://localhost:5000 — browser prompts for basic auth.

## Environment variables
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase Postgres connection string |
| `GROQ_API_KEY` | Groq API key (optional; only needed for AI text box) |
| `GROQ_MODEL` | Groq model id (default: `llama-3.3-70b-versatile`) |
| `BASIC_AUTH_USERNAME` | Homepage basic auth username |
| `BASIC_AUTH_PASSWORD` | Homepage basic auth password |

## API

### People
- `GET /api/people` — list `{id, name}`
- `POST /api/people` — body `{ "name": "manoj" }`
- `DELETE /api/people/<id>`

### Expenses
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
  Or AI body: `{ "text": "230 rs food split between me and akshay" }`
- `GET /api/expenses` — all expenses (newest first)
- `GET /api/balances` — shared balances only (personal excluded)
- `GET /api/report?filter=all|shared|personal` — itemized breakdown with per-person shares, Final Standings, Grand Total
- `DELETE /api/delete/<id>`

## Notes
- **Personal expenses**: set `is_personal: true` or use the UI toggle — full amount counts in report totals, no effect on shared balances.
- **Shared expenses**: equal split among selected participants.
- Report table matches the style of `bill_split_summary.md` (per-person columns + totals row).
