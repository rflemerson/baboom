#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔍 Starting Work Verification...${NC}"

# 1. Run Pre-commit
echo -e "\n${GREEN}🛡️  Running Pre-commit Suite...${NC}"
pre-commit run --all-files
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Pre-commit checks failed! Fix code style/types.${NC}"
    exit 1
fi

# 2. Run Unit Tests
echo -e "\n${GREEN}🧪 Running Core Tests...${NC}"
python manage.py test core scrapers
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Tests failed! Fix them before proceeding.${NC}"
    exit 1
fi

echo -e "\n${GREEN}✅ Everything looks good! You are ready to deliver.${NC}"
