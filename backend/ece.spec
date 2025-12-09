# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for ECE_Core - bundles Redis + FastAPI server into single .exe
"""

block_cipher = None

# Collect tiktoken data files
from PyInstaller.utils.hooks import collect_data_files
import os
from pathlib import Path
import glob

# Root base directory for this spec (use cwd because __file__ may not be available during spec execution)
base = Path.cwd()

tiktoken_datas = collect_data_files('tiktoken')
tiktoken_ext_datas = collect_data_files('tiktoken_ext')

# Build the datas list, adding redis data only if it exists
def conditional_redis_datas():
    datas = []
    # Use `base` that was resolved above for the spec
    # Dist folder is expected under the ECE_Core folder for packaged redis binaries
    redis_exe = (base / 'dist' / 'db' / 'redis-server.exe').resolve()
    redis_cli = (base / 'dist' / 'db' / 'redis-cli.exe').resolve()
    redis_conf = (base / 'dist' / 'db' / 'redis.windows.conf').resolve()
    if redis_exe.exists() and redis_cli.exists():
        datas.append((str(redis_exe), 'db'))
        datas.append((str(redis_cli), 'db'))
        if redis_conf.exists():
            datas.append((str(redis_conf), 'db'))
    return datas

redis_datas = conditional_redis_datas()

# Collect all ECE_Core Python files
# Prepare script files to be added into datas (must be done before Analysis call)
script_files = []
for f in glob.glob(str(base / 'scripts' / '**' / '*.*'), recursive=True):
    if os.path.isfile(f):
        rel = os.path.relpath(f, start=str(base))
        script_files.append((f, os.path.dirname(rel)))

a = Analysis(
    ['launcher.py'],
    pathex=[str(base)],
    binaries=[],
    # Add scripts folder into the bundled datas so script modules are available at runtime when packaged

    datas=[
        # Bundle Redis executables and configs
    ] + redis_datas + [
        
        # Bundle ECE_Core modules
        ('src/*.py', 'src'),
        ('src/**', 'src'),
        
        # Bundle .env file (will be copied to work dir on first run)
        ('.env.example', '.'),
    ] + script_files + tiktoken_datas + tiktoken_ext_datas,
    hiddenimports=[
        'uvicorn',
        'fastapi',
        'redis',
    'redis.asyncio',
        'tiktoken',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        'httpx',
        'pydantic',
        'pydantic_settings',
        'dotenv',
        'datetime',
        'datetime.timezone',
        'src.config',
        'src.llm',
        'src.context',
        'src.intelligent_chunker',
        'src.distiller',

        'src.graph',
        'src.markovian_reasoner',
        'src.utils',
        'src.maintenance.repair_wrapper',
        # Ensure the repair scripts are bundled so MemoryWeaver can import them at runtime
        'scripts.repair_missing_links_similarity_embeddings',
        'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PIL._avif', 'PIL.AvifImagePlugin', 'pillow_avif_plugin'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ECE_Core',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX to avoid decompression failures at runtime (PIL plugin .pyd may not decompress reliably)
    # Exclude specific binary modules from UPX even if enabled; particularly the PIL avif binary which can cause decompression issues
    upx_exclude=['PIL\_avif.cp311-win_amd64.pyd', 'PIL\_avif.cp311-win_amd64.pyd.exe', 'PIL/_avif.cp311-win_amd64.pyd'],
    runtime_tmpdir=None,
    console=True,  # Keep console window for logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if you have one
)
