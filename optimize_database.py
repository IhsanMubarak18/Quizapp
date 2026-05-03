#!/usr/bin/env python3
"""
Database Optimization Script for PythonAnywhere
Optimizes SQLite database for better performance on shared hosting
"""

import os
import sys
import django

# Add project to Python path
project_path = os.path.dirname(os.path.abspath(__file__))
if project_path not in sys.path:
    sys.path.append(project_path)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'interactive_video.settings')
django.setup()


def optimize_sqlite_database():
    """Optimize SQLite database for better performance on PythonAnywhere"""
    
    print("🔧 Optimizing SQLite Database for PythonAnywhere...")
    print("=" * 50)
    
    from django.db import connection
    
    optimizations = [
        {
            'pragma': 'PRAGMA journal_mode=WAL;',
            'description': 'Enable WAL mode for better concurrency',
            'critical': True
        },
        {
            'pragma': 'PRAGMA synchronous=NORMAL;',
            'description': 'Balance between safety and speed',
            'critical': True
        },
        {
            'pragma': 'PRAGMA cache_size=10000;',
            'description': 'Set 10MB cache size',
            'critical': False
        },
        {
            'pragma': 'PRAGMA temp_store=MEMORY;',
            'description': 'Store temp tables in memory',
            'critical': False
        },
        {
            'pragma': 'PRAGMA mmap_size=268435456;',
            'description': 'Enable 256MB memory-mapped I/O',
            'critical': False
        },
        {
            'pragma': 'PRAGMA optimize;',
            'description': 'Optimize database schema',
            'critical': True
        },
        {
            'pragma': 'PRAGMA analysis_limit=1000;',
            'description': 'Limit query planning time',
            'critical': False
        },
        {
            'pragma': 'PRAGMA foreign_keys=ON;',
            'description': 'Enable foreign key constraints',
            'critical': True
        }
    ]
    
    success_count = 0
    critical_success = 0
    
    with connection.cursor() as cursor:
        for opt in optimizations:
            try:
                cursor.execute(opt['pragma'])
                result = cursor.fetchone()
                status = "✓" if result else "✓"
                print(f"{status} {opt['description']}")
                print(f"    {opt['pragma']} -> {result}")
                success_count += 1
                if opt['critical']:
                    critical_success += 1
            except Exception as e:
                print(f"✗ {opt['description']}")
                print(f"    {opt['pragma']} -> ERROR: {e}")
                if opt['critical']:
                    print(f"    ⚠️  This is a critical optimization!")
    
    print("\n" + "=" * 50)
    print(f"Optimization Summary:")
    print(f"  Successful: {success_count}/{len(optimizations)}")
    print(f"  Critical optimizations: {critical_success}/4")
    
    # Test database performance
    print("\n📊 Testing Database Performance...")
    test_database_performance()
    
    # Get database statistics
    print("\n📈 Database Statistics:")
    get_database_stats()
    
    print("\n✅ Database optimization completed!")
    print("\n🔄 Next steps:")
    print("1. Reload your PythonAnywhere web app")
    print("2. Monitor response times")
    print("3. Check django.log for performance issues")


def test_database_performance():
    """Test database performance with common queries"""
    
    from django.db import connection, reset_queries
    import time
    
    reset_queries()
    
    # Test common queries
    test_queries = [
        ("Category Count", "SELECT COUNT(*) FROM video_app_category"),
        ("Question Count", "SELECT COUNT(*) FROM video_app_question"),
        ("Quiz Count", "SELECT COUNT(*) FROM video_app_quiz"),
        ("User Count", "SELECT COUNT(*) FROM auth_user"),
    ]
    
    with connection.cursor() as cursor:
        for name, query in test_queries:
            start_time = time.time()
            try:
                cursor.execute(query)
                result = cursor.fetchone()
                end_time = time.time()
                query_time = (end_time - start_time) * 1000
                print(f"  {name}: {result[0]} records ({query_time:.2f}ms)")
            except Exception as e:
                print(f"  {name}: ERROR - {e}")
    
    # Report total query count
    total_queries = len(connection.queries)
    print(f"  Total queries executed: {total_queries}")


def get_database_stats():
    """Get current database statistics"""
    
    from django.db import connection
    
    stats_queries = [
        ("Database Size", "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"),
        ("Page Count", "PRAGMA page_count"),
        ("Page Size", "PRAGMA page_size"),
        ("Cache Size", "PRAGMA cache_size"),
        ("Journal Mode", "PRAGMA journal_mode"),
        ("Synchronous Mode", "PRAGMA synchronous"),
    ]
    
    with connection.cursor() as cursor:
        for name, query in stats_queries:
            try:
                cursor.execute(query)
                result = cursor.fetchone()
                if "Size" in name:
                    size_mb = result[0] / (1024 * 1024)
                    print(f"  {name}: {size_mb:.2f} MB")
                else:
                    print(f"  {name}: {result[0]}")
            except Exception as e:
                print(f"  {name}: ERROR - {e}")


def check_database_integrity():
    """Check database integrity"""
    
    print("\n🔍 Checking Database Integrity...")
    
    from django.db import connection
    
    integrity_checks = [
        ("Integrity Check", "PRAGMA integrity_check"),
        ("Foreign Key Check", "PRAGMA foreign_key_check"),
        ("Quick Check", "PRAGMA quick_check"),
    ]
    
    with connection.cursor() as cursor:
        for name, query in integrity_checks:
            try:
                cursor.execute(query)
                result = cursor.fetchall()
                if len(result) == 1 and result[0][0] == "ok":
                    print(f"  ✓ {name}: PASSED")
                else:
                    print(f"  ⚠️  {name}: ISSUES FOUND")
                    for row in result:
                        print(f"    {row}")
            except Exception as e:
                print(f"  ✗ {name}: ERROR - {e}")


if __name__ == '__main__':
    try:
        optimize_sqlite_database()
        check_database_integrity()
        
        print("\n🎉 Optimization Complete!")
        print("Reload your PythonAnywhere web app to apply changes.")
        
    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        sys.exit(1)
