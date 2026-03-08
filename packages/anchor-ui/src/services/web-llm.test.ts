import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { WebLLMService } from './web-llm';
import * as webLlmModule from '@mlc-ai/web-llm';

// Mock the web-llm module
vi.mock('@mlc-ai/web-llm', () => {
    return {
        CreateMLCEngine: vi.fn(),
    };
});

// Mock the config module
vi.mock('../config/web-llm-models', () => {
    return {
        webLLMConfig: {
            model_list: [
                { model_id: 'DeepSeek-R1-Distill-Qwen-7B-q4f16_1-MLC' },
                { model_id: 'Llama-3-8B-Instruct-q4f32_1-MLC' }
            ]
        }
    };
});

describe('WebLLMService', () => {
    let service: WebLLMService;
    let mockConsoleLog: any;
    let mockConsoleError: any;

    beforeEach(() => {
        // Reset all mocks before each test
        vi.clearAllMocks();
        service = new WebLLMService();

        // Mute console output during tests to keep output clean
        mockConsoleLog = vi.spyOn(console, 'log').mockImplementation(() => {});
        mockConsoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => {
        mockConsoleLog.mockRestore();
        mockConsoleError.mockRestore();
    });

    it('should initialize with default parameters successfully', async () => {
        // Mock implementation of CreateMLCEngine
        const mockEngine = {
            chat: { completions: { create: vi.fn() } }
        };
        (webLlmModule.CreateMLCEngine as any).mockResolvedValue(mockEngine);

        expect(service.isInitialized()).toBe(false);
        expect(service.isLoadingModel()).toBe(false);

        const initPromise = service.initialize();

        expect(service.isLoadingModel()).toBe(true);

        await initPromise;

        expect(service.isInitialized()).toBe(true);
        expect(service.isLoadingModel()).toBe(false);
        expect(service.getEngine()).toBe(mockEngine);
        expect(service.getInitError()).toBeNull();
    });

    it('should initialize with a specific model ID', async () => {
        const mockEngine = { chat: { completions: { create: vi.fn() } } };
        (webLlmModule.CreateMLCEngine as any).mockResolvedValue(mockEngine);

        await service.initialize('Llama-3-8B-Instruct-q4f32_1-MLC');

        expect(webLlmModule.CreateMLCEngine).toHaveBeenCalledWith(
            'Llama-3-8B-Instruct-q4f32_1-MLC',
            expect.any(Object)
        );
    });

    it('should not initialize again if already initialized', async () => {
        const mockEngine = { chat: { completions: { create: vi.fn() } } };
        (webLlmModule.CreateMLCEngine as any).mockResolvedValue(mockEngine);

        await service.initialize();
        expect(webLlmModule.CreateMLCEngine).toHaveBeenCalledTimes(1);

        // Call again
        await service.initialize();

        // Ensure it doesn't call CreateMLCEngine again
        expect(webLlmModule.CreateMLCEngine).toHaveBeenCalledTimes(1);
    });

    it('should wait for existing initialization if called concurrently', async () => {
        const mockEngine = { chat: { completions: { create: vi.fn() } } };
        let resolveEngine: any;
        const enginePromise = new Promise(resolve => {
            resolveEngine = () => resolve(mockEngine);
        });
        (webLlmModule.CreateMLCEngine as any).mockReturnValue(enginePromise);

        // Start initialization
        const promise1 = service.initialize();

        // We need a short delay so isLoading flag is set
        await new Promise(resolve => setTimeout(resolve, 10));

        // Attempt another initialization
        const promise2 = service.initialize();

        // Ensure CreateMLCEngine is only called once
        expect(webLlmModule.CreateMLCEngine).toHaveBeenCalledTimes(1);

        // Resolve engine initialization
        resolveEngine();

        await Promise.all([promise1, promise2]);

        expect(service.isInitialized()).toBe(true);
    });

    it('should set error state on initialization failure', async () => {
        const error = new Error('Init failed');
        (webLlmModule.CreateMLCEngine as any).mockRejectedValue(error);

        await expect(service.initialize()).rejects.toThrow('Init failed');

        expect(service.isInitialized()).toBe(false);
        expect(service.isLoadingModel()).toBe(false);
        expect(service.getInitError()).toBe(error);
    });

    it('should test progress callback', async () => {
        const mockEngine = { chat: { completions: { create: vi.fn() } } };
        let initProgressCallbackFn: any;

        (webLlmModule.CreateMLCEngine as any).mockImplementation((modelId, options) => {
            initProgressCallbackFn = options.initProgressCallback;
            return Promise.resolve(mockEngine);
        });

        const progressCb = vi.fn();
        service.setProgressCallback(progressCb);

        expect(service.getProgressCallback()).toBe(progressCb);

        await service.initialize();

        // Simulate progress update
        initProgressCallbackFn({ text: 'Loading', progress: 0.5 });

        expect(progressCb).toHaveBeenCalledWith({ text: 'Loading', progress: 0.5 });
    });

    it('should throw an error if generate is called before initialization', async () => {
        await expect(service.generate([], vi.fn())).rejects.toThrow('Engine not initialized');
    });

    it('should generate text successfully and call onUpdate', async () => {
        const mockCompletion = {
            [Symbol.asyncIterator]: vi.fn().mockReturnValue({
                next: vi.fn()
                    .mockResolvedValueOnce({ value: { choices: [{ delta: { content: 'Hello' } }] }, done: false })
                    .mockResolvedValueOnce({ value: { choices: [{ delta: { content: ' world' } }] }, done: false })
                    .mockResolvedValueOnce({ value: { choices: [{ delta: {} }] }, done: false }) // empty chunk
                    .mockResolvedValueOnce({ value: undefined, done: true })
            })
        };

        const mockEngine = {
            chat: {
                completions: {
                    create: vi.fn().mockResolvedValue(mockCompletion)
                }
            }
        };

        (webLlmModule.CreateMLCEngine as any).mockResolvedValue(mockEngine);
        await service.initialize();

        const onUpdate = vi.fn();
        const result = await service.generate([{ role: 'user', content: 'Hi' }], onUpdate);

        expect(result).toBe('Hello world');
        expect(onUpdate).toHaveBeenCalledTimes(2);
        expect(onUpdate).toHaveBeenNthCalledWith(1, 'Hello');
        expect(onUpdate).toHaveBeenNthCalledWith(2, 'Hello world');

        expect(mockEngine.chat.completions.create).toHaveBeenCalledWith({
            messages: [{ role: 'user', content: 'Hi' }],
            stream: true,
        });
    });
});
