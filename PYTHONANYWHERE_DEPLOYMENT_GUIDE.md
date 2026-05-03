# PythonAnywhere Gateway Timeout Fix - Deployment Guide

## 🚨 Problem Analysis

**Current Issue**: `https://quiz.talentinfosys.com/` is taking ~5.7 seconds to respond, causing gateway timeout errors.

**Root Causes**:
1. Database not optimized for shared hosting
2. No performance monitoring
3. Missing PythonAnywhere-specific optimizations
4. Inefficient caching configuration
5. No request timeout handling

## 🎯 Solution Overview

**Expected Result**: Reduce response time from ~5.7s to <1s and eliminate gateway timeouts.

**Implementation Steps**:
1. ✅ Database optimization
2. ✅ Performance monitoring middleware
3. ✅ PythonAnywhere-specific settings
4. ✅ Caching optimization
5. ✅ Error logging and monitoring

## 📋 Step-by-Step Implementation

### Step 1: Update Django Settings

**File**: `interactive_video/settings.py`

**Add these configurations**:

```python
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

# Database optimization
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

# Performance logging
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
        'video_app': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

**Add to MIDDLEWARE**:

```python
MIDDLEWARE = [
    # ... existing middleware ...
    
    # Add performance monitoring middleware
    'video_app.middleware.PerformanceMiddleware',
    'video_app.middleware.DatabaseQueryMiddleware',
]
```

### Step 2: Create Performance Middleware

**File**: `video_app/middleware.py`

**Content**: Already created - monitors response times and logs slow requests.

### Step 3: Optimize Database

**Run the optimization script**:

```bash
cd /path/to/your/Quizapp
python optimize_database.py
```

This will:
- Enable WAL mode for better concurrency
- Optimize cache settings
- Enable memory-mapped I/O
- Test database performance

### Step 4: Update PythonAnywhere WSGI

**File**: `pythonanywhere_wsgi.py`

**Update with**:

```python
import os
import sys
import time

# Add your project directory
project_path = '/home/yourusername/Quizapp'  # Update with your actual path
if project_path not in sys.path:
    sys.path.append(project_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'interactive_video.settings')

import django
django.setup()

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Add performance monitoring
class TimingMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        start_time = time.time()
        
        def custom_start_response(status, headers, exc_info=None):
            response_time = time.time() - start_time
            headers.append(('X-Response-Time', str(response_time)))
            return start_response(status, headers, exc_info)
        
        return self.app(environ, custom_start_response)

application = TimingMiddleware(application)
```

### Step 5: Deploy and Test

**Deployment Steps**:

1. **Upload files** to PythonAnywhere
2. **Run database optimization**:
   ```bash
   python optimize_database.py
   ```
3. **Reload web app** in PythonAnywhere dashboard
4. **Test performance**:
   - Check response times in browser dev tools
   - Look for `X-Response-Time` header
   - Monitor `django.log` for slow requests

### Step 6: Monitor and Troubleshoot

**Performance Monitoring**:

```bash
# Check response times
curl -I https://quiz.talentinfosys.com/

# Look for timing headers
curl -w "@-" -o /dev/null -s "https://quiz.talentinfosys.com/" <<'EOF'
%{http_code}\n%{time_total}\n%{time_connect}\n%{time_starttransfer}\n
EOF
```

**Log Monitoring**:

```bash
# Check Django logs
tail -f /home/yourusername/Quizapp/django.log

# Look for slow requests
grep "Slow request" django.log

# Look for timeout issues
grep "VERY SLOW REQUEST" django.log
```

## 📊 Expected Results

**Before Optimization**:
- Response time: ~5.7 seconds
- Gateway timeout errors
- Poor user experience

**After Optimization**:
- Response time: <1 second
- No gateway timeouts
- Better user experience
- Performance monitoring enabled

## 🔧 Troubleshooting Guide

### If Still Slow After Optimization:

1. **Check database size**:
   ```python
   # Run in Django shell
   from django.db import connection
   with connection.cursor() as cursor:
       cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
       size_mb = cursor.fetchone()[0] / (1024 * 1024)
       print(f"Database size: {size_mb:.2f} MB")
   ```

2. **Check query performance**:
   - Look at `X-DB-Queries` header
   - Optimize slow queries
   - Add database indexes if needed

3. **Check cache hit rate**:
   - Look at `X-Cache-Hit-Rate` header
   - Low hit rates indicate cache issues

4. **Monitor memory usage**:
   - PythonAnywhere has memory limits
   - Check for memory leaks

### Common Issues and Solutions:

**Issue**: Database locked errors
**Solution**: WAL mode should fix this, but if not:
```python
DATABASES['default']['OPTIONS']['timeout'] = 30
```

**Issue**: High memory usage
**Solution**: Reduce cache size:
```python
CACHES['default']['OPTIONS']['MAX_ENTRIES'] = 500
```

**Issue**: Still slow queries
**Solution**: Add database indexes:
```python
# In your models.py
class Category(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    # ...
```

## 📈 Performance Monitoring

**Key Metrics to Monitor**:

1. **Response Time**: Should be <1 second
2. **Database Queries**: Should be <50 per request
3. **Cache Hit Rate**: Should be >50%
4. **Memory Usage**: Should be <512MB on PythonAnywhere

**Alert Thresholds**:

- **Response Time** > 2s: Warning
- **Response Time** > 5s: Critical (potential timeout)
- **DB Queries** > 100: Warning
- **Cache Hit Rate** < 30%: Warning

## 🎉 Success Criteria

**Deployment Success**:
- [ ] Response time <1 second
- [ ] No gateway timeout errors
- [ ] Performance monitoring working
- [ ] Logs show no critical errors
- [ ] All admin pages load quickly

**Long-term Success**:
- [ ] Consistent performance over time
- [ ] No memory leaks
- [ ] Database remains optimized
- [ ] Cache hit rate stable

## 📞 Support

If issues persist:
1. Check PythonAnywhere error logs
2. Monitor Django application logs
3. Test individual database queries
4. Consider upgrading PythonAnywhere plan for more resources

---

**Expected Timeline**: 30 minutes to implement, immediate performance improvement.

**Risk Level**: Low - optimizations are safe and reversible.
