from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

page_bp = Blueprint("page", __name__)


@page_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("page.app"))
    return render_template("home.html")


@page_bp.route("/app")
@login_required
def app():
    return render_template("index.html")


@page_bp.route("/robots.txt")
def robots_txt():
    base = request.url_root.rstrip("/")
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Allow: /login",
        "Allow: /register",
        "Disallow: /api/",
        "Disallow: /admin",
        "Disallow: /app",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ])
    return Response(body, mimetype="text/plain")


@page_bp.route("/sitemap.xml")
def sitemap_xml():
    base = request.url_root.rstrip("/")
    urls = [
        f"{base}/",
        f"{base}{url_for('auth.login')}",
        f"{base}{url_for('auth.register')}",
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        parts.append("    <changefreq>monthly</changefreq>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")
    return Response("\n".join(parts), mimetype="application/xml")
