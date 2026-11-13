# StrayMatch Bugfix Completion Report

Date: 2026-11-14
Project: Strays / StrayMatch (Django 6.1, SQLite, Bootstrap 5)
Scope: the 15 listed bugs plus the required regression cases.

## 1. Bugs fixed

| # | Bug | Status | Main change |
|---|-----|--------|-------------|
| 1 | Dog edit loses existing intake date | Fixed | Date widgets now render HTML5 `YYYY-MM-DD`; edit form is pre-populated and changing only the name keeps the intake date. |
| 2 | Adopter does not receive/see notifications | Fixed | Added notification center, header unread badge, read/read-all, upcoming-interview reminders, and env-configurable push provider. |
| 3 | Interview cancellation rule | Fixed | Server-side rule is now strictly **more than 24 hours**; exactly 24 hours is rejected. |
| 4 | Home-visit acceptance/confirmation | Fixed | Added adopter acknowledgement (`adopter_confirmed_at`), confirm action, staff visibility, and confirmation reset on reschedule. |
| 5 | Interview slots limited to roughly 7 days | Fixed | Slots are generated across a configurable horizon (default 60 days). |
| 6 | Incorrect interview slot generation | Fixed | Slot boundaries are anchored to shelter opening time and slot duration, never end after closing, never overlap, never are in the past. |
| 7 | Booking form too large / poor usability | Fixed | Reorganized into seven clearly labelled sections while preserving all fields/validation. |
| 8 | Address fields too free-form | Fixed | Added structured province/district/subdistrict/postal-code fields with local Thai administrative data and cascading UI. |
| 9 | Forgot password / password reset | Fixed | Full Django password-reset flow with secure tokens, no account enumeration, Argon2 preserved. |
| 10 | Post-login dashboard lacks useful status | Fixed | Adopter and Staff dashboards now surface relevant workflow items. |
| 11 | Staff navigation hard to scan | Fixed | Grouped Staff navigation/tabs by workflow area; added home-visit list. |
| 12 | Staff interview list needs filtering | Fixed | Added status, text, dog, single date, date range, and upcoming filters. |
| 13 | Follow-up overdue state not clear | Fixed | Derived `is_overdue`; pending past-due items show `เกินกำหนด`; submitted/reviewed items are not marked overdue. |
| 14 | Admin sees excessive personal data | Fixed | Admin no longer accesses adoption workflow pages or protected adoption evidence; admin account pages no longer expose/edit personal details; Django admin minimised. |
| 15 | Audit/history duplicate entries | Fixed | Removed Notification delivery history from the audit ledger, removed unnecessary Profile saves, and added a user filter. |

## 2. Files changed

### Backend

- `config/settings.py` — email/mailer options, push-provider environment configuration, interview slot/horizon settings.
- `config/urls.py` — unchanged (core URLs are included from `core/urls.py`).
- `core/addresses.py` — **new** local Thai address lookup/validation.
- `core/scheduling.py` — **new** deterministic interview-slot generation and conflict detection.
- `core/models.py` — `InterviewRequest.full_address` + cancellation window, structured address fields, `Notification.read_at`, `FollowUp.is_overdue`, `HomeVisit.adopter_confirmed_at`/`can_confirm`.
- `core/forms.py` — HTML5 date formats, structured booking address, slot select/horizon validation, password-reset forms, least-privilege admin account form.
- `core/views.py` — notification centre, dashboard data, strict cancellation, slot conflict logic, Staff filters, home-visit confirmation/list, admin least-privilege, audit filtering.
- `core/urls.py` — password reset, notifications, home-visit confirmation/list.
- `core/context_processors.py` — unread notification count for the header.
- `core/admin.py` — personal data removed from Profile admin, adoption evidence models removed from Django admin, notification message field hidden.
- `core/management/commands/queue_reminders.py` — upcoming-interview reminders.
- `requirements.txt` — added `requests==2.34.2` (already imported by the push dispatcher).

### Templates

- `core/templates/base.html` — notification bell, grouped Staff/Admin navigation.
- `core/templates/notifications/list.html` — **new** notification centre.
- `core/templates/dashboard/adopter.html`, `dashboard/staff.html` — useful status dashboards.
- `core/templates/interviews/book.html` — seven-section form, structured address, cascading selects, slot picker.
- `core/templates/interviews/staff_list.html` — new filters and interview code/date display.
- `core/templates/interviews/detail.html` — structured address and cancellation policy note.
- `core/templates/contracts/detail.html`, `contracts/staff_detail.html` — home-visit confirmation state/action.
- `core/templates/follow_ups/*.html` — `เกินกำหนด` badge.
- `core/templates/home_visits/staff_list.html` — **new** Staff home-visit overview.
- `core/templates/includes/staff_tabs.html` — grouped Staff tabs.
- `core/templates/users/user_list.html`, `users/user_form.html` — removed personal contact columns/fields.
- `core/templates/audit/log.html` — user filter.
- `core/templates/registration/login.html` — `ลืมรหัสผ่าน?` link.
- `core/templates/auth/password_reset_*.html` — **new** password-reset templates (kept out of `registration/` so Django admin templates do not shadow them).
- `static/data/thai_addresses.json` — **new** bundled local Thai administrative data (77 provinces, 928 districts, 7,436 subdistricts).

### Deployment

- `deploy/strays.env.example` — documented email, push, slot/horizon configuration.
- `BUGFIX-completion.md` — this report.

## 3. Database migrations

One migration was added:

- `core/migrations/0011_historicalhomevisit_adopter_confirmed_at_and_more.py`

It adds:

- `InterviewRequest.address_detail`, `district`, `postal_code`, `province`, `subdistrict`
- `HomeVisit.adopter_confirmed_at`
- `Notification.read_at`
- matching fields on the `simple_history` historical models

Existing rows remain valid: all new fields are nullable or blank, and legacy free-text
addresses continue to display through `InterviewRequest.full_address`.

## 4. Tests added/changed

### New test modules

- `core/tests/test_dog_edit.py` — intake date prefill, name-only update, intake date still required.
- `core/tests/test_notification_ui.py` — notification list scoping, unread badge, read/read-all, confirmed-event visibility, interview reminders.
- `core/tests/test_interview_cancel.py` — exact 24-hour boundary, >24h allowed, past/cancelled/other-adopter rejection.
- `core/tests/test_scheduling.py` — deterministic hourly slots, closing boundary, past slots, active/cancelled/legacy overlapping bookings, horizon, configurable duration.
- `core/tests/test_homevisit_confirmation.py` — adopter confirm/acknowledge, permissions, invalid states, staff visibility, reset on edit/approve.
- `core/tests/test_password_reset.py` — login link, known/unknown email, token use, new-password login, Argon2, token reuse rejection.
- `core/tests/test_dashboards.py` — adopter/staff dashboard content and adopter privacy isolation.
- `core/tests/test_followup_overdue.py` — future/today/overdue/submitted/reviewed states and template badges.
- `core/tests/test_privacy_admin.py` — Admin denied adoption workflow pages/evidence, allowed account/report pages, personal fields hidden, Django-admin model restriction, cross-adopter 404s.
- `core/tests/test_audit.py` — Notification history excluded, business history retained, user filter works.

### Updated tests

- `core/tests/test_interviews.py` — structured address data, far-future booking, configurable horizon, unaligned minute rejection, closing boundary, grouped form sections, Staff filters by dog/date range/upcoming/cancelled.
- `core/tests/test_private_media.py` — Admin may open profile photos but not adoption evidence.
- `core/tests/test_smoke.py` — new URLs, Admin least-privilege expectations, grouped Staff tabs.
- `core/tests/test_user_admin.py` — Admin account form no longer exposes or edits personal fields.

## 5. Test-suite result

Commands run from the repository root with the project virtual environment:

```text
python manage.py makemigrations --check --dry-run
No changes detected

python manage.py check
System check identified no issues (0 silenced).

python manage.py test
Ran 231 tests in ~23s
OK
```

All pre-existing regression tests still pass, including:

1. Complete interview booking creates an interview and displays its generated ID.
2. Missing adopter name prevents booking and preserves entered form data.
3. Empty dog name is rejected.
4. JPG follow-up submission succeeds and remains visible.
5. `.txt` follow-up upload is rejected and creates no submission.
6. The previously failing dog-edit regression now passes.

## 6. Security review performed

- **Role checks:** all Staff/Admin/Adopter decorators remain server-side. Admin no longer inherits adoption workflow access.
- **CSRF:** unchanged; new POST actions use `{% csrf_token %}` and `@require_POST` where appropriate.
- **Protected files:** adoption evidence is still protected server-side; Admin is denied `housing`, `interview`, `followup`, and `evaluation` files. Owner and Staff access preserved. Anonymous users are redirected to login.
- **Image validation:** unchanged `validate_image` (JPG/JPEG/PNG, 5 MB, Pillow verification) on all upload paths.
- **Passwords:** Argon2 remains first in `PASSWORD_HASHERS`; password reset uses Django's signed token mechanism.
- **Token logging:** password-reset tokens are not logged by application code. Production SMTP is configured through environment variables; no credentials are committed.
- **PDPA:** consent checkbox and `pdpa_consent_at` behaviour preserved. Admin no longer sees personal contact data in account management.
- **IDOR:** notification list/read, home-visit confirmation, contracts, follow-ups and interviews remain scoped to the owning adopter; cross-adopter access returns 404.
- **Audit integrity:** business history is retained. Only derived notification delivery history is omitted from the audit UI; the underlying history rows are not deleted.

## 7. Production configuration required after deployment

1. **Apply migrations**

   ```bash
   python manage.py migrate
   ```

   This applies `core.0011_...`.

2. **Collect static files**

   ```bash
   python manage.py collectstatic --noinput
   ```

   This is required for `static/data/thai_addresses.json` used by the cascading address selects.

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   `requests` was already imported by the push dispatcher and is now explicitly listed.

4. **Password-reset email (required for usable reset emails)**

   Set these in `/etc/strays.env` (do not commit real values):

   ```ini
   DEFAULT_FROM_EMAIL=noreply@strays.peerapeek.cc
   EMAIL_HOST=smtp.example.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=...
   EMAIL_HOST_PASSWORD=...
   EMAIL_USE_TLS=True
   # Optional override:
   # EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   ```

   Django default token expiry is 3 days; override with `PASSWORD_RESET_TIMEOUT` if desired.
   If SMTP is not configured, password reset requests will still not reveal account existence, but emails cannot be delivered.

5. **Push notification provider**

   Set the provider URL in production; an empty URL keeps development mode:

   ```ini
   PUSH_PROVIDER_URL=https://push.example.com/send
   PUSH_TIMEOUT=10
   PUSH_MAX_ATTEMPTS=4
   PUSH_RETRY_DELAY=60
   ```

6. **Schedule background jobs**

   `queue_reminders` and `send_notifications` are still management commands. They must be scheduled on the server, for example:

   ```cron
   */15 * * * * cd /srv/strays && .venv/bin/python manage.py send_notifications
   0 * * * * cd /srv/strays && .venv/bin/python manage.py queue_reminders
   ```

   Or equivalent systemd timers. Without them, in-app notifications are still visible immediately, but external push delivery and automatic reminders will not run.

7. **Optional booking configuration**

   ```ini
   INTERVIEW_BOOKING_HORIZON_DAYS=60
   INTERVIEW_SLOT_MINUTES=60
   ```

   Shelter opening/closing times remain in `ShelterSettings`.

## 8. Manual QA checklist

### Dog editing
- [ ] Log in as Staff, open a dog with an existing intake date.
- [ ] Confirm the date field shows the existing date in `YYYY-MM-DD` form.
- [ ] Change only the name and save; confirm success and unchanged intake date.
- [ ] Clear the intake date and confirm validation still rejects the form.

### Notifications
- [ ] Book an interview; confirm a notification appears in the header bell/list.
- [ ] Confirm an interview as Staff; confirm the adopter sees the confirmation notification.
- [ ] Reject an interview / record a result; confirm the adopter sees those notifications.
- [ ] Run `queue_reminders` with an interview inside the reminder window; confirm the adopter reminder exists and is deduplicated.
- [ ] Mark one/all notifications as read; confirm the badge count changes.

### Interview cancellation
- [ ] Cancel an interview more than 24 hours away; succeeds.
- [ ] Try exactly 24 hours away; rejected with the Thai more-than-one-day message.
- [ ] Try less than 24 hours/past/already cancelled; rejected.

### Home visits
- [ ] Staff schedules a home visit; adopter sees date/time, status, and confirm button.
- [ ] Adopter confirms; Staff sees “ยืนยันแล้ว”.
- [ ] Adopter requests reschedule; confirm action is hidden until the new date is approved.
- [ ] Staff edits/approves a reschedule; confirmation resets and adopter can confirm again.

### Booking / slots / address
- [ ] Booking page shows the seven sections.
- [ ] Province → district → subdistrict → postal code cascades correctly.
- [ ] A slot 20+ days ahead is selectable (default horizon 60).
- [ ] Only aligned times are offered; no 18:00 start when closing is 18:00.
- [ ] Existing booking is excluded; adjacent booking remains available.
- [ ] Invalid province/district/postal combination is rejected server-side.

### Password reset
- [ ] Login page shows `ลืมรหัสผ่าน?`.
- [ ] Request reset for a known email; receive email with secure link.
- [ ] Set a new password; log in with the new password.
- [ ] Request reset for an unknown email; response is the same and no email is sent.
- [ ] Reuse an old reset link; rejected.

### Dashboards / Staff filters / overdue
- [ ] Adopter dashboard shows upcoming interview, contract status, home visit, pending follow-ups, notifications.
- [ ] Staff dashboard shows pending requests, upcoming interviews/home visits, follow-ups to review, overdue follow-ups.
- [ ] Staff interview list filters by status, dog, date, range, upcoming.
- [ ] Pending past-due follow-up shows `เกินกำหนด`; submitted/reviewed does not.

### Privacy / audit
- [ ] Admin cannot open Staff interview/contract/follow-up/home-visit URLs (403).
- [ ] Admin cannot open housing/interview/follow-up/evaluation protected files (403).
- [ ] Admin can still open account management and reports.
- [ ] Admin user list/edit no longer shows or edits full name/phone/address.
- [ ] Audit log no longer floods with notification delivery history and supports user filtering.

## 9. Known limitations / notes

- External push delivery depends on a configured `PUSH_PROVIDER_URL` and a scheduled `send_notifications` process. The in-app notification centre works independently of provider delivery.
- Django admin is treated as a superuser/break-glass tool. Adoption-evidence models were removed from it and Profile personal fields were minimised, but a server-level superuser can always query the database directly; that cannot be prevented inside the application.
- The Thai administrative dataset is bundled locally to avoid an external API/dependency. Future updates require replacing `static/data/thai_addresses.json`.
- Notification read state is per-user and explicit. There is no email read-receipt or push read synchronisation.
- No credentials, generated databases, uploaded user files, or environment-specific data were committed.
