from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app.models.person import Person
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(fallback=None):
    """Only allow same-site relative redirects (blocks open redirects)."""
    fallback = fallback or url_for("page.app")
    next_url = (request.args.get("next") or "").strip()
    if not next_url.startswith("/") or next_url.startswith("//"):
        return fallback
    return next_url


def _login_persistent(user):
    """Keep the user signed in for SESSION_DAYS (session + remember cookie)."""
    session.permanent = True
    login_user(user, remember=True, duration=current_app.config.get("REMEMBER_COOKIE_DURATION"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Swipe-back / history to /login while signed in should return to the app,
    # not show the login form (session is still valid — this is not a logout).
    if current_user.is_authenticated:
        return redirect(url_for("page.app"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.get_by_username(username)
        if user and user.is_active and user.check_password(password):
            _login_persistent(user)
            return redirect(_safe_next_url())
        flash("Invalid username or password", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("page.app"))

    form = {"username": "", "email": ""}
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        email = (request.form.get("email") or "").strip().lower()
        form["username"] = username
        form["email"] = email

        if len(username) < 2:
            flash("Username must be at least 2 characters", "error")
        elif User.get_by_username(username):
            flash("Username already taken", "error")
        elif not email:
            flash("Email is required", "error")
        elif "@" not in email or "." not in email.split("@")[-1]:
            flash("Enter a valid email address", "error")
        elif User.get_by_email(email):
            flash("Email already registered", "error")
        elif len(password) < 4:
            flash("Password must be at least 4 characters", "error")
        else:
            user = User.create(username=username, password=password, email=email)
            Person.add(user.id, username)
            Person.add(user.id, "me")
            _login_persistent(user)
            return redirect(url_for("page.app"))
    return render_template("register.html", form=form)


@auth_bp.route("/api/check-username")
def check_username():
    """Public availability check for the register form (live username checker)."""
    username = (request.args.get("username") or "").strip().lower()
    if len(username) < 2:
        return jsonify({"ok": True, "available": False, "reason": "too_short"})
    if User.get_by_username(username):
        return jsonify({"ok": True, "available": False, "reason": "taken"})
    return jsonify({"ok": True, "available": True, "reason": None})


@auth_bp.route("/api/check-email")
def check_email():
    """Public availability check for the register form (live email checker)."""
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": True, "available": False, "reason": "empty"})
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": True, "available": False, "reason": "invalid"})
    if User.get_by_email(email):
        return jsonify({"ok": True, "available": False, "reason": "taken"})
    return jsonify({"ok": True, "available": True, "reason": None})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
