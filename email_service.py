import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from config import config

log = logging.getLogger(__name__)

_MAIL_LOG = os.path.join(os.path.dirname(__file__), "var", "mail.log")


def _parse_from():
    raw = config.SMTP_FROM or "QuickTalent <no-reply@localhost>"
    if "<" in raw and ">" in raw:
        name, addr = raw.split("<")
        return formataddr((name.strip(), addr.strip("> ")))
    return raw


def send_email(to, subject, html, text=None, reply_to=None):
    """Send an email via SMTP, or write to var/mail.log when SMTP is not configured."""
    body = text or ""
    if config.smtp_enabled:
        msg = MIMEMultipart("alternative")
        msg["From"] = _parse_from()
        msg["To"] = to
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(body or "", "plain"))
        msg.attach(MIMEText(html, "html"))
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
                server.starttls()
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to], msg.as_string())
            log.info("email sent to %s subject=%s", to, subject)
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("email to %s failed: %s", to, exc)
            return False

    os.makedirs(os.path.dirname(_MAIL_LOG), exist_ok=True)
    entry = (
        f"\n{'=' * 70}\n"
        f"TO: {to}\nSUBJECT: {subject}\nREPLY-TO: {reply_to or 'n/a'}\n"
        f"{'=' * 70}\n{body}\n"
    )
    with open(_MAIL_LOG, "a") as fh:
        fh.write(entry)
    log.info("console-email written to %s (to=%s, subject=%s)", _MAIL_LOG, to, subject)
    return True


def send_verification_email(to, verify_url):
    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:0 auto;padding:32px">
      <h2 style="color:#0f172a;margin:0 0 8px">Verify your email</h2>
      <p style="color:#475569;line-height:1.6">Welcome aboard! Confirm your QuickTalent account by clicking the button below. The link expires in 24 hours.</p>
      <p style="margin:28px 0"><a href="{verify_url}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600">Verify email</a></p>
      <p style="color:#94a3b8;font-size:13px">Or paste this link in your browser:<br>{verify_url}</p>
    </div>"""
    return send_email(
        to,
        "Verify your email — QuickTalent",
        html,
        text=f"Verify your email by opening: {verify_url}",
    )


def send_contact_email(candidate_name, candidate_email, hr, job_title):
    """Notify the candidate that an HR company wants to connect; include the HR's contact details."""
    subject = f"{hr['company_name']} is interested in your profile — {job_title or 'opportunity'}"
    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:0 auto;padding:32px">
      <h2 style="color:#0f172a;margin:0 0 12px">Hi {candidate_name},</h2>
      <p style="color:#475569;line-height:1.6">
        Great news — <strong>{hr['company_name']}</strong> saw your profile on QuickTalent and is
        interested in your experience{(' as <strong>' + job_title + '</strong>') if job_title else ''}.
      </p>
      <p style="color:#475569;line-height:1.6">Their details so you can connect:</p>
      <table style="background:#f8fafc;border-radius:10px;padding:16px;margin:16px 0;width:100%;color:#334155;font-size:14px">
        <tr><td style="padding:4px 0;color:#94a3b8">Company</td><td><strong>{hr['company_name']}</strong></td></tr>
        <tr><td style="padding:4px 0;color:#94a3b8">Contact email</td><td>{hr['email']}</td></tr>
        <tr><td style="padding:4px 0;color:#94a3b8">Phone</td><td>{hr['phone'] or '—'}</td></tr>
      </table>
      <p style="color:#475569;line-height:1.6">
        Simply <strong>reply to this email</strong> to get in touch with them directly.
      </p>
      <p style="color:#94a3b8;font-size:13px">If you are not interested, you can ignore this email.</p>
    </div>"""
    text = (
        f"Hi {candidate_name},\n\n{hr['company_name']} saw your profile on QuickTalent and is "
        f"interested in your experience{(' as ' + job_title) if job_title else ''}.\n\n"
        f"Company: {hr['company_name']}\nContact email: {hr['email']}\nPhone: {hr['phone'] or '—'}\n\n"
        f"Reply to this email to connect with them."
    )
    return send_email(
        candidate_email,
        subject,
        html,
        text=text,
        reply_to=hr["email"],
    )


def send_status_email(candidate_name, candidate_email, hr, status):
    label = {"employed": "Employed", "closed": "Profile closed"}.get(status, status.title())
    subject = f"Status update: {candidate_name} — {label}"
    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:0 auto;padding:32px">
      <h2 style="color:#0f172a;margin:0 0 12px">Hi {candidate_name},</h2>
      <p style="color:#475569;line-height:1.6">
        <strong>{hr['company_name']}</strong> has marked your profile as <strong>{label}</strong> on QuickTalent.
      </p>
      <p style="color:#475569;line-height:1.6">
        {('Congratulations on your new role!' if status == 'employed' else 'Thank you for your time — your profile is now closed.')}
      </p>
      <p style="color:#94a3b8;font-size:13px">Questions? Reply to this email.</p>
    </div>"""
    return send_email(
        candidate_email,
        subject,
        html,
        text=(
            f"Hi {candidate_name},\n\n{hr['company_name']} has marked your profile as {label} on QuickTalent.\n"
            + ("Congratulations on your new role!" if status == "employed" else "Thank you for your time.")
        ),
    )
