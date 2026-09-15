"""Development settings overrides for the Django project."""

from .apps.project import COMPONENTS

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]

# Django Components: Reload server on component file changes (dev only)
COMPONENTS["reload_on_file_change"] = True
