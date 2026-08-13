import hmac
import os
import secrets
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db

load_dotenv()

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

# username -> (failed_count, last_failure_epoch)
_failed_logins = {}


def _is_locked(username):
    count, last_ts = _failed_logins.get(username, (0, 0))
    if count < MAX_LOGIN_ATTEMPTS:
        return False
    return (datetime.now(timezone.utc).timestamp() - last_ts) < LOGIN_LOCKOUT_SECONDS


def _register_login_failure(username):
    count, _ = _failed_logins.get(username, (0, 0))
    _failed_logins[username] = (count + 1, datetime.now(timezone.utc).timestamp())


def _clear_login_failures(username):
    _failed_logins.pop(username, None)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    is_dev = os.environ.get("FLASK_ENV") == "development"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = not is_dev

    db.init_db()

    api_key = os.environ.get("CLOUD_API_KEY", "")

    # ---------------- CSRF (minimal, no flask-wtf) ----------------
    # Session-based routes (login/logout/comment save) use a random token
    # stashed in the session and echoed back on POST -- classic double
    # submit. The machine-to-machine /api/sync/* routes are API-key-only
    # (no session cookie), so CSRF doesn't apply to them.

    def _csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = _csrf_token

    def csrf_protect(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            supplied = request.form.get("csrf_token")
            if supplied is None:
                body = request.get_json(silent=True) or {}
                supplied = body.get("csrf_token") or request.headers.get("X-CSRFToken")
            expected = session.get("csrf_token")
            if not supplied or not expected or not hmac.compare_digest(str(supplied), str(expected)):
                return jsonify({"error": "csrf_invalid"}), 400
            return fn(*args, **kwargs)

        return wrapper

    def require_api_key(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            supplied = request.headers.get("X-API-Key", "")
            if not api_key or not hmac.compare_digest(supplied, api_key):
                return jsonify({"error": "unauthorized"}), 401
            return fn(*args, **kwargs)

        return wrapper

    def require_login(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("branch_code"):
                return redirect(url_for("login"))
            return fn(*args, **kwargs)

        return wrapper

    # ---------------- Manager-facing (session auth) ----------------

    @app.route("/")
    def index():
        return redirect(url_for("dashboard") if session.get("branch_code") else url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            supplied_csrf = request.form.get("csrf_token")
            expected_csrf = session.get("csrf_token")
            if not supplied_csrf or not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
                flash("La sesión expiró, intenta de nuevo.", "error")
                return render_template("login.html")
            if _is_locked(username):
                flash("Demasiados intentos fallidos. Intenta de nuevo en unos minutos.", "error")
                return render_template("login.html")
            user = db.get_branch_user_by_username(username)
            if user and check_password_hash(user["password_hash"], password):
                _clear_login_failures(username)
                session.clear()
                session["branch_code"] = user["branch_code"]
                session["username"] = user["username"]
                return redirect(url_for("dashboard"))
            _register_login_failure(username)
            flash("Usuario o contraseña incorrectos.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    @csrf_protect
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @require_login
    def dashboard():
        branch = session["branch_code"]
        clients = db.get_active_clients_by_branch(branch)
        return render_template("dashboard.html", branch=branch, clients=clients)

    @app.route("/api/my/clients/<account>/comment", methods=["POST"])
    @require_login
    @csrf_protect
    def update_comment(account):
        branch = session["branch_code"]
        client = db.get_client_by_account(account)
        if not client:
            return jsonify({"error": "not_found"}), 404
        if client["branch"] != branch:
            return jsonify({"error": "forbidden"}), 403
        data = request.get_json(silent=True) or {}
        comment = (data.get("comment") or "").strip()[:2000]
        status = (data.get("status") or "").strip()[:80]
        db.update_client_comment(account, comment, status, session.get("username"))
        return jsonify({"ok": True})

    @app.route("/api/my/clients/<account>/history")
    @require_login
    def client_history(account):
        branch = session["branch_code"]
        client = db.get_client_by_account(account)
        if not client:
            return jsonify({"error": "not_found"}), 404
        if client["branch"] != branch:
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"history": db.get_comment_history(account)})

    @app.route("/api/my/coverage")
    @require_login
    def my_coverage():
        geojson = db.get_branch_coverage(session["branch_code"])
        return jsonify({"geojson": geojson})

    # ---------------- Machine-to-machine (API key auth) ----------------

    @app.route("/api/sync/push", methods=["POST"])
    @require_api_key
    def sync_push():
        data = request.get_json(silent=True) or {}
        clients = data.get("clients", [])
        upserted, deactivated = db.sync_push_clients(clients)
        return jsonify({"ok": True, "upserted": upserted, "deactivated": deactivated})

    @app.route("/api/sync/comments", methods=["GET"])
    @require_api_key
    def sync_comments():
        since = request.args.get("since")
        comments = db.get_comments_since(since)
        return jsonify({"comments": comments})

    @app.route("/api/sync/push_coverage", methods=["POST"])
    @require_api_key
    def sync_push_coverage():
        data = request.get_json(silent=True) or {}
        branch_code = (data.get("branch_code") or "").strip().upper()
        geojson_obj = data.get("geojson")
        if not branch_code or not isinstance(geojson_obj, dict):
            return jsonify({"error": "branch_code y geojson (objeto) son requeridos"}), 400
        db.upsert_branch_coverage(branch_code, geojson_obj)
        return jsonify({"ok": True, "branch_code": branch_code, "features": len(geojson_obj.get("features", []))})

    @app.route("/api/sync/seed_user", methods=["POST"])
    @require_api_key
    def sync_seed_user():
        """Crea o actualiza el login de una sucursal. Protegido con la misma
        CLOUD_API_KEY que ya usa la sync local -- reemplaza a seed_users.py
        (que asume acceso por Shell, no disponible en el plan Free de Render)."""
        data = request.get_json(silent=True) or {}
        branch_code = (data.get("branch_code") or "").strip().upper()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not branch_code or not username or len(password) < 8:
            return jsonify({"error": "branch_code, username y password (min. 8 caracteres) son requeridos"}), 400
        db.upsert_branch_user(branch_code, username, generate_password_hash(password))
        return jsonify({"ok": True, "branch_code": branch_code, "username": username})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=False)
