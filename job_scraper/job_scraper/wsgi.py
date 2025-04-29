"""
WSGI config for job_scraper project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'job_scraper.settings')

application = get_wsgi_application()