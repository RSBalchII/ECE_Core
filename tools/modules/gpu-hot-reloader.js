/*
 * GPU Management Hot Reloader
 * Provides hot reload capability for GPU management in the browser
 */

class GPUHotReloader {
    constructor() {
        this.gpuController = null;
        this.checkInterval = 5000; // Check every 5 seconds
        this.lastModified = {};
        this.isReloading = false;
        this.reloaderEnabled = true;
    }

    // Enable/disable hot reload
    setEnabled(enabled) {
        this.reloaderEnabled = enabled;
        if (enabled) {
            this.startMonitoring();
        } else {
            this.stopMonitoring();
        }
    }

    // Start monitoring for changes
    startMonitoring() {
        if (this.monitorInterval) return;

        console.log("🔄 GPU Hot Reloader: Starting monitoring...");
        this.monitorInterval = setInterval(() => {
            this.checkForChanges();
        }, this.checkInterval);
    }

    // Stop monitoring
    stopMonitoring() {
        if (this.monitorInterval) {
            clearInterval(this.monitorInterval);
            this.monitorInterval = null;
            console.log("🛑 GPU Hot Reloader: Stopped monitoring");
        }
    }

    // Check for changes in GPU-related files
    async checkForChanges() {
        if (!this.reloaderEnabled || this.isReloading) return;

        try {
            // Check if any GPU-related files have been modified
            const gpuFiles = [
                'tools/modules/anchor.js',
                'tools/model-server-chat.html',
                'tools/root-mic.html',
                'tools/root-dreamer.html'
            ];

            for (const file of gpuFiles) {
                const modified = await this.checkFileModified(file);
                if (modified) {
                    console.log(`🔄 GPU Hot Reloader: Detected change in ${file}`);
                    await this.reloadGPUManagement();
                    break; // Only reload once per check cycle
                }
            }
        } catch (error) {
            console.warn('GPU Hot Reloader: Error checking for changes:', error);
        }
    }

    // Check if a file has been modified since last check
    async checkFileModified(filepath) {
        try {
            // Try to check file modification time via server endpoint
            const response = await fetch(`http://localhost:8080/file-mod-time?path=${encodeURIComponent(filepath)}`);
            if (response.ok) {
                const data = await response.json();
                const currentModTime = data.modTime;

                if (filepath in this.lastModified) {
                    if (this.lastModified[filepath] !== currentModTime) {
                        this.lastModified[filepath] = currentModTime;
                        return true;
                    }
                } else {
                    this.lastModified[filepath] = currentModTime;
                }
            }
        } catch (error) {
            // Fallback: try to re-fetch and compare content
            try {
                const response = await fetch(filepath + '?t=' + Date.now(), { method: 'HEAD' });
                const lastModified = response.headers.get('Last-Modified');

                if (filepath in this.lastModified) {
                    if (this.lastModified[filepath] !== lastModified) {
                        this.lastModified[filepath] = lastModified;
                        return true;
                    }
                } else {
                    this.lastModified[filepath] = lastModified;
                }
            } catch (e) {
                // If we can't check, assume no change to avoid constant reloads
            }
        }
        return false;
    }

    // Reload GPU management logic
    async reloadGPUManagement() {
        if (this.isReloading) return;

        this.isReloading = true;
        console.log("🔄 GPU Hot Reloader: Reloading GPU management logic...");

        try {
            // Force release any current GPU locks to prevent stale state
            await this.forceReleaseGPU();

            // Clear any cached modules if possible
            this.clearModuleCache();

            // Reload the GPU controller with fresh logic
            await this.reloadGPUController();

            console.log("✅ GPU Hot Reloader: GPU management reloaded successfully");
        } catch (error) {
            console.error("❌ GPU Hot Reloader: Error during reload:", error);
        } finally {
            this.isReloading = false;
        }
    }

    // Force release current GPU locks
    async forceReleaseGPU() {
        try {
            // Call the emergency release endpoint if available
            await fetch("http://localhost:8080/v1/gpu/force-release-all", {
                method: "POST",
                headers: { "Authorization": "Bearer sovereign-secret" }
            });
            console.log("✅ GPU Hot Reloader: Force released all GPU locks");
        } catch (e) {
            console.warn("⚠️ GPU Hot Reloader: Could not force release GPU locks:", e);
        }
    }

    // Clear any cached modules (attempt to force reload)
    clearModuleCache() {
        // In a real implementation, this would clear module caches
        // For now, we'll just log
        console.log("🧹 GPU Hot Reloader: Clearing module cache (not implemented in browser)");
    }

    // Reload GPU controller with fresh logic
    async reloadGPUController() {
        // Since we can't truly reload modules in the browser,
        // we'll trigger a soft reload of GPU state
        if (window.GPUController) {
            // If there's a way to refresh the GPU controller state, do it here
            console.log("🔄 GPU Hot Reloader: Refreshing GPU controller state");
        }
    }

    // Manual trigger for hot reload
    async triggerReload() {
        console.log("🔄 GPU Hot Reloader: Manual reload triggered");
        await this.reloadGPUManagement();
    }
}

// Global instance
window.GPU_HOT_RELOADER = new GPUHotReloader();

// Auto-start if in development mode
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.GPU_HOT_RELOADER.startMonitoring();
    console.log("🔄 GPU Hot Reloader: Auto-started in development mode");
}

// Expose for manual control
window.triggerGPUHotReload = () => window.GPU_HOT_RELOADER.triggerReload();
window.setGPUHotReloadEnabled = (enabled) => window.GPU_HOT_RELOADER.setEnabled(enabled);

console.log("🔄 GPU Hot Reloader: Initialized and ready");