\# Project rules

Read docs/requirements.md before every task. Django 5, SQLite, Bootstrap 5 (CDN), single app "core". UI text in Thai.



\## Rules that prevent bugs

\- Use Django's built-in views and forms: LoginView, LogoutView, ModelForm, ListView/DetailView/CreateView/UpdateView. No hand-written auth logic.

\- Every template that shows a form renders it with {{ form }} fields through a BootstrapFormMixin (adds class "form-control" or "form-select" to every widget). Never print only a label.

\- Every view that needs login uses a role mixin/decorator: Adopter, Staff, Admin (Django Groups; superuser counts as Admin).

\- Passwords: Argon2 first in PASSWORD\_HASHERS. Audit: simple\_history on every business model.

\- Image uploads: one validate\_image validator (jpg/jpeg/png, max 5 MB, verified with Pillow).

\- PDPA: personal data is saved only after a consent checkbox; store pdpa\_consent\_at.

\- Don't invent URL names or fields: grep the existing code before using one.



\## Definition of done for every task

1\. python manage.py makemigrations \&\& migrate \&\& check

2\. python manage.py test passes (never delete or weaken a test to pass).

3\. core/tests/test\_smoke.py: logs in as each role with the test Client and GETs every URL of that role, asserting status 200 (or 302 for redirects). Add new URLs to it.

4\. Commit.

