/**
 * Prometheus Metrics Export
 * 
 * Provides Prometheus-compatible metrics for monitoring Anchor Engine.
 * Exposes metrics via /metrics endpoint for scraping.
 * 
 * Standards: Observability best practices
 * 
 * Usage:
 *   import { metrics, register } from './metrics.js';
 *   metrics.searchDuration.observe(durationMs);
 *   
 *   // Express route:
 *   app.get('/metrics', async (req, res) => {
 *     res.setHeader('Content-Type', register.contentType);
 *     res.end(await register.metrics());
 *   });
 */

export interface MetricLabels {
  [key: string]: string | number;
}

export interface MetricOptions {
  name: string;
  help: string;
  labelNames?: string[];
  buckets?: number[]; // For histograms
}

class MetricRegistry {
  private counters = new Map<string, Counter>();
  private gauges = new Map<string, Gauge>();
  private histograms = new Map<string, Histogram>();
  private summaries = new Map<string, Summary>();

  /**
   * Create or get a counter metric
   */
  counter(options: MetricOptions): Counter {
    if (this.counters.has(options.name)) {
      return this.counters.get(options.name)!;
    }
    const counter = new Counter(options);
    this.counters.set(options.name, counter);
    return counter;
  }

  /**
   * Create or get a gauge metric
   */
  gauge(options: MetricOptions): Gauge {
    if (this.gauges.has(options.name)) {
      return this.gauges.get(options.name)!;
    }
    const gauge = new Gauge(options);
    this.gauges.set(options.name, gauge);
    return gauge;
  }

  /**
   * Create or get a histogram metric
   */
  histogram(options: MetricOptions & { buckets?: number[] }): Histogram {
    if (this.histograms.has(options.name)) {
      return this.histograms.get(options.name)!;
    }
    const histogram = new Histogram(options);
    this.histograms.set(options.name, histogram);
    return histogram;
  }

  /**
   * Create or get a summary metric
   */
  summary(options: MetricOptions): Summary {
    if (this.summaries.has(options.name)) {
      return this.summaries.get(options.name)!;
    }
    const summary = new Summary(options);
    this.summaries.set(options.name, summary);
    return summary;
  }

  /**
   * Get all metrics in Prometheus format
   */
  async metrics(): Promise<string> {
    const lines: string[] = [];

    for (const counter of this.counters.values()) {
      lines.push(counter.toString());
    }
    for (const gauge of this.gauges.values()) {
      lines.push(gauge.toString());
    }
    for (const histogram of this.histograms.values()) {
      lines.push(histogram.toString());
    }
    for (const summary of this.summaries.values()) {
      lines.push(summary.toString());
    }

    return lines.join('\n');
  }

  /**
   * Clear all metrics
   */
  clear(): void {
    this.counters.clear();
    this.gauges.clear();
    this.histograms.clear();
    this.summaries.clear();
  }

  /**
   * Get metric count
   */
  get size(): number {
    return this.counters.size + this.gauges.size + this.histograms.size + this.summaries.size;
  }
}

/**
 * Counter metric - only increases
 */
class Counter {
  private values = new Map<string, number>();
  private help: string;
  private labelNames: string[];

  constructor(private options: MetricOptions) {
    this.help = options.help;
    this.labelNames = options.labelNames || [];
  }

  inc(labels?: MetricLabels): void;
  inc(value: number, labels?: MetricLabels): void;
  inc(valueOrLabels?: number | MetricLabels, labels?: MetricLabels): void {
    let value = 1;
    let labelValues: MetricLabels = {};

    if (typeof valueOrLabels === 'number') {
      value = valueOrLabels;
      labelValues = labels || {};
    } else {
      labelValues = valueOrLabels || {};
    }

    const key = this.labelKey(labelValues);
    const current = this.values.get(key) || 0;
    this.values.set(key, current + value);
  }

  private labelKey(labels: MetricLabels): string {
    if (this.labelNames.length === 0) return '';
    return this.labelNames.map(name => `${name}=${labels[name] ?? ''}`).join(',');
  }

  toString(): string {
    const lines: string[] = [];
    
    lines.push(`# HELP ${this.options.name} ${this.help}`);
    lines.push(`# TYPE ${this.options.name} counter`);

    if (this.values.size === 0) {
      lines.push(`${this.options.name} 0`);
    } else {
      for (const [key, value] of this.values.entries()) {
        if (key) {
          const labelStr = `{${key}}`;
          lines.push(`${this.options.name}${labelStr} ${value}`);
        } else {
          lines.push(`${this.options.name} ${value}`);
        }
      }
    }

    return lines.join('\n');
  }
}

/**
 * Gauge metric - can increase or decrease
 */
class Gauge {
  private values = new Map<string, number>();
  private help: string;
  private labelNames: string[];

  constructor(private options: MetricOptions) {
    this.help = options.help;
    this.labelNames = options.labelNames || [];
  }

  set(value: number, labels?: MetricLabels): void {
    const key = this.labelKey(labels || {});
    this.values.set(key, value);
  }

  inc(labels?: MetricLabels): void;
  inc(value: number, labels?: MetricLabels): void;
  inc(valueOrLabels?: number | MetricLabels, labels?: MetricLabels): void {
    let value = 1;
    let labelValues: MetricLabels = {};

    if (typeof valueOrLabels === 'number') {
      value = valueOrLabels;
      labelValues = labels || {};
    } else {
      labelValues = valueOrLabels || {};
    }

    const key = this.labelKey(labelValues);
    const current = this.values.get(key) || 0;
    this.values.set(key, current + value);
  }

  dec(labels?: MetricLabels): void;
  dec(value: number, labels?: MetricLabels): void;
  dec(valueOrLabels?: number | MetricLabels, labels?: MetricLabels): void {
    let value = 1;
    let labelValues: MetricLabels = {};

    if (typeof valueOrLabels === 'number') {
      value = valueOrLabels;
      labelValues = labels || {};
    } else {
      labelValues = valueOrLabels || {};
    }

    const key = this.labelKey(labelValues);
    const current = this.values.get(key) || 0;
    this.values.set(key, current - value);
  }

  private labelKey(labels: MetricLabels): string {
    if (this.labelNames.length === 0) return '';
    return this.labelNames.map(name => `${name}=${labels[name] ?? ''}`).join(',');
  }

  toString(): string {
    const lines: string[] = [];
    
    lines.push(`# HELP ${this.options.name} ${this.help}`);
    lines.push(`# TYPE ${this.options.name} gauge`);

    if (this.values.size === 0) {
      lines.push(`${this.options.name} 0`);
    } else {
      for (const [key, value] of this.values.entries()) {
        if (key) {
          const labelStr = `{${key}}`;
          lines.push(`${this.options.name}${labelStr} ${value}`);
        } else {
          lines.push(`${this.options.name} ${value}`);
        }
      }
    }

    return lines.join('\n');
  }
}

/**
 * Histogram metric - tracks distribution
 */
class Histogram {
  private buckets: number[];
  private bucketValues = new Map<string, Map<number, number>>();
  private sums = new Map<string, number>();
  private counts = new Map<string, number>();
  private help: string;
  private labelNames: string[];

  constructor(private options: MetricOptions & { buckets?: number[] }) {
    this.help = options.help;
    this.labelNames = options.labelNames || [];
    this.buckets = options.buckets || [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];
  }

  observe(value: number, labels?: MetricLabels): void {
    const key = this.labelKey(labels || {});

    // Initialize bucket map if needed
    if (!this.bucketValues.has(key)) {
      this.bucketValues.set(key, new Map());
    }
    const bucketMap = this.bucketValues.get(key)!;

    // Increment all buckets that are >= value
    for (const bucket of this.buckets) {
      const current = bucketMap.get(bucket) || 0;
      if (value <= bucket) {
        bucketMap.set(bucket, current + 1);
      }
    }

    // Update sum and count
    this.sums.set(key, (this.sums.get(key) || 0) + value);
    this.counts.set(key, (this.counts.get(key) || 0) + 1);
  }

  private labelKey(labels: MetricLabels): string {
    if (this.labelNames.length === 0) return '';
    return this.labelNames.map(name => `${name}=${labels[name] ?? ''}`).join(',');
  }

  toString(): string {
    const lines: string[] = [];
    
    lines.push(`# HELP ${this.options.name} ${this.help}`);
    lines.push(`# TYPE ${this.options.name} histogram`);

    const keys = Array.from(this.bucketValues.keys());
    
    if (keys.length === 0) {
      // No observations
      lines.push(`${this.options.name}_count 0`);
      lines.push(`${this.options.name}_sum 0`);
      for (const bucket of this.buckets) {
        lines.push(`${this.options.name}_bucket{le="${bucket}"} 0`);
      }
      lines.push(`${this.options.name}_bucket{le="+Inf"} 0`);
    } else {
      for (const key of keys) {
        const bucketMap = this.bucketValues.get(key)!;
        const labelPrefix = key ? `{${key}}` : '';
        
        for (const bucket of this.buckets) {
          const count = bucketMap.get(bucket) || 0;
          const bucketLabel = key ? `{${key},le="${bucket}"}` : `{le="${bucket}"}`;
          lines.push(`${this.options.name}_bucket${bucketLabel} ${count}`);
        }
        
        // +Inf bucket
        const totalCount = this.counts.get(key) || 0;
        const infLabel = key ? `{${key},le="+Inf"}` : `{le="+Inf"}`;
        lines.push(`${this.options.name}_bucket${infLabel} ${totalCount}`);
        
        // Sum and count
        lines.push(`${this.options.name}_sum${labelPrefix} ${this.sums.get(key) || 0}`);
        lines.push(`${this.options.name}_count${labelPrefix} ${totalCount}`);
      }
    }

    return lines.join('\n');
  }
}

/**
 * Summary metric - tracks quantiles
 */
class Summary {
  private values = new Map<string, number[]>();
  private sums = new Map<string, number>();
  private counts = new Map<string, number>();
  private help: string;
  private labelNames: string[];

  constructor(private options: MetricOptions) {
    this.help = options.help;
    this.labelNames = options.labelNames || [];
  }

  observe(value: number, labels?: MetricLabels): void {
    const key = this.labelKey(labels || {});

    if (!this.values.has(key)) {
      this.values.set(key, []);
    }
    const arr = this.values.get(key)!;
    arr.push(value);

    // Keep last 1000 values for memory efficiency
    if (arr.length > 1000) {
      arr.shift();
    }

    this.sums.set(key, (this.sums.get(key) || 0) + value);
    this.counts.set(key, (this.counts.get(key) || 0) + 1);
  }

  private labelKey(labels: MetricLabels): string {
    if (this.labelNames.length === 0) return '';
    return this.labelNames.map(name => `${name}=${labels[name] ?? ''}`).join(',');
  }

  toString(): string {
    const lines: string[] = [];
    
    lines.push(`# HELP ${this.options.name} ${this.help}`);
    lines.push(`# TYPE ${this.options.name} summary`);

    const keys = Array.from(this.values.keys());
    
    for (const key of keys) {
      const arr = this.values.get(key)!;
      const labelPrefix = key ? `{${key}}` : '';
      
      // Calculate quantiles
      const sorted = [...arr].sort((a, b) => a - b);
      const p50 = sorted[Math.floor(sorted.length * 0.5)] || 0;
      const p90 = sorted[Math.floor(sorted.length * 0.9)] || 0;
      const p99 = sorted[Math.floor(sorted.length * 0.99)] || 0;

      lines.push(`${this.options.name}${labelPrefix}{quantile="0.5"} ${p50}`);
      lines.push(`${this.options.name}${labelPrefix}{quantile="0.9"} ${p90}`);
      lines.push(`${this.options.name}${labelPrefix}{quantile="0.99"} ${p99}`);
      lines.push(`${this.options.name}_sum${labelPrefix} ${this.sums.get(key) || 0}`);
      lines.push(`${this.options.name}_count${labelPrefix} ${this.counts.get(key) || 0}`);
    }

    return lines.join('\n');
  }
}

// Global registry
export const register = new MetricRegistry();

// Pre-defined metrics for Anchor Engine
export const metrics = {
  // Search metrics
  searchRequests: register.counter({
    name: 'anchor_search_requests_total',
    help: 'Total number of search requests',
    labelNames: ['strategy', 'status']
  }),
  
  searchDuration: register.histogram({
    name: 'anchor_search_duration_seconds',
    help: 'Search duration in seconds',
    labelNames: ['strategy'],
    buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  }),
  
  searchResults: register.histogram({
    name: 'anchor_search_results_count',
    help: 'Number of results returned per search',
    buckets: [1, 5, 10, 20, 50, 100, 200, 500, 1000]
  }),

  // Ingestion metrics
  ingestRequests: register.counter({
    name: 'anchor_ingest_requests_total',
    help: 'Total number of ingestion requests',
    labelNames: ['type', 'status']
  }),
  
  ingestDuration: register.histogram({
    name: 'anchor_ingest_duration_seconds',
    help: 'Ingestion duration in seconds',
    labelNames: ['type'],
    buckets: [0.1, 0.5, 1, 5, 10, 30, 60, 120, 300]
  }),
  
  atomsIngested: register.counter({
    name: 'anchor_atoms_ingested_total',
    help: 'Total number of atoms ingested'
  }),
  
  moleculesIngested: register.counter({
    name: 'anchor_molecules_ingested_total',
    help: 'Total number of molecules ingested'
  }),

  // System metrics
  heapUsed: register.gauge({
    name: 'anchor_heap_used_bytes',
    help: 'Current heap memory usage in bytes'
  }),
  
  heapTotal: register.gauge({
    name: 'anchor_heap_total_bytes',
    help: 'Total heap memory in bytes'
  }),
  
  rssMemory: register.gauge({
    name: 'anchor_rss_memory_bytes',
    help: 'Resident set size memory in bytes'
  }),
  
  activeConnections: register.gauge({
    name: 'anchor_active_connections',
    help: 'Number of active connections'
  }),

  // Database metrics
  dbQueries: register.counter({
    name: 'anchor_db_queries_total',
    help: 'Total number of database queries',
    labelNames: ['operation']
  }),
  
  dbQueryDuration: register.histogram({
    name: 'anchor_db_query_duration_seconds',
    help: 'Database query duration in seconds',
    labelNames: ['operation'],
    buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1]
  }),

  // Error metrics
  errors: register.counter({
    name: 'anchor_errors_total',
    help: 'Total number of errors',
    labelNames: ['operation', 'type']
  })
};

// Content-Type for Prometheus responses
export const contentType = 'text/plain; version=0.0.4; charset=utf-8';

/**
 * Get all metrics in Prometheus format
 */
export async function getMetrics(): Promise<string> {
  // Update system metrics
  const memUsage = process.memoryUsage();
  metrics.heapUsed.set(memUsage.heapUsed);
  metrics.heapTotal.set(memUsage.heapTotal);
  metrics.rssMemory.set(memUsage.rss);
  
  return register.metrics();
}

export default register;
