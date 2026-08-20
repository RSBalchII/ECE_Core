/**
 * Query Parser Module — "The Ears"
 *
 * NLP parsing, temporal extraction, query decomposition, and semantic expansion.
 * Extracted from search.ts to isolate natural language understanding
 * from the physics-based search core.
 */

import { db } from '../../core/db.js';
import { config } from '../../config/index.js';
import { expandTerms as semanticExpand, loadSynonymRing, isExpansionReady } from '@rbalchii/dse';
import wink from 'wink-nlp';
import model from 'wink-eng-lite-web-model';
import { getMasterTags } from '../tags/discovery.js';

// Initialize NLP (Fast CPU-based)
const nlp = wink(model);

// Initialize Semantic Expansion (Synonym Ring)
loadSynonymRing();

// Re-export NLP instance and expansion readiness for use by search orchestrator
export { nlp, isExpansionReady, semanticExpand };

/**
 * Fetch top tags from the system to ground the LLM's query expansion
 */
export async function getGlobalTags(limit: number = 50): Promise<string[]> {
    try {
        // Fetch unique tags from the tags table
        const query = `
        SELECT DISTINCT unnest(tags) as tag
        FROM atoms
        WHERE tags IS NOT NULL
        LIMIT $1
    `;
        const result = await db.run(query, [limit * 10]); // Get more than needed for filtering
        if (!result.rows) return [];

        const uniqueTags = (result.rows as any[])
            .map((r: any) => r.tag)
            .filter((t: any) => typeof t === 'string' && t.length > 0);
        return [...new Set(uniqueTags)].slice(0, limit);
    } catch (e) {
        console.error('[Search] Failed to fetch global tags:', e);
        return [];
    }
}

/**
 * Deterministic Query Expansion (No LLM)
 * Scans the user query for known tags from the master list.
 */
export async function expandQuery(originalQuery: string): Promise<string[]> {
    try {
        const globalTags = getMasterTags(); // This is synchronous file read
        const queryLower = originalQuery.toLowerCase();

        // Find tags specifically mentioned in the query or that substring match
        // Simple heuristic: if query contains the tag, we boost it.
        const foundTags = globalTags.filter(tag => {
            const tagLower = tag.toLowerCase();
            // Check for boundary matches or direct inclusion
            return queryLower.includes(tagLower);
        });

        if (foundTags.length > 0) {
            console.log(`[Search] Deterministically matched tags: ${foundTags.join(', ')}`);
        }
        return foundTags;
    } catch (e) {
        console.error('[Search] Expansion failed:', e);
        return [];
    }
}

/**
 * Helper to sanitize queries for FTS engine
 */
export function sanitizeFtsQuery(query: string): string {
    return query
        .replace(/[^a-zA-Z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();
}

/**
 * Expand camelCase and PascalCase identifiers into additional search terms.
 * e.g. "findAnchors" → ["findAnchors", "find", "Anchors", "anchors"]
 * Returned terms are de-duped and lowercased for FTS.
 */
export function expandCamelCase(terms: string[]): string[] {
    const expanded = new Set<string>();
    for (const term of terms) {
        expanded.add(term.toLowerCase());
        // Split on camelCase/PascalCase boundaries
        const parts = term
            .replace(/([a-z])([A-Z])/g, '$1 $2')   // camelCase → camel Case
            .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2') // acronym run: ABCDef → ABC Def
            .split(/\s+/)
            .filter(p => p.length > 1);
        for (const p of parts) {
            expanded.add(p.toLowerCase());
        }
    }
    return Array.from(expanded);
}

/**
 * Helper: Extract Temporal Context
 * Detects "last X months/years", year ranges, and returns a list of relevant year tags.
 */
export function extractTemporalContext(query: string): string[] {
    const now = new Date();
    const currentYear = now.getFullYear();
    const tags: Set<string> = new Set();
    const MAX_TEMPORAL_AMOUNT = 100;

    // Regex for "last X months/years"
    const match = query.match(/last\s+(\d+)\s+(months?|years?|days?)/i);
    if (match) {
        let amount = parseInt(match[1]);
        const unit = match[2].toLowerCase();

        // Security: Cap the amount to prevent loop exhaustion DoS
        if (amount > MAX_TEMPORAL_AMOUNT) {
            amount = MAX_TEMPORAL_AMOUNT;
        }

        tags.add(currentYear.toString()); // Always include current year

        if (unit.startsWith('year')) {
            for (let i = 1; i <= amount; i++) {
                tags.add((currentYear - i).toString());
            }
        } else if (unit.startsWith('month')) {
            // If subtracting months goes back to prev year
            const pastDate = new Date(now);
            pastDate.setMonth(now.getMonth() - amount);
            const pastYear = pastDate.getFullYear();
            if (pastYear < currentYear) {
                for (let y = pastYear; y < currentYear; y++) tags.add(y.toString());
            }
        }
    }

    // Detect year ranges like "from 2025 to 2026" or "between 2024 and 2025"
    const rangeMatch = query.match(/\b(from|between)\s+(\d{4})\s+(to|and)\s+(\d{4})\b/i);
    if (rangeMatch) {
        const startYear = parseInt(rangeMatch[2]);
        const endYear = parseInt(rangeMatch[4]);
        // Add all years in the range
        for (let year = Math.min(startYear, endYear); year <= Math.max(startYear, endYear); year++) {
            tags.add(year.toString());
        }
    }

    // Also detect explicit years (2020-2030)
    const yearMatch = query.match(/\b(202[0-9]|203[0-9])\b/g);
    if (yearMatch) {
        yearMatch.forEach(y => tags.add(y));
    }

    return Array.from(tags);
}

/**
 * Natural Language Parser (Standard 070 - Enhanced)
 * Uses NLP to extract "Meaningful Tags" including Temporal Context.
 * Enhanced to handle conversational queries of any size.
 */
export function parseNaturalLanguage(query: string): string {
    // 1. Extract Temporal Context
    const timeTags = extractTemporalContext(query);

    // 2. Handle conversational queries by extracting key entities and concepts
    // For very long queries, we want to identify the most important terms
    const queryLength = query.trim().split(/\s+/).length;

    let tokens: string[] = [];

    if (queryLength > 10) {
        // For longer conversational queries, use more sophisticated extraction
        tokens = extractKeyTermsFromConversation(query);
    } else {
        // For shorter queries, use the original approach
        const doc = nlp.readDoc(query);

        tokens = doc.tokens().filter((t: any) => {
            const tag = t.out(nlp.its.pos);
            const text = t.out().toLowerCase();

            // Whitelist specific domain words that might get misclassified or filtered
            // Uses Config-based whitelist or falls back to defaults (v5.2.0+: also supports DB via search.whitelist)
            const whitelist = config.SEARCH?.whitelist || ['burnout', 'career', 'decision', 'pattern', 'impact'];
            if (whitelist.some((w: string) => text.includes(w))) return true;

            return tag === 'NOUN' || tag === 'PROPN' || tag === 'ADJ' || tag === 'VERB';
        }).out((nlp as any).its.text);
    }

    // Combine with temporal tags
    const uniqueTokens = new Set([...tokens, ...timeTags]);

    if (uniqueTokens.size > 0) {
        return Array.from(uniqueTokens).join(' ').toLowerCase();
    }

    return sanitizeFtsQuery(query);
}

/**
 * Extract key terms from conversational queries
 * Identifies important nouns, proper nouns, adjectives, and verbs while preserving context
 */
export function extractKeyTermsFromConversation(conversation: string): string[] {
    const doc = nlp.readDoc(conversation);

    // Extract named entities (people, places, organizations)
    const entities: string[] = doc.entities().out((nlp as any).its.normal);

    // Extract important tokens (nouns, proper nouns, adjectives, verbs)
    const importantTokens: string[] = doc.tokens().filter((t: any) => {
        const tag = t.out(nlp.its.pos);
        const text = t.out().toLowerCase();

        // Include named entities
        if (entities.includes(text)) return true;

        // Include important POS tags
        return tag === 'NOUN' || tag === 'PROPN' || tag === 'ADJ' || tag === 'VERB';
    }).out((nlp as any).its.normal);

    // Combine and deduplicate
    const allTerms: string[] = [...new Set([...entities, ...importantTokens])];

    // Filter out common stop words that might have slipped through
    const stopWords = new Set([
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'can', 'shall', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
        'what', 'which', 'who', 'when', 'where', 'why', 'how', 'whose', 'whom',
    ]);

    return allTerms.filter(term => !stopWords.has(term.toLowerCase()) && term.length > 2);
}

/**
 * Split a query into sentence-like chunks (molecules)
 */
export function splitQueryIntoMolecules(query: string): string[] {
    // First, clean the query of any extraneous characters or formatting
    let cleanQuery = query.trim();

    // Remove common prefixes/suffixes that might interfere with sentence detection
    cleanQuery = cleanQuery.replace(/^[#\-\*\s]+|[#\-\*\s]+$/g, '').trim();

    // Split by sentence endings first (periods, exclamation marks, question marks)
    let sentences = cleanQuery.split(/(?<=[.!?])\s+/);

    // If no sentence endings found, try to split by commas or other separators
    if (sentences.length <= 1) {
        sentences = cleanQuery.split(/(?<=[,;:])\s+/);
    }

    // If still no good splits, split by word count (about 10-15 words per chunk)
    if (sentences.length <= 1) {
        const words = cleanQuery.split(/\s+/);
        const chunks: string[] = [];
        const chunkSize = 15; // About 15 words per "molecule"

        for (let i = 0; i < words.length; i += chunkSize) {
            const chunk = words.slice(i, i + chunkSize).join(' ');
            if (chunk.trim()) {
                chunks.push(chunk);
            }
        }

        return chunks.length > 0 ? chunks : [cleanQuery];
    }

    // Clean up the sentences
    return sentences
        .map(s => s.trim())
        .filter(s => s.length > 0);
}

export function parseQuery(query: string): { phrases: string[]; temporal: string[]; buckets: string[]; keywords: string[]; } {
    const result = { phrases: [] as string[], temporal: [] as string[], buckets: [] as string[], keywords: [] as string[] };
    const phraseRegex = /"([^"]+)"/g;
    let phraseMatch;
    while ((phraseMatch = phraseRegex.exec(query)) !== null) result.phrases.push(phraseMatch[1]);
    let remainingQuery = query.replace(/"[^"]+"/g, '');
    const temporalRegex = /@(\w+)/g;
    let temporalMatch;
    while ((temporalMatch = temporalRegex.exec(remainingQuery)) !== null) result.temporal.push(temporalMatch[1]);
    remainingQuery = remainingQuery.replace(/@\w+/g, '');
    const bucketRegex = /#(\w+)/g;
    let bucketMatch;
    while ((bucketMatch = bucketRegex.exec(remainingQuery)) !== null) result.buckets.push(bucketMatch[1]);
    remainingQuery = remainingQuery.replace(/#\w+/g, '');
    result.keywords = remainingQuery.split(/\s+/).filter(kw => kw.length > 0);
    return result;
}

/**
 * Conversational Query Expansion (Standard 086)
 * Expands natural language queries into semantic equivalents
 */
export function expandConversationalQuery(query: string): string[] {
    const expansions: string[] = [];

    // Common conversational patterns
    const patterns = [
        { pattern: /what is the (latest|current|recent) (.+)/i, replacement: '$2' },
        { pattern: /tell me about (.+)/i, replacement: '$1' },
        { pattern: /how is (.+) doing/i, replacement: '$1' },
        { pattern: /what's happening with (.+)/i, replacement: '$1' },
        { pattern: /what do you know about (.+)/i, replacement: '$1' },
        { pattern: /explain (.+)/i, replacement: '$1' },
        { pattern: /describe (.+)/i, replacement: '$1' },
        { pattern: /summarize (.+)/i, replacement: '$1' },
    ];

    for (const p of patterns) {
        const match = query.match(p.pattern);
        if (match) {
            const expanded = query.replace(p.pattern, p.replacement).trim();
            if (expanded && !expansions.includes(expanded)) {
                expansions.push(expanded);
            }
        }
    }

    return expansions;
}

/**
 * Get related tags for a given query to provide semantic serendipity
 * This function finds tags that are semantically related to the query terms
 */
export async function getRelatedTagsForQuery(query: string, maxTags: number = 5): Promise<string[]> {
    try {
        // Get all tags from the system
        const allTags = await getGlobalTags(100); // Get top 100 tags

        // Get the query terms to match against
        const queryTerms = query.toLowerCase().split(/\s+/).filter(term => term.length > 0);

        // If no query terms, return empty array
        if (queryTerms.length === 0) {
            return [];
        }

        // Find tags that are related to the query terms
        const relatedTags: { tag: string; score: number }[] = [];

        for (const tag of allTags) {
            if (typeof tag !== 'string') continue;
            const tagLower = tag.toLowerCase();
            let score = 0;

            // Increase score if tag contains or is similar to query terms
            for (const term of queryTerms) {
                if (tagLower.includes(term) || term.includes(tagLower)) {
                    score += 10; // Direct match gets high score
                } else if (tagLower.startsWith(term) || tagLower.endsWith(term)) {
                    score += 5; // Partial match gets medium score
                }
                // Additional heuristics could be added here
            }

            if (score > 0) {
                relatedTags.push({ tag, score });
            }
        }

        // Sort by score and return top tags
        relatedTags.sort((a, b) => b.score - a.score);

        return relatedTags.slice(0, maxTags).map(item => item.tag);
    } catch (error) {
        console.error('[Search] Error getting related tags:', error);
        // Return empty array if there's an error
        return [];
    }
}
