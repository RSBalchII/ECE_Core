/**
 * Streaming Search Service
 *
 * Provides memory-efficient search with async generator-based result streaming.
 * Processes results in batches to prevent memory spikes.
 *
 * Standards: 127/134/135 - Memory Management + Streaming
 */

import { config } from '../../config/index.js';
import { smartChatSearch } from './search.js';
import { StructuredLogger } from '../../utils/structured-logger.js';
import type { SearchResult } from './search-utils.js';
import type { UserContext } from '../../types/context.js';
import { logSearchResults } from './search-results-logger.js';
import { getSetting } from '../settings.js';

export interface StreamingSearchOptions {
  query: string;
  buckets?: string[];
  maxChars?: number;
  tags?: string[];
  provenance?: 'internal' | 'external' | 'quarantine' | 'all';
  useMaxRecall?: boolean;
  userContext?: UserContext;
  batchSize?: number;
  verbose?: boolean; // Enable search results logging for test verification
}

export interface SearchBatch {
  type: 'batch';
  results: SearchResult[];
  batchNumber: number;
  totalBatches: number;
  isComplete: boolean;
}

export interface SearchMetadata {
  type: 'metadata';
  strategy: string;
  totalResults: number;
  query: string;
  splitQueries?: string[];
  durationMs?: number;
}

export interface SearchProgress {
  type: 'progress';
  batchNumber: number;
  totalBatches: number;
  currentResults: number;
  percentageComplete: number;
}

export interface SearchCounterUpdate {
  type: 'counter';
  metricName: string;
  value: number;
  timestamp: number;
}

export interface SearchError {
  type: 'error';
  message: string;
  details?: string;
}

export type StreamingSearchEvent = SearchBatch | SearchMetadata | SearchProgress | SearchCounterUpdate | SearchError;

/**
 * Execute search with streaming results
 * Yields batches of results as they're processed
 */
export async function* executeStreamingSearch(
  options: StreamingSearchOptions,
): AsyncGenerator<StreamingSearchEvent> {
  const startTime = Date.now();
  const settings = await getSetting('memory.search_results_batch_size', 20);
  const batchSize = options.batchSize ?? (settings as number) ?? 20;

  try {
    StructuredLogger.info('STREAMING_SEARCH_START', {
      query: options.query.substring(0, 100),
      batchSize,
    });

    // Execute the full search first (this is the expensive part)
    // We can't easily stream the DB query itself, but we can stream the results
    const searchResult = await smartChatSearch(
      options.query,
      options.buckets || [],
      options.maxChars || 5000,
      options.tags || [],
      options.provenance || 'all',
      options.useMaxRecall || false,
      options.userContext,
    );

    const allResults = searchResult.results;
    const totalBatches = Math.ceil(allResults.length / batchSize);

    // Yield metadata first
    yield {
      type: 'metadata',
      strategy: searchResult.strategy,
      totalResults: allResults.length,
      query: options.query,
      splitQueries: searchResult.splitQueries,
    };

    // Stream results in batches with progress updates
    for (let i = 0; i < allResults.length; i += batchSize) {
      const batch = allResults.slice(i, i + batchSize);
      const batchNumber = Math.floor(i / batchSize) + 1;
      
      // Calculate current position for progress tracking
      const currentResults = i + batch.length;
      const percentageComplete = totalBatches > 0 
        ? ((batchNumber - 1) / totalBatches) * 100 
        : 0;

      // Allow event loop to breathe between batches
      await new Promise(resolve => setImmediate(resolve));

      // Optional: Force GC between batches if available
      if (global.gc && i > 0) {
        global.gc();
      }

      // Yield progress update BEFORE batch (gives user visual cue that work is happening)
      yield {
        type: 'progress',
        batchNumber,
        totalBatches,
        currentResults,
        percentageComplete: Math.round(percentageComplete * 10) / 10,
      };

      // Also track some metrics as counter updates for detailed feedback
      const counterUpdate = {
        type: 'counter' as const,
        metricName: `results_processed_${i}`,
        value: currentResults,
        timestamp: Date.now() - startTime,
      } as SearchCounterUpdate;
      yield counterUpdate;

      // Now send the batch results
      yield {
        type: 'batch',
        results: batch,
        batchNumber,
        totalBatches,
        isComplete: batchNumber === totalBatches,
      };

      StructuredLogger.info('STREAMING_BATCH_SENT', {
        batchNumber,
        totalBatches,
        resultsInBatch: batch.length,
        cumulativeResults: currentResults,
      });
    }

    const duration = Date.now() - startTime;

    // Yield final metadata with duration
    yield {
      type: 'metadata',
      strategy: searchResult.strategy,
      totalResults: allResults.length,
      query: options.query,
      splitQueries: searchResult.splitQueries,
      durationMs: duration,
    };

    // Log results to .anchor/logs/ if verbose mode is enabled (for test verification)
    const logMetadata = {
      strategy: searchResult.strategy,
      totalResults: allResults.length,
      durationMs: duration,
      splitQueries: searchResult.splitQueries,
      buckets: options.buckets,
      tags: options.tags,
    };

    logSearchResults(options.query, allResults, logMetadata, { verbose: options.verbose });

    StructuredLogger.info('STREAMING_SEARCH_COMPLETE', {
      query: options.query.substring(0, 100),
      totalResults: allResults.length,
      durationMs: duration,
      batches: totalBatches,
    });

  } catch (error: any) {
    StructuredLogger.error('STREAMING_SEARCH_ERROR', error, {
      query: options.query.substring(0, 100),
    });

    yield {
      type: 'error',
      message: error.message,
      details: error.stack,
    };
  }
}

/**
 * Format streaming event for SSE (Server-Sent Events)
 */
export function formatSSE(event: StreamingSearchEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

