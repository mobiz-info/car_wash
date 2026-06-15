"""
WSGI config for wash_pilot project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

# Ensure macOS Homebrew libraries (like libgobject for WeasyPrint) are searchable
if sys.platform == 'darwin':
    os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = '/opt/homebrew/lib:' + os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')

application = get_wsgi_application()
