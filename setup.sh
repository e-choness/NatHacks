#!/bin/bash
# ============================================================================
# NatHacks Setup Script
#
# Quickly set up environment files for Docker Compose development.
# Run this script in the project root:
#   bash setup.sh
#
# This script:
# 1. Copies .env.example files to .env (if not already present)
# 2. Provides guidance on configuring optional API keys
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 NatHacks Setup"
echo "==============================================="
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found."
    echo "   Please run this script from the project root directory."
    exit 1
fi

# Copy environment files if they don't exist
echo "📋 Setting up environment files..."
echo ""

# Backend
if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        echo -e "${GREEN}✓${NC} Created backend/.env"
    else
        echo -e "${YELLOW}⚠${NC}  backend/.env.example not found"
    fi
else
    echo "   backend/.env already exists (skipped)"
fi

# Frontend
if [ ! -f "frontend/.env" ]; then
    if [ -f "frontend/.env.example" ]; then
        cp frontend/.env.example frontend/.env
        echo -e "${GREEN}✓${NC} Created frontend/.env"
    else
        echo -e "${YELLOW}⚠${NC}  frontend/.env.example not found"
    fi
else
    echo "   frontend/.env already exists (skipped)"
fi

# Tools
if [ ! -f "tools/.env" ]; then
    if [ -f "tools/.env.example" ]; then
        cp tools/.env.example tools/.env
        echo -e "${GREEN}✓${NC} Created tools/.env"
    else
        echo -e "${YELLOW}⚠${NC}  tools/.env.example not found"
    fi
else
    echo "   tools/.env already exists (skipped)"
fi

echo ""
echo "==============================================="
echo "✅ Environment setup complete!"
echo ""
echo "📝 Optional: Add API keys for enhanced features"
echo ""
echo "   1. Gemini AI (intelligent coaching)"
echo "      - Get key: https://ai.google.dev/tutorials/setup"
echo "      - Edit: backend/.env → GEMINI_API_KEY"
echo ""
echo "   2. Google Cloud Vision (enhanced detection)"
echo "      - Get credentials: https://cloud.google.com/docs/authentication"
echo "      - Edit: backend/.env → GOOGLE_APPLICATION_CREDENTIALS"
echo ""
echo "🐳 Next: Start services with 'docker compose up'"
echo ""
