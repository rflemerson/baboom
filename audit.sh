#!/bin/bash

# ANSI color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Code Quality Audit...${NC}\n"

# Function to run a command and report status
run_check() {
    local tool_name="$1"
    local command="$2"
    
    echo -e "${YELLOW}Running ${tool_name}...${NC}"
    eval "$command"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✔ ${tool_name} Passed${NC}\n"
    else
        echo -e "${RED}✘ ${tool_name} Failed${NC}\n"
        # Optional: exit 1 if you want to stop on first failure
    fi
}

# 1. Pre-commit (Runs Ruff, DjLint, DjHTML, CurlyLint, MyPy, Deptry)
# Runs all configured hooks on all files
run_check "Pre-commit Suite" "pre-commit run --all-files"

# 2. Trivy (Container/FS Security)
if command -v trivy &> /dev/null; then
    run_check "Trivy" "trivy fs ."
else
    echo -e "${YELLOW}Trivy is not installed. Skipping.${NC}"
    echo -e "To install Trivy: https://aquasecurity.github.io/trivy/\n"
fi



echo -e "${GREEN}Audit Complete!${NC}"
