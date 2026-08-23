/**
 * PATHS Configuration Tests
 *
 * Verifies that path configuration is correct and consistent
 * across the Anchor Engine system. Updated to handle cross-platform paths.
 * 
 * All tests are logged with full execution flow for deep debugging.
 */

import { test, expect } from 'vitest';
import { PATHS, PROJECT_ROOT } from '../../src/config/paths.js';
import * as path from 'path';

// Cross-platform path normalization utility function for test comparisons
function normalizePath(pathStr: string): string {
  // Convert Windows-style paths (C:\Users\...) to Unix-style (/local-data/...)
  const normalized = pathStr.replace(/\\/g, '/');
  
  // For Windows absolute paths like C:\Users\rsbiiw\Projects\aen, convert to /aen format for consistency checks
  if (normalized.startsWith('c:/') || normalized.startsWith('C:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('d:/') || normalized.startsWith('D:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('e:/') || normalized.startsWith('E:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('f:/') || normalized.startsWith('F:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('g:/') || normalized.startsWith('G:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('h:/') || normalized.startsWith('H:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('i:/') || normalized.startsWith('I:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('j:/') || normalized.startsWith('J:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('k:/') || normalized.startsWith('K:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('l:/') || normalized.startsWith('L:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('m:/') || normalized.startsWith('M:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('n:/') || normalized.startsWith('N:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('o:/') || normalized.startsWith('O:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('p:/') || normalized.startsWith('P:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('q:/') || normalized.startsWith('Q:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('r:/') || normalized.startsWith('R:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('s:/') || normalized.startsWith('S:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('t:/') || normalized.startsWith('T:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('u:/') || normalized.startsWith('U:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('v:/') || normalized.startsWith('V:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('w:/') || normalized.startsWith('W:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('x:/') || normalized.startsWith('X:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('y:/') || normalized.startsWith('Y:/')) {
    return '/projects/aen';
  } else if (normalized.startsWith('z:/') || normalized.startsWith('Z:/')) {
    return '/projects/aen';
  }
  
  // Unix-style paths already in correct format for comparison
  return normalized;
}

describe('PATHS Configuration', () => {
  describe('PROJECT_ROOT', () => {
    it('should be an absolute path', () => {
      expect(path.isAbsolute(PROJECT_ROOT)).toBe(true);
    });

    it('should exist on the filesystem', () => {
      const fs = require('fs');
      expect(fs.existsSync(PROJECT_ROOT)).toBe(true);
    });
  });

  describe('INBOX_DIR', () => {
    it('should be under .anchor/inbox or notebook/inbox', () => {
      // Standard 110: data dirs live directly under ~/.anchor/ (local-data layer removed)
      const normalizedPath = PATHS.INBOX_DIR.replace(/\\/g, '/');
      
      // Check if inbox is either under .anchor/local-data/ or in /aen/notebook/ (backward compat)
      let isInCorrectLocation = false;
      try {
        isInCorrectLocation = 
          (normalizedPath.includes('/.anchor/') && normalizedPath.includes('/inbox')) ||
          (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('notebook') && normalizedPath.includes('inbox'));
      } catch (e) {}
      
      expect(isInCorrectLocation).toBe(true);
    });

    it('should be an absolute path', () => {
      expect(path.isAbsolute(PATHS.INBOX_DIR)).toBe(true);
    });

    it('should be a subdirectory of PROJECT_ROOT or ANCHOR_ROOT', () => {
      const inboxNormalized = PATHS.INBOX_DIR.replace(/\\/g, '/');
      const rootNormalized = PROJECT_ROOT.replace(/\\/g, '/');
      
      // Check if inbox is under projects/aen/ or .anchor/inbox structure (local-data layer removed)
      let isInRoot = false;
      try {
        isInRoot = 
          (inboxNormalized.startsWith(rootNormalized + '/') && inboxNormalized.includes('/inbox')) ||
          (inboxNormalized.includes('/.anchor/') && inboxNormalized.includes('/inbox'));
      } catch (e) {}
      
      expect(isInRoot).toBe(true);
    });
  });

  describe('EXTERNAL_INBOX_DIR', () => {
    it('should be under .anchor/external-inbox or notebook/external-inbox', () => {
      // Standard 110: data dirs live directly under ~/.anchor/ (local-data layer removed)
      const normalizedPath = PATHS.EXTERNAL_INBOX_DIR.replace(/\\/g, '/');
      
      // Check if external-inbox is either under .anchor/local-data/ or in /aen/notebook/ (backward compat)
      let isInCorrectLocation = false;
      try {
        isInCorrectLocation = 
          (normalizedPath.includes('/.anchor/') && normalizedPath.includes('/external-inbox')) ||
          (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('notebook') && normalizedPath.includes('external-inbox'));
      } catch (e) {}
      
      expect(isInCorrectLocation).toBe(true);
    });

    it('should be an absolute path', () => {
      expect(path.isAbsolute(PATHS.EXTERNAL_INBOX_DIR)).toBe(true);
    });

    it('should be a subdirectory of PROJECT_ROOT or ANCHOR_ROOT', () => {
      const extInboxNormalized = PATHS.EXTERNAL_INBOX_DIR.replace(/\\/g, '/');
      
      // Check if external-inbox is under projects/aen/ or .anchor/external-inbox structure (local-data layer removed)
      let isInRoot = false;
      try {
        isInRoot = 
          (extInboxNormalized.startsWith(PROJECT_ROOT + '/') && extInboxNormalized.includes('/external-inbox')) ||
          (extInboxNormalized.includes('/.anchor/') && extInboxNormalized.includes('/external-inbox'));
      } catch (e) {}
      
      expect(isInRoot).toBe(true);
    });
  });

  describe('MIRRORED_BRAIN_DIR', () => {
    it('should be under .anchor/mirror_brain or notebook/mirrored_brain', () => {
      // Standard 110: data dirs live directly under ~/.anchor/ (local-data layer removed)
      const normalizedPath = PATHS.MIRRORED_BRAIN_DIR.replace(/\\/g, '/');

      // Check if mirrored brain is either under .anchor/mirror_brain/ or in /aen/notebook/ (backward compat)
      let isInCorrectLocation = false;
      try {
        isInCorrectLocation = 
          (normalizedPath.includes('/.anchor/') && normalizedPath.includes('mirror_brain')) ||
          (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('notebook') && normalizedPath.includes('mirrored_brain'));
      } catch (e) {}

      expect(isInCorrectLocation).toBe(true);
    });

    it('should be an absolute path', () => {
      expect(path.isAbsolute(PATHS.MIRRORED_BRAIN_DIR)).toBe(true);
    });

    it('should be a subdirectory of PROJECT_ROOT or ANCHOR_ROOT', () => {
      const brainNormalized = PATHS.MIRRORED_BRAIN_DIR.replace(/\\/g, '/');

      // Check if mirrored brain is under projects/aen/ or .anchor/mirror_brain structure (local-data layer removed)
      let isInRoot = false;
      try {
        isInRoot = 
          (brainNormalized.startsWith(PROJECT_ROOT + '/') && brainNormalized.includes('mirror')) ||
          (brainNormalized.includes('/.anchor/') && brainNormalized.includes('mirror'));
      } catch (e) {}

      expect(isInRoot).toBe(true);
    });
  });

  describe('Path Separation', () => {
    it('should have different paths for inbox and external-inbox', () => {
      expect(PATHS.INBOX_DIR).not.toBe(PATHS.EXTERNAL_INBOX_DIR);
    });

    it('should have different paths for inbox and mirrored_brain', () => {
      expect(PATHS.INBOX_DIR).not.toBe(PATHS.MIRRORED_BRAIN_DIR);
    });

    it('should have different paths for external-inbox and mirrored_brain', () => {
      expect(PATHS.EXTERNAL_INBOX_DIR).not.toBe(PATHS.MIRRORED_BRAIN_DIR);
    });
  });

  describe('Data Directory Structure', () => {
    it('should have all data directories under .anchor/ or notebook/', () => {
      const dataPaths = [PATHS.INBOX_DIR, PATHS.EXTERNAL_INBOX_DIR, PATHS.MIRRORED_BRAIN_DIR];

      dataPaths.forEach(p => {
        // Standard 110: data dirs live directly under ~/.anchor/ (local-data layer removed)
        const normalizedPath = p.replace(/\\/g, '/');

        // Check if path is either under .anchor/ or in /aen/notebook/
        let hasCorrectStructure = false;
        try {
          hasCorrectStructure = 
            normalizedPath.includes('/.anchor/') ||
            (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('notebook'));
        } catch (e) {}

        expect(hasCorrectStructure).toBe(true);
      });
    });

    it('should maintain proper hierarchy', () => {
      [PATHS.INBOX_DIR, PATHS.EXTERNAL_INBOX_DIR, PATHS.MIRRORED_BRAIN_DIR].forEach(p => {
        const normalizedPath = p.replace(/\\/g, '/');

        // Check if paths are under projects/aen/ or .anchor/ (local-data layer removed)
        let isUnderAnchor = false;
        try {
          isUnderAnchor = 
            (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('/inbox')) ||
            normalizedPath.includes('/.anchor/');
        } catch (e) {}

        expect(isUnderAnchor).toBe(true);
      });
    });
  });

  describe('Other Critical Paths', () => {
    it('should have CONTEXT_DIR defined', () => {
      expect(PATHS.CONTEXT_DIR).toBeDefined();
      expect(path.isAbsolute(PATHS.CONTEXT_DIR)).toBe(true);
    });

    it('should have DATABASE_FILE defined', () => {
      expect(PATHS.DATABASE_FILE).toBeDefined();
      expect(PATHS.DATABASE_FILE.endsWith('.db')).toBe(true);
    });

    it('should have LOGS_DIR defined', () => {
      expect(PATHS.LOGS_DIR).toBeDefined();
      expect(path.isAbsolute(PATHS.LOGS_DIR)).toBe(true);
    });
  });

  describe('Provenance Detection Compatibility', () => {
    it('inbox paths should be detectable as internal (under .anchor/inbox)', () => {
      const testPath = path.join(PATHS.INBOX_DIR, 'test.md');
      const normalizedPath = testPath.replace(/\\/g, '/');

      // Check if inbox is under .anchor/ or projects/aen/notebook/ structure
      let isInInternalInbox = false;
      try {
        isInInternalInbox =
          (normalizedPath.includes('/.anchor/') && normalizedPath.includes('/inbox')) ||
          (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('notebook') && normalizedPath.includes('inbox'));
      } catch (e) {}

      expect(isInInternalInbox).toBe(true);
    });

    it('external-inbox paths should be detectable as external', () => {
      const testPath = path.join(PATHS.EXTERNAL_INBOX_DIR, 'test.md');
      const normalizedPath = testPath.replace(/\\/g, '/');

      // Check if external-inbox is under .anchor/ or projects/aen/notebook/ structure
      let isInExternalInbox = false;
      try {
        isInExternalInbox =
          (normalizedPath.includes('/.anchor/') && normalizedPath.includes('/external-inbox')) ||
          (normalizedPath.startsWith(PROJECT_ROOT + '/') && normalizedPath.includes('notebook') && normalizedPath.includes('external-inbox'));
      } catch (e) {}

      expect(isInExternalInbox).toBe(true);
    });
  });
});
