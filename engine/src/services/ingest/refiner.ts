// engine/src/services/ingest/refiner.ts

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import { atomizeContent as rawAtomize } from './atomizer.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(import.meta.url);

// --- NATIVE MODULE LOADING ---
let native: any = null;
try {
    // Try release build first
    native = require('../../../build/Release/ece_native.node');
    console.log('[Refiner] Loaded Native Accelerator (C++17) 🚀');
} catch (e) {
    try {
        // Try debug build or other path
        native = require('../../../build/Debug/ece_native.node');
    } catch (e2) {
        console.warn('[Refiner] running in JS-Only mode (Native module not found).');
    }
}

/**
 * Atom Interface
 */
export interface Atom {
    id: string;
    content: string;
    sourceId: string;
    sourcePath: string;
    sequence: number;
    timestamp: number;
    provenance: 'internal' | 'external' | 'quarantine';
    embedding?: number[];
    simhash: string; // <--- NEW: SimHash (Hex String)
    tags: string[]; // <--- NEW: Supports Project Root Extraction
}

// Variable to cache sovereign keywords
let cachedSovereignKeywords: string[] | null = null;

/**
 * Helper: Load Sovereign Keywords from context/sovereign_tags.json
 */
function loadSovereignKeywords(): string[] {
    if (cachedSovereignKeywords) return cachedSovereignKeywords;

    try {
        const possiblePaths = [
            path.join(process.cwd(), 'context', 'internal_tags.json'),
            path.join(process.cwd(), '..', 'context', 'internal_tags.json'),
            path.join(__dirname, '../../../../context/internal_tags.json')
        ];

        for (const p of possiblePaths) {
            if (fs.existsSync(p)) {
                const content = fs.readFileSync(p, 'utf-8');
                const json = JSON.parse(content);
                if (Array.isArray(json.keywords)) {
                    console.log(`[Refiner] Loaded ${json.keywords.length} Internal Keywords from ${p}`);
                    cachedSovereignKeywords = json.keywords;
                    return cachedSovereignKeywords!;
                }
            }
        }

        console.warn(`[Refiner] internal_tags.json not found in expected paths.`);
        cachedSovereignKeywords = [];
        return [];
    } catch (e) {
        console.error(`[Refiner] Failed to load internal_tags.json:`, e);
        return [];
    }
}

/**
 * Helper: Scan content for keywords and return relevant tags
 */
function scanForSovereignTags(content: string, keywords: string[]): string[] {
    const foundTags: string[] = [];
    const lowerContent = content.toLowerCase();

    for (const keyword of keywords) {
        // Simple case-insensitive check.
        if (lowerContent.includes(keyword.toLowerCase())) {
            foundTags.push(`#${keyword}`);
        }
    }
    return foundTags;
}

/**
 * HELPER: The Key Assassin
 * Surgically removes JSON wrapper noise without breaking code brackets.
 */
function cleanseJsonArtifacts(text: string, filePath: string): string {
    let clean = text;
    const stats = {
        metaKeys: 0,
        wrappers: 0,
        escapes: 0
    };

    // 1. Recursive Un-escape (Run this FIRST to reveal hidden keys and fix code formatting)
    // 1. Recursive Un-escape (Run this FIRST to reveal hidden keys and fix code formatting)
    // NATIVE ACCELERATION
    if (native && native.cleanse) {
        // C++ does the unescape loop in one pass
        const beforeLen = clean.length;
        clean = native.cleanse(clean);
        if (clean.length < beforeLen) stats.escapes += (beforeLen - clean.length);
    } else {
        // JS Fallback (Slower)
        let pass = 0;
        while (clean.includes('\\') && pass < 3) {
            pass++;
            const beforeLen = clean.length;
            clean = clean.replace(/\\"/g, '"');
            clean = clean.replace(/\\n/g, '\n');
            clean = clean.replace(/\\t/g, '\t');
            if (clean.length < beforeLen) stats.escapes += (beforeLen - clean.length);
        }
    }

    // 2. Code Block Protection (Masking)
    const codeBlocks: string[] = [];
    const PLACEHOLDER = '___CODE_BLOCK_PLACEHOLDER___';

    clean = clean.replace(/```[\s\S]*?```/g, (match) => {
        codeBlocks.push(match);
        return `${PLACEHOLDER}${codeBlocks.length - 1}___`;
    });

    // Helper to count and replace
    const purge = (pattern: RegExp, type: 'metaKeys' | 'wrappers' | 'escapes') => {
        const matches = clean.match(pattern);
        if (matches) {
            stats[type] += matches.length;
            clean = clean.replace(pattern, '');
        }
    };

    // 3. Remove known metadata keys (Only from non-code text)
    purge(/"type"\s*:\s*"[^"]*",?/g, 'metaKeys');
    purge(/"timestamp"\s*:\s*"[^"]*",?/g, 'metaKeys');
    purge(/"source"\s*:\s*"[^"]*",?/g, 'metaKeys');

    // 4. Remove the wrapper keys
    purge(/"response_content"\s*:\s*/g, 'wrappers');
    purge(/"thinking_content"\s*:\s*/g, 'wrappers');
    purge(/"content"\s*:\s*/g, 'wrappers');

    // 5. Structural cleanup
    // Matches: }, {  OR  },{
    clean = clean.replace(/\}\s*,\s*\{/g, '\n\n');

    // 6. Clean up outer brackets
    clean = clean.trim();
    if (clean.startsWith('[') && clean.endsWith(']')) {
        clean = clean.substring(1, clean.length - 1);
    }

    // 7. Restore Code Blocks (Unmasking)
    clean = clean.replace(/___CODE_BLOCK_PLACEHOLDER___(\d+)___/g, (match, index) => {
        return codeBlocks[parseInt(index)] || match;
    });

    // 8. Slash Compressor (Context Hygiene)
    // Collapses "C:\\\\\\\\Users" -> "C:/Users" to save tokens
    const beforeSlash = clean.length;
    clean = clean.replace(/\\{2,}/g, '/');
    if (clean.length < beforeSlash) {
        // console.log(`[Refiner] Slash Compressor saved ${beforeSlash - clean.length} chars.`);
    }

    if (stats.metaKeys > 0 || stats.wrappers > 0 || stats.escapes > 0) {
        console.log(`[Refiner] Key Assassin Report for ${filePath}: Removed ${stats.metaKeys} Metadata Keys, ${stats.wrappers} Wrappers, and processed ${stats.escapes} escape chars.`);
    }

    return clean;
}

/**
 * NEW: Project Root Extractor
 * Automatically derives context tags from the file path.
 */
function extractProjectTags(filePath: string): string[] {
    const tags: string[] = [];
    const normalized = filePath.replace(/\\/g, '/');
    const parts = normalized.split('/');

    // 1. Project Tag (Root Folder)
    // Assumption: path is relative to notebook/inbox or project root
    if (parts[0] === 'codebase' && parts[1]) {
        tags.push(`#project:${parts[1]}`);
    }
    // Fallback: If we are in ECE_Core root
    else if (process.cwd().includes('ECE_Core')) {
        tags.push(`#project:ECE_Core`);
    }

    // 2. Structural Tags (src, specs, tests)
    if (normalized.includes('/src/') || normalized.startsWith('src/')) tags.push('#src');
    if (normalized.includes('/specs/') || normalized.startsWith('specs/')) tags.push('#specs');
    if (normalized.includes('/tests/') || normalized.startsWith('tests/')) tags.push('#test');
    if (normalized.includes('/docs/') || normalized.startsWith('docs/')) tags.push('#docs');

    // 3. File Type Tags
    if (normalized.endsWith('.ts') || normalized.endsWith('.js')) tags.push('#code');
    if (normalized.endsWith('.md')) tags.push('#doc');

    return tags;
}

/**
 * Refine Content
 */
export async function refineContent(rawBuffer: Buffer | string, filePath: string, options: { skipEmbeddings?: boolean } = {}): Promise<Atom[]> {
    options.skipEmbeddings = true; // Tag-Walker Standard

    let cleanText = '';

    // --- PHASE 1: BASIC DECODING ---
    if (Buffer.isBuffer(rawBuffer)) {
        cleanText = rawBuffer.toString('utf8');
    } else {
        cleanText = rawBuffer;
    }

    // Remove BOM and Binary Trash
    cleanText = cleanText.replace(/^\uFEFF/, '').replace(/[\u0000\uFFFD]/g, '');
    cleanText = cleanText.replace(/\r\n/g, '\n');

    // SURGEON V2: Aggressive Regex cleaning for "Processing..." spam
    // Handles both newlines and mid-line concatenation (e.g., "FileA... Processing 'FileB'...")
    const beforeSurgeon = cleanText.length;
    cleanText = cleanText.replace(/(?:^|\s|\.{3}\s*)Processing '[^']+'\.{3}/g, '\n');

    // Clean up resulting empty lines
    cleanText = cleanText.replace(/\n{3,}/g, '\n\n');

    // Logic for logging removal stats
    if (cleanText.length < beforeSurgeon) {
        // console.log(`[Refiner] Surgeon V2 removed ${beforeSurgeon - cleanText.length} chars of log spam.`);
    }

    let strategy: 'code' | 'prose' | 'blob' = 'prose';

    // HEURISTIC FIX: Check for the specific schema keys
    const isSourceCode = /\.(ts|tsx|js|jsx|py|rs|go|java|cpp|h|c)$/.test(filePath);

    const isJsonLog = !isSourceCode && (
        cleanText.includes('"response_content":') ||
        (cleanText.includes('"type":') && cleanText.includes('"Coda')) ||
        cleanText.includes('"thinking_content":')
    );

    if (isJsonLog || filePath.endsWith('.json')) {
        console.log(`[Refiner] Detected JSON artifacts in ${filePath}. Attempting extraction...`);

        try {
            // STRATEGY A: Try Parsing (Perfect extraction)
            let jsonText = cleanText;
            if (!jsonText.trim().startsWith('[')) {
                const arrayStart = jsonText.indexOf('[');
                const arrayEnd = jsonText.lastIndexOf(']');
                if (arrayStart !== -1 && arrayEnd !== -1) {
                    jsonText = jsonText.substring(arrayStart, arrayEnd + 1);
                }
            }

            const json = JSON.parse(jsonText);
            const messages = Array.isArray(json) ? json : (json.messages || []);

            if (Array.isArray(messages)) {
                cleanText = messages.map((m: any) => {
                    const role = (m.role || m.type || 'unknown').toUpperCase();
                    // Prefer response_content, fallback to content
                    const content = m.response_content || m.content || '';
                    const ts = m.timestamp ? ` [${m.timestamp}]` : '';
                    return `### ${role}${ts}\n${content}`;
                }).join('\n\n');

                // DOUBLE-TAP: Run the Assassin on the extracted text to catch nested artifacts
                cleanText = cleanseJsonArtifacts(cleanText, filePath);
            } else {
                console.warn(`[Refiner] JSON Structure Mismatch for ${filePath}. Running Key Assassin...`);
                cleanText = cleanseJsonArtifacts(cleanText, filePath);
            }
        } catch (e) {
            // STRATEGY B: The Key Assassin (Fallback)
            console.warn(`[Refiner] JSON Parse failed for ${filePath}. Running Key Assassin...`);
            cleanText = cleanseJsonArtifacts(cleanText, filePath);
        }
    }

    // --- PHASE 3: STRATEGY SELECTION ---
    const lineCount = cleanText.split('\n').length;
    const avgLineLength = cleanText.length / (lineCount || 1);

    if (avgLineLength > 300 || (cleanText.length > 50000 && lineCount < 50)) {
        strategy = 'blob';
    } else if (/\.(ts|js|py|rs|cpp|c|h|go|java)$/.test(filePath)) {
        strategy = 'code';
    }

    // --- PHASE 4: ATOMIZATION ---
    const rawAtoms = rawAtomize(cleanText, strategy);

    // GENERATE FILE-LEVEL TAGS ONCE
    const autoTags = extractProjectTags(filePath);

    // LOAD KEYWORDS ONCE


    const keywords = loadSovereignKeywords();

    const sourceId = crypto.createHash('md5').update(filePath).digest('hex');
    const timestamp = Date.now();
    const normalizedPath = filePath.replace(/\\/g, '/');

    let provenance: 'internal' | 'external' = 'external';
    if (normalizedPath.includes('/internal-inbox/') || normalizedPath.includes('sovereign/') || normalizedPath.includes('/inbox/')) {
        provenance = 'internal';
    } else if (normalizedPath.includes('/external-inbox/') || normalizedPath.includes('news_agent')) {
        provenance = 'external';
    }

    return rawAtoms.map((content, index) => {
        const idHash = crypto.createHash('sha256')
            .update(sourceId + index.toString() + content)
            .digest('hex')
            .substring(0, 16);

        // DYNAMIC SCAN: Check this specific atom's content for keywords
        const contentTags = scanForSovereignTags(content, keywords);
        let finalTags = [...new Set([...autoTags, ...contentTags])];

        // NEW: Generate Fingerprint (SimHash)
        let simhash = "0";
        if (native && native.fingerprint) {
            try {
                // Get BigInt from C++, convert to Hex String for JSON safety
                const bigHash = native.fingerprint(content);
                simhash = bigHash.toString(16);
            } catch (err) {
                console.error(`[Refiner] SimHash failed for atom ${index}`, err);
            }
        }

        // QUARANTINE HEURISTICS
        let atomProvenance: 'internal' | 'external' | 'quarantine' = provenance;

        // 1. "Processing..." Log Spam Detection
        // Surgeon V2 handled this upstream, so any surviving lines are likely intentional or deep inside code blocks.
        // We leave them as sovereign.

        // 2. Excessive File Path Lists (Generic)
        // If > 50% of lines look like file paths
        const lines = content.split('\n');
        const pathLines = lines.filter(l => l.includes('/') || l.includes('\\'));
        if (lines.length > 10 && (pathLines.length / lines.length > 0.6)) {
            // Slightly weaker check, so maybe just tag it for now unless it's obviously junk
            // atomProvenance = 'quarantine'; 
            // finalTags.push('#potential_junk'); 
        }

        return {
            id: `atom_${idHash}`,
            content: content,
            sourceId: sourceId,
            sourcePath: normalizedPath,
            sequence: index,
            timestamp: timestamp,
            provenance: atomProvenance,

            embedding: [],
            simhash: simhash,
            tags: finalTags
        };
    });
}

export async function enrichAtoms(atoms: Atom[]): Promise<Atom[]> {
    return atoms;
}
