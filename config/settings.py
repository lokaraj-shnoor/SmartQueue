"""Django settings for the Smart Queue Management System."""
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.contrib.messages import constants as message_constants
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
def clean_host(raw):
    """A bare hostname from whatever someone pasted.

    ALLOWED_HOSTS matches the Host header, which carries no scheme, no path and
    no port. Pasting a full URL in is the usual reason a deployment answers
    every request with DisallowedHost, so take the hostname out of one.
    """
    host = raw.strip().strip('"').strip("'")
    if "//" in host:
        host = host.split("//", 1)[1]
    host = host.split("/", 1)[0]
    # Strip a port, but leave IPv6 literals like [::1] alone.
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.strip().lower()


ALLOWED_HOSTS = [
    cleaned
    for raw in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if (cleaned := clean_host(raw))
]

# Render (and Heroku-likes) publish the hostname they assigned. Trusting it
# means a rename, a new service or a preview environment works without anyone
# remembering to update an environment variable by hand.
for platform_host in ("RENDER_EXTERNAL_HOSTNAME", "WEBSITE_HOSTNAME"):
    assigned = clean_host(os.environ.get(platform_host, ""))
    if assigned and assigned not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(assigned)

# Django checks the Referer on secure POSTs against this list, so every host
# the site answers on needs to be here or forms fail once TLS is in front.
CSRF_TRUSTED_ORIGINS = [
    "https://" + host for host in ALLOWED_HOSTS if host not in {"localhost", "127.0.0.1"}
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "queues",
    "dashboard",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if not DEBUG:
    # Serves the collected static files in production without a separate web
    # server in front. In development the staticfiles app already does it, and
    # STATIC_ROOT does not exist until collectstatic runs, so it only goes in
    # when it has a job. It must sit directly after the security middleware.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "queues.context_processors.system_settings",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- Database -------------------------------------------------------------
# Postgres is the target. USE_SQLITE=1 is a local development escape hatch for
# machines without a Postgres server; it is never the production path.

def postgres_config():
    """Connection settings for Postgres, from DATABASE_URL or the parts.

    CONN_MAX_AGE keeps connections alive between requests; CONN_HEALTH_CHECKS
    makes Django notice one the database has already closed, which is what
    happens behind most managed Postgres services and connection poolers.
    """
    options = {}
    sslmode = os.environ.get("POSTGRES_SSLMODE", "").strip()

    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        parts = urlparse(url)
        query = parse_qs(parts.query)
        # Hosted Postgres URLs usually carry ?sslmode=require. Honour it.
        sslmode = sslmode or (query.get("sslmode", [""])[0])
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parts.path.lstrip("/")) or "smartqueue",
            "USER": unquote(parts.username or ""),
            "PASSWORD": unquote(parts.password or ""),
            "HOST": parts.hostname or "localhost",
            "PORT": str(parts.port or 5432),
        }
    else:
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "smartqueue"),
            "USER": os.environ.get("POSTGRES_USER", "queue_admin"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }

    if sslmode:
        options["sslmode"] = sslmode
    if options:
        config["OPTIONS"] = options

    config["CONN_MAX_AGE"] = int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60"))
    config["CONN_HEALTH_CHECKS"] = True
    return config


USE_SQLITE = env_bool("USE_SQLITE", False)

if USE_SQLITE and not DEBUG:
    # The escape hatch is for a developer without a Postgres server. Shipping
    # it to production would mean a single-writer database file and no
    # SELECT ... FOR UPDATE, which is what keeps two counters from calling the
    # same token. Fail loudly rather than run wrong.
    raise ImproperlyConfigured(
        "USE_SQLITE is on with DJANGO_DEBUG off. Point DATABASE_URL at Postgres, "
        "or set USE_SQLITE=0."
    )

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {"default": postgres_config()}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# In production, static files get hashed names and gzip copies so they can be
# cached forever; that needs `collectstatic` to have run, and it reads the
# manifest it writes. In development there is no manifest and no need for one,
# so the plain storage serves the files straight from disk.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "core:landing"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    # Both assume TLS terminates in front of this process. A deployment that
    # genuinely serves plain HTTP can turn them off rather than loop forever.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", 60 * 60 * 24 * 30))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)
    # Behind a proxy, Django needs telling how a request arrived.
    if env_bool("DJANGO_BEHIND_PROXY", True):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Email ----------------------------------------------------------------
# Password resets are the only mail this system sends, so any free SMTP
# account is enough. Name one in EMAIL_PROVIDER and add the two credentials it
# gives you; the host and port come from the table below.
#
# With no host configured the messages are printed to the console instead, so
# a developer can copy the reset link out of the runserver output without any
# mail account at all.

# Naming a provider fills in its host and port, so .env only carries the two
# credentials. EMAIL_HOST set by hand still wins over the preset.
SMTP_PRESETS = {
    "brevo": ("smtp-relay.brevo.com", 587),
    "mailjet": ("in-v3.mailjet.com", 587),
    "smtp2go": ("mail.smtp2go.com", 587),
    "resend": ("smtp.resend.com", 587),
    "sendgrid": ("smtp.sendgrid.net", 587),
    "gmail": ("smtp.gmail.com", 587),
    "outlook": ("smtp-mail.outlook.com", 587),
}

EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "").strip().lower()
_preset_host, _preset_port = SMTP_PRESETS.get(EMAIL_PROVIDER, ("", 587))

EMAIL_HOST = os.environ.get("EMAIL_HOST", "").strip() or _preset_host
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "") or _preset_port)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
# Port 465 is implicit TLS; 587 is STARTTLS. Setting both is an error.
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", EMAIL_PORT == 465)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", not EMAIL_USE_SSL)
EMAIL_TIMEOUT = 20

# Relays refuse to send as an address you have not proved you own. Most want
# the verified sender address here; only Gmail and Outlook, where the login is
# itself the address, can fall back to the username.
_login_is_an_address = "@" in EMAIL_HOST_USER
DEFAULT_FROM_EMAIL = (
    os.environ.get("EMAIL_SENDER", "").strip()
    or os.environ.get("DEFAULT_FROM_EMAIL", "").strip()
    or (("Smart Queue <" + EMAIL_HOST_USER + ">") if _login_is_an_address else "")
    or "Smart Queue <no-reply@smartqueue.local>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

PASSWORD_RESET_TIMEOUT = 60 * 60 * 3  # three hours

# --- Sign in with Google ---------------------------------------------------
# Optional. The button only appears once both halves are set, so the project
# runs with no Google account attached to it.

GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}
