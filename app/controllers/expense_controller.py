from datetime import date

from flask import Blueprint, current_app, jsonify, request

from app.models.expense import Expense
from app.models.person import Person
from app.services.ai_service import parse_expense_with_ai

expense_bp = Blueprint("expense", __name__, url_prefix="/api")


def _parse_expense_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value))


def _register_expense_names(payer, participants):
    Person.register_names(payer, *participants)


@expense_bp.route("/add", methods=["POST"])
def add_expense():
    data = request.get_json(force=True, silent=True) or {}

    if data.get("text"):
        text = data["text"].strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        if not current_app.config["GROQ_API_KEY"]:
            return jsonify({"error": "GROQ_API_KEY is not set on the server"}), 500
        try:
            parsed = parse_expense_with_ai(text)
        except Exception as e:
            return jsonify({"error": f"AI parsing failed: {e}"}), 500
        is_personal = len(parsed.get("participants", [])) == 1
        expense_date = _parse_expense_date(data.get("date"))
    else:
        description = (data.get("description") or "").strip()
        if not description:
            return jsonify({"error": "description is required"}), 400
        try:
            amount = float(data.get("amount"))
        except (TypeError, ValueError):
            return jsonify({"error": "amount must be a number"}), 400
        if amount <= 0:
            return jsonify({"error": "amount must be positive"}), 400

        payer = (data.get("payer") or "").strip().lower()
        if not payer:
            return jsonify({"error": "payer is required"}), 400

        is_personal = bool(data.get("is_personal"))
        if is_personal:
            participants = [payer]
        else:
            participants = [p.strip().lower() for p in data.get("participants", []) if p.strip()]
            if not participants:
                return jsonify({"error": "at least one participant is required"}), 400
            if payer not in participants:
                participants.append(payer)

        parsed = {
            "description": description,
            "amount": amount,
            "payer": payer,
            "participants": participants,
        }
        expense_date = _parse_expense_date(data.get("date"))

    try:
        exp = Expense.create(
            parsed["description"],
            parsed["amount"],
            parsed["payer"],
            parsed["participants"],
            expense_date=expense_date,
            is_personal=is_personal,
        )
        _register_expense_names(parsed["payer"], parsed["participants"])
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500

    result = exp.to_dict()
    return jsonify(result)


@expense_bp.route("/expenses", methods=["GET"])
def list_expenses():
    try:
        return jsonify(Expense.list_all())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/balances", methods=["GET"])
def balances():
    try:
        return jsonify(Expense.compute_balances())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/report", methods=["GET"])
def report():
    filter_type = request.args.get("filter", "all")
    if filter_type not in ("all", "shared", "personal"):
        filter_type = "all"
    try:
        return jsonify(Expense.compute_report(filter_type=filter_type))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/people", methods=["GET"])
def list_people():
    try:
        return jsonify(Person.list_all())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/people", methods=["POST"])
def add_person():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        person = Person.add(name)
        if not person:
            return jsonify({"error": "invalid name"}), 400
        return jsonify(person.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/people/<int:person_id>", methods=["DELETE"])
def delete_person(person_id):
    try:
        Person.delete(person_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/delete/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    try:
        Expense.delete(expense_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
