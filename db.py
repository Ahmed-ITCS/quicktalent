"""Data access layer.

Three interchangeable backends (selected at boot, highest priority first):
1. Supabase (Postgres via PostgREST)  — when SUPABASE_URL/KEY are configured
2. Airtable                          — when AIRTABLE_API_KEY/AIRTABLE_BASE_ID are configured
3. SQLite dev fallback               — otherwise (auto-seeded demo data)

All backends expose the same interface; routes are backend-agnostic.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from config import config

# ---------------------------------------------------------------------------
# Candidate schema resolution (Supabase mode): logical -> possible column names
# ---------------------------------------------------------------------------
CANDIDATE_FIELDS = {
    "name": ["name", "full_name", "candidate_name"],
    "email": ["email", "candidate_email"],
    "phone": ["phone", "mobile", "contact_phone", "contact_number"],
    "job_title": ["job_title", "title", "current_title", "desired_title"],
    "location": ["location", "city", "city_location", "current_location"],
    "linkedin_url": ["linkedin_url", "linkedin", "linkedin_profile_url"],
    "skills": ["skills", "tech_skills", "technologies", "skills_tech", "tech_stack"],
    "years_experience": [
        "years_experience",
        "years_of_experience",
        "experience_years",
        "years_exp",
        "experience",
    ],
    "last_employer": ["last_employer", "previous_employer", "employer", "last_company"],
    "resume_url": ["resume_url", "resume", "resume_path", "cv_url", "cv"],
    "status": ["status", "candidate_status", "employment_status"],
}

# Airtable canonical field names (override via env, see config.AIR_FIELDS)
AIR = config.AIR_FIELDS
AIR_HR = config.AIR_HR_FIELDS
AIR_CONTACT = config.AIR_CONTACT_FIELDS

DEV_DB_PATH = os.path.join(os.path.dirname(__file__), "var", "dev.db")


# ---------------------------------------------------------------------------
# Shared normalization helpers
# ---------------------------------------------------------------------------
def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _normalize_candidate(fields, raw_id, created_at):
    """Map a raw candidate fields-dict (keyed by logical names) to a canonical dict."""
    out = {"raw": fields}
    for logical in AIR:
        value = fields.get(logical)
        if logical == "skills":
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    value = parsed if isinstance(parsed, list) else [value]
                except Exception:
                    value = [s.strip() for s in value.split(",") if s.strip()]
            elif value is None:
                value = []
            out["skills"] = value
        else:
            out[logical] = value
    out["id"] = raw_id
    status = (out.get("status") or "available").lower()
    if status not in ("available", "employed", "closed"):
        status = "available"
    out["status"] = status
    try:
        out["years_experience"] = (
            float(out["years_experience"]) if out["years_experience"] not in (None, "") else None
        )
    except (TypeError, ValueError):
        out["years_experience"] = None
    out["created_at"] = _iso(created_at)
    return out


class _BaseBackend:
    @property
    def is_supabase(self):
        return False

    @property
    def is_airtable(self):
        return False

    def now_iso(self):
        return datetime.now(timezone.utc).isoformat()

    def normalize_candidate(self, row):
        raise NotImplementedError


# ===========================================================================
# Supabase backend
# ===========================================================================
class SupabaseBackend(_BaseBackend):
    def __init__(self):
        from supabase import create_client

        self._supa = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        self._cols = None

    @property
    def is_supabase(self):
        return True

    # -------------------------------------------------------- candidate cols
    def candidate_columns(self):
        if self._cols is not None:
            return self._cols
        data = self._supa.table("candidates").select("*").limit(1).execute().data
        self._cols = list(data[0].keys()) if data else []
        return self._cols

    def resolve_col(self, logical):
        cols = self.candidate_columns()
        for candidate in CANDIDATE_FIELDS[logical]:
            if candidate in cols:
                return candidate
        return None

    def normalize_candidate(self, row):
        if row is None:
            return None
        raw = dict(row) if not isinstance(row, dict) else row
        fields = {logical: (raw.get(col) if (col := self.resolve_col(logical)) else None) for logical in AIR}
        return _normalize_candidate(fields, raw.get("id"), raw.get("created_at"))

    # --------------------------------------------------------------- users
    def create_user(self, email, password_hash, company_name, phone, role="hr", is_verified=False):
        row = (
            self._supa.table("hr_accounts")
            .insert(
                {
                    "email": email,
                    "password_hash": password_hash,
                    "company_name": company_name,
                    "phone": phone or "",
                    "role": role,
                    "is_verified": is_verified,
                    "is_blocked": False,
                    "created_at": self.now_iso(),
                }
            )
            .execute()
            .data[0]
        )
        return self._user_from_row(row)

    def _user_from_row(self, row):
        row = dict(row) if not isinstance(row, dict) else row
        return {
            "id": row["id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "company_name": row["company_name"],
            "phone": row.get("phone") or "",
            "role": row.get("role") or "hr",
            "is_verified": bool(row.get("is_verified")),
            "is_blocked": bool(row.get("is_blocked")),
            "created_at": row.get("created_at"),
        }

    def get_user_by_email(self, email):
        rows = self._supa.table("hr_accounts").select("*").eq("email", (email or "").strip().lower()).execute().data
        return self._user_from_row(rows[0]) if rows else None

    def get_user_by_id(self, user_id):
        rows = self._supa.table("hr_accounts").select("*").eq("id", user_id).execute().data
        return self._user_from_row(rows[0]) if rows else None

    def update_user(self, user_id, **fields):
        allowed = {"company_name", "phone", "password_hash", "is_verified", "is_blocked", "role"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if updates:
            self._supa.table("hr_accounts").update(updates).eq("id", user_id).execute()

    def list_users(self):
        rows = self._supa.table("hr_accounts").select("*").order("created_at").execute().data
        return [self._user_from_row(r) for r in rows]

    def delete_user(self, user_id):
        self._supa.table("hr_accounts").delete().eq("id", user_id).execute()

    def count_users(self):
        data = self._supa.table("hr_accounts").select("id", count="exact").execute()
        return data.count if data.count is not None else len(data.data)

    # ----------------------------------------------------------- candidates
    def search_candidates(self, filters, limit=12, offset=0, sort="newest"):
        f = filters or {}
        q = self._supa.table("candidates").select("*", count="exact")
        name_col = self.resolve_col("name")
        title_col = self.resolve_col("job_title")
        city_col = self.resolve_col("location")
        years_col = self.resolve_col("years_experience")
        status_col = self.resolve_col("status")
        if f.get("q") and name_col:
            q = q.ilike(name_col, f"%{f['q']}%")
        if f.get("job_title") and title_col:
            q = q.ilike(title_col, f"%{f['job_title']}%")
        if f.get("city") and city_col:
            q = q.ilike(city_col, f"%{f['city']}%")
        if f.get("min_years") and years_col:
            q = q.gte(years_col, float(f["min_years"]))
        if f.get("max_years") and years_col:
            q = q.lte(years_col, float(f["max_years"]))
        if f.get("status") and status_col:
            q = q.eq(status_col, f["status"])
        if sort == "name" and name_col:
            q = q.order(name_col)
        elif sort == "exp" and years_col:
            q = q.order(years_col, desc=True)
        else:
            q = q.order("created_at", desc=True)
        resp = q.execute()
        rows = resp.data
        total = resp.count if resp.count is not None else len(rows)
        rows = [self.normalize_candidate(r) for r in rows]
        if f.get("skill"):
            needle = f["skill"].lower()
            rows = [r for r in rows if any(needle in s.lower() for s in r["skills"])]
            total = len(rows)
        return rows[offset : offset + limit], total

    def get_candidate(self, candidate_id):
        rows = self._supa.table("candidates").select("*").eq("id", candidate_id).execute().data
        return self.normalize_candidate(rows[0]) if rows else None

    def list_all_candidates(self):
        rows = self._supa.table("candidates").select("*").order("created_at", desc=True).execute().data
        return [self.normalize_candidate(r) for r in rows]

    def set_candidate_status(self, candidate_id, status):
        if status in ("available", "employed", "closed"):
            col = self.resolve_col("status") or "status"
            self._supa.table("candidates").update({col: status}).eq("id", candidate_id).execute()

    def update_candidate(self, candidate_id, **fields):
        allowed = {"name", "email", "phone", "job_title", "location", "linkedin_url", "last_employer"}
        for logical in allowed:
            if logical not in fields:
                continue
            col = self.resolve_col(logical)
            if col:
                self._supa.table("candidates").update({col: fields[logical]}).eq("id", candidate_id).execute()

    def delete_candidate(self, candidate_id):
        self._supa.table("candidates").delete().eq("id", candidate_id).execute()

    def count_candidates(self):
        data = self._supa.table("candidates").select("id", count="exact").execute()
        return data.count if data.count is not None else len(data.data)

    def candidate_counts_by_status(self):
        counts = {"available": 0, "employed": 0, "closed": 0}
        col = self.resolve_col("status") or "status"
        rows = self._supa.table("candidates").select(col).execute().data
        for r in rows:
            key = (r.get(col) or "available").lower()
            if key in counts:
                counts[key] += 1
        return counts

    def distinct_values(self, logical, limit=12):
        col = self.resolve_col(logical)
        if not col:
            return []
        rows = self._supa.table("candidates").select(col).limit(500).execute().data
        values = [r.get(col) for r in rows if r.get(col)]
        seen, out = set(), []
        for v in values:
            v = str(v).strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
        return out[:limit]

    # ------------------------------------------------------------- contacts
    def create_contact(self, hr_id, candidate_id):
        existing = self.get_contact(hr_id, candidate_id)
        if existing:
            return existing
        rows = (
            self._supa.table("contacts")
            .insert({"hr_id": hr_id, "candidate_id": candidate_id, "status": "requested", "created_at": self.now_iso()})
            .execute()
            .data
        )
        return self._contact_from_row(rows[0]) if rows else None

    def get_contact(self, hr_id, candidate_id):
        rows = (
            self._supa.table("contacts")
            .select("*")
            .eq("hr_id", hr_id)
            .eq("candidate_id", candidate_id)
            .execute()
            .data
        )
        return self._contact_from_row(rows[0]) if rows else None

    def _contact_from_row(self, row):
        row = dict(row) if not isinstance(row, dict) else row
        return {
            "id": row["id"],
            "hr_id": row["hr_id"],
            "candidate_id": row["candidate_id"],
            "status": row["status"],
            "created_at": row.get("created_at"),
        }

    def list_contacts_for_hr(self, hr_id):
        rows = (
            self._supa.table("contacts")
            .select("*, candidates(*)")
            .eq("hr_id", hr_id)
            .order("created_at", desc=True)
            .execute()
            .data
        )
        out = []
        for c in rows:
            cand_raw = c.get("candidates")
            out.append({"contact": self._contact_from_row(c), "candidate": self.normalize_candidate(cand_raw)})
        return out

    def list_all_contacts(self):
        rows = (
            self._supa.table("contacts")
            .select("*, candidates(*), hr_accounts(*)")
            .order("created_at", desc=True)
            .execute()
            .data
        )
        out = []
        for c in rows:
            cand_raw = c.get("candidates")
            hr_raw = c.get("hr_accounts")
            out.append(
                {
                    "contact": self._contact_from_row(c),
                    "candidate": self.normalize_candidate(cand_raw),
                    "hr": self._user_from_row(hr_raw) if hr_raw else None,
                }
            )
        return out

    def set_contact_status(self, contact_id, status):
        if status in ("requested", "approved", "declined", "closed"):
            self._supa.table("contacts").update({"status": status}).eq("id", contact_id).execute()

    def delete_contact(self, contact_id):
        self._supa.table("contacts").delete().eq("id", contact_id).execute()

    def count_contacts(self):
        data = self._supa.table("contacts").select("id", count="exact").execute()
        return data.count if data.count is not None else len(data.data)

    # ------------------------------------------------------------ resume url
    def resume_url(self, candidate):
        url = candidate.get("resume_url")
        if not url:
            return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        try:
            res = self._supa.storage.from_(config.RESUME_BUCKET).create_signed_url(url, 3600)
            return res["signedURL"]
        except Exception:
            return None

    # --------------------------------------------------------------- god
    def ensure_god(self, email, password_hash):
        user = self.get_user_by_email(email)
        if user:
            # keep .env as the source of truth: refresh password + harden flags
            self.update_user(
                user["id"],
                password_hash=password_hash,
                role="admin",
                is_verified=True,
                is_blocked=False,
            )
            return self.get_user_by_id(user["id"])
        return self.create_user(email, password_hash, "Platform Admin", "", role="admin", is_verified=True)


# ===========================================================================
# Airtable backend
# ===========================================================================
class AirtableBackend(_BaseBackend):
    def __init__(self):
        from pyairtable import Api

        self.api = Api(config.AIRTABLE_API_KEY)
        self.base = self.api.base(config.AIRTABLE_BASE_ID)
        self.candidates = self.base.table(config.AIRTABLE_CANDIDATES_TABLE)
        self.hr = self.base.table(config.AIRTABLE_HR_TABLE)
        self.contacts = self.base.table(config.AIRTABLE_CONTACTS_TABLE)

    @property
    def is_airtable(self):
        return True

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _esc(value):
        return str(value).replace("'", "\\'")

    def _fields(self, rec):
        return rec.get("fields", {})

    def normalize_candidate(self, row):
        if row is None:
            return None
        fields = dict(self._fields(row))
        logical = {k: fields.get(v) for k, v in AIR.items()}
        return _normalize_candidate(logical, row["id"], fields.get("Created At"))

    def _user_from_row(self, rec):
        f = self._fields(rec)
        return {
            "id": rec["id"],
            "email": f.get(AIR_HR["email"], ""),
            "password_hash": f.get(AIR_HR["password_hash"], ""),
            "company_name": f.get(AIR_HR["company_name"], ""),
            "phone": f.get(AIR_HR["phone"]) or "",
            "role": f.get(AIR_HR["role"]) or "hr",
            "is_verified": self._as_bool(f.get(AIR_HR["is_verified"], False)),
            "is_blocked": self._as_bool(f.get(AIR_HR["is_blocked"], False)),
            "created_at": _iso(f.get(AIR_HR["created_at"])),
        }

    @staticmethod
    def _as_bool(value):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def _contact_from_row(self, rec):
        f = self._fields(rec)
        return {
            "id": rec["id"],
            "hr_id": f.get(AIR_CONTACT["hr_id"]),
            "candidate_id": f.get(AIR_CONTACT["candidate_id"]),
            "status": f.get(AIR_CONTACT["status"]) or "requested",
            "created_at": _iso(f.get(AIR_CONTACT["created_at"])),
        }

    @staticmethod
    def _sort(sort):
        mapping = {
            "newest": ["-" + config.AIRTABLE_SORT_FIELD],
            "oldest": [config.AIRTABLE_SORT_FIELD],
            "name": [AIR["name"]],
            "exp": ["-" + AIR["years_experience"]],
        }
        return mapping.get(sort, mapping["newest"])

    def _candidate_formula(self, filters):
        f = filters or {}
        parts = []
        if f.get("q"):
            parts.append(f"FIND(LOWER('{self._esc(f['q']).lower()}'), LOWER({{{AIR['name']}}})) > 0")
        if f.get("job_title"):
            parts.append(f"FIND(LOWER('{self._esc(f['job_title']).lower()}'), LOWER({{{AIR['job_title']}}})) > 0")
        if f.get("city"):
            parts.append(f"FIND(LOWER('{self._esc(f['city']).lower()}'), LOWER({{{AIR['location']}}})) > 0")
        if f.get("min_years") is not None:
            parts.append(f"{{{AIR['years_experience']}}} >= {float(f['min_years'])}")
        if f.get("max_years") is not None:
            parts.append(f"{{{AIR['years_experience']}}} <= {float(f['max_years'])}")
        if f.get("status"):
            parts.append(f"{{{AIR['status']}}} = '{self._esc(f['status'])}'")
        return "AND(" + ", ".join(parts) + ")" if parts else None

    # --------------------------------------------------------------- users
    def create_user(self, email, password_hash, company_name, phone, role="hr", is_verified=False):
        fields = {
            AIR_HR["email"]: email,
            AIR_HR["password_hash"]: password_hash,
            AIR_HR["company_name"]: company_name,
            AIR_HR["phone"]: phone or "",
            AIR_HR["role"]: role,
            AIR_HR["is_verified"]: bool(is_verified),
            AIR_HR["is_blocked"]: False,
        }
        try:
            rec = self.hr.create(fields, typecast=True)
        except Exception:
            # some bases store flags as text/select "1"/"0" — mirror update_user
            for logical in ("is_verified", "is_blocked"):
                fields[AIR_HR[logical]] = "1" if fields[AIR_HR[logical]] else "0"
            rec = self.hr.create(fields, typecast=True)
        return self._user_from_row(rec)

    def get_user_by_email(self, email):
        email = (email or "").strip().lower()
        rows = self.hr.all(formula=f"FIND(LOWER('{self._esc(email)}'), LOWER({{{AIR_HR['email']}}})) > 0", max_records=1)
        return self._user_from_row(rows[0]) if rows else None

    def get_user_by_id(self, user_id):
        try:
            return self._user_from_row(self.hr.get(user_id))
        except Exception:
            return None

    def update_user(self, user_id, **fields):
        allowed = {"company_name", "phone", "password_hash", "is_verified", "is_blocked", "role"}
        # Adapt boolean flags to how the base actually stores them
        # (checkbox True/False, or text/select "1"/"0").
        flag_style = {}
        try:
            existing = self.hr.get(user_id)
            for logical in ("is_verified", "is_blocked"):
                raw = (existing.get("fields") or {}).get(AIR_HR[logical])
                flag_style[logical] = "01" if isinstance(raw, str) else "bool"
        except Exception:
            flag_style = {"is_verified": "bool", "is_blocked": "bool"}
        updates = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k in ("is_verified", "is_blocked"):
                v = "1" if bool(v) else "0" if flag_style[k] == "01" else bool(v)
            updates[AIR_HR[k]] = v
        if updates:
            self.hr.update(user_id, updates, typecast=True)

    def list_users(self):
        try:
            rows = self.hr.all(sort=[config.AIRTABLE_SORT_FIELD])
        except Exception:
            rows = self.hr.all()
        return [self._user_from_row(r) for r in rows]

    def delete_user(self, user_id):
        self.hr.delete(user_id)

    def count_users(self):
        return len(self.hr.all(fields=[AIR_HR["email"]], page_size=100))

    # ----------------------------------------------------------- candidates
    def search_candidates(self, filters, limit=12, offset=0, sort="newest"):
        try:
            rows = self.candidates.all(formula=self._candidate_formula(filters), sort=self._sort(sort))
        except Exception:
            # sort field may not exist in this base — fetch unsorted, sort in memory
            rows = self.candidates.all(formula=self._candidate_formula(filters))
            rows.sort(key=lambda r: (r.get("fields") or {}).get(AIR["name"]) or "", reverse=sort == "newest")
        rows = [self.normalize_candidate(r) for r in rows]
        f = filters or {}
        if f.get("skill"):
            needle = f["skill"].lower()
            rows = [r for r in rows if any(needle in s.lower() for s in r["skills"])]
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_candidate(self, candidate_id):
        try:
            return self.normalize_candidate(self.candidates.get(candidate_id))
        except Exception:
            return None

    def list_all_candidates(self):
        try:
            rows = self.candidates.all(sort=self._sort("newest"))
        except Exception:
            rows = self.candidates.all()
        return [self.normalize_candidate(r) for r in rows]

    def set_candidate_status(self, candidate_id, status):
        if status in ("available", "employed", "closed"):
            self.candidates.update(candidate_id, {AIR["status"]: status}, typecast=True)

    def update_candidate(self, candidate_id, **fields):
        allowed = {"name", "email", "phone", "job_title", "location", "linkedin_url", "last_employer"}
        updates = {AIR[k]: fields[k] for k in allowed if fields.get(k) is not None}
        if updates:
            self.candidates.update(candidate_id, updates, typecast=True)

    def delete_candidate(self, candidate_id):
        self.candidates.delete(candidate_id)

    def count_candidates(self):
        return len(self.candidates.all(fields=[AIR["status"]], page_size=100))

    def candidate_counts_by_status(self):
        counts = {"available": 0, "employed": 0, "closed": 0}
        for r in self.candidates.all(fields=[AIR["status"]], page_size=100):
            key = (self._fields(r).get(AIR["status"]) or "available").lower()
            if key in counts:
                counts[key] += 1
        return counts

    def distinct_values(self, logical, limit=12):
        col = AIR.get(logical)
        if not col:
            return []
        values = [self._fields(r).get(col) for r in self.candidates.all(fields=[col], page_size=100)]
        seen, out = set(), []
        for v in values:
            if not v:
                continue
            if isinstance(v, list):
                for item in v:
                    v = str(item).strip()
                    if v and v.lower() not in seen:
                        seen.add(v.lower())
                        out.append(v)
            else:
                v = str(v).strip()
                if v and v.lower() not in seen:
                    seen.add(v.lower())
                    out.append(v)
        return out[:limit]

    # ------------------------------------------------------------- contacts
    def _friendly_airtable_error(self, exc):
        msg = str(exc)
        if "Status" in msg or "Invalid value" in msg:
            return ValueError(
                "Airtable Contacts 'Status' field needs the options 'approved' and 'declined'. "
                "Add them in the Airtable UI, then retry."
            )
        return ValueError(f"Airtable error: {msg}")

    def create_contact(self, hr_id, candidate_id):
        existing = self.get_contact(hr_id, candidate_id)
        if existing:
            return existing
        try:
            rec = self.contacts.create(
                {
                    AIR_CONTACT["hr_id"]: hr_id,
                    AIR_CONTACT["candidate_id"]: candidate_id,
                    AIR_CONTACT["status"]: "requested",
                },
                typecast=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise self._friendly_airtable_error(exc) from exc
        return self._contact_from_row(rec)

    def get_contact(self, hr_id, candidate_id):
        formula = (
            f"AND({{{AIR_CONTACT['hr_id']}}} = '{self._esc(hr_id)}', "
            f"{{{AIR_CONTACT['candidate_id']}}} = '{self._esc(candidate_id)}')"
        )
        rows = self.contacts.all(formula=formula, max_records=1)
        return self._contact_from_row(rows[0]) if rows else None

    def _candidates_by_id(self):
        return {r["id"]: self.normalize_candidate(r) for r in self.candidates.all()}

    def _users_by_id(self):
        return {r["id"]: self._user_from_row(r) for r in self.hr.all()}

    def list_contacts_for_hr(self, hr_id):
        try:
            rows = self.contacts.all(
                formula=f"{{{AIR_CONTACT['hr_id']}}} = '{self._esc(hr_id)}'",
                sort=["-" + config.AIRTABLE_SORT_FIELD],
            )
        except Exception:
            rows = self.contacts.all(formula=f"{{{AIR_CONTACT['hr_id']}}} = '{self._esc(hr_id)}'")
        cands = self._candidates_by_id()
        out = []
        for c in rows:
            contact = self._contact_from_row(c)
            out.append({"contact": contact, "candidate": cands.get(contact["candidate_id"])})
        return out

    def list_all_contacts(self):
        try:
            rows = self.contacts.all(sort=["-" + config.AIRTABLE_SORT_FIELD])
        except Exception:
            rows = self.contacts.all()
        cands = self._candidates_by_id()
        users = self._users_by_id()
        out = []
        for c in rows:
            contact = self._contact_from_row(c)
            out.append(
                {
                    "contact": contact,
                    "candidate": cands.get(contact["candidate_id"]),
                    "hr": users.get(contact["hr_id"]),
                }
            )
        return out

    def set_contact_status(self, contact_id, status):
        if status in ("requested", "approved", "declined", "closed"):
            try:
                self.contacts.update(contact_id, {AIR_CONTACT["status"]: status}, typecast=True)
            except Exception as exc:  # noqa: BLE001
                raise self._friendly_airtable_error(exc) from exc

    def delete_contact(self, contact_id):
        self.contacts.delete(contact_id)

    def count_contacts(self):
        try:
            return len(self.contacts.all(fields=[AIR_CONTACT["status"]], page_size=100))
        except Exception:
            return len(self.contacts.all(page_size=100))

    # ------------------------------------------------------------ resume url
    def resume_url(self, candidate):
        value = candidate.get("resume_url")
        if not value:
            return None
        if isinstance(value, str):
            return value if value.startswith(("http://", "https://")) else None
        if isinstance(value, list) and value:
            url = value[0].get("url")
            return url if url else None
        return None

    # --------------------------------------------------------------- god
    def ensure_god(self, email, password_hash):
        user = self.get_user_by_email(email)
        if user:
            # keep .env as the source of truth: refresh password + harden flags
            self.update_user(
                user["id"],
                password_hash=password_hash,
                role="admin",
                is_verified=True,
                is_blocked=False,
            )
            return self.get_user_by_id(user["id"])
        return self.create_user(email, password_hash, "Platform Admin", "", role="admin", is_verified=True)


# ===========================================================================
# SQLite dev backend (local fallback, seeded demo data)
# ===========================================================================
class SqliteBackend(_BaseBackend):
    def __init__(self):
        self._sqlite = None

    def _conn(self):
        if self._sqlite is None:
            os.makedirs(os.path.dirname(DEV_DB_PATH), exist_ok=True)
            self._sqlite = sqlite3.connect(DEV_DB_PATH, check_same_thread=False)
            self._sqlite.row_factory = sqlite3.Row
            self._migrate_sqlite()
        return self._sqlite

    def _migrate_sqlite(self):
        c = self._conn()
        c.execute(
            """
            create table if not exists hr_accounts (
              id text primary key, email text unique not null,
              password_hash text not null, company_name text not null, phone text,
              role text not null default 'hr', is_verified integer not null default 0,
              is_blocked integer not null default 0, created_at text not null)
            """
        )
        c.execute(
            """
            create table if not exists candidates (
              id text primary key, name text not null, email text, phone text,
              job_title text, location text, linkedin_url text, skills text,
              years_experience real, last_employer text, resume_url text,
              status text not null default 'available', created_at text not null)
            """
        )
        c.execute(
            """
            create table if not exists contacts (
              id text primary key, hr_id text not null, candidate_id text not null,
              status text not null default 'requested', created_at text not null,
              unique (hr_id, candidate_id))
            """
        )
        c.commit()
        if not c.execute("select count(*) from candidates").fetchone()[0]:
            self._seed_sqlite()

    def _seed_sqlite(self):
        rows = [
            ("Aisha Rahman", "aisha.rahman@gmail.com", "+1 (415) 555-0112", "Senior React Engineer", "San Francisco, CA", "linkedin.com/in/aisharhman", ["React", "TypeScript", "Node.js", "GraphQL", "AWS"], 8, "Stripe", None, "available"),
            ("Marcus Chen", "marcus.chen@outlook.com", "+1 (206) 555-0184", "Staff Product Designer", "Seattle, WA", "linkedin.com/in/marcuschen", ["Figma", "Design Systems", "UX Research", "Prototyping"], 10, "Airbnb", None, "available"),
            ("Priya Patel", "priya.patel@gmail.com", "+1 (312) 555-0157", "Backend Engineer", "Chicago, IL", "linkedin.com/in/priyapatel", ["Python", "Django", "PostgreSQL", "Redis", "Docker"], 5, "Lyft", None, "available"),
            ("Daniel Osei", "daniel.osei@yahoo.com", "+1 (404) 555-0163", "DevOps Engineer", "Atlanta, GA", "linkedin.com/in/danielosei", ["Kubernetes", "Terraform", "AWS", "CI/CD", "Prometheus"], 6, "Twilio", None, "available"),
            ("Sofia Martinez", "sofia.martinez@gmail.com", "+1 (512) 555-0190", "Full Stack Developer", "Austin, TX", "linkedin.com/in/sofiamtz", ["JavaScript", "Vue.js", "Express", "MongoDB"], 4, "Indeed", None, "available"),
            ("James Whitfield", "james.whitfield@gmail.com", "+1 (917) 555-0128", "Data Scientist", "New York, NY", "linkedin.com/in/jameswhitfield", ["Python", "Pandas", "Scikit-learn", "SQL", "Airflow"], 7, "Spotify", None, "available"),
            ("Nadia Hassan", "nadia.hassan@gmail.com", "+1 (703) 555-0174", "Product Manager", "Arlington, VA", "linkedin.com/in/nadiahassan", ["Roadmapping", "Agile", "Analytics", "SQL", "Jira"], 9, "Salesforce", None, "available"),
            ("Oliver Bennett", "oliver.bennett@proton.me", "+1 (617) 555-0135", "Mobile Engineer (iOS)", "Boston, MA", "linkedin.com/in/oliverbennett", ["Swift", "SwiftUI", "Combine", "Firebase"], 6, "HubSpot", None, "available"),
            ("Grace Kim", "grace.kim@gmail.com", "+1 (213) 555-0149", "Machine Learning Engineer", "Los Angeles, CA", "linkedin.com/in/gracekim", ["PyTorch", "TensorFlow", "NLP", "Python", "GCP"], 5, "NVIDIA", None, "available"),
            ("Tomás Rivera", "tomas.rivera@outlook.com", "+1 (480) 555-0177", "QA Automation Engineer", "Phoenix, AZ", "linkedin.com/in/tomasrivera", ["Selenium", "Playwright", "Python", "Cypress", "Jest"], 4, "PayPal", None, "available"),
            ("Emily Zhang", "emily.zhang@gmail.com", "+1 (425) 555-0119", "Frontend Engineer", "Redmond, WA", "linkedin.com/in/emilyzhang", ["React", "Next.js", "Tailwind", "TypeScript"], 3, "Microsoft", None, "available"),
            ("Kwame Mensah", "kwame.mensah@gmail.com", "+1 (646) 555-0188", "Site Reliability Engineer", "New York, NY", "linkedin.com/in/kwamemensah", ["AWS", "Go", "Docker", "Grafana", "Ansible"], 7, "Datadog", None, "available"),
            ("Hannah Lee", "hannah.lee@gmail.com", "+1 (858) 555-0153", "UX Designer", "San Diego, CA", "linkedin.com/in/hannahlee", ["Figma", "User Testing", "Wireframing", "Accessibility"], 4, "Intuit", None, "available"),
            ("Victor Santos", "victor.santos@gmail.com", "+1 (305) 555-0166", "Java Backend Developer", "Miami, FL", "linkedin.com/in/victorsantos", ["Java", "Spring Boot", "Kafka", "MySQL", "Microservices"], 6, "Citrix", None, "available"),
            ("Fatima Al-Farsi", "fatima.alfarsi@gmail.com", "+1 (832) 555-0121", "Cybersecurity Analyst", "Houston, TX", "linkedin.com/in/fatimafarsi", ["SIEM", "Penetration Testing", "Python", "Cloud Security"], 5, "Palantir", None, "available"),
            ("Benjamin Roth", "benjamin.roth@gmail.com", "+1 (614) 555-0181", "Data Engineer", "Columbus, OH", "linkedin.com/in/benjaminroth", ["Spark", "Airflow", "Snowflake", "dbt", "Python"], 5, "CarMax", None, "available"),
            ("Layla Thompson", "layla.thompson@gmail.com", "+1 (720) 555-0142", "Engineering Manager", "Denver, CO", "linkedin.com/in/laylathompson", ["Leadership", "React", "Node.js", "Mentoring", "OKRs"], 11, "Gusto", None, "available"),
            ("Ahmed Khan", "ahmed.khan@gmail.com", "+1 (313) 555-0172", "DevOps Engineer", "Detroit, MI", "linkedin.com/in/ahmedkhan", ["Docker", "AWS", "Jenkins", "Bash", "Terraform"], 5, "Ford", None, "available"),
            ("Sarah Novak", "sarah.novak@gmail.com", "+1 (503) 555-0187", "Frontend Engineer", "Portland, OR", "linkedin.com/in/sarahnovak", ["React", "Redux", "Sass", "Jest", "Accessibility"], 6, "New Relic", None, "employed"),
            ("Diego Fernández", "diego.fernandez@gmail.com", "+1 (210) 555-0159", "Full Stack Engineer", "San Antonio, TX", "linkedin.com/in/diegofernandez", ["Ruby on Rails", "React", "PostgreSQL", "Heroku"], 4, "HP", None, "closed"),
        ]
        now = datetime.now(timezone.utc).isoformat()
        for r in rows:
            cid = str(uuid.uuid4())
            skills = json.dumps(r[6])
            self._conn().execute(
                "insert into candidates (id, name, email, phone, job_title, location, linkedin_url, skills, years_experience, last_employer, resume_url, status, created_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, r[0], r[1], r[2], r[3], r[4], r[5], skills, r[7], r[8], r[9], r[10], now),
            )
        self._conn().commit()

    def normalize_candidate(self, row):
        if row is None:
            return None
        raw = dict(row)
        fields = {
            "name": raw.get("name"),
            "email": raw.get("email"),
            "phone": raw.get("phone"),
            "job_title": raw.get("job_title"),
            "location": raw.get("location"),
            "linkedin_url": raw.get("linkedin_url"),
            "skills": raw.get("skills"),
            "years_experience": raw.get("years_experience"),
            "last_employer": raw.get("last_employer"),
            "resume_url": raw.get("resume_url"),
            "status": raw.get("status"),
        }
        return _normalize_candidate(fields, raw.get("id"), raw.get("created_at"))

    # --------------------------------------------------------------- users
    def create_user(self, email, password_hash, company_name, phone, role="hr", is_verified=False):
        cid = str(uuid.uuid4())
        now = self.now_iso()
        self._conn().execute(
            "insert into hr_accounts (id, email, password_hash, company_name, phone, role, is_verified, is_blocked, created_at) values (?,?,?,?,?,?,?,?,?)",
            (cid, email, password_hash, company_name, phone or "", role, 1 if is_verified else 0, 0, now),
        )
        self._conn().commit()
        return self.get_user_by_email(email)

    def _user_from_row(self, row):
        row = dict(row) if not isinstance(row, dict) else row
        return {
            "id": row["id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "company_name": row["company_name"],
            "phone": row.get("phone") or "",
            "role": row.get("role") or "hr",
            "is_verified": bool(row.get("is_verified")),
            "is_blocked": bool(row.get("is_blocked")),
            "created_at": row.get("created_at"),
        }

    def get_user_by_email(self, email):
        row = self._conn().execute("select * from hr_accounts where email = ?", ((email or "").strip().lower(),)).fetchone()
        return self._user_from_row(row) if row else None

    def get_user_by_id(self, user_id):
        row = self._conn().execute("select * from hr_accounts where id = ?", (user_id,)).fetchone()
        return self._user_from_row(row) if row else None

    def update_user(self, user_id, **fields):
        allowed = {"company_name", "phone", "password_hash", "is_verified", "is_blocked", "role"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        sets = ", ".join(f"{k} = ?" for k in updates)
        self._conn().execute(f"update hr_accounts set {sets} where id = ?", (*updates.values(), user_id))
        self._conn().commit()

    def list_users(self):
        rows = self._conn().execute("select * from hr_accounts order by created_at").fetchall()
        return [self._user_from_row(r) for r in rows]

    def delete_user(self, user_id):
        self._conn().execute("delete from hr_accounts where id = ?", (user_id,))
        self._conn().commit()

    def count_users(self):
        return self._conn().execute("select count(*) from hr_accounts").fetchone()[0]

    # ----------------------------------------------------------- candidates
    def search_candidates(self, filters, limit=12, offset=0, sort="newest"):
        f = filters or {}
        sql = "select * from candidates"
        where, params = [], []
        if f.get("q"):
            where.append("name like ?")
            params.append(f"%{f['q']}%")
        if f.get("job_title"):
            where.append("job_title like ?")
            params.append(f"%{f['job_title']}%")
        if f.get("city"):
            where.append("location like ?")
            params.append(f"%{f['city']}%")
        if f.get("min_years") is not None:
            where.append("years_experience >= ?")
            params.append(float(f["min_years"]))
        if f.get("max_years") is not None:
            where.append("years_experience <= ?")
            params.append(float(f["max_years"]))
        if f.get("status"):
            where.append("status = ?")
            params.append(f["status"])
        if where:
            sql += " where " + " and ".join(where)
        order = {"newest": "created_at desc", "oldest": "created_at", "name": "name", "exp": "years_experience desc"}.get(sort, "created_at desc")
        sql += f" order by {order}"
        rows = [self.normalize_candidate(r) for r in self._conn().execute(sql, params).fetchall()]
        if f.get("skill"):
            needle = f["skill"].lower()
            rows = [r for r in rows if any(needle in s.lower() for s in r["skills"])]
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_candidate(self, candidate_id):
        row = self._conn().execute("select * from candidates where id = ?", (candidate_id,)).fetchone()
        return self.normalize_candidate(row) if row else None

    def list_all_candidates(self):
        rows = self._conn().execute("select * from candidates order by created_at desc").fetchall()
        return [self.normalize_candidate(r) for r in rows]

    def set_candidate_status(self, candidate_id, status):
        if status in ("available", "employed", "closed"):
            self._conn().execute("update candidates set status = ? where id = ?", (status, candidate_id))
            self._conn().commit()

    def update_candidate(self, candidate_id, **fields):
        allowed = {"name", "email", "phone", "job_title", "location", "linkedin_url", "last_employer"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        sets = ", ".join(f"{k} = ?" for k in updates)
        self._conn().execute(f"update candidates set {sets} where id = ?", (*updates.values(), candidate_id))
        self._conn().commit()

    def delete_candidate(self, candidate_id):
        self._conn().execute("delete from candidates where id = ?", (candidate_id,))
        self._conn().commit()

    def count_candidates(self):
        return self._conn().execute("select count(*) from candidates").fetchone()[0]

    def candidate_counts_by_status(self):
        counts = {"available": 0, "employed": 0, "closed": 0}
        rows = self._conn().execute("select status, count(*) as n from candidates group by status").fetchall()
        for r in rows:
            key = (r["status"] or "available").lower()
            if key in counts:
                counts[key] = r["n"]
        return counts

    def distinct_values(self, logical, limit=12):
        col = {"job_title": "job_title", "location": "location"}.get(logical)
        if not col:
            return []
        rows = self._conn().execute(f"select distinct {col} from candidates where {col} is not null").fetchall()
        seen, out = set(), []
        for r in rows:
            v = str(r[0]).strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
        return out[:limit]

    # ------------------------------------------------------------- contacts
    def create_contact(self, hr_id, candidate_id):
        cid = str(uuid.uuid4())
        try:
            self._conn().execute(
                "insert into contacts (id, hr_id, candidate_id, status, created_at) values (?,?,?,?,?)",
                (cid, hr_id, candidate_id, "requested", self.now_iso()),
            )
            self._conn().commit()
        except sqlite3.IntegrityError:
            return self.get_contact(hr_id, candidate_id)
        return self.get_contact(hr_id, candidate_id)

    def get_contact(self, hr_id, candidate_id):
        row = self._conn().execute(
            "select * from contacts where hr_id = ? and candidate_id = ?", (hr_id, candidate_id)
        ).fetchone()
        return self._contact_from_row(row) if row else None

    def _contact_from_row(self, row):
        row = dict(row) if not isinstance(row, dict) else row
        return {
            "id": row["id"],
            "hr_id": row["hr_id"],
            "candidate_id": row["candidate_id"],
            "status": row["status"],
            "created_at": row.get("created_at"),
        }

    def list_contacts_for_hr(self, hr_id):
        rows = self._conn().execute("select * from contacts where hr_id = ? order by created_at desc", (hr_id,)).fetchall()
        out = []
        for c in rows:
            contact = self._contact_from_row(c)
            out.append({"contact": contact, "candidate": self.get_candidate(contact["candidate_id"])})
        return out

    def list_all_contacts(self):
        rows = self._conn().execute("select * from contacts order by created_at desc").fetchall()
        out = []
        for c in rows:
            contact = self._contact_from_row(c)
            out.append(
                {
                    "contact": contact,
                    "candidate": self.get_candidate(contact["candidate_id"]),
                    "hr": self.get_user_by_id(contact["hr_id"]),
                }
            )
        return out

    def set_contact_status(self, contact_id, status):
        if status in ("requested", "approved", "declined", "closed"):
            self._conn().execute("update contacts set status = ? where id = ?", (status, contact_id))
            self._conn().commit()

    def delete_contact(self, contact_id):
        self._conn().execute("delete from contacts where id = ?", (contact_id,))
        self._conn().commit()

    def count_contacts(self):
        return self._conn().execute("select count(*) from contacts").fetchone()[0]

    # ------------------------------------------------------------ resume url
    def resume_url(self, candidate):
        url = candidate.get("resume_url")
        if url and (url.startswith("http://") or url.startswith("https://")):
            return url
        return None

    # --------------------------------------------------------------- god
    def ensure_god(self, email, password_hash):
        user = self.get_user_by_email(email)
        if user:
            # keep .env as the source of truth: refresh password + harden flags
            self.update_user(
                user["id"],
                password_hash=password_hash,
                role="admin",
                is_verified=True,
                is_blocked=False,
            )
            return self.get_user_by_id(user["id"])
        return self.create_user(email, password_hash, "Platform Admin", "", role="admin", is_verified=True)


# ===========================================================================
# Backend selection
# ===========================================================================
def _make_backend():
    if config.supabase_enabled:
        return SupabaseBackend()
    if config.airtable_enabled:
        return AirtableBackend()
    return SqliteBackend()


db = _make_backend()
