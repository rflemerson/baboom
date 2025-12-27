import os

from .base import *
from .settings import *

env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    from .production import *
else:
    from .development import *
