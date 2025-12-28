/* tools/modules/sovereign.js */

// Import CozoDB bindings from the parent directory
import initWasm, { CozoDb } from '../cozo_lib_wasm.js';

/**
 * Sovereign Coda Kernel (v2.0)
 * Standard Library for Logging, State, Hardware, and Memory.
 */

// --- 1. THE NERVOUS SYSTEM (Unified Logging) ---
export class SovereignLogger {
    constructor(sourceId) {
        this.source = sourceId;
        this.logChannel = new BroadcastChannel('sovereign-logs');
        this.codaChannel = new BroadcastChannel('coda_logs');
    }

    info(msg) { this._emit(msg, 'info'); }
    warn(msg) { this._emit(msg, 'warn'); }
    error(msg) { this._emit(msg, 'error'); }
    success(msg) { this._emit(msg, 'success'); }

    _emit(msg, type) {
        // 1. Console Fallback
        const style = type === 'error' ? 'color:red' : (type === 'success' ? 'color:green' : 'color:blue');
        console.log(`%c[${this.source}] ${msg}`, style);
        
        // 2. Broadcast to Mission Control
        const timestamp = new Date().toISOString();
        const timeShort = new Date().toLocaleTimeString();
        
        try {
            // New JSON Channel (for Mission Control)
            this.codaChannel.postMessage({
                source: this.source,
                type,
                message: msg,
                timestamp
            });
            // Legacy Channel (for Log Viewer compatibility)
            this.logChannel.postMessage({ 
                source: 'system', 
                msg: `[${this.source}] ${msg}`, 
                type, 
                time: timeShort 
            });
        } catch (e) {
            console.warn('Logger broadcast failed', e);
        }
    }
}

// --- 2. THE STATE MANAGER (Nano Store) ---
// Zero-dependency reactive state.
export function createStore(initialState) {
    const listeners = new Set();
    
    const proxy = new Proxy(initialState, {
        set(target, property, value) {
            target[property] = value;
            listeners.forEach(fn => fn(property, value));
            return true;
        }
    });

    return {
        state: proxy,
        subscribe: (fn) => listeners.add(fn),
        unsubscribe: (fn) => listeners.delete(fn)
    };
}

// --- 3. HARDWARE DETECTOR (The XPS Fix) ---
// Centralized WebGPU configuration to prevent crashes on 256MB cards.
export async function getWebGPUConfig(profile = 'mid') {
    if (!navigator.gpu) {
        throw new Error("WebGPU is not supported by this browser. Ensure you are using a modern browser (Chrome 113+, Edge 113+) and it is not disabled in flags.");
    }
    
    // 1. Request Adapter (Progressive Fallback)
    let adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
    
    if (!adapter) {
        console.warn("[Kernel] High-performance adapter failed. Trying default...");
        adapter = await navigator.gpu.requestAdapter();
    }
    
    if (!adapter) {
        console.warn("[Kernel] Default adapter failed. Trying low-power fallback...");
        adapter = await navigator.gpu.requestAdapter({ powerPreference: 'low-power' });
    }
    
    if (!adapter) {
        throw new Error("No WebGPU Adapter found. This often happens after a GPU crash. Please RESTART YOUR BROWSER or check for driver updates.");
    }

    // 2. Detect Hardware Limits
    const hardwareLimit = adapter.limits.maxStorageBufferBindingSize;
    let requested = 1024 * 1024 * 1024; // Default 1GB

    // 3. Apply Profile Strategy
    if (profile === 'lite') requested = 256 * 1024 * 1024; // 256MB
    else if (profile === 'mid') requested = 1024 * 1024 * 1024; // 1GB
    else if (profile === 'high') requested = 2048 * 1024 * 1024; // 2GB

    // 4. The Safety Clamp
    const finalLimit = Math.min(requested, hardwareLimit);
    const isConstrained = finalLimit < requested;

    return {
        adapter,
        deviceConfig: {
            requiredLimits: { maxStorageBufferBindingSize: finalLimit },
            requiredFeatures: adapter.features.has("shader-f16") ? ["shader-f16"] : []
        },
        maxBufferSize: finalLimit,
        isConstrained
    };
}

// --- 4. MEMORY CORE (CozoDB Helper) ---
export async function initCozo(wasmUrl = '../cozo_lib_wasm_bg.wasm') {
    await initWasm(wasmUrl);
    return CozoDb;
}

// --- 5. THE BLOCKER (GPU Mutex) ---
class GPUController {
    static get BRIDGE_URL() { return 'http://localhost:8080'; }

    // System Consciousness States
    static States = {
        IDLE: 'IDLE',
        DREAMING: 'DREAMING',
        COGNITION: 'COGNITION',
        LISTENING: 'LISTENING'
    };

    static currentState = 'IDLE';
    static stateChannel = new BroadcastChannel('sovereign-state');

    // Separate locks for different operations
    static modelLoadPromise = null;  // Promise to serialize model loading
    static activeModelLoaders = new Set();  // Track active model loaders

    static broadcastState(newState) {
        if (this.currentState === newState) return;
        this.currentState = newState;
        this.stateChannel.postMessage({ type: 'STATE_CHANGE', state: newState });
        console.log(`[GPUController] State changed to: ${newState}`);
    }

    // Enhanced GPU lock with retry logic and better error handling
    static async acquireLock(agentId, timeout = 120000) { // Increased default timeout to 120 seconds
        const startTime = Date.now();

        // 1. Determine Intended State
        let intendedState = this.States.IDLE;
        if (agentId.includes('Dreamer')) intendedState = this.States.DREAMING;
        else if (agentId.includes('Console') || agentId.includes('Chat')) intendedState = this.States.COGNITION;
        else if (agentId.includes('Mic')) intendedState = this.States.LISTENING;

        // 2. SEMAPHORE CHECK (Consciousness Priority)
        const highPriority = [this.States.COGNITION, this.States.LISTENING];
        
        // If Dreamer tries to wake while Brain/Ears are active -> REJECT IMMEDIATELY
        if (intendedState === this.States.DREAMING && highPriority.includes(this.currentState)) {
             return { success: false, error: `Consciousness Semaphore: System is busy (${this.currentState}). Dreamer suppressed.` };
        }

        // If High Priority Agent (Brain/Ears) starts -> Assert Dominance
        if (highPriority.includes(intendedState)) {
            this.broadcastState(intendedState);
        } else if (intendedState === this.States.DREAMING) {
            this.broadcastState(this.States.DREAMING);
        }

        while (Date.now() - startTime < timeout) {
            try {
                // This request will HANG until the lock is available (Queue)
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);

                const res = await fetch(`${this.BRIDGE_URL}/v1/gpu/lock`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer sovereign-secret'
                    },
                    body: JSON.stringify({ id: agentId }),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (res.ok) {
                    const data = await res.json();
                    return { success: true, token: data.token };
                }

                // Handle specific error codes
                if (res.status === 503) {
                    const errorData = await res.json();
                    return { success: false, error: errorData.msg || `Queue Timeout (${res.status})` };
                }

                return { success: false, error: `GPU Lock Failed (${res.status})` };
            } catch (e) {
                if (e.name === 'AbortError') {
                    return { success: false, error: 'Lock acquisition timeout' };
                }

                console.warn("Bridge unreachable (No Lock)", e);

                // If bridge is down, try direct WebGPU access as fallback
                if (e.message.includes('fetch') || e.message.includes('network')) {
                    console.warn("Bridge offline, attempting direct WebGPU access...");
                    return { success: true, token: "direct-webgpu-fallback" };
                }

                return { success: false, error: e.message };
            }

            // Small delay before retry to avoid excessive polling
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        return { success: false, error: `Lock acquisition timeout after ${timeout}ms` };
    }

    static async releaseLock(agentId) {
        try {
            await fetch(`${this.BRIDGE_URL}/v1/gpu/unlock`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sovereign-secret'
                },
                body: JSON.stringify({ id: agentId }),
                keepalive: true // Critical: Ensure request survives tab close
            });
        } catch (e) {
            console.warn("Failed to release lock", e);
            // Don't throw error on release failure to avoid blocking cleanup
        } finally {
             // Reset state to IDLE if a high-priority agent is finishing
             if (agentId.includes('Console') || agentId.includes('Chat') || agentId.includes('Mic')) {
                 this.broadcastState(this.States.IDLE);
             }
        }
    }

    // Enhanced withLock with better error handling and retry logic
    static async withLock(agentId, taskFn, timeout = 120000) {
        const lock = await this.acquireLock(agentId, timeout);
        if (!lock.success) {
            console.error(`GPU lock acquisition failed for ${agentId}: ${lock.error}`);
            throw new Error(`Could not acquire GPU lock: ${lock.error}`);
        }

        let taskResult;
        let taskError;

        try {
            taskResult = await taskFn();
        } catch (e) {
            taskError = e;
        } finally {
            // Always try to release the lock, even if the task fails
            await this.releaseLock(agentId);
        }

        if (taskError) {
            throw taskError;
        }

        return taskResult;
    }

    // NEW: Serialize model loading to prevent multiple models loading simultaneously
    static async withModelLoadLock(agentId, taskFn, timeout = 300000) { // 5-minute timeout for model loading
        // Create a promise chain to serialize model loading at the application level
        // This ensures only one model loading operation happens at a time across all components
        const previousLoad = this.modelLoadPromise;

        // Create a new promise that waits for the previous one to complete
        this.modelLoadPromise = (async () => {
            if (previousLoad) {
                try {
                    await previousLoad;
                } catch (e) {
                    console.warn("Previous model load failed, continuing:", e);
                }
            }

            // Mark this loader as active
            this.activeModelLoaders.add(agentId);

            try {
                console.log(`[${agentId}] Starting sequential model loading (Queue: ${this.activeModelLoaders.size - 1} waiting)`);
                // The task function itself will handle GPU lock acquisition as needed
                const result = await taskFn();
                console.log(`[${agentId}] Sequential model loading completed`);
                return result;
            } finally {
                // Remove from active loaders
                this.activeModelLoaders.delete(agentId);
            }
        })();

        try {
            return await this.modelLoadPromise;
        } catch (error) {
            // Clean up on error
            this.activeModelLoaders.delete(agentId);
            throw error;
        }
    }

    // Get status of model loading queue
    static getModelLoadStatus() {
        return {
            queueSize: this.activeModelLoaders.size,
            activeLoaders: Array.from(this.activeModelLoaders),
            hasPendingLoad: this.modelLoadPromise !== null,
            modelLoadQueueInfo: `Model Load Queue: ${this.activeModelLoaders.size} active, ${this.modelLoadPromise ? 'loading' : 'idle'}`
        };
    }

    // Get mind blanking status
    static getMindBlankingStatus() {
        const isBlanking = Date.now() < this.blankingUntil;
        const remainingTime = Math.max(0, this.blankingUntil - Date.now());
        return {
            isBlanking,
            blankingUntil: new Date(this.blankingUntil).toISOString(),
            remainingMs: remainingTime,
            remainingSeconds: Math.ceil(remainingTime / 1000),
            lastIntensiveTask: this.lastIntensiveTask,
            blankingDuration: this.BLANKING_DURATION
        };
    }

    // New: Check GPU status to help with debugging
    static async checkStatus() {
        try {
            const res = await fetch(`${this.BRIDGE_URL}/v1/gpu/status`, {
                method: 'GET',
                headers: {
                    'Authorization': 'Bearer sovereign-secret'
                }
            });

            if (res.ok) {
                const bridgeStatus = await res.json();
                // Add mind blanking status to the bridge status
                const blankingStatus = this.getMindBlankingStatus();
                return {
                    ...bridgeStatus,
                    mindBlanking: blankingStatus
                };
            }
            return { error: `Status check failed (${res.status})` };
        } catch (e) {
            return { error: e.message };
        }
    }
}

// Ensure explicit export if previous style failed in some browsers
export { GPUController };
