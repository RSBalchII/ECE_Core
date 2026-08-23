/**
 * Cross-Platform Path Normalization Utility
 * 
 * Handles Windows (C:\Users\rsbiiw\Projects) and Unix (/home/user/projects) paths
 * with proper validation for the .anchor hierarchy recognition.
 */

import path from 'path';
import { existsSync } from 'fs';

/**
 * Normalize a path to use forward slashes consistently across platforms.
 * Converts Windows backslashes to forward slashes while preserving the drive letter.
 */
export function normalizePathSlashes(filePath: string): string {
  // Replace backslashes with forward slashes
  return filePath.replace(/\\/g, '/');
}

/**
 * Convert a Unix-style path to Windows format if needed.
 * @param unixPath - Path that may be in Unix format
 * @param windowsDrive - Windows drive letter (e.g., 'C:')
 * @returns Windows-formatted path or original if already Windows-style
 */
export function ensureWindowsPath(unixPath: string, windowsDrive: string = 'C:'): string {
  const normalized = normalizePathSlashes(unixPath);
  
  // If it doesn't start with a drive letter and looks like Unix, prepend C:
  if (!normalized.match(/^[a-zA-Z]:/) && !normalized.startsWith('/')) {
    return `${windowsDrive}${normalized}`;
  }
  
  // Convert leading / to drive format
  if (normalized.startsWith('/') || normalized.startsWith('//')) {
    return `${windowsDrive}${normalized.replace(/^\/+/, '/')}`;
  }
  
  return windowsDrive + ':' + normalized.substring(1);
}

/**
 * Validate that a path exists within the expected .anchor hierarchy.
 */
export function validateAnchorHierarchy(filePath: string): {
  valid: boolean;
  isInternal: boolean;
  isInExternalInbox: boolean;
  isInMirroredBrain: boolean;
  message?: string;
} {
  const normalized = normalizePathSlashes(filePath);
  
  // Check if path contains .anchor directory
  const hasAnchor = normalized.includes('/.anchor/');
  if (!hasAnchor && !normalized.match(/\.anchor[\/\\]/)) {
    return {
      valid: false,
      isInternal: false,
      isInExternalInbox: false,
      isInMirroredBrain: false,
      message: 'Path does not contain .anchor directory'
    };
  }
  
  const isInInbox = normalized.includes('/inbox/') || normalized.match(/\/inbox[\/\\]/) !== null;
  const isInExternalInbox = normalized.includes('/external-inbox/') || normalized.match(/\/external-inbox[\/\\]/) !== null;
  const isInMirroredBrain = normalized.includes('/mirror_brain/') || normalized.match(/\/mirror_brain[\\/]/) !== null;
  
  return {
    valid: true,
    isInternal: isInInbox,
    isInExternalInbox,
    isInMirroredBrain,
    message: `Path validated: ${filePath}`
  };
}

/**
 * Create a normalized path that works across Windows and Unix.
 */
export function createNormalizedAbsolutePath(
  baseDir: string, 
  relativePath: string
): string {
  const absolute = path.resolve(baseDir, relativePath);
  
  // Ensure forward slashes for consistency
  return normalizePathSlashes(absolute);
}

/**
 * Validate that a directory exists and is accessible.
 */
export function validateDirectoryExists(dirPath: string): boolean {
  try {
    const normalized = normalizePathSlashes(dirPath);
    
    // Try both forward and backward slash formats for Windows compatibility
    return existsSync(normalized) || existsSync(normalized.replace(/\/+/g, '\\'));
  } catch {
    return false;
  }
}

/**
 * Get the platform-appropriate path separator.
 */
export function getPathSeparator(): string {
  return process.platform === 'win32' ? '\\' : '/';
}

/**
 * Convert between path separators based on target platform.
 */
export function convertPathSeparators(
  filePath: string, 
  toUnix: boolean = true
): string {
  if (toUnix) {
    return normalizePathSlashes(filePath);
  }
  
  // Convert to Windows format
  return filePath.replace(/\//g, '\\');
}

/**
 * Validate paths-config hierarchy for .anchor structure.
 */
export function validatePathsConfig(
  inboxDir: string,
  externalInboxDir: string,
  mirroredBrainDir: string,
  projectRoot: string
): {
  valid: boolean;
  errors: string[];
  warnings: string[];
} {
  const errors: string[] = [];
  const warnings: string[] = [];
  
  // Normalize all paths for comparison
  const inboxNorm = normalizePathSlashes(inboxDir);
  const externalInboxNorm = normalizePathSlashes(externalInboxDir);
  const mirroredBrainNorm = normalizePathSlashes(mirroredBrainDir);
  const projectRootNorm = normalizePathSlashes(projectRoot);
  
  // Check each path is under .anchor
  if (!inboxNorm.includes('.anchor') || !inboxNorm.includes('inbox')) {
    errors.push(`INBOX_DIR (${inboxDir}) should be under .anchor/inbox`);
  }
  
  if (!externalInboxNorm.includes('.anchor') || !externalInboxNorm.includes('external-inbox')) {
    errors.push(`EXTERNAL_INBOX_DIR (${externalInboxDir}) should be under .anchor/external-inbox`);
  }
  
  if (!mirroredBrainNorm.includes('.anchor') || !mirroredBrainNorm.includes('mirror_brain')) {
    errors.push(`MIRRORED_BRAIN_DIR (${mirroredBrainDir}) should be under .anchor/mirror_brain`);
  }
  
  // Check all paths are absolute
  if (!path.isAbsolute(inboxDir)) {
    errors.push('INBOX_DIR should be an absolute path');
  }
  if (!path.isAbsolute(externalInboxDir)) {
    errors.push('EXTERNAL_INBOX_DIR should be an absolute path');
  }
  if (!path.isAbsolute(mirroredBrainDir)) {
    errors.push('MIRRORED_BRAIN_DIR should be an absolute path');
  }
  
  // Check paths are under project root
  if (!inboxNorm.startsWith(projectRootNorm + '/') && !inboxNorm.startsWith(projectRootNorm.replace(/\/$/, ''))) {
    warnings.push(`INBOX_DIR is not a subdirectory of PROJECT_ROOT`);
  }
  if (!externalInboxNorm.startsWith(projectRootNorm + '/') && !externalInboxNorm.startsWith(projectRootNorm.replace(/\/$/, ''))) {
    warnings.push(`EXTERNAL_INBOX_DIR is not a subdirectory of PROJECT_ROOT`);
  }
  if (!mirroredBrainNorm.startsWith(projectRootNorm + '/') && !mirroredBrainNorm.startsWith(projectRootNorm.replace(/\/$/, ''))) {
    warnings.push(`MIRRORED_BRAIN_DIR is not a subdirectory of PROJECT_ROOT`);
  }
  
  // Check paths are distinct
  const uniquePaths = new Set([inboxDir, externalInboxDir, mirroredBrainDir]);
  if (uniquePaths.size < 3) {
    errors.push('INBOX_DIR, EXTERNAL_INBOX_DIR, and MIRRORED_BRAIN_DIR should be different directories');
  }
  
  return {
    valid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Create a path that works on both Windows and Unix systems.
 */
export function crossPlatformJoin(
  ...parts: string[]
): string {
  // Use path.join for platform-specific separation
  const joined = path.join(...parts);
  
  // Convert to forward slashes for consistency in code/configs
  return normalizePathSlashes(joined);
}
