/**
 * Tag Infector Service - Phase 21: Weak Supervision Loop
 * 
 * Implements Standard 068: "Discover with LLM, Infect with CPU".
 */

import winkNLP from 'wink-nlp';
import model from 'wink-eng-lite-web-model';
import { db } from '../../core/db.js';
import { runSideChannel } from '../llm/provider.js';

const nlp = winkNLP(model);
const its = nlp.its;

export interface InfectionResult {
    discoveredTags: string[];
    atomsInfected: number;
    durationMs: number;
}

/**
 * Discovery Mode: Samples atoms and uses LLM to extract potential master tags.
 */
export async function runDiscovery(sampleSize: number = 20): Promise<string[]> {
    console.log(`[Infector] Discovery Mode: Sampling ${sampleSize} atoms...`);

    // Sample diverse atoms
    const query = `?[content] := *memory{content} :limit ${sampleSize}`;
    const result = await db.run(query);

    if (!result.rows || result.rows.length === 0) {
        console.warn('[Infector] No atoms found for discovery.');
        return [];
    }

    const sampledContent = result.rows.map((r: any) => r[0]).join('\n---\n');

    const prompt = `
Extract a list of highly specific entities (names, places, unique terms, pet names) from the following text atoms. 
Return ONLY a JSON array of strings. Do not include categories or explanation.
Example Output: ["Dory", "Jade", "Buster", "ECE_Core", "CozoDB"]

Text:
${sampledContent}
`;

    const response = await runSideChannel(prompt, "You are a precise entity extraction engine. Output JSON only.") as string;

    if (!response) {
        console.error('[Infector] LLM failed to respond during discovery.');
        return [];
    }

    try {
        // Find JSON array in response
        const jsonMatch = response.match(/\[.*\]/s);
        const tags = jsonMatch ? JSON.parse(jsonMatch[0]) : [];
        console.log(`[Infector] Discovered ${tags.length} potential tags: ${tags.join(', ')}`);
        return tags;
    } catch (e) {
        console.error('[Infector] Failed to parse LLM discovery response:', e);
        return [];
    }
}

/**
 * Infection Mode: Scans the entire memory table and applies tags via high-speed NLP.
 */
export async function runInfection(masterTags: string[]): Promise<InfectionResult> {
    const startTime = Date.now();
    console.log(`[Infector] Infection Mode: Spreading ${masterTags.length} tags across the graph...`);

    if (masterTags.length === 0) {
        return { discoveredTags: [], atomsInfected: 0, durationMs: 0 };
    }

    // Load all atoms from memory
    const query = '?[id, content, tags] := *memory{id, content, tags}';
    const result = await db.run(query);

    let infectedCount = 0;
    const updates: [string, string[]][] = [];

    for (const row of result.rows) {
        const [id, content, existingTags] = row;
        const doc = nlp.readDoc(content as string);
        const currentTags = new Set(existingTags as string[]);
        let changed = false;

        for (const tag of masterTags) {
            // Case-insensitive match using string include as primary (speed)
            // and NLP for token-based refinement if needed.
            if (content.toLowerCase().includes(tag.toLowerCase())) {
                // Secondary check: ensure it's a "word" match or significant match
                const tokens = doc.tokens().filter((t: any) => t.out(its.value).toLowerCase() === tag.toLowerCase());
                if (tokens.length() > 0 && !currentTags.has(tag)) {
                    currentTags.add(tag);
                    changed = true;
                }
            }
        }

        if (changed) {
            updates.push([id as string, Array.from(currentTags)]);
            infectedCount++;
        }
    }

    // Bulk update infected atoms
    if (updates.length > 0) {
        console.log(`[Infector] Applying infection to ${updates.length} atoms...`);
        const batchSize = 100;
        for (let i = 0; i < updates.length; i += batchSize) {
            const batch = updates.slice(i, i + batchSize);
            const idBatchRows = batch.map(b => [b[0]]);

            const fullDataQuery = `
                ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] <- $ids
                *memory{id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}
            `;
            const fullDataResult = await db.run(fullDataQuery, { ids: idBatchRows });

            const finalUpdateData = fullDataResult.rows.map((row: any) => {
                const id = row[0];
                const newTags = batch.find(b => b[0] === id)![1];
                const updatedRow = [...row];
                updatedRow[10] = newTags; // index 10 is tags
                return updatedRow;
            });

            await db.run(`
                ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] <- $data
                :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}
            `, { data: finalUpdateData });
        }
    }

    const duration = Date.now() - startTime;
    console.log(`[Infector] Infection complete. ${infectedCount} atoms updated in ${duration}ms.`);

    return {
        discoveredTags: masterTags,
        atomsInfected: infectedCount,
        durationMs: duration
    };
}

/**
 * The Full Loop: Discover and Infect in one go.
 */
export async function runFullInfectionCycle(): Promise<InfectionResult> {
    const discoveredTags = await runDiscovery();
    return await runInfection(discoveredTags);
}
