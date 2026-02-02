web: gunicorn dashboard.app:server --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 50 --preload --worker-class gthread
