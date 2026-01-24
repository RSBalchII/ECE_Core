/**
 * Tag Infection Service (The "Student")
 *
 * Implements Standard 068: Weak Supervision via High-Speed Pattern Matching.
 * Implements Standard 069: Functional Flow (Generators) for infinite scaling.
 */

import wink from 'wink-nlp';
import model from 'wink-eng-lite-web-model';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { db } from '../../core/db.js';

// Initialize the "Reflex" Engine (Fast CPU NLP)
// Cast to any to avoid strict typing issues with wink-nlp generic models
const nlp = wink(model) as any;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..', '..'); // engine/src/services/tags -> engine/src/services -> engine/src -> engine -> ROOT
const TAGS_FILE = path.join(PROJECT_ROOT, 'context', 'internal_tags.json');

/**
 * 1. The Generator (Source)
 * Lazily fetches atoms from the database in batches to prevent RAM spikes.
 * This replaces the need for recursion or massive array loading.
 */
async function* atomStream(batchSize = 500) {
    let lastId = '';

    while (true) {
        // Fetch next batch where ID > lastId
        const query = `
            ?[id, content, tags] := *memory{id, content, tags},
            id > $lastId,
            :order id
            :limit $limit
        `;

        const result = await db.run(query, { lastId, limit: batchSize });
        if (result.rows && result.rows.length > 0) {
            console.log(`[Infector] Stream fetched batch of ${result.rows.length} atoms...`);
        }

        if (!result.rows || result.rows.length === 0) {
            break; // Stream exhausted
        }

        // Yield one atom at a time (Functional Flow)
        for (const row of result.rows) {
            const [id, content, tags] = row;
            lastId = id as string; // Move cursor for next batch

            yield {
                id: id as string,
                content: content as string,
                tags: (tags as string[]) || []
            };
        }
    }
}

/**
 * 2. The Processor (Transform)
 * Applies "Viral Tags" to a single atom.
 */
function infectAtom(atom: { id: string, content: string, tags: string[] }, patterns: any): string[] | null {
    if (!atom.content) return null;

    const currentTags = new Set(atom.tags);
    let changed = false;

    // Use Wink-NLP to normalize text (case folding, tokenization)
    const doc = nlp.readDoc(atom.content);
    const text = (doc.out(nlp.its.text) as string).toLowerCase();

    // Fast check: Does text contain the pattern?
    patterns.keywords.forEach((keyword: string) => {
        if (!currentTags.has(keyword) && text.includes(keyword.toLowerCase())) {
            currentTags.add(keyword); // Infection!
            changed = true;
        }
    });

    // --- ENHANCEMENT: Temporal Auto-Tagging ---

    // 1. Years (1900 - 2099)
    // Regex matches 4 digits starting with 19 or 20, surrounded by boundaries
    const yearMatches = text.match(/\b((?:19|20)\d{2})\b/g);
    if (yearMatches) {
        yearMatches.forEach(year => (!currentTags.has(year)) && (currentTags.add(year), changed = true));
    }

    // 2. Months (Full Names)
    const months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ];

    // Simple inclusion check for months (since we normalized text to lowercase)
    // We check for word boundaries to avoid matching "may" inside "maybe"
    months.forEach(month => {
        // Create regex for word boundary match
        const regex = new RegExp(`\\b${month}\\b`, 'i');
        if (!currentTags.has(month) && regex.test(text)) {
            // Capitalize first letter for the tag
            const tag = month.charAt(0).toUpperCase() + month.slice(1);
            currentTags.add(tag);
            changed = true;
        }
    });

    return changed ? Array.from(currentTags) : null;
}

/**
 * 3. The Orchestrator (Sink)
 * Connects the Stream to the Processor.
 */
export async function runInfectionLoop() {
    console.log('🦠 Infection Protocol: Initializing...');

    // Load the "Virus" (Master Tag List)
    if (!fs.existsSync(TAGS_FILE)) {
        // Fallback check for alternate location (if running from dist/)
        console.warn(`🦠 No tag definitions found at ${TAGS_FILE}. Checking common paths...`);
        return;
    }

    const viralPatterns = JSON.parse(fs.readFileSync(TAGS_FILE, 'utf-8'));
    let infectedCount = 0;

    // The Loop (Looks clean, acts efficient)
    for await (const atom of atomStream()) {
        const newTags = infectAtom(atom, viralPatterns);

        if (newTags) {
            // Persist the infection
            // We update the 'tags' column. In Cozo, :update needs keys.
            // Using a retry loop to handle potential lock contention with Ingest
            let attempts = 0;
            const maxAttempts = 3;
            while (attempts < maxAttempts) {
                try {
                    await db.run(`
                        ?[id, tags] <- [[$id, $tags]]
                        :update memory {id, tags}
                    `, { id: atom.id, tags: newTags });

                    infectedCount++;
                    if (infectedCount % 100 === 0) process.stdout.write(`.`);
                    break; // Success
                } catch (error: any) {
                    attempts++;
                    if (attempts >= maxAttempts) {
                        console.warn(`[Infector] Failed to update atom ${atom.id} after ${maxAttempts} attempts:`, error.message);
                    } else {
                        // Small backoff
                        await new Promise(r => setTimeout(r, 100 * attempts));
                    }
                }
            }
        }
    }

    console.log(`\n🦠 Infection Complete. ${infectedCount} atoms infected with new context.`);
}
