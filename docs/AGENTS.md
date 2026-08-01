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
- **Settlement period scope (balances/report):** linked settlements follow their **expense’s period** (any settlement date); unlinked settlements follow their own `settlement_date`. Use `Settlement.fetch_for_balance_period`, not plain date-filtered `fetch_for_user`, for balance/pairwise math. Settlement **history list** still filters by settlement date.
- **Equal shares:** always use `_equal_shares` in balances, pairwise, outstanding, and report — never `amount / n` (cent drift).
- **General settlement cap:** unlinked POST `/api/settlements` is capped at **the pairwise debt for whichever period the request specifies** (`from`/`to` or `year`/`month` query args, same `_period_bounds()` used by `/api/balances`/`/api/report`); omitting period args caps at all-time.
- **Per-bill outstanding = FIFO ledger, not a single pool:** `Expense._build_settlement_ledger(user_id, payer)` allocates each debtor's all-time unlinked settlements to that payer against their bills **oldest-first**, per debtor. `outstanding_for_expense` / `_has_outstanding` look up `ledger[debtor][expense_id]` instead of `min(expense share left, all-time pairwise debt)`. This matters because a single aggregate pairwise number lets *new* debt accrued after a settle-up make an already-settled old bill look outstanding again (the old bug); the ledger permanently allocates a settle-up to the oldest unpaid bills it actually covered, so those stay settled no matter what debt shows up later. Known limitation: each payer→debtor direction is its own ledger call — it does not net against the reverse direction when two people alternate paying each other.
- **Ledger perf:** `to_dicts_with_outstanding` fetches all-time expenses/settlements **once** and builds one ledger per distinct payer (not once per bill); `bootstrap_payload` reuses its own period-filtered lists as the "all-time" source when the active period is already All time, instead of a second query.
- **Balances Settle button:** only when there is a pairwise balance with that person for the **currently viewed period** (`lastSelfSummary`); amount/From/To come from pairwise, not the person's global net ledger. The frontend must append `periodQuery()` to unlinked `POST /api/settlements` calls so the server validates against the same period being shown — see `quickSettle`/`submitSettlement`.
- **Unlinked settlement date:** when settling from Balances (person mode) with a period other than "All time" selected, `settleDate` defaults inside that period (today if today falls in it, else the period's end date) via `defaultSettleDate()` — otherwise the new row (matched by `settlement_date`) would not be picked up when that period is viewed again.
- **Settled badge:** shared expense rows show an explicit "Settled" tag when `!has_outstanding`, instead of only implying it via the hidden Settle button.
- **Personal vs shared:** personal forces `participants = [payer]`. Budget personal = `is_personal and payer == "self"`. Shared share only if `"self" in participants`.
- **Settlements ≠ spend:** do not fold settlements into consumption budget.
- **Consumption vs cash:** budget tracks your share, not necessarily what you paid out of pocket.
- **Vercel:** production often skips `create_all`; missing ALTER → 500s on User queries selecting new columns.
- **Hero primary figure:** **Left this month** (`monthly_budget − budget_spent`) when a target is set; **Over budget** if spent past target; **My spend this month** if no target. **You owe** / **You’re owed** come from `report.self_summary` (not a client recompute). **Shared bills** = full shared totals (`budget_shared_total`).
- **Settle modal:** expense mode prefills first debtor → payer + amount; Balances person mode: owing → From them/To self, owed → From self/To them; no Settle button on the `self` row; person-mode modal closes after successful Record payment.

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
