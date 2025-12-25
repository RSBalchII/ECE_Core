/*
 * LLM Engine Manager
 * Provides lifecycle management for LLM engine instances with hibernation capabilities
 */

class LLMEngineManager {
    constructor() {
        this.engines = new Map(); // Map of componentId -> engine instance
        this.engineWorkers = new Map(); // Map of componentId -> worker instance
        this.engineConfigs = new Map(); // Map of componentId -> config
        this.engineStates = new Map(); // Map of componentId -> state (loaded, hibernated, etc.)
    }

    // Create a new engine instance for a specific component
    async createEngine(componentId, modelConfig, webllmModule, options = {}) {
        try {
            // Store the config for potential hibernation/resume
            this.engineConfigs.set(componentId, modelConfig);

            // Create a dedicated worker for this component
            const worker = new Worker('./modules/llm-worker.js', { type: 'module' });
            this.engineWorkers.set(componentId, worker);

            // Create the engine using the provided webllm module
            const engine = await this.createWebWorkerMLCEngine(worker, modelConfig.model_id, webllmModule, {
                appConfig: { model_list: [modelConfig] },
                ...options
            });

            // Store the engine
            this.engines.set(componentId, engine);
            this.engineStates.set(componentId, 'loaded');

            return engine;
        } catch (error) {
            console.error(`Failed to create engine for ${componentId}:`, error);
            throw error;
        }
    }

    // Get an existing engine instance
    getEngine(componentId) {
        return this.engines.get(componentId);
    }

    // Check if an engine is loaded
    isLoaded(componentId) {
        return this.engineStates.get(componentId) === 'loaded';
    }

    // Hibernate an engine (save its state and dispose resources)
    async hibernate(componentId) {
        const engine = this.engines.get(componentId);
        if (!engine) return false;

        try {
            // In a real implementation, we would save the engine state here
            // For now, we'll just dispose the engine and mark as hibernated
            if (typeof engine.dispose === 'function') {
                await engine.dispose();
            }

            this.engineStates.set(componentId, 'hibernated');
            return true;
        } catch (error) {
            console.error(`Failed to hibernate engine for ${componentId}:`, error);
            return false;
        }
    }

    // Resume an engine from hibernation
    async resume(componentId) {
        if (this.engineStates.get(componentId) !== 'hibernated') {
            // If not hibernated, try to get existing engine
            return this.getEngine(componentId);
        }

        const config = this.engineConfigs.get(componentId);
        if (!config) {
            throw new Error(`No config found for hibernated engine: ${componentId}`);
        }

        // Recreate the engine
        return await this.createEngine(componentId, config);
    }

    // Dispose an engine completely
    async dispose(componentId) {
        const engine = this.engines.get(componentId);
        const worker = this.engineWorkers.get(componentId);

        try {
            if (engine && typeof engine.dispose === 'function') {
                await engine.dispose();
            }
        } catch (error) {
            console.warn(`Error disposing engine for ${componentId}:`, error);
        }

        try {
            if (worker && typeof worker.terminate === 'function') {
                worker.terminate();
            }
        } catch (error) {
            console.warn(`Error terminating worker for ${componentId}:`, error);
        }

        // Clean up maps
        this.engines.delete(componentId);
        this.engineWorkers.delete(componentId);
        this.engineConfigs.delete(componentId);
        this.engineStates.delete(componentId);

        return true;
    }

    // Get all component IDs
    getComponentIds() {
        return Array.from(this.engines.keys());
    }

    // Create WebWorkerMLCEngine with error handling
    async createWebWorkerMLCEngine(worker, modelId, webllmModule, options) {
        // Use the provided webllm module to create the engine
        if (webllmModule && typeof webllmModule.CreateWebWorkerMLCEngine !== 'undefined') {
            return await webllmModule.CreateWebWorkerMLCEngine(worker, modelId, options);
        } else if (webllmModule && typeof webllmModule.CreateMLCEngine !== 'undefined') {
            // Fallback to CreateMLCEngine if CreateWebWorkerMLCEngine is not available
            return await webllmModule.CreateMLCEngine(modelId, options);
        } else {
            throw new Error('WebLLM module not provided or does not contain required engine creation functions');
        }
    }

    // Save engine state to storage (simplified approach)
    saveStateToStorage() {
        const state = {
            components: Array.from(this.engineStates.entries()),
            configs: Array.from(this.engineConfigs.entries())
        };

        try {
            localStorage.setItem('llm_engine_manager_state', JSON.stringify(state));
            return true;
        } catch (error) {
            console.error('Failed to save engine state:', error);
            return false;
        }
    }

    // Load engine state from storage
    loadStateFromStorage() {
        try {
            const stateStr = localStorage.getItem('llm_engine_manager_state');
            if (!stateStr) return false;

            const state = JSON.parse(stateStr);

            // Restore states and configs
            state.components.forEach(([id, status]) => {
                this.engineStates.set(id, status);
            });

            state.configs.forEach(([id, config]) => {
                this.engineConfigs.set(id, config);
            });

            return true;
        } catch (error) {
            console.error('Failed to load engine state:', error);
            return false;
        }
    }
}

// Export the class for module usage
export { LLMEngineManager };

// Also make it available globally for backward compatibility
if (typeof window !== 'undefined') {
    window.LLMEngineManager = LLMEngineManager;
    console.log('🔄 LLM Engine Manager: Module loaded');
}