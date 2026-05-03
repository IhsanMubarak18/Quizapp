"""
PythonAnywhere Settings Optimization
Add these configurations to your interactive_video/settings.py
"""

# ============================================================================
# ADD TO YOUR SETTINGS.PY - PYTHONANYWHERE OPTIMIZATIONS
# ============================================================================

PYTHONANYWHERE_OPTIMIZATIONS = """
# ──────────────────────────────────────────────────────────────────────────────
# PYTHONANYWHERE SPECIFIC OPTIMIZATIONS
# ──────────────────────────────────────────────────────────────────────────────

# Detect PythonAnywhere environment
is_pythonanywhere = 'pythonanywhere.com' in os.environ.get('HTTP_HOST', '')

if is_pythonanywhere:
    DEBUG = False
    ALLOWED_HOSTS = ['quiz.talentinfosys.com', 'www.quiz.talentinfosys.com']
    SILENCED_SYSTEM_CHECKS = ['admin.E408']
    
    # Security headers for production
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Database optimization for PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data' / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,  # Reduce SQLite timeout
            'check_same_thread': False,
        },
        'CONN_MAX_AGE': 60,  # Persistent connections
    }
}

# Optimized cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pythonanywhere-cache',
        'TIMEOUT': 300,  # 5 minutes
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

# Session optimization
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Database connection optimization
CONN_MAX_AGE = 60

# Static files optimization
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Logging configuration for debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'video_app': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Performance optimization settings
USE_TZ = True
USE_L10N = True

# Email settings (keep existing)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
"""

# ============================================================================
# MIDDLEWARE ADDITION
# ============================================================================

MIDDLEWARE_ADDITION = """
# Add to MIDDLEWARE list in settings.py (after existing middleware):

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Add performance monitoring middleware
    'video_app.middleware.PerformanceMiddleware',
]
"""

# ============================================================================
# PERFORMANCE MIDDLEWARE
# ============================================================================

PERFORMANCE_MIDDLEWARE = """
# Create video_app/middleware.py

import time
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class PerformanceMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, '_start_time'):
            response_time = time.time() - request._start_time
            
            # Add timing header
            response['X-Response-Time'] = f"{response_time:.3f}s"
            
            # Log slow requests
            if response_time > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {response_time:.2f}s from {request.META.get('REMOTE_ADDR')}"
                )
            
            # Log very slow requests (potential timeout issues)
            if response_time > 5.0:
                logger.error(
                    f"VERY SLOW REQUEST: {request.method} {request.path} "
                    f"took {response_time:.2f}s - POTENTIAL TIMEOUT ISSUE"
                )
        
        return response
"""

# ============================================================================
# DATABASE OPTIMIZATION SCRIPT
# ============================================================================

DB_OPTIMIZATION_SCRIPT = """
# Create optimize_database.py in project root

import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'interactive_video.settings')
django.setup()

def optimize_sqlite_database():
    \"\"\"Optimize SQLite database for better performance\"\"\"
    
    optimizations = [
        'PRAGMA journal_mode=WAL;',           # Better concurrency
        'PRAGMA synchronous=NORMAL;',         # Balance between safety and speed
        'PRAGMA cache_size=10000;',           # 10MB cache
        'PRAGMA temp_store=MEMORY;',          # Store temp tables in memory
        'PRAGMA mmap_size=268435456;',        # 256MB memory-mapped I/O
        'PRAGMA optimize;',                   # Optimize database
        'PRAGMA analysis_limit=1000;',        # Limit query planning
    ]
    
    with connection.cursor() as cursor:
        for pragma in optimizations:
            try:
                cursor.execute(pragma)
                result = cursor.fetchone()
                print(f"✓ {pragma} -> {result}")
            except Exception as e:
                print(f"✗ {pragma} -> ERROR: {e}")
    
    print("\\nDatabase optimization completed!")

if __name__ == '__main__':
    optimize_sqlite_database()
"""

# ============================================================================
# DEPLOYMENT INSTRUCTIONS
# ============================================================================

DEPLOYMENT_STEPS = """
PYTHONANYWHERE DEPLOYMENT STEPS:

1. UPDATE SETTINGS.PY:
   - Add the PYTHONANYWHERE_OPTIMIZATIONS to your settings.py
   - Add PerformanceMiddleware to MIDDLEWARE list
   - Update ALLOWED_HOSTS with your domain

2. CREATE MIDDLEWARE FILE:
   - Create video_app/middleware.py
   - Add the PERFORMANCE_MIDDLEWARE code
   - Make sure video_app is in INSTALLED_APPS

3. OPTIMIZE DATABASE:
   - Run the database optimization script
   - Test database performance

4. UPDATE WSGI:
   - Reload your PythonAnywhere web app
   - Check the error logs for any issues

5. MONITOR PERFORMANCE:
   - Check response times in browser dev tools
   - Monitor the X-Response-Time header
   - Check django.log for slow requests

6. TEST THOROUGHLY:
   - Test all admin pages
   - Test quiz functionality
   - Monitor for timeout issues

EXPECTED RESULTS:
- Response time should drop from ~5.7s to <1s
- No more gateway timeout errors
- Better overall performance
"""

print("PYTHONANYWHERE TIMEOUT FIX")
print("=" * 40)
print()
print("FILES TO CREATE/MODIFY:")
print("1. interactive_video/settings.py - Add optimizations")
print("2. video_app/middleware.py - Performance monitoring")
print("3. optimize_database.py - Database optimization")
print()
print("QUICK FIX STEPS:")
print("1. Add database optimizations to settings.py")
print("2. Add performance middleware")
print("3. Run database optimization script")
print("4. Reload PythonAnywhere web app")
print("5. Monitor performance")
print()
print("This should reduce response time from 5.7s to <1s!")
