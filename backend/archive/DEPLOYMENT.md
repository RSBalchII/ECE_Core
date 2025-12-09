# ECE_Core Deployment Guide

## 🎯 Three Ways to Run ECE_Core

### 1. **Bundled Executable (Recommended for Deployment)**
Single `.exe` with Redis embedded - no dependencies needed!

```bash
# Build once
.\build_exe.bat

# Run anywhere
cd dist
ECE_Core.exe
```

**What it includes:**
- ✅ Redis server (embedded, auto-starts)
- ✅ ECE_Core FastAPI server
- ✅ All Python dependencies bundled
- ✅ Runs on any Windows machine (no Python needed)

---

### 2. **Launcher Script (Development with embedded Redis)**
Best for development - uses embedded Redis from External-Context-Engine-ECE

```bash
python launcher.py
```

**What it does:**
- Starts Redis from `../External-Context-Engine-ECE/dist/db/redis-server.exe`
- Starts ECE_Core in same process
- Gracefully handles shutdown (Ctrl+C)

---

### 3. **Manual Python (Original Method)**
Full control - you manage Redis separately

```bash
# Terminal 1: Redis (if not running globally)
redis-server

# Terminal 2: ECE_Core
python main.py
```

---

## 📦 Building the Executable

### Prerequisites
```bash
pip install pyinstaller
```

### Build Process
```bash
.\build_exe.bat
```

This creates:
```
dist\
  └── ECE_Core.exe     (single file, ~30-50MB)
```

### What Gets Bundled
- Redis server + CLI tools
- All Python code (main.py, memory.py, core/*, retrieval/*)
- Dependencies (FastAPI, uvicorn, redis, aiosqlite, tiktoken, etc.)
- .env.example (you need to provide .env)

---

## 🚀 Running Options Comparison

| Method | Redis | Python Needed | Best For |
|--------|-------|---------------|----------|
| **ECE_Core.exe** | Embedded | ❌ No | Deployment, sharing |
| **launcher.py** | Embedded | ✅ Yes | Development |
| **main.py** | Separate | ✅ Yes | Advanced dev, debugging |

---

## 📁 Runtime Files

All methods create these in the working directory:

```
ece_memory.db      - SQLite database (auto-created)
redis.conf         - Redis config (auto-created by launcher)
.env              - Your config (copy from .env.example)
```

---

## 🔧 Configuration

### Required: .env file
```bash
# Copy example
cp .env.example .env

# Edit with your settings
notepad .env
```

**Key settings:**
```env
# LLM Server
LLM_API_BASE=http://localhost:8080/v1
LLM_MODEL_NAME=your-model-name

# ECE Server
ECE_HOST=127.0.0.1
ECE_PORT=8000

# Redis (optional - has defaults)
REDIS_HOST=localhost
REDIS_PORT=6379
```

---

## 🎮 Usage Examples

### Start with Launcher
```bash
python launcher.py
```

Output:
```
==================================================
  ECE_Core - External Context Engine
==================================================

🔄 Starting embedded Redis server...
✓ Redis server started (port 6379)

🚀 Starting ECE_Core...
✓ Memory initialized (Redis + SQLite)
✓ LLM client ready
✓ Context manager ready
✓ Graph reasoner ready
✓ Markovian reasoner ready
🎯 ECE_Core running at http://127.0.0.1:8000
```

### Test API
```bash
curl http://localhost:8000/health
```

### Stop
Press **Ctrl+C** - gracefully shuts down Redis and ECE_Core

---

## 🐛 Troubleshooting

**"Redis failed to start"**
- Port 6379 already in use?
- ECE will continue with global Redis or SQLite-only mode

**"Module not found" errors when building**
- Make sure virtual environment is activated
- Run: `pip install -r requirements.txt`

**Executable is huge (>100MB)**
- Normal with bundled dependencies
- Use UPX compression (already enabled in spec)

**Can't connect to LLM**
- Make sure llama.cpp server is running separately
- Check `LLM_API_BASE` in .env

---

## 📝 Development Workflow

```bash
# 1. Edit code
vim memory.py

# 2. Test with launcher (fast iteration)
python launcher.py

# 3. Build exe when ready to deploy
.\build_exe.bat

# 4. Test exe
cd dist
ECE_Core.exe
```

---

## 🎁 Distribution

To share ECE_Core:

```bash
# Package
zip ECE_Core_v1.0.zip dist/ECE_Core.exe .env.example

# Send to user - they need:
1. ECE_Core.exe
2. .env file (configured)
3. Optional: ece_memory.db (if sharing data)
```

User runs: `ECE_Core.exe` - that's it!

---

## ✨ Summary

You now have **3 flexible deployment options**:

1. **Quick test**: `python main.py` (assumes Redis running)
2. **Development**: `python launcher.py` (starts Redis for you)
3. **Production**: `ECE_Core.exe` (everything bundled)

Choose based on your needs! 🚀
