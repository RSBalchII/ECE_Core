import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { verifyModel, getDeviceInfo } from './model-verifier';

describe('Model Verifier Service', () => {
    let originalGpu: any;

    beforeEach(() => {
        originalGpu = (navigator as any).gpu;
        vi.clearAllMocks();
    });

    afterEach(() => {
        Object.defineProperty(navigator, 'gpu', {
            value: originalGpu,
            writable: true,
            configurable: true,
        });
    });

    const mockGpu = (adapter: any | null = {}, throwError = false) => {
        Object.defineProperty(navigator, 'gpu', {
            value: {
                requestAdapter: vi.fn().mockImplementation(() => {
                    if (throwError) {
                        return Promise.reject(new Error('GPU request failed'));
                    }
                    return Promise.resolve(adapter);
                }),
            },
            writable: true,
            configurable: true,
        });
    };

    const removeGpu = () => {
        Object.defineProperty(navigator, 'gpu', {
            value: undefined,
            writable: true,
            configurable: true,
        });
    };

    describe('getDeviceInfo', () => {
        it('returns "WebGPU not supported" when navigator.gpu is undefined', async () => {
            removeGpu();
            const info = await getDeviceInfo();
            expect(info).toEqual({
                gpu_name: "WebGPU not supported",
                vram_estimate_MB: 0,
                is_integrated: false
            });
        });

        it('returns "No GPU adapter found" when adapter is null', async () => {
            mockGpu(null);
            const info = await getDeviceInfo();
            expect(info).toEqual({
                gpu_name: "No GPU adapter found",
                vram_estimate_MB: 0,
                is_integrated: false
            });
        });

        it('estimates 2048MB VRAM for integrated GPU', async () => {
            mockGpu({
                info: {
                    device: 'Intel(R) UHD Graphics',
                    architecture: 'integrated',
                }
            });
            const info = await getDeviceInfo();
            expect(info).toEqual({
                gpu_name: 'Intel(R) UHD Graphics',
                vram_estimate_MB: 2048,
                is_integrated: true
            });
        });

        it('estimates 8192MB VRAM for dedicated GPU', async () => {
            mockGpu({
                info: {
                    device: 'NVIDIA GeForce RTX 4090',
                    architecture: 'dedicated',
                }
            });
            const info = await getDeviceInfo();
            expect(info).toEqual({
                gpu_name: 'NVIDIA GeForce RTX 4090',
                vram_estimate_MB: 8192,
                is_integrated: false
            });
        });

        it('handles unknown GPU device name gracefully', async () => {
            mockGpu({
                info: {
                    architecture: 'dedicated',
                }
            });
            const info = await getDeviceInfo();
            expect(info.gpu_name).toBe('Unknown GPU');
        });
    });

    describe('verifyModel', () => {
        const mockModel = {
            model_id: 'test-model',
            model_lib: 'https://example.com/model',
            vram_required_MB: 4096,
        };

        it('returns not compatible when WebGPU is not supported', async () => {
            removeGpu();
            const result = await verifyModel(mockModel);
            expect(result.compatible).toBe(false);
            expect(result.error).toContain('WebGPU not supported');
        });

        it('returns not compatible when requestAdapter fails or returns null', async () => {
            mockGpu(null);
            const result = await verifyModel(mockModel);
            expect(result.compatible).toBe(false);
            expect(result.error).toContain('Failed to get GPU adapter');
        });

        it('returns error when requestAdapter throws', async () => {
            mockGpu(null, true);
            const result = await verifyModel(mockModel);
            expect(result.compatible).toBe(false);
            expect(result.error).toContain('GPU check failed: GPU request failed');
        });

        it('estimates load time under 60 seconds correctly', async () => {
            mockGpu({ info: {} });
            vi.mocked(global.fetch).mockResolvedValueOnce({ ok: true } as any);

            // vram_required_MB = 1024 -> estimatedSizeGB = 0.8 -> estimatedLoadSeconds = (0.8 * 1024) / 50 = 16.384
            const result = await verifyModel({ ...mockModel, vram_required_MB: 1024 });
            expect(result.compatible).toBe(true);
            expect(result.estimated_load_time).toBe('16s');
            expect(result.warnings).toHaveLength(0);
        });

        it('estimates load time over 60 seconds correctly', async () => {
            mockGpu({ info: {} });
            vi.mocked(global.fetch).mockResolvedValueOnce({ ok: true } as any);

            // vram_required_MB = 8192 -> estimatedSizeGB = 6.4 -> estimatedLoadSeconds = (6.4 * 1024) / 50 = 131.072 (2m 11s)
            const result = await verifyModel({ ...mockModel, vram_required_MB: 8192 });
            expect(result.compatible).toBe(true);
            expect(result.estimated_load_time).toBe('2m 11s');
        });

        it('adds warning when VRAM requirement with buffer is high', async () => {
            mockGpu({ info: {} });
            vi.mocked(global.fetch).mockResolvedValueOnce({ ok: true } as any);

            // 8192 * 1.2 = 9830.4 > 8192
            const result = await verifyModel({ ...mockModel, vram_required_MB: 8192 });
            expect(result.warnings).toContain('High VRAM requirement (8192MB). May cause OOM on integrated GPUs.');
        });

        it('adds warning when model library URL is unreachable', async () => {
            mockGpu({ info: {} });
            vi.mocked(global.fetch).mockResolvedValueOnce({ ok: false } as any);

            const result = await verifyModel(mockModel);
            expect(result.warnings).toContain('Model library URL may be unreachable. Load may fail.');
        });

        it('adds warnings when fetch throws an error', async () => {
            mockGpu({ info: {} });
            vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Network error'));

            const result = await verifyModel(mockModel);
            expect(result.warnings.some(w => w.includes('Could not verify model library URL: Error: Network error'))).toBe(true);
            expect(result.warnings).toContain('Model library URL may be unreachable. Load may fail.');
        });

        it('uses default vram if not provided', async () => {
            mockGpu({ info: {} });
            vi.mocked(global.fetch).mockResolvedValueOnce({ ok: true } as any);

            const result = await verifyModel({ model_id: 'test-model', model_lib: 'https://example.com/model' });
            expect(result.vram_required_MB).toBe(4096);
        });
    });
});
