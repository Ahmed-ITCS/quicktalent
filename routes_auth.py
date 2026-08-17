import re

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import db as database
from auth_utils import (
    hash_password,
    make_verification_token,
    read_verification_token,
    verify_password,
)
from config import config
from email_service import send_verification_email

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_hr_form(data):
    errors = []
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    company = (data.get("company_name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not company:
        errors.append("Company name is required.")
    if not phone:
        errors.append("Phone number is required.")
    if database.db.get_user_by_email(email):
        errors.append("An account with this email already exists.")
    return errors, {"email": email, "company_name": company, "phone": phone}


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        errors, data = _validate_hr_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=data), 400

        user = database.db.create_user(
            email=data["email"],
            password_hash=hash_password(request.form["password"]),
            company_name=data["company_name"],
            phone=data["phone"],
            role="hr",
            is_verified=False,
        )
        token = make_verification_token(user["email"])
        verify_url = url_for("auth.verify", token=token, _external=True)
        send_verification_email(user["email"], verify_url)
        return render_template("verify_sent.html", email=user["email"])

    return render_template("register.html", form={})


@bp.route("/verify/<token>")
def verify(token):
    email, err = read_verification_token(token)
    if err:
        flash("This verification link is invalid or has expired. Please register again.", "error")
        return redirect(url_for("auth.register"))
    user = database.db.get_user_by_email(email)
    if not user:
        flash("Account not found. Please register.", "error")
        return redirect(url_for("auth.register"))
    if user["is_verified"]:
        flash("Your email is already verified. You can log in.", "success")
        return redirect(url_for("auth.login"))
    database.db.update_user(user["id"], is_verified=True)
    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = database.db.get_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            flash("Invalid email or password.", "error")
            return render_template("login.html", form={"email": email}), 401
        if user["is_blocked"]:
            flash("This account has been blocked. Contact support.", "error")
            return render_template("login.html", form={"email": email}), 403
        if not user["is_verified"]:
            flash("Please verify your email first. Check your inbox.", "error")
            return render_template("login.html", form={"email": email}), 403

        session["user"] = {
            "id": user["id"],
            "email": user["email"],
            "company_name": user["company_name"],
            "phone": user["phone"],
            "role": user["role"],
        }
        session.permanent = True
        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        if user["role"] == "admin":
            return redirect(url_for("admin.overview"))
        return redirect(url_for("hr.dashboard"))

    return render_template("login.html", form={})


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
