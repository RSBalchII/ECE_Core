
import { ResourceManager } from '../../src/utils/resource-manager.js';
import type { SystemResources } from '../../src/utils/resource-manager.js';
import * as v8 from 'v8';
import assert from 'assert';

// Mock implementation of SystemResources
class MockSystemResources implements SystemResources {
    private totalMemory: number = 1000 * 1024 * 1024; // 1000 MB
    // Use 'any' to avoid type import issues with ts-node
    private memoryUsageStats: any = {
        rss: 200 * 1024 * 1024,
        heapTotal: 100 * 1024 * 1024,
        heapUsed: 50 * 1024 * 1024,
        external: 0,
        arrayBuffers: 0
    };
    private heapStats: any = {
        total_heap_size: 100 * 1024 * 1024,
        total_heap_size_executable: 10 * 1024 * 1024,
        total_physical_size: 100 * 1024 * 1024,
        total_available_size: 50 * 1024 * 1024,
        used_heap_size: 50 * 1024 * 1024,
        heap_size_limit: 500 * 1024 * 1024, // 500 MB Limit
        malloced_memory: 0,
        peak_malloced_memory: 0,
        does_zap_garbage: 0,
        number_of_native_contexts: 0,
        number_of_detached_contexts: 0
    };
    private heapSpaces: any[] = [];
    private gcCalled: boolean = false;
    private hasGcSupport: boolean = true;

    // Control methods for testing
    setTotalMemory(bytes: number) { this.totalMemory = bytes; }
    setMemoryUsage(stats: any) { this.memoryUsageStats = stats; }
    setHeapStatistics(stats: any) { this.heapStats = stats; }
    setHeapSpaceStatistics(stats: any[]) { this.heapSpaces = stats; }
    setHasGc(hasGc: boolean) { this.hasGcSupport = hasGc; }
    wasGcCalled(): boolean { return this.gcCalled; }
    resetGcCall() { this.gcCalled = false; }

    // Interface implementation
    getTotalMemory(): number { return this.totalMemory; }
    getMemoryUsage(): NodeJS.MemoryUsage { return this.memoryUsageStats; }
    getHeapStatistics(): v8.HeapInfo { return this.heapStats; }
    getHeapSpaceStatistics(): v8.HeapSpaceInfo[] { return this.heapSpaces; }
    gc(): void { this.gcCalled = true; }
    hasGc(): boolean { return this.hasGcSupport; }
}

// Test runner helper
async function test(name: string, fn: () => Promise<void> | void) {
    try {
        process.stdout.write(`  ${name}... `);
        await fn();
        console.log('✅ PASS');
    } catch (e: any) {
        console.log('❌ FAIL');
        console.error(`     └─ ${e.message}`);
        process.exitCode = 1;
    }
}

async function runTests() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║     RESOURCE MANAGER TESTS             ║');
    console.log('╚════════════════════════════════════════╝\n');

    await test('Initialization sets limits correctly', () => {
        const mock = new MockSystemResources();
        mock.setTotalMemory(1000 * 1024 * 1024); // 1000 MB

        ResourceManager.resetInstance();
        const rm = ResourceManager.createInstanceForTesting(mock);
        const limits = rm.getResourceLimits();

        // Max heap size should be 60% of total memory
        assert.strictEqual(limits.maxHeapSize, 600 * 1024 * 1024);
        assert.strictEqual(limits.memoryThreshold, 0.7);
        assert.strictEqual(limits.gcThreshold, 0.75);
    });

    await test('Memory Stats reporting', () => {
        const mock = new MockSystemResources();
        const heapUsed = 300 * 1024 * 1024; // 300 MB
        const heapLimit = 500 * 1024 * 1024; // 500 MB

        mock.setMemoryUsage({
            rss: 600 * 1024 * 1024,
            heapTotal: 400 * 1024 * 1024,
            heapUsed: heapUsed,
            external: 0,
            arrayBuffers: 0
        });
        mock.setHeapStatistics({
            ...mock.getHeapStatistics(),
            heap_size_limit: heapLimit
        });

        const rm = ResourceManager.createInstanceForTesting(mock);
        const stats = rm.getMemoryStats();

        assert.strictEqual(stats.heapUsed, heapUsed);
        // Percentage used is relative to heap limit
        const expectedPercentage = (heapUsed / heapLimit) * 100;
        assert.strictEqual(stats.percentageUsed, expectedPercentage);
    });

    await test('Critical Memory Detection', () => {
        const mock = new MockSystemResources();
        const rm = ResourceManager.createInstanceForTesting(mock);
        const heapLimit = 1000;

        mock.setHeapStatistics({ ...mock.getHeapStatistics(), heap_size_limit: heapLimit });

        // Case 1: Below threshold
        mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.5 }); // 50%
        assert.strictEqual(rm.isMemoryCritical(), false, 'Should not be critical at 50%');

        // Case 2: Above threshold (0.75)
        mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.8 }); // 80%
        assert.strictEqual(rm.isMemoryCritical(), true, 'Should be critical at 80%');
    });

    await test('Optimization Trigger', () => {
        const mock = new MockSystemResources();
        const rm = ResourceManager.createInstanceForTesting(mock);
        const heapLimit = 1000;

        mock.setHeapStatistics({ ...mock.getHeapStatistics(), heap_size_limit: heapLimit });

        // Case 1: Below threshold (0.7)
        mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.6 }); // 60%
        assert.strictEqual(rm.needsOptimization(), false, 'Should not need optimization at 60%');

        // Case 2: Above threshold
        mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.71 }); // 71%
        assert.strictEqual(rm.needsOptimization(), true, 'Should need optimization at 71%');
    });

    await test('Garbage Collection Logic', () => {
        const mock = new MockSystemResources();

        const rm = ResourceManager.createInstanceForTesting(mock);
        const heapLimit = 1000;

        mock.setHeapStatistics({ ...mock.getHeapStatistics(), heap_size_limit: heapLimit });

        // Case 1: No GC needed (low memory)
        mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.5 });
        rm.performGCIfNeeded();
        assert.strictEqual(mock.wasGcCalled(), false, 'GC should not be called when memory is low');

        // Case 2: GC needed (high memory)
        mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.8 });
        rm.performGCIfNeeded();
        assert.strictEqual(mock.wasGcCalled(), true, 'GC should be called when memory is high');

        // Case 3: Cooldown prevents subsequent GC
        mock.resetGcCall();
        rm.performGCIfNeeded(); // Should be blocked by cooldown (default 30s)
        assert.strictEqual(mock.wasGcCalled(), false, 'GC should be blocked by cooldown');
    });

    await test('GC unavailability handled', () => {
        const mock = new MockSystemResources();
        mock.setHasGc(false);
        const rm = ResourceManager.createInstanceForTesting(mock);

        // Suppress console.warn for this test
        const originalWarn = console.warn;
        console.warn = () => {};

        try {
            rm.performGarbageCollection();
            assert.strictEqual(mock.wasGcCalled(), false, 'GC should not be called if not available');
        } finally {
            console.warn = originalWarn;
        }
    });

    await test('updateLimits and getResourceLimits behavior', () => {
        const mock = new MockSystemResources();
        ResourceManager.resetInstance();
        const rm = ResourceManager.createInstanceForTesting(mock);

        const initialLimits = rm.getResourceLimits();

        rm.updateLimits({
            gcThreshold: 0.9,
            memoryThreshold: 0.8
        });

        const updatedLimits = rm.getResourceLimits();

        // Assert only these were updated
        assert.strictEqual(updatedLimits.gcThreshold, 0.9);
        assert.strictEqual(updatedLimits.memoryThreshold, 0.8);

        // Assert others remained the same
        assert.strictEqual(updatedLimits.maxHeapSize, initialLimits.maxHeapSize);
        assert.strictEqual(updatedLimits.maxAtomsInMemory, initialLimits.maxAtomsInMemory);
    });

    await test('startMonitoring and stopMonitoring trigger correctly based on memory usage', () => {
        const mock = new MockSystemResources();
        ResourceManager.resetInstance();
        const rm = ResourceManager.createInstanceForTesting(mock);

        const heapLimit = 1000;
        mock.setHeapStatistics({ ...mock.getHeapStatistics(), heap_size_limit: heapLimit });

        let setIntervalCalled = false;
        let clearIntervalCalled = false;
        let intervalCallback: (() => void) | null = null;

        // Mock global interval functions
        const originalSetInterval = global.setInterval;
        const originalClearInterval = global.clearInterval;
        const originalConsoleLog = console.log;

        try {
            // @ts-ignore
            global.setInterval = (cb: () => void, ms: number) => {
                setIntervalCalled = true;
                intervalCallback = cb;
                return 123 as any;
            };

            // @ts-ignore
            global.clearInterval = (id: any) => {
                clearIntervalCalled = true;
            };

            // Suppress logs during test
            console.log = () => {};

            rm.startMonitoring(1000);
            assert.strictEqual(setIntervalCalled, true, 'setInterval should have been called');
            assert.ok(intervalCallback !== null, 'interval callback should have been registered');

            // Test Case 1: Memory critical (> gcThreshold)
            mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.8 }); // 80% > 75%
            // Reset GC status and make sure it has not been called in cooldown
            mock.resetGcCall();
            // Force past cooldown manually by resetting the lastGCTime via re-instantiating, or just bypass cooldown issue:
            // Since we test the method triggering it, we can spy on performGCIfNeeded. Instead of spying, we can just look at mock gc called
            // First we need to make sure the cooldown has passed.
            // A simpler way: just check if needsOptimization is true

            // Re-create to clear the private lastGCTime
            ResourceManager.resetInstance();
            const rm2 = ResourceManager.createInstanceForTesting(mock);
            rm2.startMonitoring(1000);

            mock.resetGcCall();
            if (intervalCallback) (intervalCallback as () => void)(); // Execute the interval
            assert.strictEqual(mock.wasGcCalled(), true, 'GC should be triggered when memory is critical');

            // Test Case 2: Memory high but not critical (> memoryThreshold)
            ResourceManager.resetInstance();
            const rm3 = ResourceManager.createInstanceForTesting(mock);
            mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.72 }); // 72% > 70% but < 75%
            rm3.startMonitoring(1000);

            // For optimizeMemory, it calls performGCIfNeeded but also clearInternalCaches.
            // In our Mock, calling optimizeMemory might call GC if cooldown allows.
            // We just verify it doesn't crash and completes optimization log logic
            mock.resetGcCall();
            if (intervalCallback) (intervalCallback as () => void)();
            assert.strictEqual(mock.wasGcCalled(), true, 'GC is triggered as part of optimization if cooldown allows');

            // Test Case 3: Memory normal (< memoryThreshold)
            ResourceManager.resetInstance();
            const rm4 = ResourceManager.createInstanceForTesting(mock);
            mock.setMemoryUsage({ ...mock.getMemoryUsage(), heapUsed: heapLimit * 0.5 }); // 50% < 70%
            rm4.startMonitoring(1000);

            mock.resetGcCall();
            if (intervalCallback) (intervalCallback as () => void)();
            assert.strictEqual(mock.wasGcCalled(), false, 'GC should NOT be triggered when memory is normal');

            // Test stopMonitoring
            rm4.stopMonitoring();
            assert.strictEqual(clearIntervalCalled, true, 'clearInterval should have been called');

            // Test startMonitoring clears existing interval
            clearIntervalCalled = false;
            rm4.startMonitoring(1000); // Sets interval
            rm4.startMonitoring(1000); // Should clear previous interval
            assert.strictEqual(clearIntervalCalled, true, 'clearInterval should be called if starting when already monitoring');
            rm4.stopMonitoring();

        } finally {
            global.setInterval = originalSetInterval;
            global.clearInterval = originalClearInterval;
            console.log = originalConsoleLog;
        }
    });

    console.log('\nTest suite completed.');
}

runTests().then(() => {
    process.exit(0);
}).catch(e => {
    console.error('Test suite failed:', e);
    process.exit(1);
});
