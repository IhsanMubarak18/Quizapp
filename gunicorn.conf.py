import multiprocessing
import os


bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8000')
workers = int(os.getenv('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv('GUNICORN_THREADS', '4'))
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')
