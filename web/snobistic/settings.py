from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-_1fu7oppr0t6=h36sg2eupn8+#&bs7126kyiv7244-+n1(nl@r'

DEBUG = True

ALLOWED_HOSTS = []


# ===============================
# APLICAȚII ACTIVĂRI
# ===============================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # External
    'django_countries',
    'phonenumber_field',
    'crispy_forms',
    'crispy_bootstrap5',

    # Internal apps
    'accounts',
    'auctions',
    'cart',
    'chat',
    'core',
    'dashboard',
    'orders',
    'payments',
    'products',
    'shop',
    'support',
    'wallet',
]

# ===============================
# MIDDLEWARE
# ===============================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ===============================
# ROUTING & TEMPLATES
# ===============================

ROOT_URLCONF = 'snobistic.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # folosește directoarele globale
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'snobistic.wsgi.application'


# ===============================
# DATABASE
# ===============================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ===============================
# AUTENTIFICARE PERSONALIZATĂ
# ===============================

AUTH_USER_MODEL = 'accounts.CustomUser'


# ===============================
# VALIDĂRI PAROLĂ
# ===============================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ===============================
# LOCALIZARE
# ===============================

LANGUAGE_CODE = 'ro'

TIME_ZONE = 'Europe/Bucharest'

USE_I18N = True
USE_L10N = True
USE_TZ = True


# ===============================
# STATIC & MEDIA FILES
# ===============================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ===============================
# EMAIL CONFIG (pentru activare cont & reset)
# ===============================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # înlocuiește cu SMTP în producție
DEFAULT_FROM_EMAIL = 'no-reply@snobistic.com'


# ===============================
# TELEFON
# ===============================

PHONENUMBER_DEFAULT_REGION = 'RO'


# ===============================
# Formatare CRISPY
# ===============================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# ===============================
# DEFAULT PRIMARY KEY
# ===============================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
