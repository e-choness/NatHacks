# Environment Setup Guide

## How Docker Compose Automatically Handles Environment Files

**TL;DR**: Just run `docker compose up` — it automatically loads `.env.example` files as defaults.

---

## Automatic Configuration (No Setup Scripts Needed)

Docker Compose has been configured to automatically load environment variables with a fallback system:

```yaml
# In docker-compose.yml for each service:
env_file:
  - service/.env.example    # Defaults (loaded first)
  - service/.env            # Custom overrides (loaded second, if exists)
```

### How It Works

1. **First load**: `service/.env.example` (always exists, contains safe defaults)
2. **Second load**: `service/.env` (if it exists, overrides the defaults)
3. **Result**: 
   - Works out-of-the-box without any setup
   - Allows customization by creating `.env` files
   - Later files override earlier ones

### Example

```
Scenario 1: User just cloned the repo
├── backend/.env.example  ✓ Exists
├── backend/.env          ✗ Doesn't exist
Result: Uses .env.example defaults automatically

Scenario 2: User wants to customize (added API keys)
├── backend/.env.example  ✓ Exists
├── backend/.env          ✓ Exists (user created this)
Result: Loads both, .env overrides .env.example
```

---

## Three Ways to Use

### Option 1: Zero Setup (Recommended for Testing)

Works immediately after cloning:

```bash
git clone <repo-url>
cd NatHacks-fork
docker compose up
```

✅ Uses `.env.example` defaults automatically  
✅ No setup scripts needed  
✅ Basic features work without API keys  

---

### Option 2: Customize API Keys (Recommended for Production)

Add your own API keys for enhanced features:

```bash
# Copy example files to create custom files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp tools/.env.example tools/.env

# Edit to add your API keys
nano backend/.env

# Uncomment and fill in:
# GEMINI_API_KEY=your_key_here
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Restart services
docker compose down
docker compose up
```

✅ Uses your custom values  
✅ Still has `.env.example` as fallback  
✅ Full-featured with Gemini AI and Google Cloud Vision  

---

### Option 3: Use Setup Scripts (Alternative)

If you prefer automated setup:

```bash
# macOS/Linux
bash setup.sh

# Windows
setup.bat
```

These scripts copy `.env.example` → `.env` for you (optional convenience).

---

## Environment Variables

### What Each `.env.example` Contains

#### `backend/.env.example`

```env
# Database (auto-configured by Docker Compose)
DATABASE_URL=postgresql://user:password@localhost:5432/appdb
REDIS_URL=redis://localhost:6379/0

# Optional: Gemini AI for intelligent coaching
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Google Cloud Vision for enhanced detection
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Optional: Vision pipeline tuning
DETECT_SCALE=0.75
REDUCE_MOTION=false
ARUCO_STRIDE=2

# Server settings
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

#### `frontend/.env.example`

```env
# Backend connection URLs
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Disable telemetry
NEXT_TELEMETRY_DISABLED=1
```

#### `tools/.env.example`

```env
# Nginx configuration (optional)
# NGINX_PORT=80
# NGINX_WORKERS=4
```

---

## When to Create Custom `.env` Files

### You Should Create `.env` If:

- ✅ You have a Gemini API key and want AI coaching
- ✅ You have Google Cloud credentials for enhanced vision
- ✅ You want to change default API URLs
- ✅ You're deploying to production
- ✅ You need to tune vision pipeline parameters

### You Don't Need `.env` If:

- ✅ Testing locally without external services
- ✅ Using basic computer vision features
- ✅ Running the app for development
- ✅ Don't have API keys yet

---

## Getting API Keys

### Gemini AI (Optional but Recommended)

```
1. Visit: https://ai.google.dev/tutorials/setup
2. Click "Get API Key"
3. Create a new project
4. Copy the API key
5. Add to backend/.env:
   GEMINI_API_KEY=<paste-here>
```

**Provides**: Intelligent coaching feedback, natural language understanding

### Google Cloud Vision (Optional)

```
1. Go to: https://cloud.google.com/docs/authentication/getting-started
2. Create a new GCP project
3. Enable the Vision API
4. Create a service account
5. Download the service account JSON key
6. Add to backend/.env:
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/downloaded/key.json
```

**Provides**: Enhanced object detection fallback, OCR, scene understanding

---

## Workflow Examples

### Example 1: Local Development (No API Keys)

```bash
git clone <repo-url>
cd NatHacks-fork
docker compose up
# Access http://localhost:3000
# Basic features work with .env.example defaults
```

### Example 2: Adding Gemini Later

```bash
# Already running with defaults
docker compose ps

# Got a Gemini API key? Add it:
cp backend/.env.example backend/.env
echo "GEMINI_API_KEY=sk-..." >> backend/.env

# Restart
docker compose restart api
```

### Example 3: Production Deployment

```bash
# Copy examples to custom files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Add all your API keys and production URLs
# Edit backend/.env: Add GEMINI_API_KEY, GOOGLE_APPLICATION_CREDENTIALS
# Edit frontend/.env: Change API URLs to your production URLs

# Deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

---

## Troubleshooting

### Services Won't Start

Check if `.env.example` files exist:

```bash
ls -la backend/.env.example
ls -la frontend/.env.example
ls -la tools/.env.example
```

If missing, get fresh copies from git:

```bash
git checkout backend/.env.example frontend/.env.example tools/.env.example
```

### Want to Reset to Defaults

```bash
# Remove custom .env files
rm backend/.env frontend/.env tools/.env

# Restart (will use .env.example)
docker compose down && docker compose up
```

### Confused About Which File Is Used

```bash
# Check what environment variables are actually set in the container
docker compose exec api printenv | grep GEMINI
docker compose exec api printenv | grep DATABASE
```

---

## Key Files Reference

| File | Purpose | Git Tracked? | User Editable? |
|------|---------|-------------|---------------|
| `.env.example` | Default values | ✅ Yes | ⚠️ Not recommended |
| `.env` | Custom values | ❌ No (.gitignore) | ✅ Yes |
| `docker-compose.yml` | Service config | ✅ Yes | ⚠️ Only if needed |

---

## Quick Decision Tree

```
Do you want to use Gemini AI or Google Cloud Vision?
│
├─ NO (just testing basic features)
│  └─→ Run: docker compose up
│      Uses .env.example automatically ✅
│
└─ YES (production or enhanced features)
   └─→ Run: cp backend/.env.example backend/.env
       Edit: nano backend/.env (add API keys)
       Run: docker compose up
       Uses .env with your API keys ✅
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Default setup** | Works without any configuration |
| **Customization** | Copy `.env.example` to `.env` and edit |
| **API keys** | Optional, add if you have them |
| **Restart needed** | Yes, if you change `.env` files |
| **Setup scripts** | Optional convenience, not required |

**Bottom line**: Clone, run `docker compose up`, start developing. 🚀
