#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🧹 Cleaning previous local database (SQLite)...${NC}"
rm -f db.sqlite3

echo -e "${GREEN}🔄 Running migrations...${NC}"
python manage.py makemigrations
python manage.py migrate

echo -e "${GREEN}🌱 Seeding database...${NC}"
python .ai/seed.py

echo -e "${GREEN}🧪 Running Core Tests...${NC}"
python manage.py test core

echo -e "${GREEN}✅ Local environment ready and verified!${NC}"
