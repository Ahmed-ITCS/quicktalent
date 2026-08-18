# QuickTalent — How to Use Guide

A step-by-step guide for **HR users** (recruiters & companies) and the **God Admin**.

---

## 1. What is QuickTalent?

A private talent network where HR teams discover **laid-off professionals** ready for their next
opportunity. Candidates' contact details stay **hidden** until a real interest is shown.

**Key rule of the platform:**

> Email, phone, LinkedIn & resume are masked/hidden for everyone. Press **Contact** → the
> candidate gets an **approve / decline email** → only after they approve do **you** unlock their
> full contact details.

---

## 2. For HR Users (Recruiters / Companies)

### 2.1 Create an account

1. Go to the homepage and click **"Get started"**.
2. Fill in the registration form:
   - **Company name** (required)
   - **Work email** (your login + the address candidates will reply to)
   - **Phone number** (required — candidates see this after contact)
   - **Password** (at least 8 characters)
3. Click **Create account**.

### 2.2 Verify your email

- A verification link is emailed to you immediately.
- Open the link (valid for **24 hours**) → your account is activated.
- You can only sign in **after** verification.
- No email? Check spam/junk, or contact the admin.

### 2.3 Sign in

- Use your email + password.
- Blocked or unverified accounts are refused with a clear message.

### 2.4 Browse candidates (Dashboard → Candidates)

The candidate grid shows every available professional with:

- Name, job title, location, years of experience, last employer
- **Skill chips** (up to 4 + count of the rest)
- **Masked contact info** — e.g. `ai***@gmail.com`, `*******0112`

**Filters (top bar):**

| Filter | What it does |
|---|---|
| Search box | Matches candidate **name** |
| Role | Dropdown of job titles |
| Location | Dropdown of cities |
| Skill | Free text, e.g. `React` (matches any skill) |
| Min / Max yrs | Experience range |
| Status | Available / Employed / Closed |
| Sort | Newest, oldest, name A–Z, most experience |

Click **Apply**, or **Reset** to clear. Results are paginated (12 per page).

### 2.5 View a full profile

Click the candidate's name or **View**:

- Full skills list, experience, last employer
- **LinkedIn link and resume download are locked** until the candidate approves your request
- **Contact details panel**:
  - Haven't contacted them → locked box with masked contact preview
  - Request sent → "Awaiting approval" — you see nothing until they approve
  - Request declined → you can **Resend request** (a fresh email goes out)
  - Approved → unlocked box with **full email, phone, LinkedIn, resume** and the connected date

### 2.6 Contact a candidate (the important step)

1. On a candidate card or profile, click **Contact this person**.
2. What happens:
   - A connection record is created instantly
   - The **candidate** receives a branded email from QuickTalent with **two buttons**:
     **"Approve & share my details"** and **"Not now"**
   - The candidate opens the link → a QuickTalent decision page shows **your company name,
     contact email and phone** → they click Approve or Not now
   - If they **approve** → their email, phone, LinkedIn and resume unlock in your contacts
   - If they **decline** → nothing is shared; you can re-request later
3. The candidate's reply to the approval email goes straight to your inbox
   (emails are sent with your address as Reply-To).

Notes:
- You cannot contact a candidate whose status is **Employed** or **Closed**.
- You can only have **one** connection per candidate (no duplicates).

### 2.7 Manage your contacts (My Contacts)

A table of every candidate you've contacted:

- **Approval column** — Pending / Approved / Declined
- **Email & phone** are masked until the candidate **approves**; then they're clickable links
- **Resend** button — re-asks a Pending or Declined candidate (new email, new link)
- **Connected** — date you first made contact
- **Status dropdown** — update the candidate's status:
  - **Employed** → candidate is notified by email ("congratulations on your new role")
  - **Closed** → candidate is notified their profile is closed
  - **Available** → back to the talent pool
- Changing status to Employed/Closed also removes them from "available" in browsing.

> ⚠️ Status changes are visible to all HR teams — only set **Employed** when it's really a hire.

### 2.8 Settings

- **Company profile**: update company name & phone (shown to candidates in contact emails)
- **Change password**: verify current password, set a new one (8+ chars)
- Your email is fixed — it's your identity on the platform.

---

## 3. For the God Admin (you, the owner)

The god account is created automatically on first boot from `.env` (`GOD_EMAIL` / `GOD_PASSWORD`)
and cannot be blocked or deleted. Its sidebar shows the **God Console** section.

### 3.1 Overview

Six live stat cards:

- Total candidates / Available / Employed / Closed
- HR companies / Total connections

Plus two panels: **Recent connections** (who contacted whom, when) and **Latest candidates**.

### 3.2 All Candidates (full control)

Every candidate with **full contact info visible** and:

- **Status dropdown** — change Available / Employed / Closed inline
- **Manage ▸** popover:
  - Edit: name, email, phone, job title, location, LinkedIn, last employer
  - **Delete profile** — permanent, also removes their connection records
- **Contacted by** column — how many companies contacted this candidate

### 3.3 HR Accounts

Every company account with email, phone, verification & block state:

| Action | Effect |
|---|---|
| **Verify** | Marks a pending account as verified (use if their email failed) |
| **Block** | Instantly prevents sign-in (contact records remain) |
| **Unblock** | Restores access |
| **Delete** | Removes account + all their contacts permanently |

The god account itself is shown as **"Protected"** — it can't be modified here.

### 3.4 All Contacts

The full connection matrix:

- Company → candidate, both sides' full email/phone, date, candidate status
- **Delete** removes a connection record (both sides still keep what they've seen)

---

## 4. Emails the system sends

| When | To | What it contains |
|---|---|---|
| HR registers | HR email | Verification link (24h) |
| HR contacts a candidate | Candidate email | Branded request: HR company card + **Approve / Not now** buttons |
| Candidate approves/declines | — | Status flips in the HR's contacts (approved unlocks details) |
| HR marks Employed | Candidate email | Congratulations + company name |
| HR marks Closed | Candidate email | Profile closed notice + company name |

> If email isn't configured (SMTP not set), emails are **logged to `var/mail.log`** for development.

---

## 5. Roles at a glance

| Capability | HR | God Admin |
|---|---|---|
| Browse candidates with filters | ✅ | ✅ |
| See masked contacts | ✅ | ✅ |
| Contact candidates & unlock details | ✅ (after candidate approves) | ✅ |
| Resend an approval request | ✅ | ✅ |
| See own contacts & update status | ✅ | ✅ |
| See ALL candidates + contact info | ❌ | ✅ |
| Edit / delete candidate profiles | ❌ | ✅ |
| Verify / block / delete HR accounts | ❌ | ✅ |
| See all connections matrix | ❌ | ✅ |

---

## 6. Troubleshooting

- **"Please verify your email first"** → click the link from your inbox; request help from the admin if the link expired.
- **"This account has been blocked"** → the admin blocked the account; contact them.
- **"Candidate is not available"** → status is Employed/Closed; candidates return to Available if status is changed back.
- **Candidate not found in search** → clear filters; check skill spelling.
- **Resume won't download** → resume storage not configured for that profile (no resume uploaded).

---

## 7. Quick start checklist

- [ ] Register company account → verify email → sign in
- [ ] Browse with filters to find your first candidates
- [ ] Open a profile, review skills (resume unlocks after approval)
- [ ] Press **Contact** → candidate approves via email → you get their email/phone/LinkedIn/resume
- [ ] Reach out by email (reply thread goes both ways)
- [ ] On hire → mark **Employed** so the network stays fresh
