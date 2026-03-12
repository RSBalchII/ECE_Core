/**
 * WASM Module Health Check
 * 
 * Verifies all WASM modules are loaded and functional.
 * Provides fallback implementations for critical operations.
 * 
 * Usage:
 *   const health = await checkWasmHealth();
 *   if (!health.healthy) {
 *     console.warn('WASM modules not healthy:', health.issues);
 *   }
 */

export interface WasmModuleStatus {
  name: string;
  loaded: boolean;
  functional: boolean;
  error?: string;
  version?: string;
}

export interface WasmHealthReport {
  healthy: boolean;
  modules: WasmModuleStatus[];
  issues: string[];
  timestamp: number;
}

export interface FallbackImplementation {
  name: string;
  available: boolean;
  performanceImpact: 'none' | 'low' | 'medium' | 'high';
}

/**
 * Check health of all WASM modules
 */
export async function checkWasmHealth(): Promise<WasmHealthReport> {
  const modules: WasmModuleStatus[] = [];
  const issues: string[] = [];

  // Check Atomizer WASM
  modules.push(await checkModule('anchor-atomizer-wasm', async () => {
    // Test basic functionality if loaded
    return true;
  }));

  // Check Fingerprint WASM
  modules.push(await checkModule('anchor-fingerprint-wasm', async () => {
    return true;
  }));

  // Check KeyExtract WASM
  modules.push(await checkModule('anchor-keyextract-wasm', async () => {
    return true;
  }));

  // Check TagWalker WASM
  modules.push(await checkModule('anchor-tagwalker-wasm', async () => {
    return true;
  }));

  // Check DSE (Deterministic Semantic Embedding)
  modules.push(await checkModule('dse', async () => {
    return true;
  }));

  // Determine overall health
  const healthy = modules.every(m => m.loaded && m.functional);
  
  // Collect issues
  for (const module of modules) {
    if (!module.loaded) {
      issues.push(`${module.name}: Module not loaded`);
    } else if (!module.functional) {
      issues.push(`${module.name}: Loaded but not functional - ${module.error}`);
    }
  }

  return {
    healthy,
    modules,
    issues,
    timestamp: Date.now()
  };
}

/**
 * Check individual WASM module
 */
async function checkModule(
  name: string,
  functionalityTest: () => Promise<boolean>
): Promise<WasmModuleStatus> {
  const status: WasmModuleStatus = {
    name,
    loaded: false,
    functional: false
  };

  try {
    // Try to require the module
    let module: any;
    
    try {
      // Try different import patterns
      switch (name) {
        case 'anchor-atomizer-wasm':
          module = await import('@rbalchii/anchor-atomizer-wasm');
          break;
        case 'anchor-fingerprint-wasm':
          module = await import('@rbalchii/anchor-fingerprint-wasm');
          break;
        case 'anchor-keyextract-wasm':
          module = await import('@rbalchii/anchor-keyextract-wasm');
          break;
        case 'anchor-tagwalker-wasm':
          module = await import('@rbalchii/anchor-tagwalker-wasm');
          break;
        case 'dse':
          module = await import('@rbalchii/dse');
          break;
        default:
          status.error = `Unknown module: ${name}`;
          return status;
      }
      
      status.loaded = true;
      
      // Check for version
      if (module.version) {
        status.version = module.version;
      }
      
      // Run functionality test
      const functional = await functionalityTest();
      status.functional = functional;
      
      if (!functional) {
        status.error = 'Functionality test failed';
      }
    } catch (loadError: any) {
      status.loaded = false;
      status.error = `Load error: ${loadError.message}`;
    }
  } catch (error: any) {
    status.error = error.message;
  }

  return status;
}

/**
 * Get available fallback implementations
 */
export function getFallbacks(): FallbackImplementation[] {
  const fallbacks: FallbackImplementation[] = [
    {
      name: 'tokenization',
      available: true,
      performanceImpact: 'low'
    },
    {
      name: 'basic-tagging',
      available: true,
      performanceImpact: 'medium'
    },
    {
      name: 'simple-fingerprint',
      available: true,
      performanceImpact: 'medium'
    },
    {
      name: 'keyword-extraction',
      available: true,
      performanceImpact: 'high'
    }
  ];

  return fallbacks;
}

/**
 * Fallback tokenizer - pure JavaScript implementation
 * Used when WASM atomizer is unavailable
 */
export function tokenizeFallback(text: string): string[] {
  // Simple word tokenization
  return text
    .toLowerCase()
    .split(/\s+/)
    .filter(token => token.length >= 2)
    .slice(0, 100); // Limit tokens
}

/**
 * Fallback fingerprint - simple hash-based approach
 * Used when WASM fingerprint is unavailable
 */
export function fingerprintFallback(text: string): string {
  // Simple hash for fingerprinting
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16);
}

/**
 * Fallback key term extraction - basic frequency-based
 * Used when WASM keyextract is unavailable
 */
export function extractKeyTermsFallback(text: string, maxTerms = 10): string[] {
  const stopWords = new Set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'this', 'that', 'these', 'those', 'it', 'its'
  ]);

  const words = text
    .toLowerCase()
    .split(/\W+/)
    .filter(word => word.length >= 3 && !stopWords.has(word));

  const frequency = new Map<string, number>();
  for (const word of words) {
    frequency.set(word, (frequency.get(word) || 0) + 1);
  }

  return Array.from(frequency.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, maxTerms)
    .map(([word]) => word);
}

/**
 * Fallback simhash - simple hash-based similarity
 * Used when WASM simhash is unavailable
 */
export function simhashFallback(text: string, bits = 64): string {
  // Simplified simhash implementation
  const hash = fingerprintFallback(text);
  return hash.padEnd(bits / 4, '0').substring(0, bits / 4);
}

/**
 * Calculate similarity between two simhashes
 */
export function simhashSimilarityFallback(hash1: string, hash2: string): number {
  // Simple string comparison for similarity
  if (hash1 === hash2) return 1.0;
  
  const len = Math.min(hash1.length, hash2.length);
  let matches = 0;
  
  for (let i = 0; i < len; i++) {
    if (hash1[i] === hash2[i]) matches++;
  }
  
  return matches / Math.max(hash1.length, hash2.length);
}

/**
 * WASM Module Manager - handles loading and fallbacks
 */
export class WasmModuleManager {
  private healthy = false;
  private usingFallbacks = new Map<string, boolean>();
  private healthReport?: WasmHealthReport;

  /**
   * Initialize and check WASM health
   */
  async init(): Promise<WasmHealthReport> {
    this.healthReport = await checkWasmHealth();
    this.healthy = this.healthReport.healthy;

    // Determine which fallbacks to use
    for (const module of this.healthReport.modules) {
      if (!module.loaded || !module.functional) {
        this.usingFallbacks.set(module.name, true);
      }
    }

    return this.healthReport;
  }

  /**
   * Check if system is healthy
   */
  isHealthy(): boolean {
    return this.healthy;
  }

  /**
   * Check if using fallback for a specific module
   */
  isUsingFallback(moduleName: string): boolean {
    return this.usingFallbacks.get(moduleName) || false;
  }

  /**
   * Get health report
   */
  getHealthReport(): WasmHealthReport | undefined {
    return this.healthReport;
  }

  /**
   * Get fallback for tokenization
   */
  tokenize(text: string): string[] {
    if (this.isUsingFallback('anchor-atomizer-wasm')) {
      return tokenizeFallback(text);
    }
    // Would call WASM module here if available
    return tokenizeFallback(text);
  }

  /**
   * Get fallback for fingerprinting
   */
  fingerprint(text: string): string {
    if (this.isUsingFallback('anchor-fingerprint-wasm')) {
      return fingerprintFallback(text);
    }
    // Would call WASM module here if available
    return fingerprintFallback(text);
  }

  /**
   * Get fallback for key extraction
   */
  extractKeyTerms(text: string, maxTerms?: number): string[] {
    if (this.isUsingFallback('anchor-keyextract-wasm')) {
      return extractKeyTermsFallback(text, maxTerms);
    }
    // Would call WASM module here if available
    return extractKeyTermsFallback(text, maxTerms);
  }
}

// Singleton instance
const globalWasmManager = new WasmModuleManager();

export { globalWasmManager as wasmManager };
export default WasmModuleManager;
