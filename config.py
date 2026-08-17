import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("APP_SECRET_KEY", "dev-secret-change-me")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")

    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

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

    def has_god(self) -> bool:
        return bool(self.GOD_EMAIL and self.GOD_PASSWORD)


config = Config()
