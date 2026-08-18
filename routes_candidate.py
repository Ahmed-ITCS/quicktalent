from flask import Blueprint, render_template

import db as database
from auth_utils import read_approval_token

bp = Blueprint("candidate", __name__)


def _load(token):
    hr_id, candidate_id = read_approval_token(token)
    if not hr_id or not candidate_id:
        return None
    contact = database.db.get_contact(hr_id, candidate_id)
    if not contact:
        return None
    return {
        "contact": contact,
        "candidate": database.db.get_candidate(candidate_id),
        "hr": database.db.get_user_by_id(hr_id),
    }


def _state(status):
    if status == "approved":
        return "approved"
    if status == "declined":
        return "declined"
    if status == "closed":
        return "closed"
    return "pending"


@bp.route("/contact-requests/<token>")
def decision(token):
    item = _load(token)
    if not item:
        return render_template("approval.html", state="invalid"), 404
    return render_template("approval.html", state=_state(item["contact"]["status"]), item=item, token=token)


@bp.route("/contact-requests/<token>/approve", methods=["POST"])
def approve(token):
    item = _load(token)
    if not item:
        return render_template("approval.html", state="invalid"), 404
    if item["contact"]["status"] == "requested":
        try:
            database.db.set_contact_status(item["contact"]["id"], "approved")
        except ValueError as exc:
            return render_template("approval.html", state="invalid",
                                   error=str(exc)), 500
        item["contact"]["status"] = "approved"
    return render_template("approval.html", state=_state(item["contact"]["status"]), item=item, token=token)


@bp.route("/contact-requests/<token>/decline", methods=["POST"])
def decline(token):
    item = _load(token)
    if not item:
        return render_template("approval.html", state="invalid"), 404
    if item["contact"]["status"] == "requested":
        try:
            database.db.set_contact_status(item["contact"]["id"], "declined")
        except ValueError as exc:
            return render_template("approval.html", state="invalid",
                                   error=str(exc)), 500
        item["contact"]["status"] = "declined"
    return render_template("approval.html", state=_state(item["contact"]["status"]), item=item, token=token)