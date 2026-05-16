# Gunicorn configuration
import multiprocessing

bind = '0.0.0.0:5000'
workers = 2 * multiprocessing.cpu_count() + 1
threads = 4
worker_class = 'gthread'
timeout = 120
accesslog = '-'  # stdout
errorlog = '-'
loglevel = 'info'
