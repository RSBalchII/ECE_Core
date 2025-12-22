import { WebWorkerMLCEngineHandler, MLCEngine } from "https://esm.run/@mlc-ai/web-llm";

// The handler bridges messages between the Main Thread and the Engine
const engine = new MLCEngine();
const handler = new WebWorkerMLCEngineHandler(engine);

self.onmessage = (msg) => {
    handler.onmessage(msg);
};