@echo off
REM ============================================================================
REM NatHacks Setup Script (Windows)
REM
REM Quickly set up environment files for Docker Compose development.
REM Run this script in the project root:
REM   setup.bat
REM
REM This script:
REM 1. Copies .env.example files to .env (if not already present)
REM 2. Provides guidance on configuring optional API keys
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo 🚀 NatHacks Setup
echo ===============================================
echo.

REM Check if we're in the right directory
if not exist "docker-compose.yml" (
    echo ❌ Error: docker-compose.yml not found.
    echo    Please run this script from the project root directory.
    exit /b 1
)

REM Copy environment files if they don't exist
echo 📋 Setting up environment files...
echo.

REM Backend
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env" >nul
        echo ✓ Created backend\.env
    ) else (
        echo ⚠  backend\.env.example not found
    )
) else (
    echo    backend\.env already exists (skipped^)
)

REM Frontend
if not exist "frontend\.env" (
    if exist "frontend\.env.example" (
        copy "frontend\.env.example" "frontend\.env" >nul
        echo ✓ Created frontend\.env
    ) else (
        echo ⚠  frontend\.env.example not found
    )
) else (
    echo    frontend\.env already exists (skipped^)
)

REM Tools
if not exist "tools\.env" (
    if exist "tools\.env.example" (
        copy "tools\.env.example" "tools\.env" >nul
        echo ✓ Created tools\.env
    ) else (
        echo ⚠  tools\.env.example not found
    )
) else (
    echo    tools\.env already exists (skipped^)
)

echo.
echo ===============================================
echo ✅ Environment setup complete!
echo.
echo 📝 Optional: Add API keys for enhanced features
echo.
echo    1. Gemini AI (intelligent coaching^)
echo       - Get key: https://ai.google.dev/tutorials/setup
echo       - Edit: backend\.env ^> GEMINI_API_KEY
echo.
echo    2. Google Cloud Vision (enhanced detection^)
echo       - Get credentials: https://cloud.google.com/docs/authentication
echo       - Edit: backend\.env ^> GOOGLE_APPLICATION_CREDENTIALS
echo.
echo 🐳 Next: Start services with 'docker compose up'
echo.
pause
