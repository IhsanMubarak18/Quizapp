"""
Django settings for interactive_video project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ──────────────────────────────────────────────────────────────────────────────
# SECURITY
# ──────────────────────────────────────────────────────────────────────────────

# Read SECRET_KEY from environment; fall back to insecure default for local dev only
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-6i%g)uyn5)vho2kkxlndbo34v%hf9z^co&thi(+^t#8&t1^i4')

# Set DEBUG=False on PythonAnywhere; keep True locally
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# PythonAnywhere domain(s) — replace 'yourusername' with your actual PA username
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.pythonanywhere.com',   # covers yourusername.pythonanywhere.com
]

# CSRF trusted origins for PythonAnywhere (required when DEBUG=False)
CSRF_TRUSTED_ORIGINS = [
    'https://*.pythonanywhere.com',
]


# ──────────────────────────────────────────────────────────────────────────────
# APPLICATION DEFINITION
# ──────────────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'video_app',
    'users',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'interactive_video.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'interactive_video.wsgi.application'


# ──────────────────────────────────────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('SQLITE_NAME', str(BASE_DIR / 'db.sqlite3')),
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'users.CustomUser'


# ──────────────────────────────────────────────────────────────────────────────
# INTERNATIONALISATION
# ──────────────────────────────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_L10N = True
USE_TZ = True
SITE_ID = 1
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ──────────────────────────────────────────────────────────────────────────────
# STATIC & MEDIA FILES
# ──────────────────────────────────────────────────────────────────────────────

STATIC_URL = '/static/'

# collectstatic will gather files here — must be set for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# ──────────────────────────────────────────────────────────────────────────────
# EMAIL
# ──────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER  # OTP emails come from your Gmail address
