from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from app.models.person import Person
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.get_by_username(username)
        if user and user.is_active and user.check_password(password):
            login_user(user)
            next_url = request.args.get("next") or url_for("page.index")
            return redirect(next_url)
        flash("Invalid username or password", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        email = (request.form.get("email") or "").strip() or None
        if len(username) < 2:
            flash("Username must be at least 2 characters", "error")
        elif len(password) < 4:
            flash("Password must be at least 4 characters", "error")
        elif User.get_by_username(username):
            flash("Username already taken", "error")
        else:
            user = User.create(username=username, password=password, email=email)
            Person.add(user.id, username)
            Person.add(user.id, "me")
            login_user(user)
            return redirect(url_for("page.index"))
    return render_template("register.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
