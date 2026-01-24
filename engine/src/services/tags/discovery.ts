
import { db } from '../../core/db.js';
import { extractEntitiesWithGLiNER } from './gliner.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const MASTER_TAGS_PATH = path.join(PROJECT_ROOT, 'context', 'internal_tags.json');

/**
 * Discovery Service (The Teacher)
 * 
 * Implements "Tag Walker" Strategy (Standard 068 Phase B):
 * 1. Pick a seed tag from the master list.
 * 2. Find atoms that contain this tag ("Walking the Graph").
 * 3. Use BERT NER to find NEW entities in these specific contexts.
 * 4. Add new entities to the master list (Expansion).
 */
export async function runDiscovery(sampleSize: number = 30): Promise<string[]> {
    const masterTags = getMasterTags();
    let query = '';
    let strategy = 'random';
    let seedTag = '';

    // Strategy 1: The Walker (80% chance if we have tags)
    // "We have data specific tags... identified entities beyond the basic list that accommodate specific intricacies."
    if (masterTags.length > 0 && Math.random() > 0.2) {
        seedTag = masterTags[Math.floor(Math.random() * masterTags.length)];

        // Find atoms that contain the seed tag (Simulating Graph Walk)
        // We use the '~' operator for "contains text", which is efficient enough for now.
        // We limit to sampleSize to keep it fast.
        query = `
            ?[content] := *memory{content}, 
            content ~ $seedTag 
            :limit ${sampleSize}
        `;
        strategy = 'walker';
        console.log(`[Discovery] Teacher Mode (Walker): Expanding on seed tag '${seedTag}'...`);
    }
    // Strategy 2: The Explorer (Fallback / Initial Boot)
    else {
        query = `?[content] := *memory{content} :limit ${sampleSize}`;
        strategy = 'explorer';
        console.log(`[Discovery] Teacher Mode (Explorer): Random Sampling ${sampleSize} atoms...`);
    }

    let result;
    try {
        result = await db.run(query, { seedTag });
    } catch (e: any) {
        console.warn(`[Discovery] Query failed for strategy '${strategy}' (Seed: ${seedTag}):`, e.message);
        console.warn(`[Discovery] Falling back to safe Explorer mode.`);
        query = `?[content] := *memory{content} :limit ${sampleSize}`;
        result = await db.run(query);
    }

    if (!result.rows || result.rows.length === 0) {
        if (strategy === 'walker') {
            console.log(`[Discovery] Walker found no atoms for tag '${seedTag}'. It might be rare.`);
        } else {
            console.warn('[Discovery] No atoms found for learning.');
        }
        return [];
    }

    const sampledContent = result.rows.map((r: any) => {
        const content = String(r[0]);
        // Truncate to keep BERT fast
        return content.length > 500 ? content.substring(0, 500) : content;
    }).join('\n---\n');

    console.log(`[Discovery] Teacher analyzing ${result.rows.length} atoms via BERT...`);

    try {
        // 2a. Attempt Zero-Shot/BERT Extraction
        // We ask BERT to look for standard entities, but since the context is specific (seeded),
        // it is more likely to find domain-specific co-occurrences.
        const discoveredTags = await extractEntitiesWithGLiNER(sampledContent, [
            'person', 'organization', 'technology', 'project', 'software', 'location', 'concept'
        ]);

        console.log(`[Discovery] BERT found ${discoveredTags.length} potential tags.`);

        if (discoveredTags.length > 0) {
            // Filter out the seed tag so we don't just rediscover it
            const newTags = discoveredTags.filter(t => t.toLowerCase() !== seedTag.toLowerCase());

            if (newTags.length > 0) {
                console.log(`[Discovery] Expansion Successful! '${seedTag}' led to: ${newTags.slice(0, 5).join(', ')}...`);
                await updateMasterTags(newTags);
            }
            return newTags;
        } else {
            throw new Error("BERT found no entities.");
        }
    } catch (e: any) {
        console.warn(`[Discovery] Teacher (BERT) passed. Error: ${e.message}`);
        // Optional: LLM Fallback (Slow, but very smart)
        // For now, we return empty to stay fast/CPU-specific as requested.
        return [];
    }
}

/**
 * Updates the JSON master list with new findings.
 */
async function updateMasterTags(newTags: string[]) {
    try {
        let currentTags: any = { keywords: [] };

        // Ensure directory exists
        const contextDir = path.dirname(MASTER_TAGS_PATH);
        if (!fs.existsSync(contextDir)) {
            fs.mkdirSync(contextDir, { recursive: true });
        }

        // Read existing
        if (fs.existsSync(MASTER_TAGS_PATH)) {
            const content = fs.readFileSync(MASTER_TAGS_PATH, 'utf8');
            try {
                currentTags = JSON.parse(content);
                // Handle if it's just an array vs object
                if (Array.isArray(currentTags)) {
                    currentTags = { keywords: currentTags };
                }
            } catch (jsonErr) {
                console.warn('[Discovery] Corrupt tags file, starting fresh.');
            }
        }

        // Merge
        const existingSet = new Set(currentTags.keywords.map((t: string) => t.toLowerCase()));
        const added: string[] = [];

        newTags.forEach(tag => {
            const normalized = tag.toLowerCase().trim();
            if (normalized.length > 2 && !existingSet.has(normalized)) {
                // Basic filtering
                if (!['the', 'and', 'for', 'with'].includes(normalized)) {
                    currentTags.keywords.push(tag); // Keep original case
                    existingSet.add(normalized);
                    added.push(tag);
                }
            }
        });

        if (added.length > 0) {
            fs.writeFileSync(MASTER_TAGS_PATH, JSON.stringify(currentTags, null, 2));
            console.log(`[Discovery] Learned ${added.length} new tags:`, added.join(', '));
        }
    } catch (e) {
        console.error('[Discovery] Failed to update master list:', e);
    }
}

/**
 * Reads the master list for the Infector (and Walker).
 */
export function getMasterTags(): string[] {
    try {
        if (fs.existsSync(MASTER_TAGS_PATH)) {
            const content = fs.readFileSync(MASTER_TAGS_PATH, 'utf8');
            const data = JSON.parse(content);
            if (Array.isArray(data)) return data;
            if (data.keywords && Array.isArray(data.keywords)) return data.keywords;
        }
    } catch (e) {
        console.error('[Discovery] Failed to load master_tags.json:', e);
    }
    return [];
}
