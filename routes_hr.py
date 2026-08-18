from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

import db as database
from auth_utils import current_user, hash_password, login_required, make_approval_token, mask_email, mask_phone, verify_password
from email_service import send_contact_email, send_status_email

bp = Blueprint("hr", __name__)

PER_PAGE = 12


def _approval_base():
    proto = request.headers.get("X-Forwarded-Proto") or request.scheme
    return f"{proto}://{request.host}".rstrip("/")


def _filters_from_args():
    def _num(key):
        try:
            return float(request.args.get(key))
        except (TypeError, ValueError):
            return None

    return {
        "q": (request.args.get("q") or "").strip(),
        "job_title": (request.args.get("job_title") or "").strip(),
        "city": (request.args.get("city") or "").strip(),
        "skill": (request.args.get("skill") or "").strip(),
        "min_years": _num("min_years"),
        "max_years": _num("max_years"),
        "status": (request.args.get("status") or "").strip(),
    }


@bp.route("/dashboard")
@login_required
def dashboard():
    return redirect(url_for("hr.browse"))


@bp.route("/candidates")
@login_required
def browse():
    user = current_user()
    filters = _filters_from_args()
    sort = request.args.get("sort") or "newest"
    page = max(request.args.get("page", 1, type=int), 1)

    rows, total = database.db.search_candidates(filters, limit=PER_PAGE, offset=(page - 1) * PER_PAGE, sort=sort)
    pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    page = min(page, pages)

    my_contacts = {
        item["candidate"]["id"]
        for item in database.db.list_contacts_for_hr(user["id"])
    }

    return render_template(
        "candidates.html",
        rows=rows,
        filters=filters,
        sort=sort,
        page=page,
        pages=pages,
        total=total,
        my_contacts=my_contacts,
        job_titles=database.db.distinct_values("job_title", 12),
        cities=database.db.distinct_values("location", 12),
        mask_email=mask_email,
        mask_phone=mask_phone,
    )


@bp.route("/candidates/<candidate_id>")
@login_required
def candidate_detail(candidate_id):
    user = current_user()
    candidate = database.db.get_candidate(candidate_id)
    if not candidate:
        abort(404)
    contact = database.db.get_contact(user["id"], candidate_id)
    resume = database.db.resume_url(candidate)
    return render_template(
        "candidate_detail.html",
        candidate=candidate,
        contact=contact,
        resume=resume,
        mask_email=mask_email,
        mask_phone=mask_phone,
    )


@bp.route("/candidates/<candidate_id>/contact", methods=["POST"])
@login_required
def contact(candidate_id):
    user = current_user()
    candidate = database.db.get_candidate(candidate_id)
    if not candidate:
        abort(404)
    if candidate["status"] != "available":
        flash(f"This candidate is not available ({candidate['status']}).", "error")
        return redirect(url_for("hr.candidate_detail", candidate_id=candidate_id))

    contact = database.db.get_contact(user["id"], candidate_id)
    if not contact:
        token = make_approval_token(user["id"], candidate_id)
        try:
            contact = database.db.create_contact(user["id"], candidate_id)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("hr.candidate_detail", candidate_id=candidate_id))
        flash(
            "Request sent! The candidate will approve before your details unlock.",
            "success",
        )
        if candidate["email"]:
            send_contact_email(
                candidate_name=candidate["name"],
                candidate_email=candidate["email"],
                hr=user,
                job_title=candidate["job_title"],
                approval_url=f"{_approval_base()}/contact-requests/{token}",
            )
    else:
        flash("You already have this candidate in your contacts.", "info")
    return redirect(url_for("hr.contacts"))


@bp.route("/contacts/<contact_id>/resend", methods=["POST"])
@login_required
def resend_contact_request(contact_id):
    user = current_user()
    for item in database.db.list_contacts_for_hr(user["id"]):
        if item["contact"]["id"] != contact_id:
            continue
        contact = item["contact"]
        if contact["status"] not in ("requested", "declined"):
            flash("This request isn't waiting for approval anymore.", "error")
            return redirect(url_for("hr.contacts"))
        try:
            database.db.set_contact_status(contact_id, "requested")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("hr.contacts"))
        token = make_approval_token(user["id"], item["candidate"]["id"])
        if item["candidate"]["email"]:
            send_contact_email(
                candidate_name=item["candidate"]["name"],
                candidate_email=item["candidate"]["email"],
                hr=user,
                job_title=item["candidate"]["job_title"],
                approval_url=f"{_approval_base()}/contact-requests/{token}",
            )
            flash(f"Request re-sent to {item['candidate']['name']}.", "success")
        else:
            flash("No email on file for this candidate.", "error")
        return redirect(url_for("hr.contacts"))
    abort(404)


@bp.route("/contacts")
@login_required
def contacts():
    user = current_user()
    items = database.db.list_contacts_for_hr(user["id"])
    return render_template("contacts.html", items=items, mask_email=mask_email, mask_phone=mask_phone)


@bp.route("/contacts/<contact_id>/status", methods=["POST"])
@login_required
def set_candidate_status(contact_id):
    user = current_user()
    status = request.form.get("status") or ""
    if status not in ("available", "employed", "closed"):
        flash("Invalid status.", "error")
        return redirect(url_for("hr.contacts"))

    for item in database.db.list_contacts_for_hr(user["id"]):
        if item["contact"]["id"] == contact_id:
            database.db.set_candidate_status(item["candidate"]["id"], status)
            database.db.set_contact_status(contact_id, "closed" if status in ("employed", "closed") else "requested")
            if item["candidate"]["email"]:
                send_status_email(item["candidate"]["name"], item["candidate"]["email"], user, status)
            flash(
                f"{item['candidate']['name']} marked as {status.title()} and notified by email.",
                "success",
            )
            return redirect(url_for("hr.contacts"))
    abort(404)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    if request.method == "POST":
        company_name = (request.form.get("company_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if not company_name:
            flash("Company name is required.", "error")
            return render_template("settings.html", user=user), 400
        database.db.update_user(user["id"], company_name=company_name, phone=phone)
        user["company_name"] = company_name
        user["phone"] = phone
        session_user = current_user()
        session_user["company_name"] = company_name
        session_user["phone"] = phone
        from flask import session

        session["user"] = session_user
        flash("Settings updated.", "success")
        return redirect(url_for("hr.settings"))

    return render_template("settings.html", user=user)


@bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    user = current_user()
    old = request.form.get("old_password") or ""
    new = request.form.get("new_password") or ""
    stored = database.db.get_user_by_id(user["id"])
    if not verify_password(old, stored["password_hash"]):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("hr.settings"))
    if len(new) < 8:
        flash("New password must be at least 8 characters.", "error")
        return redirect(url_for("hr.settings"))
    database.db.update_user(user["id"], password_hash=hash_password(new))
    flash("Password changed.", "success")
    return redirect(url_for("hr.settings"))
