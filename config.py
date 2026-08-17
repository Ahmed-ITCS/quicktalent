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
