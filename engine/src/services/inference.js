/**
 * Inference Service - Local LLM Integration
 * 
 * Provides local inference using node-llama-cpp with GGUF models.
 * Implements Context Weaving for intelligent context management.
 */

const fs = require('fs');
const path = require('path');
const { MODELS_DIR } = require('../config/paths');

const DEFAULT_MODEL = 'gemma-3-4b-it.i1-Q4_K_S.gguf';

let llama = null;
let model = null;
let context = null;
let session = null;
let currentModelName = '';
let currentCtxSize = 4096;

/**
 * Get list of available GGUF model files
 */
function listModels() {
    try {
        if (!fs.existsSync(MODELS_DIR)) {
            console.warn(`Models directory not found: ${MODELS_DIR}`);
            return [];
        }
        const models = fs.readdirSync(MODELS_DIR).filter(f => f.endsWith('.gguf'));
        console.log(`[Inference] Found ${models.length} models in ${MODELS_DIR}`);
        return models;
    } catch (e) {
        console.error('Error listing models:', e.message);
        return [];
    }
}

async function getLlamaInstance() {
    if (!llama) {
        const llamaModule = await import('node-llama-cpp');
        llama = await llamaModule.getLlama();
    }
    return llama;
}

async function loadModel(modelName, options = {}) {
    if (modelName === currentModelName && session) {
        console.log(`🧠 Model ${modelName} already loaded.`);
        return { status: 'ready', message: 'Model already loaded' };
    }

    console.log(`🧠 Loading Model: ${modelName} with options:`, options);
    
    const l = await getLlamaInstance();

    // Cleanup old session
    session = null;
    context = null;
    model = null;

    try {
        const modelPath = path.join(MODELS_DIR, modelName);
        if (!fs.existsSync(modelPath)) throw new Error(`Model not found: ${modelName}`);

        model = await l.loadModel({
            modelPath: modelPath
        });

        try {
            context = await model.createContext({
                contextSize: parseInt(options.ctxSize) || 4096,
                batchSize: parseInt(options.batchSize) || 512
            });
        } catch (ctxError) {
            if (ctxError.message.includes("VRAM")) {
                throw new Error(`VRAM Exhausted: Context size ${options.ctxSize} is too large for this model on your hardware. Try reducing Context Size to 4096 or 8192.`);
            }
            throw ctxError;
        }

        const { LlamaChatSession } = await import('node-llama-cpp');
        session = new LlamaChatSession({
            contextSequence: context.getSequence(),
            systemPrompt: options.systemPrompt || "You are a helpful AI assistant connected to the Anchor Context Engine."
        });

        currentModelName = modelName;
        currentCtxSize = parseInt(options.ctxSize) || 4096;
        return { status: 'success', message: `Loaded ${modelName}` };
    } catch (e) {
        console.error("Model Load Error:", e);
        throw e;
    }
}

async function initInference() {
    if (session) return session;
    const models = listModels();
    const modelToLoad = models.includes(DEFAULT_MODEL) ? DEFAULT_MODEL : models[0];
    if (!modelToLoad) throw new Error(`No models found in ${MODELS_DIR}. Please add GGUF files.`);
    await loadModel(modelToLoad);
    return session;
}

async function generateTags(text, existingTags = []) {
    try {
        const s = await initInference();
        
        const prompt = `
Analyze the following text and assign 1-3 generic category tags (buckets).
Existing tags in the system: [${existingTags.join(', ')}].
Prefer using existing tags if they fit, otherwise invent a new generic one.
Return ONLY a JSON list of strings, for example: ["tag1", "tag2"].
Ensure all strings are enclosed in double quotes.

Text:
${text.substring(0, 2000)}

JSON Tags:`;

        const response = await s.prompt(prompt);
        // Extract JSON list from response
        const match = response.match(/\[.*\]/s);
        if (match) {
            let jsonStr = match[0];
            try {
                return JSON.parse(jsonStr);
            } catch (e) {
                // Try to fix unquoted strings like [tag1, tag2] -> ["tag1", "tag2"]
                jsonStr = jsonStr.replace(/\[(.*)\]/, (m, p1) => {
                    return '[' + p1.split(',').map(s => `"${s.trim().replace(/^"|"$/g, '')}"`).join(',') + ']';
                });
                return JSON.parse(jsonStr);
            }
        }
        return ['core'];
    } catch (e) {
        console.error('Inference error:', e);
        return ['core'];
    }
}

/**
 * Raw completion without session management.
 * Used by internal services like Scribe that need direct prompting.
 * 
 * @param {string} text - Raw prompt text
 * @param {Object} options - Generation options
 * @returns {string} - Model response
 */
async function rawCompletion(text, options = {}) {
    try {
        const s = await initInference();
        return await s.prompt(text, {
            temperature: parseFloat(options.temperature) || 0.5,
            maxTokens: parseInt(options.maxTokens) || 500,
        });
    } catch (e) {
        console.error('Raw completion error:', e.message);
        throw new Error(`Raw completion failed: ${e.message}`);
    }
}

/**
 * Chat with Context Weaving
 * 
 * Implements intelligent context management:
 * 1. System Prompt (fixed)
 * 2. Markovian State (from Scribe, if available)
 * 3. User Message
 * 
 * @param {Array} messages - Array of {role, content} objects
 * @param {Object} generationOptions - Temperature, topP, maxTokens, etc.
 * @returns {string} - Model response
 */
async function chat(messages, generationOptions = {}) {
    try {
        const s = await initInference();
        
        // --- Context Weaving ---
        let contextParts = [];
        
        // 1. Markovian State (High Priority)
        try {
            const { getState } = require('./scribe');
            const state = await getState();
            if (state && state.trim()) {
                contextParts.push(`[SESSION STATE]\n${state}\n[/SESSION STATE]`);
            }
        } catch (e) {
            // Scribe not available, continue without state
        }
        
        // 2. User's message
        const lastMsg = messages[messages.length - 1]?.content || '';
        
        // 3. Construct augmented prompt
        let augmentedMsg = lastMsg;
        if (contextParts.length > 0) {
            augmentedMsg = contextParts.join('\n\n') + '\n\n' + lastMsg;
        }
        
        // 4. Generate with error boundary
        const response = await s.prompt(augmentedMsg, {
            temperature: parseFloat(generationOptions.temperature) || 0.7,
            topP: parseFloat(generationOptions.topP) || 0.9,
            topK: parseInt(generationOptions.topK) || 40,
            repeatPenalty: parseFloat(generationOptions.repeatPenalty) || 1.1,
            maxTokens: parseInt(generationOptions.maxTokens) || 1024,
        });
        
        return response;
        
    } catch (e) {
        console.error('Chat inference error:', e.message);
        return `[Inference Error] ${e.message}`;
    }
}

/**
 * Get current model status
 */
function getStatus() {
    return {
        loaded: !!session,
        model: currentModelName || null,
        contextSize: currentCtxSize,
        modelsDir: MODELS_DIR
    };
}

module.exports = {
    listModels,
    loadModel,
    generateTags,
    rawCompletion,
    chat,
    initInference,
    getStatus
};
