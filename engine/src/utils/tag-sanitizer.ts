/**
 * Tag Sanitization at Write Time
 * 
 * Ensures all tags are sanitized BEFORE being written to the database.
 * This is the single source of truth for tag filtering.
 * 
 * Standard 123: Search Result Tag Sanitization
 * 
 * Usage:
 *   import { sanitizeTagsForWrite } from './tag-sanitizer.js';
 *   const cleanTags = sanitizeTagsForWrite(rawTags);
 */

import { filterTags, filterTagsWithLogging, isTagBlacklisted } from './tag-filter.js';
import { config } from '../config/index.js';

/**
 * Sanitize tags for database write
 * - Filters blacklisted tags
 * - Normalizes tag format
 * - Enforces max tags per entity
 * - Optional logging for debugging
 */
export function sanitizeTagsForWrite(
  tags: string[] | null | undefined,
  options?: {
    context?: string;
    enableLogging?: boolean;
    maxTags?: number;
  }
): string[] {
  if (!tags || !Array.isArray(tags) || tags.length === 0) {
    return [];
  }

  const {
    context = 'tag-sanitizer',
    enableLogging = false,
    maxTags = config.TAGGING?.max_tags_per_molecule || 20
  } = options || {};

  // Step 1: Filter blacklisted tags
  let sanitized = enableLogging
    ? filterTagsWithLogging(tags, context)
    : filterTags(tags);

  // Step 2: Normalize tags (trim, lowercase optional based on config)
  sanitized = sanitized.map(tag => tag.trim());

  // Step 3: Enforce minimum tag length (from config)
  const minTagLength = config.TAGGING?.min_tag_length || 3;
  sanitized = sanitized.filter(tag => tag.length >= minTagLength);

  // Step 4: Limit max tags to prevent bloat
  if (sanitized.length > maxTags) {
    if (enableLogging) {
      console.debug(`[TagSanitizer] ${context}: Truncated from ${sanitized.length} to ${maxTags} tags`);
    }
    sanitized = sanitized.slice(0, maxTags);
  }

  return sanitized;
}

/**
 * Sanitize a single tag for write
 * Returns null if tag should be filtered
 */
export function sanitizeSingleTagForWrite(tag: string): string | null {
  if (!tag || typeof tag !== 'string') {
    return null;
  }

  const trimmed = tag.trim();

  if (isTagBlacklisted(trimmed)) {
    return null;
  }

  const minTagLength = config.TAGGING?.min_tag_length || 3;
  if (trimmed.length < minTagLength) {
    return null;
  }

  return trimmed;
}

/**
 * Sanitize tags stored as JSON string in database
 * Used when reading tags from DB columns
 */
export function sanitizeTagsFromDb(
  dbValue: string | any[] | null | undefined,
  context?: string
): string[] {
  if (!dbValue) {
    return [];
  }

  let tags: string[];

  if (typeof dbValue === 'string') {
    try {
      tags = JSON.parse(dbValue);
    } catch {
      console.warn(`[TagSanitizer] ${context}: Failed to parse tags JSON, returning empty`);
      return [];
    }
  } else if (Array.isArray(dbValue)) {
    tags = dbValue;
  } else {
    console.warn(`[TagSanitizer] ${context}: Unexpected tags type ${typeof dbValue}, returning empty`);
    return [];
  }

  return sanitizeTagsForWrite(tags, { context, enableLogging: false });
}

/**
 * Merge and sanitize tags from multiple sources
 * Deduplicates and applies all sanitization rules
 */
export function mergeAndSanitizeTags(
  tagArrays: (string[] | null | undefined)[],
  options?: {
    context?: string;
    enableLogging?: boolean;
  }
): string[] {
  const allTags = new Set<string>();

  for (const tags of tagArrays) {
    if (tags && Array.isArray(tags)) {
      const sanitized = sanitizeTagsForWrite(tags, options);
      sanitized.forEach(tag => allTags.add(tag));
    }
  }

  return Array.from(allTags);
}

/**
 * Validate tags before write - throws if invalid
 * Use for critical paths where tag integrity is required
 */
export function validateTagsForWrite(
  tags: string[],
  options?: {
    context?: string;
    strict?: boolean;
  }
): void {
  const { context = 'tag-validation', strict = false } = options || {};

  if (!Array.isArray(tags)) {
    throw new Error(`[${context}] Tags must be an array`);
  }

  const invalidTags = tags.filter(tag => {
    if (!tag || typeof tag !== 'string') return true;
    if (tag.trim().length === 0) return true;
    if (strict && isTagBlacklisted(tag)) return true;
    return false;
  });

  if (invalidTags.length > 0) {
    throw new Error(
      `[${context}] Invalid tags detected: ${invalidTags.slice(0, 10).join(', ')}${invalidTags.length > 10 ? '...' : ''}`
    );
  }
}
