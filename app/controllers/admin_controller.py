from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.user import User
from app.utils.auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    users = User.list_all()
    return render_template("admin/dashboard.html", users=users)


@admin_bp.route("/users")
@login_required
@admin_required
def list_users():
    return jsonify([u.to_dict() for u in User.list_all()])


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "Cannot disable yourself"}), 400
    user = User.toggle_active(user_id)
    if not user:
        return jsonify({"error": "Cannot modify this user"}), 400
    return jsonify(user.to_dict())


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "Cannot delete yourself"}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.role == "admin":
        return jsonify({"error": "Cannot delete admin"}), 400
    User.delete_user(user_id)
    return jsonify({"ok": True})
