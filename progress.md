# QuickTalent — Project Progress & Business Logic

## 1. Product Concept

A private talent network where **HR teams discover laid-off professionals** (data loaded in
Supabase) and initiate contact. Contact details are **hidden by default**; pressing *Contact*
notifies the candidate by email, and **both sides immediately unlock each other's email & phone**
for a two-way conversation.

**Status: fully implemented and end-to-end tested locally.** (See §9.)

---

## 2. Architecture

```
Flask 3 (server-rendered, Jinja2)  ──  pyairtable (REST)  ──  Airtable (primary backend)
        │
        ├── Supabase (PostgREST) alternative backend
        ├── SQLite dev fallback (var/dev.db, seeded demo data)
        └── SMTP (smtplib)  ── console mode logs emails to var/mail.log
```

| Component | File | Responsibility |
|---|---|---|
| App factory | `app.py` | Blueprints, error pages, context vars, **god seeding** |
| Config | `config.py` | Env vars from `.env` (dotenv); backend selection |
| Data layer | `db.py` | **Three interchangeable backends**: Airtable → Supabase → SQLite dev; same interface |
| Email | `email_service.py` | SMTP sending + console-mode logging to `var/mail.log` |
| Auth helpers | `auth_utils.py` | Password hashing, verification tokens, decorators, masking |
| Auth routes | `routes_auth.py` | Register → verify → login/logout |
| HR routes | `routes_hr.py` | Browse, detail, contact, contacts, status, settings |
| God routes | `routes_admin.py` | Overview, all candidates, HR accounts, contacts matrix |
| Design | `static/css/styles.css` | Minimal light-green & white enterprise design |

### Backend priority (set in `.env`)

| Env config | Backend |
|---|---|
| `AIRTABLE_API_KEY` + `AIRTABLE_BASE_ID` | **Airtable** (primary) |
| Only `SUPABASE_URL` + `SUPABASE_KEY` | Supabase |
| Neither | SQLite dev mode (`var/dev.db`, 20 demo candidates, emails → `var/mail.log`) |

---

## 3. Roles & access

| Role | Flag | Capabilities |
|---|---|---|
| **HR** | `role='hr'` | Browse/filter candidates, view profiles, contact, manage own contacts & statuses, settings |
| **God admin** | `role='admin'` | Everything in HR + full visibility of all candidates/HR/contacts + verify/block/delete/update |

- God account **seeded at boot** from `GOD_EMAIL`/`GOD_PASSWORD` (`db.ensure_god`) — always
  verified, never blockable/deletable (`routes_admin.hr_action` refuses `role='admin'`).
- Access control: `@login_required` (session cookie) and `@admin_required` (403 for HR).

---

## 4. Database schema

### `candidates` (existing, user-loaded — column names auto-detected)

Logical fields resolved by `CANDIDATE_FIELDS` fallback list in `db.py`:

| Logical | Fallback columns tried in order |
|---|---|
| name | name, full_name, candidate_name |
| email | email, candidate_email |
| phone | phone, mobile, contact_phone, contact_number |
| job_title | job_title, title, current_title, desired_title |
| location | location, city, city_location, current_location |
| linkedin_url | linkedin_url, linkedin, linkedin_profile_url |
| skills | skills, tech_skills, technologies, skills_tech, tech_stack *(jsonb array or comma text)* |
| years_experience | years_experience, years_of_experience, experience_years, years_exp, experience |
| last_employer | last_employer, previous_employer, employer, last_company |
| resume_url | resume_url, resume, resume_path, cv_url, cv |
| status | status, candidate_status, employment_status → normalized to `available`/`employed`/`closed` |

> Status column is **added automatically** by `schema.sql` if missing (default `available`).

### `hr_accounts` (created by `schema.sql`)

`id (uuid PK) · email (unique) · password_hash · company_name · phone · role ('hr'|'admin')
· is_verified · is_blocked · created_at`

### `contacts` (created by `schema.sql`)

`id (uuid PK) · hr_id (FK hr_accounts) · candidate_id (FK candidates) · status
('requested'|'closed') · created_at` — **unique (hr_id, candidate_id)** prevents duplicates.

---

## 5. Business logic (flows)

### 5.1 HR registration & verification

1. `POST /register` validates: valid email, password ≥ 8 chars, company name, phone, email not taken.
2. Creates `hr_accounts` row (`is_verified=false`), hashed via Werkzeug pbkdf2.
3. Signs `email` into an **itsdangerous token** (salt `email-verify`, expiry **24h**).
4. Sends verification email with link `/verify/<token>`.
5. `GET /verify/<token>`: invalid/expired → error flash → back to register; success → `is_verified=true`.
6. Login blocked until verified; blocked accounts (`is_blocked`) refused with message.

### 5.2 Browse & filter

`GET /candidates` builds filters from query params → `db.search_candidates`:

- Server-side filters (Airtable formula / PostgREST / SQL): q (name), job_title, city, min/max
  years, status, sort (newest/oldest/name/exp).
- **Skills filter is applied in-memory** (Airtable Multi-select / jsonb arrays / text columns).
- Pagination: 12 per page, page numbers clamped to valid range.
- Contact info rendered **masked**: email `ab***@domain`, phone `********0112` (`auth_utils.mask_*`).

### 5.3 Contact flow (core feature)

`POST /candidates/<id>/contact` (login required):

1. Candidate must exist and be `available` (employed/closed → error flash).
2. `db.get_contact` → already exists? flash info, redirect (no duplicate).
3. Else `db.create_contact` (status `requested`), **immediately**:
   - HR unlocks candidate's full email/phone (My Contacts page + profile unlocked box).
   - Email to candidate via `send_contact_email` containing **HR company name, contact email,
     phone** with **Reply-To = HR email** → candidate's reply goes straight to the HR mailbox.
     *This is the "both can contact to and fro" mechanism, candidates have no accounts.*

### 5.4 Status management ("Employed / Closed")

Two entry points:

- **HR** (`POST /contacts/<contact_id>/status`) — only own contacts; sets candidate status +
  flips contact status (`employed`/`closed` → `closed`; `available` → `requested`).
- **God** (`POST /admin/candidates/<id>/status`) — any candidate, inline dropdown.

Either way the candidate gets a **status email** (congratulations on Employed; notice on Closed).
Status changes are global (visible to all HR) and immediately affect browse availability.

### 5.5 God console

| Route | Function |
|---|---|
| `/admin` | 6 stat cards (total/available/employed/closed candidates, HR count, connections) + recent activity |
| `/admin/candidates` | Full table: contact info, contacted-by count, status dropdown, **Manage popover** (edit fields, delete) |
| `/admin/hr` | All accounts: verify / block / unblock / delete (god row protected) + contacts-made count |
| `/admin/contacts` | Connection matrix both sides' contacts, delete records |

---

## 6. Emails (SMTP)

`email_service.send_email` — SMTP STARTTLS (port 587) when `SMTP_HOST` set, otherwise writes to
`var/mail.log` (dev mode).

| Template | Trigger | To | Reply-To |
|---|---|---|---|
| `send_verification_email` | registration | HR | — |
| `send_contact_email` | contact | candidate | **HR email** |
| `send_status_email` | employed/closed | candidate | — |

---

## 7. Resume handling

`db.resume_url`: full http(s) URL → used as-is; Airtable attachment list → first item's URL;
Supabase storage **path** → signed URL (`RESUME_BUCKET`, default `resumes`, 1h expiry);
otherwise `None` → UI shows "no resume".

---

## 8. Files map

```
app.py · config.py · db.py · email_service.py · auth_utils.py · schema.sql
routes_auth.py · routes_hr.py · routes_admin.py
requirements.txt · .env(.example) · HOW_TO_USE.md · AIRTABLE_SETUP.md
templates/   base_public.html · base_app.html · landing · register · verify_sent · login
             candidates · candidate_detail · contacts · settings · error
             admin/ overview · candidates · hr · contacts
static/css/styles.css · static/js/main.js
```

---

## 9. Testing performed

| Flow | Result |
|---|---|
| Landing/register/login pages | ✅ 200 |
| God login → `/admin` + all 4 god views | ✅ 200 (HR gets 403) |
| HR register → verify link → login | ✅ |
| Browse with filters, masked emails (`ai***@gmail.com`) | ✅ |
| Contact → row created, candidate email sent (console log), duplicate blocked | ✅ |
| My Contacts shows unlocked email/phone | ✅ |
| Mark Employed → status email + candidate status change | ✅ |
| Settings page | ✅ 200 |
| Airtable backend (stubbed pyairtable API): god seed, users, formulas, pagination, contacts, statuses | ✅ all pass |

Bugs found & fixed during testing: sqlite Row `.get` compatibility (×2), verification token
return shape, `list_contacts_for_hr` set-comprehension unpacking, Airtable `AIR["created_at"]`
KeyError, sort mappings for `newest`/`oldest`.

## 10. Deploy checklist (Airtable + real email)

- [ ] Create the Airtable base with exact tables/fields from `AIRTABLE_SETUP.md`
  (Candidates, HR Accounts, Contacts — the app does **not** create them)
- [ ] Import candidate CSV into Candidates; set Status single-select values
- [ ] Fill `.env`: `AIRTABLE_API_KEY` (PAT), `AIRTABLE_BASE_ID`, SMTP creds,
      `APP_SECRET_KEY` (long random), `APP_BASE_URL`, `GOD_EMAIL`, `GOD_PASSWORD`
- [ ] Verify field names match `AIR`/`AIR_HR`/`AIR_CONTACT` maps in `db.py` (case-sensitive)
- [ ] `pip install -r requirements.txt && python app.py` (or gunicorn for production)

> Supabase remains an alternative backend: set only `SUPABASE_URL` + `SUPABASE_KEY` and
> run `schema.sql` in the SQL editor.
