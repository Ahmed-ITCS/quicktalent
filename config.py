import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("APP_SECRET_KEY", "dev-secret-change-me")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")

    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

    AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
    AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
    AIRTABLE_CANDIDATES_TABLE = os.environ.get("AIRTABLE_CANDIDATES_TABLE", "Candidates")
    AIRTABLE_HR_TABLE = os.environ.get("AIRTABLE_HR_TABLE", "HR Accounts")
    AIRTABLE_CONTACTS_TABLE = os.environ.get("AIRTABLE_CONTACTS_TABLE", "Contacts")
    # Field used for newest/oldest sorting (some bases lack "Created At").
    AIRTABLE_SORT_FIELD = os.environ.get("AIRTABLE_SORT_FIELD", "Created At")

    # Canonical Airtable field maps (override any entry with env vars,
    # e.g. AIR_EMAIL=email to use a lowercase "email" column).
    AIR_FIELDS = {
        "name": os.environ.get("AIR_NAME", "Name"),
        "email": os.environ.get("AIR_EMAIL", "Email"),
        "phone": os.environ.get("AIR_PHONE", "Phone"),
        "job_title": os.environ.get("AIR_JOB_TITLE", "Job Title"),
        "location": os.environ.get("AIR_LOCATION", "Location"),
        "linkedin_url": os.environ.get("AIR_LINKEDIN", "LinkedIn URL"),
        "skills": os.environ.get("AIR_SKILLS", "Skills"),
        "years_experience": os.environ.get("AIR_YEARS_EXPERIENCE", "Years of Experience"),
        "last_employer": os.environ.get("AIR_LAST_EMPLOYER", "Last Employer"),
        "resume_url": os.environ.get("AIR_RESUME", "Resume"),
        "status": os.environ.get("AIR_STATUS", "Status"),
    }
    AIR_HR_FIELDS = {
        "email": os.environ.get("AIRHR_EMAIL", "Email"),
        "password_hash": os.environ.get("AIRHR_PASSWORD_HASH", "Password Hash"),
        "company_name": os.environ.get("AIRHR_COMPANY_NAME", "Company Name"),
        "phone": os.environ.get("AIRHR_PHONE", "Phone"),
        "role": os.environ.get("AIRHR_ROLE", "Role"),
        "is_verified": os.environ.get("AIRHR_VERIFIED", "Verified"),
        "is_blocked": os.environ.get("AIRHR_BLOCKED", "Blocked"),
        "created_at": os.environ.get("AIRHR_CREATED_AT", "Created At"),
    }
    AIR_CONTACT_FIELDS = {
        "hr_id": os.environ.get("AIRCONTACT_HR_ID", "HR ID"),
        "candidate_id": os.environ.get("AIRCONTACT_CANDIDATE_ID", "Candidate ID"),
        "status": os.environ.get("AIRCONTACT_STATUS", "Status"),
        "created_at": os.environ.get("AIRCONTACT_CREATED_AT", "Created At"),
    }

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "QuickTalent <no-reply@localhost>")

    GOD_EMAIL = os.environ.get("GOD_EMAIL", "").strip().lower()
    GOD_PASSWORD = os.environ.get("GOD_PASSWORD", "")

    # Candidate resume storage bucket (Supabase mode only)
    RESUME_BUCKET = os.environ.get("RESUME_BUCKET", "resumes")

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST)

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_KEY)

    @property
    def airtable_enabled(self) -> bool:
        return bool(self.AIRTABLE_API_KEY and self.AIRTABLE_BASE_ID)

    @property
    def backend_name(self) -> str:
        if self.supabase_enabled:
            return "supabase"
        if self.airtable_enabled:
            return "airtable"
        return "local-dev"

    def has_god(self) -> bool:
        return bool(self.GOD_EMAIL and self.GOD_PASSWORD)


config = Config()
