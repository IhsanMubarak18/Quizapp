"""
PythonAnywhere Gateway Timeout Solutions

This file contains configurations and optimizations to fix gateway timeout issues
on PythonAnywhere deployment of the Django quiz application.

PROBLEM ANALYSIS:
- Site taking ~5.7 seconds to respond (should be <1 second)
- PythonAnywhere has specific timeout limitations
- Need to optimize for shared hosting environment

SOLUTIONS IMPLEMENTED:
1. Database connection optimization
2. Cache configuration for PythonAnywhere
3. Static file serving optimization
4. WSGI configuration improvements
5. Django settings optimization
"""

import os
from pathlib import Path

# ============================================================================
# SOLUTION 1: OPTIMIZED DJANGO SETTINGS FOR PYTHONANYWHERE
# ============================================================================

PYTHONANYWHERE_SETTINGS = """
# Add to settings.py for PythonAnywhere deployment

# ──────────────────────────────────────────────────────────────────────────────
# PYTHONANYWHERE OPTIMIZATIONS
# ──────────────────────────────────────────────────────────────────────────────

# Database optimization for PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data' / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,  # SQLite timeout
            'check_same_thread': False,
        },
        'CONN_MAX_AGE': 60,  # Persistent connections
    }
}

# Optimized cache for PythonAnywhere
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

# Static files optimization for PythonAnywhere
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# PythonAnywhere specific settings
if 'pythonanywhere.com' in os.environ.get('HTTP_HOST', ''):
    DEBUG = False
    ALLOWED_HOSTS = ['quiz.talentinfosys.com', 'www.quiz.talentinfosys.com']
    
    # Disable migrations warning in production
    SILENCED_SYSTEM_CHECKS = ['admin.E408']
    
    # Security headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# Logging for debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
"""

# ============================================================================
# SOLUTION 2: OPTIMIZED WSGI CONFIGURATION
# ============================================================================

PYTHONANYWHERE_WSGI = """
# Replace contents of pythonanywhere_wsgi.py with this:

import os
import sys
import time

# Add your project directory to the Python path
project_path = '/home/yourusername/Quizapp'  # Update with your actual path
if project_path not in sys.path:
    sys.path.append(project_path)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'interactive_video.settings')

# Import Django and set up
import django
django.setup()

# Import WSGI application
from django.core.wsgi import get_wsgi_application

# Optimize for PythonAnywhere
application = get_wsgi_application()

# Add performance monitoring
class TimingMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        start_time = time.time()
        
        def custom_start_response(status, headers, exc_info=None):
            # Add timing headers
            response_time = time.time() - start_time
            headers.append(('X-Response-Time', str(response_time)))
            return start_response(status, headers, exc_info)
        
        return self.app(environ, custom_start_response)

# Apply timing middleware
application = TimingMiddleware(application)
"""

# ============================================================================
# SOLUTION 3: DATABASE OPTIMIZATION SCRIPT
# ============================================================================

DATABASE_OPTIMIZATION = """
# Run this script to optimize database performance

import os
import django
from django.conf import settings
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'interactive_video.settings')
django.setup()

def optimize_database():
    \"\"\"Optimize SQLite database for better performance\"\"\"
    
    # Enable WAL mode for better concurrency
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA cache_size=10000;')
        cursor.execute('PRAGMA temp_store=MEMORY;')
        cursor.execute('PRAGMA mmap_size=268435456;')  # 256MB
        
    print("Database optimized for PythonAnywhere")

if __name__ == '__main__':
    optimize_database()
"""

# ============================================================================
# SOLUTION 4: PERFORMANCE MONITORING
# ============================================================================

PERFORMANCE_MONITORING = """
# Add to views.py for performance monitoring

import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def monitor_performance(func):
    \"\"\"Monitor view performance\"\"\"
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        
        try:
            response = func(request, *args, **kwargs)
            response_time = time.time() - start_time
            
            # Log slow requests
            if response_time > 2.0:  # Log requests taking more than 2 seconds
                logger.warning(
                    f"Slow request: {request.path} took {response_time:.2f}s"
                )
            
            # Add timing header
            response['X-Response-Time'] = f"{response_time:.3f}s"
            return response
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Error in {request.path}: {e} (took {response_time:.2f}s)")
            raise
    
    return wrapper

# Apply to admin views
@monitor_performance
def admin_dashboard(request):
    # ... existing code ...
"""

# ============================================================================
# SOLUTION 5: PYTHONANYWHERE DEPLOYMENT CHECKLIST
# ============================================================================

DEPLOYMENT_CHECKLIST = """
PYTHONANYWHERE DEPLOYMENT CHECKLIST:

1. UPDATE SETTINGS.PHP:
   ✓ Set DEBUG = False
   ✓ Add domain to ALLOWED_HOSTS
   ✓ Configure static files properly
   ✓ Optimize database settings
   ✓ Set up proper logging

2. CONFIGURE WSGI:
   ✓ Update pythonanywhere_wsgi.py
   ✓ Add performance monitoring
   ✓ Set correct paths
   ✓ Test WSGI configuration

3. OPTIMIZE DATABASE:
   ✓ Run database optimization script
   ✓ Enable WAL mode
   ✓ Configure SQLite settings
   ✓ Test database performance

4. STATIC FILES:
   ✓ Run collectstatic
   ✓ Configure static file serving
   ✓ Check file permissions
   ✓ Test static file access

5. MONITOR PERFORMANCE:
   ✓ Add performance middleware
   ✓ Monitor response times
   ✓ Check PythonAnywhere logs
   ✓ Set up error logging

6. TEST EVERYTHING:
   ✓ Test all admin pages
   ✓ Check response times
   ✓ Verify functionality
   ✓ Monitor for timeouts
"""

# ============================================================================
# SOLUTION 6: QUICK FIX IMPLEMENTATION
# ============================================================================

def create_optimized_settings():
    """Create optimized settings file for PythonAnywhere"""
    
    settings_content = f"""
# PythonAnywhere Optimized Settings
# Add these to your settings.py

# Database optimization
DATABASES['default']['OPTIONS'] = {{
    'timeout': 20,
    'check_same_thread': False,
}}
DATABASES['default']['CONN_MAX_AGE'] = 60

# Cache optimization
CACHES = {{
    'default': {{
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'TIMEOUT': 300,
    }}
}}

# Session optimization
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# PythonAnywhere specific
if 'pythonanywhere.com' in os.environ.get('HTTP_HOST', ''):
    DEBUG = False
    ALLOWED_HOSTS = ['quiz.talentinfosys.com', 'www.quiz.talentinfosys.com']
    SILENCED_SYSTEM_CHECKS = ['admin.E408']

# Performance logging
LOGGING = {{
    'version': 1,
    'handlers': {{
        'file': {{
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '{Path.cwd()}/django.log',
        }},
    }},
    'loggers': {{
        'django': {{
            'handlers': ['file'],
            'level': 'INFO',
        }},
    }},
}}
"""
    
    return settings_content

def create_performance_middleware():
    """Create performance monitoring middleware"""
    
    middleware_content = """
# Add to middleware.py or views.py

import time
import logging

logger = logging.getLogger(__name__)

class PerformanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        response_time = time.time() - start_time
        
        # Log slow requests
        if response_time > 2.0:
            logger.warning(f"Slow request: {request.path} took {response_time:.2f}s")
        
        response['X-Response-Time'] = f"{response_time:.3f}s"
        return response

# Add to MIDDLEWARE in settings.py:
# 'video_app.middleware.PerformanceMiddleware',
"""
    
    return middleware_content

# ============================================================================
# IMPLEMENTATION INSTRUCTIONS
# ============================================================================

if __name__ == '__main__':
    print("PYTHONANYWHERE TIMEOUT FIX SOLUTIONS")
    print("=" * 50)
    print()
    print("PROBLEM: https://quiz.talentinfosys.com/ taking ~5.7 seconds")
    print("SOLUTION: Implement the following optimizations:")
    print()
    print("1. Update settings.py with PythonAnywhere optimizations")
    print("2. Configure WSGI for better performance")
    print("3. Optimize SQLite database settings")
    print("4. Add performance monitoring middleware")
    print("5. Run database optimization script")
    print("6. Test and monitor response times")
    print()
    print("EXPECTED RESULT: Response time < 1 second")
    print()
    print("See individual solution sections above for detailed code.")
