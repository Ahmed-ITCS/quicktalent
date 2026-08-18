# Airtable Setup Guide — QuickTalent

QuickTalent runs on Airtable as its database. Follow these steps to get a working base.

---

## 1. Create the Airtable base

1. Go to [airtable.com/create/templates](https://airtable.com/create/templates) → **Start from scratch** → name it `QuickTalent`.
2. Create **3 tables** with the exact names: `Candidates`, `HR Accounts`, `Contacts`.

> Table names can be customized — override them in `.env`:
> `AIRTABLE_CANDIDATES_TABLE`, `AIRTABLE_HR_TABLE`, `AIRTABLE_CONTACTS_TABLE`.

---

## 2. Table schemas (exact field names required)

### Table: `Candidates`

| Field name | Type | Notes |
|---|---|---|
| Name | Single line text | Required |
| Email | Email | Required |
| Phone | Phone | |
| Job Title | Single line text | |
| Location | Single line text | Preferred location works too |
| LinkedIn URL | URL | |
| Skills | Multiple select | Alternatively single line text, comma-separated |
| Years of Experience | Number | Integer or decimal |
| Last Employer | Single line text | Optional |
| Resume | Attachment | PDF/Word — shown as download link |
| Status | Single select | Options: `available`, `employed`, `closed`. Default `available` |

### Table: `HR Accounts`

| Field name | Type | Notes |
|---|---|---|
| Email | Email | Required, unique |
| Password Hash | Long text | Auto-created by the app |
| Company Name | Single line text | |
| Phone | Phone | |
| Role | Single select | Options: `hr`, `admin` |
| Verified | Checkbox | |
| Blocked | Checkbox | |
| Created At | Created time | Auto |

### Table: `Contacts`

| Field name | Type | Notes |
|---|---|---|
| HR ID | Single line text | Auto-created — record ID from HR Accounts |
| Candidate ID | Single line text | Auto-created — record ID from Candidates |
| Status | Single select | Options: `requested`, `approved`, `declined`, `closed` |
| Created At | Created time | Auto |

> The candidate approval flow needs the **approved** and **declined** options in the
> Status field. Existing `requested` contacts created before this feature were already
> visible to HR — set them to `approved` once when rolling out.

---

## 3. Import existing candidate data

1. In Airtable → **Candidates** table → **Insert** → **Import from CSV/Google Sheets**.
2. Your CSV should have columns matching the field names above (Name, Email, Job Title, …).
3. For **Skills**, use comma-separated text in the CSV — the app splits it into chips.
4. Set the **Status** column value to `available` (or `employed`/`closed`).
5. Add resumes afterwards via the **Resume** attachment field.

---

## 4. Get your API credentials

1. Create a Personal Access Token: [airtable.com/create/tokens](https://airtable.com/create/tokens)
   - Scopes: `data.records:read`, `data.records:write`
   - Access: your `QuickTalent` base only
2. Copy the token → `AIRTABLE_API_KEY` in `.env`.
3. Get your **Base ID**: open the base in the browser — the URL is
   `https://airtable.com/appXXXXXXXXXXXX/...` — the part after `/app` is the Base ID.

---

## 5. Run

```bash
# .env
AIRTABLE_API_KEY=patXXXXXXXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXX

pip install -r requirements.txt
python app.py
```

On boot the god account (`GOD_EMAIL` / `GOD_PASSWORD` from `.env`) is created in the
`HR Accounts` table automatically.

## 6. Backend priority

| Env config | Backend used |
|---|---|
| `AIRTABLE_API_KEY` + `AIRTABLE_BASE_ID` set | **Airtable** |
| Only `SUPABASE_URL` + `SUPABASE_KEY` set | Supabase |
| Neither set | Local SQLite dev mode (`var/dev.db`, demo data, emails logged to `var/mail.log`) |
