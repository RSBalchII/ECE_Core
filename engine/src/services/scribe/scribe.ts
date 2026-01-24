/**
 * Scribe Service - Markovian Rolling Context
 *
 * Maintains a "Session State" that summarizes the current conversation.
 * This enables the model to maintain coherence across long conversations
 * without requiring the full history in context.
 */

import { db } from '../../core/db.js';

// Lazy-load inference to avoid circular dependency
let inferenceModule: any = null;
function getInference() {
    if (!inferenceModule) {
        inferenceModule = require('../inference/inference');
    }
    return inferenceModule;
}

const SESSION_STATE_ID = 'session_state';
const STATE_BUCKET = ['system', 'state'];

interface HistoryItem {
    role: string;
    content: string;
}

interface UpdateStateResult {
    status: string;
    summary?: string;
    message?: string;
}

interface ClearStateResult {
    status: string;
    message?: string;
}

/**
 * Updates the rolling session state based on recent conversation history.
 * Uses the LLM to compress recent turns into a coherent state summary.
 *
 * @param {HistoryItem[]} history - Array of {role, content} message objects
 * @returns {Promise<UpdateStateResult>} - {status, summary} or {status, error}
 */
export async function updateState(history: HistoryItem[]): Promise<UpdateStateResult> {
    console.log('✍️ Scribe: Analyzing conversation state...');

    try {
        // 1. Flatten last 10 turns into readable text
        const recentTurns = history.slice(-10);
        const recentText = recentTurns
            .map(m => `${m.role.toUpperCase()}: ${m.content}`)
            .join('\n\n');

        if (!recentText.trim()) {
            return { status: 'skipped', message: 'No conversation history to analyze' };
        }

        // 2. Construct the state extraction prompt
        const prompt = `Analyze this conversation segment and produce a concise "Session State" summary.

Keep it under 200 words. Focus on:
- Current Goal: What is the user trying to accomplish?
- Key Decisions: What has been decided or agreed upon?
- Active Tasks: What work is in progress or pending?
- Important Context: What background information is critical to remember?

Conversation:
${recentText}

---
Session State Summary:`;

        // 3. Generate the state summary
        const inf = getInference();
        const summary = await inf.rawCompletion(prompt);

        if (!summary || summary.trim().length < 10) {
            return { status: 'error', message: 'Failed to generate meaningful state' };
        }

        // 4. Persist to database with special ID
        const timestamp = Date.now();
        const query = `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] <- $data :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}`;

        await db.run(query, {
            data: [[
                SESSION_STATE_ID,
                timestamp,
                summary.trim(),
                'Scribe',
                SESSION_STATE_ID, // source_id
                0, // sequence
                'state', // type
                `state_${timestamp}`, // hash
                STATE_BUCKET,
                [], // epochs
                [], // tags
                'system', // provenance
                '0', // simhash
                new Array(768).fill(0.0) // embedding (stub)
            ]]
        });

        console.log('✍️ Scribe: State updated successfully');
        return { status: 'updated', summary: summary.trim() };

    } catch (e: any) {
        console.error('✍️ Scribe Error:', e.message);
        return { status: 'error', message: e.message };
    }
}

/**
 * Retrieves the current session state from the database.
 *
 * @returns {Promise<string | null>} - The state summary or null if not found
 */
export async function getState(): Promise<string | null> {
    try {
        const query = '?[content] := *memory{id: mem_id, content}, mem_id == $id';
        const res = await db.run(query, { id: SESSION_STATE_ID });

        if (res.rows && res.rows.length > 0) {
            return res.rows[0][0] as string;
        }
        return null;
    } catch (e: any) {
        console.error('✍️ Scribe: Failed to retrieve state:', e.message);
        return null;
    }
}

/**
 * Clears the current session state.
 * Useful for starting a fresh conversation.
 *
 * @returns {Promise<ClearStateResult>} - {status}
 */
export async function clearState(): Promise<ClearStateResult> {
    try {
        const query = `?[id] <- [[$id]] :delete memory {id}`;
        await db.run(query, { id: SESSION_STATE_ID });
        console.log('✍️ Scribe: State cleared');
        return { status: 'cleared' };
    } catch (e: any) {
        console.error('✍️ Scribe: Failed to clear state:', e.message);
        return { status: 'error', message: e.message };
    }
}