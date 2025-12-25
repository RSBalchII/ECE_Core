# GPU Resource Management Fixes

## Overview
This document outlines the fixes implemented to resolve GPU resource contention and timeout issues in the ECE_Core system.

## Issues Identified
1. **GPU Lock Timeouts**: Multiple processes (Root Console, Root Mic, Root Dreamer) competing for GPU access
2. **Inadequate Timeout Handling**: 60-second timeouts too short for model loading
3. **No Status Monitoring**: Difficult to diagnose GPU lock issues
4. **No Emergency Release**: Stuck locks could not be released without restarting services

## Changes Made

### 1. Enhanced GPU Controller (`tools/modules/sovereign.js`)
- Increased default lock timeout from 60s to 120s (2 minutes)
- Added retry logic with better error handling
- Implemented fallback to direct WebGPU access when bridge is unavailable
- Added GPU status checking functionality
- **NEW: Model Loading Serialization**: Added `withModelLoadLock()` to ensure models load sequentially, preventing GPU overload during initial loading

### 2. Improved GPU Bridge (`tools/webgpu_bridge.py`)
- Increased timeout from 60s to 120s for lock acquisition
- Added request tracking to prevent starvation
- Implemented emergency force-release-all endpoint
- Enhanced logging for better debugging

### 3. Updated Components
- **Root Console (`model-server-chat.html`)**: Added 2-minute timeout for model loading, improved error handling, now uses model loading lock, fixed model URL, enhanced bridge connection with proper context manager initialization, **NEW: Decoupled bridge functionality allowing memory queries without loaded LLM model**
- **Root Mic (`root-mic.html`)**: Enhanced GPU lock acquisition with status checking, now uses model loading lock
- **Root Dreamer (`root-dreamer.html`)**: Added retry logic for model loading, now uses model loading lock, uses more reliable model configuration, fixed Datalog query for finding orphan memories

### 4. New Utilities
- **GPU Manager Script** (`scripts/gpu_manager.py`): Command-line tool to monitor and manage GPU resources
- **Test Script** (`scripts/test_gpu_fixes.py`): Comprehensive testing of GPU resource management

## Usage

### Monitoring GPU Status
```bash
python scripts/gpu_manager.py --status
```

### Monitoring Continuously
```bash
python scripts/gpu_manager.py --monitor --interval 10
```

### Force Releasing GPU Locks
```bash
python scripts/gpu_manager.py --force-release
```

### Testing the Fixes
```bash
python scripts/test_gpu_fixes.py
```

## Emergency Procedures

If GPU locks become stuck:

1. **Check Status**: `python scripts/gpu_manager.py --status`
2. **Standard Reset**: `python scripts/gpu_manager.py --reset`
3. **Emergency Release**: `python scripts/gpu_manager.py --force-release`

## Bridge Endpoints

- `GET /v1/gpu/status` - Get current GPU lock status
- `POST /v1/gpu/lock` - Acquire GPU lock (with 2-minute timeout)
- `POST /v1/gpu/unlock` - Release GPU lock
- `POST /v1/gpu/reset` - Standard reset
- `POST /v1/gpu/force-release-all` - Emergency release all locks

## Priority System

The system uses a priority-based queue:
- **Priority 0**: Microphone (voice input) - highest priority
- **Priority 10**: Console (chat) - medium priority
- **Priority 15**: Default
- **Priority 20**: Dreamer (background processing) - lowest priority

## Best Practices

1. Always use the enhanced `GPUController.withLock()` method
2. Implement proper error handling around GPU operations
3. Monitor GPU status when experiencing issues
4. Use appropriate timeouts for different operations:
   - Model loading: 2 minutes (120s)
   - Inference: 1 minute (60s)
   - Status checks: 10 seconds (10s)