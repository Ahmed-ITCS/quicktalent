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
from auth_utils import admin_required, mask_email, mask_phone

bp = Blueprint("admin", __name__)


def _contacted_by_counts():
    counts = {}
    for item in database.db.list_all_contacts():
        cid = item["candidate"]["id"]
        counts.setdefault(cid, 0)
        counts[cid] += 1
    return counts


@bp.route("/admin")
@admin_required
def overview():
    stats = {
        "candidates_total": database.db.count_candidates(),
        **database.db.candidate_counts_by_status(),
        "hr_total": database.db.count_users(),
        "contacts_total": database.db.count_contacts(),
    }
    recent_contacts = database.db.list_all_contacts()[:8]
    recent_candidates = database.db.list_all_candidates()[:8]
    return render_template(
        "admin/overview.html",
        stats=stats,
        recent_contacts=recent_contacts,
        recent_candidates=recent_candidates,
        mask_email=mask_email,
        mask_phone=mask_phone,
    )


@bp.route("/admin/candidates")
@admin_required
def candidates():
    rows = database.db.list_all_candidates()
    counts = _contacted_by_counts()
    return render_template(
        "admin/candidates.html",
        rows=rows,
        counts=counts,
        mask_email=mask_email,
        mask_phone=mask_phone,
    )


@bp.route("/admin/candidates/<candidate_id>/status", methods=["POST"])
@admin_required
def set_status(candidate_id):
    status = request.form.get("status") or ""
    candidate = database.db.get_candidate(candidate_id)
    if not candidate:
        abort(404)
    if status not in ("available", "employed", "closed"):
        flash("Invalid status.", "error")
        return redirect(url_for("admin.candidates"))
    database.db.set_candidate_status(candidate_id, status)
    flash(f"{candidate['name']} → {status.title()}", "success")
    return redirect(url_for("admin.candidates"))


@bp.route("/admin/candidates/<candidate_id>/edit", methods=["POST"])
@admin_required
def edit_candidate(candidate_id):
    candidate = database.db.get_candidate(candidate_id)
    if not candidate:
        abort(404)
    fields = {k: (request.form.get(k) or "").strip() for k in ("name", "email", "phone", "job_title", "location", "linkedin_url", "last_employer")}
    if not fields["name"]:
        flash("Name is required.", "error")
        return redirect(url_for("admin.candidates"))
    database.db.update_candidate(candidate_id, **fields)
    flash(f"{fields['name']} updated.", "success")
    return redirect(url_for("admin.candidates"))


@bp.route("/admin/candidates/<candidate_id>/delete", methods=["POST"])
@admin_required
def delete_candidate(candidate_id):
    candidate = database.db.get_candidate(candidate_id)
    if not candidate:
        abort(404)
    database.db.delete_candidate(candidate_id)
    flash(f"{candidate['name']} deleted.", "success")
    return redirect(url_for("admin.candidates"))


@bp.route("/admin/hr")
@admin_required
def hr_accounts():
    users = database.db.list_users()
    counts = {u["id"]: 0 for u in users}
    for item in database.db.list_all_contacts():
        if item["hr"] and item["hr"]["id"] in counts:
            counts[item["hr"]["id"]] += 1
    return render_template("admin/hr.html", users=users, counts=counts, mask_email=mask_email, mask_phone=mask_phone)


@bp.route("/admin/hr/<user_id>/action", methods=["POST"])
@admin_required
def hr_action(user_id):
    action = request.form.get("action") or ""
    user = database.db.get_user_by_id(user_id)
    if not user:
        abort(404)
    if user["role"] == "admin":
        flash("Cannot modify the god account.", "error")
        return redirect(url_for("admin.hr_accounts"))

    if action == "verify":
        database.db.update_user(user_id, is_verified=True)
        flash(f"{user['email']} verified.", "success")
    elif action == "block":
        database.db.update_user(user_id, is_blocked=True)
        flash(f"{user['email']} blocked.", "success")
    elif action == "unblock":
        database.db.update_user(user_id, is_blocked=False)
        flash(f"{user['email']} unblocked.", "success")
    elif action == "delete":
        database.db.delete_user(user_id)
        flash(f"{user['email']} deleted.", "success")
    else:
        flash("Unknown action.", "error")
    return redirect(url_for("admin.hr_accounts"))


@bp.route("/admin/contacts")
@admin_required
def contacts():
    items = database.db.list_all_contacts()
    return render_template(
        "admin/contacts.html",
        items=items,
        mask_email=mask_email,
        mask_phone=mask_phone,
    )


@bp.route("/admin/contacts/<contact_id>/delete", methods=["POST"])
@admin_required
def delete_contact(contact_id):
    database.db.delete_contact(contact_id)
    flash("Contact record deleted.", "success")
    return redirect(url_for("admin.contacts"))
