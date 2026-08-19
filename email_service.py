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


def send_contact_email(candidate_name, candidate_email, hr, job_title, approval_url):
    """Ask the candidate to approve sharing their contact details with an interested HR company."""
    subject = f"{hr['company_name']} wants to connect — approve & share your details?"
    html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f8f7;padding:32px 16px">
      <tr><td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:540px;background:#ffffff;border:1px solid #e7ede9;border-radius:16px;overflow:hidden;font-family:Inter,Arial,sans-serif">
          <tr>
            <td style="padding:36px 40px 8px">
              <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%">
                <tr>
                  <td>
                    <table role="presentation" cellpadding="0" cellspacing="0">
                      <tr>
                        <td width="34" height="34" align="center" valign="middle" style="background:#15803d;border-radius:10px;color:#ffffff;font:800 16px/1 Inter,Arial,sans-serif">Q</td>
                        <td style="padding-left:10px;font:800 17px/1 Inter,Arial,sans-serif;color:#101d17;letter-spacing:-0.02em">QuickTalent</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px 0">
              <h1 style="margin:0 0 10px;font:800 24px/1.2 Inter,Arial,sans-serif;color:#101d17;letter-spacing:-0.02em">Hi {candidate_name},</h1>
              <p style="margin:0;color:#34483d;line-height:1.65;font-size:15px">
                <strong>{hr['company_name']}</strong> saw your profile on QuickTalent and would like your contact details{(' for the <strong>' + job_title + '</strong> role') if job_title else ''}.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:26px 40px 0">
              <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%">
                <tr>
                  <td align="center" style="padding-bottom:10px">
                    <a href="{approval_url}" style="display:inline-block;background:#15803d;color:#ffffff;text-decoration:none;padding:14px 30px;border-radius:999px;font:600 15px/1 Inter,Arial,sans-serif">Approve</a>
                  </td>
                </tr>
                <tr>
                  <td align="center">
                    <a href="{approval_url}" style="display:inline-block;background:#ffffff;color:#34483d;text-decoration:none;padding:12px 30px;border-radius:999px;border:1px solid #d4dfd8;font:600 15px/1 Inter,Arial,sans-serif">Not now</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 40px 36px">
              <p style="margin:0;color:#93a79c;font-size:12.5px;line-height:1.6">
                This request came from <strong>{hr['company_name']}</strong> via QuickTalent. If you're not interested, choose "Not now" — they won't see your details.<br>
                If you have questions, just reply to this email.
              </p>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>"""
    text = (
        f"Hi {candidate_name},\n\n"
        f"{hr['company_name']} saw your profile on QuickTalent and wants to connect"
        f"{(' for the ' + job_title + ' role') if job_title else ''}.\n\n"
        f"Company: {hr['company_name']}\nContact email: {hr['email']}\nPhone: {hr['phone'] or '—'}\n\n"
        f"Approve sharing your email, phone, LinkedIn and resume:\n{approval_url}\n"
        f"Not interested? Choose 'Not now' on that page — nothing is shared without your approval."
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
