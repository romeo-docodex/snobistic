# snobistic/settings.py
from pathlib import Path
import os
from decimal import Decimal

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------------
# Load .env (IMPORTANT)
# -------------------------------------------------------------------------
# Pe VPS cu Apache/mod_wsgi, .env NU este încărcat automat.
# Asta îți permite să folosești .env în dev/staging rapid.
# În prod e recomandat să pui variabilele în Apache (SetEnv) sau systemd.
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-_1fu7oppr0t6=h36sg2eupn8+#&bs7126kyiv7244-+n1(nl@r",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "0"

ALLOWED_HOSTS = [
    "snobistic.ro",
    "www.snobistic.ro",
    "localhost",
    "127.0.0.1",
]

# Pentru Django 4+ în producție (și recomandat și în dev dacă folosești https local)
CSRF_TRUSTED_ORIGINS = [
    "https://snobistic.ro",
    "https://www.snobistic.ro",
]
if DEBUG:
    # dacă rulezi și local pe http
    CSRF_TRUSTED_ORIGINS += ["http://localhost", "http://127.0.0.1"]

# -----------------------------------------------------------------------------
# Apps
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Required for django-allauth
    "django.contrib.sites",

    # External
    "django_countries",
    "phonenumber_field",
    "crispy_forms",
    "crispy_bootstrap5",

    # django-allauth (social login)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.apple",

    # Internal apps
    "core",
    "accounts.apps.AccountsConfig",
    "catalog",
    "cart",
    "orders",
    "auctions",
    "authenticator",
    "messaging",
    "dashboard",
    "payments",
    "support",
    "invoices",
    "logistics",
]

SITE_ID = int(os.environ.get("DJANGO_SITE_ID", "1"))
SITE_NAME = os.environ.get("SITE_NAME", "Snobistic")

# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "snobistic.urls"

# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                # IMPORTANT: allauth are nevoie de request context processor (deja îl ai)
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.login_form_context",
                "cart.context_processors.cart",
                "catalog.context_processors.favorites_badge",
                "catalog.context_processors.mega_menu_categories",
                "core.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "snobistic.wsgi.application"

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = [
    # păstrează login normal (admin + auth clasic)
    "django.contrib.auth.backends.ModelBackend",
    # allauth (necesar pentru social login)
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:buyer_dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# -----------------------------------------------------------------------------
# django-allauth (social login)
# -----------------------------------------------------------------------------
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SnobisticSocialAccountAdapter"

ACCOUNT_EMAIL_VERIFICATION = "optional" if DEBUG else "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http" if DEBUG else "https"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "facebook": {
        "APP": {
            "client_id": os.environ.get("FACEBOOK_APP_ID", ""),
            "secret": os.environ.get("FACEBOOK_APP_SECRET", ""),
            "key": "",
        },
        "METHOD": "oauth2",
        "SCOPE": ["email", "public_profile"],
        "FIELDS": ["id", "email", "name", "first_name", "last_name"],
        "VERIFIED_EMAIL": False,
    },
    "apple": {
        "APP": {
            "client_id": os.environ.get("APPLE_SERVICE_ID", ""),
            "secret": os.environ.get("APPLE_CLIENT_SECRET", ""),
            "key": os.environ.get("APPLE_KEY_ID", ""),
        },
        "SCOPE": ["name", "email"],
    },
}

# -----------------------------------------------------------------------------
# Email / site (Gmail SMTP)
# -----------------------------------------------------------------------------
# IMPORTANT (real talk):
# Gmail SMTP va trimite "From" doar ca adresa Gmail sau ca alias verificat.
# Dacă vrei no-reply@snobistic.ro ca From real, trebuie alias în Gmail (“Send mail as”) + verificare.

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Snobistic <no-reply@snobistic.ro>")

# Emailuri de business (le poți folosi în UI / footer / formulare)
SNOBISTIC_CONTACT_EMAIL = os.environ.get("SNOBISTIC_CONTACT_EMAIL", "support@snobistic.ro")

# Reply-To (unde se duc răspunsurile), folosit în notifications.py
SNOBISTIC_REPLY_TO_EMAIL = os.environ.get("SNOBISTIC_REPLY_TO_EMAIL", SNOBISTIC_CONTACT_EMAIL)

PRIVACY_POLICY_VERSION = os.environ.get("PRIVACY_POLICY_VERSION", "1.0")

# Alege backend-ul din env:
# - dev: django.core.mail.backends.console.EmailBackend
# - prod: django.core.mail.backends.smtp.EmailBackend
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

# Gmail SMTP (când folosești SMTP backend)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

# Recomandat pentru Gmail: STARTTLS pe 587
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"

EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))

# (opțional) prefix subiect, util în staging
EMAIL_SUBJECT_PREFIX = os.environ.get("EMAIL_SUBJECT_PREFIX", "")

# -----------------------------------------------------------------------------
# Security cookies
# -----------------------------------------------------------------------------
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if DEBUG:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
else:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# -----------------------------------------------------------------------------
# Password validators
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------
# i18n / tz
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "ro"
TIME_ZONE = "Europe/Bucharest"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# Static / media
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -----------------------------------------------------------------------------
# Phone / Crispy
# -----------------------------------------------------------------------------
PHONENUMBER_DEFAULT_REGION = "RO"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Stripe
# -----------------------------------------------------------------------------
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

SNOBISTIC_CURRENCY = "RON"

SNOBISTIC_SELLER_THRESHOLDS = {
    "AMATOR": Decimal("0"),
    "RISING": Decimal("3000"),
    "TOP": Decimal("15000"),
    "VIP": Decimal("50000"),
}

SNOBISTIC_COMMISSION_RATES = {
    "AMATOR": Decimal("9.00"),
    "RISING": Decimal("8.00"),
    "TOP": Decimal("7.00"),
    "VIP": Decimal("6.00"),
}

SNOBISTIC_TRUST_SCORE_MIN = 0
SNOBISTIC_TRUST_SCORE_MAX = 100
SNOBISTIC_TRUST_A_MIN = 85
SNOBISTIC_TRUST_B_MIN = 70
SNOBISTIC_TRUST_C_MIN = 50

PUBLIC_DOMAIN = os.environ.get("PUBLIC_DOMAIN", "").strip()
FORCE_HTTPS_LINKS = os.environ.get("FORCE_HTTPS_LINKS", "0").strip() == "1"
