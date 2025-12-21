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
    if (!navigator.gpu) throw new Error("WebGPU not supported");
    
    // 1. Request Adapter (Prefer High Performance)
    const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' }) 
                 || await navigator.gpu.requestAdapter();
    
    if (!adapter) throw new Error("No WebGPU Adapter found.");

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
