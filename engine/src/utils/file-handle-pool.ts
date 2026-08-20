/**
 * File Handle Pool (v5.2.0+)
 *
 * Bounded pool for concurrent disk reads to prevent EMFILE errors and
 * excessive file descriptor usage during context inflation, search, and ingest.
 *
 * Max 10 concurrent file handles — matches Linux default ulimit soft limit
 * with headroom for other operations.
 */

import fs from 'fs';

interface PoolOptions {
  maxConcurrent?: number;
  timeoutMs?: number;
}

class FileHandlePool {
  private maxConcurrent: number;
  private activeCount = 0;
  private queue: Array<() => void> = [];
  private timeoutMs: number;

  constructor(options: PoolOptions = {}) {
    this.maxConcurrent = options.maxConcurrent ?? 10;
    this.timeoutMs = options.timeoutMs ?? 30000;
  }

  async acquire<T>(fn: () => Promise<T>): Promise<T> {
    if (this.activeCount >= this.maxConcurrent) {
      await new Promise<void>((resolve) => {
        this.queue.push(resolve);
      });
    }

    this.activeCount++;

    try {
      return await fn();
    } finally {
      this.activeCount--;
      if (this.queue.length > 0) {
        const next = this.queue.shift();
        if (next) next();
      }
    }
  }

  async readFile(path: string, encoding: BufferEncoding = 'utf-8'): Promise<string> {
    return this.acquire(() => fs.promises.readFile(path, encoding));
  }

  async openFile(path: string, flags: string = 'r'): Promise<fs.promises.FileHandle> {
    return this.acquire(() => fs.promises.open(path, flags));
  }

  getStats() {
    return {
      active: this.activeCount,
      queued: this.queue.length,
      maxConcurrent: this.maxConcurrent,
    };
  }
}

// Singleton pool for the entire engine
export const filePool = new FileHandlePool({ maxConcurrent: 10 });

/**
 * Helper to read a file with bounded concurrency.
 */
export async function pooledReadFile(path: string, encoding: BufferEncoding = 'utf-8'): Promise<string> {
  return filePool.readFile(path, encoding);
}

/**
 * Helper to open a file handle with bounded concurrency.
 */
export async function pooledOpenFile(path: string, flags: string = 'r'): Promise<fs.promises.FileHandle> {
  return filePool.openFile(path, flags);
}
