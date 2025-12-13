#!/bin/bash
# Move to parent directory (SatoApp) if in directory called "scripts"

YAML_FILE=${1:-.env.cloudrun.yaml}

if [ "$(basename "$(pwd)")" = "scripts" ]; then
    cd ..
fi
echo "Current directory: $(pwd)"

# Load environment variables from .env file
echo -e "${BLUE}📄 Loading environment variables from .env file...${NC}"
if [ ! -f "$(pwd)/.env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found in SatoApp directory ("$(pwd)/.env")!${NC}"
    echo "Please create a .env file in the SatoApp directory with required environment variables."
    echo "Expected location: $(pwd)/../.env"
    exit 1
fi

if [ -f "${YAML_FILE}" ]; then
    \rm -f ${YAML_FILE}
fi

# Convert .env to YAML format for Cloud Run
echo -e "${BLUE}🔄 Converting .env to Cloud Run YAML format...${NC}"
python3 << 'PYTHON_SCRIPT'
import os
import re
import sys

def parse_env_line(line):
    """Parse a single line from .env file"""
    line = line.strip()
    
    # Skip comments and empty lines
    if not line or line.startswith('#'):
        return None, None
    
    # Must have = sign
    if '=' not in line:
        return None, None
    
    # Split on first = only
    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip()
    
    # Remove surrounding quotes if present
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    
    return key, value

# Read .env file
try:
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
except FileNotFoundError:
    print("ERROR: .env file not found in SatoApp directory!", file=sys.stderr)
    sys.exit(1)

# Parse all environment variables and convert to development URLs
env_vars = {}
# Reserved environment variables that Cloud Run sets automatically
RESERVED_VARS = ['PORT']

for line in lines:
    key, value = parse_env_line(line)
    if key and value:
        # Skip reserved environment variables
        if key in RESERVED_VARS:
            continue
        # Skip placeholder values
        if value.startswith('your-') or value.startswith('your_'):
            continue
        
        # Use values as-is from .env file (no transformation needed)
        # The .env symlink already points to the correct environment file
        env_vars[key] = value

# Write YAML file for Cloud Run
with open('.env.cloudrun.yaml', 'w', encoding='utf-8') as f:
    for key, value in env_vars.items():
        # For YAML, we need to properly escape the value
        if '\n' in value or '"' in value:
            # Use literal block scalar for complex values
            f.write(f'{key}: |-\n')
            for line in value.split('\n'):
                f.write(f'  {line}\n')
        else:
            # Simple quoted value
            f.write(f'{key}: "{value}"\n')

print(f"✅ Converted {len(env_vars)} environment variables to YAML format")
PYTHON_SCRIPT

mv .env.cloudrun.yaml ${YAML_FILE}

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ ERROR: Failed to convert .env to YAML format!${NC}"
    exit 1
fi


# Validate required environment variables
echo -e "${BLUE}🔍 Validating required environment variables...${NC}"
REQUIRED_VARS=("GEMINI_API_KEY" "API_TOKEN" "DATABASE_URL" "DB_PASSWORD")
MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}:" ${YAML_FILE}; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${RED}❌ ERROR: Missing required environment variables:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "${RED}  - $var${NC}"
    done
    echo ""
    echo "Please fill in these variables in your .env file with actual values"
    rm -f ${YAML_FILE}
    exit 1
fi


# Verify YAML file still exists
if [ ! -f "${YAML_FILE}" ]; then
    echo -e "${RED}❌ ERROR: ${YAML_FILE} file not found after build!${NC}"
    exit 1
fi


echo -e "${GREEN}✅ Environment variables loaded and validated with development URLs${NC}"
echo ""

