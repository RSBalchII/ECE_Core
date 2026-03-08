import { describe, it, expect, beforeEach, vi } from 'vitest';
import { WebLLMService } from './web-llm';
import { CreateMLCEngine } from '@mlc-ai/web-llm';

vi.mock('@mlc-ai/web-llm', () => ({
    CreateMLCEngine: vi.fn(),
}));

vi.mock('../config/web-llm-models', () => ({
    webLLMConfig: {
        modelBasePath: 'https://huggingface.co/',
        model_list: [
            { model_id: 'DeepSeek-R1-Distill-Qwen-7B-q4f16_1-MLC', model_lib: 'some-lib' },
            { model_id: 'custom-model', model_lib: 'custom-lib' }
        ]
    }
}));

describe('WebLLMService', () => {
    let service: WebLLMService;
    let mockEngine: any;

    beforeEach(() => {
        vi.clearAllMocks();
        service = new WebLLMService();
        mockEngine = {
            chat: {
                completions: {
                    create: vi.fn()
                }
            }
        };
        (CreateMLCEngine as any).mockResolvedValue(mockEngine);
    });

    it('should be created in uninitialized state', () => {
        expect(service.isInitialized()).toBe(false);
        expect(service.isLoadingModel()).toBe(false);
        expect(service.getInitError()).toBeNull();
        expect(service.getEngine()).toBeNull();
    });

    describe('Progress callback', () => {
        it('should allow setting and getting progress callback', () => {
            const callback = vi.fn();
            service.setProgressCallback(callback);
            expect(service.getProgressCallback()).toBe(callback);

            // Should be callable
            service.getProgressCallback()({ text: 'test', progress: 0.5 });
            expect(callback).toHaveBeenCalledWith({ text: 'test', progress: 0.5 });
        });
    });

    describe('initialize', () => {
        it('should initialize successfully with default model', async () => {
            await service.initialize();

            expect(CreateMLCEngine).toHaveBeenCalledWith(
                'DeepSeek-R1-Distill-Qwen-7B-q4f16_1-MLC',
                expect.any(Object)
            );
            expect(service.isInitialized()).toBe(true);
            expect(service.isLoadingModel()).toBe(false);
            expect(service.getEngine()).toBe(mockEngine);
        });

        it('should initialize successfully with custom model', async () => {
            await service.initialize('custom-model');

            expect(CreateMLCEngine).toHaveBeenCalledWith(
                'custom-model',
                expect.any(Object)
            );
            expect(service.isInitialized()).toBe(true);
        });

        it('should skip initialization if already initialized', async () => {
            await service.initialize();
            (CreateMLCEngine as any).mockClear();

            await service.initialize();
            expect(CreateMLCEngine).not.toHaveBeenCalled();
        });

        it('should wait if already loading', async () => {
            let resolveEngine: any;
            (CreateMLCEngine as any).mockImplementation(() => {
                return new Promise(resolve => {
                    resolveEngine = resolve;
                });
            });

            // Start first init
            const init1 = service.initialize();
            expect(service.isLoadingModel()).toBe(true);

            // Start second init
            const init2 = service.initialize();

            // Resolve engine
            resolveEngine(mockEngine);

            await Promise.all([init1, init2]);
            expect(CreateMLCEngine).toHaveBeenCalledTimes(1);
        });

        it('should throw and set initError on initialization failure', async () => {
            const error = new Error('Init failed');
            (CreateMLCEngine as any).mockRejectedValue(error);

            await expect(service.initialize()).rejects.toThrow('Init failed');
            expect(service.isInitialized()).toBe(false);
            expect(service.isLoadingModel()).toBe(false);
            expect(service.getInitError()).toBe(error);
        });

        it('should trigger progress callback during initialization', async () => {
            const callback = vi.fn();
            service.setProgressCallback(callback);

            (CreateMLCEngine as any).mockImplementation((_modelId: string, options: any) => {
                options.initProgressCallback({ text: 'Loading...', progress: 0.1 });
                return Promise.resolve(mockEngine);
            });

            await service.initialize();
            expect(callback).toHaveBeenCalledWith({ text: 'Loading...', progress: 0.1 });
        });
    });

    describe('generate', () => {
        it('should throw if engine is not initialized', async () => {
            await expect(service.generate([{ role: 'user', content: 'hello' }], vi.fn()))
                .rejects.toThrow('Engine not initialized');
        });

        it('should generate text and call onUpdate stream', async () => {
            await service.initialize();

            // Mock async iterable for stream
            const mockStream = {
                async *[Symbol.asyncIterator]() {
                    yield { choices: [{ delta: { content: 'Hello' } }] };
                    yield { choices: [{ delta: { content: ' world' } }] };
                    yield { choices: [{ delta: { content: '!' } }] };
                }
            };

            mockEngine.chat.completions.create.mockResolvedValue(mockStream);

            const onUpdate = vi.fn();
            const messages = [{ role: 'user', content: 'Say hello' }];
            const result = await service.generate(messages, onUpdate);

            expect(mockEngine.chat.completions.create).toHaveBeenCalledWith({
                messages,
                stream: true,
            });

            expect(onUpdate).toHaveBeenCalledTimes(3);
            expect(onUpdate).toHaveBeenNthCalledWith(1, 'Hello');
            expect(onUpdate).toHaveBeenNthCalledWith(2, 'Hello world');
            expect(onUpdate).toHaveBeenNthCalledWith(3, 'Hello world!');

            expect(result).toBe('Hello world!');
        });
    });
});
