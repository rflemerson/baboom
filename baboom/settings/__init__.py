import os

from .apps.celery import *

# 3. Add Component Configurations
from .apps.logging import *

# 2. Add Project Specific Configuration (Apps, Middleware, Static, Locale)
from .apps.project import *

# 1. Start with the Pure Django Base Settings
from .base import *

# 4. Apply Environment Specific Overrides (Dev vs Prod)
env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    from .production import *
else:
    from .development import *
