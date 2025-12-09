# Building ECE_Core Executable

## Quick Build

```bash
.\build_exe.bat
```

This creates `dist\ECE_Core.exe` - a single executable that:
- ✅ Starts Redis server automatically
- ✅ Starts ECE_Core FastAPI server
- ✅ Bundles all dependencies
- ✅ Runs standalone (no Python needed)

## Running the Executable

```bash
cd dist
ECE_Core.exe
```

The exe will:
1. Start Redis on port 6379
2. Start ECE_Core on http://localhost:8000
3. Create `redis.conf` in current directory
4. Use `ece_memory.db` in current directory

## Running Without Building (Development)

**Option 1: Launcher (Redis + ECE)**
```bash
python launcher.py
```

**Option 2: Manual (like before)**
```bash
# Terminal 1: Start Redis (if not already running globally)
redis-server

# Terminal 2: Start ECE_Core
python main.py
```

## Structure

```
ECE_Core.exe
  ├── Redis server (embedded)
  ├── FastAPI server
  ├── Memory system (SQLite + Redis) [LEGACY]
  ├── Markovian reasoner
  └── Graph reasoner

Runtime files (created in working directory):
  ├── redis.conf      (auto-generated)
  ├── ece_memory.db   (SQLite database)
  └── .env           (copy .env.example and configure)
```

## Deployment

To deploy on another machine:
1. Copy `dist\ECE_Core.exe` to target machine
2. Create `.env` file (or copy your configured one)
3. Run `ECE_Core.exe`

No Python, no Redis install needed! Everything is bundled.

## Troubleshooting

**Redis fails to start:**
- Check if port 6379 is already in use
- ECE will continue with SQLite-only mode (graceful degradation)

**Missing .env:**
- Copy `.env.example` to `.env` and configure
- Or set environment variables manually

**LLM connection fails:**
- Make sure llama.cpp server is running (separate process)
- Configure `LLM_API_BASE` in `.env`
