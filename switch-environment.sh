#!/bin/bash

# Sato AI Environment Switcher
# This script helps you switch between local, development, and production environments

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}🔄 Sato AI Environment Switcher${NC}"
echo ""

if [ "$1" = "local" ]; then
    echo -e "${CYAN}💻 Switching to LOCAL environment...${NC}"
    
    # Remove existing .env if it exists
    if [ -L ".env" ]; then
        rm .env
    fi
    
    # Create symbolic link to local
    ln -s .env.local .env
    
    echo -e "${GREEN}✅ Switched to LOCAL environment${NC}"
    echo ""
    echo -e "${BLUE}📋 Local Configuration:${NC}"
    echo "  Database: sato_dev (development database - safe for testing)"
    echo "  Backend: localhost:8000"
    echo "  Frontend: localhost:3000"
    echo "  Debug: true"
    echo ""
    echo -e "${CYAN}💡 Perfect for local development and testing!${NC}"
    
elif [ "$1" = "dev" ] || [ "$1" = "development" ]; then
    echo -e "${YELLOW}🛠️  Switching to DEVELOPMENT environment...${NC}"
    
    # Remove existing .env if it exists
    if [ -L ".env" ]; then
        rm .env
    fi
    
    # Create symbolic link to development
    ln -s .env.development .env
    
    echo -e "${GREEN}✅ Switched to DEVELOPMENT environment${NC}"
    echo ""
    echo -e "${BLUE}📋 Development Configuration:${NC}"
    echo "  Database: sato_dev (development database - safe for testing)"
    echo "  Backend: sato-backend-dev-397762748853.me-west1.run.app"
    echo "  Frontend: sato-frontend-dev-397762748853.me-west1.run.app"
    echo "  Debug: true"
    echo ""
    echo -e "${YELLOW}⚠️  Remember: Development changes will NOT affect production!${NC}"
    
elif [ "$1" = "prod" ] || [ "$1" = "production" ]; then
    echo -e "${RED}🚨 Switching to PRODUCTION environment...${NC}"
    
    # Remove existing .env if it exists
    if [ -L ".env" ]; then
        rm .env
    fi
    
    # Create symbolic link to production
    ln -s .env.production .env
    
    echo -e "${GREEN}✅ Switched to PRODUCTION environment${NC}"
    echo ""
    echo -e "${BLUE}📋 Production Configuration:${NC}"
    echo "  Database: sato (production database)"
    echo "  Backend: sato-backend-v2-397762748853.me-west1.run.app"
    echo "  Frontend: sato-frontend-397762748853.me-west1.run.app"
    echo "  Debug: false"
    echo ""
    echo -e "${RED}⚠️  WARNING: Changes will affect LIVE PRODUCTION!${NC}"
    
else
    echo -e "${YELLOW}Usage: $0 [local|dev|prod]${NC}"
    echo ""
    echo "Available environments:"
    echo "  local            - Switch to local environment (localhost URLs)"
    echo "  dev, development - Switch to development environment (Cloud Run dev)"
    echo "  prod, production - Switch to production environment (Cloud Run prod)"
    echo ""
    echo "Database Configuration:"
    echo "  ${CYAN}local & dev${NC} → sato_dev (safe for testing)"
    echo "  ${RED}production${NC}   → sato (live production data)"
    echo ""
    echo "Current environment:"
    if [ -L ".env" ]; then
        CURRENT_ENV=$(readlink .env)
        if [ "$CURRENT_ENV" = ".env.local" ]; then
            echo -e "  ${CYAN}💻 LOCAL${NC}"
        elif [ "$CURRENT_ENV" = ".env.development" ]; then
            echo -e "  ${YELLOW}🛠️  DEVELOPMENT${NC}"
        elif [ "$CURRENT_ENV" = ".env.production" ]; then
            echo -e "  ${RED}🚨 PRODUCTION${NC}"
        else
            echo -e "  ${BLUE}❓ UNKNOWN ($CURRENT_ENV)${NC}"
        fi
    else
        echo -e "  ${BLUE}❓ NO ENVIRONMENT SET${NC}"
    fi
fi
