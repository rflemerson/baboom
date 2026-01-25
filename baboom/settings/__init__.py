import os

from .apps.celery import *
from .apps.logging import *
from .apps.project import *
from .base import *

env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    from .production import *
else:
    from .development import *
