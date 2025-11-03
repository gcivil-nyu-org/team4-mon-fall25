"""
Django settings for testing on Travis CI.

This file extends the base settings with test-specific configurations.
"""
from .settings import *

# Use SQLite for tests (faster than PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # In-memory database for speed
    }
}

# Use InMemoryChannelLayer for tests (no Redis required)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Disable migrations for faster tests
# Comment this out if you need to test migrations
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

# MIGRATION_MODULES = DisableMigrations()

# Security settings for tests
SECRET_KEY = 'test-secret-key-unsafe-for-production'
DEBUG = True
ALLOWED_HOSTS = ['*']

# Disable CSRF for API tests
MIDDLEWARE = [m for m in MIDDLEWARE if 'CsrfViewMiddleware' not in m]

# Logging configuration for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Password validators - disable for faster test user creation
AUTH_PASSWORD_VALIDATORS = []

# Email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Static files
STATIC_ROOT = BASE_DIR / 'test_staticfiles'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'