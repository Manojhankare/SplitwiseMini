from flask import Blueprint, render_template

from app.utils.auth import requires_basic_auth

page_bp = Blueprint("page", __name__)


@page_bp.route("/")
@requires_basic_auth
def index():
    return render_template("index.html")
