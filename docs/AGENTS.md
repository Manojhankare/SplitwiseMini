# AGENTS.md — Playbook for AI agents

Read this file, [PROJECT.md](PROJECT.md), and [README.md](../README.md) before changing code.

## Mission

Improve or extend Splitwise Mini without breaking existing behavior: auth isolation, expense/settlement math, template IDs/handlers, or deploy assumptions.

## Hard rules

1. **Preserve UI contracts** in `app/templates/index.html`: do not rename/remove existing element `id`s, `data-tab` / `data-panel`, `onclick` / `onchange` / `oninput` / `onfocus`, or Jinja (`current_username`, `url_for`, `{% if is_admin %}`) unless the task explicitly requires a migration of those contracts.
2. **Do not change fetch URLs or request bodies** for existing endpoints unless the task is an API change; prefer additive fields.
3. **Always scope data by `user_id` / `current_user.id`.** Never return or mutate another user’s rows.
4. **No drive-by refactors.** Touch only files needed for the task.
5. **Schema:** `db.create_all()` does not ALTER existing tables. New columns need `scripts/*.sql` and a README note. Deployers must run ALTER on Supabase before code that SELECTs the new column ships.
6. **Git:** do not commit, push, amend, or change git config unless the user explicitly asks.
7. **Secrets:** never commit `.env` or credentials.

## Where things live

| Need | Open first |
|------|------------|
| HTTP API | `app/controllers/expense_controller.py`, `auth_controller.py`, `admin_controller.py` |
| Domain logic / shares / balances / budget | `app/models/expense.py`, `settlement.py`, `user.py` |
| Main UI | `app/templates/index.html` |
| Pages / login | `app/controllers/page_controller.py`, `templates/login.html` |
| App wiring | `app/__init__.py`, `app/config.py` |
| DB patches | `scripts/` |
| Product/architecture context | `docs/PROJECT.md` |
| Setup / API list | `README.md` |

## How to add a feature (checklist)

1. **Model** — column/table on the right model; keep `user_id` FKs.
2. **SQL ALTER** — `scripts/add_<feature>.sql` for existing DBs; mention in README/PROJECT.md.
3. **API** — additive routes or bootstrap keys; validate input; return JSON errors consistently.
4. **Bootstrap** — if the home UI needs the data on every load, add fields in `Expense.bootstrap_payload` (compute with correct date scope — see pitfalls).
5. **UI** — new IDs only; wire save → `refresh()` when bootstrap carries the state.
6. **Docs** — update `docs/PROJECT.md` semantics + `README.md` API if public; update this file if you introduce a new pitfall.

## Common pitfalls

- **Zero-sum balances:** summing all `balances` values ≈ 0. Use `balances.self` or pairwise `self_summary` for “my” net.
- **Period vs budget month:** bootstrap expenses follow UI period filters. Monthly budget must use a **separate** current-UTC-month fetch (`compute_monthly_budget_summary`), not the period-filtered list.
- **Equal shares:** use `_equal_shares`, not `amount / n`, or cents will disagree with the report.
- **Personal vs shared:** personal forces `participants = [payer]`. Budget personal = `is_personal and payer == "self"`. Shared share only if `"self" in participants`.
- **Settlements ≠ spend:** do not fold settlements into consumption budget.
- **Consumption vs cash:** budget tracks your share, not necessarily what you paid out of pocket.
- **Vercel:** production often skips `create_all`; missing ALTER → 500s on User queries selecting new columns.
- **Hero primary figure:** **Left this month** (`monthly_budget − budget_spent`) when a target is set; **Over budget** if spent past target; **My spend this month** if no target. Settlement net is only in **You owe** / **You’re owed**. **Shared bills** = full shared totals (`budget_shared_total`).

## What to pick when stuck

| Symptom | Likely place |
|---------|----------------|
| Wrong split / report totals | `_equal_shares`, `compute_report` |
| Wrong who-owes-whom | `compute_balances`, `compute_pairwise_with_self`, settlement apply |
| UI button does nothing | `id` missing / JS `getElementById` / `onclick` typo in `index.html` |
| Data leaked across users | missing `user_id` filter in model/controller |
| Budget wrong on “All time” | budget computed from period expenses instead of current-month fetch |
| Column does not exist | run `scripts/add_*.sql` |
| Login / admin | `auth_controller`, `User` model, `ADMIN_*` env |

## Budget quick reference

- Column: `users.monthly_budget`
- API: `GET/PUT /api/settings/budget`
- Bootstrap keys: `monthly_budget`, `budget_personal`, `budget_my_shared`, `budget_spent`, `budget_shared_total`
- SQL: `scripts/add_monthly_budget.sql`

## Out of scope unless asked

- Force-push, rewriting unrelated history
- Payment/billing SaaS features
- Rewriting the whole frontend framework
- In-app `/docs` route (docs live in this folder)
