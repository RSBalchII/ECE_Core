import { Worker } from 'worker_threads';
import path from 'path';
import { fileURLToPath } from 'url';
import { MODELS_DIR } from '../../config/paths.js';
import config from '../../config/index.js';

// Global State
let clientWorker: Worker | null = null;
let orchestratorWorker: Worker | null = null;
let currentChatModelName = "";
let currentOrchestratorModelName = "";

// ESM __dirname fix
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper to resolve worker path dynamically based on environment (src vs dist)
function resolveWorkerPath(relativePath: string) {
  const isDev = __dirname.includes('src');
  const ext = isDev ? '.ts' : '.js';
  return path.resolve(__dirname, relativePath + ext);
}

const CHAT_WORKER_PATH = resolveWorkerPath('../../core/inference/ChatWorker');


export interface LoadModelOptions {
  ctxSize?: number;
  batchSize?: number;
  systemPrompt?: string;
  gpuLayers?: number;
}

// Initialize workers based on configuration
export async function initWorker() {
  // TAG-WALKER MODE (Lightweight)
  // We strictly skip embedding workers to save RAM. 
  // All embedding calls return zero-stubs.

  if (!clientWorker) {
    console.log(`[Provider] Tag-Walker Mode Active. Spawning Chat Worker...`);
    // Use Chat Worker for Main Chat (Standardized)
    clientWorker = await spawnWorker("ChatWorker", CHAT_WORKER_PATH, {
      gpuLayers: config.MODELS.MAIN.GPU_LAYERS,
      // Pass forceCpu if needed, but we rely on gpuLayers config
      forceCpu: config.MODELS.MAIN.GPU_LAYERS === 0
    });
  }

  // Spawn Orchestrator (Side Channel) Worker - CPU Optimized
  if (!orchestratorWorker) {
    orchestratorWorker = await spawnWorker("OrchestratorWorker", CHAT_WORKER_PATH, {
      gpuLayers: config.MODELS.ORCHESTRATOR.GPU_LAYERS,
      forceCpu: config.MODELS.ORCHESTRATOR.GPU_LAYERS === 0
    });
  }

  return clientWorker;
}

async function spawnWorker(name: string, workerPath: string, workerData: any = {}): Promise<Worker> {
  return new Promise((resolve, reject) => {
    const w = new Worker(workerPath, { workerData });
    w.on('message', (msg) => {
      if (msg.type === 'ready') resolve(w);
      if (msg.type === 'error') console.error(`[${name}] Error:`, msg.error);
    });
    w.on('error', (err) => {
      console.error(`[${name}] Thread Error:`, err);
      reject(err);
    });
    w.on('exit', (code) => {
      if (code !== 0) console.error(`[${name}] Stopped with exit code ${code}`);
    });
  });
}

// Lock for initAutoLoad
let initPromise: Promise<void> | null = null;

// Auto-loader for Engine Start
export async function initAutoLoad() {
  if (initPromise) return initPromise;

  initPromise = (async () => {
    console.log("[Provider] Auto-loading configured models...");
    console.log(`[Provider] DEBUG: process.env['LLM_GPU_LAYERS'] = "${process.env['LLM_GPU_LAYERS']}"`);
    console.log(`[Provider] DEBUG: process.env['LLM_MODEL_PATH'] = "${process.env['LLM_MODEL_PATH']}"`);
    console.log(`[Provider] DEBUG: config.MODELS.MAIN.GPU_LAYERS = ${config.MODELS.MAIN.GPU_LAYERS}`);
    console.log(`[Provider] DEBUG: config.MODELS.MAIN.PATH = "${config.MODELS.MAIN.PATH}"`);

    try {
      await initWorker();

      // Load Chat Model
      console.log(`[Provider] Loading Main Chat Model: ${config.MODELS.MAIN.PATH}`);
      await loadModel(config.MODELS.MAIN.PATH, {
        ctxSize: config.MODELS.MAIN.CTX_SIZE,
        gpuLayers: config.MODELS.MAIN.GPU_LAYERS
      }, 'chat');

      // Load Orchestrator Model
      console.log(`[Provider] Loading Orchestrator Model: ${config.MODELS.ORCHESTRATOR.PATH}`);
      await loadModel(config.MODELS.ORCHESTRATOR.PATH, {
        ctxSize: config.MODELS.ORCHESTRATOR.CTX_SIZE,
        gpuLayers: config.MODELS.ORCHESTRATOR.GPU_LAYERS
      }, 'orchestrator');

    } catch (e) {
      console.error("[Provider] Auto-load failed:", e);
      // Reset promise on failure to allow retry
      initPromise = null;
      throw e;
    }
  })();

  return initPromise;
}

// Model Loading Logic
let chatLoadingPromise: Promise<any> | null = null;
let orchLoadingPromise: Promise<any> | null = null;

export async function loadModel(modelPath: string, options: LoadModelOptions = {}, target: 'chat' | 'orchestrator' = 'chat') {
  console.log(`[Provider] loadModel called for: ${modelPath} [Target: ${target}]`);

  if (!clientWorker) await initWorker();

  let targetWorker = clientWorker;
  if (target === 'orchestrator') {
    targetWorker = orchestratorWorker;
    if (!targetWorker) console.warn("[Provider] Warning: Orchestrator target requested but OrchestratorWorker is null. Fallback to ClientWorker?");
  }

  if (!targetWorker) throw new Error(`Worker not initialized for target ${target}`);

  // Check if already loaded
  if (target === 'chat' && modelPath === currentChatModelName) return { status: "ready" };
  if (target === 'orchestrator' && modelPath === currentOrchestratorModelName) return { status: "ready" };

  // Prevent parallel loads for *same target*
  if (target === 'chat' && chatLoadingPromise) return chatLoadingPromise;
  if (target === 'orchestrator' && orchLoadingPromise) return orchLoadingPromise;

  const loadTask = new Promise((resolve, reject) => {
    const fullModelPath = path.isAbsolute(modelPath) ? modelPath : path.join(MODELS_DIR, modelPath);

    const handler = (msg: any) => {
      if (msg.type === 'modelLoaded') {
        console.log(`[Provider] ${target} Model loaded successfully: ${modelPath} into ${target === 'chat' ? 'ClientWorker' : 'OrchestratorWorker'}`);
        targetWorker!.off('message', handler);
        if (target === 'chat') {
          currentChatModelName = modelPath;
          chatLoadingPromise = null;
        } else {
          currentOrchestratorModelName = modelPath;
          orchLoadingPromise = null;
        }
        resolve({ status: "success" });
      } else if (msg.type === 'error') {
        targetWorker!.off('message', handler);
        if (target === 'chat') chatLoadingPromise = null;
        else orchLoadingPromise = null;
        console.error(`[Provider] Worker ${target} Error:`, msg.error);
        reject(new Error(msg.error));
      }
    };

    targetWorker!.on('message', handler);
    targetWorker!.postMessage({
      type: 'loadModel',
      data: { modelPath: fullModelPath, options }
    });
  });

  if (target === 'chat') chatLoadingPromise = loadTask;
  else orchLoadingPromise = loadTask;

  return loadTask;
}

// ... Inference ...

export async function runInference(prompt: string, data: any) {
  if (!clientWorker || !currentChatModelName) throw new Error("Chat Model not loaded");
  // Stub implementation
  console.log("runInference called with", prompt.substring(0, 10), data ? "data present" : "no data");
  return null;
}

export async function runStreamingChat(
  prompt: string,
  onToken: (token: string) => void,
  systemInstruction = "You are a helpful assistant.",
  options: any = {}
): Promise<string> {
  // Always use ClientWorker for Main Chat
  const targetWorker = clientWorker;
  const targetModel = currentChatModelName;

  if (!targetWorker || !targetModel) {
    console.log("[Provider] Chat Model not loaded, auto-loading...");
    await initAutoLoad();
    if (!clientWorker || !currentChatModelName) throw new Error("Chat Model failed to load.");
  }

  // Double check worker reference after await
  const worker = clientWorker!;

  console.log(`[Provider] Streaming Chat: Prompting ${currentChatModelName} (${prompt.length} chars)...`);

  return new Promise((resolve, reject) => {
    let fullResponse = "";

    const handler = (msg: any) => {
      if (msg.type === 'token') {
        if (onToken) onToken(msg.token);
        fullResponse += msg.token;
      } else if (msg.type === 'chatResponse') {
        worker.off('message', handler);
        console.log(`[Provider] Chat Complete (${fullResponse.length} chars)`);
        resolve(msg.data || fullResponse);
      } else if (msg.type === 'error') {
        worker.off('message', handler);
        console.error("Chat Error:", msg.error);
        reject(new Error(msg.error));
      }
    };

    worker.on('message', handler);
    worker.postMessage({
      type: 'chat',
      data: { prompt, options: { ...options, systemPrompt: systemInstruction } }
    });
  });
}

export async function runSideChannel(prompt: string, systemInstruction = "You are a helpful assistant.", options: any = {}) {
  // Use Orchestrator Worker if available, falling back to client
  // Robust Worker Selection
  let targetWorker: Worker | null = null;
  let targetModel: string = "";

  if (orchestratorWorker && currentOrchestratorModelName) {
    targetWorker = orchestratorWorker;
    targetModel = currentOrchestratorModelName;
  } else if (clientWorker && currentChatModelName) {
    targetWorker = clientWorker;
    targetModel = currentChatModelName;
  }

  if (!targetWorker || !targetModel) {
    if (initPromise) await initPromise;
    else await initAutoLoad();

    // Retry selection
    if (orchestratorWorker && currentOrchestratorModelName) {
      targetWorker = orchestratorWorker;
      targetModel = currentOrchestratorModelName;
    } else {
      targetWorker = clientWorker;
      targetModel = currentChatModelName;
    }
  }

  if (!targetWorker || !targetModel) throw new Error("Orchestrator/Chat Model failed to load.");

  console.log(`[Provider] SideChannel: Prompting ${targetModel} (${prompt.length} chars)...`);

  return new Promise((resolve, _reject) => {
    const handler = (msg: any) => {
      if (msg.type === 'chatResponse') {
        targetWorker?.off('message', handler);
        console.log(`[Provider] SideChannel: Response received (${msg.data?.length || 0} chars)`);
        resolve(msg.data);
      } else if (msg.type === 'error') {
        targetWorker?.off('message', handler);
        console.error("SideChannel Error:", msg.error);
        resolve(null);
      }
    };
    targetWorker?.on('message', handler);
    targetWorker?.postMessage({
      type: 'chat',
      data: { prompt, options: { ...options, systemPrompt: systemInstruction } }
    });
  });
}

// Embeddings - STUBBED (Tech Debt Removal)
export async function getEmbedding(text: string): Promise<number[] | null> {
  const result = await getEmbeddings([text]);
  return result ? result[0] : null;
}

export async function getEmbeddings(texts: string[]): Promise<number[][] | null> {
  // Return stubbed zero-vectors to satisfy DB schema
  const dim = config.MODELS.EMBEDDING_DIM || 768; // Fallback to 768
  return texts.map(() => new Array(dim).fill(0.1));
}

// Stub for now to match interface compatibility with rest of system
export async function initInference() {
  // This is called by context.ts usually to ensure model loaded
  // ANTI-GRAVITY PATCH: disable this legacy auto-load which picks random models without config
  console.warn("[Provider] initInference called (Legacy). BLOCKED to prevent random model loading.");
  /* 
  const fs = await import('fs');
  if (!fs.existsSync(MODELS_DIR)) return null;
  try {
    const models = fs.readdirSync(MODELS_DIR).filter((f: string) => f.endsWith(".gguf"));
    if (models.length > 0) {
      return await loadModel(models[0]);
    }
  } catch (e) { console.error("Error listing models", e); }
  */
  return null;
  return null;
}

export function getSession() { return null; } // Worker handles session
export function getContext() { return null; }
export function getModel() { return null; }
export function getCurrentModelName() { return currentChatModelName; }
export function getCurrentCtxSize() { return config.MODELS.MAIN.CTX_SIZE; }

// Legacy/Unused exports needed to satisfy imports elsewhere until refactored
export const DEFAULT_GPU_LAYERS = config.MODELS.MAIN.GPU_LAYERS;
export async function listModels(customDir?: string) {
  const fs = await import('fs');
  const targetDir = customDir ? path.resolve(customDir) : MODELS_DIR;
  if (!fs.existsSync(targetDir)) return [];
  return fs.readdirSync(targetDir).filter((f: string) => f.endsWith(".gguf"));
}