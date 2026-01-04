import os

# 1. Start with the Pure Django Base Settings
from baboom.django.base import *

from .celery import *

# 3. Add Component Configurations
from .logging import *

# 2. Add Project Specific Configuration (Apps, Middleware, Static, Locale)
from .project import *

# 4. Apply Environment Specific Overrides (Dev vs Prod)
env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    from baboom.django.production import *
else:
    from baboom.django.development import *
