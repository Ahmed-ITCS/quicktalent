from functools import wraps

from flask import abort, redirect, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from config import config

VERIFY_MAX_AGE = 60 * 60 * 24  # 24h


def get_serializer():
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="email-verify")


def make_verification_token(email):
    return get_serializer().dumps(email)


def read_verification_token(token):
    try:
        return get_serializer().loads(token, max_age=VERIFY_MAX_AGE), None
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    except Exception:
        return None, "invalid"


def _approval_serializer():
    return URLSafeSerializer(config.SECRET_KEY, salt="candidate-approval")


def make_approval_token(hr_id, candidate_id):
    """Stateless signed token for a candidate's approve/decline link (no DB storage)."""
    return _approval_serializer().dumps({"hr_id": hr_id, "candidate_id": candidate_id})


def read_approval_token(token):
    try:
        data = _approval_serializer().loads(token)
        return data.get("hr_id"), data.get("candidate_id")
    except BadSignature:
        return None, None
    except Exception:
        return None, None


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


def current_user():
    return session.get("user")


def is_admin():
    u = current_user()
    return bool(u and u.get("role") == "admin")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth.login", next=__import__("flask").request.path))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth.login", next=__import__("flask").request.path))
        if not is_admin():
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def mask_email(email):
    if not email or "@" not in email:
        return "•••@•••"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def mask_phone(phone):
    if not phone:
        return ""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
