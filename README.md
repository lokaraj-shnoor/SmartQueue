# Smart Queue

Counter queue management for offices, clinics and labs. People take a numbered
token from their phone and watch the board instead of standing in a line; staff
call the next person from a console; administrators configure the desks and read
the wait times afterwards.

Django 5, server-rendered. No front-end build step and no JavaScript framework —
two small scripts do the whole client side.

## What it does

**Visitor** — take a token for any open service, see the number, how many people
are ahead, and a rough wait; give up a place; read the history of a token.

**Counter staff** — a console per counter: call next, call again, mark someone
as arrived, finish, or mark a no-show; put a skipped number back in line; open,
pause and close the desk, which opens and closes a shift.

**Administrator** — services, counters, staff accounts, a system-wide pause and
a board announcement; history and wait times for any day.

**The wall board** — a public screen at `/board/` showing what each counter is
serving, the last numbers called, and who is waiting. It refreshes itself and
needs no login.

## Running it

```bash
python -m venv .venv && .venv/Scripts/activate    # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### The database

Postgres is what this runs on. If you have no server to hand, the repo ships one:

```bash
docker compose up -d db
```

That brings up Postgres 16 on 5432 with the database, user and password the
example `DATABASE_URL` already points at, keeping its data in a named volume.

To install it on the machine instead (Windows):

```bash
winget install -e --id PostgreSQL.PostgreSQL.16
```

then create the role and database, giving the role `CREATEDB` because the test
runner makes its own database:

```sql
CREATE ROLE queue_admin WITH LOGIN PASSWORD 'choose-one' CREATEDB;
CREATE DATABASE smartqueue OWNER queue_admin ENCODING 'UTF8';
```

Either way, set `USE_SQLITE=0` and the matching `DATABASE_URL` in `.env`, then
run `migrate`.

`USE_SQLITE=1` is a development escape hatch for a machine with neither. It is
**refused when `DJANGO_DEBUG=0`**: the call desk depends on `SELECT ... FOR
UPDATE` to stop two counters calling the same token, and SQLite has no such
lock, so a production run on it would hand out duplicates under load rather
than fail visibly.

Tests:

```bash
python manage.py test
```

## Deploying

1. **Environment** — set `DJANGO_DEBUG=0`, a long random `DJANGO_SECRET_KEY`,
   `DJANGO_ALLOWED_HOSTS` for the real hostname, and `DATABASE_URL` for the
   Postgres instance. Managed Postgres wants TLS: keep `?sslmode=require` on
   the URL, or set `POSTGRES_SSLMODE=require`.
2. **Migrate and collect static:**

   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

   With `DEBUG=0` static files are served by WhiteNoise from `staticfiles/`,
   with hashed names and gzip, so no separate web server is needed to serve
   them — but `collectstatic` must have run or every page 500s on a missing
   manifest entry.
3. **Run it** — the project is ASGI, and Daphne is already a dependency:

   ```bash
   daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ```

4. **Check the deployment settings:**

   ```bash
   python manage.py check --deploy
   ```

   With `DEBUG=0` the secure cookie flags, HSTS and the SSL redirect all switch
   themselves on. They assume TLS terminates in front of the process; if it
   genuinely does not, set `DJANGO_SSL_REDIRECT=0` or the redirect loops.
5. **Register the production callback** on the Google OAuth client, and set the
   mail credentials, or sign-in and password resets will work locally and
   nowhere else.

## Configuration

Everything lives in `.env`; `.env.example` lists the keys with comments.

### Password resets

Resets are Django's own token flow behind this project's templates. Links work
once and last three hours.

With no `EMAIL_HOST` set, mail is printed to the console — the reset link can be
copied straight out of the `runserver` output, which is enough for development.

For real delivery, any free SMTP account will do. Name the provider and the
host and port are filled in for you, so `.env` carries only the credentials:

```
EMAIL_PROVIDER=brevo
EMAIL_HOST_USER=the-login-from-the-SMTP-page
EMAIL_HOST_PASSWORD=the-SMTP-key
EMAIL_SENDER=Smart Queue <the-address-you-verified@example.com>
```

Then check it, before touching the UI:

```bash
python manage.py mailcheck you@example.com
```

That prints the settings actually in force — never the password — and names the
fix for the usual failures instead of showing a raw SMTP error.

| Provider   | Free allowance | Two-factor needed? | Username is |
|------------|----------------|--------------------|-------------|
| `brevo`    | 300 a day      | no                 | the login on the SMTP page, often a number |
| `smtp2go`  | 1,000 a month  | no                 | the SMTP user you create |
| `mailjet`  | 200 a day      | no                 | the API key (password is the secret key) |
| `resend`   | 3,000 a month  | no                 | literally `resend` (password is the API key) |
| `gmail`    | ~500 a day     | **yes**            | your Gmail address (password must be an app password) |

Gmail is only workable on an account where you can turn on 2-Step Verification;
managed work accounts often forbid it, and without 2FA there is no app password
and the normal account password is rejected. The others need no 2FA at all.

`EMAIL_SENDER` is the address mail appears to come from. Free relays refuse to
send as an address you have not verified with them, so set it to the one you
verified on their dashboard. With Gmail or Outlook, where the login is itself
an address, it can be left out.

Or ignore the presets and set `EMAIL_HOST`, `EMAIL_PORT` and `EMAIL_USE_TLS`
(or `EMAIL_USE_SSL` for port 465) by hand.

### Sign in with Google

Optional: the button only appears once both values are set, so the project runs
with no Google account attached to it.

1. Google Cloud console → **APIs & Services → Credentials → Create credentials →
   OAuth client ID**, type **Web application**.
2. Add the redirect URI, matching your host exactly:
   `http://localhost:8000/accounts/google/callback/` (and the production one).
3. Put the client ID and secret in `.env` as `GOOGLE_OAUTH_CLIENT_ID` and
   `GOOGLE_OAUTH_CLIENT_SECRET`.

The callback URL is built from the host the request came in on, so the
development server has to run on the port registered above — `runserver 8000`
if the redirect URI says `:8000`. A mismatch shows up as Google's
`Error 400: redirect_uri_mismatch`. In production, register that site's own
`https://…/accounts/google/callback/` on the same client, and publish the
consent screen or Google will only let accounts listed as test users in.

The flow is authorization code with PKCE, in `accounts/oauth.py`. Accounts are
matched on the verified Google email, so someone an administrator made staff
keeps that role when they use the button; an unrecognised email becomes a new
visitor account with no password, which can be given one through the forgotten
password flow.

## Layout

```
accounts/   users, roles, sign-in, password resets, Google OAuth
queues/     models, services.py (everything that writes), reports.py (read-only)
dashboard/  the three role dashboards and the admin screens
core/       landing page and the public wall board
```

`queues/services.py` holds every state change — issuing a token, calling,
serving, skipping — each in a transaction, each writing a `QueueEvent`. Views
stay thin: permissions and messages only. Reporting queries are kept separate in
`queues/reports.py` so a slow report never locks the live queue.
