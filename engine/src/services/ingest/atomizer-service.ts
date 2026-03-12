import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { Atom, Molecule, Compound } from '../../types/atomic.js';
import { 
  shouldUseStrictAtomSelection, 
  modulateTags,
  isEntityTag as isEntityByModulation
} from '../../utils/tag-modulation.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Native modules from @rbalchii packages (with fallbacks)
let wasmFingerprint: ((text: string) => string) | null = null;
let wasmSanitize: ((text: string) => string) | null = null;

try {
    const fp = await import('@rbalchii/anchor-fingerprint-wasm');
    wasmFingerprint = (text: string) => String(fp.fingerprint(text));
} catch { /* use JS fallback */ }

try {
    const atom = await import('@rbalchii/anchor-atomizer-wasm');
    wasmSanitize = atom.sanitize;
} catch { /* use JS fallback */ }

export class AtomizerService {

    /**
     * Tag blacklist patterns - prevents low-value tags from being stored
     * These patterns filter out noise at ingestion time
     */
    private static TAG_BLACKLIST_PATTERNS = [
        // Color codes (hex)
        /^#[0-9a-fA-F]{3,8}$/,
        
        // Pure numbers or too short
        /^#\d{1,3}$/,
        /^#_\w*$/,
        /^#__[\w\d_]+$/,
        
        // HTML/DOM artifacts
        /^#btn\b/, /^#class\b/, /^#div\b/, /^#id\b/,
        /^#span\b/, /^#href\b/, /^#src\b/,
        
        // Code artifacts
        /^#fn\b/, /^#elif\b/, /^#else\b/, /^#endif\b/,
        /^#ifdef\b/, /^#ifndef\b/, /^#include\b/,
        /^#define\b/, /^#pragma\b/,
        
        // Scraping artifacts
        /^#cite_note/, /^#cite_ref/, /^#amp_tf/,
        /^#details_of_atom/, /^#entry_lin/, /^#entry_links/,
        /^#opensearch_extension/, /^#extension_elements/,
        /^#simple_examples/, /^#query_interface/,
        /^#api_response/, /^#response_example/,
        /^#examples?$/, /^#overview$/, /^#preface$/,
        /^#appendix/, /^#appendices$/, /^#bib\b/, /^#ref\b/,
        
        // Error/artifact tags
        /^#incorrect_/, /^#error_/, /^#null\b/,
        /^#undefined\b/, /^#nan\b/,
        
        // Too generic
        /^#slow_pickup$/, /^#late_night$/, /^#early_morning$/,
        /^#monday\b/, /^#tuesday\b/, /^#wednesday\b/,
        /^#thursday\b/, /^#friday\b/, /^#saturday\b/,
        /^#sunday\b/, /^#manual\b/, /^#manually_/,
        /^#test_/, /^#tmp\b/, /^#temp\b/, /^#untagged$/,
        
        // Deprecated project names
        /^#agentgpt$/, /^#babyagi$/, /^#autogen$/, /^#chimaera$/,
        
        // System tags
        /^#manually_quarantined$/, /^#quarantined$/,
        /^#system$/, /^#internal$/, /^#external$/,

        // Test fixture tags (from unit test mock data bleeding into production)
        /^#tag\d*$/i,           // #Tag, #Tag1, #tag2
        /^#shared[a-z]$/i,      // #sharedA, #sharedB
        /^#word\d*$/i,          // #Word, #Word1
        /^#fixture/i,           // #fixture...
        /^#mock/i,              // #mock...
        /^#dummy/i,             // #dummy...
        /^#sample[a-z0-9]*$/i,  // #sample, #sampleA
    ];

    private static TAG_BLACKLIST_EXACT = new Set([
        '#_', '#0', '#1', '#2', '#3', '#4', '#5', '#6', '#7', '#8', '#9',
        '#00', '#000', '#0000', '#00000', '#000000',
    ]);

    /**
     * Check if a tag should be filtered out
     */
    private isBlacklistedTag(tag: string): boolean {
        if (!tag || typeof tag !== 'string') return true;

        const normalizedTag = tag.trim();

        if (AtomizerService.TAG_BLACKLIST_EXACT.has(normalizedTag)) {
            return true;
        }

        for (const pattern of AtomizerService.TAG_BLACKLIST_PATTERNS) {
            if (pattern.test(normalizedTag)) {
                return true;
            }
        }

        return false;
    }

    /**
     * Apply tag modulation to atom labels
     * Filters based on modulation level and blacklist strictness from user_settings.json
     */
    private applyTagModulation(atomLabels: string[]): string[] {
        if (!atomLabels || atomLabels.length === 0) return [];
        
        // Convert atom labels to tag format
        const rawTags = atomLabels.map(label => 
            label.startsWith('#') ? label : `#${label}`
        );
        
        // Apply modulation filtering
        return modulateTags(rawTags);
    }

    /**
     * Transient data patterns to exclude from ingestion
     * These patterns identify temporary/noisy content that clutters context
     */
    private static TRANSIENT_PATTERNS = [
        // Terminal error logs
        /Traceback \(most recent call last\)/i,
        /KeyError:/i,
        /TypeError:/i,
        /ValueError:/i,
        /Error:.*at line \d+/i,
        /Exception in thread/i,
        /Fatal error:/i,

        // Package installation logs
        /npm install/i,
        /pip install/i,
        /yarn add/i,
        /pnpm add/i,
        /Collecting [a-zA-Z0-9_-]+/i,  // pip "Collecting package"
        /Downloading [a-zA-Z0-9_-]+/i,  // pip "Downloading package"
        /added \d+ package/i,           // npm "added X packages"
        /Successfully installed/i,

        // Build artifacts
        /Build succeeded/i,
        /Build failed/i,
        /Compiling\.\.\./i,
        /Linking\.\.\./i,
        /Generating\.\.\./i,

        // Repetitive log noise
        /^\[\d{4}-\d{2}-\d{2}.*\]$/m,  // Standalone timestamp lines
        /^={50,}$/m,                    // Separator lines (====...)
        /^-{50,}$/m,                    // Separator lines (----...)
    ];

    /**
     * Check if content is transient/temporary data that should be excluded
     */
    private isTransientData(content: string): boolean {
        // Check if more than 50% of content matches transient patterns
        const lines = content.split('\n');
        if (lines.length < 5) return false; // Too short to be log output

        let transientLines = 0;
        for (const pattern of AtomizerService.TRANSIENT_PATTERNS) {
            for (const line of lines) {
                if (pattern.test(line)) {
                    transientLines++;
                    if (transientLines > lines.length * 0.5) {
                        return true; // More than 50% is transient
                    }
                }
            }
        }
        return false;
    }

    /**
     * Deconstructs raw content into Atomic Topology.
     * Returns the Compound (Main Body) and its Constituent Particles (Atoms/Molecules).
     */
    async atomize(
        content: string,
        sourcePath: string,
        provenance: 'internal' | 'external',
        fileTimestamp?: number
    ): Promise<{ compound: Compound, molecules: Molecule[], atoms: Atom[] } | null> {
        const filename = sourcePath.split(/[/\\]/).pop() || sourcePath;
        const contentSizeMB = (content.length / (1024 * 1024)).toFixed(2);
        const startTime = Date.now();

        // Check for transient data before processing
        if (this.isTransientData(content)) {
            console.log(`[Atomizer] ⚠️ SKIP: ${filename} - Transient data detected (error logs, install output, etc.)`);
            return null; // Skip ingestion entirely
        }

        // Note: System output (Anchor search results) is NOT skipped - it's cleaned during sanitization
        // The sanitization step removes score markers, system IDs, YAML formatting, etc.
        // Deduplication handles any remaining duplicates

        console.log(`[Atomizer] ⏱️ START: ${filename} (${contentSizeMB}MB)`);

        try {
            // 1. Sanitize (Iron Lung) - Chunked Strategy for Large Files
            // Optimized port of Refiner's Key Assassin
            // For very large files, we sanitize in chunks to avoid string length limits/OOM
            const sanitizeStart = Date.now();
            const CHUNK_SIZE = 1024 * 1024; // 1MB chunks
            let cleanContent = '';

            if (content.length > CHUNK_SIZE * 2) {
                // Generator approach for memory efficiency
                let chunkCount = 0;
                for (const chunk of this.chunkedSanitize(content, sourcePath, CHUNK_SIZE)) {
                    cleanContent += chunk;
                    chunkCount++;
                    if (chunkCount % 10 === 0) {
                        console.log(`[Atomizer] ⏱️ Sanitize chunk ${chunkCount}... (${((Date.now() - sanitizeStart) / 1000).toFixed(1)}s)`);
                    }
                    // Yield to event loop to keep server responsive
                    await new Promise(resolve => setImmediate(resolve));
                }
            } else {
                cleanContent = this.sanitize(content, sourcePath);
            }
            console.log(`[Atomizer] ⏱️ Sanitize complete: ${((Date.now() - sanitizeStart) / 1000).toFixed(2)}s`);

            // 2. Identification (Hash)
            const hashStart = Date.now();
            const compoundId = crypto.createHash('md5').update(cleanContent + sourcePath).digest('hex');
            const timestamp = fileTimestamp || Date.now();
            console.log(`[Atomizer] ⏱️ Hash complete: ${Date.now() - hashStart}ms`);

            // 3. System Atoms (Project/File Level)
            const systemAtoms = this.extractSystemAtoms(sourcePath);

            // 4. Construct Compound ID
            const fullCompoundId = `mem_${compoundId}`;

            // 5. Molecular Fission (Semantic Splitting)
            // Determine Type & Extract Data
            const splitStart = Date.now();
            const type = this.detectMoleculeType(cleanContent, sourcePath); // Determine main type

            // Pass type to optimize splitting strategy
            const moleculeParts = this.splitIntoMolecules(cleanContent, type);
            console.log(`[Atomizer] ⏱️ Split into ${moleculeParts.length} molecules: ${((Date.now() - splitStart) / 1000).toFixed(2)}s`);

            // 5. Molecular Enrichment (Granular Tagging & Typing)
            const enrichStart = Date.now();
            const molecules: Molecule[] = [];
            const allAtomsMap = new Map<string, Atom>();

            // Add System Atoms to global map
            systemAtoms.forEach(a => allAtomsMap.set(a.id, a));

            // Define maximum content length for individual molecules
            const MAX_MOLECULE_CONTENT_LENGTH = 500 * 1024; // 500KB limit

            // Timestamp Context: Start with file timestamp (modification time)
            // As we scan molecules, if we find a date in the content (e.g. log timestamp),
            // we update this context so subsequent atoms inherit it.
            let currentTimestamp = timestamp;
            const totalMolecules = moleculeParts.length;
            const progressInterval = Math.max(100, Math.floor(totalMolecules / 10)); // Log every 10% or every 100

            // Process molecules in batches to yield to event loop
            for (let i = 0; i < moleculeParts.length; i++) {
                const part = moleculeParts[i];
                const { content: text, start, end, timestamp: partTimestamp } = part;

                // Progress logging and yield every 100 molecules
                if (i % progressInterval === 0 && i > 0) {
                    const pct = ((i / totalMolecules) * 100).toFixed(0);
                    console.log(`[Atomizer] ⏱️ Enriching: ${pct}% (${i}/${totalMolecules}) - ${((Date.now() - enrichStart) / 1000).toFixed(1)}s`);
                }
                if (i % 100 === 0) {
                    await new Promise(resolve => setImmediate(resolve));
                }

                // Update time context if this part has a specific timestamp
                // Extract earliest timestamp from content for temporal ordering
                const extractedTs = this.extractEarliestTimestamp(text, currentTimestamp);
                if (extractedTs) {
                    currentTimestamp = extractedTs;
                }

                // Check content length and truncate if necessary
                let processedText = text;
                if (processedText.length > MAX_MOLECULE_CONTENT_LENGTH) {
                    console.warn(`[Atomizer] Molecule content exceeds maximum length (${processedText.length} chars), truncating...`);
                    processedText = processedText.substring(0, MAX_MOLECULE_CONTENT_LENGTH) + '... [TRUNCATED]';
                }

                // Scan for concepts in this specific molecule
                // PERFORMANCE: Skip for pure data rows (CSV lines) that have no prose
                // But keep scanning for conversational YAML which has semantic content
                const conceptAtoms = this.scanAtoms(processedText);
                const moleculeAtoms = [...systemAtoms, ...conceptAtoms];

                // Add concepts to global map
                conceptAtoms.forEach(a => allAtomsMap.set(a.id, a));

                const molId = `mol_${crypto.createHash('md5').update(compoundId + i + processedText).digest('hex').substring(0, 12)}`;

                // Re-Determine Type locally (e.g. code block in markdown)
                // Use the passed type as default, but refined per chunk if needed
                const molType = (type === 'prose' && (processedText.includes('```') || processedText.includes('function') || processedText.includes('const '))) ? 'code' : type;

                let numericVal: number | undefined = undefined;
                let numericUnit: string | undefined = undefined;

                if (molType === 'data') {
                    const data = this.extractNumericData(processedText);
                    if (data) {
                        numericVal = data.value;
                        numericUnit = data.unit;
                    }
                }

                molecules.push({
                    id: molId,
                    content: processedText,
                    atoms: moleculeAtoms.map(a => a.id),
                    sequence: i,
                    compoundId: fullCompoundId,

                    // Universal Coordinates
                    start_byte: start,
                    end_byte: end,

                    // Metadata
                    type: molType,
                    numeric_value: numericVal,
                    numeric_unit: numericUnit,
                    molecular_signature: this.generateSimHash(processedText),
                    timestamp: currentTimestamp,
                    // Apply tag modulation: filter blacklisted tags and apply modulation level
                    tags: this.applyTagModulation(moleculeAtoms.map(a => a.label)),
                    entities: {
                        people: moleculeAtoms.filter(a => ['#coda', '#rob', '#oliver'].includes(a.label.toLowerCase())).map(a => a.label),
                        concepts: moleculeAtoms.filter(a => a.type === 'concept').map(a => a.label),
                        projects: moleculeAtoms.filter(a => ['#project', '#engine', '#agent'].some(kw => a.label.toLowerCase().includes(kw))).map(a => a.label)
                    }
                });
            }
            console.log(`[Atomizer] ⏱️ Enrichment complete: ${((Date.now() - enrichStart) / 1000).toFixed(2)}s`);

            const allAtoms = Array.from(allAtomsMap.values());

            const compound: Compound = {
                id: fullCompoundId,
                compound_body: cleanContent,
                molecules: molecules.map(m => m.id),
                atoms: allAtoms.map(a => a.id),
                path: sourcePath,
                timestamp: fileTimestamp || timestamp, // Compound keeps file timestamp if provided
                provenance: provenance,
                molecular_signature: this.generateSimHash(cleanContent)
            };

            const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);
            console.log(`[Atomizer] ✅ COMPLETE: ${filename} (${contentSizeMB}MB) → ${molecules.length} molecules, ${allAtoms.length} atoms in ${totalTime}s`);

            return {
                compound,
                molecules,
                atoms: allAtoms
            };
        } catch (error: any) {
            console.error(`[Atomizer] FATAL ERROR processing ${sourcePath}:`, error.message);
            throw error;
        }
    }

    private *chunkedSanitize(text: string, filePath: string, chunkSize: number): Generator<string> {
        let offset = 0;
        while (offset < text.length) {
            let end = Math.min(offset + chunkSize, text.length);

            // Align to newline if not at the end
            if (end < text.length) {
                const nextNewline = text.indexOf('\n', end);
                if (nextNewline !== -1 && nextNewline < end + 1000) { // Don't drift too far
                    end = nextNewline + 1;
                }
            }

            const chunk = text.substring(offset, end);
            yield this.sanitize(chunk, filePath);
            offset = end;
        }
    }

    // --- PORTED LOGIC FROM REFINER.TS ---

    /**
     * Enhanced Content Sanitization (The Key Assassin)
     * Surgically removes JSON wrappers, log spam, and PII.
     */
    private sanitize(text: string, filePath: string = ''): string {
        let clean = text;

        // 1. Fundamental Normalization
        clean = clean.replace(/^\uFEFF/, '').replace(/[\u0000\uFFFD]/g, '');
        // Aggressive Newline Normalization: convert all \r\n and literal "\r\n" strings to real newlines
        clean = clean.replace(/\\r\\n/g, '\n').replace(/\r\n/g, '\n');

        // 2. Enhanced Surgeon: Log Spam Removal
        clean = clean.replace(/(?:^|\s|\.{3}\s*)Processing '[^']+'\.{3}/g, '\n');
        clean = clean.replace(/(?:^|\s|\.{3}\s*)Loading '[^']+'\.{3}/g, '\n');
        clean = clean.replace(/(?:^|\s|\.{3}\s*)Indexing '[^']+'\.{3}/g, '\n');
        clean = clean.replace(/(?:^|\s|\.{3}\s*)Analyzing '[^']+'\.{3}/g, '\n');

        // [NEW] Robust Processing Log Filter (for " - [TIMESTAMP] ... Processing ...")
        clean = clean.replace(/(?:^|\n)\s*-\s*\[\d{4}-\d{2}-\d{2}.*?\].*?Processing.*?(?:\n|$)/gi, '\n');

        // Strip Log Timestamps (at start of lines)
        clean = clean.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?\s*(?:AM|PM)?\s*[-:>]/gm, '');

        // Strip bracketed metadata like [2026-01-25...]
        clean = clean.replace(/\[\d{4}-\d{2}-\d{2}.*?\]/g, '');
        clean = clean.replace(/\[[#=]{0,10}\s{0,10}\]\s*\d{1,3}%/g, ''); // [===] 100%

        // 2.5 PII Masking
        clean = clean.replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, '[EMAIL_REDACTED]');
        clean = clean.replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, '[IP_REDACTED]');
        clean = clean.replace(/sk-[a-zA-Z0-9]{32,}/g, 'sk-[REDACTED]');

        // --- DENSITY-AWARE SCRUBBER (Standard 073) ---

        // 1. Strip "Dirty Read" Source Headers & Recursive Metadata
        // Matches: [Source: ...] or status: [Source: ...]
        clean = clean.replace(/(?:status:\s*)?\[Source: .*?\](?:\s*\(Timestamp: .*?\))?/g, '');

        // 2. Strip Logging/YAML/JSON Wrappers (Aggressive Pattern)
        // This targets the keys and the quotes around them, but leaves the content.
        const metaKeys = ['response_content', 'thinking_content', 'content', 'message', 'text', 'body', 'type', 'timestamp', 'source_path'];
        metaKeys.forEach(key => {
            // Match "key": " or key: |- or "key": |- etc.
            const regex = new RegExp(`["']?${key}["']?\\s*:\\s*(?:\\|-?|")?`, 'g');
            clean = clean.replace(regex, '');
        });

        // Strip trailing quotes and braces from JSON-like fragments
        clean = clean.replace(/"\s*,\s*"/g, '\n');
        clean = clean.replace(/"\s*}/g, '');
        clean = clean.replace(/{\s*"/g, '');

        // 3. Strip LLM Role Markers
        clean = clean.replace(/<\|user\|>/g, '');
        clean = clean.replace(/<\|assistant\|>/g, '');
        clean = clean.replace(/<\|system\|>/g, '');

        // 4. Strip Anchor System Output (prevent self-contamination)
        // Remove score markers from search results
        clean = clean.replace(/score:\s*\d+(?:\.\d+)?/g, '');
        // Remove virtual molecule IDs
        clean = clean.replace(/virtual_mem_[a-f0-9_]+/g, '');
        // Remove system memory IDs
        clean = clean.replace(/\bid:\s*["']?mem_[a-f0-9_]+["']?\s*,?/g, '');
        // Remove source path markers
        clean = clean.replace(/source:\s*["']?inbox\/[^"'\n]+["']?\s*,?/g, '');
        // Remove provenance markers
        clean = clean.replace(/provenance:\s*["']?(internal|external|quarantine)["']?\s*,?/g, '');
        // Remove bucket arrays
        clean = clean.replace(/buckets:\s*\[[\s\w,"']*\]\s*,?/g, '');
        // Remove epoch data
        clean = clean.replace(/epochs?:\s*['"]?[^,\n"']+['"]?\s*,?/g, '');
        // Remove timestamp fields from system output
        clean = clean.replace(/timestamp:\s*["']?[^"'\n]+["']?\s*,?/g, '');
        // Remove compound_id and byte range markers
        clean = clean.replace(/compound_id:\s*["']?[a-f0-9_]+["']?\s*,?/g, '');
        clean = clean.replace(/start_byte:\s*\d+\s*,?/g, '');
        clean = clean.replace(/end_byte:\s*\d+\s*,?/g, '');
        clean = clean.replace(/molecular_signature:\s*["']?[a-f0-9]+["']?\s*,?/g, '');
        clean = clean.replace(/is_inflated:\s*(true|false)\s*,?/g, '');

        // 5. Strip MCP/Agent Output Formatting
        // Remove YAML list markers from search results
        clean = clean.replace(/^\s*-\s*(id|source|score|content|tags|buckets|provenance):\s*/gm, '');
        // Remove YAML block markers
        clean = clean.replace(/^\s*\|\s*$/gm, '');
        // Remove code block wrappers (keep content)
        clean = clean.replace(/```yaml\s*/g, '');
        clean = clean.replace(/```\s*$/gm, '');
        // Remove emoji markers from system output
        clean = clean.replace(/🔍\s*|🤖\s*|⚙️\s*|✅\s*|❌\s*/g, '');

        // 6. Final Polish
        clean = clean.replace(/\n{3,}/g, '\n\n');

        return clean.trim();
    }

    /**
     * Helper: The Key Assassin
     * Recursively un-escapes and removes JSON wrappers.
     */
    private cleanseJsonArtifacts(text: string): string {
        let clean = text;

        // 1. Recursive Un-escape
        // DISABLED NATIVE CLEANSE due to stack overflow on deep nesting
        // if (native && native.cleanse) {
        //    clean = native.cleanse(clean);
        // } else {
        let pass = 0;
        while (clean.includes('\\') && pass < 3) {
            pass++;
            clean = clean.replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\t/g, '\t');
        }
        // }

        // 2. Code Block Protection
        const codeBlocks: string[] = [];
        const PLACEHOLDER = '___CODE_BLOCK_PLACEHOLDER___';
        clean = clean.replace(/```[\s\S]*?```/g, (match) => {
            codeBlocks.push(match);
            return `${PLACEHOLDER}${codeBlocks.length - 1}___`;
        });

        // 3. Remove Metadata & Wrappers
        const purge = (ptrn: RegExp) => { clean = clean.replace(ptrn, ''); };
        purge(/"type"\s*:\s*"[^"]*",?/g);
        purge(/"timestamp"\s*:\s*"[^"]*",?/g);
        purge(/"source"\s*:\s*"[^"]*",?/g);
        purge(/"response_content"\s*:\s*/g);
        purge(/"thinking_content"\s*:\s*/g);
        purge(/"content"\s*:\s*/g);

        // 4. Structural Cleanup
        clean = clean.replace(/\}\s*,\s*\{/g, '\n\n');
        clean = clean.trim();
        if (clean.startsWith('[') && clean.endsWith(']')) clean = clean.substring(1, clean.length - 1);

        // 5. Restore Code Blocks
        clean = clean.replace(/___CODE_BLOCK_PLACEHOLDER___(\d+)___/g, (_, idx) => codeBlocks[parseInt(idx)] || _);

        // 6. Slash Compressor
        clean = clean.replace(/\\{2,}/g, '/');

        return clean;
    }

    private extractSystemAtoms(filePath: string): Atom[] {
        const atoms: Atom[] = [];
        const normalized = filePath.replace(/\\/g, '/');
        const lowerPath = normalized.toLowerCase();
        const parts = normalized.split('/');

        // --- TIME-LADDER LOGIC ---
        // History/Archive gets down-weighted #Archive tag
        if (lowerPath.includes('/history/') || lowerPath.includes('/archive/')) {
            atoms.push(this.createAtom('#Archive', 'system', 0.5));
        }
        // Everything else is implicitly Current/Truth (Weight 1.0) unless specified otherwise

        // 1. Project Root & Structure (Auto-Tagging)
        const projectIndicators = ['codebase', 'projects', 'repos', 'src', 'packages', 'apps', 'personal', 'work', 'client'];

        for (let i = 0; i < parts.length; i++) {
            if (projectIndicators.includes(parts[i].toLowerCase()) && parts[i + 1]) {
                atoms.push(this.createAtom(`#project:${parts[i + 1]}`, 'system'));
                break;
            }
        }

        // Structure Tags
        if (normalized.includes('/src/') || normalized.startsWith('src/')) atoms.push(this.createAtom('#src', 'system'));
        if (normalized.includes('/docs/') || normalized.startsWith('docs/')) atoms.push(this.createAtom('#docs', 'system'));
        if (normalized.includes('/tests/') || normalized.startsWith('tests/')) atoms.push(this.createAtom('#test', 'system'));

        // File Type Tags
        const ext = normalized.split('.').pop()?.toLowerCase() || '';
        if (['ts', 'js', 'py', 'rs', 'go', 'java', 'cpp', 'c', 'h'].includes(ext)) atoms.push(this.createAtom('#code', 'system'));
        if (['md', 'txt', 'rst'].includes(ext)) atoms.push(this.createAtom('#doc', 'system'));
        if (['json', 'yaml', 'yml', 'xml'].includes(ext)) atoms.push(this.createAtom('#config', 'system'));

        return atoms;
    }

    private scanAtoms(content: string): Atom[] {
        const atoms: Atom[] = [];
        const strictMode = shouldUseStrictAtomSelection();

        // 1. Sovereign Keywords - OPTIMIZED with compiled regex
        const keywordRegex = this.getKeywordRegex();
        if (keywordRegex) {
            const lowerContent = content.toLowerCase();
            const matches = lowerContent.match(keywordRegex);
            if (matches) {
                // Use cached lowercase->original mapping
                const keywordMap = this.getKeywordMap();
                const seen = new Set<string>();
                for (const match of matches) {
                    const original = keywordMap.get(match);
                    if (original && !seen.has(original)) {
                        seen.add(original);
                        atoms.push(this.createAtom(`#${original}`, 'concept'));
                    }
                }
            }
        }

        // 2. Explicit Content Tags (#tag)
        const tagMatches = content.match(/#(\w+)/g);
        if (tagMatches) {
            const seen = new Set<string>();
            tagMatches.forEach(m => {
                const tag = m.toLowerCase();
                // In strict mode, filter out common words and low-value tags
                if (strictMode) {
                    const cleanTag = tag.replace(/^#/, '');
                    // Skip if too short, common word, or looks like noise
                    if (cleanTag.length < 3 || 
                        this.isCommonWord(cleanTag) || 
                        this.isBlacklistedTag(tag)) {
                        return;
                    }
                }
                if (!seen.has(tag)) {
                    seen.add(tag);
                    atoms.push(this.createAtom(m, 'concept'));
                }
            });
        }

        // Deduplicate locally
        const unique = new Map();
        atoms.forEach(a => unique.set(a.id, a));
        return Array.from(unique.values());
    }

    /**
     * Check if a word is a common word that should be filtered in strict mode
     */
    private isCommonWord(word: string): boolean {
        const commonWords = new Set([
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'which', 'who', 'whom', 'whose', 'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'can', 'just', 'now', 'then', 'here', 'there', 'if', 'as', 'but', 'or'
        ]);
        return commonWords.has(word.toLowerCase());
    }

    // Cache for keywords and compiled regex
    private cachedKeywords: string[] | null = null;
    private cachedKeywordRegex: RegExp | null = null;
    private cachedKeywordMap: Map<string, string> | null = null;

    private getKeywordRegex(): RegExp | null {
        if (this.cachedKeywordRegex !== null) return this.cachedKeywordRegex;
        const keywords = this.loadSovereignKeywords();
        if (keywords.length === 0) {
            return null;
        }
        // Escape regex special chars and join with | for single-pass matching
        const escaped = keywords.map(kw => kw.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
        this.cachedKeywordRegex = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');
        return this.cachedKeywordRegex;
    }

    private getKeywordMap(): Map<string, string> {
        if (this.cachedKeywordMap) return this.cachedKeywordMap;
        const keywords = this.loadSovereignKeywords();
        this.cachedKeywordMap = new Map();
        for (const kw of keywords) {
            this.cachedKeywordMap.set(kw.toLowerCase(), kw);
        }
        return this.cachedKeywordMap;
    }

    private loadSovereignKeywords(): string[] {
        if (this.cachedKeywords) return this.cachedKeywords;
        try {
            // Check likely locations for internal_tags.json
            const possiblePaths = [
                path.join(process.cwd(), 'engine', 'context', 'internal_tags.json'),
                path.join(process.cwd(), '..', 'engine', 'context', 'internal_tags.json'),
                // engine/src/services/ingest -> ../../../../engine/context
                path.join(__dirname, '../../../../engine/context/internal_tags.json'),
                // Fallback to old location
                path.join(process.cwd(), 'context', 'internal_tags.json')
            ];

            for (const p of possiblePaths) {
                if (fs.existsSync(p)) {
                    const content = fs.readFileSync(p, 'utf-8');
                    const json = JSON.parse(content);
                    if (Array.isArray(json.keywords)) {
                        this.cachedKeywords = json.keywords;
                        return json.keywords;
                    }
                }
            }
            this.cachedKeywords = [];
            return [];
        } catch (e) {
            console.error('[Atomizer] Failed to load internal_tags.json', e);
            return [];
        }
    }

    private createAtom(label: string, type: Atom['type'], weight: number = 1.0): Atom {
        return {
            id: `atom_${crypto.createHash('sha256').update(label).digest('hex').substring(0, 12)}`,
            label,
            type,
            weight
        };
    }

    /**
     * Splits content into molecules with byte offsets and extracted timestamps.
     * Enhanced with Type awareness (Prose vs Code vs Data).
     */
    private splitIntoMolecules(text: string, type: 'prose' | 'code' | 'data' = 'prose', maxSize: number = 1024): { content: string, start: number, end: number, timestamp?: number }[] {
        const results: { content: string, start: number, end: number, timestamp?: number }[] = [];

        // Helper to get UTF-8 byte length of a string
        const getByteLength = (str: string): number => {
            return Buffer.byteLength(str, 'utf8');
        };

        // Helper to convert string index to byte offset
        const stringIndexToByteOffset = (str: string, stringIndex: number): number => {
            if (stringIndex <= 0) return 0;
            if (stringIndex >= str.length) return getByteLength(str);
            return getByteLength(str.substring(0, stringIndex));
        };

        // Helper to extract FIRST timestamp from a chunk (legacy - used for molecule splitting)
        const extractTimestamp = (chunk: string): number | undefined => {
            // Match ISO timestamps: 2026-01-25T03:43:54.405Z or 2026-01-25 03:43:54
            const isoRegex = /\b(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?)\b/g;
            let match = isoRegex.exec(chunk);
            if (match) {
                const ts = Date.parse(match[1]);
                if (!isNaN(ts)) return ts;
            }

            // Match YYYY-MM-DD format (without time)
            const dateRegex = /\b(20[2-9]\d-\d{2}-\d{2})\b/;
            let match2 = chunk.match(dateRegex);
            if (match2) {
                const ts = Date.parse(match2[1]);
                if (!isNaN(ts)) return ts;
            }

            // Match MM/DD/YYYY or DD/MM/YYYY format
            const usDateRegex = /\b(\d{1,2}\/\d{1,2}\/\d{4})\b/;
            let match3 = chunk.match(usDateRegex);
            if (match3) {
                const ts = Date.parse(match3[1]);
                if (!isNaN(ts)) return ts;
            }

            // Match Month DD, YYYY format
            const monthDayYearRegex = /\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})\b/;
            let match4 = chunk.match(monthDayYearRegex);
            if (match4) {
                const [, month, day, year] = match4;
                const monthIndex = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December']
                    .indexOf(month);
                const date = new Date(parseInt(year), monthIndex, parseInt(day));
                if (!isNaN(date.getTime())) return date.getTime();
            }

            // Match DD Month YYYY format
            const dayMonthYearRegex = /\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b/;
            let match5 = chunk.match(dayMonthYearRegex);
            if (match5) {
                const [, day, month, year] = match5;
                const monthIndex = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December']
                    .indexOf(month);
                const date = new Date(parseInt(year), monthIndex, parseInt(day));
                if (!isNaN(date.getTime())) return date.getTime();
            }

            return undefined;
        };

        // --- STRATEGY: CODE (AST BLOCKS) ---
        if (type === 'code') {
            // "Heuristic AST": Split by top-level blocks (functions, classes) or chunks of logic.
            // Using regex to detect block starts and tracking braces.
            const lines = text.split('\n');
            let currentBlock = '';
            let blockStart = 0;
            let currentCursor = 0;

            let braceDepth = 0;

            for (const line of lines) {
                const lineWithNewline = line + '\n';
                const lineByteLen = getByteLength(lineWithNewline);
                const openBraces = (line.match(/\{/g) || []).length;
                const closeBraces = (line.match(/\}/g) || []).length;

                const prevDepth = braceDepth;
                braceDepth += (openBraces - closeBraces);

                currentBlock += lineWithNewline;

                // End of a top-level block?
                if (braceDepth === 0 && prevDepth > 0) {
                    // Just closed a root block (function/class)
                    results.push({ content: currentBlock, start: blockStart, end: currentCursor + lineByteLen, timestamp: extractTimestamp(currentBlock) });
                    currentBlock = '';
                    blockStart = currentCursor + lineByteLen;
                }
                // Double newline in root scope -> likely separate statements?
                else if (braceDepth === 0 && line.trim() === '' && currentBlock.trim().length > 0) {
                    results.push({ content: currentBlock, start: blockStart, end: currentCursor + lineByteLen, timestamp: extractTimestamp(currentBlock) });
                    currentBlock = '';
                    blockStart = currentCursor + lineByteLen;
                }

                currentCursor += lineByteLen;
            }

            if (currentBlock.trim().length > 0) {
                results.push({ content: currentBlock, start: blockStart, end: currentCursor, timestamp: extractTimestamp(currentBlock) });
            }
        }
        else if (type === 'data') {
            // --- STRATEGY: DATA (ROWS) ---
            // Split by line
            let cursor = 0;
            const lines = text.split('\n');
            for (const line of lines) {
                const lineWithNewline = line + '\n';
                const byteLen = getByteLength(lineWithNewline);
                if (line.trim().length > 0) {
                    // Store without the newline in content, but account for it in byte offsets
                    const lineByteLen = getByteLength(line);
                    results.push({ content: line, start: cursor, end: cursor + lineByteLen, timestamp: extractTimestamp(line) });
                }
                cursor += byteLen;
            }
        }
        else {
            // --- STRATEGY: PROSE (SENTENCES with MARKDOWN FISSION) ---

            // MARKDOWN FISSION: Split on code fences first to separate code from prose
            const codeFenceRegex = /```[\s\S]*?```/g;
            const codeFences: { match: string, stringIndex: number, startByte: number, endByte: number }[] = [];
            let fenceMatch;

            while ((fenceMatch = codeFenceRegex.exec(text)) !== null) {
                const startByte = stringIndexToByteOffset(text, fenceMatch.index);
                const endByte = stringIndexToByteOffset(text, fenceMatch.index + fenceMatch[0].length);
                codeFences.push({
                    match: fenceMatch[0],
                    stringIndex: fenceMatch.index,
                    startByte: startByte,
                    endByte: endByte
                });
            }

            // If we have code fences, split around them
            if (codeFences.length > 0) {
                let stringCursor = 0; // Track position in string indices
                let byteCursor = 0; // Track position in byte offsets

                for (const fence of codeFences) {
                    // Pre-fence prose
                    const fenceStringStart = fence.stringIndex;
                    if (fenceStringStart > stringCursor) {
                        const preProse = text.substring(stringCursor, fenceStringStart);
                        if (preProse.trim().length > 0) {
                            // Recursively split the prose portion into sentences
                            const proseParts = preProse.split(/(?<=[.!?])\s+(?=[A-Z])/);
                            let proseStringCursor = 0;
                            for (const part of proseParts) {
                                if (part.trim().length === 0) continue;
                                const partStringStart = preProse.indexOf(part, proseStringCursor);
                                if (partStringStart !== -1) {
                                    const partByteStart = byteCursor + stringIndexToByteOffset(preProse, partStringStart);
                                    const partByteEnd = partByteStart + getByteLength(part);
                                    results.push({ content: part, start: partByteStart, end: partByteEnd, timestamp: extractTimestamp(part) });
                                    proseStringCursor = partStringStart + part.length;
                                }
                            }
                        }
                    }

                    // The code fence itself (will be typed as 'code' in molecule enrichment)
                    results.push({ content: fence.match, start: fence.startByte, end: fence.endByte, timestamp: extractTimestamp(fence.match) });
                    stringCursor = fenceStringStart + fence.match.length;
                    byteCursor = fence.endByte;
                }

                // Post-fence prose (after last fence)
                if (stringCursor < text.length) {
                    const postProse = text.substring(stringCursor);
                    if (postProse.trim().length > 0) {
                        const proseParts = postProse.split(/(?<=[.!?])\s+(?=[A-Z])/);
                        let proseStringCursor = 0;
                        for (const part of proseParts) {
                            if (part.trim().length === 0) continue;
                            const partStringStart = postProse.indexOf(part, proseStringCursor);
                            if (partStringStart !== -1) {
                                const partByteStart = byteCursor + stringIndexToByteOffset(postProse, partStringStart);
                                const partByteEnd = partByteStart + getByteLength(part);
                                results.push({ content: part, start: partByteStart, end: partByteEnd, timestamp: extractTimestamp(part) });
                                proseStringCursor = partStringStart + part.length;
                            }
                        }
                    }
                }
            } else {
                // No code fences - standard sentence splitting
                const parts = text.split(/(?<=[.!?])\s+(?=[A-Z])/);
                let searchStringCursor = 0;

                for (const part of parts) {
                    if (part.trim().length === 0) continue;
                    const realStringStart = text.indexOf(part, searchStringCursor); // Find next occurrence

                    if (realStringStart !== -1) {
                        const realByteStart = stringIndexToByteOffset(text, realStringStart);
                        const realByteEnd = realByteStart + getByteLength(part);
                        results.push({ content: part, start: realByteStart, end: realByteEnd, timestamp: extractTimestamp(part) });
                        searchStringCursor = realStringStart + part.length;
                    }
                }
            }
        }

        // --- ENFORCE SIZE LIMIT (POST-PROCESS) ---
        const finalResults: { content: string, start: number, end: number, timestamp?: number }[] = [];

        for (const item of results) {
            const itemByteLen = getByteLength(item.content);
            if (itemByteLen <= maxSize) {
                finalResults.push(item);
            } else {
                // Force split large molecules by byte size
                let currentStart = item.start;
                let remaining = item.content;

                while (remaining.length > 0) {
                    // Find a safe split point that doesn't exceed maxSize bytes
                    let splitPoint = remaining.length;
                    let chunkByteLen = getByteLength(remaining);

                    // Binary search for the right split point if we're over the limit
                    if (chunkByteLen > maxSize) {
                        let low = 0;
                        let high = remaining.length;
                        while (low < high) {
                            const mid = Math.floor((low + high + 1) / 2);
                            const testChunk = remaining.substring(0, mid);
                            const testByteLen = getByteLength(testChunk);
                            if (testByteLen <= maxSize) {
                                low = mid;
                            } else {
                                high = mid - 1;
                            }
                        }
                        // Walk back to nearest newline to avoid splitting mid-line
                        let newlinePos = remaining.lastIndexOf('\n', low);
                        splitPoint = newlinePos > 0 ? newlinePos + 1 : low;
                    }

                    const chunk = remaining.substring(0, splitPoint);
                    const chunkBytes = getByteLength(chunk);

                    // Inherit timestamp for all chunks if the original item had one
                    finalResults.push({
                        content: chunk,
                        start: currentStart,
                        end: currentStart + chunkBytes,
                        timestamp: item.timestamp
                    });

                    remaining = remaining.substring(splitPoint);
                    currentStart += chunkBytes;
                }
            }
        }

        return finalResults;
    }

    private detectMoleculeType(text: string, filePath: string): 'prose' | 'code' | 'data' {
        // 1. File Extension hints
        if (filePath.endsWith('.csv') || filePath.endsWith('.json') || filePath.endsWith('.yaml') || filePath.endsWith('.yml')) return 'data';
        if (filePath.match(/\.(ts|js|py|rs|go|cpp|h|c)$/)) return 'code';

        // 2. Large file safety: treat files > 5MB as data to avoid regex timeout
        if (text.length > 5 * 1024 * 1024) {
            console.log(`[Atomizer] Large file (${(text.length / (1024 * 1024)).toFixed(1)}MB) - using data strategy for performance`);
            return 'data';
        }

        // 3. Content Heuristics
        if (text.trim().startsWith('|') && text.includes('|')) return 'data'; // Markdown Table row
        if (text.includes('```') || text.includes('function ') || text.includes('const ') || text.includes('import ')) return 'code';

        return 'prose';
    }

    /**
     * Extract earliest timestamp from content for temporal ordering
     * Scans for multiple timestamp formats and returns the earliest found
     */
    private extractEarliestTimestamp(chunk: string, fallbackTimestamp?: number): number {
        const timestamps: number[] = [];

        // ISO timestamps: 2026-01-25T03:43:54.405Z or 2026-01-25 03:43:54
        const isoRegex = /\b(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?)\b/g;
        let isoMatch;
        while ((isoMatch = isoRegex.exec(chunk)) !== null) {
            const ts = Date.parse(isoMatch[1]);
            if (!isNaN(ts)) timestamps.push(ts);
        }

        // YYYY-MM-DD
        const dateRegex = /\b(20[2-9]\d-\d{2}-\d{2})\b/g;
        let dateMatch;
        while ((dateMatch = dateRegex.exec(chunk)) !== null) {
            const ts = Date.parse(dateMatch[1]);
            if (!isNaN(ts)) timestamps.push(ts);
        }

        // MM/DD/YYYY or DD/MM/YYYY
        const usDateRegex = /\b(\d{1,2}\/\d{1,2}\/\d{4})\b/g;
        let usMatch;
        while ((usMatch = usDateRegex.exec(chunk)) !== null) {
            const ts = Date.parse(usMatch[1]);
            if (!isNaN(ts)) timestamps.push(ts);
        }

        // Return earliest timestamp found, or fallback
        if (timestamps.length > 0) {
            return Math.min(...timestamps);
        }
        return fallbackTimestamp || Date.now();
    }

    private extractNumericData(text: string): { value: number, unit?: string } | null {
        // Examples: "1500 PSI", "15%", "$10.50"
        const matches = text.match(/([\d,]+\.?\d*)\s?([A-Za-z%]+)?/g);
        if (!matches) return null;

        let bestCandidate: { value: number, unit?: string } | null = null;

        for (const m of matches) {
            const valStr = m.match(/[\d,]+\.?\d*/)?.[0]?.replace(/,/g, '');
            const unit = m.match(/[A-Za-z%]+/)?.[0];

            if (valStr) {
                const val = parseFloat(valStr);
                // Filter out likely years (1900-2100) if no unit, to avoid false positives in history
                if ((val >= 1900 && val <= 2100) && Number.isInteger(val) && !unit) continue;

                if (unit || !bestCandidate) {
                    bestCandidate = { value: val, unit: unit };
                }
            }
        }

        return bestCandidate;
    }

    private generateSimHash(text: string): string {
        // Use @rbalchii/anchor-fingerprint-wasm if available
        if (wasmFingerprint) {
            try {
                return wasmFingerprint(text);
            } catch { /* fall through to JS fallback */ }
        }

        // JS Fallback: Simple Jenkins Hash
        let hash = 0;
        if (text.length === 0) return "0";
        for (let i = 0; i < text.length; i++) {
            const char = text.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return Math.abs(hash).toString(16);
    }
}
