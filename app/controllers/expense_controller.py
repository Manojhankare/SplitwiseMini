from calendar import monthrange
from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.models.expense import Expense
from app.models.group import Group
from app.models.person import Person
from app.models.settlement import Settlement
from app.models.user import User

expense_bp = Blueprint("expense", __name__, url_prefix="/api")


def _parse_expense_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value))


def _parse_period_args(req):
    """Parse period query args.

    Returns ((start, end) | None, error_message | None).
    None period means all-time. Prefer from/to over year/month.
    """
    from_s = (req.args.get("from") or "").strip()
    to_s = (req.args.get("to") or "").strip()
    year_s = (req.args.get("year") or "").strip()
    month_s = (req.args.get("month") or "").strip()

    if from_s or to_s:
        if not from_s or not to_s:
            return None, "both from and to are required"
        try:
            start = date.fromisoformat(from_s)
            end = date.fromisoformat(to_s)
        except ValueError:
            return None, "invalid from/to date"
        if start > end:
            return None, "from must be on or before to"
        return (start, end), None

    if year_s or month_s:
        if not year_s or not month_s:
            return None, "both year and month are required"
        try:
            year = int(year_s)
            month = int(month_s)
            if month < 1 or month > 12:
                raise ValueError("month out of range")
            start = date(year, month, 1)
            end = date(year, month, monthrange(year, month)[1])
        except ValueError:
            return None, "invalid year/month"
        return (start, end), None

    return None, None


def _period_bounds():
    period, err = _parse_period_args(request)
    if err:
        return None, (jsonify({"error": err}), 400)
    if period is None:
        return (None, None), None
    return period, None


def _expense_fields_from_body(data):
    """Parse/validate expense JSON body. Returns (fields_dict, error_response)."""
    description = (data.get("description") or "").strip()
    if not description:
        return None, (jsonify({"error": "description is required"}), 400)
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return None, (jsonify({"error": "amount must be a number"}), 400)
    if amount <= 0:
        return None, (jsonify({"error": "amount must be positive"}), 400)

    payer = (data.get("payer") or "").strip().lower() or "self"
    is_personal = bool(data.get("is_personal"))
    if is_personal:
        participants = [payer]
    else:
        participants = [p.strip().lower() for p in data.get("participants", []) if p.strip()]
        if not participants:
            return None, (jsonify({"error": "select at least one person to split with"}), 400)

    expense_date = _parse_expense_date(data.get("date"))
    return {
        "description": description,
        "amount": amount,
        "payer": payer,
        "participants": participants,
        "expense_date": expense_date,
        "is_personal": is_personal,
    }, None


@expense_bp.route("/add", methods=["POST"])
@login_required
def add_expense():
    data = request.get_json(force=True, silent=True) or {}
    fields, err = _expense_fields_from_body(data)
    if err:
        return err
    user_id = current_user.id
    try:
        exp = Expense.create(
            user_id,
            fields["description"],
            fields["amount"],
            fields["payer"],
            fields["participants"],
            expense_date=fields["expense_date"],
            is_personal=fields["is_personal"],
        )
        Person.register_names(user_id, fields["payer"], *fields["participants"])
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500

    return jsonify(exp.to_dict())


@expense_bp.route("/expenses/<int:expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):
    data = request.get_json(force=True, silent=True) or {}
    fields, err = _expense_fields_from_body(data)
    if err:
        return err
    user_id = current_user.id
    try:
        exp = Expense.update(
            expense_id,
            user_id,
            fields["description"],
            fields["amount"],
            fields["payer"],
            fields["participants"],
            expense_date=fields["expense_date"],
            is_personal=fields["is_personal"],
        )
        if not exp:
            return jsonify({"error": "expense not found"}), 404
        Person.register_names(user_id, fields["payer"], *fields["participants"])
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500

    return jsonify(exp.to_dict())


@expense_bp.route("/expenses", methods=["GET"])
@login_required
def list_expenses():
    bounds, err = _period_bounds()
    if err:
        return err
    start_date, end_date = bounds
    try:
        return jsonify(Expense.list_all(current_user.id, start_date=start_date, end_date=end_date))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/bootstrap", methods=["GET"])
@login_required
def bootstrap():
    filter_type = request.args.get("filter", "all")
    if filter_type not in ("all", "shared", "personal"):
        filter_type = "all"
    bounds, err = _period_bounds()
    if err:
        return err
    start_date, end_date = bounds
    try:
        return jsonify(
            Expense.bootstrap_payload(
                current_user.id,
                filter_type=filter_type,
                start_date=start_date,
                end_date=end_date,
            )
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/balances", methods=["GET"])
@login_required
def balances():
    bounds, err = _period_bounds()
    if err:
        return err
    start_date, end_date = bounds
    try:
        expenses = Expense.fetch_for_user(current_user.id, start_date=start_date, end_date=end_date)
        settlements = Settlement.fetch_for_user(current_user.id, start_date=start_date, end_date=end_date)
        return jsonify(
            Expense.compute_balances(
                current_user.id, expenses=expenses, settlements=settlements
            )
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/report", methods=["GET"])
@login_required
def report():
    filter_type = request.args.get("filter", "all")
    if filter_type not in ("all", "shared", "personal"):
        filter_type = "all"
    bounds, err = _period_bounds()
    if err:
        return err
    start_date, end_date = bounds
    try:
        expenses = Expense.fetch_for_user(current_user.id, start_date=start_date, end_date=end_date)
        settlements = Settlement.fetch_for_user(current_user.id, start_date=start_date, end_date=end_date)
        return jsonify(
            Expense.compute_report(
                current_user.id,
                filter_type=filter_type,
                expenses=expenses,
                settlements=settlements,
            )
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/people", methods=["GET"])
@login_required
def list_people():
    try:
        return jsonify(Person.list_all(current_user.id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/people", methods=["POST"])
@login_required
def add_person():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        person = Person.add(current_user.id, name)
        if not person:
            return jsonify({"error": "invalid name"}), 400
        return jsonify(person.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/people/<int:person_id>", methods=["DELETE"])
@login_required
def delete_person(person_id):
    try:
        Person.delete(person_id, current_user.id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/groups", methods=["GET"])
@login_required
def list_groups():
    try:
        return jsonify(Group.list_all(current_user.id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/groups", methods=["POST"])
@login_required
def create_group():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    member_ids = data.get("member_ids") or []
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not member_ids:
        return jsonify({"error": "at least one member is required"}), 400
    try:
        group = Group.create(current_user.id, name, member_ids)
        return jsonify(group.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/groups/<int:group_id>", methods=["PUT"])
@login_required
def update_group(group_id):
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    member_ids = data.get("member_ids")
    try:
        group = Group.update(group_id, current_user.id, name=name, member_ids=member_ids)
        if not group:
            return jsonify({"error": "group not found"}), 404
        return jsonify(group.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/groups/<int:group_id>", methods=["DELETE"])
@login_required
def delete_group(group_id):
    try:
        Group.delete(group_id, current_user.id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/delete/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):
    try:
        Expense.delete(expense_id, current_user.id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/settlements", methods=["GET"])
@login_required
def list_settlements():
    bounds, err = _period_bounds()
    if err:
        return err
    start_date, end_date = bounds
    try:
        return jsonify(Settlement.list_all(current_user.id, start_date=start_date, end_date=end_date))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/settlements", methods=["POST"])
@login_required
def create_settlement():
    data = request.get_json(force=True, silent=True) or {}
    from_person = (data.get("from_person") or "").strip().lower()
    to_person = (data.get("to_person") or "").strip().lower()
    if not from_person or not to_person:
        return jsonify({"error": "from_person and to_person are required"}), 400
    if from_person == to_person:
        return jsonify({"error": "from_person and to_person must differ"}), 400
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be positive"}), 400

    expense_id = data.get("expense_id")
    if expense_id is not None:
        try:
            expense_id = int(expense_id)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid expense_id"}), 400
        expense = Expense.get_for_user(expense_id, current_user.id)
        if not expense:
            return jsonify({"error": "expense not found"}), 404
        if expense.is_personal:
            return jsonify({"error": "cannot settle a personal expense"}), 400
        outstanding = Expense.outstanding_for_expense(expense)["outstanding"]
        max_owed = outstanding.get(from_person, 0.0)
        if amount > max_owed + 0.001:
            return jsonify({"error": f"amount exceeds outstanding share ({max_owed:.2f})"}), 400
        if to_person != expense.payer:
            return jsonify({"error": f"to_person must be the expense payer ({expense.payer})"}), 400
    else:
        expense_id = None

    settlement_date = _parse_expense_date(data.get("date"))
    note = (data.get("note") or "").strip() or None

    try:
        settlement = Settlement.create(
            current_user.id,
            from_person,
            to_person,
            amount,
            expense_id=expense_id,
            settlement_date=settlement_date,
            note=note,
        )
        Person.register_names(current_user.id, from_person, to_person)
        return jsonify(settlement.to_dict())
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500


@expense_bp.route("/settlements/<int:settlement_id>", methods=["DELETE"])
@login_required
def delete_settlement(settlement_id):
    try:
        Settlement.delete(settlement_id, current_user.id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/expenses/<int:expense_id>/outstanding", methods=["GET"])
@login_required
def expense_outstanding(expense_id):
    try:
        expense = Expense.get_for_user(expense_id, current_user.id)
        if not expense:
            return jsonify({"error": "expense not found"}), 404
        return jsonify(Expense.outstanding_for_expense(expense))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/settings/budget", methods=["GET"])
@login_required
def get_budget():
    try:
        budget = current_user.monthly_budget
        return jsonify({
            "monthly_budget": float(budget) if budget is not None else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/settings/budget", methods=["PUT"])
@login_required
def put_budget():
    data = request.get_json(silent=True) or {}
    if "monthly_budget" not in data:
        return jsonify({"error": "monthly_budget is required (number or null)"}), 400

    raw = data.get("monthly_budget")
    if raw is None or raw == "":
        amount = None
    else:
        try:
            amount = float(raw)
        except (TypeError, ValueError):
            return jsonify({"error": "monthly_budget must be a number or null"}), 400
        if amount < 0:
            return jsonify({"error": "monthly_budget cannot be negative"}), 400
        if amount == 0:
            amount = None
        else:
            amount = round(amount, 2)

    try:
        user = User.set_monthly_budget(current_user.id, amount)
        if not user:
            return jsonify({"error": "user not found"}), 404
        return jsonify({
            "monthly_budget": float(user.monthly_budget) if user.monthly_budget is not None else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
