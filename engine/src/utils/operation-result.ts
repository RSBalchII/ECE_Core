/**
 * OperationResult Pattern
 * 
 * Standardized result type for operations that can succeed or fail.
 * Provides consistent error handling and metrics tracking.
 * 
 * Usage:
 *   const result = await someOperation();
 *   if (!result.success) {
 *     console.error(result.error);
 *     return;
 *   }
 *   // Use result.data
 */

export interface OperationResult<T> {
  success: true;
  data: T;
  metrics?: OperationMetrics;
}

export interface OperationFailure {
  success: false;
  error: string;
  errorCode?: string;
  cause?: Error;
  metrics?: OperationMetrics;
}

export interface OperationMetrics {
  durationMs: number;
  startTime: number;
  endTime: number;
  retries?: number;
  warnings?: string[];
}

export type Result<T> = OperationResult<T> | OperationFailure;

/**
 * Create a successful operation result
 */
export function success<T>(data: T, metrics?: Partial<OperationMetrics>): OperationResult<T> {
  return {
    success: true,
    data,
    metrics: metrics ? {
      durationMs: metrics.durationMs || 0,
      startTime: metrics.startTime || Date.now(),
      endTime: metrics.endTime || Date.now(),
      retries: metrics.retries,
      warnings: metrics.warnings
    } : undefined
  };
}

/**
 * Create a failed operation result
 */
export function failure(
  error: string | Error,
  options?: {
    errorCode?: string;
    cause?: Error;
    metrics?: Partial<OperationMetrics>;
  }
): OperationFailure {
  const errorObj = typeof error === 'string' ? new Error(error) : error;
  
  return {
    success: false,
    error: errorObj.message,
    errorCode: options?.errorCode,
    cause: options?.cause || errorObj,
    metrics: options?.metrics ? {
      durationMs: options.metrics.durationMs || 0,
      startTime: options.metrics.startTime || Date.now(),
      endTime: options.metrics.endTime || Date.now(),
      retries: options.metrics.retries,
      warnings: options.metrics.warnings
    } : undefined
  };
}

/**
 * Execute an operation with timing and error handling
 */
export async function executeWithMetrics<T>(
  operation: () => Promise<T>,
  options?: {
    operationName?: string;
    maxRetries?: number;
    retryDelayMs?: number;
    shouldRetry?: (error: Error) => boolean;
  }
): Promise<Result<T>> {
  const {
    operationName = 'anonymous',
    maxRetries = 0,
    retryDelayMs = 100,
    shouldRetry = () => false
  } = options || {};

  const startTime = Date.now();
  let retries = 0;
  const warnings: string[] = [];

  while (true) {
    try {
      const data = await operation();
      const endTime = Date.now();

      return success(data, {
        durationMs: endTime - startTime,
        startTime,
        endTime,
        retries,
        warnings: warnings.length > 0 ? warnings : undefined
      });
    } catch (error) {
      const errorObj = error instanceof Error ? error : new Error(String(error));
      const endTime = Date.now();

      // Check if we should retry
      if (retries < maxRetries && shouldRetry(errorObj)) {
        warnings.push(`Retry ${retries + 1}/${maxRetries} after error: ${errorObj.message}`);
        retries++;
        
        if (retryDelayMs > 0) {
          await new Promise(resolve => setTimeout(resolve, retryDelayMs));
        }
        continue;
      }

      return failure(errorObj, {
        errorCode: `${operationName}_FAILED`,
        metrics: {
          durationMs: endTime - startTime,
          startTime,
          endTime,
          retries,
          warnings: warnings.length > 0 ? warnings : undefined
        }
      });
    }
  }
}

/**
 * Unwrap a result or throw an error
 */
export function unwrap<T>(result: Result<T>): T {
  if (!result.success) {
    const error = new Error(result.error);
    if (result.cause) {
      error.cause = result.cause;
    }
    throw error;
  }
  return result.data;
}

/**
 * Unwrap a result or return a default value
 */
export function unwrapOr<T>(result: Result<T>, defaultValue: T): T {
  return result.success ? result.data : defaultValue;
}

/**
 * Unwrap a result or return null
 */
export function unwrapOrNull<T>(result: Result<T>): T | null {
  return result.success ? result.data : null;
}

/**
 * Map a result's data
 */
export function mapResult<T, U>(result: Result<T>, mapper: (data: T) => U): Result<U> {
  if (result.success) {
    return success(mapper(result.data), result.metrics);
  }
  return result as OperationFailure;
}

/**
 * Chain operations - only execute next if previous succeeded
 */
export async function chain<T, U>(
  result: Result<T>,
  next: (data: T) => Promise<Result<U>>
): Promise<Result<U>> {
  if (!result.success) {
    return result as OperationFailure;
  }
  return await next(result.data);
}
