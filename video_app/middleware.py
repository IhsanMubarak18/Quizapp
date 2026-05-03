"""
Performance Monitoring Middleware for PythonAnywhere
This middleware monitors response times and logs slow requests
"""

import time
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class PerformanceMiddleware(MiddlewareMixin):
    """
    Middleware to monitor and log performance metrics.
    
    - Adds X-Response-Time header to responses
    - Logs requests taking more than 2 seconds
    - Logs errors for requests taking more than 5 seconds (potential timeout issues)
    - Provides performance insights for debugging
    """
    
    def process_request(self, request):
        """Record start time when request begins"""
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Calculate and log performance metrics when request ends"""
        if hasattr(request, '_start_time'):
            response_time = time.time() - request._start_time
            
            # Add timing header for debugging
            response['X-Response-Time'] = f"{response_time:.3f}s"
            
            # Log slow requests (warning level)
            if response_time > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {response_time:.2f}s from {request.META.get('REMOTE_ADDR')}"
                )
            
            # Log very slow requests (error level - potential timeout issues)
            if response_time > 5.0:
                logger.error(
                    f"VERY SLOW REQUEST: {request.method} {request.path} "
                    f"took {response_time:.2f}s - POTENTIAL TIMEOUT ISSUE"
                )
                
                # Additional logging for debugging timeout issues
                self._log_timeout_details(request, response_time)
        
        return response
    
    def _log_timeout_details(self, request, response_time):
        """Log detailed information for timeout debugging"""
        details = {
            'method': request.method,
            'path': request.path,
            'response_time': response_time,
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
            'remote_addr': request.META.get('REMOTE_ADDR', 'Unknown'),
            'referer': request.META.get('HTTP_REFERER', 'None'),
        }
        
        # Log user information if available
        if hasattr(request, 'user') and request.user.is_authenticated:
            details['user'] = request.user.email
            details['is_staff'] = request.user.is_staff
        
        logger.error(f"Timeout details: {details}")


class DatabaseQueryMiddleware(MiddlewareMixin):
    """
    Middleware to monitor database query performance.
    Useful for identifying slow database operations.
    """
    
    def process_request(self, request):
        """Reset query count at start of request"""
        from django.db import connection
        connection.queries_log.clear()
        request._db_queries = 0
        return None
    
    def process_response(self, request, response):
        """Log database query statistics"""
        from django.db import connection
        
        if hasattr(request, '_db_queries'):
            query_count = len(connection.queries)
            
            # Add query count to response header
            response['X-DB-Queries'] = str(query_count)
            
            # Log high query counts
            if query_count > 50:
                logger.warning(
                    f"High query count: {request.path} executed {query_count} database queries"
                )
            
            # Log very high query counts (potential performance issues)
            if query_count > 100:
                logger.error(
                    f"VERY HIGH QUERY COUNT: {request.path} executed {query_count} database queries"
                )
        
        return response


class CacheMiddleware(MiddlewareMixin):
    """
    Middleware to monitor cache performance.
    """
    
    def process_request(self, request):
        """Track cache hits/misses"""
        request._cache_hits = 0
        request._cache_misses = 0
        return None
    
    def process_response(self, request, response):
        """Log cache performance"""
        if hasattr(request, '_cache_hits'):
            total_requests = request._cache_hits + request._cache_misses
            if total_requests > 0:
                hit_rate = (request._cache_hits / total_requests) * 100
                response['X-Cache-Hit-Rate'] = f"{hit_rate:.1f}%"
                
                # Log low cache hit rates
                if hit_rate < 50 and total_requests > 10:
                    logger.warning(
                        f"Low cache hit rate: {request.path} - {hit_rate:.1f}% "
                        f"({request._cache_hits}/{total_requests})"
                    )
        
        return response
